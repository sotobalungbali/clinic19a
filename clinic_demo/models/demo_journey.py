"""Evidence-owned progress for one existing dataset, not a second dataset."""
from odoo import api, fields, models
from odoo.exceptions import AccessError

JOURNEY_TOKEN = object()

class ClinicDemoJourney(models.Model):
    _name = 'clinic.demo.journey'
    _description = 'Demo Journey Evidence'
    _order = 'sequence, id'
    run_id = fields.Many2one('clinic.demo.run', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='run_id.company_id', store=True, readonly=True)
    journey_key = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    sequence = fields.Integer()
    owner_addon = fields.Char()
    primary_model = fields.Char()
    master_prompt = fields.Char()
    dependencies = fields.Text()
    contract = fields.Text()
    state = fields.Selection([(s,s.upper()) for s in ('waiting','ready','running','pass','partial','blocked','failed')], default='waiting', required=True, index=True)
    classification = fields.Selection([(s,s.upper()) for s in ('adopt','reconcile','rebuild','block','missing')], default='missing')
    expected = fields.Integer(string='Expected minimum')
    existing = fields.Integer()
    adopted = fields.Integer()
    created = fields.Integer()
    reconciled = fields.Integer()
    invalid = fields.Integer()
    missing = fields.Integer()
    duplicate = fields.Integer()
    last_execution = fields.Datetime()
    last_validation = fields.Datetime()
    diagnostic = fields.Text()
    evidence = fields.Text()
    needs_refresh = fields.Boolean(default=False)
    _run_key_unique = models.Constraint('UNIQUE(run_id, journey_key)', 'Journey identity must be unique per run.')

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('_clinic_journey_token') is not JOURNEY_TOKEN:
            raise AccessError('Journey evidence is maintained by the execution engine.')
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('_clinic_journey_token') is not JOURNEY_TOKEN:
            raise AccessError('Journey evidence is maintained by the execution engine.')
        return super().write(vals)

    def action_execute_current(self):
        self.ensure_one()
        return self.run_id._journey_action('current', self.journey_key)

    def action_open_journey(self):
        self.ensure_one()
        return {'type':'ir.actions.act_window','name':self.name,'res_model':self._name,
                'view_mode':'form','res_id':self.id,'target':'current'}

    def action_open_run(self):
        self.ensure_one()
        return {'type':'ir.actions.act_window','name':'Demo Run','res_model':'clinic.demo.run',
                'view_mode':'form','res_id':self.run_id.id,'target':'current'}








