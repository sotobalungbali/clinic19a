
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicRoomSession(models.Model):
    """
    Ruang Sesi Klinis (ClinicOne)
    Merekam satu interval penggunaan ruangan, berikut konteks pasien/dokter/booking/antrean & perangkat yang dipakai.

    Integrasi lintas modul (optional-safe):
    - clinic_room_device:
        • clinic.room (room_id)  → sumber kebijakan booking_policy
        • clinic.room.device.assignment → perangkat aktif/terpakai
    - clinic_booking (opsional):
        • booking.booking (booking_id)
    - clinic_patient (opsional):
        • res.partner (patient_id)  [tanpa memaksa field is_patient, aman default]
    - clinic_doctor / hr (opsional):
        • hr.employee (doctor_id/employee_id)
    - clinic_queue_room (opsional):
        • clinic.room.assignment (queue link) / token (queue_token)
    """

    _name = "clinic.room.session"
    _description = "Clinic Room Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc, id desc"

    # ---------------------------
    # Identity & Company
    # ---------------------------
    name = fields.Char(string="Session Ref", tracking=True, readonly=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, default=lambda s: s.env.company, index=True
    )

    # ---------------------------
    # Core Links
    # ---------------------------
    room_id = fields.Many2one(
        "clinic.room", string="Room", required=True, index=True, tracking=True,
        domain=[("active", "=", True)]
    )
    # booking_id = fields.Many2one(
    #     "booking.booking", string="Booking", index=True,
    #     help="Relasi ke booking jika sesi ini berasal dari jadwal booking.",
    # )
    patient_id = fields.Many2one(
        "res.partner", string="Patient", index=True,
        domain=[("is_company", "=", False)],
        help="Pasien yang dilayani pada sesi ini (opsional)."
    )
    doctor_id = fields.Many2one(
        "hr.employee", string="Doctor/Practitioner", index=True,
        help="Tenaga medis utama pada sesi ini (opsional)."
    )
    employee_ids = fields.Many2many(
        "hr.employee", "clinic_room_session_hr_rel", "session_id", "employee_id",
        string="Supporting Staff", help="Staf pendukung pada sesi."
    )

    # Antrean (opsional)
    # queue_assignment_id = fields.Many2one(
    #     "clinic.room.assignment", string="Queue Link",
    #     help="Link Room↔Queue yang melahirkan sesi ini (jika berasal dari antrean)."
    # )
    queue_token = fields.Char(string="Queue Token", help="Nomor token antrean (opsional).")

    # ---------------------------
    # Timebox
    # ---------------------------
    start_datetime = fields.Datetime(string="Start", required=True, tracking=True)
    end_datetime = fields.Datetime(string="End", tracking=True)
    duration_minutes = fields.Integer(
        string="Duration (min)",
        compute="_compute_duration", store=True, readonly=True
    )

    # ---------------------------
    # Policy Snapshot & State
    # ---------------------------
    booking_policy = fields.Selection(
        selection=[
            ("exclusive", "Exclusive"),
            ("shared", "Shared"),
            ("queue_based", "Queue Based"),
        ],
        string="Room Policy (at Start)",
        compute="_compute_policy_from_room",
        store=True,
        help="Snapshot kebijakan dari Room pada saat sesi dimulai."
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("no_show", "No Show"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )

    # ---------------------------
    # Devices used
    # ---------------------------
    # Perangkat yang "terpakai" dalam sesi ini (free-tag). Jika ingin otomatis,
    # ada helper action yang menarik dari assignment aktif di room pada jam mulai.
    device_ids = fields.Many2many(
        "clinic.device",
        "clinic_room_session_device_rel",
        "session_id", "device_id",
        string="Devices Used"
    )
    device_count = fields.Integer(string="Devices", compute="_compute_device_count", store=False)

    notes = fields.Html(string="Notes")

    # Constraints unik ringan
        # Odoo 19 table constraints
    _start_before_end = models.Constraint(
        'CHECK (end_datetime IS NULL OR start_datetime <= end_datetime)',
        'End time must be after Start time.',
    )

    # ---------------------------
    # Compute
    # ---------------------------
    @api.depends("start_datetime", "end_datetime")
    def _compute_duration(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime:
                delta = fields.Datetime.to_datetime(rec.end_datetime) - fields.Datetime.to_datetime(rec.start_datetime)
                rec.duration_minutes = max(int(delta.total_seconds() // 60), 0)
            else:
                rec.duration_minutes = 0

    @api.depends("room_id", "room_id.booking_policy")
    def _compute_policy_from_room(self):
        for rec in self:
            rec.booking_policy = rec.room_id.booking_policy if rec.room_id else "exclusive"

    @api.depends("device_ids")
    def _compute_device_count(self):
        for rec in self:
            rec.device_count = len(rec.device_ids)

    # ---------------------------
    # ORM
    # ---------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if not rec.name:
                seq = self.env.ref("clinic_room_device.seq_room_session", raise_if_not_found=False)
                rec.name = (seq._next() if seq else _("Session-%s") % rec.id)
        # Validasi overlap setelah create
        recs._check_overlap_policy()
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._check_overlap_policy()
        return res

    # ---------------------------
    # Policy / Overlap Guard
    # ---------------------------
    def _check_overlap_policy(self):
        """
        Untuk room dengan policy 'exclusive', cegah overlap jadwal sesi.
        Untuk 'shared' → izinkan overlap.
        Untuk 'queue_based' → izinkan overlap (diatur kanal antrean).
        """
        for rec in self:
            if not rec.room_id or not rec.start_datetime:
                continue
            if rec.booking_policy != "exclusive":
                continue
            # Cari sesi lain di room yang overlap
            domain = [
                ("id", "!=", rec.id),
                ("room_id", "=", rec.room_id.id),
                ("state", "in", ["scheduled", "in_progress"]),  # hanya status aktif
                ("start_datetime", "<", rec.end_datetime or fields.Datetime.add(rec.start_datetime, hours=4)),
                ("end_datetime", ">", rec.start_datetime)  # tumpang tindih
            ]
            clash = self.search_count(domain)
            if clash:
                raise ValidationError(_(
                    "Overlap session is not allowed for room '%(room)s' with Exclusive policy."
                ) % {"room": rec.room_id.display_name or rec.room_id.name})

    # ---------------------------
    # Onchange heuristics
    # ---------------------------
    @api.onchange("booking_id")
    def _onchange_booking_id(self):
        """Tarik info default dari booking (opsional, aman jika model/field tersedia)."""
        if not self.booking_id:
            return
        # Map umum, hanya jika kosong
        if hasattr(self.booking_id, "room_id") and self.booking_id.room_id and not self.room_id:
            self.room_id = self.booking_id.room_id.id
        if hasattr(self.booking_id, "patient_id") and self.booking_id.patient_id and not self.patient_id:
            self.patient_id = self.booking_id.patient_id.id
        if hasattr(self.booking_id, "doctor_id") and self.booking_id.doctor_id and not self.doctor_id:
            self.doctor_id = self.booking_id.doctor_id.id
        if hasattr(self.booking_id, "start_datetime") and self.booking_id.start_datetime and not self.start_datetime:
            self.start_datetime = self.booking_id.start_datetime
        if hasattr(self.booking_id, "end_datetime") and self.booking_id.end_datetime and not self.end_datetime:
            self.end_datetime = self.booking_id.end_datetime

    @api.onchange("room_id", "start_datetime")
    def _onchange_room_devices_default(self):
        """
        Jika device_ids kosong, sarankan perangkat dari assignment aktif pada jam start.
        """
        if self.device_ids or not (self.room_id and self.start_datetime):
            return
        if "clinic.room.device.assignment" in self.env:
            asg = self.env["clinic.room.device.assignment"].sudo().search([
                ("room_id", "=", self.room_id.id),
                ("state", "=", "active"),
                ("start", "<=", self.start_datetime),
                "|", ("end", "=", False), ("end", ">=", self.start_datetime),
            ])
            devices = asg.mapped("device_id")
            if devices:
                self.device_ids = [(6, 0, devices.ids)]

    # ---------------------------
    # State machine
    # ---------------------------
    def action_schedule(self):
        for rec in self:
            if rec.state != "draft":
                continue
            rec.state = "scheduled"

    def action_start(self):
        for rec in self:
            if rec.state not in ("draft", "scheduled"):
                continue
            if not rec.start_datetime:
                rec.start_datetime = fields.Datetime.now()
            rec.state = "in_progress"

    def action_finish(self):
        for rec in self:
            if rec.state != "in_progress":
                continue
            if not rec.end_datetime:
                rec.end_datetime = fields.Datetime.now()
            rec.state = "done"

    def action_cancel(self):
        for rec in self:
            if rec.state in ("done", "cancelled"):
                continue
            rec.state = "cancelled"

    def action_no_show(self):
        for rec in self:
            if rec.state not in ("scheduled",):
                continue
            rec.state = "no_show"

    # ---------------------------
    # Smart actions
    # ---------------------------
    def action_open_room(self):
        self.ensure_one()
        return {
            "name": _("Room"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room",
            "view_mode": "form",
            "res_id": self.room_id.id,
        }

    def action_open_devices(self):
        self.ensure_one()
        return {
            "name": _("Devices"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device",
            "view_mode": "list,form",
            "domain": [("id", "in", self.device_ids.ids or [])],
        }

    # def action_open_booking(self):
    #     self.ensure_one()
    #     if not self.booking_id:
    #         raise UserError(_("This session is not linked to a booking."))
    #     return {
    #         "name": _("Booking"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "booking.booking",
    #         "view_mode": "form",
    #         "res_id": self.booking_id.id,
    #     }
