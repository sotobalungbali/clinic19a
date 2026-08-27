
# from odoo import http


# class ClinicStaff(http.Controller):
#     @http.route('/clinic_staff/clinic_staff', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_staff/clinic_staff/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_staff.listing', {
#             'root': '/clinic_staff/clinic_staff',
#             'objects': http.request.env['clinic_staff.clinic_staff'].search([]),
#         })

#     @http.route('/clinic_staff/clinic_staff/objects/<model("clinic_staff.clinic_staff"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_staff.object', {
#             'object': obj
#         })

