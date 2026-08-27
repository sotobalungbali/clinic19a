
# from odoo import http


# class ClinicTriageVitals(http.Controller):
#     @http.route('/clinic_triage_vitals/clinic_triage_vitals', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_triage_vitals/clinic_triage_vitals/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_triage_vitals.listing', {
#             'root': '/clinic_triage_vitals/clinic_triage_vitals',
#             'objects': http.request.env['clinic_triage_vitals.clinic_triage_vitals'].search([]),
#         })

#     @http.route('/clinic_triage_vitals/clinic_triage_vitals/objects/<model("clinic_triage_vitals.clinic_triage_vitals"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_triage_vitals.object', {
#             'object': obj
#         })

