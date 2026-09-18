"""Explicit report-source closure, owned by management.reports (registry stays 35).

Enrollment and pre-authorization are intentionally open operational documents.
Stock consumption, Wallet top-up and procedure execution use owner workflows.
No metric is written here. Business dates derive only from the run anchor.
"""
from datetime import datetime, time, timedelta
from odoo.exceptions import UserError
from ...services.constants import RESET_FRESH_DB_ONLY

GROUPS = (
    'clinic_membership.group_clinic_membership_manager',
    'clinic_insurance_authorization.group_clinic_insurance_manager',
    'clinic_wallet.group_wallet_manager', 'stock.group_stock_manager',
    'account.group_account_manager',
    'product.group_product_manager',
)
PREREQUISITES = {
    'DEMO-PAT-INS-001': 'clinic.patient', 'DEMO-PAT-MEM-001': 'clinic.patient',
    'DEMO-INS-PLAN-CORP80': 'clinic.insurance.plan',
    'DEMO-MEM-PLAN-ESSENTIAL': 'membership.plan',
    'DEMO-WAREHOUSE-PRIMARY': 'stock.warehouse', 'DEMO-BRANCH-001': 'clinic.branch',
    'DEMO-ENC-LIVE-001': 'clinic.encounter', 'DEMO-PROC-CONSULT': 'clinic.procedure.catalog',
}
# Every direct write model, nested child and owner-created financial/stock child.
CONTRACTS = {
    'clinic.insurance.policy': 'name company_id branch_id patient_id plan_id insurer_partner_id policy_number start_date end_date state',
    'clinic.insurance.authorization': 'name company_id branch_id patient_id policy_id request_date service_date source_type submission_channel line_ids state',
    'clinic.insurance.authorization.line': 'authorization_id description quantity unit_price coverage_percent copay_percent requested_amount',
    'membership.contract': 'name company_id currency_id partner_id patient_id plan_id start_date end_date state contract_value',
    'product.category': 'name',
    'product.template': 'name company_id type uom_id categ_id',
    'product.product': 'product_tmpl_id name default_code company_id type is_storable tracking uom_id categ_id standard_price',
    'stock.location': 'name usage company_id location_id',
    'stock.move': 'origin company_id product_id product_uom product_uom_qty location_id location_dest_id move_line_ids state date clinic_usage_id picked quantity',
    'stock.move.line': 'move_id product_id product_uom_id quantity location_id location_dest_id date',
    'clinic.treatment.product.usage': 'name company_id warehouse_id patient_id src_location_id dest_location_id date_usage line_ids state move_ids',
    'clinic.treatment.product.usage.line': 'usage_id product_id product_uom product_uom_qty',
    'account.account': 'name code account_type company_ids active',
    'account.journal': 'name code type company_id default_account_id',
    'account.move': 'name ref date company_id journal_id state line_ids',
    'account.move.line': 'name account_id debit credit partner_id',
    'clinic.wallet': 'name partner_id patient_id company_id currency_id issue_date expiry_policy state balance',
    'clinic.wallet.transaction': 'name wallet_id transaction_type amount date journal_id state move_id',
    'clinic.execution.log': 'name session_id company_id event_type date_event',
    'clinic.procedure.session': 'name company_id encounter_id procedure_id product_id uom_id quantity planned_start planned_end date_start date_end state',
}
METHODS = {
    'clinic.insurance.authorization': ('action_prepare',),
    'clinic.wallet': ('action_open',), 'clinic.wallet.transaction': ('action_post',),
    'clinic.treatment.product.usage': ('action_consume',),
    'stock.move': ('_action_confirm', '_action_done'),
    'clinic.procedure.session': ('action_start', 'action_done'),
}
SOURCE_KEYS = {
    'FIN-INS': ('DEMO-SOURCE-AUTH-001', 'clinic.insurance.authorization', 'prepared'),
    'OPS-INV': ('DEMO-SOURCE-USAGE-001', 'clinic.treatment.product.usage', 'done'),
    'OPS-MEM': ('DEMO-SOURCE-MEMBER-001', 'membership.contract', 'draft'),
    'OPS-WALLET': ('DEMO-SOURCE-TOPUP-001', 'clinic.wallet.transaction', 'posted'),
    'CLN-PROC': ('DEMO-SOURCE-PROC-001', 'clinic.procedure.session', 'done'),
}


