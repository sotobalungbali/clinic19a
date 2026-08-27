# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # =========================================================
    # Roles (Peran Partner dalam ekosistem ClinicOne)
    # =========================================================
    is_device_vendor = fields.Boolean(
        string="Device Vendor",
        help="Centang jika partner ini adalah vendor/supplier perangkat klinik."
    )
    is_device_installer = fields.Boolean(
        string="Device Installer",
        help="Centang jika partner ini menyediakan layanan instalasi perangkat."
    )
    is_maintenance_provider = fields.Boolean(
        string="Maintenance Provider",
        help="Centang jika partner ini menyediakan layanan maintenance/perawatan perangkat."
    )
    is_training_provider = fields.Boolean(
        string="Training Provider",
        help="Centang jika partner ini menyediakan pelatihan operator/teknisi perangkat."
    )

    # =========================================================
    # Kategori Perangkat & Produk Terkait
    # =========================================================
    device_category_ids = fields.Many2many(
        comodel_name="clinic.device.category" if "clinic.device.category" else "ir.model",
        relation="res_partner_device_category_rel",
        column1="partner_id",
        column2="device_category_id",
        string="Device Categories (Focus)",
        help="Kategori perangkat yang menjadi fokus/kompetensi partner ini."
    )
    product_category_ids = fields.Many2many(
        "product.category",
        "res_partner_product_category_rel",
        "partner_id",
        "product_category_id",
        string="Product Categories (Consumables/Parts)",
        help="Kategori produk/consumables/parts yang biasa disuplai partner ini."
    )

    # =========================================================
    # SLA & Coverage (untuk service/maintenance)
    # =========================================================
    service_level = fields.Selection(
        selection=[
            ("bronze", "Bronze"),
            ("silver", "Silver"),
            ("gold", "Gold"),
            ("platinum", "Platinum"),
        ],
        string="Service Level",
        help="Tingkat layanan untuk kontrak/mitra ini."
    )
    sla_response_hours = fields.Float(
        string="SLA Response (hours)",
        help="Target waktu respon sejak tiket/service request dibuat."
    )
    sla_resolution_hours = fields.Float(
        string="SLA Resolution (hours)",
        help="Target penyelesaian sejak tiket/service request dibuat."
    )
    coverage_days = fields.Selection(
        selection=[
            ("business", "Business Days (Mon–Fri)"),
            ("extended", "Extended (Mon–Sat)"),
            ("fullweek", "Full Week (Mon–Sun)"),
        ],
        string="Coverage Days",
        default="business",
        help="Hari kerja dukungan teknis."
    )
    coverage_start = fields.Float(
        string="Coverage Start (hour)",
        default=9.0,
        help="Jam mulai dukungan (format 24 jam, contoh 9.0 = 09:00)."
    )
    coverage_end = fields.Float(
        string="Coverage End (hour)",
        default=17.0,
        help="Jam akhir dukungan (format 24 jam, contoh 17.0 = 17:00)."
    )
    onsite_available = fields.Boolean(
        string="On-site Support Available",
        help="Centang jika partner menyediakan dukungan on-site."
    )
    remote_available = fields.Boolean(
        string="Remote Support Available",
        help="Centang jika partner menyediakan dukungan remote."
    )

    # =========================================================
    # Contract/Agreement (opsional, gunakan dokumen/attachment)
    # =========================================================
    contract_reference = fields.Char(
        string="Contract Reference",
        help="Nomor/Referensi kontrak/PKS dengan partner ini (opsional)."
    )
    contract_start = fields.Date(string="Contract Start")
    contract_end = fields.Date(string="Contract End")
    contract_notes = fields.Text(string="Contract Notes")

    # =========================================================
    # Personel & Sertifikasi
    # =========================================================
    technician_ids = fields.Many2many(
        "hr.employee",
        "res_partner_hr_employee_tech_rel",
        "partner_id",
        "employee_id",
        string="Technicians (External)",
        help="Teknisi eksternal (dari partner ini) yang biasa menangani perangkat kita."
    )
    certifications = fields.Text(
        string="Certifications/Accreditations",
        help="Daftar sertifikasi/akreditasi teknis yang dimiliki partner."
    )

    # =========================================================
    # Relasi Bisnis dengan Device/Room/Request
    # =========================================================
    # Devices yang terkait partner sebagai vendor (lihat device.py: vendor_id)
    device_ids = fields.One2many(
        comodel_name="clinic.device" if "clinic.device" else "ir.model",
        inverse_name="vendor_id",
        string="Devices Supplied",
        help="Daftar perangkat yang disuplai partner ini (berdasarkan field vendor_id di clinic.device)."
    )

    # Bila kita menambahkan field partner/vendor pada maintenance.request di addon ini:
    #   _inherit "maintenance.request"; partner_id = fields.Many2one('res.partner', ...)
    # Maka relasi ini bisa aktif untuk metrik & smart action.
    maintenance_request_ids = fields.One2many(
        comodel_name="maintenance.request" if "maintenance.request" else "ir.model",
        inverse_name="partner_id" if "maintenance.request" in locals() else "id",
        string="Maintenance Requests (as Vendor)",
        help="Tiket maintenance yang ditangani partner ini (jika field partner_id ditambahkan via inherit)."
    )

    # =========================================================
    # KPI/Metrics (computed ringan)
    # =========================================================
    device_count = fields.Integer(
        string="Devices Supplied",
        compute="_compute_metrics",
        store=False
    )
    maintenance_request_open_count = fields.Integer(
        string="Open Maintenance Requests",
        compute="_compute_metrics",
        store=False
    )
    last_service_date = fields.Date(
        string="Last Service Date",
        compute="_compute_metrics",
        store=False,
        help="Tanggal terakhir partner ini tercatat menangani maintenance (jika integrasi aktif)."
    )
    active_contract = fields.Boolean(
        string="Active Contract",
        compute="_compute_active_contract",
        store=False
    )

    # =========================================================
    # Compute
    # =========================================================
    def _get_maintenance_model(self):
        """Return model string untuk maintenance.request jika ada."""
        return "maintenance.request" if "maintenance.request" in self.env else False

    @api.depends(
        "device_ids",
        "maintenance_request_ids",
        "maintenance_request_ids.request_date",
        "maintenance_request_ids.stage_id",
        "contract_start", "contract_end"
    )
    def _compute_metrics(self):
        MRequest = self._get_maintenance_model()
        for rec in self:
            # Devices supplied
            rec.device_count = len(rec.device_ids) if rec.device_ids else 0

            # Maintenance metrics (aman jika modul/field tidak ada)
            open_count = 0
            last_date = False
            if MRequest and "partner_id" in self.env[MRequest]._fields:
                # hitung open (state berdasarkan stage/kanban: gunakan heuristik aman)
                # Asumsi: stage_id.fold = True → closed; else open (bila field tersedia).
                m_reqs = rec.maintenance_request_ids
                if m_reqs:
                    # last service date
                    dates = [r.request_date.date() for r in m_reqs if getattr(r, "request_date", False)]
                    if dates:
                        last_date = max(dates)
                    # open count
                    for r in m_reqs:
                        fold = False
                        if "stage_id" in r._fields and r.stage_id:
                            fold = bool(getattr(r.stage_id, "fold", False))
                        # treat non-folded as open
                        if not fold:
                            open_count += 1
            rec.maintenance_request_open_count = open_count
            rec.last_service_date = last_date or False

    @api.depends("contract_start", "contract_end")
    def _compute_active_contract(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.contract_start and rec.contract_end:
                rec.active_contract = rec.contract_start <= today <= rec.contract_end
            elif rec.contract_start and not rec.contract_end:
                rec.active_contract = rec.contract_start <= today
            elif not rec.contract_start and rec.contract_end:
                rec.active_contract = today <= rec.contract_end
            else:
                rec.active_contract = False

    # =========================================================
    # Helper: SLA Coverage Window Checker
    # =========================================================
    def check_in_coverage_window(self, dt=None):
        """
        Cek apakah 'dt' (Datetime) berada di dalam jam & hari coverage partner.
        Return: bool.
        Dipakai modul lain (mis. pembuatan maintenance.request) untuk memberi hint apakah
        request kemungkinan ditangani segera oleh partner ini.
        """
        self.ensure_one()
        dt = dt or fields.Datetime.now()

        # Hari (0=Mon .. 6=Sun)
        weekday = fields.Datetime.context_timestamp(self, dt).weekday()
        if self.coverage_days == "business" and weekday > 4:
            return False
        if self.coverage_days == "extended" and weekday > 5:
            return False

        # Jam
        time_str = fields.Datetime.context_timestamp(self, dt).strftime("%H.%M")
        current_hour = float(time_str.replace(".", ".", 1))
        start = self.coverage_start or 0.0
        end = self.coverage_end or 24.0
        return start <= current_hour <= end

    # =========================================================
    # Smart Actions (UI)
    # =========================================================
    def action_view_devices(self):
        """Buka perangkat yang disuplai partner ini (berdasar clinic.device.vendor_id)."""
        self.ensure_one()
        if "clinic.device" not in self.env:
            raise UserError(_("Model clinic.device belum tersedia."))
        return {
            "name": _("Devices Supplied"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device",
            "view_mode": "list,form,kanban",
            "domain": [("vendor_id", "=", self.id)],
            "context": {"default_vendor_id": self.id},
        }

    def action_view_maintenance_requests(self):
        """
        Buka maintenance requests yang ditangani partner ini.
        Hanya bekerja jika kita meng-extend maintenance.request menambahkan partner_id.
        """
        self.ensure_one()
        MRequest = self._get_maintenance_model()
        if not MRequest or "partner_id" not in self.env[MRequest]._fields:
            raise UserError(_("Integrasi Maintenance belum aktif (field partner_id tidak ditemukan)."))
        return {
            "name": _("Maintenance Requests (Vendor)"),
            "type": "ir.actions.act_window",
            "res_model": MRequest,
            "view_mode": "list,form,kanban,pivot,graph",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    def action_view_stock_pickings(self):
        """
        Opsional: buka picking dari/ke partner ini (supplier/customer).
        """
        self.ensure_one()
        if "stock.picking" not in self.env:
            raise UserError(_("Modul Stock/Inventory belum terpasang."))
        return {
            "name": _("Stock Pickings"),
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "list,form,kanban",
            "domain": ["|", ("partner_id", "=", self.id), ("owner_id", "=", self.id)],
        }

    # =========================================================
    # Onchange Heuristics
    # =========================================================
    @api.onchange("is_device_vendor")
    def _onchange_is_device_vendor(self):
        """
        Heuristik kecil:
        - Jika dicentang & partner belum punya supplier_rank, naikkan ke 1 agar terlihat sebagai vendor.
        """
        if self.is_device_vendor and hasattr(self, "supplier_rank"):
            if not self.supplier_rank or self.supplier_rank <= 0:
                self.supplier_rank = 1

    @api.onchange("service_level")
    def _onchange_service_level(self):
        """
        Preset SLA berdasarkan service level (hanya isi jika kosong).
        """
        presets = {
            "bronze": dict(sla_response_hours=24.0, sla_resolution_hours=72.0, coverage_days="business",
                           coverage_start=9.0, coverage_end=17.0, remote_available=True, onsite_available=False),
            "silver": dict(sla_response_hours=12.0, sla_resolution_hours=48.0, coverage_days="extended",
                           coverage_start=8.0, coverage_end=18.0, remote_available=True, onsite_available=True),
            "gold": dict(sla_response_hours=4.0, sla_resolution_hours=24.0, coverage_days="fullweek",
                         coverage_start=8.0, coverage_end=20.0, remote_available=True, onsite_available=True),
            "platinum": dict(sla_response_hours=1.0, sla_resolution_hours=8.0, coverage_days="fullweek",
                             coverage_start=0.0, coverage_end=23.99, remote_available=True, onsite_available=True),
        }
        if self.service_level in presets:
            for k, v in presets[self.service_level].items():
                cur = getattr(self, k, None)
                if not cur and cur != 0:
                    setattr(self, k, v)

    # =========================================================
    # Public API untuk modul lain
    # =========================================================
    def get_service_profile_payload(self):
        """
        Kembalikan profil layanan partner untuk konsumsi modul lain (JSON-like dict).
        """
        self.ensure_one()
        return {
            "partner_id": self.id,
            "service_level": self.service_level,
            "sla_response_hours": self.sla_response_hours,
            "sla_resolution_hours": self.sla_resolution_hours,
            "coverage_days": self.coverage_days,
            "coverage_start": self.coverage_start,
            "coverage_end": self.coverage_end,
            "remote_available": self.remote_available,
            "onsite_available": self.onsite_available,
            "device_category_ids": self.device_category_ids.ids,
            "product_category_ids": self.product_category_ids.ids,
            "active_contract": self.active_contract,
            "contract_start": self.contract_start,
            "contract_end": self.contract_end,
        }
