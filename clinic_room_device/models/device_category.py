# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicDeviceCategory(models.Model):
    """
    Kategori Perangkat/Alat Medis Klinik

    Contoh: Laser/IPL, USG, RF, Injector, Dental Chair, X-Ray, ECG, dll.

    Integrasi lintas modul:
    - clinic_room_device:
        • clinic.device (One2many) → perangkat dalam kategori ini
        • default_* (maintenance/calibration) dipakai sebagai default pada device baru (lihat device.py _onchange_category_id)
    - maintenance:
        • maintenance.team → routing default request untuk kategori ini
    - product/stock:
        • product.category/product.product → parts/consumables rekomendasi
    - booking/queue/treatment:
        • readiness_hint, usage_kind untuk filtering device saat pemilihan treatment/ruang
    - audit:
        • mail.thread untuk jejak konfigurasi
    """

    _name = "clinic.device.category"
    _description = "Clinic Device Category"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"
    _rec_name = "display_name"

    # -----------------------
    # Identity & Display
    # -----------------------
    name = fields.Char(
        string="Category Name",
        required=True,
        index=True,
        tracking=True,
        help="Nama kategori perangkat (mis. Laser/IPL, USG, RF, Injector).",
    )
    code = fields.Char(
        string="Category Code",
        index=True,
        tracking=True,
        help="Kode unik kategori (mis. LASER, USG, RF, INJ).",
    )
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(string="Color Index")

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda s: s.env.company,
        index=True,
        required=True,
    )

    # -----------------------
    # Classification & Policy
    # -----------------------
    usage_kind = fields.Selection(
        selection=[
            ("laser_ipl", "Laser / IPL"),
            ("ultrasound", "Ultrasound / USG"),
            ("rf", "Radio Frequency"),
            ("injector", "Injector / Infusion / Pump"),
            ("monitoring", "Monitoring / Vitals"),
            ("imaging", "Imaging / X-Ray / CT / MRI"),
            ("dental", "Dental Equipment"),
            ("surgery", "Surgical Tools / OR"),
            ("lab", "Laboratory Equipment"),
            ("other", "Other"),
        ],
        string="Usage Kind",
        default="other",
        tracking=True,
        required=True,
        help="Klasifikasi fungsional untuk reporting & filtering.",
    )
    readiness_hint = fields.Selection(
        selection=[
            ("immediate", "Immediate Ready (plug-and-play)"),
            ("prep_required", "Prep Required (warm-up, calibration, sterilization)"),
            ("technician_required", "Technician Required"),
        ],
        string="Readiness Hint",
        default="immediate",
        help="Petunjuk kesiapan umum kategori ini.",
    )

    # -----------------------
    # Default Policy for Devices
    # -----------------------
    default_maintenance_interval_days = fields.Integer(
        string="Default Maintenance Interval (days)",
        default=0,
        help="Nilai default untuk device baru. 0 = tidak diset.",
    )
    default_calibration_interval_days = fields.Integer(
        string="Default Calibration Interval (days)",
        default=0,
        help="Nilai default untuk device baru. 0 = tidak diset.",
    )
    default_warranty_months = fields.Integer(
        string="Default Warranty (months)",
        default=12,
        help="Default masa garansi perangkat baru dalam kategori ini.",
    )
    maintenance_team_id = fields.Many2one(
        "maintenance.team",
        string="Default Maintenance Team",
        help="Tim maintenance default untuk seluruh device di kategori ini.",
    )

    # -----------------------
    # Compliance & Safety
    # -----------------------
    requires_certification = fields.Boolean(
        string="Requires Certification",
        help="Centang jika kategori ini memerlukan sertifikasi/kalibrasi berkala resmi.",
    )
    certification_notes = fields.Text(
        string="Certification Notes",
        help="Catatan standar sertifikasi/kalibrasi, regulasi, SOP, dsb.",
    )
    safety_tags = fields.Char(
        string="Safety Tags",
        help="Tag keamanan (comma separated), mis. 'protective_glasses,grounded,sterile'.",
    )

    # -----------------------
    # Consumables / Parts Mapping
    # -----------------------
    product_category_ids = fields.Many2many(
        "product.category",
        "clinic_device_cat_product_cat_rel",
        "device_category_id",
        "product_category_id",
        string="Related Product Categories",
        help="Kategori produk untuk parts/consumables yang relevan.",
    )
    # recommended_product_ids = fields.Many2many(
    #     "product.product",
    #     "clinic_device_cat_product_rel",
    #     "device_category_id",
    #     "product_id",
    #     string="Recommended Products (Consumables/Parts)",
    #     domain=[("product_tmpl_id.detailed_type", "in", ["consu", "service"])],
    #     help="Daftar produk yang direkomendasikan untuk kategori ini.",
    # )

    recommended_product_ids = fields.Many2many(
        "product.product",
        "clinic_device_cat_product_rel",
        "device_category_id",
        "product_id",
        string="Recommended Products (Consumables/Parts)",
        # Aman lintas versi: cek type di product.product ATAU di template
        domain=["|",
                ("type", "in", ["consu", "service"]),
                ("product_tmpl_id.type", "in", ["consu", "service"])],
        help="Daftar produk yang direkomendasikan untuk kategori ini.",
    )


    # -----------------------
    # Vendor & Training
    # -----------------------
    # Odoo 19 / dependency guard:
    # `supplier_rank` is provided by the Accounting addon. clinic_room_device
    # intentionally does not hard-depend on Accounting, so this relation stays
    # vendor-neutral at ORM level instead of using a supplier_rank domain.
    preferred_vendor_ids = fields.Many2many(
        "res.partner",
        "clinic_device_cat_vendor_rel",
        "device_category_id",
        "partner_id",
        string="Preferred Vendors",
        help="Vendor/supplier yang disarankan untuk kategori ini.",
    )
    training_required = fields.Boolean(
        string="Training Required",
        help="Centang jika operator wajib training untuk memakai device kategori ini.",
    )
    training_description = fields.Text(
        string="Training Notes",
        help="Deskripsi ringkas kebutuhan training/operator requirement.",
    )

    # -----------------------
    # Relations & Stats
    # -----------------------
    device_ids = fields.One2many(
        "clinic.device",
        "category_id",
        string="Devices",
    )
    device_count = fields.Integer(
        string="Devices",
        compute="_compute_device_stats",
        store=False,
    )
    due_maintenance_count = fields.Integer(
        string="Due Maintenance",
        compute="_compute_device_stats",
        store=False,
        help="Perangkat dengan next_maintenance_date <= today.",
    )
    due_calibration_count = fields.Integer(
        string="Due Calibration",
        compute="_compute_device_stats",
        store=False,
        help="Perangkat dengan calibration_due_date <= today.",
    )

    # -----------------------
    # Images / Notes
    # -----------------------
    image_1920 = fields.Image(string="Image", max_width=1920, max_height=1920)
    image_512 = fields.Image(related="image_1920", max_width=512, max_height=512, store=True)
    notes = fields.Html(string="Notes")

    # -----------------------
    # Constraints
    # -----------------------
        # Odoo 19 table constraints
    _code_company_uniq = models.Constraint(
        'unique(company_id, code)',
        'Category Code harus unik per perusahaan.',
    )
    _maint_interval_nonneg = models.Constraint(
        'CHECK (default_maintenance_interval_days >= 0)',
        'Maintenance interval default tidak boleh negatif.',
    )
    _calib_interval_nonneg = models.Constraint(
        'CHECK (default_calibration_interval_days >= 0)',
        'Calibration interval default tidak boleh negatif.',
    )
    _warranty_nonneg = models.Constraint(
        'CHECK (default_warranty_months >= 0)',
        'Warranty default tidak boleh negatif.',
    )

    # -----------------------
    # Computes
    # -----------------------
    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            if rec.code:
                rec.display_name = "[%s] %s" % (rec.code, rec.name or "")
            else:
                rec.display_name = rec.name or ""

    def _get_device_model(self):
        return "clinic.device" if "clinic.device" in self.env else False

    @api.depends("device_ids", "device_ids.next_maintenance_date", "device_ids.calibration_due_date")
    def _compute_device_stats(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.device_count = len(rec.device_ids)
            # hitung due maintenance/calibration dengan aman
            due_maint = 0
            due_calib = 0
            for d in rec.device_ids:
                if d.next_maintenance_date and d.next_maintenance_date <= today:
                    due_maint += 1
                if d.calibration_due_date and d.calibration_due_date <= today:
                    due_calib += 1
            rec.due_maintenance_count = due_maint
            rec.due_calibration_count = due_calib

    # -----------------------
    # ORM Overrides
    # -----------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = (vals["code"] or "").strip().upper()
            # user-friendly validations
            if vals.get("default_maintenance_interval_days", 0) < 0:
                raise ValidationError(_("Maintenance interval default tidak boleh negatif."))
            if vals.get("default_calibration_interval_days", 0) < 0:
                raise ValidationError(_("Calibration interval default tidak boleh negatif."))
            if vals.get("default_warranty_months", 0) < 0:
                raise ValidationError(_("Warranty default tidak boleh negatif."))
        return super().create(vals_list)

    def write(self, vals):
        if "code" in vals and vals["code"]:
            vals["code"] = (vals["code"] or "").strip().upper()
        # validations
        if "default_maintenance_interval_days" in vals and vals["default_maintenance_interval_days"] < 0:
            raise ValidationError(_("Maintenance interval default tidak boleh negatif."))
        if "default_calibration_interval_days" in vals and vals["default_calibration_interval_days"] < 0:
            raise ValidationError(_("Calibration interval default tidak boleh negatif."))
        if "default_warranty_months" in vals and vals["default_warranty_months"] < 0:
            raise ValidationError(_("Warranty default tidak boleh negatif."))
        return super().write(vals)

    # -----------------------
    # Onchange & Heuristics
    # -----------------------
    @api.onchange("usage_kind")
    def _onchange_usage_kind(self):
        """
        Set default heuristik berdasarkan jenis penggunaan.
        """
        presets = {
            "laser_ipl": dict(default_maintenance_interval_days=180, default_calibration_interval_days=180, default_warranty_months=12, readiness_hint="prep_required"),
            "ultrasound": dict(default_maintenance_interval_days=365, default_calibration_interval_days=365, default_warranty_months=12, readiness_hint="immediate"),
            "rf": dict(default_maintenance_interval_days=365, default_calibration_interval_days=365, default_warranty_months=12, readiness_hint="immediate"),
            "injector": dict(default_maintenance_interval_days=180, default_calibration_interval_days=180, default_warranty_months=12, readiness_hint="technician_required"),
            "monitoring": dict(default_maintenance_interval_days=365, default_calibration_interval_days=365, default_warranty_months=12, readiness_hint="immediate"),
            "imaging": dict(default_maintenance_interval_days=180, default_calibration_interval_days=180, default_warranty_months=12, readiness_hint="prep_required"),
            "dental": dict(default_maintenance_interval_days=365, default_calibration_interval_days=365, default_warranty_months=12, readiness_hint="prep_required"),
            "surgery": dict(default_maintenance_interval_days=90, default_calibration_interval_days=180, default_warranty_months=12, readiness_hint="technician_required"),
            "lab": dict(default_maintenance_interval_days=180, default_calibration_interval_days=365, default_warranty_months=12, readiness_hint="prep_required"),
            "other": dict(default_maintenance_interval_days=365, default_calibration_interval_days=365, default_warranty_months=12, readiness_hint="immediate"),
        }
        if self.usage_kind in presets:
            for k, v in presets[self.usage_kind].items():
                # hanya isi jika kosong/0 agar tidak menimpa isian user
                cur = getattr(self, k)
                if not cur:
                    setattr(self, k, v)

    # -----------------------
    # Naming Helpers
    # -----------------------
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

    # -----------------------
    # Smart Buttons / Actions
    # -----------------------
    def action_view_devices(self):
        self.ensure_one()
        return {
            "name": _("Devices"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device",
            "view_mode": "list,form",
            "domain": [("category_id", "=", self.id)],
            "context": {"default_category_id": self.id},
        }

    def action_view_due_maintenance(self):
        self.ensure_one()
        if "clinic.device" not in self.env:
            return False
        today = fields.Date.context_today(self)
        return {
            "name": _("Devices Due for Maintenance"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device",
            "view_mode": "list,form",
            "domain": [
                ("category_id", "=", self.id),
                ("next_maintenance_date", "!=", False),
                ("next_maintenance_date", "<=", today),
            ],
            "context": {"search_default_group_by_status": 1},
        }

    def action_view_due_calibration(self):
        self.ensure_one()
        if "clinic.device" not in self.env:
            return False
        today = fields.Date.context_today(self)
        return {
            "name": _("Devices Due for Calibration"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device",
            "view_mode": "list,form",
            "domain": [
                ("category_id", "=", self.id),
                ("calibration_due_date", "!=", False),
                ("calibration_due_date", "<=", today),
            ],
            "context": {"search_default_group_by_status": 1},
        }

    # -----------------------
    # Public API (Helper)
    # -----------------------
    def get_default_policy_payload(self):
        """
        Berikan paket default kebijakan untuk digunakan oleh wizard pembuatan device massal.
        """
        self.ensure_one()
        return {
            "maintenance_team_id": self.maintenance_team_id.id if self.maintenance_team_id else False,
            "default_maintenance_interval_days": max(self.default_maintenance_interval_days or 0, 0),
            "default_calibration_interval_days": max(self.default_calibration_interval_days or 0, 0),
            "default_warranty_months": max(self.default_warranty_months or 0, 0),
            "readiness_hint": self.readiness_hint,
            "usage_kind": self.usage_kind,
        }
