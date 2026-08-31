
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicRoom(models.Model):
    """
    Master Ruangan Klinik (ClinicOne)

    Integrasi lintas modul:
    - clinic_room_device:
        • room_type_id (Clinic Room Type)
        • availability_ids (jadwal/slot ketersediaan ruangan)
        • assignment_ids (penempatan device -> room)
        • movement perangkat akan merujuk room ini secara historis
    - clinic_queue_room (atau modul antrean sejenis):
        • TIDAK lagi Many2one ke clinic.queue.room
        • Link antrean via pivot 'clinic.room.assignment' (room_id <-> queue_id/clinic.queue)
    - stock/inventory:
        • location_id (opsional; ditautkan dari inherit stock.location)
    - hr:
        • supervisor_id (penanggung jawab)
        • technician_ids (daftar teknisi)
    - maintenance/booking:
        • lokasi untuk permintaan maintenance / booking planning

    Catatan:
    - Desain multi-company.
    - mail.thread untuk audit perubahan.
    """

    _name = "clinic.room"
    _description = "Clinic Room"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"
    _rec_name = "display_name"

    # ---------------------------------------------------------
    # Identity
    # ---------------------------------------------------------
    name = fields.Char(
        string="Room Name",
        required=True,
        index=True,
        tracking=True,
        help="Nama ruangan; contoh: Poli 1, Treatment A, OR-02."
    )
    code = fields.Char(
        string="Room Code",
        index=True,
        tracking=True,
        help="Kode unik ruangan; contoh: R-POLI-01, TR-A, OR-02."
    )
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda s: s.env.company,
        index=True,
    )
    color = fields.Integer(string="Color Index")

    # ---------------------------------------------------------
    # Classification & Policy
    # ---------------------------------------------------------
    room_type_id = fields.Many2one(
        "clinic.room.type",
        string="Room Type",
        required=False,
        index=True,
        tracking=True,
        help="Klasifikasi ruangan (Poli, Treatment, Bed, OR, Lab, dll.)."
    )
    usage_kind = fields.Selection(
        related="room_type_id.usage_kind",
        string="Usage Kind",
        store=True,
        readonly=True,
    )
    booking_policy = fields.Selection(
        selection=[
            ("exclusive", "Exclusive (1 session at a time)"),
            ("shared", "Shared (parallel up to capacity)"),
            ("queue_based", "Queue Based"),
        ],
        string="Booking Policy",
        compute="_compute_booking_policy",
        store=True,
        help="Turunan dari Room Type; bisa dipakai modul booking/queue untuk saran penjadwalan."
    )
    require_queue = fields.Boolean(
        string="Require Queue Channel",
        compute="_compute_booking_policy",
        store=True,
        help="True jika booking_policy=queue_based dari tipe."
    )

    capacity = fields.Integer(
        string="Capacity (people/sessions)",
        default=1,
        tracking=True,
        help="Kapasitas/slot paralel ideal ruangan ini (untuk shared policy)."
    )
    is_bookable = fields.Boolean(
        string="Bookable",
        default=True,
        help="Centang jika ruangan ini dapat di-booking."
    )

    status = fields.Selection(
        selection=[
            ("available", "Available"),
            ("occupied", "Occupied"),
            ("maintenance", "Maintenance"),
            ("closed", "Closed"),
        ],
        string="Operational Status",
        default="available",
        tracking=True,
    )

    # ---------------------------------------------------------
    # People
    # ---------------------------------------------------------
    supervisor_id = fields.Many2one(
        "hr.employee",
        string="Supervisor",
        help="Penanggung jawab ruangan."
    )
    technician_ids = fields.Many2many(
        "hr.employee",
        "clinic_room_hr_employee_rel",
        "room_id", "employee_id",
        string="Technicians",
        help="Teknisi yang biasa bertugas di ruangan ini."
    )

    # ---------------------------------------------------------
    # Physical / Inventory Mapping
    # ---------------------------------------------------------
    location_id = fields.Many2one(
        "stock.location",
        string="Stock Location",
        domain=[("usage", "in", ["internal", "transit"])],
        help="Lokasi gudang yang mewakili ruangan ini (opsional)."
    )

    # ---------------------------------------------------------
    # Availability / Assignments / Devices
    # ---------------------------------------------------------
    availability_ids = fields.One2many(
        "clinic.room.availability",
        "room_id",
        string="Availabilities"
    )
    next_available_from = fields.Datetime(
        string="Next Available From",
        compute="_compute_next_available_from",
        store=False,
        help="Slot tersedia berikutnya (hint) dari model availability."
    )

    assignment_ids = fields.One2many(
        "clinic.room.device.assignment",
        "room_id",
        string="Device Assignments"
    )
    device_count = fields.Integer(
        string="Active Devices",
        compute="_compute_device_count",
        store=False,
        help="Jumlah perangkat aktif (berdasarkan assignment aktif)."
    )

    # ---------------------------------------------------------
    # Queue Integration (via Pivot clinic.room.assignment)
    #   - Menggantikan M2O ke clinic.queue.room
    # ---------------------------------------------------------
    # queue_assignment_ids = fields.One2many(
    #     "clinic.room.assignment",
    #     "room_id",
    #     string="Queue Links",
    #     help="Relasi pivot Room ↔ Queue. Setiap baris menghubungkan room ini dengan satu channel antrean."
    # )
    # queue_channel_count = fields.Integer(
    #     string="Queue Channels",
    #     compute="_compute_queue_counters",
    #     store=False,
    # )

    # ---------------------------------------------------------
    # Notes / Image
    # ---------------------------------------------------------
    image_1920 = fields.Image(max_width=1920, max_height=1920)
    image_512 = fields.Image(related="image_1920", max_width=512, max_height=512, store=True)
    notes = fields.Html(string="Notes")

    # ---------------------------------------------------------
    # Constraints
    # ---------------------------------------------------------
        # Odoo 19 table constraints
    _code_company_uniq = models.Constraint(
        'unique(company_id, code)',
        'Room Code harus unik per perusahaan.',
    )
    _capacity_nonneg = models.Constraint(
        'CHECK (capacity >= 0)',
        'Capacity tidak boleh negatif.',
    )

    # ---------------------------------------------------------
    # Computes
    # ---------------------------------------------------------
    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            if rec.code:
                rec.display_name = "[%s] %s" % (rec.code, rec.name or "")
            else:
                rec.display_name = rec.name or ""

    @api.depends("room_type_id.booking_policy", "room_type_id.require_queue")
    def _compute_booking_policy(self):
        for rec in self:
            rec.booking_policy = rec.room_type_id.booking_policy if rec.room_type_id else "exclusive"
            rec.require_queue = rec.room_type_id.require_queue if rec.room_type_id else False

    @api.depends("availability_ids.start", "availability_ids.stop", "availability_ids.state")
    def _compute_next_available_from(self):
        for rec in self:
            rec.next_available_from = False
            if "clinic.room.availability" not in rec.env:
                continue
            # cari slot aktiv berikutnya
            slot = rec.env["clinic.room.availability"].sudo().search([
                ("room_id", "=", rec.id),
                ("state", "=", "active"),
                ("start", ">=", fields.Datetime.now()),
            ], order="start asc", limit=1)
            rec.next_available_from = slot.start if slot else False

    @api.depends("assignment_ids.state", "assignment_ids.end")
    def _compute_device_count(self):
        for rec in self:
            rec.device_count = len(rec.assignment_ids.filtered(lambda a: a.state == "active" and not a.end).mapped("device_id"))

    # @api.depends("queue_assignment_ids", "queue_assignment_ids.queue_id")
    # def _compute_queue_counters(self):
    #     for rec in self:
    #         if "clinic.room.assignment" not in self.env:
    #             rec.queue_channel_count = 0
    #             continue
    #         q_ids = rec.queue_assignment_ids.mapped("queue_id").ids if rec.queue_assignment_ids else []
    #         rec.queue_channel_count = len(set(q_ids))

    # ---------------------------------------------------------
    # ORM Overrides
    # ---------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Normalisasi code
            if vals.get("code"):
                vals["code"] = (vals["code"] or "").strip().upper()

            # Default dari Room Type (jika ada)
            if vals.get("room_type_id"):
                rt = self.env["clinic.room.type"].browse(vals["room_type_id"])
                if rt:
                    vals.setdefault("capacity", max(rt.default_capacity or 0, 0))
                    vals.setdefault("is_bookable", bool(rt.default_is_bookable))
        return super().create(vals_list)

    def write(self, vals):
        if "code" in vals and vals["code"]:
            vals["code"] = (vals["code"] or "").strip().upper()

        # Guard kapasitas
        if "capacity" in vals and vals["capacity"] is not None and vals["capacity"] < 0:
            raise ValidationError(_("Capacity tidak boleh negatif."))

        return super().write(vals)

    # ---------------------------------------------------------
    # Onchange & Helpers
    # ---------------------------------------------------------
    @api.onchange("room_type_id")
    def _onchange_room_type_id(self):
        """
        Tarik default dari tipe ruangan saat user mengganti room_type_id.
        Tidak menimpa nilai jika sudah terisi.
        """
        rt = self.room_type_id
        if not rt:
            return
        if not self.capacity:
            self.capacity = max(rt.default_capacity or 0, 0)
        if self.is_bookable is None:
            self.is_bookable = bool(rt.default_is_bookable)

    # ---------------------------------------------------------
    # Name helpers
    # ---------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            name = rec.display_name or rec.name or ""
            res.append((rec.id, name))
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = domain or []
        search_domain = []
        if name:
            search_domain = ["|", ("code", operator, name), ("name", operator, name)]
        recs = self.search(search_domain + domain, limit=limit)
        return recs.name_get()

    # ---------------------------------------------------------
    # Actions / Smart Buttons
    # ---------------------------------------------------------
    def action_view_availability(self):
        self.ensure_one()
        if "clinic.room.availability" not in self.env:
            raise UserError(_("Model availability ruangan belum tersedia."))
        return {
            "name": _("Room Availability"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room.availability",
            "view_mode": "calendar,tree,form",
            "domain": [("room_id", "=", self.id)],
            "context": {"default_room_id": self.id},
        }

    def action_view_assignments(self):
        self.ensure_one()
        if "clinic.room.device.assignment" not in self.env:
            raise UserError(_("Model assignment perangkat belum tersedia."))
        return {
            "name": _("Device Assignments"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room.device.assignment",
            "view_mode": "list,form",
            "domain": [("room_id", "=", self.id)],
            "context": {"default_room_id": self.id},
        }

    def action_view_devices(self):
        self.ensure_one()
        if "clinic.device" not in self.env:
            raise UserError(_("Model device belum tersedia."))
        # ambil device dari assignment aktif
        device_ids = self.assignment_ids.filtered(lambda a: a.state == "active" and not a.end).mapped("device_id").ids
        return {
            "name": _("Devices in Room"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device",
            "view_mode": "list,form",
            "domain": [("id", "in", device_ids or [])],
        }

    # def action_view_queues(self):
    #     """
    #     Tampilkan channel antrean (model: clinic.queue) yang terhubung ke room ini
    #     melalui pivot clinic.room.assignment. Jika model antrean/pivot tidak ada, berikan pesan ramah.
    #     """
    #     self.ensure_one()

    #     if "clinic.room.assignment" not in self.env:
    #         raise UserError(_("Integrasi antrean belum aktif (model clinic.room.assignment tidak ditemukan)."))

    #     queue_ids = self.queue_assignment_ids.mapped("queue_id").ids
    #     if not queue_ids:
    #         # Belum ada link → buka pivot supaya user dapat menambah link
    #         return {
    #             "name": _("Queue Links"),
    #             "type": "ir.actions.act_window",
    #             "res_model": "clinic.room.assignment",
    #             "view_mode": "list,form",
    #             "domain": [("room_id", "=", self.id)],
    #             "context": {"default_room_id": self.id},
    #         }

    #     if "clinic.queue" in self.env:
    #         return {
    #             "name": _("Queue Channels"),
    #             "type": "ir.actions.act_window",
    #             "res_model": "clinic.queue",
    #             "view_mode": "list,form",
    #             "domain": [("id", "in", queue_ids)],
    #         }
    #     else:
    #         # fallback buka pivot
    #         return {
    #             "name": _("Queue Links"),
    #             "type": "ir.actions.act_window",
    #             "res_model": "clinic.room.assignment",
    #             "view_mode": "list,form",
    #             "domain": [("room_id", "=", self.id)],
    #             "context": {"default_room_id": self.id},
    #         }

    # ---------------------------------------------------------
    # Public API (untuk modul lain)
    # ---------------------------------------------------------
    def get_room_snapshot(self):
        """
        Ringkasan profil ruangan untuk konsumsi modul lain (JSON-like dict).
        """
        self.ensure_one()
        return {
            "room_id": self.id,
            "name": self.display_name or self.name,
            "company_id": self.company_id.id if self.company_id else False,
            "room_type_id": self.room_type_id.id if self.room_type_id else False,
            "usage_kind": self.usage_kind,
            "booking_policy": self.booking_policy,
            "require_queue": bool(self.require_queue),
            "capacity": max(self.capacity or 0, 0),
            "is_bookable": bool(self.is_bookable),
            "status": self.status,
            "supervisor_id": self.supervisor_id.id if self.supervisor_id else False,
            "technician_ids": self.technician_ids.ids,
            "location_id": self.location_id.id if self.location_id else False,
            "device_count": self.device_count,
            "next_available_from": fields.Datetime.to_string(self.next_available_from) if self.next_available_from else False,
            "queue_channel_count": self.queue_channel_count,
        }
