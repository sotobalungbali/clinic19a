"""All controls dispatch into the same journey engine."""
from odoo import api, fields, models
from odoo.exceptions import UserError

class ClinicDemoRunJourneys(models.Model):
    _inherit = 'clinic.demo.run'
    journey_ids = fields.One2many('clinic.demo.journey', 'run_id', readonly=True)
    selected_journey_id = fields.Many2one('clinic.demo.journey', domain="[('run_id','=',id)]", ondelete='set null')
    journey_progress = fields.Float(compute='_compute_journey_progress', string='Validated progress (%)')
    reporting_evidence = fields.Text(readonly=True)
    reporting_status = fields.Selection([('pending','Pending'),('fail','Insufficient'),('pass','Sufficient')], default='pending', readonly=True)

    @api.depends('journey_ids.state')
    def _compute_journey_progress(self):
        for run in self:
            run.journey_progress = 100 * len(run.journey_ids.filtered(lambda row: row.state == 'pass')) / len(run.journey_ids) if run.journey_ids else 0

    def _journey_action(self, mode, key=None):
        self.ensure_one()
        self._check_generation_preflight()
        from ..services.journey_engine import JourneyEngine
        return JourneyEngine(self.env).dispatch(self, mode, key)

    def action_reconcile_existing(self):
        return self._journey_action('reconcile')

    def action_execute_current(self):
        self.ensure_one()
        if not self.selected_journey_id or self.selected_journey_id.run_id != self:
            raise UserError('Select a journey belonging to this Demo Run.')
        return self._journey_action('current', self.selected_journey_id.journey_key)

    def action_execute_next(self):
        return self._journey_action('next')

    def action_rebuild_journeys(self):
        # Rebuild never deletes: reset preview/confirmation remains owner-controlled.
        return self._journey_action('full')

    def action_open_journeys(self):
        self.ensure_one()
        return {'type':'ir.actions.act_window','name':'Journey Progress','res_model':'clinic.demo.journey',
                'view_mode':'list,form','domain':[('run_id','=',self.id)]}

    def action_validate(self):
        self.ensure_one()
        self._check_generation_preflight()
        from ..services.journey_engine import JourneyEngine
        from ..services.reporting_sufficiency import evaluate
        rows=JourneyEngine(self.env).reconcile(self)
        result=super().action_validate()
        reporting_ok=evaluate(self)
        journey_ok=all(row.state=='pass' for row in rows.values())
        Result=self.env['clinic.demo.validation.result']
        for key,ok,evidence in [('journey.actual_progress',journey_ok,'Actual identity, scope and owner validator evidence'),
                                ('reporting.sufficiency',reporting_ok,self.reporting_evidence)]:
            row=Result.search([('run_id','=',self.id),('check_key','=',key)],limit=1)
            vals={'run_id':self.id,'check_key':key,'category':'journey migration','severity':'info' if ok else 'critical',
                  'state':'pass' if ok else 'fail','message':evidence}
            row.write(vals) if row else Result.create(vals)
        if not (reporting_ok and journey_ok):
            self.write({'state':'failed','validation_status':'fail'})
            return self._display_notification('Dataset acceptance incomplete',
                'Review Journey Progress and Reporting Sufficiency. Technical generation does not prove enterprise population sufficiency.',
                'danger',sticky=True)
        return result

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








