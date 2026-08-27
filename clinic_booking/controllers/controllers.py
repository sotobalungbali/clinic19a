# -*- coding: utf-8 -*-
# from odoo import http


# class ClinicBooking(http.Controller):
#     @http.route('/clinic_booking/clinic_booking', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_booking/clinic_booking/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_booking.listing', {
#             'root': '/clinic_booking/clinic_booking',
#             'objects': http.request.env['clinic_booking.clinic_booking'].search([]),
#         })

#     @http.route('/clinic_booking/clinic_booking/objects/<model("clinic_booking.clinic_booking"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_booking.object', {
#             'object': obj
#         })

