
# -*- coding: utf-8 -*-
# from odoo import http


# class ClinicBase(http.Controller):
#     @http.route('/clinic_base/clinic_base', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_base/clinic_base/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_base.listing', {
#             'root': '/clinic_base/clinic_base',
#             'objects': http.request.env['clinic_base.clinic_base'].search([]),
#         })

#     @http.route('/clinic_base/clinic_base/objects/<model("clinic_base.clinic_base"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_base.object', {
#             'object': obj
#         })


