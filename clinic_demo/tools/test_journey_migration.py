"""Behavioral migration contracts without claiming native Odoo execution."""
import ast
import copy
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import runpy
ROOT=Path(__file__).resolve().parents[1]

def load(path,scope):
    tree=ast.parse(path.read_text());tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
    exec(compile(tree,str(path),'exec'),scope)

class Row:
    def __init__(self,**values):self.__dict__.update(dict(state='waiting',needs_refresh=False,diagnostic='',created=0,reconciled=0,last_validation='now')|values)
    def write(self,values):self.__dict__.update(values)

class Cr:
    def __init__(self):self.business={}
    @contextmanager
    def savepoint(self):
        before=copy.deepcopy(self.business)
        try:yield
        except Exception:
            self.business=before
            raise

scope={'json':__import__('json'),'traceback':__import__('traceback'),'fields':NS(Datetime=NS(now=lambda:'now')),'UserError':ValueError}
load(ROOT/'services/journey_engine.py',scope)
Engine=scope['JourneyEngine']

def spec(key,deps=(),family=''):
    return NS(key=key,name=key,dependencies=deps,family=family,primary_model='example',models=('example',))

def facts(existing=1,issues=None,blocked=None):
    return dict(existing=existing,missing=0,duplicate=0,invalid=len(issues or [])+len(blocked or []),expected=1,evidence=[],issues=issues or [],blocked=blocked or [],notes=[])

class Harness(Engine):
    def __init__(self,specs,rows,evidence):
        self.specs=specs;self.by_key={s.key:s for s in specs};self.rows=rows;self.proof=evidence
        self.env=NS(cr=Cr());self.adoptions=[];self.calls=[]
        self.kernel=NS(logging=NS(log=lambda **kw:self.calls.append(kw)))
    def sync(self,run):return self.rows
    def inspect(self,run,s):return self.proof[s.key]
    def adopt_checkpoint(self,run,s):self.adoptions.append(s.key)

