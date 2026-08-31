

# -*- coding: utf-8 -*-
# from odoo import http


# class ClinicDoctor(http.Controller):
#     @http.route('/clinic_doctor/clinic_doctor', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_doctor/clinic_doctor/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_doctor.listing', {
#             'root': '/clinic_doctor/clinic_doctor',
#             'objects': http.request.env['clinic_doctor.clinic_doctor'].search([]),
#         })

#     @http.route('/clinic_doctor/clinic_doctor/objects/<model("clinic_doctor.clinic_doctor"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_doctor.object', {
#             'object': obj
#         })


