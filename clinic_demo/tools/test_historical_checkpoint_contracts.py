"""Historical identities across adoption, execution reuse and retry."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
ROOT = Path(__file__).resolve().parents[1]
ns = {}
exec((ROOT/'services/historical_checkpoint_contracts.py').read_text(), ns)
exec((ROOT/'services/build_adoption_service.py').read_text().replace('from .historical_checkpoint_contracts import historical_scenarios, is_historical_checkpoint', ''), ns)


def registry_contracts():
    classes = {}
    registered = []
    for path in (ROOT/'generators').rglob('*.py'):
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, ast.ClassDef):
                continue
            vals = {}
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for name in item.targets:
                        if isinstance(name, ast.Name):
                            try: vals[name.id] = ast.literal_eval(item.value)
                            except (ValueError, TypeError): pass
            classes[node.name] = ([b.id for b in node.bases if isinstance(b, ast.Name)], vals)
            if any(ast.unparse(d) == 'GENERATOR_REGISTRY.register' for d in node.decorator_list):
                registered.append(node.name)
    def resolve(name):
        bases, vals = classes.get(name, ([], {})); result = {}
        for base in bases: result.update(resolve(base))
        return result | vals
    out = {}
    for name in registered:
        vals = resolve(name)
        out[vals['key']] = (vals['phase'], vals['scenario_keys'], vals.get('depends_on', ()))
    return out


class HistoricalContracts(unittest.TestCase):
    def test_real_35_generator_contracts_and_reported_v45_checkpoint(self):
        contracts = registry_contracts()
        self.assertEqual(len(contracts), 35)
        rows = [dict(generator_key=k,phase_key=v[0],scenario_key=v[1][0],
                     checkpoint_key=f'{v[0]}:{k}:{v[1][0]}',state='done') for k,v in contracts.items()]
        refs = [dict(generator_key=k,demo_key='DEMO-'+k) for k in contracts]
        row = next(row for row in rows if row['generator_key']=='resources.rooms_devices')
        row.update(scenario_key='SCN-QUEUE-01',checkpoint_key='12_resources:resources.rooms_devices:SCN-QUEUE-01')
        for version, source in [('19.0.1.0.45',ns['LEGACY_SOURCE']),('19.0.1.0.49',ns['V49_SOURCE']),('19.0.1.0.50',ns['V50_SOURCE']),('19.0.1.0.51',ns['V51_SOURCE'])]:
            self.assertEqual(ns['adoption_issues'](version,source,'failed',rows,refs,contracts),[])
        row['scenario_key']='SCN-BOOKING-TODAY-01'
        self.assertEqual(ns['adoption_issues']('19.0.1.0.45',ns['LEGACY_SOURCE'],'draft',rows,refs,contracts),[])
        # No other unknown scenario or cross-owner tuple becomes admissible.
        row.update(scenario_key='SCN-UNKNOWN',checkpoint_key='12_resources:resources.rooms_devices:SCN-UNKNOWN')
        self.assertTrue(ns['adoption_issues']('19.0.1.0.45',ns['LEGACY_SOURCE'],'draft',rows,refs,contracts))

    def test_every_alias_targets_real_registry_and_requires_owner_provenance(self):
        contracts = registry_contracts()
        for (phase,key,scenario),aliases in ns['HISTORICAL_SCENARIOS'].items():
            self.assertEqual(contracts[key][0],phase)
            self.assertIn(scenario,contracts[key][1])
            self.assertNotIn(aliases[0],contracts[key][1])
        self.assertEqual(ns['historical_scenarios']('15_arrival','operations.queue_triage',('SCN-QUEUE-01',)),())
        row=dict(generator_key='resources.rooms_devices',phase_key='12_resources',scenario_key='SCN-QUEUE-01',checkpoint_key='12_resources:resources.rooms_devices:SCN-QUEUE-01',state='done')
        errors=ns['adoption_issues']('19.0.1.0.45',ns['LEGACY_SOURCE'],'draft',[row],[],contracts)
        self.assertTrue(any('owner provenance' in e for e in errors))

    def ensure(self, state, canonical_present=False):
        writes=[];creates=[]
        legacy=NS(run_id=7,checkpoint_key='12_resources:resources.rooms_devices:SCN-QUEUE-01',phase_key='12_resources',generator_key='resources.rooms_devices',scenario_key='SCN-QUEUE-01',state=state)
        legacy.write=lambda vals:writes.append(vals)
        canonical=NS(run_id=7,checkpoint_key='12_resources:resources.rooms_devices:SCN-BOOKING-TODAY-01',phase_key='12_resources',generator_key='resources.rooms_devices',scenario_key='SCN-BOOKING-TODAY-01',state='done')
        rows=[legacy]+([canonical] if canonical_present else [])
        def search(domain,limit):
            return next((row for row in rows if all((getattr(row,k) in v if op == 'in' else getattr(row,k)==v) for k,op,v in domain)),False)
        model=NS(search=search,create=lambda vals:creates.append(vals))
        cls=next(n for n in ast.parse((ROOT/'services/checkpoint_service.py').read_text()).body if isinstance(n,ast.ClassDef))
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='ensure')
        scope=dict(ns);exec(compile(ast.Module(body=[fn],type_ignores=[]),'<checkpoint>','exec'),scope)
        run=NS(id=7,ensure_one=lambda:None,source_fingerprint='current')
        got=scope['ensure'](NS(env={'clinic.demo.checkpoint':model}),run,canonical.checkpoint_key,'12_resources','resources.rooms_devices',120,'SCN-BOOKING-TODAY-01')
        return got,legacy,canonical,writes,creates

    def test_done_alias_is_reused_without_writes_or_creation(self):
        got,legacy,_,writes,creates=self.ensure('done')
        self.assertIs(got,legacy);self.assertFalse(writes);self.assertFalse(creates)

    def test_retry_keeps_original_identity_and_current_canonical_wins(self):
        got,legacy,_,writes,creates=self.ensure('failed')
        self.assertIs(got,legacy);self.assertFalse(creates)
        self.assertEqual(writes[0]['scenario_key'],'SCN-QUEUE-01')
        self.assertNotIn('checkpoint_key',writes[0]);self.assertNotIn('state',writes[0])
        got,_,canonical,writes,creates=self.ensure('done',True)
        self.assertIs(got,canonical);self.assertFalse(writes);self.assertFalse(creates)

if __name__=='__main__': unittest.main()











