from odoo import api, fields, models, _


## Source bridges below are provenance/navigation only; none changes owner workflow state semantics.
class BookingBooking(models.Model):
    """eCommerce provenance only; Booking workflow remains owned by clinic_booking."""

    _inherit = "booking.booking"

    clinic_ecommerce_fulfillment_id = fields.Many2one(
        "clinic.ecommerce.fulfillment",
        string="eCommerce Fulfillment",
        ondelete="set null",
        copy=False,
        index=True,
    )
    clinic_ecommerce_sale_order_id = fields.Many2one(
        "sale.order",
        string="eCommerce Sales Order",
        ondelete="set null",
        copy=False,
    )
    clinic_ecommerce_sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="eCommerce Sales Line",
        ondelete="set null",
        copy=False,
    )
    clinic_ecommerce_branch_id = fields.Many2one(
        "clinic.branch",
        string="eCommerce Branch",
        ondelete="set null",
        copy=False,
    )

    def action_open_clinic_ecommerce_fulfillment(self):
        self.ensure_one()
        if not self.clinic_ecommerce_fulfillment_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("eCommerce Fulfillment"),
            "res_model": "clinic.ecommerce.fulfillment",
            "view_mode": "form",
            "res_id": self.clinic_ecommerce_fulfillment_id.id,
        }


class ClinicPackageAllocation(models.Model):
    """Package Allocation provenance only; package entitlement semantics stay upstream."""

    _inherit = "clinic.package.allocation"

    clinic_ecommerce_fulfillment_id = fields.Many2one(
        "clinic.ecommerce.fulfillment",
        string="eCommerce Fulfillment",
        ondelete="set null",
        copy=False,
        index=True,
    )
    clinic_ecommerce_sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="eCommerce Sales Line",
        ondelete="set null",
        copy=False,
    )

    def action_open_clinic_ecommerce_fulfillment(self):
        self.ensure_one()
        if not self.clinic_ecommerce_fulfillment_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("eCommerce Fulfillment"),
            "res_model": "clinic.ecommerce.fulfillment",
            "view_mode": "form",
            "res_id": self.clinic_ecommerce_fulfillment_id.id,
        }


class MembershipContract(models.Model):
    """Membership provenance without invoking the owner module's duplicate-invoice workflow."""

    _inherit = "membership.contract"

    clinic_ecommerce_fulfillment_id = fields.Many2one(
        "clinic.ecommerce.fulfillment",
        string="eCommerce Fulfillment",
        ondelete="set null",
        copy=False,
        index=True,
    )
    clinic_ecommerce_sale_order_id = fields.Many2one(
        "sale.order",
        string="eCommerce Sales Order",
        ondelete="set null",
        copy=False,
    )
    clinic_ecommerce_sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="eCommerce Sales Line",
        ondelete="set null",
        copy=False,
    )

    def action_open_clinic_ecommerce_fulfillment(self):
        self.ensure_one()
        if not self.clinic_ecommerce_fulfillment_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("eCommerce Fulfillment"),
            "res_model": "clinic.ecommerce.fulfillment",
            "view_mode": "form",
            "res_id": self.clinic_ecommerce_fulfillment_id.id,
        }


class ClinicBranch(models.Model):
    """Branch-level eCommerce navigation while clinic_branch stays the Branch owner."""

    _inherit = "clinic.branch"

    clinic_ecommerce_fulfillment_ids = fields.One2many(
        "clinic.ecommerce.fulfillment",
        "branch_id",
        string="eCommerce Fulfillments",
    )
    clinic_ecommerce_fulfillment_count = fields.Integer(
        compute="_compute_clinic_ecommerce_fulfillment_count"
    )

    @api.depends("clinic_ecommerce_fulfillment_ids")
    def _compute_clinic_ecommerce_fulfillment_count(self):
        # Branch users should not receive an AccessError simply because this
        # addon adds a count field to clinic.branch. Only an aggregate count is
        # computed under sudo; opening the records still uses normal ACLs.
        for branch in self:
            branch.clinic_ecommerce_fulfillment_count = self.env[
                "clinic.ecommerce.fulfillment"
            ].sudo().search_count([("branch_id", "=", branch.id)])

    def action_open_clinic_ecommerce_fulfillments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Branch eCommerce Fulfillments"),
            "res_model": "clinic.ecommerce.fulfillment",
            "view_mode": "list,form",
            "domain": [("branch_id", "=", self.id)],
        }


class ProductTemplate(models.Model):
    """Navigation from an Odoo Product to governed Clinic eCommerce catalog mappings."""

    _inherit = "product.template"

    clinic_ecommerce_catalog_item_count = fields.Integer(
        compute="_compute_clinic_ecommerce_catalog_item_count"
    )

    def _compute_clinic_ecommerce_catalog_item_count(self):
        # Product users may not belong to the Clinic eCommerce privilege.
        # Compute only the aggregate with sudo; the action below still checks
        # the caller's eCommerce access before exposing catalog records.
        Catalog = self.env["clinic.ecommerce.catalog.item"].sudo()
        for template in self:
            template.clinic_ecommerce_catalog_item_count = len(
                Catalog.search([]).filtered(
                    lambda item: item.sale_product_tmpl_id == template
                )
            )

    def action_open_clinic_ecommerce_catalog_items(self):
        self.ensure_one()
        if not self.env.user.has_group(
            "clinic_ecommerce.group_ecommerce_user"
        ):
            return False
        item_ids = self.env["clinic.ecommerce.catalog.item"].search([]).filtered(
            lambda item: item.sale_product_tmpl_id == self
        ).ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic eCommerce Catalog Items"),
            "res_model": "clinic.ecommerce.catalog.item",
            "view_mode": "list,form",
            "domain": [("id", "in", item_ids)],
        }