class JourneyMigration(unittest.TestCase):
    def test_unexecuted_population_is_ready_not_failed(self):
        s=spec('population.setup',family='population');row=Row(state='failed')
        engine=Harness([s],{s.key:row},{})
        engine.references=lambda run,s:[]
        engine.population=lambda run,s:NS(expected_reference_keys=lambda:tuple(f'K-{i}' for i in range(16)))
        engine.validate_owner=lambda run,s:(_ for _ in ()).throw(AssertionError('validator must not resolve absent records'))
        proof=Engine.inspect(engine,None,s)
        self.assertEqual((proof['expected'],proof['missing'],proof['invalid']),(16,16,0))
        self.assertFalse(proof['issues']);self.assertTrue(proof['notes'])
        engine.proof={s.key:proof};engine.reconcile(None)
        self.assertEqual((row.state,row.classification),('ready','missing'))

    def test_empty_foundation_provenance_cannot_be_adopted_from_weak_validator(self):
        s=spec('foundation.native');s.models=()
        engine=Harness([s],{},{});engine.references=lambda run,s:[]
        engine.validate_owner=lambda run,s:[]
        result=Engine.inspect(engine,None,s)
        self.assertEqual(result['expected'],1);self.assertEqual(result['missing'],1)
        self.assertTrue(result['issues'])

    def test_legacy_state_is_not_proof_and_dependencies_wait(self):
        specs=[spec('a'),spec('b',('a',))];rows={s.key:Row(state='pass') for s in specs}
        engine=Harness(specs,rows,{'a':facts(issues=['broken relationship']),'b':facts()})
        engine.reconcile(None)
        self.assertEqual(rows['a'].state,'partial');self.assertEqual(rows['b'].state,'waiting')
        self.assertFalse(engine.adoptions)

    def test_adoption_is_validated_and_reexecution_creates_zero(self):
        s=spec('a');row=Row();engine=Harness([s],{'a':row},{'a':facts()})
        engine.reconcile(None)
        self.assertEqual(row.state,'pass');self.assertEqual(row.adopted,1)
        self.assertTrue(engine.run_one(None,s,engine.rows));self.assertEqual(row.created,0)
        self.assertFalse(engine.calls)

    def test_ambiguity_blocks_and_stale_consumer_requires_refresh(self):
        specs=[spec('a'),spec('management.reports',('a',))]
        rows={'a':Row(),'management.reports':Row(needs_refresh=True)}
        engine=Harness(specs,rows,{'a':facts(blocked=['two candidates']),'management.reports':facts()})
        engine.reconcile(None);self.assertEqual(rows['a'].state,'blocked')
        engine.proof['a']=facts();engine.reconcile(None)
        self.assertEqual(rows['management.reports'].state,'partial')
        self.assertTrue(rows['management.reports'].needs_refresh)

    def test_failure_rolls_back_current_aggregate_and_keeps_prior_progress(self):
        s=spec('source.inventory',family='OPS-INV');row=Row(state='ready')
        engine=Harness([s],{s.key:row},{s.key:facts()});engine.env.cr.business={'earlier':'committed'}
        def fail(family):engine.env.cr.business['partial_receipt']='created';raise ValueError('bad owner workflow')
        engine.source=lambda run:NS(generate_family=fail)
        run=Row(company_id=NS(display_name='Demo Company'))
        self.assertFalse(engine.run_one(run,s,engine.rows))
        self.assertEqual(engine.env.cr.business,{'earlier':'committed'})
        self.assertEqual(row.state,'failed');self.assertIn('bad owner workflow',row.diagnostic)
        self.assertEqual(row.created,0)

    def test_reconciliation_rolls_back_validator_business_writes(self):
        s=spec('source.wallet',family='OPS-WALLET');engine=Harness([s],{}, {})
        def validate(**kw):engine.env.cr.business['unexpected']='mutation';return ['warning']
        engine.source=lambda run:NS(validate=validate)
        self.assertEqual(engine.validate_owner(None,s),['warning'])
        self.assertEqual(engine.env.cr.business,{})

    def test_current_next_and_full_share_dispatch_and_stop_on_failure(self):
        specs=[spec('a'),spec('b',('a',)),spec('c',('b',))]
        for mode,key,expected in [('current','b',['b']),('next',None,['b']),('full',None,['a','b'])]:
            rows={'a':Row(state='pass'),'b':Row(state='ready'),'c':Row(state='waiting')}
            engine=Harness(specs,rows,{})
            engine.reconcile=lambda run,rows=None,keys=None:engine.rows
            calls=[]
            def execute(run,s,rows):calls.append(s.key);return s.key!='b'
            engine.run_one=execute;engine.notice=lambda *args,**kwargs:'stopped'
            run=NS(ensure_one=lambda:None,lock_for_update=lambda:None)
            self.assertEqual(engine.dispatch(run,mode,key),'stopped');self.assertEqual(calls,expected)

    def test_next10_is_incremental_caps_at_ten_and_never_sweeps_all_rows(self):
        specs=[spec(chr(ord('a')+index),((chr(ord('a')+index-1),) if index else ())) for index in range(12)]
        rows={item.key:Row(state='ready' if not index else 'waiting') for index,item in enumerate(specs)}
        engine=Harness(specs,rows,{})
        reconciled=[]
        def reconcile(run,rows=None,keys=None):
            self.assertIsNotNone(keys)
            reconciled.append(set(keys))
            item=next(iter(keys));engine.rows[item].state='ready'
            return engine.rows
        def execute(run,item,rows):
            rows[item.key].state='pass';return True
        engine.reconcile=reconcile;engine.run_one=execute
        engine.notice=lambda *args,**kwargs:'done'
        run=NS(id=1,ensure_one=lambda:None,lock_for_update=lambda:None)
        self.assertEqual(engine.dispatch(run,'next10'),'done')
        self.assertEqual(sum(row.state=='pass' for row in rows.values()),10)
        self.assertTrue(all(len(keys)==1 for keys in reconciled))
        self.assertLessEqual(len(reconciled),11)

    def test_final_acceptance_uses_persisted_dependency_closed_pass_evidence(self):
        specs=[spec('a'),spec('b',('a',))]
        rows={'a':Row(state='pass'),'b':Row(state='pass')}
        engine=Harness(specs,rows,{})
        class Stored(list):
            def mapped(self,name):return [getattr(row,name) for row in self]
        engine.Rows=NS(search=lambda domain:Stored(rows.values()))
        engine.by_key={item.key:item for item in specs}
        for key,row in rows.items():row.journey_key=key
        _snapshot,issues=engine.acceptance_snapshot(NS(id=7))
        self.assertEqual(issues,[])
        rows['a'].state='partial'
        _snapshot,issues=engine.acceptance_snapshot(NS(id=7))
        self.assertTrue(any('state is partial' in issue for issue in issues))
        self.assertTrue(any('dependencies are not PASS' in issue for issue in issues))

    def test_registry_keeps_all_35_and_adds_five_without_cycles(self):
        old=runpy.run_path(str(ROOT/'tools/test_historical_checkpoint_contracts.py'))['registry_contracts']()
        classes=[]
        for key,(phase,scenarios,deps) in old.items():
            classes.append(type('Generator',(),dict(key=key,phase=phase,scenario_keys=scenarios,depends_on=deps,sequence=10,owned_models=())))
        from dataclasses import dataclass
        registry={'MODEL_OWNER_ADDONS':{},'dataclass':dataclass,'GENERATOR_REGISTRY':NS(validate=lambda:True,all=lambda:classes),
                  'ScenarioRegistry':NS(get=lambda key:NS(golden_refs=key))}
        registry.update(runpy.run_path(str(ROOT/'services/population_plan.py')))
        load(ROOT/'services/journey_registry.py',registry)
        journeys=registry['ordered_journeys']();self.assertEqual(len(journeys),137)
        seen=set()
        for j in journeys:self.assertTrue(set(j.dependencies)<=seen);seen.add(j.key)
        self.assertTrue(set(old)<=seen)
        reports=next(j for j in journeys if j.key=='management.reports')
        self.assertTrue(set(registry['SOURCE_FAMILIES'])<=set(reports.dependencies))

    def test_token_population_fails_all_reporting_layers(self):
        report={};load(ROOT/'services/reporting_sufficiency.py',report)
        pop={model:dict(count=1,months={'2020-01':1},states={'done':1},dimensions={'one':1}) for model in report['TRANSACTIONS']}
        result=report['assess_population'](pop,1)
        self.assertEqual(set(result),{'L'+str(i) for i in range(1,9)})
        self.assertTrue(all(level['state']=='FAIL' for level in result.values()))

    def test_declared_enterprise_population_passes_all_reporting_layers(self):
        report={};load(ROOT/'services/reporting_sufficiency.py',report)
        pop={model:dict(count=minimum,
                        months={f'2025-{month:02d}':1 for month in range(1,13)},
                        states={'done':minimum-1,'cancelled':1},
                        dimensions={'one':1,'two':1,'three':1})
             for model,minimum in report['DOMAIN_MINIMUMS'].items()}
        result=report['assess_population'](pop,5)
        self.assertTrue(all(level['state']=='PASS' for level in result.values()))

    def test_reporting_evidence_is_read_in_bounded_model_batches(self):
        source=(ROOT/'services/reporting_sufficiency.py').read_text()
        self.assertIn("REPORTING_MODELS = frozenset(TRANSACTIONS) | EXCEPTION_MODELS",source)
        self.assertIn("if ref.model_name not in REPORTING_MODELS",source)
        self.assertIn("if ref.record_status!='bound'",source)
        self.assertIn("groups.setdefault((ref.model_name,actor_key(ref)),[]).append(ref)",source)
        self.assertIn("records=Model.browse(ids).exists()",source)
        self.assertIn("records.read(list(dict.fromkeys(field_names)))",source)
        self.assertNotIn("read_model(run,ref).browse(ref.res_id).exists()",source)

    def test_status_token_cannot_be_forged_by_rpc_context(self):
        tree=ast.parse((ROOT/'models/demo_journey.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='write')
        token=object();space={'JOURNEY_TOKEN':token,'AccessError':PermissionError}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<write>','exec'),space)
        for value in [True,'token',{},None]:
            with self.assertRaises(PermissionError):space['write'](NS(env=NS(context={'_clinic_journey_token':value})),{'state':'pass'})

if __name__=='__main__':unittest.main()
















