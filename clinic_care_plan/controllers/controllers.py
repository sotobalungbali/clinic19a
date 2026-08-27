
# -*- coding: utf-8 -*-
# from odoo import http


# class ClinicCarePlan(http.Controller):
#     @http.route('/clinic_care_plan/clinic_care_plan', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_care_plan/clinic_care_plan/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_care_plan.listing', {
#             'root': '/clinic_care_plan/clinic_care_plan',
#             'objects': http.request.env['clinic_care_plan.clinic_care_plan'].search([]),
#         })

#     @http.route('/clinic_care_plan/clinic_care_plan/objects/<model("clinic_care_plan.clinic_care_plan"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_care_plan.object', {
#             'object': obj
#         })

