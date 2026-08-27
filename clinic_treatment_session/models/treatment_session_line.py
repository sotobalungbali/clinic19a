# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicTreatmentSessionLine(models.Model):
    """
    Detail/line model for ClinicOne treatment sessions.

    Satu record merepresentasikan satu langkah, item, atau bahan yang
    dipakai di dalam satu sesi treatment (clinic.treatment.session).
    Dirancang agar bisa menjadi titik integrasi untuk:
      - Inventory (stock.move)
      - Billing (clinic.billing, account.move)
      - Package & Membership (clinic.package, clinic.membership)
      - Wallet / Voucher (clinic.wallet)
      - Referral dan modul-modul lain di ClinicOne.
    """
    _name = "clinic.treatment.session.line"
    _description = "Clinic Treatment Session Line"
    _order = "session_id, sequence, id"
    _rec_name = "display_name"

    # ---------------------------------------------------------------------
    # Relational Context (Session, Company, Patient, Doctor, Treatment)
    # ---------------------------------------------------------------------
    session_id = fields.Many2one(
        "clinic.treatment.session",
        string="Session",
        required=True,
        ondelete="cascade",
        index=True,
        help="Parent treatment session.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="session_id.company_id",
        store=True,
        readonly=True,
    )

    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="session_id.patient_id",
        store=True,
        readonly=True,
    )

    clinic_doctor_id = fields.Many2one(
        "hr.employee",
        string="Doctor / Therapist",
        related="session_id.clinic_doctor_id",
        store=True,
        readonly=True,
    )

    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="session_id.treatment_id",
        store=True,
        readonly=True,
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order of this line within the session.",
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )

    display_type = fields.Selection(
        [
            ("line", "Normal Line"),
            ("section", "Section"),
            ("note", "Note"),
        ],
        string="Display Type",
        default="line",
        help=(
            "Technical field for UX: sections and notes are non-billable "
            "and do not affect stock."
        ),
    )

    usage_type = fields.Selection(
        [
            ("service", "Service / Procedure Step"),
            ("consumable", "Consumable / Material"),
            ("medication", "Medication"),
            ("package", "Package Component"),
            ("note", "Note / Documentation"),
        ],
        string="Usage Type",
        default="service",
        required=True,
        help="Classify this line within the session workflow.",
    )

    name = fields.Char(
        string="Description",
        help="Short description or label for this line. Defaults from product.",
    )

    # ---------------------------------------------------------------------
    # Product & Quantities
    # ---------------------------------------------------------------------
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain=[("sale_ok", "=", True)],
        help="Product representing this service step, consumable, or medication.",
    )

    product_type = fields.Selection(
        related="product_id.type",
        string="Product Type",
        readonly=True,
    )

    # NOTE: domain per category dihapus karena Odoo 19 tidak lagi punya
    # uom.uom.category_id seperti versi sebelumnya. Kita biarkan UoM bebas.
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Unit of measure for the quantity on this line.",
    )

    quantity = fields.Float(
        string="Planned Quantity",
        default=1.0,
        digits="Product Unit of Measure",
        help="Planned quantity for this step or consumable.",
    )

    consumed_qty = fields.Float(
        string="Consumed Quantity",
        default=0.0,
        digits="Product Unit of Measure",
        help="Actual quantity consumed (for inventory & costing).",
    )

    is_billable = fields.Boolean(
        string="Billable",
        default=True,
        help=(
            "If unchecked, this line will not be included in billing payload "
            "even when the session is billed."
        ),
    )

    # ---------------------------------------------------------------------
    # Pricing & Taxes (Billing Integration)
    # ---------------------------------------------------------------------
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        help="Unit price for billing. Defaults from product sale price.",
    )

    discount = fields.Float(
        string="Discount (%)",
        digits="Discount",
        help="Discount percentage applied at line level.",
    )

    tax_ids = fields.Many2many(
        "account.tax",
        "clinic_session_line_tax_rel",
        "line_id",
        "tax_id",
        string="Taxes",
        help="Taxes to apply when this line is invoiced.",
    )

    price_subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    price_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    # ---------------------------------------------------------------------
    # Consumption / Stock Integration
    # ---------------------------------------------------------------------
    consumption_state = fields.Selection(
        [
            ("planned", "Planned"),
            ("ready", "Ready"),
            ("consumed", "Consumed"),
            ("cancelled", "Cancelled"),
        ],
        string="Consumption Status",
        default="planned",
        help="Track whether the material/step was actually performed or consumed.",
    )

    date_consumed = fields.Datetime(
        string="Date Consumed",
        help="Timestamp when the consumable was actually used.",
    )

    is_stock_relevant = fields.Boolean(
        string="Stock Relevant",
        compute="_compute_is_stock_relevant",
        store=True,
        help=(
            "Indicates that this line should affect stock (product type product/consu "
            "and quantity > 0)."
        ),
    )

    stock_move_id = fields.Many2one(
        "stock.move",
        string="Stock Move",
        readonly=True,
        help="Stock move created when this line is marked as consumed.",
    )

    location_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        help=(
            "Source location for stock consumption. If not set, default locations "
            "from configuration will be used."
        ),
    )

    location_dest_id = fields.Many2one(
        "stock.location",
        string="Destination Location",
        help=(
            "Destination location for stock consumption, usually a consumption "
            "or scrap location."
        ),
    )

    note_internal = fields.Text(
        string="Internal Notes",
        help="Internal notes related specifically to this step or item.",
    )

    # ---------------------------------------------------------------------
    # Cross-Module Linkage (Packages, Membership, Wallet, Referral, dll)
    # ---------------------------------------------------------------------
    package_line_id = fields.Many2one(
        "clinic.package.line",
        string="Package Line",
        help=(
            "Link to a Clinic Package line that covers this item. "
            "Addon clinic_package can use this to decrement balances."
        ),
    )

    # clinic.membership.benefit >>> lama
    # membership.plan.benefit >>> baru, aman
    # membership_benefit_id = fields.Many2one(
    #     "membership.plan.benefit",
    #     string="Membership Benefit",
    #     help=(
    #         "If this line is covered by a membership benefit, link it here for "
    #         "tracking and reporting."
    #     ),
    # )

    # wallet_voucher_line_id = fields.Many2one(
    #     "clinic.wallet.voucher.line",
    #     string="Wallet Voucher Line",
    #     help="If this line is paid via clinic wallet, reference the voucher line.",
    # )

    referral_id = fields.Many2one(
        "clinic.referral",
        string="Referral",
        help="Optional linkage to referral that generated this line.",
    )

    _quantity_nonnegative = models.Constraint(
        "CHECK(quantity >= 0)",
        "Planned quantity must be non-negative.",
    )
    _consumed_quantity_nonnegative = models.Constraint(
        "CHECK(consumed_qty >= 0)",
        "Consumed quantity must be non-negative.",
    )

    # ---------------------------------------------------------------------
    # COMPUTE METHODS
    # ---------------------------------------------------------------------
    @api.depends("product_id", "name", "session_id", "quantity", "product_uom_id")
    def _compute_display_name(self):
        """
        Build human-friendly display name:
          <SessionName> - <Product/Name> (Qty)
        """
        for line in self:
            session_label = line.session_id.name or _("No Session")
            label = line.name or line.product_id.display_name or _("Unnamed Line")
            qty_part = ""
            if line.quantity:
                qty_part = " (%.2f %s)" % (
                    line.quantity,
                    line.product_uom_id.display_name
                    if line.product_uom_id
                    else "",
                )
            line.display_name = "%s - %s%s" % (session_label, label, qty_part)

    @api.depends("product_id", "quantity")
    def _compute_is_stock_relevant(self):
        """
        A line is stock relevant if:
          - Has product_id
          - Product type in ('product', 'consu')
          - Quantity > 0
        """
        for line in self:
            line.is_stock_relevant = bool(
                line.product_id
                and line.product_id.type in ("product", "consu")
                and line.quantity > 0
            )

    @api.depends(
        "quantity",
        "price_unit",
        "discount",
        "tax_ids",
        "currency_id",
        "company_id",
        "session_id.patient_id",
    )
    def _compute_amounts(self):
        """
        Compute price_subtotal & price_total using taxes when Accounting is available.
        Jika account.tax / modul Accounting belum terpasang, fallback ke perhitungan
        sederhana:
            subtotal = qty * price * (1 - disc%)
            total = subtotal
        """
        tax_model_available = "account.tax" in self.env and hasattr(
            self.env["account.tax"], "compute_all"
        )

        for line in self:
            qty = line.quantity or 0.0
            price = line.price_unit or 0.0
            discount = (line.discount or 0.0) / 100.0
            price_after_disc = price * (1.0 - discount)
            subtotal = qty * price_after_disc
            total = subtotal

            if tax_model_available and line.tax_ids:
                partner = line.session_id.patient_id
                taxes_res = line.tax_ids.compute_all(
                    price_after_disc,
                    line.currency_id,
                    qty,
                    product=line.product_id,
                    partner=partner,
                )
                subtotal = taxes_res.get("total_excluded", subtotal)
                total = taxes_res.get("total_included", total)

            line.price_subtotal = subtotal
            line.price_total = total

    # ---------------------------------------------------------------------
    # CONSTRAINTS
    # ---------------------------------------------------------------------
    @api.constrains("usage_type", "display_type", "product_id")
    def _check_product_required(self):
        """
        Untuk line dengan usage_type bukan 'note' dan display_type 'line',
        product_id sebaiknya diisi (untuk billing & inventory). Section/note
        boleh tanpa product.
        """
        for line in self:
            if (
                line.display_type == "line"
                and line.usage_type in ("service", "consumable", "medication", "package")
                and not line.product_id
            ):
                raise ValidationError(
                    _(
                        "Product is required for line '%s' (usage type: %s) "
                        "because it is billable or stock relevant."
                    )
                    % (line.display_name or line.name or "", line.usage_type)
                )

    @api.constrains("consumed_qty", "quantity")
    def _check_consumed_not_exceed_quantity(self):
        for line in self:
            if line.consumed_qty and line.quantity and line.consumed_qty > line.quantity:
                raise ValidationError(
                    _(
                        "Consumed quantity (%.2f) cannot exceed planned quantity (%.2f) "
                        "for line %s."
                    )
                    % (
                        line.consumed_qty,
                        line.quantity,
                        line.display_name or line.name or "",
                    )
                )

    # ---------------------------------------------------------------------
    # ONCHANGE HELPERS
    # ---------------------------------------------------------------------
    @api.onchange("product_id")
    def _onchange_product_id(self):
        """
        Set default UoM, description, price, and taxes from product when selected.
        """
        for line in self:
            if not line.product_id:
                continue
            product = line.product_id
            if not line.name:
                line.name = product.display_name
            line.product_uom_id = product.uom_id
            # Default price dari harga jual product.
            line.price_unit = product.lst_price or getattr(product, "list_price", 0.0)
            # Default taxes dari product atau category jika modul Accounting tersedia.
            if "account.tax" in self.env:
                line.tax_ids = (
                    product.taxes_id
                    or getattr(product.categ_id, "account_tax_ids", False)
                    or self.env["account.tax"]
                )

    @api.onchange("usage_type", "display_type")
    def _onchange_usage_type_display_type(self):
        """
        Jika display_type bukan 'line', paksa non-billable dan non-stock.
        """
        for line in self:
            if line.display_type in ("section", "note") or line.usage_type == "note":
                line.is_billable = False
                line.is_stock_relevant = False
                line.tax_ids = False

    # ---------------------------------------------------------------------
    # STOCK / CONSUMPTION ACTIONS
    # ---------------------------------------------------------------------
    def _get_default_consumption_locations(self):
        """
        Ambil lokasi default dari konfigurasi ir.config_parameter:

          clinic_treatment_session.location_src_id
          clinic_treatment_session.location_dest_id

        Jika tidak di-set, return (False, False) dan konsumsi hanya akan
        meng-update status tanpa membuat stock.move. Modul Inventory ClinicOne
        bisa override method ini untuk logika yang lebih spesifik.
        """
        Param = self.env["ir.config_parameter"].sudo()
        src_id_str = Param.get_param(
            "clinic_treatment_session.location_src_id", default=""
        )
        dest_id_str = Param.get_param(
            "clinic_treatment_session.location_dest_id", default=""
        )

        def to_int(value):
            try:
                return int(value)
            except Exception:
                return False

        src = to_int(src_id_str)
        dest = to_int(dest_id_str)

        src_loc = (
            self.env["stock.location"].browse(src)
            if src and "stock.location" in self.env
            else self.env["stock.location"]
        )
        dest_loc = (
            self.env["stock.location"].browse(dest)
            if dest and "stock.location" in self.env
            else self.env["stock.location"]
        )
        return src_loc, dest_loc

    def action_mark_ready(self):
        """
        Transition consumption_state to READY.
        Tidak membuat stock move; hanya status operasional.
        """
        for line in self:
            if line.consumption_state in ("consumed", "cancelled"):
                continue
            line.consumption_state = "ready"
        return True

    def action_mark_consumed(self):
        """
        Tandai line sebagai CONSUMED.

        Jika:
          - is_stock_relevant = True
          - modul Stock tersedia
          - lokasi src/dest tersedia (baik dari field maupun config)
        maka akan dibuat stock.move untuk mencatat konsumsi.

        Modul Inventory ClinicOne dapat meng-override method ini untuk:
          - mengelompokkan consumption per session
          - menambahkan layer analitik / valuation khusus klinik.
        """
        StockMove = (
            self.env["stock.move"] if "stock.move" in self.env else None
        )

        for line in self:
            if line.consumption_state == "consumed":
                continue

            if not line.quantity:
                # Tidak ada qty, hanya update status.
                line.consumption_state = "consumed"
                line.consumed_qty = 0.0
                line.date_consumed = fields.Datetime.now()
                continue

            # Update consumed quantity bila belum di-set
            if not line.consumed_qty:
                line.consumed_qty = line.quantity

            # Jika tidak stock relevant atau tidak ada product/barang, cukup status.
            if (
                not line.is_stock_relevant
                or not line.product_id
                or line.product_id.type not in ("product", "consu")
                or not StockMove
            ):
                line.consumption_state = "consumed"
                line.date_consumed = fields.Datetime.now()
                continue

            # Tentukan lokasi sumber & tujuan
            src_loc = line.location_id
            dest_loc = line.location_dest_id
            if not src_loc or not dest_loc:
                default_src, default_dest = line._get_default_consumption_locations()
                src_loc = src_loc or default_src
                dest_loc = dest_loc or default_dest

            if not src_loc or not dest_loc:
                # Lokasi belum di-setup; kita tidak paksa stock.move
                line.consumption_state = "consumed"
                line.date_consumed = fields.Datetime.now()
                continue

            # Jika sudah punya stock_move_id, tidak perlu create lagi.
            if not line.stock_move_id:
                move_vals = {
                    "name": line.name or line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.consumed_qty or line.quantity,
                    "product_uom": line.product_uom_id.id
                    or line.product_id.uom_id.id,
                    "location_id": src_loc.id,
                    "location_dest_id": dest_loc.id,
                    "company_id": line.company_id.id,
                    "origin": line.session_id.name,
                    "reference": line.session_id.name,
                }
                move = StockMove.create(move_vals)
                # Confirm & assign immediately if possible.
                if hasattr(move, "action_confirm"):
                    move.action_confirm()
                if hasattr(move, "action_assign"):
                    move.action_assign()
                if hasattr(move, "action_done"):
                    move.action_done()
                line.stock_move_id = move.id

            line.consumption_state = "consumed"
            line.date_consumed = fields.Datetime.now()
        return True

    def action_reset_consumption(self):
        """
        Reset consumption_state ke PLANNED dan reset qty & timestamp.
        Tidak menghapus stock.move yang sudah dibuat, hanya memutus relasi logis.
        Modul inventory bisa override jika perlu membalikkan stock move.
        """
        for line in self:
            line.consumption_state = "planned"
            line.consumed_qty = 0.0
            line.date_consumed = False
            # Jangan otomatis hapus stock_move_id di sini, supaya aman untuk valuasi.
            # Modul inventory boleh override dengan reversal jika diperlukan.
        return True

    # ---------------------------------------------------------------------
    # BILLING PAYLOAD HELPER
    # ---------------------------------------------------------------------
    def prepare_billing_payload_line(self):
        """
        Helper yang mengembalikan struktur dict untuk satu baris billing.

        Dipakai oleh clinic.treatment.session.action_prepare_billing()
        atau dapat dipanggil langsung oleh modul billing lain.

        Struktur return:
          {
            'session_line_id': self.id,
            'product_id': product_id,
            'qty': quantity,
            'price_unit': price_unit,
            'name': description,
            'discount': discount,
            'tax_ids': [ids],
          }
        """
        self.ensure_one()
        if (
            self.display_type != "line"
            or self.usage_type == "note"
            or not self.is_billable
        ):
            return {}

        if not self.product_id:
            # Secara normal sudah dicegah oleh constraint,
            # tapi kita tetap aman di sini.
            return {}

        return {
            "session_line_id": self.id,
            "product_id": self.product_id.id,
            "qty": self.quantity or 1.0,
            "price_unit": self.price_unit or 0.0,
            "name": self.name or self.product_id.display_name,
            "discount": self.discount or 0.0,
            "tax_ids": self.tax_ids.ids if self.tax_ids else [],
        }
