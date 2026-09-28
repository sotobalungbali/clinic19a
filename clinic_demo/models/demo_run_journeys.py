"""All controls dispatch into the same journey engine."""
import json
from odoo import api, fields, models
from odoo.exceptions import UserError

class ClinicDemoRunJourneys(models.Model):
    _inherit = 'clinic.demo.run'
    journey_ids = fields.One2many('clinic.demo.journey', 'run_id', readonly=True)
    selected_journey_id = fields.Many2one('clinic.demo.journey', domain="[('run_id','=',id)]", ondelete='set null')
    journey_progress = fields.Float(compute='_compute_journey_progress', string='Validated progress (%)')
    reporting_evidence = fields.Text(readonly=True, copy=False)
    reporting_checked_at = fields.Datetime(readonly=True, copy=False)
    reporting_status = fields.Selection([('pending','Pending'),('fail','Insufficient'),('pass','Sufficient')], default='pending', readonly=True)

    @api.depends('journey_ids.state')
    def _compute_journey_progress(self):
        for run in self:
            run.journey_progress = 100 * len(run.journey_ids.filtered(lambda row: row.state == 'pass')) / len(run.journey_ids) if run.journey_ids else 0

    def _journey_action(self, mode, key=None):
        self.ensure_one()
        # Journey status fields are tracked.  A bounded Safe-Mode execution
        # must not turn those internal control writes into follower email at
        # HTTP post-commit, so the no-outbound contract starts at the run and
        # flows into every owner adapter.
        run = self.with_context(
            tracking_disable=True,
            mail_create_nosubscribe=True,
            mail_notify_noemail=True,
            mail_notify_force_send=False,
            clinic_demo_safe_mode=True,
        )
        run._check_generation_preflight()
        from ..services.journey_engine import JourneyEngine
        return JourneyEngine(run.env).dispatch(run, mode, key)

    def action_reconcile_existing(self):
        return self._journey_action('reconcile')

    def action_execute_current(self):
        self.ensure_one()
        if not self.selected_journey_id or self.selected_journey_id.run_id != self:
            raise UserError('Select a journey belonging to this Demo Run.')
        return self._journey_action('current', self.selected_journey_id.journey_key)

    def action_execute_next(self):
        return self._journey_action('next')

    def action_execute_next_10(self):
        return self._journey_action('next10')

    def action_rebuild_journeys(self):
        # Rebuild never deletes: reset preview/confirmation remains owner-controlled.
        return self._journey_action('full')

    def action_open_journeys(self):
        self.ensure_one()
        return {'views': [(False, 'list'), (False, 'form')], 'type':'ir.actions.act_window','name':'Journey Progress','res_model':'clinic.demo.journey',
                'view_mode':'list,form','domain':[('run_id','=',self.id)]}

    def action_validate(self):
        self.ensure_one()
        self._check_generation_preflight()
        from ..services.journey_engine import JourneyEngine
        from ..services.reporting_sufficiency import evaluate
        rows, journey_issues = JourneyEngine(self.env).acceptance_snapshot(self)
        result=super().action_validate()
        owner_ok=self.validation_status!='fail'
        reporting_ok=evaluate(self)
        journey_ok=not journey_issues
        Result=self.env['clinic.demo.validation.result']
        journey_evidence = ('Persisted owner-validation evidence is complete for all registered journeys'
                            if journey_ok else '; '.join(journey_issues))
        for key,ok,evidence in [('journey.actual_progress',journey_ok,journey_evidence),
                                ('reporting.sufficiency',reporting_ok,self.reporting_evidence)]:
            row=Result.search([('run_id','=',self.id),('check_key','=',key)],limit=1)
            vals={'run_id':self.id,'check_key':key,'category':'journey migration','severity':'info' if ok else 'critical',
                  'state':'pass' if ok else 'fail','message':evidence}
            row.write(vals) if row else Result.create(vals)
        if not (owner_ok and reporting_ok and journey_ok):
            reasons=[]
            if not owner_ok:reasons.append('Owner readiness validation has critical failures')
            if journey_issues:reasons.append('Journey evidence: '+'; '.join(journey_issues[:3]))
            if not reporting_ok:
                try:
                    reporting=json.loads(self.reporting_evidence or '{}')
                    failed=[key for key,value in reporting.get('levels',{}).items() if value.get('state')!='PASS']
                    deficits=[]
                    for model,value in reporting.get('source_populations',{}).items():
                        minimum=reporting.get('domain_minimums',{}).get(model,0)
                        if value.get('count',0)<minimum:deficits.append(f'{model} {value.get("count",0)}/{minimum}')
                    errors=reporting.get('errors',[])
                    detail=[]
                    if failed:detail.append('levels '+', '.join(failed))
                    if deficits:detail.append('volume '+', '.join(deficits[:4]))
                    if errors:detail.append('evidence '+ '; '.join(errors[:2]))
                    reasons.append('Reporting Sufficiency: '+('; '.join(detail) if detail else 'insufficient evidence'))
                except Exception:
                    reasons.append('Reporting Sufficiency did not pass')
            self.write({'state':'failed','validation_status':'fail'})
            result = self._display_notification('Dataset acceptance incomplete',
                '. '.join(reasons)+'. Review Validation and Reporting Sufficiency for complete evidence.',
                'danger',sticky=True)
        # A notification alone leaves the loaded form and One2many evidence stale.
        # Reopen this exact run after the notification; normal RPC commit owns persistence.
        result['params']['next'] = {'views': [(False, 'form')], 
            'type': 'ir.actions.act_window', 'name': 'Demo Dataset Control Center',
            'res_model': 'clinic.demo.run', 'res_id': self.id,
            'view_mode': 'form', 'target': 'current',
        }
        return result

    def action_open_acceptance_results(self):
        self.ensure_one()
        return {'views': [(False, 'list'), (False, 'form')], 
            'type': 'ir.actions.act_window', 'name': 'Acceptance Results',
            'res_model': 'clinic.demo.validation.result', 'view_mode': 'list,form',
            'domain': [('run_id', '=', self.id), ('check_key', 'in',
                        ['journey.actual_progress', 'reporting.sufficiency'])],
        }

    def action_preview_journey_reset(self):
        self.ensure_one();self._check_operator();self.lock_for_update()
        import json
        from ..services.reset_service import DemoResetService
        from ..services.journey_registry import ordered_journeys
        specs=ordered_journeys();service=DemoResetService(self.env);details=[]
        for ref in self.reference_ids.sorted(key=lambda ref:ref.reset_sequence,reverse=True):
            try:decision=service.inspect(ref)
            except Exception as exc:decision={'action':'blocked','reason':str(exc)}
            details.append({'journey':ref.generator_key,'model':ref.model_name,'key':ref.demo_key,'count':1,
                            'ownership':ref.ownership_kind,'decision':decision,
                            'downstream':[s.key for s in specs if ref.generator_key in s.dependencies]})
        self.write({'reset_journey_evidence':json.dumps(details,sort_keys=True,default=str,indent=2)})
        return self.action_open_reset_wizard()

    reset_journey_evidence = fields.Text(readonly=True)


















