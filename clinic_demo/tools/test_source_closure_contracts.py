"""Regression gates for owner APIs and source-closure re-entry (no Odoo DB)."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT.parent


def function(path, name, namespace):
    tree = ast.parse(path.read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class SourceClosureContracts(unittest.TestCase):
    def test_membership_explicit_name_never_evaluates_sequence(self):
        tree = ast.parse((SUITE/'clinic_membership/models/membership_contract.py').read_text())
        create = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'create')
        loop = next(n for n in create.body if isinstance(n, ast.For))
        guard = loop.body[0]
        def sequence():
            raise AssertionError('Mutable sequence was consumed')
        for name in ['DEMO-SOURCE-MEMBER-001', 'MEMBER/EXPLICIT/001']:
            ns = {'vals': {'name': name}, 'self': NS(_next_name=sequence)}
            exec(compile(ast.Module(body=[guard], type_ignores=[]), '<name-guard>', 'exec'), ns)
            self.assertEqual(ns['vals']['name'], name)
        ns = {'vals': {}, 'self': NS(_next_name=lambda: 'PRODUCTION/001')}
        exec(compile(ast.Module(body=[guard], type_ignores=[]), '<name-guard>', 'exec'), ns)
        self.assertEqual(ns['vals']['name'], 'PRODUCTION/001')

    def test_wallet_explicit_contract_posts_once_and_default_remains_valid(self):
        fn = function(SUITE/'clinic_wallet/models/wallet_transaction.py', 'action_post',
                      {'UserError': ValueError, '_': lambda x:x})
        calls = []
        class Tx:
            state = 'draft'
            transaction_type = 'topup'
            wallet_id = NS(_lock_for_update=lambda:None, _check_access_manager=lambda:None)
            def __iter__(self): return iter([self])
            def ensure_one(self): return None
            def _check_rules(self): pass
            def _check_balance_policy_before_post(self): pass
            def _should_post_accounting_now(self): return True
            def _create_account_move(self, *args): calls.append(args); return NS(id=9)
            def with_context(self, **kw): return self
            def write(self, values): self.__dict__.update(values)
        tx = Tx()
        fn(tx, 'DW48/2026/0001', '2026-09-13', 42)
        fn(tx, 'DW48/2026/0001', '2026-09-13', 42)
        self.assertEqual(calls, [('DW48/2026/0001', '2026-09-13', 42)])
        self.assertEqual(tx.state, 'posted')
        self.assertEqual(tx.move_id, 9)
        fn(Tx())
        self.assertEqual(calls[-1], (None, None, None))
        with self.assertRaisesRegex(ValueError, 'together'):
            fn(Tx(), accounting_name='INCOMPLETE')

    def test_execution_events_preserve_explicit_identity_and_time(self):
        fn=function(SUITE/'clinic_encounter/models/execution_log.py','log_for_session', {
            'UserError':ValueError, '_':lambda x:x,
            'fields':NS(Datetime=NS(now=lambda:'wall-clock-fallback')),
        })
        session=NS(_name='clinic.procedure.session',id=3,company_id=NS(id=4),state='done')
        for event in ('create','start','done'):
            contract={event:{'name':'DEMO-EVENT-'+event.upper(),'date_event':'anchor-event-time'}}
            owner=NS(env=NS(context={'clinic_execution_event_contract':contract},user=NS(id=5)),create=lambda vals:vals)
            result=fn(owner,session,event)
            self.assertEqual(result['name'],'DEMO-EVENT-'+event.upper())
            self.assertEqual(result['date_event'],'anchor-event-time')
            self.assertEqual(result['session_id'],3)
            self.assertEqual(result['company_id'],4)
        owner.env.context={'clinic_execution_event_contract':{}}
        with self.assertRaisesRegex(ValueError,'requires event name and date'):
            fn(owner,session,'start')

    def test_no_new_wallet_names_leak_into_unlink(self):
        tree = ast.parse((SUITE/'clinic_wallet/models/wallet_transaction.py').read_text())
        unlink = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name=='unlink')
        names = {n.id for n in ast.walk(unlink) if isinstance(n, ast.Name)}
        self.assertFalse(names & {'accounting_name', 'accounting_date', 'liability_account_id'})

    def test_all_source_models_have_reset_policy(self):
        source = ast.parse((ROOT/'generators/management/source_journeys.py').read_text())
        models = set()
        for n in ast.walk(source):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr=='ensure':
                models.add(ast.literal_eval(n.args[1]))
        ns={}
        exec((ROOT/'services/constants.py').read_text(),ns)
        tree=ast.parse((ROOT/'services/reset_policy_registry.py').read_text())
        tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
        from dataclasses import dataclass
        ns.update(dataclass=dataclass,ValidationError=ValueError)
        exec(compile(tree,'<reset>','exec'),ns)
        for model in models:
            self.assertIn(ns['ResetPolicyRegistry']().decision_for_values(model, {'state':'done'}).policy,
                          {'fresh_db_reset_only','deactivate','reverse_then_retain'})
        with self.assertRaises(ValueError):
            ns['ResetPolicyRegistry']().decision_for_values('unknown.model',{})

    def test_stock_owner_contract_matches_odoo19_and_marks_picked(self):
        usage = (SUITE/'clinic_inventory/models/treatment_product_usage.py').read_text()
        tree=ast.parse(usage)
        fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='action_consume')
        rendered=ast.unparse(fn)
        self.assertLess(rendered.index("'picked': True"), rendered.index('moves._action_done()'))
        payload=function(SUITE/'clinic_inventory/models/product_template.py', '_clinic_hook_prepare_consumption_vals', {'_':lambda x:x})
        product=NS(id=1,uom_id=NS(id=2))
        result=payload(NS(ensure_one=lambda:None,product_variant_id=product,display_name='Gauze'),1)
        self.assertNotIn('name',result)
        self.assertIn('origin',result)

    def test_reentry_uses_reference_identity_and_refuses_drift(self):
        fn=function(ROOT/'generators/management/source_journeys.py','ensure',{'RESET_FRESH_DB_ONLY':'fresh_db_reset_only','UserError':ValueError})
        created=[];store={}
        class Record(dict):
            company_id=1
            _fields={'name':NS(type='char')}
        def ensure_record(**kw):
            key=kw['demo_key']
            if key not in store:store[key]=kw['create_callback']()
            return store[key],None,'reused'
        model=NS(create=lambda vals: (created.append(vals) or Record(vals)))
        context=NS(run=1,reference_service=NS(ensure_record=ensure_record))
        owner=NS(_actor=lambda record,*args:record)
        service=NS(ctx=context,manager=1,company=1,model=lambda name:model,owner=owner,counts={"reused":0})
        one=fn(service,'DEMO-KEY','example',{'name':'fixed'})
        two=fn(service,'DEMO-KEY','example',{'name':'fixed'})
        self.assertIs(one,two)
        self.assertEqual(len(created),1)
        with self.assertRaisesRegex(ValueError,'business contract'):
            fn(service,'DEMO-KEY','example',{'name':'changed'})

    def test_closure_is_atomic_and_does_not_reset_checkpoints(self):
        source=(ROOT/'services/source_closure_service.py').read_text()
        tree=ast.parse(source)
        fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='complete_source_journeys')
        text=ast.unparse(fn)
        self.assertIn("run._journey_action('sources')",text)
        engine=(ROOT/'services/journey_engine.py').read_text()
        self.assertIn('with self.env.cr.savepoint():',engine)
        self.assertIn("'refresh':True",engine)
        self.assertNotIn('checkpoint_ids.write',text)
        self.assertNotIn('action_open_reset_wizard',text)
        self.assertIn('return run.action_validate()',engine)

if __name__=='__main__': unittest.main()













