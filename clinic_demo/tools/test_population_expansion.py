"""Population v1 behavior and owner contracts; no claim of native ORM execution."""
import ast
import calendar
from datetime import date,datetime,timedelta
from pathlib import Path
import runpy
from types import SimpleNamespace as NS
import unittest
ROOT=Path(__file__).resolve().parents[1]
PLAN=runpy.run_path(str(ROOT/'services/population_plan.py'))
TREE=ast.parse((ROOT/'services/population_service.py').read_text())
CLS=next(n for n in TREE.body if isinstance(n,ast.ClassDef))

def method(name):
    fn=next(n for n in CLS.body if isinstance(n,ast.FunctionDef) and n.name==name)
    scope={'UserError':ValueError}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<owner-adapter>','exec'),scope)
    return scope[name]

class PopulationContracts(unittest.TestCase):
    def test_volume_is_enterprise_not_twenty_record_floor(self):
        self.assertEqual(len(PLAN['batch_specs']()),96)
        for domain in PLAN['DOMAINS']:
            n=sum(PLAN['volume'](domain,m) for m in range(1,13))
            self.assertGreaterEqual(n,24 if domain=='incident' else 120 if domain in ('membership','insurance') else 500)
            self.assertLessEqual(max(PLAN['volume'](domain,m) for m in range(1,13)),56)
    def test_reference_inventory_is_exact_and_collision_free(self):
        anchor=date(2026,8,27)
        self.assertEqual(len(PLAN['reference_keys'](anchor,'setup')),16)
        for domain in PLAN['DOMAINS']:
            for month in range(1,13):
                keys=PLAN['reference_keys'](anchor,domain,month)
                self.assertEqual(len(keys),len(set(keys)))
                n=PLAN['volume'](domain,month);cancelled=sum(i%7==0 for i in range(n))
                expected={'booking':n,'procedure':5*n-cancelled,'billing':5*n-2*cancelled,
                          'insurance':2*n,'membership':n+cancelled,'inventory':3*n-2*cancelled,
                          'wallet':2*n-cancelled,'incident':n}[domain]
                self.assertEqual(len(keys),expected)
                self.assertTrue(all(key.startswith(PLAN['prefix'](domain,month)+'-') for key in keys))
    def test_dates_unique_keys_and_distribution_for_leap_and_month_end_anchors(self):
        for anchor in (date(2026,8,27),date(2026,1,1),date(2024,2,29),date(2025,3,31),date(2025,12,31)):
            for domain in PLAN['DOMAINS']:
                items=[v for m in range(1,13) for v in PLAN['entries'](anchor,domain,m)]
                with self.subTest(anchor=anchor,domain=domain):
                    self.assertEqual(len({x['key'] for x in items}),len(items))
                    self.assertTrue(all(anchor-timedelta(days=365)<=x['day']<anchor for x in items))
                    self.assertGreaterEqual(len({str(x['day'])[:7] for x in items}),12)
                    self.assertEqual(items,[v for m in range(1,13) for v in PLAN['entries'](anchor,domain,m)])
                    if domain!='incident':
                        self.assertGreaterEqual(len({x['patient'] for x in items}),4)
                        self.assertEqual({x['cancelled'] for x in items},{True,False})
    def test_core_paths_share_period_patient_and_origin_identity(self):
        for m in range(1,13):
            booking=PLAN['entries'](date(2026,8,27),'booking',m)
            proc=PLAN['entries'](date(2026,8,27),'procedure',m)
            bills=PLAN['entries'](date(2026,8,27),'billing',m)
            for b,p,i in zip(booking,proc,bills):
                self.assertEqual((b['patient'],b['day'],b['cancelled']),(p['patient'],p['day'],p['cancelled']))
                self.assertEqual(i['key'].replace('BILLING','PROCEDURE'),p['key'])
    def test_finished_owner_record_is_never_replayed_or_rewound(self):
        calls=[];rec=NS(state='done',display_name='owned',action_done=lambda:calls.append('called'))
        finish=method('finish');finish(NS(dry=False),rec,'done',[('action_done',{})])
        self.assertEqual(calls,[])
        rec.state='cancelled'
        with self.assertRaisesRegex(ValueError,'unexpected intermediate'):finish(NS(dry=False),rec,'done',[('action_done',{})])
        self.assertEqual(calls,[])
    def test_read_only_validation_cannot_execute_owner_actions(self):
        calls=[];rec=NS(state='draft',display_name='owned',action_done=lambda:calls.append('called'))
        with self.assertRaisesRegex(ValueError,'expected done'):method('finish')(NS(dry=True),rec,'done',[('action_done',{})])
        self.assertEqual(calls,[])
    def test_workflow_uses_official_transitions_before_state_proof(self):
        rec=NS(state='draft',display_name='owned');calls=[]
        def post():calls.append('post');rec.state='posted'
        rec.action_post=post
        method('finish')(NS(dry=False),rec,'posted',[('action_post',{})])
        self.assertEqual(calls,['post'])
    def test_failure_does_not_turn_into_pass(self):
        rec=NS(state='draft',display_name='owned',action_post=lambda:None)
        with self.assertRaisesRegex(ValueError,'expected posted'):method('finish')(NS(dry=False),rec,'posted',[('action_post',{})])
    def test_no_business_rewrite_sequence_or_outbound_shortcut(self):
        text=(ROOT/'services/population_service.py').read_text()
        for bad in ('sudo(', 'next_by_code(', 'uuid', '.commit(', 'requests.', 'send_mail(', "write({'state'"):
            self.assertNotIn(bad,text)
        self.assertIn('update_callback=None',text)
        self.assertIn('RESET_FRESH_DB_ONLY',text)

    def test_warehouse_creation_crosses_config_boundary_only_in_private_owner_adapter(self):
        population=(ROOT/'services/population_service.py').read_text()
        owner=(ROOT.parent/'clinic_inventory/models/stock_warehouse.py').read_text()
        self.assertIn("('_clinic_demo_create_bounded_warehouse',)",population)
        self.assertIn("clinic_demo_safe_mode=True",population)
        self.assertIn("clinic_demo_run_id=self.run.id",population)
        self.assertIn("'branch_id':False",population)
        self.assertNotIn('base.group_system',population)
        self.assertIn('def _clinic_demo_create_bounded_warehouse',owner)
        self.assertIn('stock.group_stock_manager',owner)
        self.assertIn('set(values) != allowed_fields',owner)
        self.assertIn('company not in self.env.user.company_ids',owner)
        self.assertIn('return self.sudo().with_company(company).create(dict(values))',owner)
        branch_owner=(ROOT.parent/'clinic_branch/models/stock_warehouse_inherit.py').read_text()
        self.assertIn("if 'branch_id' not in vals:",branch_owner)
        self.assertNotIn("if not vals.get('branch_id'):\n                default_bid",branch_owner)

    def test_bounded_warehouse_identity_is_closed_not_prefix_based(self):
        owner_tree=ast.parse((ROOT.parent/'clinic_inventory/models/stock_warehouse.py').read_text())
        registry=next(ast.literal_eval(node.value) for node in owner_tree.body
            if isinstance(node,ast.Assign) and any(
                isinstance(target,ast.Name) and target.id=='_DEMO_POPULATION_WAREHOUSES'
                for target in node.targets))
        self.assertEqual(registry,{
            'DP1':'Demo Population Supply Unit 1',
            'DP2':'Demo Population Supply Unit 2',
            'DP3':'Demo Population Supply Unit 3',
        })

    def test_billing_income_account_is_source_proven_and_explicit(self):
        population=(ROOT/'services/population_service.py').read_text()
        owner=(ROOT.parent/'clinic_billing/models/account_move_hook.py').read_text()
        base=(ROOT.parent/'clinic_billing/models/billing_invoice.py').read_text()
        self.assertIn("line.clinic_billing_line_id.id==source_line.id",population)
        self.assertIn("account.account_type!='income'",population)
        self.assertIn("{'clinic_billing_income_account_id':income.id}",population)
        self.assertIn("rec._clinic_demo_generate_move_with_income(income)",population)
        self.assertIn("money_lines.account_id.id!=income.id",population)
        self.assertIn("money_lines.clinic_billing_line_id.id!=rec.line_ids.id",population)
        self.assertNotIn("rec.action_confirm();rec.action_generate_account_move()",population)
        self.assertIn("bill._validate_explicit_income_account(account)",population)
        for source in (owner,base):
            self.assertIn('clinic_billing_income_account_id',source)
            self.assertIn('explicit.account_type != "income"',source)
            self.assertIn('company not in explicit.company_ids',source)
        self.assertIn('def _validate_explicit_income_account',owner)
        self.assertIn('def _clinic_demo_generate_move_with_income',owner)
        self.assertIn('def _clinic_billing_product_invoice_lines',owner)
        self.assertIn('line.display_type not in ("line_section", "line_note")',owner)
        self.assertIn('move._clinic_billing_product_invoice_lines()',owner)
        self.assertIn('move_line.account_id.id != account.id',owner)
        self.assertIn('move_line.clinic_billing_line_id.id != billing_line.id',owner)
        self.assertNotIn('move.invoice_line_ids.filtered(lambda line: not line.display_type)',owner)
        self.assertNotIn('invoice_line_ids.filtered(lambda line:not line.display_type)',population)

    def test_population_owner_context_suppresses_external_mail(self):
        population=(ROOT/'services/population_service.py').read_text()
        controls=(ROOT/'models/demo_run_journeys.py').read_text()
        self.assertIn('mail_notify_noemail=True',population)
        self.assertIn('mail_notify_force_send=False',population)
        self.assertIn('clinic_demo_safe_mode=True',population)
        self.assertIn('mail_notify_noemail=True',controls)
        self.assertIn('return JourneyEngine(run.env).dispatch(run, mode, key)',controls)
        self.assertIn("return self._journey_action('next10')",controls)
        self.assertIn("mode in ('next','resume','next10')",(ROOT/'services/journey_engine.py').read_text())

    def test_inventory_receipt_and_consumption_share_one_owner_quantity_contract(self):
        population=(ROOT/'services/population_service.py').read_text()
        source=(ROOT/'generators/management/source_journeys.py').read_text()
        owner=(ROOT.parent/'clinic_inventory/models/stock_move.py').read_text()
        self.assertIn('def _clinic_demo_complete_bounded_receipt',owner)
        self.assertIn('def _clinic_demo_has_completed_quantity',owner)
        self.assertIn('receipt._action_confirm(merge=False)',owner)
        self.assertIn('receipt.write({"quantity": quantity})',owner)
        self.assertIn('receipt.move_line_ids.write({"picked": True, "date": business_date})',owner)
        self.assertIn('requires exactly one native move line',owner)
        self.assertIn('prepared_quantity = receipt._quantity_sml()',owner)
        self.assertIn('receipt._action_done(cancel_backorder=True).exists()',owner)
        self.assertIn('completed.filtered(lambda move: move.id == receipt.id)',owner)
        self.assertIn('done_quantity = self._quantity_sml()',owner)
        self.assertIn('float_compare(done_quantity, quantity',owner)
        self.assertNotIn('sum(self.move_line_ids.mapped("quantity"))',owner)
        self.assertNotIn('receipt.write({"move_line_ids"',owner)
        for consumer in (population,source):
            self.assertIn('_clinic_demo_complete_bounded_receipt',consumer)
            self.assertIn('_clinic_demo_has_completed_quantity',consumer)
        self.assertNotIn("receipt.quantity!=qty",population)
        self.assertNotIn("receipt._action_done()",population)
    def test_owner_methods_exist_in_composite(self):
        expected={'booking.booking':('action_confirm','action_done','action_cancel'),
                  'clinic.encounter':('action_start','action_done','action_cancel'),
                  'clinic.procedure.session':('action_start','action_done','action_cancel'),
                  'clinic.billing.invoice':('action_confirm','action_generate_account_move','action_post_account_move','action_cancel'),
                  'clinic.insurance.authorization':('action_prepare','action_cancel'),
                  'membership.contract':('action_cancel',),
                  'clinic.wallet.transaction':('action_post','action_cancel'),
                  'clinic.incident':('action_report','action_start_triage'),
                  'clinic.treatment.product.usage':('action_consume','action_cancel')}
        models={}
        for path in ROOT.parent.glob('clinic_*/models/*.py'):
            tree=ast.parse(path.read_text(encoding='utf-8-sig'))
            for cls in (n for n in tree.body if isinstance(n,ast.ClassDef)):
                names=[]
                for n in cls.body:
                    if isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str):
                        if any(isinstance(t,ast.Name) and t.id in ('_name','_inherit') for t in n.targets):names.append(n.value.value)
                for name in names:models.setdefault(name,set()).update(n.name for n in cls.body if isinstance(n,ast.FunctionDef))
        for name,methods in expected.items():self.assertTrue(set(methods)<=models.get(name,set()),name)


class ExplicitOwnerNames(unittest.TestCase):
    def test_production_default_and_complete_demo_contract(self):
        for addon, filename, method_name, context_key in (
            ('clinic_billing','integration_event.py','_explicit_billing_event_name','clinic_billing_event_names'),
            ('clinic_membership','mixins.py','_explicit_membership_event_name','clinic_membership_event_names'),
        ):
            tree=ast.parse((ROOT.parent/addon/'models'/filename).read_text())
            fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==method_name)
            scope={'UserError':ValueError,'_':lambda x:x}
            exec(compile(ast.Module(body=[fn],type_ignores=[]),'<explicit-owner-name>','exec'),scope)
            invoke=scope[method_name]
            rec=NS(name='DEMO-X',env=NS(context={}),ensure_one=lambda:None)
            self.assertIsNone(invoke(rec,'posted'))
            rec.env.context={context_key:{'DEMO-X:posted':'DEMO-X-EVENT'}}
            self.assertEqual(invoke(rec,'posted'),'DEMO-X-EVENT')
            for malformed in ({},[],{'DEMO-X:posted':''},{'DEMO-X:posted':12}):
                rec.env.context={context_key:malformed}
                with self.assertRaises(ValueError):invoke(rec,'posted')


