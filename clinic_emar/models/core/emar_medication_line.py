# -*- coding: utf-8 -*-
"""ClinicOne eMAR - Core: Medication Line.

Odoo 19 models UoM compatibility through ``uom.uom.relative_uom_id``.
Inventory quantity UoMs on medication lines therefore share the same root
reference UoM as the product.  Clinical dose UoMs remain independent because
a 500 mg dose may legitimately be administered from a tablet/unit product.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


def _has(model, field_name):
    return hasattr(model, "_fields") and field_name in model._fields


class ClinicEmarMedicationLine(models.Model):
    _name = "clinic.emar.medication.line"
    _description = "eMAR Medication Line"
    _order = "sequence, id"
    _check_company_auto = True
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.emar.mixin.audit"]

    # -------------------------------------------------------------------------
    # BASIC INFO
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Medication/Instruction",
        help="Free-text medication or instruction label displayed to users.",
        tracking=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Line order for display and scheduling.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Unchecked to hide this line without deleting it.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
        required=True,
    )

    # -------------------------------------------------------------------------
    # HEADERS
    # -------------------------------------------------------------------------
    order_id = fields.Many2one(
        "clinic.emar.order",
        string="Order",
        index=True,
        ondelete="cascade",
        help="Execution order this line belongs to.",
        tracking=True,
    )
    prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="Prescription",
        index=True,
        ondelete="set null",
        help="Prescription that originated this line.",
        tracking=True,
    )

    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        index=True,
        help="Patient resolved from order/prescription.",
        tracking=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        help="Doctor who prescribed/approved this medication line.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # PRODUCT & UoM (ODOO 19)
    # -------------------------------------------------------------------------
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        index=True,
        ondelete="restrict",
        required=True,
        help="Medication product (drug/consumable) for this line.",
        tracking=True,
    )

    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        ondelete="restrict",
        help="Unit of measure for 'Quantity'. Use compatible unit with the product.",
        tracking=True,
        required=True,
    )

    # Root reference UoM from the Odoo 19 relative_uom_id hierarchy
    uom_reference_id = fields.Many2one(
        "uom.uom",
        string="Reference UoM",
        compute="_compute_uom_reference",
        store=True,
        readonly=True,
        help="Root reference UoM for the product inventory-unit hierarchy.",
    )

    # List UoM kompatibel untuk domain di view: [('id','in',available_uom_ids)]
    available_uom_ids = fields.Many2many(
        "uom.uom",
        string="Available UoMs",
        compute="_compute_available_uoms",
        help="Reference unit and relative units compatible with the product inventory UoM.",
    )

    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        help="Planned quantity to be dispensed/administrated per schedule.",
        tracking=True,
    )

    # Optional clinical dose (terpisah dari inventory UoM)
    dose = fields.Float(
        string="Dose",
        help="Clinical dose amount (e.g., 500).",
        tracking=True,
    )
    dose_uom_id = fields.Many2one(
        "uom.uom",
        string="Dose Unit",
        ondelete="restrict",
        help="Clinical dose unit (e.g., mg, ml). Not tied to inventory UoM.",
        tracking=True,
    )

    instructions = fields.Text(
        string="Instructions (SIG)",
        help="Clinical instructions for administration (e.g., take after meal).",
        tracking=True,
    )

    is_prn = fields.Boolean(
        string="PRN (As Needed)",
        help="True if this medication should be given as needed.",
        tracking=True,
    )
    is_substitutable = fields.Boolean(
        string="Allow Substitution",
        default=True,
        help="Allow equivalent substitution if original drug is unavailable.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # UOM HELPERS & COMPUTES (ODOO 19)
    # -------------------------------------------------------------------------
    @api.model
    def _uom_root(self, uom):
        """Return the root reference UoM of an Odoo 19 UoM hierarchy.

        ``relative_uom_id`` is Odoo 19's parent relation.  The loop is
        deliberately defensive so corrupted/custom hierarchies cannot create
        an infinite traversal during validation.
        """
        current = uom
        seen = set()
        while current and current.id and current.relative_uom_id:
            if current.id in seen:
                break
            seen.add(current.id)
            current = current.relative_uom_id
        return current

    @api.depends(
        "product_id",
        "product_id.uom_id",
        "product_id.uom_id.relative_uom_id",
        "product_uom_id",
        "product_uom_id.relative_uom_id",
    )
    def _compute_uom_reference(self):
        """Normalize the inventory UoM to its Odoo 19 root reference UoM."""
        for rec in self:
            candidate = rec.product_uom_id or (rec.product_id.uom_id if rec.product_id else False)
            rec.uom_reference_id = rec._uom_root(candidate) if candidate else False

    @api.depends("uom_reference_id")
    def _compute_available_uoms(self):
        """Expose the reference unit plus all relative units beneath it."""
        Uom = self.env["uom.uom"]
        for rec in self:
            if not rec.uom_reference_id:
                rec.available_uom_ids = Uom.browse()
                continue
            rec.available_uom_ids = Uom.search(
                [("id", "child_of", rec.uom_reference_id.id)]
            )

    # -------------------------------------------------------------------------
    # ONCHANGES
    # -------------------------------------------------------------------------
    @api.onchange("product_id")
    def _onchange_product_id_set_defaults(self):
        for rec in self:
            if rec.product_id:
                if not rec.name:
                    rec.name = rec.product_id.display_name
                if rec.product_id.uom_id:
                    rec.product_uom_id = rec.product_id.uom_id

    @api.onchange("order_id", "prescription_id")
    def _onchange_header_context_fill(self):
        """Populate canonical ClinicOne clinical identities from the header.

        ``clinic.emar.order`` deliberately keeps ``patient_id`` as ``res.partner``
        and ``doctor_id`` as ``hr.employee`` for downstream compatibility.  Never
        copy those raw IDs into ``clinic.patient`` / ``clinic.doctor`` fields.
        """
        for rec in self:
            order = rec.order_id
            rx = rec.prescription_id
            if order:
                rec.patient_id = order.clinic_patient_id
                rec.doctor_id = order.clinic_doctor_id
                rec.company_id = order.company_id
            elif rx:
                rec.patient_id = rx.patient_id
                rec.doctor_id = rx.doctor_id
                rec.company_id = rx.company_id

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("company_id", "order_id", "prescription_id")
    def _check_company_alignment(self):
        for rec in self:
            for obj in (rec.order_id, rec.prescription_id):
                if obj and _has(obj, "company_id") and obj.company_id and obj.company_id != rec.company_id:
                    raise ValidationError(_("Company mismatch between the Medication Line and its header."))

    @api.constrains("product_id", "product_uom_id")
    def _check_uom_compatibility(self):
        """Require inventory quantity UoM to share the product's root UoM."""
        for rec in self:
            if not rec.product_id or not rec.product_uom_id or not rec.product_id.uom_id:
                continue
            product_root = rec._uom_root(rec.product_id.uom_id)
            selected_root = rec._uom_root(rec.product_uom_id)
            if not product_root or not selected_root or product_root != selected_root:
                raise ValidationError(
                    _("Selected UoM is not compatible with the product's reference unit.")
                )

    # -------------------------------------------------------------------------
    # MISC
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or rec.product_id.display_name or _("Medication Line")
            if rec.quantity and rec.product_uom_id:
                label = "%s — %s %s" % (label, rec.quantity, rec.product_uom_id.display_name)
            res.append((rec.id, label))
        return res
