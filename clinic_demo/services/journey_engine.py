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
                by_key[spec.key].write(values)
        return by_key

    def references(self, run, spec):
        refs = run.reference_ids
        if spec.family:
            return refs.filtered(lambda row:row.generator_key=='management.reports' and row.demo_key.startswith(SOURCE_PREFIXES[spec.family]))
        return refs.filtered(lambda row:row.generator_key==spec.key and not (spec.key=='management.reports' and row.demo_key.startswith('DEMO-SOURCE-')))

    def source(self, run):
        from ..generators.management.reports import ManagementReportsGenerator
        from ..generators.management.source_journeys import ReportSourceJourneys
        owner = ManagementReportsGenerator()
        ctx = self.kernel._context(run, ScenarioRegistry.get('SCN-REPORT-01'))
        manager = owner._resolve(ctx, 'DEMO-USER-MGR', 'res.users')
        return ReportSourceJourneys(owner, ctx, manager)

    def validate_owner(self, run, spec):
        # Always roll back validator side effects. Only evidence outside this
        # savepoint is persisted by reconciliation, never business corrections.
        try:
            with self.env.cr.savepoint():
                if spec.family:
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
        evidence=[]; blocked=[]; existing=0; missing=0; duplicates=0
        for ref in refs:
            item={'model':ref.model_name,'business_key':ref.demo_key,'owner':ref.ownership_kind,'candidates':0}
            try:
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
        issues=[]
        if not blocked:
            try:issues=list(self.validate_owner(run,spec))
            except Exception as exc:issues=[f'{exc.__class__.__name__}: {exc}']
        needs_provenance=not spec.key.startswith('validation.') and spec.key!='workforce.preflight'
        if not refs and needs_provenance:
            missing=max(missing,1)
            issues.append('No run provenance exists for this journey; execute through the owner adapter')
        return dict(existing=existing,missing=missing,duplicate=duplicates,invalid=len(blocked)+len(issues),
                    expected=max(len(refs),1 if needs_provenance else 0),evidence=evidence,blocked=blocked,issues=issues)

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
            if row.state=='failed' and state in ('ready','partial'):
                state='failed'
            diagnostic='; '.join(facts['blocked']+facts['issues']+(['Waiting for: '+', '.join(deps)] if deps else [])+(['Consumer refresh required after upstream changes'] if row.needs_refresh else []))
            if clean and not deps and not spec.family:
                self.adopt_checkpoint(run,spec)
            row.write({key:facts[key] for key in ('expected','existing','missing','duplicate','invalid')} | {
                'state':state,'classification':kind,'adopted':facts['existing'] if clean else 0,
                'last_validation':fields.Datetime.now(),'diagnostic':diagnostic or 'Identity, scope and owner validation passed',
                'evidence':json.dumps(facts['evidence'],sort_keys=True),
            })
        return rows

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
                if spec.family:
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
        rows=self.reconcile(run)
        if mode=='reconcile':return self.notice(run,rows,'Existing dataset reconciled')
        if mode=='current':
            if key not in self.by_key:raise UserError('Unknown journey key')
            targets=[self.by_key[key]]
        elif mode in ('next','resume'):
            targets=[spec for spec in self.specs if rows[spec.key].state!='pass'][:1]
        elif mode=='phase':targets=[spec for spec in self.specs if spec.generator and spec.generator.phase==run.current_phase]
        elif mode=='sources':
            targets=[spec for spec in self.specs if spec.family or spec.key.startswith(('management.','validation.'))]
        else:targets=list(self.specs)
        for spec in targets:
            # Upstream success releases dependents using the same validation path.
            self.reconcile(run,rows,keys={spec.key})
            if not self.run_one(run,spec,rows):return self.notice(run,rows,'Journey stopped')
        self.reconcile(run,rows)
        if all(row.state=='pass' for row in rows.values()) and mode not in ('current','next','resume','phase'):
            return run.action_validate()
        return self.notice(run,rows,'Journey progress updated')

    def notice(self,run,rows,title):
        passed=sum(row.state=='pass' for row in rows.values())
        first=next((row for spec in self.specs if (row:=rows[spec.key]).state!='pass'),None)
        message=f'{passed}/{len(rows)} journeys validated PASS.'
        if first:message+=f' Next: {first.name} [{first.state.upper()}]. {first.diagnostic or ""}'
        return self.kernel._notification(title,message,'danger' if first and first.state in ('failed','blocked') else 'info',sticky=True)








