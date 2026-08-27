# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/procedure_catalog.py
#
# Fungsi:
# - Master katalog prosedur klinis (harga, durasi, pajak, jumlah sesi).
# - Mapping ke product.product untuk pricing & pajak (opsional).
# - Consumables (bahan/alat) default per prosedur (opsional).
# - Billing policy default (per_plan/per_session/no_bill) yang diturunkan ke rencana prosedur.
# - Integrasi “soft-coupled” dengan Encounter → Procedure Plan → Session.
#
# Catatan:
# - Tidak memaksa dependensi ke modul room/device/stock lanjutan; hanya menyediakan hook/field umum.
# - actions helper untuk melihat rencana/sesi terkait prosedur ini.
#
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# -----------------------------------------------------------------------------
# Tag & Kategori Prosedur (opsional untuk pelabelan & pelaporan)
# -----------------------------------------------------------------------------
class ClinicProcedureTag(models.Model):
    _name = "clinic.procedure.tag"
    _description = "Procedure Tag"
    _order = "name"

    name = fields.Char(required=True, translate=True, index=True)
    color = fields.Integer(string="Color Index")
    active = fields.Boolean(default=True)
    description = fields.Text()


class ClinicProcedureCategory(models.Model):
    _name = "clinic.procedure.category"
    _description = "Procedure Category"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(index=True, help="Optional code for external mapping.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    parent_id = fields.Many2one("clinic.procedure.category", string="Parent", index=True)
    child_ids = fields.One2many("clinic.procedure.category", "parent_id", string="Children")
    description = fields.Text()


# -----------------------------------------------------------------------------
# Master Katalog Prosedur
# -----------------------------------------------------------------------------
class ClinicProcedureCatalog(models.Model):
    _name = "clinic.procedure.catalog"
    _description = "Procedure Catalog"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Perusahaan
    # -------------------------------------------------------------------------
    name = fields.Char(required=True, translate=True, tracking=True, index=True)
    code = fields.Char(
        string="Procedure Code",
        copy=False,
        index=True,
        help="Internal/External code. If empty, will be filled by sequence.",
    )
    display_name = fields.Char(string="Display", compute="_compute_display_name", store=True)
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Kategori & Tag
    # -------------------------------------------------------------------------
    category_id = fields.Many2one("clinic.procedure.category", string="Category", ondelete="set null", index=True)
    tag_ids = fields.Many2many("clinic.procedure.tag", string="Tags")

    # -------------------------------------------------------------------------
    # Mapping ke Produk & Satuan
    # -------------------------------------------------------------------------
    product_id = fields.Many2one(
        "product.product",
        string="Product (Pricing)",
        help="Mapped product/service for pricing and taxation. Optional but recommended.",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Default UoM for billing/quantity on procedure plan.",
    )

    # -------------------------------------------------------------------------
    # Pricing & Pajak
    # -------------------------------------------------------------------------
    list_price = fields.Monetary(
        string="List Price",
        help="Default unit price used on encounter procedure line. If product is set, initialized from product.",
        currency_field="currency_id",
        tracking=True,
    )
    standard_price = fields.Monetary(
        string="Cost",
        help="Optional internal cost reference (not used in billing).",
        currency_field="currency_id",
    )
    tax_ids = fields.Many2many(
        "account.tax",
        "clinic_proc_catalog_tax_rel",
        "catalog_id",
        "tax_id",
        string="Customer Taxes",
        domain=[("type_tax_use", "in", ["sale", "none"])],
        help="Default taxes applied for patient/customer billing.",
    )
    billing_policy = fields.Selection(
        [
            ("per_plan", "Bill per Plan Line"),
            ("per_session", "Bill per Session"),
            ("no_bill", "Do Not Bill"),
        ],
        string="Default Billing Policy",
        default="per_plan",
        help="Default policy propagated to encounter procedure lines.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Waktu & Sesi Default
    # -------------------------------------------------------------------------
    default_duration_min = fields.Float(
        string="Default Duration (min)",
        help="Estimated duration per session (minutes).",
    )
    default_sessions = fields.Integer(
        string="Default Sessions",
        default=1,
        help="How many sessions are typically planned for this procedure.",
    )

    # -------------------------------------------------------------------------
    # Kebijakan Klinis
    # -------------------------------------------------------------------------
    require_consent = fields.Boolean(
        string="Require Consent",
        help="If enabled, encounter stage may enforce consent before execution.",
        tracking=True,
    )
    require_checklist = fields.Boolean(
        string="Require Checklist",
        help="If enabled, a pre/post checklist is expected during session.",
    )
    instructions_pre = fields.Html(string="Pre-Procedure Instructions")
    instructions_post = fields.Html(string="Post-Procedure Instructions")
    risks = fields.Html(string="Risks / Adverse Events (Info)")

    # -------------------------------------------------------------------------
    # Consumables (Bahan/Alat) Default
    # -------------------------------------------------------------------------
    consumable_ids = fields.One2many(
        "clinic.procedure.consumable",
        "procedure_id",
        string="Default Consumables",
        help="Default materials/equipment consumed during the procedure (for inventory bridge).",
    )

    # -------------------------------------------------------------------------
    # Relasi ke Langkah (Step) — didefinisikan di models/procedure_step.py
    # -------------------------------------------------------------------------
    step_ids = fields.One2many(
        "clinic.procedure.step",
        "procedure_id",
        string="Steps",
        help="Structured steps of this procedure.",
    )

    # -------------------------------------------------------------------------
    # Analitik & Penggunaan
    # -------------------------------------------------------------------------
    plan_count = fields.Integer(string="Procedure Plans", compute="_compute_usage_counters", store=False)
    session_count = fields.Integer(string="Sessions", compute="_compute_usage_counters", store=False)

    color = fields.Integer(string="Color Index")
    note = fields.Text(string="Internal Note")

    # -------------------------------------------------------------------------
    # Komputasi
    # -------------------------------------------------------------------------
    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "[%s] %s" % (rec.code, rec.name) if rec.code else (rec.name or "")

    def _compute_usage_counters(self):
        Plan = self.env["clinic.encounter.procedure"]
        Session = self.env["clinic.procedure.session"]
        for rec in self:
            rec.plan_count = Plan.search_count([("procedure_id", "=", rec.id)])
            rec.session_count = Session.search_count([("procedure_id", "=", rec.id)]) if "procedure_id" in Session._fields else 0

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    @api.onchange("product_id")
    def _onchange_product_id(self):
        """Prefill UoM, List Price, Cost, Taxes from product."""
        prod = self.product_id
        if not prod:
            return
        vals = {}
        if prod.uom_id:
            vals["uom_id"] = prod.uom_id.id
        # Harga
        vals["list_price"] = prod.lst_price
        if "standard_price" in prod._fields and prod.standard_price is not False:
            vals["standard_price"] = prod.standard_price
        # Pajak customer
        if prod.taxes_id:
            vals["tax_ids"] = [(6, 0, prod.taxes_id.ids)]
        self.update(vals)

    # -------------------------------------------------------------------------
    # Constraint
    # -------------------------------------------------------------------------
    _constraint_uniq_code_company = models.Constraint(
        'unique(code, company_id)',
        'Procedure Code must be unique per company.',
    )
    _constraint_check_default_sessions = models.Constraint(
        'CHECK (default_sessions >= 0)',
        'Default Sessions must be positive or zero.',
    )
    _constraint_check_duration = models.Constraint(
        'CHECK (default_duration_min >= 0)',
        'Duration must be positive or zero.',
    )

    @api.constrains("uom_id", "product_id")
    def _check_uom_category(self):
        for rec in self:
            if rec.product_id and rec.uom_id and rec.product_id.uom_id.category_id != rec.uom_id.category_id:
                raise ValidationError(_("The selected Unit of Measure is not compatible with the product's UoM."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            # Isi code dari sequence bila kosong
            if not vals.get("code"):
                vals["code"] = seq.next_by_code("clinic.procedure.catalog") or False
            # Prefill list_price/tax dari product jika belum ada
            if vals.get("product_id"):
                prod = self.env["product.product"].browse(vals["product_id"])
                vals.setdefault("uom_id", prod.uom_id.id)
                vals.setdefault("list_price", prod.lst_price)
                if "standard_price" in prod._fields:
                    vals.setdefault("standard_price", prod.standard_price)
                if prod.taxes_id and not vals.get("tax_ids"):
                    vals["tax_ids"] = [(6, 0, prod.taxes_id.ids)]
        recs = super().create(vals_list)
        # Jadwalkan aktivitas ringan untuk melengkapi langkah/consumables (opsional)
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Complete procedure steps/consumables"),
                    user_id=self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        # Bila product diganti dan uom belum diset di vals, sinkronkan uom & pajak default
        if "product_id" in vals:
            prod = self.env["product.product"].browse(vals["product_id"]) if vals.get("product_id") else False
            if prod:
                vals.setdefault("uom_id", prod.uom_id.id)
                vals.setdefault("list_price", prod.lst_price)
                if "standard_price" in prod._fields:
                    vals.setdefault("standard_price", prod.standard_price)
                if prod.taxes_id and "tax_ids" not in vals:
                    vals["tax_ids"] = [(6, 0, prod.taxes_id.ids)]
        return super().write(vals)

    # -------------------------------------------------------------------------
    # Helper untuk Encounter → Procedure Plan
    # -------------------------------------------------------------------------
    def prepare_plan_vals(self, encounter, quantity=1.0, diagnosis=None, price_unit=None, uom=None):
        """
        Siapkan vals untuk pembuatan record clinic.encounter.procedure dari katalog ini.
        - encounter: record clinic.encounter
        - quantity: default 1.0 (atau sesuai kebutuhan)
        - diagnosis: optional clinic.diagnosis
        - price_unit: override harga (jika None → pakai list_price)
        - uom: override uom (jika None → pakai uom_id / product.uom_id)
        """
        self.ensure_one()
        if not encounter:
            raise UserError(_("Encounter is required to prepare a procedure plan."))
        if quantity is None:
            quantity = 1.0

        # Tentukan UoM dan pajak default
        uom_id = uom.id if getattr(uom, "id", False) else (self.uom_id.id or (self.product_id.uom_id.id if self.product_id else False))
        taxes = self.tax_ids
        partner = encounter.partner_id
        # Map tax via fiscal position partner (jika ada)
        if partner and partner.property_account_position_id:
            taxes = partner.property_account_position_id.map_tax(taxes, product=self.product_id, partner=partner)

        vals = {
            "encounter_id": encounter.id,
            "diagnosis_id": diagnosis.id if diagnosis else False,
            "procedure_id": self.id,
            "product_id": self.product_id.id if self.product_id else False,
            "uom_id": uom_id,
            "quantity": quantity,
            "planned_sessions": (self.default_sessions or 1),
            "planned_duration": (self.default_duration_min or 0.0),
            "price_unit": price_unit if price_unit is not None else (self.list_price or 0.0),
            "discount": 0.0,
            "tax_ids": [(6, 0, taxes.ids)] if taxes else [],
            "billing_policy": self.billing_policy or "per_plan",
        }
        return vals

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_open_related_plans(self):
        """Lihat semua rencana prosedur (clinic.encounter.procedure) yang memakai katalog ini."""
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter_procedure").read()[0]
        action["domain"] = [("procedure_id", "=", self.id)]
        return action

    def action_open_related_sessions(self):
        """Lihat semua sesi tindakan (clinic.procedure.session) yang memakai katalog ini (jika field tersedia)."""
        self.ensure_one()
        Session = self.env["clinic.procedure.session"]
        if "procedure_id" not in Session._fields:
            raise UserError(_("Session model doesn't link to procedure catalog in this configuration."))
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["domain"] = [("procedure_id", "=", self.id)]
        return action

    def action_quick_plan_for_encounter(self):
        """
        Buka action rencana prosedur dengan context default terisi dari katalog ini.
        Dipakai dari smart button 'Plan in Encounter'.
        """
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter_procedure").read()[0]
        ctx = {
            "default_procedure_id": self.id,
            "default_product_id": self.product_id.id if self.product_id else False,
            "default_uom_id": self.uom_id.id if self.uom_id else (self.product_id.uom_id.id if self.product_id else False),
            "default_price_unit": self.list_price or 0.0,
            "default_planned_sessions": (self.default_sessions or 1),
            "default_planned_duration": (self.default_duration_min or 0.0),
            "default_billing_policy": self.billing_policy or "per_plan",
        }
        action["context"] = ctx
        return action

    # -------------------------------------------------------------------------
    # Name & Search
    # -------------------------------------------------------------------------

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", ("name", operator, name), ("code", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# -----------------------------------------------------------------------------
# Child: Default Consumables for a Procedure
# -----------------------------------------------------------------------------
class ClinicProcedureConsumable(models.Model):
    _name = "clinic.procedure.consumable"
    _description = "Procedure Consumable"
    _order = "sequence, id"
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="procedure_id.company_id",
        store=True,
        readonly=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="restrict",
        index=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="If empty, the product's UoM will be used.",
    )
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        digits="Product Unit of Measure",
        help="Default quantity to be consumed per session (or per plan, depending on implementation).",
    )
    auto_issue = fields.Boolean(
        string="Auto Issue",
        default=True,
        help="If enabled, stock can be auto-issued when the session starts/finishes (inventory bridge needed).",
    )
    required = fields.Boolean(
        string="Required",
        default=True,
        help="If enabled, this consumable is required (session may warn if not available).",
    )
    notes = fields.Char(string="Notes")

    # Visual
    color = fields.Integer(string="Color Index")

    # Onchange
    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id and not self.uom_id:
            self.uom_id = self.product_id.uom_id

    # Constraints
    _constraint_check_qty = models.Constraint(
        'CHECK (quantity >= 0)',
        'Quantity must be positive or zero.',
    )

    @api.constrains("uom_id", "product_id")
    def _check_uom_category(self):
        for rec in self:
            if rec.product_id and rec.uom_id and rec.product_id.uom_id.category_id != rec.uom_id.category_id:
                raise ValidationError(_("The selected Unit of Measure is not compatible with the product's UoM."))
