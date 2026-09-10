
# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class clinic_queue_room(models.Model):
#     _name = 'clinic_queue_room.clinic_queue_room'
#     _description = 'clinic_queue_room.clinic_queue_room'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
