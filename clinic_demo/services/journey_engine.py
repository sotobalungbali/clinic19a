"""Single journey dispatcher. Existing generators are business adapters, not engines."""
import json
import traceback
from odoo import fields
from odoo.exceptions import UserError
from .journey_registry import ordered_journeys, SOURCE_FAMILIES
from .scenario_registry import ScenarioRegistry
from .telemedicine_scope import prepare_telemedicine_scope
from .journey_read_context import read_model, actor_key
from .execution_engine import DemoExecutionEngine
from ..models.demo_journey import JOURNEY_TOKEN

class ReadOnlyEvidence(Exception):
    def __init__(self, result):
        self.result = result

SOURCE_PREFIXES = {
    'FIN-INS': ('DEMO-SOURCE-POLICY-', 'DEMO-SOURCE-AUTH-'),
    'OPS-MEM': ('DEMO-SOURCE-MEMBER-',),
    'OPS-INV': ('DEMO-SOURCE-CATEGORY-', 'DEMO-SOURCE-STOCK-', 'DEMO-SOURCE-RECEIPT-', 'DEMO-SOURCE-USAGE-', 'DEMO-SOURCE-CONSUMPTION-'),
    'OPS-WALLET': ('DEMO-SOURCE-WALLET-', 'DEMO-SOURCE-TOPUP-'),
    'CLN-PROC': ('DEMO-SOURCE-PROC-',),
}

