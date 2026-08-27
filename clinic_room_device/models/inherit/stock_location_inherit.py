# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class StockLocation(models.Model):
    _inherit = "stock.location"

    # =========================================================
    # ClinicOne flags & mapping
    # =========================================================
    is_clinic_room_location = fields.Boolean(
        string="Clinic Room Location",
        help="Tandai lokasi ini sebagai representasi fisik dari sebuah Ruangan Klinik."
    )
    clinic_room_id = fields.Many2one(
        comodel_name="clinic.room" if "clinic.room" else "ir.model",
        string="Linked Clinic Room",
        domain=[("active", "=", True)],
        help="Hubungkan lokasi gudang ini dengan Ruang Klinik untuk sinkronisasi stok & operasional."
    )

    # behavior hints (untuk proses operasional/pembersihan)
    sanitation_required = fields.Boolean(
        string="Sanitation Required",
        help="Jika dicentang, stok yang masuk ke lokasi ini memerlukan prosedur sanitasi/sterilisasi."
    )
    quarantine_location = fields.Boolean(
        string="Quarantine Area",
        help="Tandai jika lokasi ini dipakai karantina sementara alat/perbekalan sebelum dinyatakan 'siap pakai'."
    )
    maintenance_dropzone = fields.Boolean(
        string="Maintenance Dropzone",
        help="Tandai jika lokasi ini digunakan sebagai area parkir perangkat yang menunggu/baru selesai maintenance."
    )

    # kapasitas & readiness untuk operasional ruang
    capacity_device_hint = fields.Integer(
        string="Device Capacity (hint)",
        default=0,
        help="Opsional. Batas perangkat yang ideal di lokasi/ruang ini (0 = abaikan)."
    )
    allow_device_storage = fields.Boolean(
        string="Allow Device Storage",
        default=True,
        help="Jika dimatikan, assignment perangkat ke ruangan ini akan memberi peringatan."
    )

    # =========================================================
    # KPI / Metrics
    # =========================================================
    device_count = fields.Integer(
        string="Active Devices in Room",
        compute="_compute_metrics",
        store=False,
        help="Jumlah perangkat yang sedang aktif di ruangan ini (berdasar assignment)."
    )
    stock_quant_count = fields.Integer(
        string="Stock Quants",
        compute="_compute_metrics",
        store=False,
        help="Jumlah baris quants (produk) yang tercatat di lokasi ini."
    )
    maintenance_queue_count = fields.Integer(
        string="Pending Maintenance",
        compute="_compute_metrics",
        store=False,
        help="Perkiraan jumlah tiket maintenance terkait ruangan/perangkat di lokasi ini (jika integrasi aktif)."
    )

    # =========================================================
    # Constraints
    # =========================================================
        # Odoo 19 table constraints
    _clinic_room_location_unique = models.Constraint(
        'unique(company_id, clinic_room_id)',
        'Satu Ruangan Klinik hanya boleh terhubung ke satu Lokasi (per perusahaan).',
    )

    # =========================================================
    # Compute
    # =========================================================
    def _get_assignment_model(self):
        return "clinic.room.device.assignment" if "clinic.room.device.assignment" in self.env else False

    def _get_maintenance_model(self):
        return "maintenance.request" if "maintenance.request" in self.env else False

    @api.depends("clinic_room_id", "is_clinic_room_location")
    def _compute_metrics(self):
        AssignmentModel = self._get_assignment_model()
        MreqModel = self._get_maintenance_model()
        for rec in self:
            # Devices aktif (assignment active, end False) pada room yang ditaut
            if rec.is_clinic_room_location and rec.clinic_room_id and AssignmentModel:
                active_asg = self.env[AssignmentModel].sudo().search_count([
                    ("room_id", "=", rec.clinic_room_id.id),
                    ("state", "=", "active"),
                    ("end", "=", False),
                ])
                rec.device_count = active_asg
            else:
                rec.device_count = 0

            # Stock quants di lokasi ini
            if "stock.quant" in self.env:
                rec.stock_quant_count = self.env["stock.quant"].sudo().search_count([("location_id", "=", rec.id)])
            else:
                rec.stock_quant_count = 0

            # Maintenance queue (opsional): request yg menyinggung room ini atau device yg sedang di room ini
            pending = 0
            if MreqModel:
                # jika field room_id tersedia → hitung langsung
                if "room_id" in self.env[MreqModel]._fields and rec.clinic_room_id:
                    domain = [("room_id", "=", rec.clinic_room_id.id)]
                    # heuristik open: stage.fold=False bila field ada
                    reqs = self.env[MreqModel].sudo().search(domain)
                    for r in reqs:
                        fold = False
                        if "stage_id" in r._fields and r.stage_id:
                            fold = bool(getattr(r.stage_id, "fold", False))
                        if not fold:
                            pending += 1
            rec.maintenance_queue_count = pending

    # =========================================================
    # ORM overrides / Validations
    # =========================================================
    def _ensure_usage_valid(self, vals):
        """
        Jika lokasi ditandai sebagai Clinic Room Location → usage harus INTERNAL/TRANSIT.
        """
        usage = vals.get("usage", self.usage)
        is_room_loc = vals.get("is_clinic_room_location", self.is_clinic_room_location)
        if is_room_loc and usage not in ("internal", "transit"):
            raise ValidationError(_("Clinic Room Location harus bertipe usage 'internal' atau 'transit'."))

    def _ensure_room_company_match(self, vals):
        """
        Pastikan company lokasi = company room ketika di-link.
        """
        room_id = vals.get("clinic_room_id", self.clinic_room_id.id if self.clinic_room_id else False)
        if room_id:
            room = self.env["clinic.room"].browse(room_id)
            cmp_loc = vals.get("company_id", self.company_id.id if self.company_id else self.env.company.id)
            if room and room.company_id and room.company_id.id != cmp_loc:
                raise ValidationError(_("Perusahaan pada Lokasi & Ruangan harus sama."))

    def _ensure_capacity_hint_guard(self, vals):
        """
        Opsional: beri warning (UserError) jika melebihi hint kapasitas saat sudah ada assignment aktif.
        (Tidak memblok, hanya di action di bawah—di sini kita hanya menjaga konsistensi angka.)
        """
        cap = vals.get("capacity_device_hint", self.capacity_device_hint or 0)
        if cap is not None and cap < 0:
            raise ValidationError(_("Device Capacity (hint) tidak boleh negatif."))

    def write(self, vals):
        # Validasi usage & company/room
        self._ensure_usage_valid(vals)
        self._ensure_room_company_match(vals)
        self._ensure_capacity_hint_guard(vals)

        # Jika baru dipasang flag Clinic Room Location dan belum ada usage → set internal
        if vals.get("is_clinic_room_location") and not vals.get("usage"):
            vals.setdefault("usage", "internal")
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        recs = self.browse()
        for vals in vals_list:
            # Default usage internal bila ditandai sebagai room location
            if vals.get("is_clinic_room_location") and not vals.get("usage"):
                vals["usage"] = "internal"
            # Validations
            self._ensure_usage_valid(vals)
            self._ensure_room_company_match(vals)
            self._ensure_capacity_hint_guard(vals)
            recs |= super().create(vals)
        return recs

    # =========================================================
    # Smart Actions (UI)
    # =========================================================
    def action_open_clinic_room(self):
        self.ensure_one()
        if not self.clinic_room_id:
            raise UserError(_("Lokasi ini belum ditautkan ke Ruang Klinik."))
        return {
            "name": _("Clinic Room"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room",
            "view_mode": "form",
            "res_id": self.clinic_room_id.id,
        }

    def action_open_active_devices(self):
        """
        Tampilkan perangkat aktif (via assignment) pada room yang ditautkan.
        """
        self.ensure_one()
        if not self.clinic_room_id:
            raise UserError(_("Lokasi ini belum ditautkan ke Ruang Klinik."))
        if "clinic.room.device.assignment" not in self.env:
            raise UserError(_("Model assignment perangkat belum tersedia."))
        # ambil devices via assignment aktif
        asg = self.env["clinic.room.device.assignment"].sudo().search([
            ("room_id", "=", self.clinic_room_id.id),
            ("state", "=", "active"),
            ("end", "=", False),
        ])
        device_ids = asg.mapped("device_id").ids
        if not device_ids:
            # tetap buka list kosong agar user bisa tambah dari sana
            return {
                "name": _("Active Devices"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.device",
                "view_mode": "list,form,kanban",
                "domain": [("id", "in", [])],
            }
        return {
            "name": _("Active Devices"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device",
            "view_mode": "list,form,kanban",
            "domain": [("id", "in", device_ids)],
        }

    def action_open_quants(self):
        self.ensure_one()
        if "stock.quant" not in self.env:
            raise UserError(_("Modul Inventory belum terpasang."))
        return {
            "name": _("Stock Quants"),
            "type": "ir.actions.act_window",
            "res_model": "stock.quant",
            "view_mode": "list,pivot,graph,form",
            "domain": [("location_id", "=", self.id)],
            "context": {"search_default_internal_loc": 1},
        }

    def action_open_stock_moves(self):
        self.ensure_one()
        if "stock.move.line" not in self.env:
            raise UserError(_("Modul Inventory belum terpasang."))
        return {
            "name": _("Stock Move Lines"),
            "type": "ir.actions.act_window",
            "res_model": "stock.move.line",
            "view_mode": "list,form",
            "domain": ["|", ("location_id", "=", self.id), ("location_dest_id", "=", self.id)],
        }

    def action_open_maintenance_requests(self):
        self.ensure_one()
        MreqModel = self._get_maintenance_model()
        if not MreqModel or "room_id" not in self.env[MreqModel]._fields:
            raise UserError(_("Integrasi Maintenance belum aktif (field room_id tidak tersedia)."))
        return {
            "name": _("Maintenance Requests"),
            "type": "ir.actions.act_window",
            "res_model": MreqModel,
            "view_mode": "list,form,kanban,pivot,graph",
            "domain": [("room_id", "=", self.clinic_room_id.id)],
        }

    # =========================================================
    # Helpers: Sync & Guards
    # =========================================================
    def sync_room_location_link(self):
        """
        Sinkronisasi ringan:
        - Jika lokasi bertanda 'Clinic Room Location' & ter-link room, maka set 'room.location_id' menjadi lokasi ini
          (tanpa memaksa; hanya jika field tersedia & berbeda).
        """
        self.ensure_one()
        if not self.is_clinic_room_location or not self.clinic_room_id:
            raise UserError(_("Lokasi ini bukan Clinic Room Location atau belum ditautkan ke Room."))

        if "location_id" in self.clinic_room_id._fields and self.clinic_room_id.location_id != self:
            self.clinic_room_id.sudo().write({"location_id": self.id})
        return True

    def guard_assignment_capacity(self):
        """
        Peringatan kapasitas: jika capacity_device_hint > 0 dan jumlah assignment aktif melebihi kapasitas, raise warning.
        Dipanggil dari server action/wizard (opsional) sebelum melakukan assignment masal.
        """
        self.ensure_one()
        if not (self.is_clinic_room_location and self.clinic_room_id and self.capacity_device_hint):
            return True
        AssignmentModel = self._get_assignment_model()
        if not AssignmentModel:
            return True
        active_count = self.env[AssignmentModel].sudo().search_count([
            ("room_id", "=", self.clinic_room_id.id),
            ("state", "=", "active"),
            ("end", "=", False),
        ])
        if active_count > self.capacity_device_hint:
            raise UserError(_(
                "Perhatian: jumlah perangkat aktif (%(use)d) melebihi kapasitas hint (%(cap)d) pada lokasi/ruang ini."
            ) % {"use": active_count, "cap": self.capacity_device_hint})
        return True

    # =========================================================
    # Onchange
    # =========================================================
    @api.onchange("is_clinic_room_location")
    def _onchange_is_clinic_room_location(self):
        """
        Heuristik: jika baru ditandai sebagai Clinic Room Location dan usage bukan internal/transit,
        set usage = internal agar aman.
        """
        if self.is_clinic_room_location and self.usage not in ("internal", "transit"):
            self.usage = "internal"

    @api.onchange("clinic_room_id")
    def _onchange_clinic_room_id(self):
        """
        Heuristik: samakan company jika berbeda.
        """
        if self.clinic_room_id and self.company_id and self.clinic_room_id.company_id and \
           self.clinic_room_id.company_id.id != self.company_id.id:
            self.company_id = self.clinic_room_id.company_id.id

    # =========================================================
    # Public API payload (untuk modul lain)
    # =========================================================
    def get_room_location_payload(self):
        """
        JSON-like dict untuk konsumsi modul lain, menyatukan info lokasi-ruang.
        """
        self.ensure_one()
        return {
            "location_id": self.id,
            "location_name": self.complete_name if hasattr(self, "complete_name") else self.name,
            "company_id": self.company_id.id if self.company_id else False,
            "is_clinic_room_location": self.is_clinic_room_location,
            "clinic_room_id": self.clinic_room_id.id if self.clinic_room_id else False,
            "sanitation_required": self.sanitation_required,
            "quarantine_location": self.quarantine_location,
            "maintenance_dropzone": self.maintenance_dropzone,
            "capacity_device_hint": max(self.capacity_device_hint or 0, 0),
            "allow_device_storage": bool(self.allow_device_storage),
            "device_count": self.device_count,
            "stock_quant_count": self.stock_quant_count,
            "maintenance_queue_count": self.maintenance_queue_count,
        }