class ReportSourceJourneys:
    def __init__(self, owner, ctx, manager):
        self.owner, self.ctx, self.manager = owner, ctx, manager
        self.company = ctx.run.company_id
        self.day = ctx.run.anchor_date
        self.refs = {}
        self.counts = owner._counts()

    def model(self, name):
        return self.owner._actor(self.ctx.env[name], self.manager, self.ctx)

    def _prepare_actor(self):
        # Explicit functional entitlements, including the delegated Product
        # Template owner. Stock Manager alone does not grant product creation.
        groups = [(xmlid, self.ctx.env.ref(xmlid, raise_if_not_found=False)) for xmlid in GROUPS]
        missing = [xmlid for xmlid, group in groups if not group]
        if missing:
            raise UserError('Source journeys actor groups missing: ' + '; '.join(missing))
        commands = [(4, group.id) for _xmlid, group in groups if group not in self.manager.group_ids]
        if commands:
            self.manager.write({'group_ids': commands})

    def preflight(self):
        issues = []
        if not self.ctx.run.safe_mode:
            issues.append('Source journeys require Demo Safe Mode')
        self._prepare_actor()
        for key, model in PREREQUISITES.items():
            try:
                rec = self.owner._resolve(self.ctx, key, model, user=self.manager)
                if 'company_id' in rec._fields and rec.company_id and rec.company_id != self.company:
                    issues.append(f'{key} is outside the run company')
                self.refs[key] = rec
            except Exception as error:
                issues.append(f'{key}: {error}')
        for name, fields in CONTRACTS.items():
            if name not in self.ctx.env:
                issues.append(f'Missing model {name}')
                continue
            Model = self.model(name)
            missing = set(fields.split()) - set(Model._fields)
            if missing:
                issues.append(f'{name} missing fields {sorted(missing)}')
            for operation in ('read', 'create', 'write'):
                try:
                    Model.browse().check_access(operation)
                except Exception as error:
                    issues.append(f'{name} {operation}: {error}')
            for method in METHODS.get(name, ()):
                if not callable(getattr(Model, method, None)):
                    issues.append(f'{name} missing method {method}')
        for model in ('uom.uom', 'stock.quant', 'clinic.procedure.catalog'):
            try:
                self.model(model).browse().check_access('read')
            except Exception as error:
                issues.append(f'{model} read: {error}')
        relations = {
            ('clinic.insurance.authorization', 'policy_id'): 'clinic.insurance.policy',
            ('membership.contract', 'plan_id'): 'membership.plan',
            ('clinic.treatment.product.usage', 'patient_id'): 'res.partner',
            ('clinic.wallet.transaction', 'wallet_id'): 'clinic.wallet',
            ('clinic.procedure.session', 'encounter_id'): 'clinic.encounter',
            ('stock.move', 'clinic_usage_id'): 'clinic.treatment.product.usage',
            ('product.product', 'uom_id'): 'uom.uom',
            ('product.product', 'product_tmpl_id'): 'product.template',
            ('product.template', 'uom_id'): 'uom.uom',
            ('product.template', 'categ_id'): 'product.category',
        }
        for (model, field), target in relations.items():
            found = self.ctx.env[model]._fields.get(field)
            if not found or found.comodel_name != target:
                issues.append(f'{model}.{field} must reference {target}')
        # Detect mismatched companion code before creating any business record.
        import inspect
        parameters = inspect.signature(self.model('clinic.wallet.transaction').action_post).parameters
        if not {'accounting_name', 'accounting_date', 'liability_account_id'} <= set(parameters):
            issues.append('Wallet explicit posting API is missing; upgrade companion clinic_wallet')
        # Native backorder confirmation and reservation pass these keywords,
        # including for an empty backorder recordset on a fully received move.
        for method, keywords in {
            '_action_confirm': {'merge', 'merge_into', 'create_proc'},
            '_action_assign': {'force_qty'},
            '_action_done': {'cancel_backorder'},
        }.items():
            parameters = inspect.signature(getattr(self.model('stock.move'), method)).parameters
            if not keywords <= set(parameters) and not any(
                    parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
                issues.append(f'Stock owner {method} is missing keyword contract {sorted(keywords)}; upgrade clinic_inventory')
        proc = self.refs.get('DEMO-PROC-CONSULT')
        if proc and (proc.require_consent or proc.require_checklist):
            issues.append('Consultation catalog unexpectedly requires consent/checklist; source contract changed')
        for key in ('DEMO-INS-PLAN-CORP80', 'DEMO-MEM-PLAN-ESSENTIAL'):
            plan = self.refs.get(key)
            if plan and plan.state != 'active':
                issues.append(f'{key} must be active')
        encounter = self.refs.get('DEMO-ENC-LIVE-001')
        if encounter and (not encounter.date_planned_start or not encounter.date_planned_end
                          or encounter.date_planned_end - encounter.date_planned_start <= timedelta(minutes=5)):
            issues.append('Procedure requires an explicit positive encounter window')
        if issues:
            raise UserError('Source journeys whole-path preflight failed: ' + '; '.join(issues))

    def ensure(self, key, model, values):
        Model = self.model(model)
        context = {}
        if model == 'clinic.procedure.session':
            context['clinic_execution_event_contract'] = {
                'create': {'name': key + '-CREATE', 'date_event': values['date_start'] - timedelta(minutes=1)},
                'start': {'name': key + '-START', 'date_event': values['date_start']},
                'done': {'name': key + '-DONE', 'date_event': values['date_end']},
            }
            Model = Model.with_context(**context)
        record, reference, _status = self.ctx.reference_service.ensure_record(
            run=self.ctx.run, demo_key=key, model_name=model,
            generator_key='management.reports', scenario_key='SCN-REPORT-01',
            create_callback=lambda: Model.create(values), update_callback=None,
            reset_policy=RESET_FRESH_DB_ONLY, reset_sequence=1290, record_user=self.manager,
        )
        if reference and reference.ownership_kind == "reused":
            raise UserError(f"{key} is not owned by this demo closure; external records cannot be mutated")
        self.counts[_status] += 1
        record = self.owner._actor(record, self.manager, self.ctx)
        if 'company_id' in record._fields and record.company_id and record.company_id != self.company:
            raise UserError(f'{key} belongs to a different company')
        if context:
            record = record.with_context(**context)
        for field_name, expected in values.items():
            if isinstance(expected, list):
                continue  # Owner child structure is verified below, never overwritten.
            actual = record[field_name]
            if record._fields[field_name].type == 'many2one':
                actual = actual.id
            if actual != expected:
                raise UserError(f'{key}.{field_name} differs from its explicit business contract')
        return record

    def bind(self, key, record):
        self.ctx.reference_service.bind(
            run=self.ctx.run, demo_key=key, record=record,
            generator_key='management.reports', scenario_key='SCN-REPORT-01',
            reset_policy=RESET_FRESH_DB_ONLY, reset_sequence=1295, record_user=self.manager,
        )

    def generate(self):
        self.preflight()
        for family in SOURCE_KEYS:
            self._generate_family(family)
        self.validate()
        return self.counts

    def generate_family(self, family):
        self.preflight()
        self._generate_family(family)
        self.validate(families={family})
        return self.counts

    def _generate_family(self, family):
        if family == 'FIN-INS':
            self.insurance()
        elif family == 'OPS-MEM':
            self.membership()
        elif family == 'OPS-INV':
            self.inventory(self.refs['DEMO-PAT-INS-001'])
        elif family == 'OPS-WALLET':
            self.wallet(self.refs['DEMO-PAT-MEM-001'])
        elif family == 'CLN-PROC':
            self.procedure()
        else:
            raise UserError('Unknown source journey: ' + family)

    def insurance(self):
        c = self.company.id
        branch = self.refs['DEMO-BRANCH-001']
        insured = self.refs['DEMO-PAT-INS-001']
        member = self.refs['DEMO-PAT-MEM-001']
        plan = self.refs['DEMO-INS-PLAN-CORP80']
        # Prepared payer request: enrollment remains unverified, so no synthetic
        # eligibility or payer approval is fabricated and no external submission occurs.
        policy = self.ensure('DEMO-SOURCE-POLICY-001', 'clinic.insurance.policy', {
            'name': 'DEMO-SOURCE-POLICY-001', 'company_id': c, 'branch_id': branch.id,
            'patient_id': insured.id, 'plan_id': plan.id, 'insurer_partner_id': plan.insurer_partner_id.id,
            'policy_number': 'DEMO-SOURCE-POLICY-001', 'start_date': self.day,
            'end_date': self.day + timedelta(days=365),
        })
        auth = self.ensure('DEMO-SOURCE-AUTH-001', 'clinic.insurance.authorization', {
            'name': 'DEMO-SOURCE-AUTH-001', 'policy_id': policy.id, 'patient_id': insured.id,
            'company_id': c, 'branch_id': branch.id, 'request_date': self.day, 'service_date': self.day,
            'source_type': 'manual', 'submission_channel': 'manual',
            'line_ids': [(0, 0, {'description': 'Synthetic consultation pre-authorization request',
                'quantity': 1, 'unit_price': 250000, 'coverage_percent': 80, 'copay_percent': 20})],
        })
        if auth.state == 'draft':
            auth.action_prepare()

    def membership(self):
        c = self.company.id
        branch = self.refs['DEMO-BRANCH-001']
        insured = self.refs['DEMO-PAT-INS-001']
        member = self.refs['DEMO-PAT-MEM-001']
        plan = self.refs['DEMO-INS-PLAN-CORP80']
        self.ensure('DEMO-SOURCE-MEMBER-001', 'membership.contract', {
            'name': 'DEMO-SOURCE-MEMBER-001', 'company_id': c, 'currency_id': self.company.currency_id.id,
            'partner_id': member.partner_id.id, 'patient_id': member.id,
            'plan_id': self.refs['DEMO-MEM-PLAN-ESSENTIAL'].id,
            'start_date': self.day, 'end_date': self.day + timedelta(days=365),
        })

    def procedure(self):
        c = self.company.id
        branch = self.refs['DEMO-BRANCH-001']
        insured = self.refs['DEMO-PAT-INS-001']
        member = self.refs['DEMO-PAT-MEM-001']
        plan = self.refs['DEMO-INS-PLAN-CORP80']
        enc = self.refs['DEMO-ENC-LIVE-001']
        proc = self.refs['DEMO-PROC-CONSULT']
        start = enc.date_planned_start + timedelta(minutes=5)
        end = min(start + timedelta(minutes=15), enc.date_planned_end)
        session = self.ensure('DEMO-SOURCE-PROC-001', 'clinic.procedure.session', {
            'name': 'DEMO-SOURCE-PROC-001', 'company_id': c, 'encounter_id': enc.id,
            'procedure_id': proc.id, 'product_id': proc.product_id.id, 'uom_id': proc.uom_id.id,
            'quantity': 1, 'planned_start': start, 'planned_end': end,
            'date_start': start, 'date_end': end,
        })
        if session.state == 'draft':
            session.action_start()
        if session.state == 'in_progress':
            session.action_done()
        for event in ('create', 'start', 'done'):
            log = self.model('clinic.execution.log').search([
                ('session_id', '=', session.id), ('event_type', '=', event),
                ('name', '=', 'DEMO-SOURCE-PROC-001-' + event.upper()),
            ])
            if len(log) != 1:
                raise UserError(f'Procedure must have one deterministic {event} log')
            self.bind('DEMO-SOURCE-PROC-001-' + event.upper(), log)

    def inventory(self, patient):
        c = self.company.id
        wh = self.refs['DEMO-WAREHOUSE-PRIMARY']
        category = self.ensure('DEMO-SOURCE-CATEGORY-001', 'product.category', {'name': 'DEMO-SOURCE Clinical Consumables'})
        product = self.ensure('DEMO-SOURCE-STOCK-PRODUCT-001', 'product.product', {
            'name': 'Synthetic donated gauze - demo consumption', 'default_code': 'DEMO-SOURCE-GAUZE',
            'company_id': c, 'type': 'consu', 'is_storable': True, 'tracking': 'none',
            'uom_id': self.ctx.env.ref('uom.product_uom_unit').id,
            'categ_id': category.id, 'standard_price': 0.0,
        })
        source = self.ensure('DEMO-SOURCE-STOCK-LOCATION-001', 'stock.location', {
            'name': 'DEMO-SOURCE Stock', 'usage': 'internal', 'company_id': c, 'location_id': wh.view_location_id.id,
        })
        sink = self.ensure('DEMO-SOURCE-STOCK-SINK-001', 'stock.location', {
            'name': 'DEMO-SOURCE Consumption', 'usage': 'inventory', 'company_id': c, 'location_id': wh.view_location_id.id,
        })
        supplier = self.ensure('DEMO-SOURCE-STOCK-SUPPLIER-001', 'stock.location', {
            'name': 'DEMO-SOURCE Donor', 'usage': 'supplier', 'company_id': c,
        })
        # Exercise the owner template/variant contract before any stock movement.
        payload = product.clinic_prepare_consumption_move_vals(
            qty=1, uom=product.uom_id, patient=patient.partner_id, location=source)
        unknown = set(payload) - set(self.model('stock.move')._fields)
        required = {'origin', 'product_id', 'product_uom', 'product_uom_qty'}
        missing = required - set(payload)
        if unknown or missing:
            raise UserError('Consumption payload contract: unknown fields %s; missing keys %s'
                            % (sorted(unknown), sorted(missing)))
        received = datetime.combine(self.day, time(8, 0))
        used = received + timedelta(hours=2)
        receipt = self.ensure('DEMO-SOURCE-RECEIPT-001', 'stock.move', {
            'origin': 'DEMO-SOURCE-RECEIPT-001', 'company_id': c, 'product_id': product.id,
            'product_uom': product.uom_id.id, 'product_uom_qty': 10,
            'location_id': supplier.id, 'location_dest_id': source.id, 'date': received,
        })
        if receipt.state != 'done':
            if receipt.state != 'draft':
                raise UserError('Demo receipt has an unexpected intermediate state')
            receipt._action_confirm()
            receipt.write({'move_line_ids': [(0, 0, {'product_id': product.id,
                'product_uom_id': product.uom_id.id, 'quantity': 10,
                'location_id': supplier.id, 'location_dest_id': source.id})]})
            receipt.write({'picked': True})
            receipt._action_done()
            # Native stock workflow stamps processing time. Set the explicit
            # business event date on this new, zero-value demo receipt only.
            receipt.write({'date': received})
            receipt.move_line_ids.write({'date': received})
        usage = self.ensure('DEMO-SOURCE-USAGE-001', 'clinic.treatment.product.usage', {
            'name': 'DEMO-SOURCE-USAGE-001', 'company_id': c, 'warehouse_id': wh.id,
            'patient_id': patient.partner_id.id, 'src_location_id': source.id,
            'dest_location_id': sink.id, 'date_usage': used,
            'line_ids': [(0, 0, {'product_id': product.id, 'product_uom': product.uom_id.id, 'product_uom_qty': 1})],
        })
        if usage.state == 'draft':
            usage.action_consume()
            usage.move_ids.write({'date': used})
            usage.move_ids.move_line_ids.write({'date': used})
        if len(usage.move_ids) != 1 or usage.move_ids.state != 'done':
            raise UserError('Demo consumption must have exactly one completed owner stock move')
        self.bind('DEMO-SOURCE-CONSUMPTION-MOVE-001', usage.move_ids)

    def wallet(self, patient):
        c = self.company.id
        # No fallback to the first production journal or liability account.
        cash = self.ensure('DEMO-SOURCE-WALLET-CASH-001', 'account.account', {
            'name': 'Demo Wallet Cash Clearing', 'code': 'DEMO4801', 'account_type': 'asset_current', 'company_ids': [(6, 0, [c])],
        })
        liability = self.ensure('DEMO-SOURCE-WALLET-LIABILITY-001', 'account.account', {
            'name': 'Demo Wallet Liability', 'code': 'DEMO4802', 'account_type': 'liability_current', 'company_ids': [(6, 0, [c])],
        })
        journal = self.ensure('DEMO-SOURCE-WALLET-JOURNAL-001', 'account.journal', {
            'name': 'Demo Wallet Journal', 'code': 'DW48', 'type': 'general',
            'company_id': c, 'default_account_id': cash.id,
        })
        wallet = self.ensure('DEMO-SOURCE-WALLET-001', 'clinic.wallet', {
            'name': 'DEMO-SOURCE-WALLET-001', 'company_id': c, 'currency_id': self.company.currency_id.id,
            'patient_id': patient.id, 'partner_id': patient.partner_id.id, 'issue_date': self.day,
            'expiry_policy': 'none',
        })
        if wallet.state == 'draft':
            wallet.action_open()
        tx = self.ensure('DEMO-SOURCE-TOPUP-001', 'clinic.wallet.transaction', {
            'name': 'DEMO-SOURCE-TOPUP-001', 'wallet_id': wallet.id, 'transaction_type': 'topup',
            'amount': 500000, 'date': datetime.combine(self.day, time(9, 0)), 'journal_id': journal.id,
        })
        if tx.state == 'draft':
            tx.action_post(accounting_name=f'DW48/{self.day.year}/0001', accounting_date=self.day,
                           liability_account_id=liability.id)
        if not tx.move_id or tx.move_id.state != 'posted' or tx.move_id.date != self.day:
            raise UserError('Wallet top-up must have an anchor-dated posted journal')
        self.bind('DEMO-SOURCE-WALLET-MOVE-001', tx.move_id)

    def validate(self, reports=False, families=None):
        issues = []
        selected = set(SOURCE_KEYS) if families is None else set(families)
        for report, (key, model, state) in SOURCE_KEYS.items():
            if report not in selected:
                continue
            rec = self.owner._resolve(self.ctx, key, model, missing_ok=True, user=self.manager)
            if not rec or rec.state != state:
                issues.append(f'{report}: {key} must be {state}')
            if reports and rec:
                output = self.owner._resolve(self.ctx, f'DEMO-REPORT-{report}', 'clinic.report.run', missing_ok=True, user=self.manager)
                if not output or not output.detail_ids.filtered(lambda line: line.source_model == model and line.source_res_id == rec.id):
                    issues.append(f'{report}: report details must trace to {key}')
        resolve = lambda key, model: self.owner._resolve(self.ctx, key, model, missing_ok=True, user=self.manager)
        auth = resolve('DEMO-SOURCE-AUTH-001', 'clinic.insurance.authorization') if 'FIN-INS' in selected else False
        if auth and (auth.request_date != self.day or len(auth.line_ids) != 1
                     or auth.line_ids.requested_amount <= 0 or auth.patient_id != auth.policy_id.patient_id):
            issues.append('Insurance request date, positive service or patient-policy link is invalid')
        member = resolve('DEMO-SOURCE-MEMBER-001', 'membership.contract') if 'OPS-MEM' in selected else False
        if member and (member.start_date != self.day or member.end_date <= member.start_date or member.contract_value <= 0):
            issues.append('Membership enrollment must have a positive term and commercial value')
        tx = resolve('DEMO-SOURCE-TOPUP-001', 'clinic.wallet.transaction') if 'OPS-WALLET' in selected else False
        if tx and (tx.amount != 500000 or not tx.move_id or tx.move_id.state != 'posted'
                   or tx.move_id.name != f'DW48/{self.day.year}/0001' or tx.move_id.date != self.day
                   or tx.date.date() != self.day or tx.wallet_id.state != 'open'
                   or abs(sum(tx.move_id.line_ids.mapped('debit')) - sum(tx.move_id.line_ids.mapped('credit'))) > 0.001):
            issues.append('Wallet must retain the expected positive balanced posted journal and business date')
        usage = resolve('DEMO-SOURCE-USAGE-001', 'clinic.treatment.product.usage') if 'OPS-INV' in selected else False
        if usage and (len(usage.move_ids) != 1 or usage.move_ids.state != 'done'
                      or usage.move_ids.quantity != 1 or usage.date_usage.date() != self.day):
            issues.append('Inventory must retain one completed unit of source consumption')
        session = resolve('DEMO-SOURCE-PROC-001', 'clinic.procedure.session') if 'CLN-PROC' in selected else False
        if session and (not session.date_start or not session.date_end
                        or not session.encounter_id.date_planned_start <= session.date_start < session.date_end <= session.encounter_id.date_planned_end):
            issues.append('Procedure must have a positive execution window inside its encounter')
        if session and session.date_start and session.date_end:
            for event, expected_date in [('create', session.date_start - timedelta(minutes=1)),
                                         ('start', session.date_start), ('done', session.date_end)]:
                log = resolve('DEMO-SOURCE-PROC-001-' + event.upper(), 'clinic.execution.log')
                if not log or log.session_id != session or log.date_event != expected_date:
                    issues.append(f'Procedure {event} log must retain its explicit identity and event time')
        if issues:
            raise UserError('Source journeys evidence failed: ' + '; '.join(issues))













