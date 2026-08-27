# -*- coding: utf-8 -*-
# from odoo import http


# class ClinicPatient(http.Controller):
#     @http.route('/clinic_patient/clinic_patient', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_patient/clinic_patient/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_patient.listing', {
#             'root': '/clinic_patient/clinic_patient',
#             'objects': http.request.env['clinic_patient.clinic_patient'].search([]),
#         })

#     @http.route('/clinic_patient/clinic_patient/objects/<model("clinic_patient.clinic_patient"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_patient.object', {
#             'object': obj
#         })


