
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicDevice(models.Model):
    """
    Master Perangkat/Alat Medis Klinik.

    Integrasi lintas modul:
    - clinic_room_device:
        • clinic.room.device.assignment → historis & status assignment aktif
        • clinic.device.movement → historis perpindahan
    - clinic_room_device (room): current_room_id dihitung dari assignment aktif
    - maintenance:
        • maintenance.request (opsional device_id ditambahkan via inherit)
        • maintenance.team untuk routing request
    - stock/product:
        • product.product (opsional) untuk valuasi/consumables
        • stock.lot (opsional) untuk serial/lot
        • stock.location untuk mapping lokasi fisik (opsional)
    - booking/queue/treatment:
        • readiness/status sebagai sinyal pemilihan device

    Best Practices:
    - mail.thread & mail.activity.mixin: audit log & kolaborasi
    - Sequence untuk field code (unik & readable)
    - Constraints untuk serial unik per company
    - Smart buttons untuk navigasi cepat
    """

    _name = "clinic.device"
    _description = "Clinic Device / Medical Equipment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"
    _rec_name = "display_name"

    # --------------------------
    # Identity
    # --------------------------
    name = fields.Char(
        string="Device Name",
        required=True,
        index=True,
        tracking=True,
        help="Nama perangkat/alat medis. Contoh: 'IPL Shooter A', 'USG Unit 02'.",
    )
    code = fields.Char(
        string="Device Code",
        index=True,
        tracking=True,
        help="Kode unik perangkat. Jika kosong, diisi otomatis dari sequence.",
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
        default=lambda s: s.env.company,
        index=True,
        required=True,
    )

    # --------------------------
    # Classification
    # --------------------------
    category_id = fields.Many2one(
        "clinic.device.category",
        string="Device Category",
        required=False,
        tracking=True,
        help="Kategori perangkat/alat (mis. Laser/IPL, USG, RF, Injector).",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Linked Product",
        help="Opsional. Hubungkan ke produk untuk kebutuhan valuasi/komponen.",
    )
    lot_id = fields.Many2one(
        # "stock.lot",
        "stock.lot",
        string="Lot/Serial (Stock)",
        help="Opsional. Gunakan jika ingin melacak via stock lot/serial resmi.",
    )
    serial_no = fields.Char(
        string="Serial Number",
        index=True,
        tracking=True,
        help="Nomor seri perangkat (jika ada).",
    )
    model = fields.Char(
        string="Model/Type",
        help="Model/tipe perangkat dari pabrikan.",
    )
    manufacturer = fields.Char(
        string="Manufacturer",
        help="Nama produsen/perusahaan pembuat.",
    )

    # --------------------------
    # Lifecycle & Readiness
    # --------------------------
    status = fields.Selection(
        selection=[
            ("available", "Available"),
            ("reserved", "Reserved"),
            ("in_use", "In Use"),
            ("maintenance", "Maintenance"),
            ("offline", "Offline"),
            ("retired", "Retired"),
        ],
        string="Status",
        default="available",
        tracking=True,
        required=True,
        help="Status kesiapan perangkat.",
    )
    is_ready = fields.Boolean(
        string="Ready for Use",
        compute="_compute_is_ready",
        store=False,
        help="True bila status termasuk kategori siap pakai.",
    )

    # --------------------------
    # Location / Room Mapping
    # --------------------------
    location_id = fields.Many2one(
        "stock.location",
        string="Stock Location",
        domain=[("usage", "in", ["internal", "transit"])],
        help="Lokasi fisik perangkat di gudang/lokasi internal.",
    )
    assignment_ids = fields.One2many(
        "clinic.room.device.assignment",
        "device_id",
        string="Room Assignments",
        help="Riwayat penempatan perangkat ke ruangan.",
    )
    current_room_id = fields.Many2one(
        "clinic.room",
        string="Current Room",
        compute="_compute_current_room",
        store=False,
        help="Ruangan saat ini (berdasarkan assignment aktif).",
    )

    movement_ids = fields.One2many(
        "clinic.device.movement",
        "device_id",
        string="Movements",
        help="Riwayat perpindahan perangkat (ruang/lokasi/alasan).",
    )

    # --------------------------
    # Maintenance & Calibration
    # --------------------------
    maintenance_team_id = fields.Many2one(
        "maintenance.team",
        string="Maintenance Team",
        help="Tim maintenance default untuk perangkat ini.",
    )
    maintenance_interval_days = fields.Integer(
        string="Maintenance Interval (days)",
        default=0,
        help="Interval rekomendasi maintenance berkala. 0 = tidak diset.",
    )
    last_maintenance_date = fields.Date(
        string="Last Maintenance Date",
        help="Tanggal maintenance terakhir.",
    )
    next_maintenance_date = fields.Date(
        string="Next Maintenance",
        compute="_compute_next_maintenance_date",
        store=True,
        help="Tanggal maintenance berikutnya (berdasarkan interval).",
    )
    maintenance_request_count = fields.Integer(
        string="Maintenance Requests",
        compute="_compute_counters",
        store=False,
    )

    calibration_interval_days = fields.Integer(
        string="Calibration Interval (days)",
        default=0,
        help="Interval kalibrasi. 0 = tidak diset.",
    )
    calibration_date_last = fields.Date(
        string="Last Calibration",
    )
    calibration_due_date = fields.Date(
        string="Calibration Due",
        compute="_compute_calibration_due",
        store=True,
    )

    # --------------------------
    # Procurement / Warranty
    # --------------------------
    vendor_id = fields.Many2one("res.partner", string="Vendor/Supplier")
    purchase_date = fields.Date(string="Purchase Date")
    purchase_price = fields.Monetary(string="Purchase Price")
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda s: s.env.company.currency_id.id,
    )
    warranty_months = fields.Integer(
        string="Warranty (months)",
        default=0,
        help="Masa garansi dari tanggal pembelian.",
    )
    warranty_end_date = fields.Date(
        string="Warranty End",
        compute="_compute_warranty_end",
        store=True,
    )

    # --------------------------
    # Images / Notes
    # --------------------------
    image_1920 = fields.Image(string="Image", max_width=1920, max_height=1920)
    image_512 = fields.Image(related="image_1920", max_width=512, max_height=512, store=True)
    notes = fields.Html(string="Notes")

    # --------------------------
    # Stats
    # --------------------------
    assignment_count = fields.Integer(
        string="Assignments",
        compute="_compute_counters",
        store=False,
    )
    movement_count = fields.Integer(
        string="Movements",
        compute="_compute_counters",
        store=False,
    )

    qualified_doctor_ids = fields.Many2many(
        "hr.employee",
        relation="clinic_doctor_device_rel",
        column1="device_id",      # mirror
        column2="employee_id",    # mirror
        string="Qualified Doctors",
    )

    # --------------------------
    # Constraints
    # --------------------------
        # Odoo 19 table constraints
    _serial_company_uniq = models.Constraint(
        'unique(company_id, serial_no)',
        'Serial Number harus unik per perusahaan.',
    )
    _maint_interval_nonneg = models.Constraint(
        'CHECK (maintenance_interval_days >= 0)',
        'Maintenance interval tidak boleh negatif.',
    )
    _calib_interval_nonneg = models.Constraint(
        'CHECK (calibration_interval_days >= 0)',
        'Calibration interval tidak boleh negatif.',
    )
    _warranty_nonneg = models.Constraint(
        'CHECK (warranty_months >= 0)',
        'Warranty (months) tidak boleh negatif.',
    )

    # --------------------------
    # Computes
    # --------------------------
    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            if rec.code:
                rec.display_name = "[%s] %s" % (rec.code, rec.name or "")
            else:
                rec.display_name = rec.name or ""

    @api.depends("status")
    def _compute_is_ready(self):
        ready_states = {"available", "reserved"}
        for rec in self:
            rec.is_ready = rec.status in ready_states

    @api.depends("assignment_ids.is_active", "assignment_ids.room_id", "assignment_ids.end")
    def _compute_current_room(self):
        """
        Ambil assignment aktif (is_active & end kosong).
        Jika >1 (anomali), ambil yang terbaru berdasarkan start.
        """
        for rec in self:
            actives = rec.assignment_ids.filtered(lambda a: a.is_active and not a.end)
            if not actives:
                rec.current_room_id = False
                continue
            # pilih paling baru
            latest = sorted(actives, key=lambda a: (a.start or fields.Datetime.from_string("1970-01-01")), reverse=True)[0]
            rec.current_room_id = latest.room_id.id if latest.room_id else False

    @api.depends("last_maintenance_date", "maintenance_interval_days")
    def _compute_next_maintenance_date(self):
        for rec in self:
            if rec.last_maintenance_date and rec.maintenance_interval_days and rec.maintenance_interval_days > 0:
                rec.next_maintenance_date = fields.Date.add(rec.last_maintenance_date, days=rec.maintenance_interval_days)
            else:
                rec.next_maintenance_date = False

    @api.depends("calibration_date_last", "calibration_interval_days")
    def _compute_calibration_due(self):
        for rec in self:
            if rec.calibration_date_last and rec.calibration_interval_days and rec.calibration_interval_days > 0:
                rec.calibration_due_date = fields.Date.add(rec.calibration_date_last, days=rec.calibration_interval_days)
            else:
                rec.calibration_due_date = False

    @api.depends("purchase_date", "warranty_months")
    def _compute_warranty_end(self):
        for rec in self:
            if rec.purchase_date and rec.warranty_months and rec.warranty_months > 0:
                rec.warranty_end_date = fields.Date.add(rec.purchase_date, months=rec.warranty_months)
            else:
                rec.warranty_end_date = False

    def _get_maintenance_request_model(self):
        return "maintenance.request" if "maintenance.request" in self.env else False

    # def _get_booking_model(self):
    #     return "booking.booking" if "booking.booking" in self.env else False

    def _get_room_model(self):
        return "clinic.room" if "clinic.room" in self.env else False

    def _get_movement_model(self):
        return "clinic.device.movement" if "clinic.device.movement" in self.env else False

    @api.depends("assignment_ids", "movement_ids")
    def _compute_counters(self):
        MRequestModel = self._get_maintenance_request_model()
        for rec in self:
            rec.assignment_count = len(rec.assignment_ids)
            rec.movement_count = len(rec.movement_ids)
            # maintenance count aman jika modul ada & field device_id ditambahkan via inherit
            if MRequestModel and "device_id" in self.env[MRequestModel]._fields:
                rec.maintenance_request_count = self.env[MRequestModel].sudo().search_count([("device_id", "=", rec.id)])
            else:
                rec.maintenance_request_count = 0

    # --------------------------
    # ORM Overrides
    # --------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        - Isi code via sequence 'clinic.device.code' jika kosong.
        - Normalisasi serial_no (strip).
        - Validasi angka agar user error friendly (meski ada SQL CHECK).
        """
        seq_ref = self.env.ref("clinic_room_device.seq_clinic_device", raise_if_not_found=False)
        for vals in vals_list:
            if not vals.get("code") and seq_ref:
                vals["code"] = self.env["ir.sequence"].next_by_code("clinic.device.code") or False
            if vals.get("serial_no"):
                vals["serial_no"] = (vals["serial_no"] or "").strip()
            # user-friendly validations
            if vals.get("maintenance_interval_days", 0) < 0:
                raise ValidationError(_("Maintenance interval tidak boleh negatif."))
            if vals.get("calibration_interval_days", 0) < 0:
                raise ValidationError(_("Calibration interval tidak boleh negatif."))
            if vals.get("warranty_months", 0) < 0:
                raise ValidationError(_("Warranty (months) tidak boleh negatif."))
        return super().create(vals_list)

    def write(self, vals):
        if "serial_no" in vals and vals["serial_no"]:
            vals["serial_no"] = (vals["serial_no"] or "").strip()
        for k in ("maintenance_interval_days", "calibration_interval_days", "warranty_months"):
            if k in vals and vals[k] is not None and vals[k] < 0:
                raise ValidationError(_("%s tidak boleh negatif.") % k)
        return super().write(vals)

    # --------------------------
    # Onchange
    # --------------------------
    @api.onchange("category_id")
    def _onchange_category_id(self):
        """
        Contoh heuristik: jika kategori punya interval default,
        ambil sebagai default perangkat baru.
        """
        if self.category_id:
            fields_map = {
                "default_maintenance_interval_days": "maintenance_interval_days",
                "default_calibration_interval_days": "calibration_interval_days",
            }
            for cat_field, dev_field in fields_map.items():
                if cat_field in self.category_id._fields:
                    val = getattr(self.category_id, cat_field, 0) or 0
                    if not getattr(self, dev_field):
                        setattr(self, dev_field, val)

    # --------------------------
    # Name helpers
    # --------------------------
    def name_get(self):
        res = []
        for rec in self:
            name = rec.display_name or rec.name or ""
            if rec.serial_no:
                name = "%s (%s)" % (name, rec.serial_no)
            res.append((rec.id, name))
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = domain or []
        search_domain = []
        if name:
            search_domain = ["|", "|",
                      ("code", operator, name),
                      ("name", operator, name),
                      ("serial_no", operator, name)]
        recs = self.search(search_domain + domain, limit=limit)
        return recs.name_get()

    # --------------------------
    # Status Helpers
    # --------------------------
    def set_available(self): self.write({"status": "available"})
    def set_reserved(self): self.write({"status": "reserved"})
    def set_in_use(self): self.write({"status": "in_use"})
    def set_maintenance(self): self.write({"status": "maintenance"})
    def set_offline(self): self.write({"status": "offline"})
    def set_retired(self): self.write({"status": "retired"})

    # --------------------------
    # Smart Buttons / Actions
    # --------------------------
    def action_view_assignments(self):
        self.ensure_one()
        return {
            "name": _("Room Assignments"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room.device.assignment",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "context": {"default_device_id": self.id},
        }

    def action_view_movements(self):
        self.ensure_one()
        return {
            "name": _("Device Movements"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.device.movement",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "context": {"default_device_id": self.id},
        }

    def action_view_maintenance_requests(self):
        self.ensure_one()
        MRequestModel = self._get_maintenance_request_model()
        if not MRequestModel or "device_id" not in self.env[MRequestModel]._fields:
            raise UserError(_("Integrasi Maintenance belum aktif (field device_id tidak ditemukan)."))
        context = {"default_device_id": self.id}
        if "maintenance_team_id" in self.env[MRequestModel]._fields and self.maintenance_team_id:
            context["default_maintenance_team_id"] = self.maintenance_team_id.id
        return {
            "name": _("Maintenance Requests"),
            "type": "ir.actions.act_window",
            "res_model": MRequestModel,
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "context": context,
        }

    def action_request_maintenance(self):
        """Buat 1 maintenance.request untuk perangkat ini (jika modul & field tersedia)."""
        self.ensure_one()
        MRequestModel = self._get_maintenance_request_model()
        if not MRequestModel or "device_id" not in self.env[MRequestModel]._fields:
            raise UserError(_("Integrasi Maintenance belum aktif (field device_id tidak ditemukan)."))

        # Odoo 19 maintenance.request uses `maintenance_team_id` and a Date
        # `request_date`. Build values only for fields actually supplied by the
        # optional device-maintenance bridge; do not activate dormant inherit code.
        request_fields = self.env[MRequestModel]._fields
        vals = {
            "name": _("Maintenance for %s") % (self.display_name or self.name),
            "device_id": self.id,
        }
        if "request_date" in request_fields:
            vals["request_date"] = fields.Date.context_today(self)
        if "maintenance_team_id" in request_fields and self.maintenance_team_id:
            vals["maintenance_team_id"] = self.maintenance_team_id.id
        if "room_id" in request_fields and self.current_room_id:
            vals["room_id"] = self.current_room_id.id

        req = self.env[MRequestModel].sudo().create(vals)
        return {
            "name": _("Maintenance Request"),
            "type": "ir.actions.act_window",
            "res_model": MRequestModel,
            "view_mode": "form",
            "res_id": req.id,
        }

    def action_open_stock_moves(self):
        """
        Opsional: buka stock moves terkait product/lot perangkat ini.
        Aman dipanggil hanya jika modul stock terpasang.
        """
        self.ensure_one()
        if "stock.move.line" not in self.env:
            raise UserError(_("Modul Inventory belum terpasang."))
        domain = []
        if self.product_id:
            domain.append(("product_id", "=", self.product_id.id))
        if self.lot_id and "lot_id" in self.env["stock.move.line"]._fields:
            domain.append(("lot_id", "=", self.lot_id.id))
        if not domain:
            raise UserError(_("Tidak ada product/lot yang terhubung untuk ditampilkan."))
        return {
            "name": _("Stock Move Lines"),
            "type": "ir.actions.act_window",
            "res_model": "stock.move.line",
            "view_mode": "list,form",
            "domain": domain,
        }
