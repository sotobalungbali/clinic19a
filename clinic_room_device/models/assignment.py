# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicRoomDeviceAssignment(models.Model):
    """
    Penempatan/Assignment Perangkat → Ruangan

    Tujuan:
    - Melacak histori device ditempatkan di ruangan mana, kapan mulai/selesai, dan alasan.
    - Menjamin 1 device hanya punya 1 assignment aktif pada suatu waktu (no overlap).
    - (Opsional) Menjaga kapasitas room (jumlah device aktif ≤ capacity).

    Integrasi lintas modul:
    - clinic_room_device:
        • clinic.device (device_id)
        • clinic.room (room_id, capacity)
        • clinic.device.movement (auto log perpindahan saat activate/move/end)
    - maintenance:
        • activity ping ke teknisi/supervisor ruangan saat device dipindahkan
    - booking/queue:
        • tidak mengubah data booking, namun assignment aktif menjadi sinyal readiness

    Catatan:
    - end bersifat opsional; saat end = False → assignment dianggap aktif.
    - Untuk "perpindahan", buat assignment baru ke room tujuan (state=active) dan auto-end assignment lama.
    """

    _name = "clinic.room.device.assignment"
    _description = "Clinic Room ↔ Device Assignment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start desc, id desc"

    # --------------------------
    # Identity
    # --------------------------
    name = fields.Char(
        string="Reference",
        index=True,
        tracking=True,
        help="Referensi assignment. Dapat diisi otomatis dari kombinasi Device/Room & tanggal.",
    )
    code = fields.Char(
        string="Assignment Code",
        index=True,
        help="Kode unik assignment. Jika kosong, akan diisi otomatis dari sequence.",
    )
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda s: s.env.company,
        index=True,
        required=True,
    )

    # --------------------------
    # Core Links
    # --------------------------
    device_id = fields.Many2one(
        "clinic.device",
        string="Device",
        required=True,
        index=True,
        tracking=True,
        ondelete="restrict",
    )
    room_id = fields.Many2one(
        "clinic.room",
        string="Room",
        required=True,
        index=True,
        tracking=True,
        ondelete="restrict",
    )

    # redundansi ringan untuk reporting cepat
    room_type_id = fields.Many2one(
        related="room_id.room_type_id",
        string="Room Type",
        store=True,
        readonly=True,
    )

    # --------------------------
    # Lifecycle
    # --------------------------
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("active", "Active"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        required=True,
    )
    start = fields.Datetime(
        string="Start",
        required=True,
        default=lambda s: fields.Datetime.now(),
        tracking=True,
        help="Waktu mulai penempatan device di ruangan ini.",
    )
    end = fields.Datetime(
        string="End",
        tracking=True,
        help="Waktu berakhir penempatan. Kosong berarti masih aktif.",
    )
    is_active = fields.Boolean(
        string="Is Active",
        compute="_compute_is_active",
        store=True,
        help="True jika state=active dan end masih kosong.",
    )
    duration_hours = fields.Float(
        string="Duration (hours)",
        compute="_compute_duration",
        store=True,
        help="Durasi dari start→end (jam). Jika aktif, dihitung sampai waktu saat ini.",
    )

    # --------------------------
    # Responsibility & Reasons
    # --------------------------
    responsible_id = fields.Many2one(
        "hr.employee",
        string="Responsible",
        help="Penanggung jawab pemindahan/penempatan.",
    )
    reason = fields.Selection(
        selection=[
            ("initial", "Initial Placement"),
            ("routine", "Routine Rearrangement"),
            ("load_balance", "Load Balancing"),
            ("maintenance", "Maintenance Preparation"),
            ("replacement", "Temporary Replacement"),
            ("other", "Other"),
        ],
        string="Reason",
        default="initial",
        help="Alasan penempatan/pemindahan perangkat.",
    )
    notes = fields.Text(string="Notes")

    # --------------------------
    # Movement Integration
    # --------------------------
    create_movement_logs = fields.Boolean(
        string="Create Movement Logs",
        default=True,
        help="Jika dicentang, otomatis membuat record clinic.device.movement saat activate/move/end.",
    )

    # --------------------------
    # SQL Constraints
    # --------------------------
        # Odoo 19 table constraints
    _start_before_end = models.Constraint(
        'CHECK (end IS NULL OR start <= end)',
        'Field End harus sesudah atau sama dengan Start.',
    )

    # --------------------------
    # Compute
    # --------------------------
    @api.depends("state", "end")
    def _compute_is_active(self):
        for rec in self:
            rec.is_active = rec.state == "active" and not rec.end

    @api.depends("start", "end")
    def _compute_duration(self):
        now = fields.Datetime.now()
        for rec in self:
            start = rec.start
            stop = rec.end or now
            if start and stop and stop >= start:
                delta = stop - start
                rec.duration_hours = round(delta.total_seconds() / 3600.0, 2)
            else:
                rec.duration_hours = 0.0

    # --------------------------
    # Helpers
    # --------------------------
    def _sequence_next(self):
        seq_ref = self.env.ref("clinic_room_device.seq_clinic_room_device_assignment", raise_if_not_found=False)
        return self.env["ir.sequence"].next_by_code("clinic.room.device.assignment") if seq_ref else False

    def _build_default_name(self, vals):
        """Nama default: [DEV-CODE or Device Name] → [ROOM-CODE or Room Name] @ YYYY-MM-DD HH:MM"""
        device = False
        room = False
        # coba dari vals, fallback dari self (ketika write)
        if vals.get("device_id"):
            device = self.env["clinic.device"].browse(vals["device_id"])
        elif self.device_id:
            device = self.device_id

        if vals.get("room_id"):
            room = self.env["clinic.room"].browse(vals["room_id"])
        elif self.room_id:
            room = self.room_id

        start_dt = vals.get("start") or self.start or fields.Datetime.now()
        start_dt_str = fields.Datetime.to_string(start_dt)

        dev_disp = device.display_name if device else _("(Device)")
        room_disp = room.display_name if room else _("(Room)")
        return "%s → %s @ %s" % (dev_disp, room_disp, start_dt_str)

    def _room_capacity_guard(self, room, when_start, when_end=None, device_self_id=None):
        """
        Validasi kapasitas ruangan:
        - Hitung assignment aktif di room pada interval (when_start, when_end).
        - Bandingkan dengan capacity room (jika > 0).
        Catatan: untuk kesederhanaan, dianggap 1 device memakan 1 kapasitas.
        """
        capacity = (room.capacity or 0)
        if capacity <= 0:
            return  # tidak memaksa kapasitas

        # definisikan jendela cek
        start = when_start
        stop = when_end or fields.Datetime.from_string("9999-12-31 23:59:59")

        # Ambil semua assignment di room tersebut yang overlap dgn interval
        domain = [("room_id", "=", room.id), ("state", "=", "active")]
        assigns = self.search(domain)
        # Tambahkan diri sendiri jika sedang di-create (device_self_id digunakan untuk menghindari double count pada write)
        in_use = 0
        for a in assigns:
            if device_self_id and a.device_id.id == device_self_id:
                # ini kemungkinan assignment lama; abaikan agar tidak double hitung
                continue
            a_start = a.start
            a_end = a.end or fields.Datetime.from_string("9999-12-31 23:59:59")
            # overlap rule: a_start <= stop and a_end >= start
            if a_start and a_start <= stop and a_end and a_end >= start:
                in_use += 1

        # plus 1 untuk device yang akan ditempatkan
        projected = in_use + 1
        if projected > capacity:
            raise ValidationError(
                _("Kapasitas ruangan terlampaui.\n"
                  "Room: %(room)s | Capacity: %(cap)d | In Use (projected): %(use)d") % {
                    "room": room.display_name or room.name,
                    "cap": capacity,
                    "use": projected,
                }
            )

    def _ensure_no_device_overlap(self, device, start, end, self_id=None):
        """
        Pastikan untuk device yang sama tidak ada dua assignment overlapping.
        Overlap jika: other.start <= end AND other.end >= start
        end yang kosong dianggap +infinity.
        """
        if not device or not start:
            return

        stop = end or fields.Datetime.from_string("9999-12-31 23:59:59")
        domain = [
            ("device_id", "=", device.id),
            ("state", "in", ["draft", "active"]),
            # overlap formula
            ("start", "<=", stop),
            "|",
            ("end", "=", False),
            ("end", ">=", start),
        ]
        overlapped = self.search(domain)
        if self_id:
            overlapped = overlapped.filtered(lambda r: r.id != self_id)
        if overlapped:
            raise ValidationError(_("Device ini sudah memiliki assignment lain yang overlap pada periode tersebut."))

    def _auto_end_previous_active(self, device, new_start, new_room_id):
        """
        Akhiri assignment aktif device sebelumnya (jika ada) ketika assignment baru diaktifkan.
        """
        prev = self.search([
            ("device_id", "=", device.id),
            ("state", "=", "active"),
            ("end", "=", False),
        ], order="start desc", limit=1)
        if prev:
            # End tepat 1 detik sebelum new_start agar tak overlap
            prev_end = fields.Datetime.add(new_start, seconds=-1)
            prev.write({"end": prev_end, "state": "done"})
            # movement log: from prev.room → new_room
            if self.create_movement_logs and "clinic.device.movement" in self.env:
                self.env["clinic.device.movement"].sudo().create({
                    "device_id": device.id,
                    "from_room_id": prev.room_id.id if prev.room_id else False,
                    "to_room_id": new_room_id,
                    "reason": "move",
                    "date": new_start,
                    "note": _("Auto move on new assignment activation."),
                })

    # --------------------------
    # ORM
    # --------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq_needed = self.env.ref("clinic_room_device.seq_clinic_room_device_assignment", raise_if_not_found=False)
        records = self.browse()
        for vals in vals_list:
            # default company mengikuti room/device jika ada
            if not vals.get("company_id"):
                if vals.get("room_id"):
                    vals["company_id"] = self.env["clinic.room"].browse(vals["room_id"]).company_id.id
                elif vals.get("device_id"):
                    vals["company_id"] = self.env["clinic.device"].browse(vals["device_id"]).company_id.id
                else:
                    vals["company_id"] = self.env.company.id

            # sequence code
            if not vals.get("code") and seq_needed:
                vals["code"] = self._sequence_next()

            # name default
            if not vals.get("name"):
                vals["name"] = self._build_default_name(vals)

            # normalisasi start/end
            start = vals.get("start") or fields.Datetime.now()
            end = vals.get("end")

            # validasi overlap device
            device = self.env["clinic.device"].browse(vals["device_id"])
            self._ensure_no_device_overlap(device, start, end)

            # kapasitas room (hanya ketika state=active)
            room = self.env["clinic.room"].browse(vals["room_id"])
            future_state = vals.get("state") or "draft"
            if future_state == "active":
                self._room_capacity_guard(room, start, end, device_self_id=device.id)

            rec = super().create(vals)
            records |= rec

            # jika langsung active → auto end assignment aktif sebelumnya & buat movement
            if rec.state == "active":
                rec._auto_end_previous_active(device, start, rec.room_id.id)

                if self.env.user and rec.create_movement_logs and "clinic.device.movement" in self.env:
                    # jika tidak ada prev (initial), tetap log 'assign'
                    self.env["clinic.device.movement"].sudo().create({
                        "device_id": rec.device_id.id,
                        "from_room_id": False,
                        "to_room_id": rec.room_id.id,
                        "reason": "assign",
                        "date": start,
                        "note": rec.notes or _("Initial assignment."),
                    })
        return records

    def write(self, vals):
        for rec in self:
            # cegah perubahan device_id ketika active kecuali admin sengaja (lebih aman)
            if "device_id" in vals and rec.state == "active":
                raise UserError(_("Tidak boleh mengganti Device pada assignment yang sedang Active. Akhiri dulu."))

            # validasi overlap saat ubah start/end/state/room
            n_start = fields.Datetime.to_datetime(vals.get("start")) if vals.get("start") else rec.start
            n_end = fields.Datetime.to_datetime(vals.get("end")) if vals.get("end") else rec.end
            n_state = vals.get("state") or rec.state
            n_room = self.env["clinic.room"].browse(vals["room_id"]) if vals.get("room_id") else rec.room_id

            # rule overlap: hanya relevan saat draft/active
            if n_state in ("draft", "active"):
                self._ensure_no_device_overlap(rec.device_id, n_start, n_end, self_id=rec.id)

            # guard kapasitas saat akan/masih active
            if n_state == "active":
                self._room_capacity_guard(n_room, n_start, n_end, device_self_id=rec.device_id.id)

            # auto set name jika kosong
            if vals.get("name") in (None, False):
                vals["name"] = rec._build_default_name(vals)

        res = super().write(vals)

        # jika perubahan state menjadi active → end prev
        for rec in self:
            if rec.state == "active":
                rec._auto_end_previous_active(rec.device_id, rec.start, rec.room_id.id)
        return res

    # --------------------------
    # Business Actions
    # --------------------------
    def action_activate(self):
        """
        Aktifkan assignment ini:
        - Validasi overlap & kapasitas.
        - Auto-end assignment aktif sebelumnya.
        - Buat movement 'assign' atau 'move'.
        """
        for rec in self:
            if rec.state in ("done", "cancelled"):
                raise UserError(_("Assignment sudah %s dan tidak dapat diaktifkan.") % rec.state)

            # Validasi
            rec._ensure_no_device_overlap(rec.device_id, rec.start, rec.end, self_id=rec.id)
            rec._room_capacity_guard(rec.room_id, rec.start, rec.end, device_self_id=rec.device_id.id)

            # Aktifkan
            rec.write({"state": "active", "end": False})

            # End prev & movement
            rec._auto_end_previous_active(rec.device_id, rec.start, rec.room_id.id)

            if rec.create_movement_logs and "clinic.device.movement" in self.env:
                self.env["clinic.device.movement"].sudo().create({
                    "device_id": rec.device_id.id,
                    "from_room_id": False,
                    "to_room_id": rec.room_id.id,
                    "reason": "assign",
                    "date": rec.start,
                    "note": rec.notes or _("Manual activation."),
                })

            # Activity ping ke supervisor/teknisi ruangan
            if rec.room_id and rec.room_id.supervisor_id and "hr.employee" in self.env:
                partner = rec.room_id.supervisor_id.user_id.partner_id if rec.room_id.supervisor_id.user_id else False
                if partner:
                    rec.activity_schedule(
                        "mail.mail_activity_data_todo",
                        user_id=rec.room_id.supervisor_id.user_id.id,
                        summary=_("Perangkat ditempatkan di ruangan"),
                        note=_("Device %(d)s ditempatkan di Room %(r)s.") % {
                            "d": rec.device_id.display_name,
                            "r": rec.room_id.display_name,
                        },
                    )

    def action_end(self):
        """
        Akhiri assignment (state → done) dan log movement 'unassign'.
        """
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != "active":
                raise UserError(_("Hanya assignment Active yang dapat diakhiri."))
            rec.write({"end": now, "state": "done"})

            if rec.create_movement_logs and "clinic.device.movement" in self.env:
                self.env["clinic.device.movement"].sudo().create({
                    "device_id": rec.device_id.id,
                    "from_room_id": rec.room_id.id,
                    "to_room_id": False,
                    "reason": "unassign",
                    "date": now,
                    "note": rec.notes or _("Assignment ended."),
                })

    def action_cancel(self):
        """
        Batalkan assignment (state → cancelled).
        """
        for rec in self:
            if rec.state == "active":
                raise UserError(_("Tidak dapat membatalkan assignment yang Active. Akhiri dulu jika perlu."))
            rec.write({"state": "cancelled"})

    def action_move_to_room(self, new_room_id, start_datetime=False, reason="move"):
        """
        Pindahkan device ke ruangan lain:
        - End assignment aktif saat ini.
        - Buat assignment baru Active pada room tujuan.

        Params:
            new_room_id (int or record): target Clinic Room id/record.
            start_datetime (datetime): default now().
            reason (str): alasan perpindahan.
        """
        self.ensure_one()
        if self.state != "active":
            raise UserError(_("Hanya assignment Active yang bisa dipakai untuk perpindahan."))

        new_room = new_room_id if isinstance(new_room_id, models.Model) else self.env["clinic.room"].browse(new_room_id)
        if not new_room or not new_room.exists():
            raise UserError(_("Ruangan tujuan tidak ditemukan."))

        when = start_datetime or fields.Datetime.now()

        # Akhiri assignment ini
        self.write({"end": fields.Datetime.add(when, seconds=-1), "state": "done"})

        # Buat assignment baru
        new_vals = {
            "company_id": self.company_id.id,
            "device_id": self.device_id.id,
            "room_id": new_room.id,
            "start": when,
            "state": "active",
            "reason": reason or "move",
            "create_movement_logs": self.create_movement_logs,
            "responsible_id": self.responsible_id.id or False,
            "notes": _("Auto-created by move from %s") % (self.room_id.display_name or self.room_id.name),
        }
        new_assignment = self.create([new_vals])

        # Log perpindahan eksplisit (tambahan, walau create() sudah logging)
        if self.create_movement_logs and "clinic.device.movement" in self.env:
            self.env["clinic.device.movement"].sudo().create({
                "device_id": self.device_id.id,
                "from_room_id": self.room_id.id,
                "to_room_id": new_room.id,
                "reason": "move",
                "date": when,
                "note": _("Moved via action from assignment %s → %s") % (
                    self.room_id.display_name or self.room_id.name,
                    new_room.display_name or new_room.name,
                ),
            })
        return new_assignment

    # --------------------------
    # Views: Smart Action Helpers
    # --------------------------
    def action_open_device(self):
        self.ensure_one()
        return {
            "name": _("Device"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device",
            "view_mode": "form",
            "res_id": self.device_id.id,
        }

    def action_open_room(self):
        self.ensure_one()
        return {
            "name": _("Room"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room",
            "view_mode": "form",
            "res_id": self.room_id.id,
        }
