from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicInsuranceAuthorization(models.Model):
    """Insurance pre-authorization request and payer adjudication evidence."""

    _name = "clinic.insurance.authorization"
    _description = "Clinic Insurance Pre-Authorization"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.insurance.company.mixin"]
    _order = "request_date desc, id desc"
    _check_company_auto = True

    _validity_order = models.Constraint(
        "CHECK(valid_to IS NULL OR valid_from IS NULL OR valid_from <= valid_to)",
        "Authorization validity start must be before or equal to validity end.",
    )
    _amounts_nonnegative = models.Constraint(
        "CHECK(requested_amount >= 0 AND approved_amount >= 0)",
        "Authorization requested and approved totals cannot be negative.",
    )
    _policy_state_idx = models.Index("(company_id, policy_id, state, service_date)")
    _patient_state_idx = models.Index("(company_id, patient_id, state, valid_to)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    policy_id = fields.Many2one(
        "clinic.insurance.policy",
        required=True,
        check_company=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id), ('patient_id', '=', patient_id), ('state', '=', 'active')]",
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        related="patient_id.partner_id",
        store=True,
        readonly=True,
        index=True,
    )
    insurer_partner_id = fields.Many2one(
        related="policy_id.insurer_partner_id",
        store=True,
        readonly=True,
        index=True,
    )
    plan_id = fields.Many2one(
        related="policy_id.plan_id",
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    source_type = fields.Selection(
        [
            ("manual", "Manual"),
            ("booking", "Booking"),
            ("appointment", "Appointment"),
            ("encounter", "Encounter"),
            ("treatment", "Treatment"),
            ("billing", "Billing Invoice"),
        ],
        default="manual",
        required=True,
        tracking=True,
        index=True,
    )
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        ondelete="set null",
        index=True,
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        ondelete="set null",
        index=True,
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        ondelete="set null",
        index=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        ondelete="set null",
        index=True,
    )
    billing_invoice_id = fields.Many2one(
        "clinic.billing.invoice",
        string="Clinic Billing Invoice",
        ondelete="set null",
        index=True,
    )

    request_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    service_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    submitted_at = fields.Datetime(readonly=True)
    decided_at = fields.Datetime(readonly=True)
    decided_by_id = fields.Many2one("res.users", readonly=True)
    valid_from = fields.Date(readonly=True, tracking=True)
    valid_to = fields.Date(readonly=True, tracking=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("prepared", "Prepared"),
            ("submitted", "Submitted"),
            ("pending", "Pending Payer"),
            ("approved", "Approved"),
            ("partial", "Partially Approved"),
            ("rejected", "Rejected"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    authorization_code = fields.Char(index=True, tracking=True)
    external_reference = fields.Char(index=True, tracking=True)
    submission_channel = fields.Selection(
        [
            ("portal", "Payer Portal"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("api", "API / EDI"),
            ("manual", "Manual"),
        ],
        default="manual",
        required=True,
    )
    request_reason = fields.Text()
    diagnosis_summary = fields.Text()
    clinical_note = fields.Text()
    rejection_reason = fields.Text()

    line_ids = fields.One2many(
        "clinic.insurance.authorization.line",
        "authorization_id",
        string="Requested Services",
        copy=True,
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_insurance_authorization_attachment_rel",
        "authorization_id",
        "attachment_id",
        string="Supporting Documents",
    )

    requested_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    approved_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    insurer_payable_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    patient_responsibility_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )

    authorization_required = fields.Boolean(
        compute="_compute_authorization_required",
        store=True,
        index=True,
    )
    eligibility_ok = fields.Boolean(
        compute="_compute_eligibility_ok",
        store=True,
        index=True,
    )
    currently_valid = fields.Boolean(
        compute="_compute_currently_valid",
        store=True,
        index=True,
    )

    claim_ids = fields.One2many(
        "clinic.insurance.claim",
        "authorization_id",
        string="Insurance Claims",
        copy=False,
    )
    claim_count = fields.Integer(compute="_compute_claim_count")
    note = fields.Text()

    @api.depends(
        "line_ids.requested_amount",
        "line_ids.approved_amount",
        "line_ids.insurer_payable_amount",
        "line_ids.patient_responsibility_amount",
    )
    def _compute_totals(self):
        for record in self:
            record.requested_amount = sum(record.line_ids.mapped("requested_amount"))
            record.approved_amount = sum(record.line_ids.mapped("approved_amount"))
            record.insurer_payable_amount = sum(record.line_ids.mapped("insurer_payable_amount"))
            record.patient_responsibility_amount = sum(
                record.line_ids.mapped("patient_responsibility_amount")
            )

    @api.depends(
        "policy_id.authorization_required",
        "line_ids.authorization_required",
    )
    def _compute_authorization_required(self):
        for record in self:
            record.authorization_required = bool(
                record.policy_id.authorization_required
                or record.line_ids.filtered("authorization_required")
            )

    @api.depends(
        "policy_id.eligibility_state",
        "policy_id.eligibility_valid_until",
    )
    def _compute_eligibility_ok(self):
        today = fields.Date.context_today(self)
        for record in self:
            policy = record.policy_id
            record.eligibility_ok = bool(
                policy
                and policy.eligibility_state == "eligible"
                and (
                    not policy.eligibility_valid_until
                    or policy.eligibility_valid_until >= today
                )
            )

    @api.depends("state", "valid_from", "valid_to")
    def _compute_currently_valid(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.currently_valid = bool(
                record.state in ("approved", "partial")
                and record.valid_from
                and record.valid_from <= today
                and (not record.valid_to or record.valid_to >= today)
            )

    def _compute_claim_count(self):
        for record in self:
            record.claim_count = len(record.claim_ids)

    @api.onchange("policy_id")
    def _onchange_policy(self):
        for record in self:
            if not record.policy_id:
                continue
            record.patient_id = record.policy_id.patient_id
            record.company_id = record.policy_id.company_id
            if not record.branch_id:
                record.branch_id = record.policy_id.branch_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            policy = self.env["clinic.insurance.policy"].browse(vals.get("policy_id"))
            if policy.exists():
                vals.setdefault("patient_id", policy.patient_id.id)
                vals.setdefault("company_id", policy.company_id.id)
                vals.setdefault("branch_id", policy.branch_id.id)
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.insurance.authorization")
                    or "/"
                )
        return super().create(vals_list)

    @api.constrains(
        "policy_id",
        "patient_id",
        "company_id",
        "booking_id",
        "appointment_id",
        "encounter_id",
        "treatment_id",
        "billing_invoice_id",
    )
    def _check_authorization_scope(self):
        for record in self:
            if record.policy_id.patient_id != record.patient_id:
                raise ValidationError(_("Authorization Patient must match the Insurance Policy Patient."))
            if record.policy_id.company_id != record.company_id:
                raise ValidationError(_("Authorization and Insurance Policy company must match."))

            source_partner = False
            if record.booking_id:
                source_partner = record.booking_id.patient_id
            elif record.appointment_id:
                source_partner = record.appointment_id.patient_id or record.appointment_id.partner_id
            elif record.treatment_id:
                source_partner = record.treatment_id.patient_id
            elif record.billing_invoice_id:
                source_partner = record.billing_invoice_id.patient_id

            if source_partner and source_partner != record.partner_id:
                raise ValidationError(_("Authorization source record belongs to a different patient."))

            if record.encounter_id and record.encounter_id.patient_id != record.patient_id:
                raise ValidationError(_("Authorization Encounter belongs to a different Patient."))

    def write(self, vals):
        workflow_fields = {
            "state",
            "submitted_at",
            "decided_at",
            "decided_by_id",
            "valid_from",
            "valid_to",
        }
        scope_fields = {
            "policy_id",
            "patient_id",
            "company_id",
            "branch_id",
            "booking_id",
            "appointment_id",
            "encounter_id",
            "treatment_id",
            "billing_invoice_id",
        }
        if workflow_fields.intersection(vals) and not self.env.context.get("insurance_transition"):
            raise AccessError(_("Use Authorization workflow actions to change status or decision evidence."))
        if scope_fields.intersection(vals):
            for record in self:
                if record.state not in ("draft", "prepared"):
                    raise UserError(_("Authorization source/policy scope can only be edited before submission."))
        return super().write(vals)

    # Submission hard-gate protects Policy dates, annual-limit status and configured eligibility requirements.
    def _active_policy_guard(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        policy = self.policy_id
        if policy.state != "active":
            raise UserError(_("Insurance Policy must be Active before Authorization submission."))
        if policy.start_date > self.service_date:
            raise UserError(_("Requested service date is before Policy coverage start."))
        if policy.end_date and policy.end_date < self.service_date:
            raise UserError(_("Requested service date is after Policy coverage end."))
        if policy.annual_limit and policy.remaining_annual_limit <= 0:
            raise UserError(_("Insurance Policy annual benefit limit has been exhausted."))
        if (
            self.company_id.clinic_insurance_require_eligibility_before_authorization
            and not self.eligibility_ok
        ):
            raise UserError(_("A current Eligible insurance verification is required before submission."))

    def _clear_lines(self):
        self.line_ids.unlink()

    # Source preparation snapshots commercial service data; later upstream edits cannot silently change the payer request.
    def _build_lines_from_source(self):
        """Populate request lines from the selected ClinicOne source when possible."""
        self.ensure_one()
        Line = self.env["clinic.insurance.authorization.line"]

        if self.line_ids:
            return

        if self.booking_id and self.booking_id.line_ids:
            for source in self.booking_id.line_ids.filtered(lambda line: not line.display_type):
                Line.create(self._line_vals(
                    treatment=source.treatment_id,
                    product=source.product_id,
                    description=source.name,
                    quantity=source.product_uom_qty or 1.0,
                    unit_price=source.price_unit or 0.0,
                    requested_snapshot=source.price_subtotal or 0.0,
                ))
            return

        if self.encounter_id and self.encounter_id.procedure_line_ids:
            for source in self.encounter_id.procedure_line_ids:
                Line.create(self._line_vals(
                    treatment=source.treatment_id,
                    procedure=source.procedure_id,
                    product=source.product_id,
                    description=source.name,
                    quantity=source.quantity or 1.0,
                    unit_price=source.price_unit or 0.0,
                    requested_snapshot=source.price_subtotal or 0.0,
                ))
            return

        if self.billing_invoice_id and self.billing_invoice_id.line_ids:
            for source in self.billing_invoice_id.line_ids.filtered(lambda line: not line.display_type):
                Line.create(self._line_vals(
                    treatment=source.treatment_id,
                    product=source.product_id,
                    description=source.name,
                    quantity=source.quantity or 1.0,
                    # Current clinic.billing.line owns `unit_price`; do not
                    # reference historical/nonexistent alternate pricing fields.
                    unit_price=source.unit_price or 0.0,
                    requested_snapshot=source.subtotal_excl_tax or 0.0,
                ))
            return

        treatment = self.treatment_id or (
            self.booking_id.treatment_id if self.booking_id else False
        ) or (
            self.appointment_id.treatment_id if self.appointment_id else False
        )
        if treatment:
            Line.create(self._line_vals(
                treatment=treatment,
                product=treatment.catalog_id.product_id if treatment.catalog_id else False,
                description=treatment.display_name,
                quantity=1.0,
                unit_price=(
                    treatment.catalog_id.base_price
                    if treatment.catalog_id and "base_price" in treatment.catalog_id._fields
                    else 0.0
                ),
                requested_snapshot=0.0,
            ))

    def _line_vals(
        self,
        treatment=False,
        procedure=False,
        product=False,
        description=False,
        quantity=1.0,
        unit_price=0.0,
        requested_snapshot=0.0,
    ):
        self.ensure_one()
        treatment_catalog = treatment.catalog_id if treatment and "catalog_id" in treatment._fields else False
        rule = self.plan_id.get_rule_for_service(
            treatment_catalog=treatment_catalog,
            procedure_catalog=procedure,
            product=product,
        )
        return {
            "authorization_id": self.id,
            "treatment_id": treatment.id if treatment else False,
            "treatment_catalog_id": treatment_catalog.id if treatment_catalog else False,
            "procedure_catalog_id": procedure.id if procedure else False,
            "product_id": product.id if product else False,
            "description": description or (product.display_name if product else _("Insurance Service")),
            "quantity": quantity or 1.0,
            "unit_price": unit_price or 0.0,
            "requested_amount_snapshot": requested_snapshot or 0.0,
            "benefit_rule_id": rule.id if rule else False,
            "authorization_required": (
                rule.authorization_required if rule else self.policy_id.authorization_required
            ),
            "coverage_percent": (
                rule.coverage_percent if rule else self.policy_id.coverage_percent
            ),
            "copay_percent": (
                rule.copay_percent if rule else self.policy_id.copay_percent
            ),
            "deductible_amount": (
                rule.deductible_amount if rule else self.policy_id.deductible_amount
            ),
            "maximum_insurer_amount": rule.maximum_amount if rule else 0.0,
            "maximum_quantity": rule.maximum_quantity if rule else 0.0,
        }

    def action_prepare(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can prepare Authorizations."),
        )
        for record in self:
            if record.state not in ("draft", "prepared"):
                raise UserError(_("Only Draft/Prepared Authorizations can be prepared."))
            record._build_lines_from_source()
            if not record.line_ids:
                raise UserError(_("Add at least one requested service line."))
            record.with_context(insurance_transition=True).write({"state": "prepared"})
        return True

    def action_submit(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can submit Authorizations."),
        )
        for record in self:
            if record.state == "draft":
                record.action_prepare()
            if record.state != "prepared":
                raise UserError(_("Only a Prepared Authorization can be submitted."))
            record._active_policy_guard()
            record.with_context(insurance_transition=True).write({
                "state": "submitted",
                "submitted_at": fields.Datetime.now(),
            })
            record.message_post(body=_("Insurance pre-authorization submitted for payer review."))
        return True

    def action_mark_pending(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can mark payer-pending Authorizations."),
        )
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only Submitted Authorizations can become Pending Payer."))
            record.with_context(insurance_transition=True).write({"state": "pending"})
        return True

    def _decision_validity(self):
        self.ensure_one()
        start = self.service_date or fields.Date.context_today(self)
        days = self.policy_id.authorization_valid_days or self.company_id.clinic_insurance_default_authorization_valid_days or 0
        return start, start + timedelta(days=days)

    # Payer approval writes decision evidence and validity dates; it never posts Billing or Accounting automatically.
    def action_approve(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_adjudicator",
            _("Only Insurance Adjudicators can approve Authorizations."),
        )
        for record in self:
            if record.state not in ("submitted", "pending"):
                raise UserError(_("Only Submitted/Pending Authorizations can be approved."))
            for line in record.line_ids:
                if not line.approved_quantity:
                    line.approved_quantity = line.quantity
                if not line.approved_amount:
                    line.approved_amount = line.requested_amount
                line._apply_rule_caps()
            start, end = record._decision_validity()
            decision_state = (
                "approved"
                if record.approved_amount >= record.requested_amount
                else "partial"
            )
            record.with_context(insurance_transition=True).write({
                "state": decision_state,
                "decided_at": fields.Datetime.now(),
                "decided_by_id": self.env.user.id,
                "valid_from": start,
                "valid_to": end,
            })
            record.message_post(body=_("Insurance pre-authorization approved by payer decision workflow."))
        return True

    def action_reject(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_adjudicator",
            _("Only Insurance Adjudicators can reject Authorizations."),
        )
        for record in self:
            if record.state not in ("submitted", "pending"):
                raise UserError(_("Only Submitted/Pending Authorizations can be rejected."))
            if not record.rejection_reason:
                raise UserError(_("Rejection Reason is required."))
            record.with_context(insurance_transition=True).write({
                "state": "rejected",
                "decided_at": fields.Datetime.now(),
                "decided_by_id": self.env.user.id,
            })
        return True

    def action_cancel(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can cancel Authorizations."),
        )
        for record in self:
            if record.state in ("approved", "partial") and record.claim_ids:
                raise UserError(_("An Authorization linked to Insurance Claims cannot be cancelled."))
            record.with_context(insurance_transition=True).write({"state": "cancelled"})
        return True

    # Claim creation deliberately delegates line coverage/settlement to the existing Billing claim engine.
    def action_create_claim(self):
        """Create/prepare the existing Billing-owned Insurance Claim from an approved authorization."""
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can create Claims from Authorizations."),
        )
        self.ensure_one()
        if self.state not in ("approved", "partial"):
            raise UserError(_("Only Approved/Partially Approved Authorizations can create Claims."))

        if self.claim_ids:
            claim = self.claim_ids[:1]
        else:
            invoice = self.billing_invoice_id
            if not invoice and self.booking_id:
                invoice = self.env["clinic.billing.invoice"].search(
                    [("booking_id", "=", self.booking_id.id), ("state", "!=", "cancelled")],
                    order="id desc",
                    limit=1,
                )
            if not invoice and self.encounter_id:
                invoice = self.env["clinic.billing.invoice"].search(
                    [("encounter_id", "=", self.encounter_id.id), ("state", "!=", "cancelled")],
                    order="id desc",
                    limit=1,
                )
            if not invoice:
                raise UserError(_(
                    "No Clinic Billing Invoice is linked to this Authorization. "
                    "Create/link Billing first, then create the Insurance Claim."
                ))

            claim = self.env["clinic.insurance.claim"].create({
                "invoice_id": invoice.id,
                "policy_id": self.policy_id.id,
                "authorization_id": self.id,
                "insurer_partner_id": self.insurer_partner_id.id,
                "policy_number": self.policy_id.policy_number,
                "coverage_percent": self.policy_id.coverage_percent,
                "copay_percent": self.policy_id.copay_percent,
                "deductible_amount": self.policy_id.deductible_amount,
                "settlement_journal_id": self.plan_id.settlement_journal_id.id or False,
            })
            claim.action_prepare()

        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Claim"),
            "res_model": "clinic.insurance.claim",
            "view_mode": "form",
            "res_id": claim.id,
        }

    def action_view_claims(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Claims"),
            "res_model": "clinic.insurance.claim",
            "view_mode": "list,form",
            "domain": [("authorization_id", "=", self.id)],
        }

    def action_open_policy(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Policy"),
            "res_model": "clinic.insurance.policy",
            "view_mode": "form",
            "res_id": self.policy_id.id,
        }

    def action_open_patient(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient"),
            "res_model": "clinic.patient",
            "view_mode": "form",
            "res_id": self.patient_id.id,
        }

    def action_open_source(self):
        self.ensure_one()
        source = {
            "booking": ("booking.booking", self.booking_id),
            "appointment": ("clinic.appointment", self.appointment_id),
            "encounter": ("clinic.encounter", self.encounter_id),
            "treatment": ("clinic.treatment", self.treatment_id),
            "billing": ("clinic.billing.invoice", self.billing_invoice_id),
        }.get(self.source_type)
        if not source or not source[1]:
            raise UserError(_("No source record is linked to this Authorization."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Authorization Source"),
            "res_model": source[0],
            "view_mode": "form",
            "res_id": source[1].id,
        }

    def action_print_authorization(self):
        self.ensure_one()
        return self.env.ref(
            "clinic_insurance_authorization.action_report_insurance_authorization"
        ).report_action(self)

    @api.model
    def _cron_expire_authorizations(self):
        today = fields.Date.context_today(self)
        expired = self.sudo().search([
            ("state", "in", ("approved", "partial")),
            ("valid_to", "!=", False),
            ("valid_to", "<", today),
        ])
        if expired:
            expired.with_context(insurance_transition=True).write({"state": "expired"})


class ClinicInsuranceAuthorizationLine(models.Model):
    """Requested and adjudicated service line under an Insurance Authorization."""

    _name = "clinic.insurance.authorization.line"
    _description = "Clinic Insurance Authorization Line"
    _order = "authorization_id, sequence, id"
    _check_company_auto = True

    _quantity_nonnegative = models.Constraint(
        "CHECK(quantity >= 0 AND approved_quantity >= 0 AND maximum_quantity >= 0)",
        "Authorization quantities cannot be negative.",
    )
    _percentage_range = models.Constraint(
        "CHECK(coverage_percent >= 0 AND coverage_percent <= 100 AND copay_percent >= 0 AND copay_percent <= 100)",
        "Coverage and co-pay percentages must be between 0 and 100.",
    )
    _line_amounts_nonnegative = models.Constraint(
        "CHECK(unit_price >= 0 AND requested_amount_snapshot >= 0 AND approved_amount >= 0 AND deductible_amount >= 0 AND maximum_insurer_amount >= 0)",
        "Authorization service amounts cannot be negative.",
    )
    _authorization_sequence_idx = models.Index("(authorization_id, sequence)")

    authorization_id = fields.Many2one(
        "clinic.insurance.authorization",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="authorization_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="authorization_id.currency_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(default=10)
    state = fields.Selection(
        related="authorization_id.state",
        store=True,
        readonly=True,
        index=True,
        string="Authorization State",
    )

    treatment_id = fields.Many2one("clinic.treatment", ondelete="set null")
    treatment_catalog_id = fields.Many2one("clinic.treatment.catalog", ondelete="set null")
    procedure_catalog_id = fields.Many2one("clinic.procedure.catalog", ondelete="set null")
    product_id = fields.Many2one("product.product", ondelete="set null")
    description = fields.Char(required=True)

    quantity = fields.Float(default=1.0)
    unit_price = fields.Monetary(currency_field="currency_id", default=0.0)
    requested_amount_snapshot = fields.Monetary(
        currency_field="currency_id",
        default=0.0,
        help="Optional source subtotal snapshot. When zero, quantity × unit price is used.",
    )
    requested_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    benefit_rule_id = fields.Many2one(
        "clinic.insurance.plan.rule",
        string="Benefit Rule",
        ondelete="set null",
    )
    authorization_required = fields.Boolean(default=True)
    coverage_percent = fields.Float(default=0.0)
    copay_percent = fields.Float(default=0.0)
    deductible_amount = fields.Monetary(currency_field="currency_id", default=0.0)
    maximum_insurer_amount = fields.Monetary(currency_field="currency_id", default=0.0)
    maximum_quantity = fields.Float(default=0.0)

    approved_quantity = fields.Float(default=0.0)
    approved_amount = fields.Monetary(currency_field="currency_id", default=0.0)
    insurer_payable_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )
    patient_responsibility_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )
    decision_note = fields.Char()

    @api.depends(
        "quantity",
        "unit_price",
        "requested_amount_snapshot",
        "approved_amount",
        "coverage_percent",
        "copay_percent",
        "deductible_amount",
        "maximum_insurer_amount",
    )
    def _compute_amounts(self):
        for line in self:
            requested = (
                line.requested_amount_snapshot
                if line.requested_amount_snapshot
                else (line.quantity or 0.0) * (line.unit_price or 0.0)
            )
            requested = max(requested, 0.0)
            approved = max(line.approved_amount or 0.0, 0.0)
            after_deductible = max(approved - (line.deductible_amount or 0.0), 0.0)
            covered = after_deductible * ((line.coverage_percent or 0.0) / 100.0)
            insurer = covered * (1.0 - ((line.copay_percent or 0.0) / 100.0))
            if line.maximum_insurer_amount:
                insurer = min(insurer, line.maximum_insurer_amount)
            insurer = max(insurer, 0.0)

            line.requested_amount = requested
            line.insurer_payable_amount = insurer
            line.patient_responsibility_amount = max(requested - insurer, 0.0)

    @api.constrains("benefit_rule_id", "authorization_id")
    def _check_benefit_rule_plan(self):
        for line in self:
            if (
                line.benefit_rule_id
                and line.benefit_rule_id.plan_id != line.authorization_id.plan_id
            ):
                raise ValidationError(_("Benefit Rule must belong to the Authorization Insurance Plan."))

    def write(self, vals):
        decision_fields = {"approved_quantity", "approved_amount", "decision_note"}
        if decision_fields.intersection(vals) and not self.env.user.has_group(
            "clinic_insurance_authorization.group_clinic_insurance_adjudicator"
        ):
            raise AccessError(
                _("Only an Insurance Adjudicator can record payer service-line decisions.")
            )

        if self.filtered(lambda line: line.authorization_id.state not in ("draft", "prepared", "submitted", "pending")):
            protected = {
                "treatment_id",
                "treatment_catalog_id",
                "procedure_catalog_id",
                "product_id",
                "quantity",
                "unit_price",
                "requested_amount_snapshot",
                "coverage_percent",
                "copay_percent",
                "deductible_amount",
            }
            if protected.intersection(vals):
                raise AccessError(_("Approved/rejected Authorization service scope is immutable."))
        return super().write(vals)

    def _apply_rule_caps(self):
        for line in self:
            if line.maximum_quantity and line.approved_quantity > line.maximum_quantity:
                line.approved_quantity = line.maximum_quantity

            quantity_ratio = (
                line.approved_quantity / line.quantity
                if line.quantity
                else 0.0
            )
            quantity_based_amount = line.requested_amount * min(quantity_ratio, 1.0)
            if line.approved_amount > quantity_based_amount and quantity_based_amount:
                line.approved_amount = quantity_based_amount

            if line.maximum_insurer_amount and line.insurer_payable_amount > line.maximum_insurer_amount:
                # insurer_payable_amount is computed, so the maximum is already
                # applied there; this branch documents/guards the contract.
                line.invalidate_recordset(["insurer_payable_amount"])

    def action_apply_benefit_rule(self):
        self.ensure_one()
        auth = self.authorization_id
        rule = auth.plan_id.get_rule_for_service(
            treatment_catalog=self.treatment_catalog_id,
            procedure_catalog=self.procedure_catalog_id,
            product=self.product_id,
        )
        if not rule:
            raise UserError(_("No matching Insurance Plan Benefit Rule was found."))
        self.write({
            "benefit_rule_id": rule.id,
            "authorization_required": rule.authorization_required,
            "coverage_percent": rule.coverage_percent,
            "copay_percent": rule.copay_percent,
            "deductible_amount": rule.deductible_amount,
            "maximum_insurer_amount": rule.maximum_amount,
            "maximum_quantity": rule.maximum_quantity,
        })
        return True

    def action_open_authorization(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Authorization"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "form",
            "res_id": self.authorization_id.id,
        }

