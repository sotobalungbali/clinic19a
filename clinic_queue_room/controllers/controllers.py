
# from odoo import http


# class ClinicQueueRoom(http.Controller):
#     @http.route('/clinic_queue_room/clinic_queue_room', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/clinic_queue_room/clinic_queue_room/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('clinic_queue_room.listing', {
#             'root': '/clinic_queue_room/clinic_queue_room',
#             'objects': http.request.env['clinic_queue_room.clinic_queue_room'].search([]),
#         })

#     @http.route('/clinic_queue_room/clinic_queue_room/objects/<model("clinic_queue_room.clinic_queue_room"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('clinic_queue_room.object', {
#             'object': obj
#         })
