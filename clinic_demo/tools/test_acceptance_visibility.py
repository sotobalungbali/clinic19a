"""Execute acceptance orchestration with record doubles; no native Odoo claim."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
ROOT = Path(__file__).resolve().parents[1]

class Results:
    def __init__(self): self.rows = {}
    def search(self, domain, limit=1): return self.rows.get(domain[1][2])
    def create(self, vals):
        row = NS(**vals)
        row.write = lambda values: row.__dict__.update(values)
        self.rows[vals['check_key']] = row
        return row

class Base:
    def ensure_one(self): pass
    def _check_generation_preflight(self): pass
    def write(self, vals): self.__dict__.update(vals)
    def _display_notification(self, title, message, kind, sticky=False):
        return {'type':'ir.actions.client','tag':'display_notification',
                'params':{'title':title,'message':message,'type':kind,'sticky':sticky}}
    def action_validate(self):
        self.state = 'failed' if self.owner_failed else 'ready'
        self.validation_status = 'fail' if self.owner_failed else 'pass'
        return self._display_notification('owner result','owner evidence','danger' if self.owner_failed else 'success')

class RemoveImports(ast.NodeTransformer):
    def visit_ImportFrom(self, node): return None

source = ast.parse((ROOT/'models/demo_run_journeys.py').read_text())
original = next(n for n in source.body if isinstance(n, ast.ClassDef))
original.bases = [ast.Name(id='Base', ctx=ast.Load())]
original.body = [n for n in original.body if isinstance(n, ast.FunctionDef) and n.name in ('action_validate','action_open_acceptance_results')]
module = RemoveImports().visit(ast.Module(body=[original], type_ignores=[]))
ast.fix_missing_locations(module)

def evaluate(run):
    run.reporting_evidence = 'population proof'
    run.reporting_status = 'pass' if run.population_ok else 'fail'
    return run.population_ok

scope = {'Base':Base, 'evaluate':evaluate, 'json':__import__('json'),
         'JourneyEngine':lambda env: NS(acceptance_snapshot=lambda run: (
             {'one': NS(state=run.journey_state)},
             [] if run.journey_state == 'pass' else ['one is not PASS']
         ))}
exec(compile(module, '<acceptance>', 'exec'), scope)
Run = scope['ClinicDemoRunJourneys']

def run():
    obj = Run(); obj.id = 7; obj.owner_failed = False
    obj.population_ok = False; obj.journey_state = 'pass'
    obj.env = {'clinic.demo.validation.result':Results()}
    return obj

class AcceptanceVisibility(unittest.TestCase):
    def test_insufficient_evidence_saved_before_navigation_and_repeat_updates(self):
        obj = run()
        for _ in range(2):
            action = obj.action_validate()
            self.assertEqual(obj.reporting_status,'fail')
            self.assertEqual(obj.state,'failed')
            self.assertEqual(obj.env['clinic.demo.validation.result'].rows['reporting.sufficiency'].state,'fail')
            self.assertEqual(action['params']['next']['res_id'],7)
            self.assertEqual(action['params']['next']['target'],'current')
        self.assertEqual(len(obj.env['clinic.demo.validation.result'].rows),2)
    def test_pass_refreshes_form_too(self):
        obj=run(); obj.population_ok=True
        result=obj.action_validate()
        self.assertEqual(obj.state,'ready')
        self.assertEqual(result['params']['next']['res_model'],'clinic.demo.run')
    def test_owner_failure_is_not_promoted_by_population_pass(self):
        obj=run(); obj.population_ok=True; obj.owner_failed=True
        self.assertEqual(obj.action_validate()['params']['type'],'danger')
        self.assertEqual(obj.validation_status,'fail')
    def test_journey_failure_remains_failure(self):
        obj=run(); obj.population_ok=True; obj.journey_state='partial'
        obj.action_validate()
        self.assertEqual(obj.state,'failed')
    def test_acceptance_navigation_is_run_scoped(self):
        obj=run(); action=obj.action_open_acceptance_results()
        self.assertIn(('run_id','=',7),action['domain'])
        self.assertIn('reporting.sufficiency',action['domain'][1][2])


class WindowActionContracts(unittest.TestCase):
    def test_every_inline_window_action_has_explicit_matching_views(self):
        count = 0
        for path in (ROOT/'models').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node, ast.Dict): continue
                d = {k.value:v for k,v in zip(node.keys,node.values) if isinstance(k,ast.Constant)}
                if not isinstance(d.get('type'),ast.Constant) or d['type'].value != 'ir.actions.act_window': continue
                with self.subTest(path=path.name, line=node.lineno):
                    self.assertIn('views',d)
                    views=ast.literal_eval(d['views'])
                    self.assertEqual(views,[(False,m) for m in ast.literal_eval(d['view_mode']).split(',')])
                    count += 1
        self.assertGreaterEqual(count,14)

    def test_notification_next_is_complete_without_server_action_normalization(self):
        for sufficient in (False,True):
            obj=run();obj.population_ok=sufficient
            action=obj.action_validate()['params']['next']
            self.assertEqual(action['views'],[(False,'form')])
            self.assertEqual(action['res_id'],obj.id)
        self.assertEqual(run().action_open_acceptance_results()['views'],[(False,'list'),(False,'form')])











