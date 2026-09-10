# -*- coding: utf-8 -*-
"""Medication master metadata used by ClinicOne eMAR.

The product remains owned by Odoo Inventory/Product.  This model stores
clinical medication metadata without overloading product.template.
"""

from odoo import api, fields, models, _


ROUTE_SELECTION = [
    ("oral", "Oral"),
    ("iv", "Intravenous"),
    ("im", "Intramuscular"),
    ("sc", "Subcutaneous"),
    ("topical", "Topical"),
    ("inhaled", "Inhaled"),
    ("ophthalmic", "Ophthalmic"),
    ("otic", "Otic"),
    ("nasal", "Nasal"),
    ("rectal", "Rectal"),
    ("vaginal", "Vaginal"),
    ("other", "Other"),
]

FREQUENCY_SELECTION = [
    ("once", "Once"),
    ("qd", "Once Daily"),
    ("bid", "Twice Daily (BID)"),
    ("tid", "Three Times Daily (TID)"),
    ("qid", "Four Times Daily (QID)"),
    ("q4h", "Every 4 Hours"),
    ("q6h", "Every 6 Hours"),
    ("q8h", "Every 8 Hours"),
    ("q12h", "Every 12 Hours"),
    ("weekly", "Weekly"),
    ("prn", "As Needed (PRN)"),
]


class ClinicEmarMedicationProfile(models.Model):
    _name = "clinic.emar.medication.profile"
    _description = "eMAR Medication Clinical Profile"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.emar.mixin.audit"]
    _order = "name, id"
    _check_company_auto = True

    name = fields.Char(
        string="Medication Name",
        related="product_id.display_name",
        store=True,
        readonly=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Medication Product",
        required=True,
        ondelete="restrict",
        check_company=True,
        index=True,
        tracking=True,
        domain="[('type', '!=', 'service')]",
    )
    medication_code = fields.Char(index=True, tracking=True)
    medication_class = fields.Char(index=True, tracking=True)
    controlled_level = fields.Selection(
        [
            ("none", "Not Controlled"),
            ("controlled", "Controlled"),
            ("high_control", "High-Control / Restricted"),
        ],
        default="none",
        required=True,
        tracking=True,
        index=True,
    )
    high_alert = fields.Boolean(
        string="High-Alert Medication",
        default=False,
        tracking=True,
        help="Requires heightened verification and may require an independent double check.",
    )
    requires_double_check = fields.Boolean(
        default=False,
        tracking=True,
        help="Require an independent second user before administration can be completed.",
    )
    requires_patient_scan = fields.Boolean(
        default=False,
        tracking=True,
        help="Require patient barcode verification when barcode policy is enabled.",
    )
    requires_product_scan = fields.Boolean(
        default=False,
        tracking=True,
        help="Require medication/product barcode verification when barcode policy is enabled.",
    )
    requires_lot = fields.Boolean(
        default=False,
        tracking=True,
        help="Require a lot/serial on the administration even if the product tracking policy is less strict.",
    )
    allow_substitution = fields.Boolean(default=True, tracking=True)

    default_route = fields.Selection(ROUTE_SELECTION, tracking=True)
    default_frequency = fields.Selection(FREQUENCY_SELECTION, tracking=True)
    dose_uom_id = fields.Many2one(
        "uom.uom",
        string="Dose UoM",
        ondelete="restrict",
        tracking=True,
    )
    max_single_dose = fields.Float(
        tracking=True,
        help="Clinical guardrail. Zero means no profile-level single-dose limit.",
    )
    max_daily_dose = fields.Float(
        tracking=True,
        help="Clinical guardrail. Zero means no profile-level daily-dose limit.",
    )
    notes = fields.Html()

    _uniq_product_company = models.Constraint(
        "UNIQUE(product_id, company_id)",
        "Only one eMAR medication profile is allowed per product and company.",
    )
    _nonnegative_dose_limits = models.Constraint(
        "CHECK(max_single_dose >= 0 AND max_daily_dose >= 0)",
        "Medication dose limits cannot be negative.",
    )

    @api.onchange("high_alert")
    def _onchange_high_alert(self):
        for rec in self:
            if rec.high_alert:
                rec.requires_double_check = True

    # ``dose_uom_id`` is intentionally NOT constrained against product.uom_id.
    # Clinical dose units and inventory units represent different dimensions in
    # real medication workflows (for example 500 mg from one tablet).  Inventory
    # UoM compatibility is enforced on clinic.emar.medication.line.product_uom_id.

    def action_open_product(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Medication Product"),
            "res_model": "product.product",
            "view_mode": "form",
            "res_id": self.product_id.id,
            "target": "current",
        }

    def action_view_orders(self):
        self.ensure_one()
        order_ids = self.env["clinic.emar.medication.line"].search(
            [
                ("product_id", "=", self.product_id.id),
                ("order_id", "!=", False),
            ]
        ).mapped("order_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("eMAR Orders"),
            "res_model": "clinic.emar.order",
            "view_mode": "list,form",
            "domain": [("id", "in", order_ids)],
        }

