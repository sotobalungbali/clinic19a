# -*- coding: utf-8 -*-
# from odoo import http


# class ClinicTreatmentSession(http.Controller):
#     @http.route('/clinic_treatment_session/clinic_treatment_session', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_treatment_session/clinic_treatment_session/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_treatment_session.listing', {
#             'root': '/clinic_treatment_session/clinic_treatment_session',
#             'objects': http.request.env['clinic_treatment_session.clinic_treatment_session'].search([]),
#         })

#     @http.route('/clinic_treatment_session/clinic_treatment_session/objects/<model("clinic_treatment_session.clinic_treatment_session"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_treatment_session.object', {
#             'object': obj
#         })

