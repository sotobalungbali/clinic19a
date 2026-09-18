# -*- coding: utf-8 -*-
# from odoo import http


# class ClinicInventory(http.Controller):
#     @http.route('/clinic_inventory/clinic_inventory', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_inventory/clinic_inventory/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_inventory.listing', {
#             'root': '/clinic_inventory/clinic_inventory',
#             'objects': http.request.env['clinic_inventory.clinic_inventory'].search([]),
#         })

#     @http.route('/clinic_inventory/clinic_inventory/objects/<model("clinic_inventory.clinic_inventory"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_inventory.object', {
#             'object': obj
#         })





