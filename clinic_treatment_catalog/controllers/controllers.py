# from odoo import http


# class ClinicTreatmentCatalog(http.Controller):
#     @http.route('/clinic_treatment_catalog/clinic_treatment_catalog', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_treatment_catalog/clinic_treatment_catalog/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_treatment_catalog.listing', {
#             'root': '/clinic_treatment_catalog/clinic_treatment_catalog',
#             'objects': http.request.env['clinic_treatment_catalog.clinic_treatment_catalog'].search([]),
#         })

#     @http.route('/clinic_treatment_catalog/clinic_treatment_catalog/objects/<model("clinic_treatment_catalog.clinic_treatment_catalog"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_treatment_catalog.object', {
#             'object': obj
#         })

