
# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class clinic_room_device(models.Model):
#     _name = 'clinic_room_device.clinic_room_device'
#     _description = 'clinic_room_device.clinic_room_device'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

