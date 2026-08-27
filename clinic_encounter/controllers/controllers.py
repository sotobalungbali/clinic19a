# -*- coding: utf-8 -*-
# from odoo import http


# class ClinicEncounter(http.Controller):
#     @http.route('/clinic_encounter/clinic_encounter', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_encounter/clinic_encounter/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_encounter.listing', {
#             'root': '/clinic_encounter/clinic_encounter',
#             'objects': http.request.env['clinic_encounter.clinic_encounter'].search([]),
#         })

#     @http.route('/clinic_encounter/clinic_encounter/objects/<model("clinic_encounter.clinic_encounter"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_encounter.object', {
#             'object': obj
#         })

