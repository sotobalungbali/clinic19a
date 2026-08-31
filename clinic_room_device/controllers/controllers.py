
# -*- coding: utf-8 -*-
# from odoo import http


# class ClinicRoomDevice(http.Controller):
#     @http.route('/clinic_room_device/clinic_room_device', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_room_device/clinic_room_device/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_room_device.listing', {
#             'root': '/clinic_room_device/clinic_room_device',
#             'objects': http.request.env['clinic_room_device.clinic_room_device'].search([]),
#         })

#     @http.route('/clinic_room_device/clinic_room_device/objects/<model("clinic_room_device.clinic_room_device"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_room_device.object', {
#             'object': obj
#         })

