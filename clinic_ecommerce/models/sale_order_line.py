from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    """Carry ClinicOne purchase metadata through the native Odoo 19 cart line."""

    _inherit = "sale.order.line"

    clinic_ecommerce_catalog_item_id = fields.Many2one(
        "clinic.ecommerce.catalog.item",
        string="Clinic Catalog Item",
        ondelete="restrict",
        index=True,
        copy=False,
    )
    clinic_ecommerce_branch_id = fields.Many2one(
        "clinic.branch",
        string="Clinic Branch",
        domain="[('company_id', '=', company_id)]",
        copy=False,
    )
    clinic_ecommerce_preferred_date = fields.Date(
        string="Preferred Date",
        copy=False,
    )
    clinic_ecommerce_time_window = fields.Selection(
        [
            ("morning", "Morning"),
            ("afternoon", "Afternoon"),
            ("evening", "Evening"),
            ("flexible", "Flexible"),
        ],
        string="Preferred Time Window",
        copy=False,
    )
    clinic_ecommerce_notes = fields.Text(
        string="Clinic Purchase Notes",
        copy=False,
    )
    clinic_ecommerce_terms_accepted = fields.Boolean(
        string="Clinic Terms Accepted",
        default=False,
        copy=False,
    )
    clinic_ecommerce_terms_accepted_at = fields.Datetime(
        string="Clinic Terms Accepted At",
        readonly=True,
        copy=False,
    )
    clinic_ecommerce_fulfillment_ids = fields.One2many(
        "clinic.ecommerce.fulfillment",
        "sale_order_line_id",
        string="Clinic Fulfillment",
        copy=False,
    )
    clinic_ecommerce_fulfillment_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("waiting_input", "Waiting Input"),
            ("ready", "Ready"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("error", "Error"),
            ("reversal_required", "Reversal Required"),
            ("cancelled", "Cancelled"),
        ],
        compute="_compute_clinic_ecommerce_fulfillment_state",
        string="Clinic Fulfillment Status",
    )

    @api.depends("clinic_ecommerce_fulfillment_ids.state")
    def _compute_clinic_ecommerce_fulfillment_state(self):
        for line in self:
            fulfillment = line.sudo().clinic_ecommerce_fulfillment_ids[:1]
            line.clinic_ecommerce_fulfillment_state = (
                fulfillment.state if fulfillment else False
            )

    @api.constrains(
        "clinic_ecommerce_catalog_item_id",
        "product_id",
        "company_id",
        "clinic_ecommerce_branch_id",
    )
    def _check_clinic_ecommerce_line_contract(self):
        for line in self:
            item = line.clinic_ecommerce_catalog_item_id
            if not item:
                continue
            if item.company_id != line.company_id:
                raise ValidationError(
                    _("Catalog Item and Sales Line company must match.")
                )
            if item.sale_product_id and line.product_id != item.sale_product_id:
                raise ValidationError(
                    _("Sales Line product must match the Catalog Item sale product.")
                )
            if (
                line.clinic_ecommerce_branch_id
                and line.clinic_ecommerce_branch_id.company_id != line.company_id
            ):
                raise ValidationError(
                    _("Sales Line Clinic Branch must belong to its company.")
                )

    def action_open_clinic_fulfillment(self):
        self.ensure_one()
        fulfillment = self.clinic_ecommerce_fulfillment_ids[:1]
        if not fulfillment:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic eCommerce Fulfillment"),
            "res_model": "clinic.ecommerce.fulfillment",
            "view_mode": "form",
            "res_id": fulfillment.id,
        }
