# -*- coding: utf-8 -*-
# from odoo import http


# class ClinicImaging(http.Controller):
#     @http.route('/clinic_imaging/clinic_imaging', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_imaging/clinic_imaging/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_imaging.listing', {
#             'root': '/clinic_imaging/clinic_imaging',
#             'objects': http.request.env['clinic_imaging.clinic_imaging'].search([]),
#         })

#     @http.route('/clinic_imaging/clinic_imaging/objects/<model("clinic_imaging.clinic_imaging"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_imaging.object', {
#             'object': obj
#         })

