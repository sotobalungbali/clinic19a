"""Bounded population owner adapters. One domain/month per transaction savepoint."""
from datetime import timedelta
from odoo.exceptions import UserError
from .population_plan import DOMAINS, PATIENT_KEYS, entries, prefix, reference_keys
from .constants import RESET_FRESH_DB_ONLY
from ..generators.management.source_journeys import ReportSourceJourneys, PREREQUISITES

EXTRA = {
 'booking.booking': ('name patient_id doctor_id treatment_id start_datetime end_datetime auto_create_appointment lock_slot_on_confirm checkin_time checkout_time', ('action_confirm','action_done','action_cancel')),
 'clinic.encounter': ('appointment_id name patient_id doctor_id user_id stage_id date_planned_start date_planned_end date_start date_end diagnosis_note', ('action_start','action_done','action_cancel')),
 'clinic.billing.invoice': ('encounter_id name clinic_patient_id patient_id invoice_date invoice_date_due journal_id line_ids external_origin', ('action_confirm','action_generate_account_move','action_post_account_move','action_cancel','_validate_explicit_income_account','_clinic_demo_generate_move_with_income')),
 'clinic.billing.line': ('invoice_id name product_id product_uom_id quantity unit_price tax_ids',()),
 'account.move': ('invoice_line_ids',('_clinic_billing_product_invoice_lines',)),
 'account.move.line': ('account_id clinic_billing_line_id',()),
 'stock.move': ('origin company_id product_id product_uom product_uom_qty location_id location_dest_id move_line_ids state date picked',('_clinic_demo_complete_bounded_receipt','_clinic_demo_has_completed_quantity')),
 'stock.warehouse': ('name code company_id branch_id view_location_id',('_clinic_demo_create_bounded_warehouse',)),
 'clinic.incident': ('name title category_id company_id branch_id classification severity harm_level recurrence_risk occurred_at case_owner_id description immediate_action',('action_report','action_start_triage')),
 'clinic.insurance.authorization': ('request_date service_date',('action_cancel',)),
 'membership.contract': ('start_date end_date',('action_cancel',)),
 'clinic.wallet.transaction': ('date',('action_cancel',)),
 'clinic.procedure.session': ('planned_start planned_end date_start date_end',('action_cancel',)),
 'clinic.treatment.product.usage': ('date_usage',('action_cancel',)),
}

