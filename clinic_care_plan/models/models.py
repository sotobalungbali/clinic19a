
# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class clinic_care_plan(models.Model):
#     _name = 'clinic_care_plan.clinic_care_plan'
#     _description = 'clinic_care_plan.clinic_care_plan'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

