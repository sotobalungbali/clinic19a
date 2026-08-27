from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicEcommerceFulfillment(models.Model):
    """Traceable handoff from one eCommerce Sales Line into its owner workflow."""

    _name = "clinic.ecommerce.fulfillment"
    _description = "Clinic eCommerce Fulfillment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _check_company_auto = True

    _sale_line_unique = models.Constraint(
        "UNIQUE(sale_order_line_id)",
        "A Sales Line can have only one Clinic eCommerce Fulfillment.",
    )
    _company_state_idx = models.Index(
        "(company_id, state, fulfillment_type, create_date)"
    )
    _branch_state_idx = models.Index("(branch_id, state, create_date)")

    name = fields.Char(
        default="/",
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
    )
    website_id = fields.Many2one(
        "website",
        required=True,
        index=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        domain="[('company_id', '=', company_id)]",
        index=True,
        tracking=True,
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    catalog_item_id = fields.Many2one(
        "clinic.ecommerce.catalog.item",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    offering_type = fields.Selection(
        related="catalog_item_id.offering_type",
        store=True,
        readonly=True,
        index=True,
    )
    fulfillment_type = fields.Selection(
        related="catalog_item_id.fulfillment_type",
        store=True,
        readonly=True,
        index=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        tracking=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        index=True,
        tracking=True,
    )

    preferred_date = fields.Date(string="Preferred Date")
    preferred_time_window = fields.Selection(
        [
            ("morning", "Morning"),
            ("afternoon", "Afternoon"),
            ("evening", "Evening"),
            ("flexible", "Flexible"),
        ],
        string="Preferred Time Window",
    )
    customer_notes = fields.Text()
    terms_accepted_at = fields.Datetime(readonly=True)

    booking_start_datetime = fields.Datetime(
        string="Exact Booking Start",
        tracking=True,
        help="Required before a Treatment fulfillment can create its Booking handoff.",
    )
    booking_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Booking Doctor",
        tracking=True,
    )
    booking_room_id = fields.Many2one(
        "booking.room",
        string="Booking Room",
        tracking=True,
    )

    booking_id = fields.Many2one(
        "booking.booking",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    package_allocation_id = fields.Many2one(
        "clinic.package.allocation",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    membership_contract_id = fields.Many2one(
        "membership.contract",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )

    state = fields.Selection(
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
        default="pending",
        required=True,
        readonly=True,
        tracking=True,
        index=True,
    )
    requested_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    last_attempt_at = fields.Datetime(readonly=True)
    last_attempt_by_id = fields.Many2one("res.users", readonly=True)
    processed_at = fields.Datetime(readonly=True)
    processed_by_id = fields.Many2one("res.users", readonly=True)
    attempt_count = fields.Integer(default=0, readonly=True)
    error_message = fields.Text(readonly=True)
    outcome_note = fields.Text(readonly=True)
    internal_note = fields.Text()

    @api.model_create_multi
    # Fulfillment provenance is derived from the Sales Line so operators cannot detach evidence from the commercial order.
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            line = self.env["sale.order.line"].browse(
                vals.get("sale_order_line_id")
            ).exists()
            if line:
                vals.setdefault("sale_order_id", line.order_id.id)
                vals.setdefault("company_id", line.company_id.id)
                vals.setdefault("website_id", line.order_id.website_id.id)
                vals.setdefault(
                    "catalog_item_id",
                    line.clinic_ecommerce_catalog_item_id.id,
                )
                vals.setdefault(
                    "branch_id",
                    line.clinic_ecommerce_branch_id.id
                    or line.order_id.clinic_ecommerce_branch_id.id,
                )
                vals.setdefault("partner_id", line.order_id.partner_id.id)
                vals.setdefault(
                    "patient_id",
                    line.order_id.clinic_ecommerce_patient_id.id,
                )
                vals.setdefault(
                    "preferred_date",
                    line.clinic_ecommerce_preferred_date,
                )
                vals.setdefault(
                    "preferred_time_window",
                    line.clinic_ecommerce_time_window,
                )
                vals.setdefault(
                    "customer_notes",
                    line.clinic_ecommerce_notes,
                )
                vals.setdefault(
                    "terms_accepted_at",
                    line.clinic_ecommerce_terms_accepted_at,
                )
            company = self.env["res.company"].browse(
                vals.get("company_id")
            ) or self.env.company
            if vals.get("name", "/") in (False, "/", "New"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.ecommerce.fulfillment")
                    or "/"
                )
            vals["state"] = "pending"
            prepared.append(vals)
        records = super().create(prepared)
        records.action_evaluate_readiness()
        return records

    # Workflow/output fields are engine-owned; completed evidence stays immutable except for Internal Note/archival metadata.
    def write(self, vals):
        if "state" in vals and not self.env.context.get(
            "ecommerce_fulfillment_transition"
        ):
            raise AccessError(
                _("Use Fulfillment workflow actions to change status.")
            )

        protected = {
            "company_id",
            "website_id",
            "sale_order_id",
            "sale_order_line_id",
            "catalog_item_id",
            "partner_id",
            "booking_id",
            "package_allocation_id",
            "membership_contract_id",
            "requested_at",
            "processed_at",
            "processed_by_id",
            "attempt_count",
            "error_message",
            "outcome_note",
        }
        if protected.intersection(vals) and not self.env.context.get(
            "ecommerce_fulfillment_engine"
        ):
            raise AccessError(
                _("Fulfillment provenance/output fields are engine-owned.")
            )

        locked = self.filtered(
            lambda rec: rec.state in ("done", "reversal_required", "cancelled")
        )
        if locked and set(vals) - {"internal_note", "active"}:
            raise AccessError(
                _("Completed/Reversal/Cancelled Fulfillments are immutable except Internal Note.")
            )
        return super().write(vals)

    def unlink(self):
        raise AccessError(
            _("Fulfillment evidence cannot be deleted. Archive it instead.")
        )

    @api.constrains(
        "company_id",
        "website_id",
        "branch_id",
        "sale_order_id",
        "sale_order_line_id",
        "catalog_item_id",
        "partner_id",
        "patient_id",
    )
    def _check_scope(self):
        for rec in self:
            if rec.sale_order_line_id.order_id != rec.sale_order_id:
                raise ValidationError(
                    _("Fulfillment Sales Line must belong to its Sales Order.")
                )
            if rec.sale_order_id.company_id != rec.company_id:
                raise ValidationError(
                    _("Fulfillment and Sales Order company must match.")
                )
            if rec.catalog_item_id.company_id != rec.company_id:
                raise ValidationError(
                    _("Fulfillment and Catalog Item company must match.")
                )
            if rec.catalog_item_id.website_id != rec.website_id:
                raise ValidationError(
                    _("Fulfillment and Catalog Item Website must match.")
                )
            if rec.branch_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(
                    _("Fulfillment Branch must belong to its company.")
                )
            if rec.patient_id:
                if rec.patient_id.company_id != rec.company_id:
                    raise ValidationError(
                        _("Fulfillment Patient must belong to its company.")
                    )
                if rec.patient_id.partner_id and rec.patient_id.partner_id not in (
                    rec.partner_id,
                    rec.partner_id.commercial_partner_id,
                ):
                    raise ValidationError(
                        _("Fulfillment Patient does not match the Sales Order customer.")
                    )

    def _require_operator(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_ecommerce.group_ecommerce_operator"
        ):
            raise AccessError(
                _("Only an eCommerce Operator or Manager can process Fulfillments.")
            )
        return True

    def _transition(self, state, **extra):
        values = {"state": state, **extra}
        return self.with_context(
            ecommerce_fulfillment_transition=True,
            ecommerce_fulfillment_engine=True,
        ).write(values)

    # Readiness separates commercial payment/confirmation from clinical scheduling and owner-module prerequisites.
    def _readiness_error(self):
        self.ensure_one()
        item = self.catalog_item_id
        if self.sale_order_id.state not in ("sale", "done"):
            return _("Sales Order must be confirmed before fulfillment.")
        if item.requires_patient and not self.patient_id:
            return _("A Clinic Patient card is required.")
        if item.requires_branch and not self.branch_id:
            return _("A Branch is required for this offering.")
        if (
            item.terms_required
            or self.company_id.clinic_ecommerce_require_terms
        ) and not self.terms_accepted_at:
            return _("Required eCommerce terms have not been accepted.")
        if self.fulfillment_type == "booking":
            if not self.booking_start_datetime:
                return _("Exact Booking Start must be assigned by staff.")
        return False

    def action_evaluate_readiness(self):
        for rec in self:
            if rec.state in ("done", "reversal_required", "cancelled"):
                continue
            error = rec._readiness_error()
            rec._transition(
                "waiting_input" if error else "ready",
                error_message=error or False,
            )
        return True

    # Each handoff uses a savepoint so one failing Clinic artifact becomes an operator exception instead of corrupting the queue.
    def action_process(self):
        self._require_operator()
        for rec in self:
            if rec.state in ("done", "reversal_required", "cancelled"):
                continue
            rec.action_evaluate_readiness()
            if rec.state != "ready":
                continue

            rec._transition(
                "processing",
                last_attempt_at=fields.Datetime.now(),
                last_attempt_by_id=self.env.user.id,
                attempt_count=rec.attempt_count + 1,
                error_message=False,
            )
            try:
                with self.env.cr.savepoint():
                    outcome = rec._process_one()
                rec._transition(
                    "done",
                    processed_at=fields.Datetime.now(),
                    processed_by_id=self.env.user.id,
                    outcome_note=outcome or _("Fulfillment handoff completed."),
                    error_message=False,
                )
            except Exception as exc:
                rec._transition(
                    "error",
                    error_message=str(exc),
                )
        return True

    def _process_one(self):
        self.ensure_one()
        if self.fulfillment_type == "native_sale":
            return _(
                "Native Odoo Sale/Delivery lifecycle remains authoritative; no parallel Clinic artifact was created."
            )
        if self.fulfillment_type == "booking":
            return self._process_booking()
        if self.fulfillment_type == "package_allocation":
            return self._process_package_allocation()
        if self.fulfillment_type == "membership_contract":
            return self._process_membership_contract()
        return _("Manual Fulfillment retained for operator completion.")

    # Treatment fulfillment creates Draft Booking only; clinic_booking retains availability, overlap and confirmation authority.
    def _process_booking(self):
        self.ensure_one()
        if self.booking_id:
            return _("Existing Booking handoff retained.")

        item = self.catalog_item_id
        treatment = item.treatment_id
        if not treatment:
            raise UserError(_("Treatment source is missing."))
        if not self.patient_id or not self.patient_id.partner_id:
            raise UserError(_("Patient Contact is required to create a Booking."))
        if not self.booking_start_datetime:
            raise UserError(_("Exact Booking Start is required."))

        duration = max(treatment.duration_minutes or 60, 1)
        end_datetime = self.booking_start_datetime + timedelta(minutes=duration)
        booking = self.env["booking.booking"].sudo().create({
            "company_id": self.company_id.id,
            "patient_id": self.patient_id.partner_id.id,
            "treatment_id": treatment.id,
            "doctor_id": self.booking_doctor_id.id or False,
            "room_id": self.booking_room_id.id or False,
            "start_datetime": self.booking_start_datetime,
            "end_datetime": end_datetime,
            "notes": self.customer_notes or False,
            "clinic_ecommerce_fulfillment_id": self.id,
            "clinic_ecommerce_sale_order_id": self.sale_order_id.id,
            "clinic_ecommerce_sale_order_line_id": self.sale_order_line_id.id,
            "clinic_ecommerce_branch_id": self.branch_id.id or False,
        })
        self.with_context(ecommerce_fulfillment_engine=True).write({
            "booking_id": booking.id,
        })
        return _(
            "Draft Booking %(booking)s created. Booking confirmation/overlap checks remain owned by clinic_booking."
        ) % {"booking": booking.display_name}

    # Package fulfillment creates the owner Allocation and optionally calls its existing activation workflow.
    def _process_package_allocation(self):
        self.ensure_one()
        if self.package_allocation_id:
            allocation = self.package_allocation_id
        else:
            package = self.catalog_item_id.package_id
            if not package:
                raise UserError(_("Package source is missing."))
            if not self.patient_id:
                raise UserError(_("Patient is required for Package Allocation."))
            allocation = self.env["clinic.package.allocation"].sudo().create({
                "company_id": self.company_id.id,
                "package_id": package.id,
                "patient_id": self.patient_id.id,
                "partner_id": self.partner_id.id,
                "branch_id": self.branch_id.id or False,
                "sale_order_id": self.sale_order_id.id,
                "qty": self.sale_order_line_id.product_uom_qty,
                "clinic_ecommerce_fulfillment_id": self.id,
                "clinic_ecommerce_sale_order_line_id": self.sale_order_line_id.id,
            })
            self.with_context(ecommerce_fulfillment_engine=True).write({
                "package_allocation_id": allocation.id,
            })

        if (
            self.company_id.clinic_ecommerce_auto_activate_package
            and allocation.state == "draft"
        ):
            allocation.sudo().action_activate()
            return _(
                "Package Allocation %(allocation)s created and activated through clinic_package."
            ) % {"allocation": allocation.display_name}
        return _(
            "Draft Package Allocation %(allocation)s created; clinic_package remains lifecycle owner."
        ) % {"allocation": allocation.display_name}

    # Membership fulfillment intentionally avoids action_confirm(), which can create a second invoice outside Website Sale.
    def _process_membership_contract(self):
        self.ensure_one()
        if self.membership_contract_id:
            contract = self.membership_contract_id
        else:
            plan = self.catalog_item_id.membership_plan_id
            if not plan:
                raise UserError(_("Membership Plan source is missing."))
            contract = self.env["membership.contract"].sudo().create({
                "plan_id": plan.id,
                "company_id": self.company_id.id,
                "partner_id": self.partner_id.id,
                "patient_id": self.patient_id.id or False,
                "start_date": fields.Date.context_today(self),
                "notes": _("Created from eCommerce Sales Order %s") % self.sale_order_id.name,
                "clinic_ecommerce_fulfillment_id": self.id,
                "clinic_ecommerce_sale_order_id": self.sale_order_id.id,
                "clinic_ecommerce_sale_order_line_id": self.sale_order_line_id.id,
            })
            self.with_context(ecommerce_fulfillment_engine=True).write({
                "membership_contract_id": contract.id,
            })

        # Reuse the Odoo Website Sale invoice when available. We deliberately
        # do not call membership.action_confirm(), because that method creates
        # a second Membership invoice and would duplicate the online sale.
        paid_invoice = self.sale_order_id.invoice_ids.filtered(
            lambda invoice: invoice.state == "posted"
            and invoice.payment_state == "paid"
        )[:1]
        if paid_invoice and not contract.invoice_id:
            contract.sudo().write({"invoice_id": paid_invoice.id})

        if self.company_id.clinic_ecommerce_auto_activate_membership:
            Config = self.env["membership.config.service"].sudo()
            require_paid = Config.get_value(
                "require_paid_before_activation",
                self.company_id,
            )
            if require_paid and contract.contract_value > 0 and not (
                contract.invoice_id
                and contract.invoice_id.payment_state == "paid"
            ):
                return _(
                    "Membership Contract %(contract)s created, but automatic activation is intentionally deferred until a paid Odoo Sale invoice is available."
                ) % {"contract": contract.display_name}
            if contract.state in ("draft", "awaiting_payment"):
                contract.sudo().action_activate()
                return _(
                    "Membership Contract %(contract)s created and activated through clinic_membership using the existing paid Sale invoice when applicable."
                ) % {"contract": contract.display_name}

        return _(
            "Membership Contract %(contract)s created in Draft. eCommerce did not create a duplicate Membership invoice or bypass activation policy."
        ) % {"contract": contract.display_name}

    def action_retry(self):
        self._require_operator()
        retryable = self.filtered(
            lambda rec: rec.state in ("error", "waiting_input", "pending", "ready")
        )
        retryable.action_evaluate_readiness()
        retryable.filtered(lambda rec: rec.state == "ready").action_process()
        return True

    # Completed owner artifacts are never silently reversed: Sales cancellation raises a controlled reversal-required case.
    def action_cancel(self):
        self._require_operator()
        for rec in self:
            if rec.state == "done":
                rec._transition(
                    "reversal_required",
                    error_message=_(
                        "Sale was cancelled after fulfillment. Reverse/cancel the owner-module artifact manually, then mark reversal resolved."
                    ),
                )
            elif rec.state not in ("reversal_required", "cancelled"):
                rec._transition("cancelled", error_message=False)
        return True

    def action_mark_reversal_required(self, reason=None):
        for rec in self:
            if rec.state == "done":
                rec._transition(
                    "reversal_required",
                    error_message=reason
                    or _("Downstream fulfillment requires controlled reversal review."),
                )
        return True

    def action_mark_reversal_resolved(self):
        if not self.env.user.has_group(
            "clinic_ecommerce.group_ecommerce_manager"
        ):
            raise AccessError(
                _("Only an eCommerce Manager can close Reversal Required cases.")
            )
        for rec in self:
            if rec.state != "reversal_required":
                raise UserError(_("Only Reversal Required cases can be resolved."))
            rec._transition(
                "cancelled",
                error_message=False,
                outcome_note=_("Reversal review completed by %s.") % self.env.user.display_name,
            )
        return True

    def action_open_sale_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sales Order"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
        }

    def action_open_catalog_item(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Catalog Item"),
            "res_model": "clinic.ecommerce.catalog.item",
            "view_mode": "form",
            "res_id": self.catalog_item_id.id,
        }

    def action_open_booking(self):
        self.ensure_one()
        if not self.booking_id:
            raise UserError(_("No Booking handoff exists."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Booking"),
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.booking_id.id,
        }

    def action_open_package_allocation(self):
        self.ensure_one()
        if not self.package_allocation_id:
            raise UserError(_("No Package Allocation exists."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Allocation"),
            "res_model": "clinic.package.allocation",
            "view_mode": "form",
            "res_id": self.package_allocation_id.id,
        }

    def action_open_membership_contract(self):
        self.ensure_one()
        if not self.membership_contract_id:
            raise UserError(_("No Membership Contract exists."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Contract"),
            "res_model": "membership.contract",
            "view_mode": "form",
            "res_id": self.membership_contract_id.id,
        }