class PopulationService:
    def __init__(self, source, key):
        self.source=source;self.ctx=source.ctx;self.owner=source.owner;self.manager=source.manager
        self.run=self.ctx.run;self.company=self.run.company_id;self.key=key
        self.counts=self.owner._counts();self.dry=False
        self.domain,self.month=('setup',0) if key=='population.setup' else (key.split('.')[1],int(key.split('.')[2][1:]))

    def model(self,name):
        return self.source.model(name).with_context(tracking_disable=True,mail_create_nosubscribe=True,
            mail_notify_noemail=True,mail_notify_force_send=False,
            clinic_demo_safe_mode=True,tz=self.run.timezone or 'UTC')

    def resolve(self,key,model):
        return self.owner._resolve(self.ctx,key,model,user=self.manager)

    def expected_reference_keys(self):
        return reference_keys(self.run.anchor_date,self.domain,self.month)

    def income_account(self):
        """Freeze the exact Income account proven by the source Billing move."""
        bill=self.resolve('DEMO-BILL-001','clinic.billing.invoice')
        source_line=bill.line_ids.filtered(
            lambda line:line.display_type not in ('line_section','line_note'))
        if len(source_line)!=1 or not bill.move_id or bill.move_id.state!='posted':
            raise UserError('DEMO-BILL-001 must have one monetary line and a posted move')
        move_line=bill.move_id._clinic_billing_product_invoice_lines().filtered(
            lambda line:line.clinic_billing_line_id.id==source_line.id)
        if len(move_line)!=1:
            raise UserError('DEMO-BILL-001 accounting line provenance is not exact')
        account=move_line.account_id
        if (not account or account.account_type!='income'
                or self.company not in account.company_ids):
            raise UserError('DEMO-BILL-001 does not prove one company-scoped Income account')
        bill._validate_explicit_income_account(account)
        return account

    def preflight(self):
        self.source.preflight()
        issues=[]
        if self.run.profile!='full_enterprise':issues.append('Population v1 requires Full Enterprise profile')
        for name,(names,methods) in EXTRA.items():
            m=self.model(name)
            missing=set(names.split())-set(m._fields)
            if missing:issues.append(f'{name} missing fields {sorted(missing)}')
            for op in ('read','create','write'):
                try:m.browse().check_access(op)
                except Exception as exc:issues.append(f'{name} {op}: {exc}')
            for method in methods:
                if not callable(getattr(m,method,None)):issues.append(f'{name}.{method} missing')
        for key in PATIENT_KEYS:
            self.resolve(key,'clinic.patient')
        for key,model in [('DEMO-BILL-001','clinic.billing.invoice'),('DEMO-INC-001','clinic.incident'),
                          ('DEMO-SOURCE-WALLET-JOURNAL-001','account.journal'),
                          ('DEMO-SOURCE-WALLET-LIABILITY-001','account.account'),
                          ('DEMO-SOURCE-STOCK-PRODUCT-001','product.product')]:self.resolve(key,model)
        bill=self.resolve('DEMO-BILL-001','clinic.billing.invoice')
        if not bill.move_id or not bill.move_id.journal_id:issues.append('Posted source billing journal is required')
        try:self.income_account()
        except Exception as exc:issues.append(f'Billing Income account contract: {exc}')
        for model,method in [('clinic.billing.invoice','_explicit_billing_event_name'),('membership.contract','_explicit_membership_event_name')]:
            if not callable(getattr(self.model(model),method,None)):issues.append(model+': explicit event-name API missing')
        for model in ('clinic.billing.integration.event','membership.integration.event'):
            for op in ('read','write'):
                try:self.model(model).browse().check_access(op)
                except Exception as exc:issues.append(f'{model} {op}: {exc}')
        if issues:raise UserError('Population whole-path preflight: '+'; '.join(issues))

    def ensure(self,key,model,values,context=None):
        Model=self.model(model).with_context(**(context or {}))
        if model=='clinic.billing.invoice':
            events=('invoice_created','invoice_confirmed','invoice_posted','invoice_paid','invoice_cancelled')
            Model=Model.with_context(clinic_billing_event_names={key+':'+event:key+'-EVT-'+event.upper() for event in events})
        if model=='membership.contract':
            Model=Model.with_context(clinic_membership_event_names={key+':contract.cancelled':key+'-EVT-CANCELLED'})
        missing=set(values)-set(Model._fields)
        if missing:raise UserError(f'{model} unknown payload fields {sorted(missing)}')
        if self.dry:
            record=self.resolve(key,model)
        else:
            if model == 'stock.warehouse':
                create_callback=lambda: Model.with_context(
                    clinic_demo_safe_mode=True,
                    clinic_demo_run_id=self.run.id,
                )._clinic_demo_create_bounded_warehouse(values)
            else:
                create_callback=lambda: Model.create(values)
            record,ref,status=self.ctx.reference_service.ensure_record(
                run=self.run,demo_key=key,model_name=model,generator_key='management.reports',
                scenario_key='SCN-REPORT-01',create_callback=create_callback,update_callback=None,
                reset_policy=RESET_FRESH_DB_ONLY,reset_sequence=1280,record_user=self.manager)
            if ref.ownership_kind=='reused':raise UserError(f'{key}: external record cannot be adopted')
            self.counts[status]+=1
        record=Model.browse(record.id)
        record.check_access('read')
        if 'company_id' in record._fields and record.company_id and record.company_id!=self.company:
            raise UserError(f'{key}: wrong company')
        for field,expected in values.items():
            if isinstance(expected,list):continue
            actual=record[field]
            if record._fields[field].type=='many2one':actual=actual.id
            if actual!=expected:raise UserError(f'{key}.{field}: existing data differs from frozen population plan')
        return record

    def bind(self,key,rec):
        if self.dry:
            if self.resolve(key,rec._name)!=rec:raise UserError(f'{key}: owner child provenance mismatch')
        else:
            self.ctx.reference_service.bind(run=self.run,demo_key=key,record=rec,
                generator_key='management.reports',scenario_key='SCN-REPORT-01',
                reset_policy=RESET_FRESH_DB_ONLY,reset_sequence=1295,record_user=self.manager)

    def finish(self,rec,wanted,actions):
        if not self.dry and rec.state!=wanted:
            if rec.state!='draft':raise UserError(f'{rec.display_name}: unexpected intermediate state {rec.state}; expected {wanted}')
            for action,kwargs in actions:getattr(rec,action)(**kwargs)
        if rec.state!=wanted:raise UserError(f'{rec.display_name}: expected {wanted}, found {rec.state}')

    def shared(self):
        c=self.company.id
        for i in range(1,4):
            wh=self.ensure(f'DEMO-POP-SETUP-WH-{i}','stock.warehouse',
                           {'name':f'Demo Population Supply Unit {i}','code':f'DP{i}',
                            'company_id':c,'branch_id':False})
            for tag,usage in [('STOCK','internal'),('SINK','inventory'),('DONOR','supplier')]:
                self.ensure(f'DEMO-POP-SETUP-{tag}-{i}','stock.location',
                            {'name':f'Demo Population {tag} {i}','usage':usage,'company_id':c,
                             'location_id':wh.view_location_id.id})
        for i,key in enumerate(PATIENT_KEYS):
            patient=self.resolve(key,'clinic.patient')
            wallet=self.ensure(f'DEMO-POP-SETUP-WALLET-{i}','clinic.wallet',
                {'name':f'DEMO-POP-SETUP-WALLET-{i}','company_id':c,'currency_id':self.company.currency_id.id,
                 'patient_id':patient.id,'partner_id':patient.partner_id.id,
                 'issue_date':self.run.anchor_date-timedelta(days=365),'expiry_policy':'none'})
            self.finish(wallet,'open',[('action_open',{})])

    def patient(self,item):return self.resolve(item['patient'],'clinic.patient')

    def booking(self,item):
        from ..generators.operations.booking import BookingOperationsGenerator
        adapter=BookingOperationsGenerator();patient=self.patient(item)
        doctor=adapter._doctor_for_patient(self.ctx,patient)
        treatment=self.resolve('DEMO-TREAT-CONSULT-GEN','clinic.treatment')
        # Fixed short slots, with room/resource assignment left to later scheduling.
        # This is a booking request workflow, not a fabricated resource reservation.
        values=dict(name=item['key'],company_id=self.company.id,patient_id=patient.partner_id.id,
                    doctor_id=doctor.id,treatment_id=treatment.id,start_datetime=item['at'],
                    end_datetime=item['at']+timedelta(minutes=5),auto_create_appointment=False,
                    lock_slot_on_confirm=False)
        if not item['cancelled']:values.update(checkin_time=item['at'],checkout_time=item['at']+timedelta(minutes=5))
        rec=self.ensure(item['key'],'booking.booking',values)
        actions=[('action_cancel',{'reason':'Synthetic historical patient cancellation'})] if item['cancelled'] else [('action_confirm',{}),('action_done',{})]
        self.finish(rec,'cancelled' if item['cancelled'] else 'done',actions)

    def procedure(self,item):
        from ..generators.operations.booking import BookingOperationsGenerator
        patient=self.patient(item);doctor=BookingOperationsGenerator()._doctor_for_patient(self.ctx,patient)
        start=item['at'];end=start+timedelta(minutes=5)
        key=item['key'];enc_key=key+'-ENC'
        # A new encounter owns each procedure; completed original encounters are untouched.
        enc=self.ensure(enc_key,'clinic.encounter',dict(name=enc_key,company_id=self.company.id,
            patient_id=patient.id,doctor_id=doctor.id,user_id=doctor.user_id.id,
            appointment_id=self.resolve(key.replace('PROCEDURE','BOOKING'),'booking.booking').id,
            date_planned_start=start,date_planned_end=end,date_start=False if item['cancelled'] else start,date_end=False if item['cancelled'] else end,
            diagnosis_note='Synthetic follow-up consultation; no real patient diagnosis.'))
        proc=self.resolve('DEMO-PROC-CONSULT','clinic.procedure.catalog')
        events={event:{'name':key+'-'+event.upper(),'date_event':at}
                for event,at in [('create',start-timedelta(minutes=1)),('start',start),('done',end),('cancel',start)]}
        rec=self.ensure(key,'clinic.procedure.session',dict(name=key,company_id=self.company.id,
            encounter_id=enc.id,procedure_id=proc.id,product_id=proc.product_id.id,uom_id=proc.uom_id.id,
            quantity=1,planned_start=start,planned_end=end,date_start=False if item['cancelled'] else start,date_end=False if item['cancelled'] else end),
            {'clinic_execution_event_contract':events})
        actions=[('action_cancel',{'reason':'Synthetic patient cancellation'})] if item['cancelled'] else [('action_start',{}),('action_done',{})]
        self.finish(rec,'cancelled' if item['cancelled'] else 'done',actions)
        if not self.dry and enc.state=='in_progress' and not item['cancelled']:
            enc.action_done()
        self.finish(enc,'cancelled' if item['cancelled'] else 'done',
                    [('action_cancel',{})] if item['cancelled'] else [('action_done',{})])
        for event in (('create','cancel') if item['cancelled'] else ('create','start','done')):
            log=self.model('clinic.execution.log').search([('session_id','=',rec.id),('event_type','=',event),('name','=',events[event]['name'])])
            if len(log)!=1 or log.date_event!=events[event]['date_event']:raise UserError(key+': missing deterministic procedure event '+event)
            self.bind(events[event]['name'],log)

    def billing(self,item):
        patient=self.patient(item);source=self.resolve('DEMO-BILL-001','clinic.billing.invoice')
        product=source.line_ids.filtered(
            lambda line:line.display_type not in ('line_section','line_note'))[:1].product_id
        key=item['key'];journal=source.move_id.journal_id
        income=self.income_account()
        rec=self.ensure(key,'clinic.billing.invoice',dict(name=key,company_id=self.company.id,
            currency_id=self.company.currency_id.id,clinic_patient_id=patient.id,patient_id=patient.partner_id.id,
            invoice_date=item['day'],invoice_date_due=item['day']+timedelta(days=30),journal_id=journal.id,
            external_origin=key.replace('BILLING','PROCEDURE'),
            encounter_id=self.resolve(key.replace('BILLING','PROCEDURE')+'-ENC','clinic.encounter').id,
            line_ids=[(0,0,dict(name='Synthetic historical consultation',product_id=product.id,
                product_uom_id=product.uom_id.id,quantity=1,unit_price=item['amount'],tax_ids=[(6,0,[])]))]),
            {'clinic_billing_income_account_id':income.id})
        if len(rec.line_ids)!=1 or rec.line_ids.unit_price!=item['amount'] or rec.line_ids.product_id!=product:
            raise UserError(key+': billing source line drift')
        if item['cancelled']:
            self.finish(rec,'cancelled',[('action_cancel',{})])
            self.events(rec,item['key'],('invoice_created','invoice_cancelled'))
            return
        if not self.dry and rec.state=='draft' and not rec.move_id:
            rec.action_confirm();rec._clinic_demo_generate_move_with_income(income)
            # An explicit unique name is assigned to the new draft move before posting.
            rec.move_id.write({'name':f'DPOP/{item["day"].year}/{self.month:02d}{item["index"]+1:04d}', 'date':item['day']})
            rec.action_post_account_move()
        if rec.state!='posted' or not rec.move_id or rec.move_id.state!='posted' or rec.amount_total<=0:
            raise UserError(key+': positive posted invoice required')
        if rec.move_id.name!=f'DPOP/{item["day"].year}/{self.month:02d}{item["index"]+1:04d}' or rec.move_id.date!=item['day']:
            raise UserError(key+': accounting identity/date mismatch')
        money_lines=rec.move_id._clinic_billing_product_invoice_lines().filtered(
            lambda line:line.clinic_billing_line_id.id==rec.line_ids.id)
        if (len(money_lines)!=1 or money_lines.account_id.id!=income.id
                or money_lines.clinic_billing_line_id.id!=rec.line_ids.id):
            raise UserError(key+': explicit Income account was not honored by Billing owner')
        self.bind(key+'-MOVE',rec.move_id)
        self.events(rec,key,('invoice_created','invoice_confirmed','invoice_posted'))

    def insurance(self,item):
        patient=self.patient(item);plan=self.resolve('DEMO-INS-PLAN-CORP80','clinic.insurance.plan');key=item['key']
        branch=patient.partner_id.branch_id
        policy=self.ensure(key+'-POLICY','clinic.insurance.policy',dict(name=key+'-POLICY',company_id=self.company.id,
            branch_id=branch.id,patient_id=patient.id,plan_id=plan.id,insurer_partner_id=plan.insurer_partner_id.id,
            policy_number=key+'-POLICY',start_date=item['day'],end_date=item['day']+timedelta(days=365)))
        rec=self.ensure(key,'clinic.insurance.authorization',dict(name=key,company_id=self.company.id,
            branch_id=branch.id,policy_id=policy.id,patient_id=patient.id,request_date=item['day'],service_date=item['day'],
            source_type='manual',submission_channel='manual',line_ids=[(0,0,dict(description='Synthetic pre-authorization consultation request',
                quantity=1,unit_price=item['amount'],coverage_percent=80,copay_percent=20))]))
        self.finish(rec,'cancelled' if item['cancelled'] else 'prepared',
                    [('action_cancel',{})] if item['cancelled'] else [('action_prepare',{})])
        if len(rec.line_ids)!=1 or rec.line_ids.requested_amount!=item['amount']:raise UserError(key+': authorization lines drift')

    def membership(self,item):
        patient=self.patient(item);key=item['key'];plan=self.resolve('DEMO-MEM-PLAN-ESSENTIAL','membership.plan')
        rec=self.ensure(key,'membership.contract',dict(name=key,company_id=self.company.id,currency_id=self.company.currency_id.id,
            partner_id=patient.partner_id.id,patient_id=patient.id,plan_id=plan.id,start_date=item['day'],end_date=item['day']+timedelta(days=365)))
        self.finish(rec,'cancelled' if item['cancelled'] else 'draft',[('action_cancel',{})] if item['cancelled'] else [])
        if item['cancelled']:self.events(rec,key,('contract.cancelled',))
        if rec.contract_value<=0:raise UserError(key+': enrollment needs a positive plan value')

    def events(self,rec,key,codes):
        member=rec._name=='membership.contract'
        model='membership.integration.event' if member else 'clinic.billing.integration.event'
        for code in codes:
            name=key+'-EVT-'+('CANCELLED' if member else code.upper())
            event=self.model(model).search([('name','=',name)])
            if len(event)!=1 or event.company_id!=self.company:raise UserError(key+': missing owner event '+code)
            if member:
                if event.source_res_id!=rec.id or event.source_model!=rec._name or event.event_code!=code:raise UserError(key+': event source mismatch')
            elif event.invoice_id!=rec or event.event_type!=code:raise UserError(key+': event source mismatch')
            if not self.dry and event.state=='pending':event.action_ignore()
            if event.state!='ignored':raise UserError(key+': Safe Mode requires ignored event '+code)
            self.bind(name,event)

    def inventory(self,item):
        i=item['index']%3+1;key=item['key'];patient=self.patient(item)
        wh=self.resolve(f'DEMO-POP-SETUP-WH-{i}','stock.warehouse')
        source=self.resolve(f'DEMO-POP-SETUP-STOCK-{i}','stock.location')
        sink=self.resolve(f'DEMO-POP-SETUP-SINK-{i}','stock.location')
        donor=self.resolve(f'DEMO-POP-SETUP-DONOR-{i}','stock.location')
        product=self.resolve('DEMO-SOURCE-STOCK-PRODUCT-001','product.product')
        at=item['at'];qty=1+item['index']%3
        rec=self.ensure(key,'clinic.treatment.product.usage',dict(name=key,company_id=self.company.id,warehouse_id=wh.id,
            patient_id=patient.partner_id.id,src_location_id=source.id,dest_location_id=sink.id,date_usage=at,
            line_ids=[(0,0,dict(product_id=product.id,product_uom=product.uom_id.id,product_uom_qty=qty))]))
        if len(rec.line_ids)!=1 or rec.line_ids.product_uom_qty!=qty:raise UserError(key+': consumption lines drift')
        if item['cancelled']:
            self.finish(rec,'cancel',[('action_cancel',{})]);return
        received=at-timedelta(hours=1)
        receipt=self.ensure(key+'-RECEIPT','stock.move',dict(origin=key+'-RECEIPT',company_id=self.company.id,
            product_id=product.id,product_uom=product.uom_id.id,product_uom_qty=qty,
            location_id=donor.id,location_dest_id=source.id,date=received))
        if not self.dry and receipt.state=='draft':
            receipt._clinic_demo_complete_bounded_receipt(qty,received)
        if not receipt._clinic_demo_has_completed_quantity(qty):raise UserError(key+': stock receipt not complete')
        newly_consumed = not self.dry and rec.state == 'draft'
        self.finish(rec,'done',[('action_consume',{})])
        if newly_consumed:
            rec.move_ids.write({'date':at});rec.move_ids.move_line_ids.write({'date':at})
        if len(rec.move_ids)!=1 or not rec.move_ids._clinic_demo_has_completed_quantity(qty):raise UserError(key+': stock consumption not complete')
        self.bind(key+'-MOVE',rec.move_ids)

    def wallet(self,item):
        key=item['key'];i=item['index']%len(PATIENT_KEYS)
        wallet=self.resolve(f'DEMO-POP-SETUP-WALLET-{i}','clinic.wallet')
        journal=self.resolve('DEMO-SOURCE-WALLET-JOURNAL-001','account.journal')
        liability=self.resolve('DEMO-SOURCE-WALLET-LIABILITY-001','account.account')
        rec=self.ensure(key,'clinic.wallet.transaction',dict(name=key,wallet_id=wallet.id,transaction_type='topup',
            amount=item['amount'],date=item['at'],journal_id=journal.id))
        name=f'DPW/{item["day"].year}/{self.month:02d}{item["index"]+1:04d}'
        self.finish(rec,'canceled' if item['cancelled'] else 'posted',
            [('action_cancel',{})] if item['cancelled'] else [('action_post',dict(accounting_name=name,accounting_date=item['day'],liability_account_id=liability.id))])
        if not item['cancelled']:
            if not rec.move_id or rec.move_id.state!='posted' or rec.move_id.name!=name or rec.move_id.date!=item['day']:
                raise UserError(key+': wallet accounting mismatch')
            if abs(sum(rec.move_id.line_ids.mapped('debit'))-sum(rec.move_id.line_ids.mapped('credit')))>0.001:raise UserError(key+': unbalanced wallet posting')
            self.bind(key+'-MOVE',rec.move_id)

    def incident(self,item):
        source=self.resolve('DEMO-INC-001','clinic.incident');key=item['key']
        branch=self.patient(item).partner_id.branch_id
        rec=self.ensure(key,'clinic.incident',dict(name=key,company_id=self.company.id,
            branch_id=branch.id if self.company.policy_branch_scope_incident_event else False,
            title=('Stock handover delay' if item['index']==0 else 'Appointment coordination gap')+f' / period {self.month}',
            category_id=source.category_id.id,classification='operational',severity='high' if item['index']==0 else 'medium',
            harm_level='none',recurrence_risk='medium',occurred_at=item['at'],case_owner_id=self.manager.id,
            description='<p>Synthetic operational exception, retained for supervisor review; no patient harm.</p>',
            immediate_action='Workflow paused pending internal review. No external notification dispatched.'))
        self.finish(rec,'triage',[('action_report',{}),('action_start_triage',{})])

    def generate(self):
        self.preflight()
        self._run()
        self.validate()
        return self.counts

    def _run(self):
        if self.domain=='setup':self.shared();return
        for item in entries(self.run.anchor_date,self.domain,self.month):getattr(self,self.domain)(item)

    def validate(self):
        self.dry=True
        try:self._run()
        finally:self.dry=False
        return []





