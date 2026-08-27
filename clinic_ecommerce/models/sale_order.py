from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class SaleOrder(models.Model):
    """Add ClinicOne online-sale provenance without replacing Odoo Sale lifecycle."""

    _inherit = "sale.order"

    clinic_ecommerce_branch_id = fields.Many2one(
        "clinic.branch",
        string="Clinic eCommerce Branch",
        domain="[('company_id', '=', company_id)]",
        tracking=True,
        copy=False,
    )
    clinic_ecommerce_patient_id = fields.Many2one(
        "clinic.patient",
        string="Clinic Patient",
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        tracking=True,
        copy=False,
    )
    clinic_ecommerce_terms_accepted_at = fields.Datetime(
        string="Clinic Terms Accepted At",
        readonly=True,
        copy=False,
    )
    clinic_ecommerce_fulfillment_ids = fields.One2many(
        "clinic.ecommerce.fulfillment",
        "sale_order_id",
        string="Clinic eCommerce Fulfillments",
        copy=False,
    )
    clinic_ecommerce_line_count = fields.Integer(
        compute="_compute_clinic_ecommerce_counts"
    )
    clinic_ecommerce_fulfillment_count = fields.Integer(
        compute="_compute_clinic_ecommerce_counts"
    )
    clinic_ecommerce_exception_count = fields.Integer(
        compute="_compute_clinic_ecommerce_counts"
    )
    clinic_ecommerce_processing_state = fields.Selection(
        [
            ("none", "No Clinic eCommerce"),
            ("pending", "Pending"),
            ("attention", "Needs Attention"),
            ("done", "Fulfilled"),
        ],
        compute="_compute_clinic_ecommerce_counts",
        store=False,
    )

    @api.depends(
        "order_line.clinic_ecommerce_catalog_item_id",
        "clinic_ecommerce_fulfillment_ids",
        "clinic_ecommerce_fulfillment_ids.state",
    )
    def _compute_clinic_ecommerce_counts(self):
        for order in self:
            ecom_lines = order.order_line.filtered(
                "clinic_ecommerce_catalog_item_id"
            )
            # This is aggregate state only. Native Sale/Website users must
            # not hit a Fulfillment ACL error while Odoo computes Sale fields.
            fulfillments = order.sudo().clinic_ecommerce_fulfillment_ids
            order.clinic_ecommerce_line_count = len(ecom_lines)
            order.clinic_ecommerce_fulfillment_count = len(fulfillments)
            order.clinic_ecommerce_exception_count = len(
                fulfillments.filtered(
                    lambda rec: rec.state
                    in ("waiting_input", "error", "reversal_required")
                )
            )
            if not ecom_lines:
                order.clinic_ecommerce_processing_state = "none"
            elif order.clinic_ecommerce_exception_count:
                order.clinic_ecommerce_processing_state = "attention"
            elif fulfillments and all(
                rec.state in ("done", "cancelled") for rec in fulfillments
            ):
                order.clinic_ecommerce_processing_state = "done"
            else:
                order.clinic_ecommerce_processing_state = "pending"

    @api.constrains(
        "company_id",
        "clinic_ecommerce_branch_id",
        "clinic_ecommerce_patient_id",
    )
    def _check_clinic_ecommerce_scope(self):
        for order in self:
            if (
                order.clinic_ecommerce_branch_id
                and order.clinic_ecommerce_branch_id.company_id != order.company_id
            ):
                raise ValidationError(
                    _("Clinic eCommerce Branch must belong to the Sales Order company.")
                )
            if (
                order.clinic_ecommerce_patient_id
                and order.clinic_ecommerce_patient_id.company_id != order.company_id
            ):
                raise ValidationError(
                    _("Clinic Patient must belong to the Sales Order company.")
                )

    # Sales Orders reuse an existing Patient card; eCommerce never creates clinical identity implicitly.
    def _clinic_ecommerce_resolve_patient(self):
        self.ensure_one()
        if self.clinic_ecommerce_patient_id:
            return self.clinic_ecommerce_patient_id
        partner_ids = {self.partner_id.id}
        if self.partner_id.commercial_partner_id:
            partner_ids.add(self.partner_id.commercial_partner_id.id)
        patient = self.env["clinic.patient"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
            ("partner_id", "in", list(partner_ids)),
        ], order="id", limit=1)
        if patient:
            self.sudo().write({
                "clinic_ecommerce_patient_id": patient.id,
            })
        return patient

    # One-Branch cart semantics and company policy are validated server-side before downstream handoff.
    def _clinic_ecommerce_validate_branch_policy(self):
        for order in self:
            if not order.clinic_ecommerce_branch_id:
                continue
            if (
                "policy_branch_scope_ecommerce" in order.company_id._fields
                and not order.company_id.policy_branch_scope_ecommerce
            ):
                raise UserError(
                    _("eCommerce Branch scoping is disabled for this company.")
                )
            mismatched = order.order_line.filtered(
                lambda line: line.clinic_ecommerce_catalog_item_id
                and line.clinic_ecommerce_branch_id
                and line.clinic_ecommerce_branch_id
                != order.clinic_ecommerce_branch_id
            )
            if mismatched:
                raise UserError(
                    _("A Clinic eCommerce cart can contain only one Branch scope.")
                )
        return True

    # One Fulfillment per Clinic Sales Line provides idempotent provenance across confirmation/payment callbacks.
    def _clinic_ecommerce_create_fulfillments(self):
        Fulfillment = self.env["clinic.ecommerce.fulfillment"].sudo()
        for order in self:
            patient = order._clinic_ecommerce_resolve_patient()
            for line in order.order_line.filtered(
                "clinic_ecommerce_catalog_item_id"
            ):
                existing = Fulfillment.search([
                    ("sale_order_line_id", "=", line.id),
                ], limit=1)
                if existing:
                    continue
                Fulfillment.create({
                    "sale_order_line_id": line.id,
                    "patient_id": patient.id or False,
                })
        return True

    # Trigger selection gates orchestration timing; it never changes the owner-module business rules.
    def _clinic_ecommerce_process_fulfillments(self, trigger="manual"):
        """Process only when the company-configured lifecycle trigger matches."""
        for order in self:
            if order.state not in ("sale", "done"):
                continue
            order._clinic_ecommerce_create_fulfillments()
            configured = order.company_id.clinic_ecommerce_fulfillment_trigger
            if trigger != "manual" and configured != trigger:
                continue
            if trigger == "manual" and configured != "manual" and not self.env.su:
                # Explicit operator action is still allowed regardless of automatic trigger.
                pass
            pending = order.clinic_ecommerce_fulfillment_ids.filtered(
                lambda rec: rec.state
                in ("pending", "waiting_input", "ready", "error")
            )
            if pending:
                processor = pending.sudo() if trigger != "manual" else pending
                processor.action_evaluate_readiness()
                processor.filtered(lambda rec: rec.state == "ready").action_process()
        return True

    def action_confirm(self):
        result = super().action_confirm()
        self._clinic_ecommerce_validate_branch_policy()
        self._clinic_ecommerce_create_fulfillments()
        self._clinic_ecommerce_process_fulfillments(
            trigger="order_confirmed"
        )
        return result

    def action_cancel(self):
        result = super().action_cancel()
        for order in self:
            order.clinic_ecommerce_fulfillment_ids.sudo().action_cancel()
        return result

    def action_process_clinic_ecommerce_fulfillments(self):
        if not self.env.user.has_group(
            "clinic_ecommerce.group_ecommerce_operator"
        ):
            raise AccessError(
                _("Only an eCommerce Operator or Manager can process Clinic Fulfillments.")
            )
        self._clinic_ecommerce_process_fulfillments(trigger="manual")
        return True

    def action_view_clinic_ecommerce_fulfillments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic eCommerce Fulfillments"),
            "res_model": "clinic.ecommerce.fulfillment",
            "view_mode": "list,form",
            "domain": [("sale_order_id", "=", self.id)],
            "context": {"default_sale_order_id": self.id},
        }


    # Cart merge protection keeps Branch/date/time/catalog semantics from collapsing into one native Sales Line.
    def _cart_find_product_line(
        self,
        product_id,
        uom_id,
        linked_line_id=False,
        no_variant_attribute_value_ids=None,
        **kwargs,
    ):
        lines = super()._cart_find_product_line(
            product_id,
            uom_id,
            linked_line_id=linked_line_id,
            no_variant_attribute_value_ids=no_variant_attribute_value_ids,
            **kwargs,
        )
        item_id = kwargs.get("clinic_ecommerce_catalog_item_id")
        if not item_id:
            return lines
        branch_id = kwargs.get("clinic_ecommerce_branch_id") or False
        preferred_date = kwargs.get("clinic_ecommerce_preferred_date") or False
        time_window = kwargs.get("clinic_ecommerce_time_window") or False
        return lines.filtered(
            lambda line: line.clinic_ecommerce_catalog_item_id.id == int(item_id)
            and (line.clinic_ecommerce_branch_id.id or False)
            == (int(branch_id) if branch_id else False)
            and (line.clinic_ecommerce_preferred_date or False)
            == (fields.Date.to_date(preferred_date) if preferred_date else False)
            and (line.clinic_ecommerce_time_window or False) == time_window
        )

    # Native Sales Lines receive only Clinic provenance metadata; Odoo continues to own price/tax/cart computations.
    def _prepare_order_line_values(
        self,
        product_id,
        quantity,
        uom_id,
        *,
        linked_line_id=False,
        no_variant_attribute_value_ids=None,
        product_custom_attribute_values=None,
        combo_item_id=None,
        **kwargs,
    ):
        values = super()._prepare_order_line_values(
            product_id,
            quantity,
            uom_id,
            linked_line_id=linked_line_id,
            no_variant_attribute_value_ids=no_variant_attribute_value_ids,
            product_custom_attribute_values=product_custom_attribute_values,
            combo_item_id=combo_item_id,
            **kwargs,
        )

        item_id = kwargs.get("clinic_ecommerce_catalog_item_id")
        if not item_id and self.website_id:
            # Native /shop exposure is opt-in. If a Product has exactly one
            # published native Catalog mapping for this Website, preserve its
            # provenance even when the line originated from Odoo's native Shop.
            candidates = self.env["clinic.ecommerce.catalog.item"].sudo().search([
                ("company_id", "=", self.company_id.id),
                ("website_id", "=", self.website_id.id),
                ("state", "=", "published"),
                ("active", "=", True),
                ("publish_native_product", "=", True),
            ]).filtered(lambda item: item.sale_product_id.id == product_id)
            if len(candidates) == 1:
                item_id = candidates.id

        if item_id:
            item = self.env["clinic.ecommerce.catalog.item"].sudo().browse(
                int(item_id)
            ).exists()
            if item:
                values.update({
                    "clinic_ecommerce_catalog_item_id": item.id,
                    "clinic_ecommerce_branch_id": kwargs.get(
                        "clinic_ecommerce_branch_id"
                    ) or False,
                    "clinic_ecommerce_preferred_date": kwargs.get(
                        "clinic_ecommerce_preferred_date"
                    ) or False,
                    "clinic_ecommerce_time_window": kwargs.get(
                        "clinic_ecommerce_time_window"
                    ) or False,
                    "clinic_ecommerce_notes": kwargs.get(
                        "clinic_ecommerce_notes"
                    ) or False,
                    "clinic_ecommerce_terms_accepted": bool(
                        kwargs.get("clinic_ecommerce_terms_accepted")
                    ),
                    "clinic_ecommerce_terms_accepted_at": (
                        fields.Datetime.now()
                        if kwargs.get("clinic_ecommerce_terms_accepted")
                        else False
                    ),
                })
        return values

    # Quantity policy is applied after Odoo native quantity validation so core stock/UoM warnings remain authoritative.
    def _verify_updated_quantity(
        self,
        order_line,
        product_id,
        new_qty,
        uom_id,
        **kwargs,
    ):
        quantity, warning = super()._verify_updated_quantity(
            order_line,
            product_id,
            new_qty,
            uom_id,
            **kwargs,
        )
        item = (
            order_line.clinic_ecommerce_catalog_item_id
            if order_line
            else self.env["clinic.ecommerce.catalog.item"].sudo().browse(
                kwargs.get("clinic_ecommerce_catalog_item_id") or False
            )
        )
        if not item:
            return quantity, warning

        message = False
        if item.single_quantity_only:
            if quantity != 1.0:
                quantity = 1.0
                message = _("This Clinic offering can only be purchased one at a time.")
        else:
            if quantity < item.min_quantity:
                quantity = item.min_quantity
                message = _("Quantity was raised to the minimum allowed for this Clinic offering.")
            if item.max_quantity and quantity > item.max_quantity:
                quantity = item.max_quantity
                message = _("Quantity was reduced to the maximum allowed for this Clinic offering.")
        combined = " ".join(part for part in (warning, message) if part)
        return quantity, combined
