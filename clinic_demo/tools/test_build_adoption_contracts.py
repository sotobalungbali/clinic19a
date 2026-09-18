"""Execute migration policy and metadata-only service with record doubles."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

ROOT=Path(__file__).resolve().parents[1]
ns={}
exec((ROOT/'services/historical_checkpoint_contracts.py').read_text(),ns)
exec((ROOT/'services/build_adoption_service.py').read_text().replace('from .historical_checkpoint_contracts import historical_scenarios, is_historical_checkpoint', ''),ns)
issues=ns['adoption_issues']
LEGACY=ns['LEGACY_SOURCE']
V48=ns['V48_SOURCE']
CONTRACTS={
    'foundation.native':('foundation',('first','historical'),()),
    'management.reports':('reports',('report',),('foundation.native',)),
    'management.analytics':('analytics',('analytics',),('management.reports',)),
    'validation.temporal':('validation',('time',),('management.analytics',)),
}
def row(key,state='done',scenario=None):
    phase,scenarios,_=CONTRACTS[key];scenario=scenario or scenarios[0]
    return dict(generator_key=key,phase_key=phase,scenario_key=scenario,
                checkpoint_key=f'{phase}:{key}:{scenario}',state=state)

def facts():
    return [row(k) for k in list(CONTRACTS)[:3]]
REFS=[dict(generator_key='foundation.native',demo_key='DEMO-FOUNDATION')]

class BuildAdoptionContracts(unittest.TestCase):
    def check(self,rows=None,refs=None,version='19.0.1.0.42',source=LEGACY,state='draft'):
        return issues(version,source,state,rows if rows is not None else facts(),REFS if refs is None else refs,CONTRACTS)

    def test_stored_version_can_lag_installed_addon(self):
        for patch in (31,38,42,43,47):
            self.assertEqual(self.check(version=f'19.0.1.0.{patch}'),[])
        self.assertEqual(self.check(version='19.0.1.0.48',source=V48),[])

    def test_no_raw_35_row_requirement_or_acceptance_deadlock(self):
        self.assertEqual(self.check(),[])
        self.assertEqual(self.check(rows=facts()+[row('validation.temporal','failed')],state='failed'),[])
        self.assertEqual(self.check(rows=facts()+[row('foundation.native',scenario='historical')]),[])

    def test_unknown_fingerprint_and_future_version_block(self):
        self.assertTrue(self.check(source='unknown'))
        self.assertTrue(self.check(version='19.0.1.0.99'))
        self.assertTrue(self.check(version='19.0.1.0.48',source=LEGACY))

    def test_busy_and_running_work_block(self):
        self.assertTrue(self.check(state='generating'))
        self.assertTrue(self.check(rows=facts()+[row('validation.temporal','running')]))

    def test_dependency_holes_block(self):
        self.assertTrue(self.check(rows=facts()[1:]))
        self.assertTrue(self.check(rows=facts()[:2]))

    def test_checkpoint_identity_and_unknown_producer_block(self):
        rows=facts();rows[0]['checkpoint_key']='invented'
        self.assertTrue(self.check(rows=rows))
        self.assertTrue(self.check(refs=[dict(generator_key='unknown',demo_key='DEMO-X')]))
        self.assertTrue(self.check(refs=[]))

    def test_service_retains_history_and_requires_exact_native_suite(self):
        tree=ast.parse((ROOT/'services/build_adoption_service.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='adopt_supported_build')
        fn.body=[n for n in fn.body if not isinstance(n,ast.ImportFrom)]
        runtime={'compatible':False,'message':'Wallet owner not upgraded'}
        scope=dict(ns,GENERATOR_VERSION='19.0.1.0.49',AUTHORITATIVE_SOURCE_FINGERPRINT='current',EXPECTED_SUITE_FINGERPRINT='suite')
        scope['GENERATOR_REGISTRY']=NS(all=lambda:[NS(key=k,phase=v[0],scenario_keys=v[1],depends_on=v[2]) for k,v in CONTRACTS.items()])
        scope['SourceFingerprintService']=lambda env:NS(check_compatibility=lambda:runtime)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<service>','exec'),scope)
        changes=[];logs=[]
        run=NS(generator_version='19.0.1.0.42',source_fingerprint=LEGACY,state='draft',expected_suite_fingerprint='old-suite',env=None,
               checkpoint_ids=facts(),reference_ids=REFS,_log_control_event=lambda *args:logs.append(args))
        def write(vals):changes.append(vals);run.__dict__.update(vals)
        run.write=write
        self.assertFalse(scope['adopt_supported_build'](run));self.assertFalse(changes)
        self.assertIn('not upgraded',run.patch_compatibility_status)
        runtime.update(compatible=True,message='matching')
        original=list(run.checkpoint_ids)
        self.assertTrue(scope['adopt_supported_build'](run))
        self.assertEqual(run.checkpoint_ids,original)
        self.assertEqual(run.reference_ids,REFS)
        self.assertEqual(run.source_fingerprint,'current')
        self.assertEqual(len(logs),1)
        self.assertIn(LEGACY,logs[0][2])
        self.assertFalse(scope['adopt_supported_build'](run))

if __name__=='__main__':unittest.main()












