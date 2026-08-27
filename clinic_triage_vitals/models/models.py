
# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class clinic_triage_vitals(models.Model):
#     _name = 'clinic_triage_vitals.clinic_triage_vitals'
#     _description = 'clinic_triage_vitals.clinic_triage_vitals'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

