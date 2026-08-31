
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HREmployee(models.Model):
    _inherit = "hr.employee"

    # =========================================================
    # Roles (peran dalam ekosistem ClinicOne)
    # =========================================================
    is_room_supervisor = fields.Boolean(
        string="Room Supervisor",
        help="Centang bila karyawan ini menjadi penanggung jawab (supervisor) ruangan klinik."
    )
    is_device_technician = fields.Boolean(
        string="Device Technician",
        help="Centang bila karyawan ini menjadi teknisi/perawat perangkat klinik."
    )

    # =========================================================
    # Kapabilitas Teknis & Cakupan Kerja
    # =========================================================
    device_category_ids = fields.Many2many(
        comodel_name="clinic.device.category" if "clinic.device.category" else "ir.model",
        relation="hr_employee_device_category_rel",
        column1="employee_id", column2="device_category_id",
        string="Expertise: Device Categories",
        help="Kategori perangkat yang dikuasai teknisi ini."
    )
    room_type_ids = fields.Many2many(
        comodel_name="clinic.room.type" if "clinic.room.type" else "ir.model",
        relation="hr_employee_room_type_rel",
        column1="employee_id", column2="room_type_id",
        string="Expertise: Room Types",
        help="Jenis ruangan yang biasa ditangani/diampu."
    )
    # Integrasi maintenance team (opsional, aman bila modul tidak ada)
    maintenance_team_ids = fields.Many2many(
        comodel_name="maintenance.team" if "maintenance.team" else "ir.model",
        relation="hr_employee_maintenance_team_rel",
        column1="employee_id", column2="team_id",
        string="Maintenance Teams",
        help="Tim maintenance tempat karyawan ini bergabung."
    )

    # =========================================================
    # Relasi Operasional Langsung
    # =========================================================
    # - Ruang yang disupervisi → 1:N (lihat clinic.room.supervisor_id)
    supervised_room_ids = fields.One2many(
        comodel_name="clinic.room" if "clinic.room" else "ir.model",
        inverse_name="supervisor_id",
        string="Supervised Rooms",
        help="Daftar ruangan di mana karyawan ini bertindak sebagai supervisor."
    )
    supervised_room_count = fields.Integer(
        string="Supervised Rooms",
        compute="_compute_counts",
        store=False
    )

    # - Keterlibatan sebagai teknisi ruangan (M2M pada clinic.room.technician_ids)
    technician_room_ids = fields.Many2many(
        comodel_name="clinic.room" if "clinic.room" else "ir.model",
        relation="clinic_room_hr_employee_rel",  # sama seperti di model room.py
        column1="employee_id", column2="room_id",
        string="Technician of Rooms",
        help="Daftar ruangan di mana karyawan ini tercatat sebagai teknisi."
    )
    technician_room_count = fields.Integer(
        string="Rooms as Technician",
        compute="_compute_counts",
        store=False
    )

    # - Assignment perangkat yang menunjuk employee sebagai penanggung jawab
    assignment_ids = fields.One2many(
        comodel_name="clinic.room.device.assignment" if "clinic.room.device.assignment" else "ir.model",
        inverse_name="responsible_id" if "clinic.room.device.assignment" else "id",
        string="Device Assignments (Responsible)",
        help="Riwayat assignment perangkat yang ditandai dengan karyawan ini sebagai penanggung jawab."
    )
    assignment_active_count = fields.Integer(
        string="Active Assignments",
        compute="_compute_counts",
        store=False
    )

    # - Movement log yang dipicu atau ditangani oleh employee (opsional, jika Anda menambah field responsible_id)
    movement_ids = fields.One2many(
        comodel_name="clinic.device.movement" if "clinic.device.movement" else "ir.model",
        inverse_name="create_uid",  # fallback: pembuat record movement
        string="Device Movements (created by)",
        help="Log perpindahan perangkat yang dibuat oleh user karyawan ini."
    )
    movement_count = fields.Integer(
        string="Movements (created)",
        compute="_compute_counts",
        store=False
    )

    # - Maintenance request yang ditugaskan/ditandai ke employee ini (opsional, tergantung field di maintenance)
    maintenance_request_ids = fields.One2many(
        comodel_name="maintenance.request" if "maintenance.request" else "ir.model",
        inverse_name="employee_id" if "maintenance.request" in locals() else "id",
        string="Maintenance Requests (Assigned)",
        help="Tiket maintenance yang ditugaskan pada karyawan ini (jika field employee_id tersedia)."
    )
    maintenance_open_count = fields.Integer(
        string="Open Maintenance",
        compute="_compute_counts",
        store=False
    )

    # - Booking/Queue yang berelasi dengan employee (opsional)
    # booking_ids = fields.One2many(
    #     comodel_name="booking.booking" if "booking.booking" else "ir.model",
    #     inverse_name="employee_id" if "booking.booking" in locals() else "id",
    #     string="Bookings (as Staff/Doctor)",
    #     help="Booking yang menunjuk karyawan ini (jika field employee_id tersedia di modul booking)."
    # )
    booking_upcoming_count = fields.Integer(
        string="Upcoming Bookings (7d)",
        compute="_compute_counts",
        store=False
    )

    # =========================================================
    # Shift / Coverage (opsional, ringan)
    # =========================================================
    shift_days = fields.Selection(
        selection=[
            ("business", "Business Days (Mon–Fri)"),
            ("extended", "Extended (Mon–Sat)"),
            ("fullweek", "Full Week (Mon–Sun)"),
        ],
        string="Shift Days",
        default="business",
        help="Hari kerja standar karyawan ini dalam konteks operasional klinik."
    )
    shift_start = fields.Float(string="Shift Start (hour)", default=9.0, help="Contoh 9.0 = 09:00")
    shift_end = fields.Float(string="Shift End (hour)", default=17.0, help="Contoh 17.0 = 17:00")
    on_shift_now = fields.Boolean(
        string="On Shift Now",
        compute="_compute_on_shift_now",
        store=False
    )

    # =========================================================
    # Compute
    # =========================================================
    # def _get_booking_model(self):
    #     return "booking.booking" if "booking.booking" in self.env else False

    def _get_maintenance_model(self):
        return "maintenance.request" if "maintenance.request" in self.env else False

    @api.depends(
        "supervised_room_ids",
        "technician_room_ids",
        "assignment_ids.state", "assignment_ids.end",
        "movement_ids",
        "maintenance_request_ids.stage_id", "maintenance_request_ids.request_date",
        "booking_ids.start_datetime", "booking_ids.state",
    )
    # def _compute_counts(self):
    #     today = fields.Date.context_today(self)
    #     BookingModel = self._get_booking_model()
    #     for rec in self:
    #         # Rooms
    #         rec.supervised_room_count = len(rec.supervised_room_ids)
    #         rec.technician_room_count = len(rec.technician_room_ids)

    #         # Active Assignments (state=active & end False)
    #         rec.assignment_active_count = len(rec.assignment_ids.filtered(lambda a: a.state == "active" and not a.end))

    #         # Movements created (by create_uid == employee's user) → perkiraan
    #         if rec.user_id:
    #             rec.movement_count = self.env["clinic.device.movement"].sudo().search_count([
    #                 ("create_uid", "=", rec.user_id.id)
    #             ]) if "clinic.device.movement" in self.env else 0
    #         else:
    #             rec.movement_count = 0

    #         # Maintenance open (heuristik: stage.fold = False dianggap open)
    #         if self._get_maintenance_model() and "partner_id" in self.env["maintenance.request"]._fields:
    #             open_count = 0
    #             for r in rec.maintenance_request_ids:
    #                 fold = False
    #                 if "stage_id" in r._fields and r.stage_id:
    #                     fold = bool(getattr(r.stage_id, "fold", False))
    #                 if not fold:
    #                     open_count += 1
    #             rec.maintenance_open_count = open_count
    #         else:
    #             rec.maintenance_open_count = 0

    #         # Upcoming bookings in 7 days (opsional & aman jika modul tersedia)
    #         rec.booking_upcoming_count = 0
    #         if BookingModel and "employee_id" in self.env[BookingModel]._fields and "start_datetime" in self.env[BookingModel]._fields:
    #             # ambil booking karyawan ini dalam status aktif & mulai >= hari ini, <= +7 hari
    #             start_from = fields.Datetime.now()
    #             start_to = fields.Datetime.add(start_from, days=7)
    #             rec.booking_upcoming_count = self.env[BookingModel].sudo().search_count([
    #                 ("employee_id", "=", rec.id),
    #                 ("state", "not in", ["cancelled", "canceled", "cancel"]),
    #                 ("start_datetime", ">=", start_from),
    #                 ("start_datetime", "<=", start_to),
    #             ])

    @api.depends("shift_days", "shift_start", "shift_end")
    def _compute_on_shift_now(self):
        for rec in self:
            rec.on_shift_now = rec._is_in_shift_window(fields.Datetime.now())

    # =========================================================
    # Helper: Shift Window Checker
    # =========================================================
    def _is_in_shift_window(self, dt):
        """
        Periksa apakah datetime 'dt' berada dalam jendela jam & hari kerja employee.
        Return bool. Tidak mengikat jadwal HR Attendance; hanya hint operasional.
        """
        self.ensure_one()
        if not dt:
            dt = fields.Datetime.now()

        # Hari (0=Mon .. 6=Sun)
        loc_dt = fields.Datetime.context_timestamp(self, dt)
        weekday = loc_dt.weekday()
        if self.shift_days == "business" and weekday > 4:
            return False
        if self.shift_days == "extended" and weekday > 5:
            return False

        # Jam → float hour
        hour_str = loc_dt.strftime("%H.%M")
        try:
            hour_float = float(hour_str.replace(".", ".", 1))
        except Exception:
            hour_float = float(loc_dt.strftime("%H"))  # fallback

        start = self.shift_start or 0.0
        end = self.shift_end or 24.0
        return start <= hour_float <= end

    # =========================================================
    # Smart Actions (UI)
    # =========================================================
    def action_view_supervised_rooms(self):
        """Buka ruangan yang disupervisi karyawan ini."""
        self.ensure_one()
        if "clinic.room" not in self.env:
            raise UserError(_("Model clinic.room belum tersedia."))
        return {
            "name": _("Supervised Rooms"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("supervisor_id", "=", self.id)],
            "context": {"default_supervisor_id": self.id},
        }

    def action_view_technician_rooms(self):
        """Buka ruangan di mana employee ini menjadi teknisi."""
        self.ensure_one()
        if "clinic.room" not in self.env:
            raise UserError(_("Model clinic.room belum tersedia."))
        return {
            "name": _("Rooms as Technician"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("technician_ids", "in", [self.id])],
        }

    def action_view_assignments(self):
        """Buka assignment perangkat yang employee ini sebagai penanggung jawab."""
        self.ensure_one()
        if "clinic.room.device.assignment" not in self.env:
            raise UserError(_("Model assignment perangkat belum tersedia."))
        return {
            "name": _("Device Assignments (Responsible)"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room.device.assignment",
            "view_mode": "list,form",
            "domain": [("responsible_id", "=", self.id)],
            "context": {"default_responsible_id": self.id},
        }

    def action_view_device_movements(self):
        """Buka movement log yang dibuat oleh user karyawan ini (indikatif)."""
        self.ensure_one()
        if "clinic.device.movement" not in self.env:
            raise UserError(_("Model movement perangkat belum tersedia."))
        if not self.user_id:
            raise UserError(_("Karyawan ini belum tertaut ke User, sehingga tidak ada jejak pembuat movement."))
        return {
            "name": _("Device Movements (created by me)"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device.movement",
            "view_mode": "list,form,graph,pivot",
            "domain": [("create_uid", "=", self.user_id.id)],
        }

    def action_view_maintenance_requests(self):
        """Buka maintenance request yang ditugaskan ke employee ini (jika field employee_id tersedia)."""
        self.ensure_one()
        MModel = self._get_maintenance_model()
        if not MModel or "employee_id" not in self.env[MModel]._fields:
            raise UserError(_("Integrasi Maintenance belum aktif (field employee_id tidak ditemukan)."))
        return {
            "name": _("Maintenance Requests (Assigned)"),
            "type": "ir.actions.act_window",
            "res_model": MModel,
            "view_mode": "list,form,kanban,graph,pivot",
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id},
        }

    # def action_view_upcoming_bookings(self):
    #     """Buka booking 7 hari ke depan di mana employee ini terlibat (jika modul booking tersedia)."""
    #     self.ensure_one()
    #     BModel = self._get_booking_model()
    #     if not BModel or "employee_id" not in self.env[BModel]._fields:
    #         raise UserError(_("Integrasi Booking belum aktif (field employee_id tidak ditemukan)."))
    #     start_from = fields.Datetime.now()
    #     start_to = fields.Datetime.add(start_from, days=7)
    #     return {
    #         "name": _("Upcoming Bookings (7 days)"),
    #         "type": "ir.actions.act_window",
    #         "res_model": BModel,
    #         "view_mode": "calendar,tree,form",
    #         "domain": [
    #             ("employee_id", "=", self.id),
    #             ("state", "not in", ["cancelled", "canceled", "cancel"]),
    #             ("start_datetime", ">=", start_from),
    #             ("start_datetime", "<=", start_to),
    #         ],
    #         "context": {"default_employee_id": self.id},
    #     }

    # =========================================================
    # Onchange Heuristics
    # =========================================================
    @api.onchange("is_room_supervisor")
    def _onchange_is_room_supervisor(self):
        """Heuristik ringan: beri sinyal di chatter bila diaktifkan (optional)."""
        if self.is_room_supervisor and "message_post" in dir(self):
            self.message_post(body=_("Role 'Room Supervisor' diaktifkan untuk karyawan ini."))

    @api.onchange("is_device_technician")
    def _onchange_is_device_technician(self):
        """Heuristik ringan: jika teknisi, dan belum ada keahlian, ajukan saran (tidak memodifikasi data)."""
        if self.is_device_technician and not self.device_category_ids:
            # Tidak mengubah data—cukup memberi catatan agar user mengisi keahlian.
            if "message_post" in dir(self):
                self.message_post(body=_("Tandai kategori perangkat yang dikuasai teknisi ini pada tab 'ClinicOne'."))

    # =========================================================
    # Public API (dipakai modul lain)
    # =========================================================
    def get_profile_payload(self):
        """
        Kembalikan profil operasional employee untuk konsumsi modul lain:
        - Peran & cakupan
        - Keahlian
        - KPI ringkas
        - Shift window
        """
        self.ensure_one()
        return {
            "employee_id": self.id,
            "name": self.name,
            "is_room_supervisor": self.is_room_supervisor,
            "is_device_technician": self.is_device_technician,
            "device_category_ids": self.device_category_ids.ids,
            "room_type_ids": self.room_type_ids.ids,
            "maintenance_team_ids": self.maintenance_team_ids.ids,
            "supervised_room_count": self.supervised_room_count,
            "technician_room_count": self.technician_room_count,
            "assignment_active_count": self.assignment_active_count,
            "movement_count": self.movement_count,
            "maintenance_open_count": self.maintenance_open_count,
            "booking_upcoming_count": self.booking_upcoming_count,
            "shift_days": self.shift_days,
            "shift_start": self.shift_start,
            "shift_end": self.shift_end,
            "on_shift_now": self._is_in_shift_window(fields.Datetime.now()),
        }
