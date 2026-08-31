
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    # =========================================================
    # Linkage ke ekosistem ClinicOne
    # =========================================================
    device_id = fields.Many2one(
        "clinic.device",
        string="Device",
        index=True,
        help="Perangkat yang dilaporkan mengalami isu/maintenance."
    )
    room_id = fields.Many2one(
        "clinic.room",
        string="Room",
        index=True,
        help="Ruangan terkait isu/maintenance."
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Vendor/Partner",
        domain=[("is_company", "=", True)],
        help="Partner penyedia layanan (vendor, installer, maintenance provider)."
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Assigned Technician",
        help="Teknisi internal yang ditugaskan."
    )

    # =========================================================
    # SLA & Service Profile (terambil dari partner/team/konfigurasi)
    # =========================================================
    service_level = fields.Selection(  # mirror ringan dari res.partner
        selection=[("bronze", "Bronze"), ("silver", "Silver"), ("gold", "Gold"), ("platinum", "Platinum")],
        string="Service Level",
        help="Service level yang berlaku untuk request ini (turunan dari partner/team)."
    )
    sla_response_hours = fields.Float(string="SLA Response (hours)", help="Target respon sejak request dibuat.")
    sla_resolution_hours = fields.Float(string="SLA Resolution (hours)", help="Target selesai sejak request dibuat.")
    coverage_days = fields.Selection(
        selection=[("business", "Business Days (Mon–Fri)"), ("extended", "Extended (Mon–Sat)"), ("fullweek", "Full Week (Mon–Sun)")],
        string="Coverage Days",
        help="Hari layanan yang berlaku."
    )
    coverage_start = fields.Float(string="Coverage Start", help="Jam mulai layanan (24h).")
    coverage_end = fields.Float(string="Coverage End", help="Jam akhir layanan (24h).")

    # Due dates dihitung dari SLA
    response_due = fields.Datetime(string="Response Due", compute="_compute_sla_due", store=True)
    resolution_due = fields.Datetime(string="Resolution Due", compute="_compute_sla_due", store=True)
    response_overdue = fields.Boolean(string="Response Overdue", compute="_compute_overdue_flags", store=False)
    resolution_overdue = fields.Boolean(string="Resolution Overdue", compute="_compute_overdue_flags", store=False)

    # =========================================================
    # Impact / Urgency → Priority (ITIL-like ringan)
    # =========================================================
    impact = fields.Selection(
        selection=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
        string="Impact",
        default="medium",
        help="Dampak bisnis/operasional dari isu/permintaan ini."
    )
    urgency = fields.Selection(
        selection=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
        string="Urgency",
        default="medium",
        help="Kegentingan kebutuhan penanganan."
    )
    priority_score = fields.Integer(
        string="Priority Score",
        compute="_compute_priority_score",
        store=True,
        help="Skor prioritas berbasis impact & urgency."
    )
    # Odoo punya 'priority' Many2one stages; namun field integer ini membantu auto-sorting/pemetaan SLA.

    # =========================================================
    # Status & Counter terpadu
    # =========================================================
    booking_overlap_count = fields.Integer(
        string="Overlapped Bookings",
        compute="_compute_booking_overlap",
        store=False,
        help="Jumlah booking yang berpotensi terdampak di ruangan ini saat device bermasalah."
    )
    active_assignment_id = fields.Many2one(
        "clinic.room.device.assignment",
        string="Active Assignment",
        compute="_compute_active_assignment",
        store=False,
        help="Assignment perangkat yang aktif saat ini (jika ada)."
    )
    movement_count = fields.Integer(
        string="Movements",
        compute="_compute_counts",
        store=False
    )
    assignment_count = fields.Integer(
        string="Assignments",
        compute="_compute_counts",
        store=False
    )

    # =========================================================
    # Compliance & Dokumen
    # =========================================================
    requires_shutdown = fields.Boolean(string="Requires Shutdown", help="Centang jika perangkat perlu dimatikan sementara.")
    safety_notes = fields.Text(string="Safety Notes")
    certification_required = fields.Boolean(
        string="Certification Required",
        help="Centang jika perbaikan ini memerlukan sertifikasi/kalibrasi ulang."
    )

    # =========================================================
    # Constraints
    # =========================================================
        # Odoo 19 table constraints
    _device_or_room = models.Constraint(
        'CHECK (device_id IS NOT NULL OR room_id IS NOT NULL)',
        'Minimal pilih Device atau Room.',
    )

    # =========================================================
    # Default & Heuristik
    # =========================================================
    @api.onchange("device_id")
    def _onchange_device_id(self):
        """
        - Tarik room saat ini dari device (current_room_id).
        - Tarik vendor default & maintenance team dari device/category bila ada.
        - Suggest employee/team berdasarkan kategori/keahlian.
        """
        if not self.device_id:
            return
        # Room dari assignment aktif
        if self.device_id.current_room_id:
            self.room_id = self.device_id.current_room_id.id

        # Partner/vendor default dari device
        if self.device_id.vendor_id and not self.partner_id:
            self.partner_id = self.device_id.vendor_id.id

        # Maintenance team dari device/category → map ke field team_id (bawaan maintenance)
        if not self.team_id:
            if self.device_id.maintenance_team_id:
                self.team_id = self.device_id.maintenance_team_id.id
            elif self.device_id.category_id and self.device_id.category_id.maintenance_team_id:
                self.team_id = self.device_id.category_id.maintenance_team_id.id

        # Pull SLA preset dari partner jika ada
        if self.partner_id:
            self._apply_partner_service_profile(self.partner_id)

    @api.onchange("room_id")
    def _onchange_room_id(self):
        """
        - Jika room punya supervisor/technicians, jadikan kandidat employee_id (hanya saran).
        - Jika stock.location ditaut, tampilkan peringatan jika lokasi karantina/sanitation aktif.
        """
        if not self.room_id:
            return
        # Hint: jika supervisor ada dan employee kosong → set
        if self.room_id.supervisor_id and not self.employee_id:
            self.employee_id = self.room_id.supervisor_id.id

        # Note sanitasi/karantina
        if "location_id" in self.room_id._fields and self.room_id.location_id:
            loc = self.room_id.location_id
            danger = []
            if getattr(loc, "sanitation_required", False):
                danger.append(_("Sanitation required"))
            if getattr(loc, "quarantine_location", False):
                danger.append(_("Quarantine area"))
            if danger and "message_post" in dir(self):
                self.message_post(body=_("Room location flags: %s") % ", ".join(danger))

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Tarik profil layanan partner (SLA, coverage) ke request ini."""
        if self.partner_id:
            self._apply_partner_service_profile(self.partner_id)

    def _apply_partner_service_profile(self, partner):
        """
        Baca profil layanan dari res.partner (lihat res_partner_inherit.py:get_service_profile_payload)
        dan tempelkan ke request ini (tanpa override bila user sudah isi).
        """
        if not partner or "get_service_profile_payload" not in dir(partner):
            return
        payload = partner.get_service_profile_payload()
        # hanya set yang belum terisi / 0
        field_map = [
            ("service_level", "service_level"),
            ("sla_response_hours", "sla_response_hours"),
            ("sla_resolution_hours", "sla_resolution_hours"),
            ("coverage_days", "coverage_days"),
            ("coverage_start", "coverage_start"),
            ("coverage_end", "coverage_end"),
        ]
        for src, dst in field_map:
            cur = getattr(self, dst, None)
            val = payload.get(src)
            if (cur in (None, False, 0)) and val not in (None, False, 0):
                setattr(self, dst, val)

    # =========================================================
    # Computes
    # =========================================================
    @api.depends("request_date", "sla_response_hours", "sla_resolution_hours")
    def _compute_sla_due(self):
        for rec in self:
            req_dt = rec.request_date or fields.Datetime.now()
            rec.response_due = fields.Datetime.add(req_dt, hours=(rec.sla_response_hours or 0))
            rec.resolution_due = fields.Datetime.add(req_dt, hours=(rec.sla_resolution_hours or 0))

    def _impact_urgency_score(self, val):
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(val or "medium", 2)

    @api.depends("impact", "urgency")
    def _compute_priority_score(self):
        for rec in self:
            score = rec._impact_urgency_score(rec.impact) * rec._impact_urgency_score(rec.urgency)
            rec.priority_score = score

    def _get_booking_model(self):
        return "booking.booking" if "booking.booking" in self.env else False

    @api.depends("room_id", "request_date")
    def _compute_booking_overlap(self):
        BookingModel = self._get_booking_model()
        for rec in self:
            rec.booking_overlap_count = 0
            if not (BookingModel and rec.room_id):
                continue
            # Cek booking yang overlap ±1 hari dari request_date (heuristik ringan)
            start_w = fields.Datetime.add(rec.request_date or fields.Datetime.now(), days=-1)
            stop_w = fields.Datetime.add(rec.request_date or fields.Datetime.now(), days=+1)
            domain = [
                ("room_id", "=", rec.room_id.id),
                ("state", "not in", ["cancelled", "canceled", "cancel"]),
                ("start_datetime", "<=", stop_w),
                ("end_datetime", ">=", start_w),
            ]
            cnt = self.env[BookingModel].sudo().search_count(domain)
            rec.booking_overlap_count = cnt

    @api.depends("device_id", "room_id")
    def _compute_active_assignment(self):
        for rec in self:
            rec.active_assignment_id = False
            if not rec.device_id:
                continue
            Asg = self.env["clinic.room.device.assignment"] if "clinic.room.device.assignment" in self.env else False
            if not Asg:
                continue
            asg = Asg.sudo().search([
                ("device_id", "=", rec.device_id.id),
                ("state", "=", "active"),
                ("end", "=", False),
            ], order="start desc", limit=1)
            rec.active_assignment_id = asg.id if asg else False

    @api.depends("device_id")
    def _compute_counts(self):
        for rec in self:
            rec.movement_count = 0
            rec.assignment_count = 0
            if rec.device_id:
                if "clinic.device.movement" in self.env:
                    rec.movement_count = self.env["clinic.device.movement"].sudo().search_count([("device_id", "=", rec.device_id.id)])
                if "clinic.room.device.assignment" in self.env:
                    rec.assignment_count = self.env["clinic.room.device.assignment"].sudo().search_count([("device_id", "=", rec.device_id.id)])

    @api.depends("response_due", "resolution_due", "stage_id")
    def _compute_overdue_flags(self):
        now = fields.Datetime.now()
        for rec in self:
            # Heuristik: bila stage.fold=True → dianggap closed (tidak overdue)
            closed = False
            if rec.stage_id and hasattr(rec.stage_id, "fold"):
                closed = bool(rec.stage_id.fold)
            rec.response_overdue = (rec.response_due and rec.response_due < now and not closed) or False
            rec.resolution_overdue = (rec.resolution_due and rec.resolution_due < now and not closed) or False

    # =========================================================
    # ORM: Create/Write Hooks
    # =========================================================
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec, vals in zip(recs, vals_list):
            # Jika device terisi tapi room kosong, isi dari current_room device
            if rec.device_id and not rec.room_id and rec.device_id.current_room_id:
                rec.sudo().write({"room_id": rec.device_id.current_room_id.id})

            # Auto-activity ping supervisor room
            if rec.room_id and rec.room_id.supervisor_id and rec.room_id.supervisor_id.user_id:
                try:
                    rec.activity_schedule(
                        "mail.mail_activity_data_todo",
                        user_id=rec.room_id.supervisor_id.user_id.id,
                        summary=_("New Maintenance Request"),
                        note=_("Room: %(r)s — Device: %(d)s") % {
                            "r": rec.room_id.display_name or rec.room_id.name,
                            "d": rec.device_id.display_name if rec.device_id else "-",
                        },
                    )
                except Exception:
                    # jangan blokir create hanya karena activity gagal
                    pass

            # Jika butuh shutdown, ubah status device/room (soft signal)
            rec._apply_operational_signals_on_create(vals)
        return recs

    def write(self, vals):
        res = super().write(vals)

        for rec in self:
            # Perbarui room dari device jika user mengganti device
            if "device_id" in vals and rec.device_id and not vals.get("room_id"):
                if rec.device_id.current_room_id:
                    rec.sudo().write({"room_id": rec.device_id.current_room_id.id})

            # Jika stage berubah menjadi closed (fold=True) → clear overdue activity
            if "stage_id" in vals and rec.stage_id and hasattr(rec.stage_id, "fold") and rec.stage_id.fold:
                try:
                    rec.activity_unlink()  # bersihkan activity terkait request ini
                except Exception:
                    pass

            # Update sinyal operasional bila status berubah
            rec._apply_operational_signals_on_write(vals)

        return res

    # =========================================================
    # Operasional Signals (optional hooks)
    # =========================================================
    def _apply_operational_signals_on_create(self, vals):
        """
        - Jika requires_shutdown=True → set device status 'maintenance' (bila memungkinkan).
        - Catat movement 'maintenance' ke/ dari room jika relevan (optional).
        """
        for rec in self:
            if rec.requires_shutdown and rec.device_id:
                try:
                    if hasattr(rec.device_id, "set_maintenance"):
                        rec.device_id.set_maintenance()
                except Exception:
                    pass
            # movement log indikatif
            if rec.device_id and "clinic.device.movement" in self.env and rec.room_id:
                try:
                    self.env["clinic.device.movement"].sudo().create({
                        "device_id": rec.device_id.id,
                        "from_room_id": rec.device_id.current_room_id.id if rec.device_id.current_room_id else False,
                        "to_room_id": rec.room_id.id,
                        "reason": "maintenance",
                        "date": rec.request_date or fields.Datetime.now(),
                        "note": _("Movement auto-logged from maintenance request."),
                    })
                except Exception:
                    pass

    def _apply_operational_signals_on_write(self, vals):
        """
        - Jika stage closed → kembalikan status device bila aman.
        - Jika partner diisi & punya SLA sangat ketat → jadwalkan activity reminder sebelum due.
        """
        for rec in self:
            # Close signal → device available?
            if "stage_id" in vals and rec.stage_id and hasattr(rec.stage_id, "fold") and rec.stage_id.fold:
                try:
                    if rec.device_id and hasattr(rec.device_id, "set_available"):
                        rec.device_id.set_available()
                except Exception:
                    pass

            # SLA reminder activity (reschedule ringan)
            if any(k in vals for k in ("sla_response_hours", "sla_resolution_hours", "request_date")):
                # Jadwalkan reminder 30 menit sebelum due jika due < 72h
                for due_field in ("response_due", "resolution_due"):
                    due = getattr(rec, due_field)
                    if not due:
                        continue
                    delta_h = (due - fields.Datetime.now()).total_seconds() / 3600.0
                    if 0 < delta_h <= 72:
                        try:
                            rec.activity_schedule(
                                "mail.mail_activity_data_todo",
                                date_deadline=fields.Date.to_date(fields.Datetime.add(due, hours=-0.5)),
                                summary=_("SLA Reminder (%s)") % due_field.replace("_", " ").title(),
                                note=_("Approaching due: %s") % fields.Datetime.to_string(due),
                            )
                        except Exception:
                            pass

    # =========================================================
    # Actions / Smart Buttons
    # =========================================================
    def action_open_device(self):
        self.ensure_one()
        if not self.device_id:
            raise UserError(_("Request ini tidak terkait Device."))
        return {
            "name": _("Device"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device",
            "view_mode": "form",
            "res_id": self.device_id.id,
        }

    def action_open_room(self):
        self.ensure_one()
        if not self.room_id:
            raise UserError(_("Request ini tidak terkait Room."))
        return {
            "name": _("Room"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room",
            "view_mode": "form",
            "res_id": self.room_id.id,
        }

    def action_open_assignments(self):
        self.ensure_one()
        if "clinic.room.device.assignment" not in self.env:
            raise UserError(_("Model assignment perangkat belum tersedia."))
        return {
            "name": _("Device Assignments"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room.device.assignment",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.device_id.id)] if self.device_id else [("id", "in", [])],
        }

    def action_open_movements(self):
        self.ensure_one()
        if "clinic.device.movement" not in self.env:
            raise UserError(_("Model movement perangkat belum tersedia."))
        return {
            "name": _("Device Movements"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device.movement",
            "view_mode": "list,form,graph,pivot",
            "domain": [("device_id", "=", self.device_id.id)] if self.device_id else [("id", "in", [])],
        }

    def action_mark_requires_shutdown(self):
        """Toggle requires_shutdown dan set status device ke 'maintenance' bila perlu."""
        for rec in self:
            rec.requires_shutdown = not rec.requires_shutdown
            if rec.requires_shutdown and rec.device_id and hasattr(rec.device_id, "set_maintenance"):
                try:
                    rec.device_id.set_maintenance()
                except Exception:
                    pass

    def action_check_room_booking_impact(self):
        """Buka daftar booking yang berpotensi terdampak (±1 hari window)."""
        self.ensure_one()
        BookingModel = self._get_booking_model()
        if not (BookingModel and self.room_id):
            raise UserError(_("Integrasi Booking belum aktif atau Room kosong."))
        start_w = fields.Datetime.add(self.request_date or fields.Datetime.now(), days=-1)
        stop_w = fields.Datetime.add(self.request_date or fields.Datetime.now(), days=+1)
        domain = [
            ("room_id", "=", self.room_id.id),
            ("state", "not in", ["cancelled", "canceled", "cancel"]),
            ("start_datetime", "<=", stop_w),
            ("end_datetime", ">=", start_w),
        ]
        return {
            "name": _("Potentially Impacted Bookings"),
            "type": "ir.actions.act_window",
            "res_model": BookingModel,
            "view_mode": "calendar,tree,form",
            "domain": domain,
            "context": {"default_room_id": self.room_id.id},
        }

    # =========================================================
    # Public API (dipakai modul lain)
    # =========================================================
    def get_operational_snapshot(self):
        """
        Ringkasan status operasional untuk dashboard:
        - Device, Room, Assignment aktif
        - SLA & overdue flags
        - Booking impact
        """
        self.ensure_one()
        return {
            "request_id": self.id,
            "device_id": self.device_id.id if self.device_id else False,
            "room_id": self.room_id.id if self.room_id else False,
            "active_assignment_id": self.active_assignment_id.id if self.active_assignment_id else False,
            "sla": {
                "service_level": self.service_level,
                "response_due": fields.Datetime.to_string(self.response_due) if self.response_due else False,
                "resolution_due": fields.Datetime.to_string(self.resolution_due) if self.resolution_due else False,
                "response_overdue": bool(self.response_overdue),
                "resolution_overdue": bool(self.resolution_overdue),
            },
            "booking_overlap_count": self.booking_overlap_count,
            "priority_score": self.priority_score,
        }