class JourneyEngine:
    def __init__(self, env):
        self.env = env
        self.specs = ordered_journeys()
        self.by_key = {spec.key:spec for spec in self.specs}
        self.kernel = DemoExecutionEngine(env)
        self.Rows = env['clinic.demo.journey'].with_context(_clinic_journey_token=JOURNEY_TOKEN)

    def sync(self, run):
        rows = self.Rows.search([('run_id','=',run.id)])
        by_key = {row.journey_key:row for row in rows}
        for index,spec in enumerate(self.specs,1):
            values = dict(name=spec.name,sequence=index,owner_addon=spec.owner,
                          primary_model=spec.primary_model,master_prompt=spec.master_prompt,
                          dependencies=', '.join(spec.dependencies),contract=json.dumps({
                              'models':spec.models,'expected_records':spec.expected_records,'generation':spec.generation_callable,
                              'validation_callable':spec.validation_callable,'reconciliation':'JourneyEngine.inspect + validate_owner',
                              'identity':spec.identity_policy,'scope':spec.scope_policy,
                              'workflow':spec.workflow_policy,'validation':spec.validation_policy,
                              'reset':spec.reset_policy,'idempotency':spec.idempotency_policy},sort_keys=True))
            if spec.key not in by_key:
                by_key[spec.key] = self.Rows.create(dict(values,run_id=run.id,journey_key=spec.key))
            else:
                # Registry metadata is immutable for a build. Avoid 137
                # tracked writes on every Execute Next request when nothing
                # changed; this keeps the bounded runner inside HTTP limits.
                row = by_key[spec.key]
                if any(((row[field] or '') != value) if isinstance(value,str)
                       else row[field] != value for field,value in values.items()):
                    row.write(values)
        return by_key

    def references(self, run, spec):
        refs = run.reference_ids
        if spec.family=='population':
            from .population_plan import prefix
            tag='DEMO-POP-SETUP-' if spec.key=='population.setup' else prefix(spec.key.split('.')[1],int(spec.key.split('.')[2][1:]))+'-'
            return refs.filtered(lambda row:row.generator_key=='management.reports' and row.demo_key.startswith(tag))
        if spec.family:
            return refs.filtered(lambda row:row.generator_key=='management.reports' and row.demo_key.startswith(SOURCE_PREFIXES[spec.family]))
        return refs.filtered(lambda row:row.generator_key==spec.key and not (spec.key=='management.reports' and row.demo_key.startswith(('DEMO-SOURCE-','DEMO-POP-'))))

    def source(self, run):
        from ..generators.management.reports import ManagementReportsGenerator
        from ..generators.management.source_journeys import ReportSourceJourneys
        owner = ManagementReportsGenerator()
        ctx = self.kernel._context(run, ScenarioRegistry.get('SCN-REPORT-01'))
        manager = owner._resolve(ctx, 'DEMO-USER-MGR', 'res.users')
        return ReportSourceJourneys(owner, ctx, manager)

    def population(self,run,spec):
        from .population_service import PopulationService
        return PopulationService(self.source(run),spec.key)

    def validate_owner(self, run, spec):
        # Always roll back validator side effects. Only evidence outside this
        # savepoint is persisted by reconciliation, never business corrections.
        try:
            with self.env.cr.savepoint():
                if spec.family=='population':
                    result=self.population(run,spec).validate()
                elif spec.family:
                    result = self.source(run).validate(families={spec.family}) or []
                else:
                    scenario = ScenarioRegistry.get(spec.generator.scenario_keys[0])
                    from ..generators.base import BaseDemoGenerator
                    if spec.generator.validate is BaseDemoGenerator.validate:
                        raise UserError('No semantic validation adapter is implemented')
                    result = spec.generator().validate(self.kernel._context(run,scenario),scenario) or []
                raise ReadOnlyEvidence(result)
        except ReadOnlyEvidence as proof:
            return proof.result

    def inspect(self, run, spec):
        refs = self.references(run,spec)
        evidence=[]; blocked=[]; issues=[]; notes=[]; existing=0; missing=0; duplicates=0
        expected_keys=None
        if spec.family=='population':
            expected_keys=set(self.population(run,spec).expected_reference_keys())
        referenced_keys=set(refs.mapped('demo_key')) if hasattr(refs,'mapped') else {ref.demo_key for ref in refs}
        if expected_keys is not None:
            missing += len(expected_keys-referenced_keys)
        for ref in refs:
            item={'model':ref.model_name,'business_key':ref.demo_key,'owner':ref.ownership_kind,'candidates':0}
            try:
                if expected_keys is not None and ref.demo_key not in expected_keys:
                    raise UserError('Unexpected population provenance identity')
                if not ref.demo_key.startswith('DEMO-') or ref.ownership_kind not in ('created','reused','updated_demo_owned'):
                    raise UserError('Unresolved identity/provenance')
                item['reader']=actor_key(ref) or 'control_center_operator'
                Model=read_model(run,ref)
                record=Model.browse(ref.res_id).exists()
                if not record:
                    missing+=1;item['classification']='MISSING'
                    # A detached candidate is not safe to adopt by name alone.
                    if 'name' in Model._fields:
                        domain=[('name','=',ref.demo_key)]
                        if 'company_id' in Model._fields:domain += [('company_id','in',[False,run.company_id.id])]
                        candidates=Model.search_count(domain)
                        item['candidates']=candidates
                        if candidates:
                            duplicates+=int(candidates>1)
                            raise UserError('Detached candidate found; restore verified provenance before creating a replacement')
                else:
                    record.check_access('read')
                    if 'name' in Model._fields and Model._fields['name'].type == 'char' and record['name'] == ref.demo_key:
                        domain=[('name','=',ref.demo_key)]
                        if 'company_id' in Model._fields:domain += [('company_id','in',[False,run.company_id.id])]
                        candidates=Model.search_count(domain)
                        if candidates>1:
                            duplicates+=1;item['candidates']=candidates
                            raise UserError('Ambiguous deterministic identity; multiple candidates require explicit resolution')
                    if 'company_id' in record._fields and record.company_id and record.company_id!=run.company_id:
                        raise UserError('Record company differs from run company')
                    if 'company_ids' in record._fields and record.company_ids and run.company_id not in record.company_ids:
                        raise UserError('Run company is not in the record company scope')
                    if 'branch_id' in record._fields and record.branch_id and 'company_id' in record.branch_id._fields and record.branch_id.company_id!=run.company_id:
                        raise UserError('Branch company differs from run company')
                    existing+=1;item.update(candidates=1,classification='ADOPT_CANDIDATE')
            except Exception as exc:
                item.update(classification='BLOCK',reason=str(exc));blocked.append(f'{ref.model_name} / {ref.demo_key}: {exc}')
            evidence.append(item)
        # An entirely absent population batch is valid MISSING/READY evidence,
        # not a semantic validation failure.  Once any provenance exists, the
        # full owner validator runs and partial aggregates remain fail-closed.
        if not blocked and not (spec.family=='population' and not refs):
            try:issues=list(self.validate_owner(run,spec))
            except Exception as exc:issues=[f'{exc.__class__.__name__}: {exc}']
        needs_provenance=not spec.key.startswith('validation.') and spec.key!='workforce.preflight'
        if not refs and needs_provenance:
            missing=max(missing,1)
            message='No run provenance exists for this journey; execute through the owner adapter'
            if spec.family=='population':notes.append(message)
            else:issues.append(message)
        return dict(existing=existing,missing=missing,duplicate=duplicates,invalid=len(blocked)+len(issues),
                    expected=(len(expected_keys) if expected_keys is not None else max(len(refs),1 if needs_provenance else 0)),
                    evidence=evidence,blocked=blocked,issues=issues,notes=notes)

    def reconcile(self, run, rows=None, keys=None):
        rows=rows or self.sync(run)
        for spec in self.specs:
            if keys is not None and spec.key not in keys:
                continue
            row=rows[spec.key]
            if spec.key == 'clinical.telemedicine':
                try:
                    with self.env.cr.savepoint():
                        prepare_telemedicine_scope(run, optional=True)
                except Exception as exc:
                    row.write({'state':'blocked','classification':'block','invalid':1,
                               'diagnostic':'Telemedicine scope contract: '+str(exc)})
                    continue
            facts=self.inspect(run,spec)
            deps=[key for key in spec.dependencies if rows[key].state!='pass']
            clean=not(facts['blocked'] or facts['issues'] or facts['missing'] or row.needs_refresh)
            if facts['blocked']:
                state,kind='blocked','block'
            elif deps:
                state,kind='waiting',('reconcile' if facts['existing'] else 'missing')
            elif clean:
                state,kind='pass','adopt'
            else:
                state,kind=('partial','reconcile') if facts['existing'] else ('ready','missing')
            for item in facts['evidence']:
                if item.get('classification')=='ADOPT_CANDIDATE':item['classification']='ADOPT' if clean else 'RECONCILE'
            if row.state=='failed' and state=='partial':
                state='failed'
            diagnostic='; '.join(facts['blocked']+facts['issues']+facts.get('notes',[])+(['Waiting for: '+', '.join(deps)] if deps else [])+(['Consumer refresh required after upstream changes'] if row.needs_refresh else []))
            if clean and not deps and not spec.family:
                self.adopt_checkpoint(run,spec)
            row.write({key:facts[key] for key in ('expected','existing','missing','duplicate','invalid')} | {
                'state':state,'classification':kind,'adopted':facts['existing'] if clean else 0,
                'last_validation':fields.Datetime.now(),'diagnostic':diagnostic or 'Identity, scope and owner validation passed',
                'evidence':json.dumps(facts['evidence'],sort_keys=True),
            })
        return rows

    def acceptance_snapshot(self, run):
        """Validate the persisted journey closure without replaying 137 owners.

        Every PASS row is produced only after ``inspect`` and the owner
        validator succeed in the bounded runner.  Final acceptance therefore
        verifies the immutable registry, the stored validation timestamp,
        refresh flags and dependency closure.  An explicit Reconcile Existing
        Dataset remains the operation that deliberately re-reads every owner
        aggregate.
        """
        rows = self.sync(run)
        stored = self.Rows.search([('run_id', '=', run.id)])
        expected_keys = set(self.by_key)
        actual_keys = set(stored.mapped('journey_key'))
        issues = []
        if actual_keys != expected_keys:
            missing = sorted(expected_keys - actual_keys)
            unknown = sorted(actual_keys - expected_keys)
            if missing:
                issues.append('Missing journey rows: ' + ', '.join(missing))
            if unknown:
                issues.append('Unknown journey rows: ' + ', '.join(unknown))
        if len(stored) != len(self.specs):
            issues.append(
                f'Journey registry cardinality is {len(stored)}; expected {len(self.specs)}'
            )
        for spec in self.specs:
            row = rows[spec.key]
            if row.state != 'pass':
                issues.append(f'{spec.key}: state is {row.state}, expected pass')
            if row.needs_refresh:
                issues.append(f'{spec.key}: downstream refresh is still required')
            if not row.last_validation:
                issues.append(f'{spec.key}: no persisted owner-validation timestamp')
            incomplete = [key for key in spec.dependencies if rows[key].state != 'pass']
            if incomplete:
                issues.append(f'{spec.key}: dependencies are not PASS: {", ".join(incomplete)}')
        return rows, issues

    def adopt_checkpoint(self,run,spec):
        scenario=ScenarioRegistry.get(spec.generator.scenario_keys[0])
        cp=self.kernel.checkpoints.ensure(run,self.kernel._checkpoint_key(spec.generator,scenario),
                                          spec.generator.phase,spec.key,spec.generator.sequence,scenario.key)
        if cp.state!='done':
            cp.write({'state':'done','error_summary':False,'completed_at':fields.Datetime.now(),
                      'created_count':0,'reused_count':len(self.references(run,spec))})
            run._log_control_event('info','journey_adopt',f'{spec.key}: actual source validation passed; checkpoint reconciled without business mutation')

    def invalidate_consumers(self, key, rows):
        affected={key}
        for spec in self.specs:
            if affected.intersection(spec.dependencies):
                affected.add(spec.key)
                rows[spec.key].write({'state':'waiting','needs_refresh':spec.key in ('management.reports','management.dashboard','management.analytics'),
                                      'diagnostic':'Upstream journey executed; revalidation required'})

    def run_one(self, run, spec, rows):
        row=rows[spec.key]
        deps=[key for key in spec.dependencies if rows[key].state!='pass']
        if deps or row.state=='blocked':
            return False
        # Reconciliation already proved PASS against actual records: no writes.
        if row.state=='pass' and not row.needs_refresh:
            row.write({'created':0,'reconciled':0})
            return True
        row.write({'state':'running','last_execution':fields.Datetime.now(),'created':0,'reconciled':0})
        try:
            with self.env.cr.savepoint():
                if spec.family=='population':
                    counts=self.population(run,spec).generate()
                elif spec.family:
                    counts=self.source(run).generate_family(spec.family)
                else:
                    kwargs={}
                    if spec.key=='management.reports':kwargs={'refresh':True,'include_sources':False}
                    elif spec.key in ('management.dashboard','management.analytics'):kwargs={'refresh':True}
                    ok,message=self.kernel._execute_generator(run,spec.generator,force=True,generate_kwargs=kwargs)
                    if not ok:raise UserError(message)
                    cp=run.checkpoint_ids.filtered(lambda c:c.generator_key==spec.key and c.state=='done')
                    counts={'created':sum(cp.mapped('created_count')),'updated':sum(cp.mapped('updated_count'))}
                facts=self.inspect(run,spec)
                if facts['blocked'] or facts['issues'] or facts['missing']:
                    raise UserError('; '.join(facts['blocked']+facts['issues']) or 'Missing provenance records')
                row.write({'state':'pass','classification':'adopt','needs_refresh':False,'created':counts.get('created',0),
                           'reconciled':counts.get('updated',0),'existing':facts['existing'],'adopted':max(0,facts['existing']-counts.get('created',0)),
                           'expected':facts['expected'],'invalid':0,'missing':0,'duplicate':0,
                           'last_validation':fields.Datetime.now(),'diagnostic':'Owner workflow and validation passed',
                           'evidence':json.dumps(facts['evidence'],sort_keys=True)})
            self.invalidate_consumers(spec.key,rows)
            run.write({'state':'draft'})
            return True
        except Exception as exc:
            detail=json.dumps({'journey':spec.key,'model':spec.primary_model,'operation':'execute_journey',
                               'company':run.company_id.display_name,'dependencies':spec.dependencies,
                               'exception':exc.__class__.__name__,'message':str(exc)},sort_keys=True)
            row.write({'state':'failed','diagnostic':detail,'created':0,'reconciled':0})
            run.write({'state':'failed'})
            self.kernel.logging.log(run=run,level='error',generator_key=spec.key,operation='execute_journey',message=detail,
                                    exception_class=exc.__class__.__name__,traceback_excerpt=traceback.format_exc())
            return False

    def dispatch(self, run, mode, key=None):
        run.ensure_one();run.lock_for_update()
        rows=self.sync(run)
        if mode=='reconcile':
            rows=self.reconcile(run,rows)
            return self.notice(run,rows,'Existing dataset reconciled')
        if mode=='current':
            if key not in self.by_key:raise UserError('Unknown journey key')
            spec=self.by_key[key]
            self.reconcile(run,rows,keys={spec.key})
            if not self.run_one(run,spec,rows):return self.notice(run,rows,'Journey stopped')
            following=next((item for item in self.specs if rows[item.key].state!='pass'),None)
            if following and following.key!=spec.key:self.reconcile(run,rows,keys={following.key})
            return self.notice(run,rows,'Journey progress updated')
        elif mode in ('next','resume','next10'):
            # These modes are incremental. PASS rows already contain actual
            # owner-validation evidence and must not be re-read on every click.
            # The target is reconciled immediately before execution and the
            # next remaining target once at the end.
            limit=10 if mode=='next10' else 1
            completed=0
            while completed<limit:
                spec=next((item for item in self.specs if rows[item.key].state!='pass'),None)
                if not spec:break
                self.reconcile(run,rows,keys={spec.key})
                before=rows[spec.key].state
                if not self.run_one(run,spec,rows):
                    title='Execute Next 10 stopped' if mode=='next10' else 'Journey stopped'
                    return self.notice(run,rows,title,prefix=f'{completed} journey(s) completed in this request. ' if mode=='next10' else '')
                if before!='pass' or rows[spec.key].state=='pass':completed+=1
            following=next((item for item in self.specs if rows[item.key].state!='pass'),None)
            if following:self.reconcile(run,rows,keys={following.key})
            title='Execute Next 10 completed' if mode=='next10' else 'Journey progress updated'
            prefix=f'{completed} journey(s) completed in this request. ' if mode=='next10' else ''
            return self.notice(run,rows,title,prefix=prefix)
        elif mode=='phase':targets=[spec for spec in self.specs if spec.generator and spec.generator.phase==run.current_phase]
        elif mode=='sources':
            targets=[spec for spec in self.specs if spec.family or spec.key.startswith(('management.','validation.'))]
        else:targets=list(self.specs)
        # Broad modes intentionally perform whole-path reconciliation. The
        # incremental buttons above never sweep all 137 rows.
        self.reconcile(run,rows)
        for spec in targets:
            # Upstream success releases dependents using the same validation path.
            self.reconcile(run,rows,keys={spec.key})
            executed_population=spec.family=='population' and (rows[spec.key].state!='pass' or rows[spec.key].needs_refresh)
            if not self.run_one(run,spec,rows):return self.notice(run,rows,'Journey stopped')
            # Never put multiple population batches into one long HTTP transaction.
            if executed_population:break
        self.reconcile(run,rows)
        if all(row.state=='pass' for row in rows.values()) and mode not in ('current','next','resume','phase'):
            return run.action_validate()
        return self.notice(run,rows,'Journey progress updated')

    def notice(self,run,rows,title,prefix=''):
        passed=sum(row.state=='pass' for row in rows.values())
        first=next((row for spec in self.specs if (row:=rows[spec.key]).state!='pass'),None)
        message=prefix+f'{passed}/{len(rows)} journeys validated PASS.'
        if first:message+=f' Next: {first.name} [{first.state.upper()}]. {first.diagnostic or ""}'
        return self.kernel._notification(title,message,'danger' if first and first.state in ('failed','blocked') else 'info',sticky=True)

















