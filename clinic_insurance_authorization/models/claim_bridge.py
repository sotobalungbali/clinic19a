from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


# clinic_billing remains owner of claim settlement through clinic.billing.payment.
class ClinicInsuranceClaim(models.Model):
    """Enterprise Policy/Authorization governance over Billing-owned Claims."""

    _inherit = "clinic.insurance.claim"

    policy_id = fields.Many2one(
        "clinic.insurance.policy",
        string="Insurance Policy",
        check_company=True,
        ondelete="restrict",
        index=True,
        domain="[('company_id', '=', company_id), ('partner_id', '=', patient_id)]",
    )
    plan_id = fields.Many2one(
        related="policy_id.plan_id",
        store=True,
        readonly=True,
        index=True,
        string="Insurance Plan",
    )
    authorization_id = fields.Many2one(
        "clinic.insurance.authorization",
        string="Pre-Authorization",
        check_company=True,
        ondelete="restrict",
        index=True,
        domain="[('company_id', '=', company_id), ('partner_id', '=', patient_id), ('state', 'in', ('approved','partial','expired'))]",
    )
    eligibility_check_id = fields.Many2one(
        "clinic.insurance.eligibility.check",
        string="Eligibility Evidence",
        check_company=True,
        ondelete="set null",
        domain="[('policy_id', '=', policy_id), ('state', '=', 'eligible')]",
    )

    external_claim_reference = fields.Char(
        string="Payer Claim Reference",
        index=True,
        tracking=True,
    )
    payer_status = fields.Selection(
        [
            ("not_sent", "Not Sent"),
            ("received", "Received by Payer"),
            ("under_review", "Under Review"),
            ("approved", "Approved"),
            ("partially_approved", "Partially Approved"),
            ("denied", "Denied"),
            ("settled", "Settled"),
        ],
        default="not_sent",
        tracking=True,
        index=True,
    )
    adjudicated_date = fields.Date(readonly=True, tracking=True)
    denial_code = fields.Char(index=True)
    denial_reason = fields.Text()
    authorization_code = fields.Char(
        related="authorization_id.authorization_code",
        store=True,
        readonly=True,
    )
    authorization_valid = fields.Boolean(
        compute="_compute_authorization_valid",
        store=True,
        index=True,
    )
    policy_valid = fields.Boolean(
        compute="_compute_policy_valid",
        store=True,
        index=True,
    )

    @api.depends(
        "authorization_id.state",
        "authorization_id.valid_from",
        "authorization_id.valid_to",
        "claim_date",
    )
    def _compute_authorization_valid(self):
        for claim in self:
            auth = claim.authorization_id
            date = claim.claim_date or fields.Date.context_today(self)
            claim.authorization_valid = bool(
                auth
                and auth.state in ("approved", "partial")
                and auth.valid_from
                and auth.valid_from <= date
                and (not auth.valid_to or auth.valid_to >= date)
            )

    @api.depends(
        "policy_id.state",
        "policy_id.start_date",
        "policy_id.end_date",
        "claim_date",
    )
    def _compute_policy_valid(self):
        for claim in self:
            policy = claim.policy_id
            date = claim.claim_date or fields.Date.context_today(self)
            claim.policy_valid = bool(
                policy
                and policy.state == "active"
                and policy.start_date <= date
                and (not policy.end_date or policy.end_date >= date)
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            invoice = self.env["clinic.billing.invoice"].browse(vals.get("invoice_id"))
            if invoice.exists():
                policy = self.env["clinic.insurance.policy"].browse(vals.get("policy_id"))
                if not policy and "insurance_policy_id" in invoice._fields:
                    policy = invoice.insurance_policy_id

                if policy:
                    vals.setdefault("policy_id", policy.id)
                    vals.setdefault("insurer_partner_id", policy.insurer_partner_id.id)
                    vals.setdefault("policy_number", policy.policy_number)
                    vals.setdefault("coverage_percent", policy.coverage_percent)
                    vals.setdefault("copay_percent", policy.copay_percent)
                    vals.setdefault("deductible_amount", policy.deductible_amount)

                auth = self.env["clinic.insurance.authorization"].browse(vals.get("authorization_id"))
                if not auth and "insurance_authorization_id" in invoice._fields:
                    auth = invoice.insurance_authorization_id
                if auth:
                    vals.setdefault("authorization_id", auth.id)
                    vals.setdefault("policy_id", auth.policy_id.id)
                    vals.setdefault("eligibility_check_id", auth.policy_id.last_eligibility_check_id.id or False)

        return super().create(vals_list)

    @api.constrains(
        "policy_id",
        "authorization_id",
        "eligibility_check_id",
        "invoice_id",
    )
    def _check_insurance_claim_scope(self):
        for claim in self:
            if claim.policy_id:
                if claim.policy_id.partner_id != claim.patient_id:
                    raise ValidationError(_("Insurance Claim Policy belongs to a different patient."))
                if claim.policy_id.company_id != claim.company_id:
                    raise ValidationError(_("Insurance Claim Policy belongs to a different company."))

            if claim.authorization_id:
                if claim.authorization_id.policy_id != claim.policy_id:
                    raise ValidationError(_("Claim Authorization must belong to the selected Insurance Policy."))
                if claim.authorization_id.partner_id != claim.patient_id:
                    raise ValidationError(_("Claim Authorization belongs to a different patient."))

            if claim.eligibility_check_id and claim.eligibility_check_id.policy_id != claim.policy_id:
                raise ValidationError(_("Eligibility Evidence must belong to the selected Insurance Policy."))

    def write(self, vals):
        governed = {
            "policy_id",
            "authorization_id",
            "eligibility_check_id",
            "external_claim_reference",
        }
        adjudication = {
            "payer_status",
            "adjudicated_date",
            "denial_code",
            "denial_reason",
        }

        if adjudication.intersection(vals) and not self.env.context.get("insurance_adjudication"):
            raise AccessError(_("Use Claim workflow/adjudication actions to update payer decision evidence."))

        if governed.intersection(vals):
            for claim in self:
                if claim.state in ("approved", "settled"):
                    raise UserError(_("Approved/Settled Claim insurance linkage is immutable."))

        return super().write(vals)

    def _insurance_claim_permission(self, role="coordinator"):
        role_xmlid = {
            "coordinator": "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            "adjudicator": "clinic_insurance_authorization.group_clinic_insurance_adjudicator",
            "manager": "clinic_insurance_authorization.group_clinic_insurance_manager",
        }[role]

        if self.env.user.has_group(role_xmlid):
            return True

        # Preserve the historically installed Billing Manager authority.
        if self.env.user.has_group("clinic_billing.group_clinic_billing_manager"):
            return True

        raise AccessError(_("You do not have permission for this Insurance Claim action."))

    # Link discovery is evidence-based (Billing source/Patient/approved Authorization) and never creates a Policy implicitly.
    def _auto_link_policy_authorization(self):
        for claim in self:
            invoice = claim.invoice_id

            if not claim.policy_id:
                policy = (
                    invoice.insurance_policy_id
                    if invoice and "insurance_policy_id" in invoice._fields
                    else False
                )
                if not policy and claim.patient_id:
                    policy = self.env["clinic.insurance.policy"].search([
                        ("partner_id", "=", claim.patient_id.id),
                        ("company_id", "=", claim.company_id.id),
                        ("state", "=", "active"),
                    ], order="start_date desc, id desc", limit=1)
                if policy:
                    claim.policy_id = policy.id

            if claim.policy_id:
                claim.insurer_partner_id = claim.policy_id.insurer_partner_id
                claim.policy_number = claim.policy_id.policy_number
                if not claim.coverage_percent:
                    claim.coverage_percent = claim.policy_id.coverage_percent
                if not claim.copay_percent:
                    claim.copay_percent = claim.policy_id.copay_percent
                if not claim.deductible_amount:
                    claim.deductible_amount = claim.policy_id.deductible_amount
                if not claim.eligibility_check_id:
                    claim.eligibility_check_id = claim.policy_id.last_eligibility_check_id

            if not claim.authorization_id:
                auth = (
                    invoice.insurance_authorization_id
                    if invoice and "insurance_authorization_id" in invoice._fields
                    else False
                )
                if not auth and claim.policy_id:
                    domain = [
                        ("policy_id", "=", claim.policy_id.id),
                        ("state", "in", ("approved", "partial")),
                    ]
                    if invoice and invoice.booking_id:
                        domain.append(("booking_id", "=", invoice.booking_id.id))
                    elif invoice and invoice.encounter_id:
                        domain.append(("encounter_id", "=", invoice.encounter_id.id))
                    auth = self.env["clinic.insurance.authorization"].search(
                        domain,
                        order="decided_at desc, id desc",
                        limit=1,
                    )
                if auth:
                    claim.authorization_id = auth.id

    def action_prepare(self):
        self._insurance_claim_permission("coordinator")
        self._auto_link_policy_authorization()
        result = super().action_prepare()

        # Match prepared Billing claim lines to Authorization lines by source
        # service/product whenever the correspondence is unambiguous.
        for claim in self:
            if not claim.authorization_id:
                continue
            for claim_line in claim.claim_line_ids:
                if claim_line.authorization_line_id:
                    continue
                candidates = claim.authorization_id.line_ids.filtered(
                    lambda auth_line:
                        (
                            claim_line.product_id
                            and auth_line.product_id == claim_line.product_id
                        )
                        or (
                            claim_line.billing_line_id
                            and auth_line.treatment_id
                            and auth_line.treatment_id == claim_line.billing_line_id.treatment_id
                        )
                )
                if len(candidates) == 1:
                    claim_line.authorization_line_id = candidates.id
                    claim_line.benefit_rule_id = candidates.benefit_rule_id
        return result

    # Integrated claims receive stricter Policy/Authorization validation while legacy no-Policy Billing claims remain backward compatible.
    def action_submit(self):
        self._insurance_claim_permission("coordinator")
        self._auto_link_policy_authorization()

        for claim in self:
            if claim.policy_id:
                if not claim.policy_valid:
                    raise UserError(_("Insurance Policy is not valid on the Claim date."))

                if (
                    claim.policy_id.authorization_required
                    and claim.company_id.clinic_insurance_claim_require_authorization
                ):
                    if not claim.authorization_id:
                        raise UserError(_("This Policy requires an approved Pre-Authorization before Claim submission."))
                    if not claim.authorization_valid:
                        raise UserError(_("The linked Pre-Authorization is not valid on the Claim date."))

        result = super().action_submit()
        self.with_context(insurance_adjudication=True).write({"payer_status": "received"})
        return result

    def action_mark_under_review(self):
        self._insurance_claim_permission("adjudicator")
        for claim in self:
            if claim.state != "submitted":
                raise UserError(_("Only Submitted Claims can be marked Under Review."))
        self.with_context(insurance_adjudication=True).write({"payer_status": "under_review"})
        return True

    def action_approve(self):
        self._insurance_claim_permission("adjudicator")
        result = super().action_approve()
        today = fields.Date.context_today(self)
        for claim in self:
            claim.with_context(insurance_adjudication=True).write({
                "payer_status": "approved",
                "adjudicated_date": today,
                "denial_code": False,
                "denial_reason": False,
            })
        return result

    def action_reject(self):
        self._insurance_claim_permission("adjudicator")
        result = super().action_reject()
        today = fields.Date.context_today(self)
        for claim in self:
            claim.with_context(insurance_adjudication=True).write({
                "payer_status": "denied",
                "adjudicated_date": today,
                "denial_reason": claim.denial_reason or claim.reason_rejected,
            })
        return result

    # Settlement calls Billing super(), preserving clinic.billing.payment and its accounting reconciliation path.
    def action_settle(self):
        self._insurance_claim_permission("manager")

        # Preserve the old Billing behavior for legacy claims with no Insurance
        # Policy. Integrated Policy claims, however, must be adjudicated before
        # settlement.
        for claim in self:
            if claim.policy_id and claim.state != "approved":
                raise UserError(_("Policy-linked Claims must be Approved before settlement."))

        result = super().action_settle()
        self.with_context(insurance_adjudication=True).write({"payer_status": "settled"})
        return result

    def action_open_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Billing Invoice"),
            "res_model": "clinic.billing.invoice",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
        }

    def action_open_policy(self):
        self.ensure_one()
        if not self.policy_id:
            raise UserError(_("No Insurance Policy is linked to this Claim."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Policy"),
            "res_model": "clinic.insurance.policy",
            "view_mode": "form",
            "res_id": self.policy_id.id,
        }

    def action_open_authorization(self):
        self.ensure_one()
        if not self.authorization_id:
            raise UserError(_("No Pre-Authorization is linked to this Claim."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Pre-Authorization"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "form",
            "res_id": self.authorization_id.id,
        }

    def action_print_insurance_claim(self):
        self.ensure_one()
        return self.env.ref(
            "clinic_insurance_authorization.action_report_insurance_claim"
        ).report_action(self)


class ClinicInsuranceClaimLine(models.Model):
    """Trace Billing-owned Claim lines back to Authorization service decisions."""

    _inherit = "clinic.insurance.claim.line"

    authorization_line_id = fields.Many2one(
        "clinic.insurance.authorization.line",
        string="Authorization Service Line",
        ondelete="set null",
        index=True,
    )
    benefit_rule_id = fields.Many2one(
        related="authorization_line_id.benefit_rule_id",
        store=True,
        readonly=True,
        string="Benefit Rule",
    )
    authorized_amount = fields.Monetary(
        related="authorization_line_id.approved_amount",
        currency_field="currency_id",
        store=True,
        readonly=True,
    )
    authorization_variance = fields.Monetary(
        string="Claim vs Authorization Variance",
        currency_field="currency_id",
        compute="_compute_authorization_variance",
        store=True,
    )

    @api.depends(
        "subtotal_excl_tax",
        "quantity",
        "unit_price",
        "authorized_amount",
    )
    def _compute_authorization_variance(self):
        for line in self:
            requested = line.subtotal_excl_tax or (
                (line.quantity or 0.0) * (line.unit_price or 0.0)
            )
            line.authorization_variance = (
                max(requested, 0.0) - (line.authorized_amount or 0.0)
            )

    @api.constrains("authorization_line_id", "claim_id")
    def _check_authorization_line(self):
        for line in self:
            if (
                line.authorization_line_id
                and line.claim_id.authorization_id
                and line.authorization_line_id.authorization_id != line.claim_id.authorization_id
            ):
                raise ValidationError(_("Claim Line Authorization Service must belong to the Claim Authorization."))

    def action_open_authorization_line(self):
        self.ensure_one()
        if not self.authorization_line_id:
            raise UserError(_("No Authorization Service Line is linked."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Authorization Service Line"),
            "res_model": "clinic.insurance.authorization.line",
            "view_mode": "form",
            "res_id": self.authorization_line_id.id,
        }

