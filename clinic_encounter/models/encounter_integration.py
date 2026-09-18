from odoo import _, api, fields, models
# encounter_id

class ClinicPatientVitalEncounter(models.Model):
    _inherit = 'clinic.patient.vital'

    encounter_id = fields.Many2one(comodel_name="clinic.encounter", string="Encounter")
    



