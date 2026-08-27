from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicInsurancePolicy(models.Model):
    """Patient enrollment in a payer Insurance Plan."""

    _name = "clinic.insurance.policy"
    _description = "Clinic Insurance Policy"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.insurance.company.mixin"]
    _order = "patient_id, start_date desc, id desc"
    _check_company_auto = True

    _policy_number_unique = models.Constraint(
        "UNIQUE(company_id, insurer_partner_id, policy_number)",
        "Insurance Policy number must be unique per company and insurer.",
    )
    _date_order = models.Constraint(
        "CHECK(end_date IS NULL OR start_date IS NULL OR start_date <= end_date)",
        "Insurance Policy start date must be before or equal to end date.",
    )
    _coverage_range = models.Constraint(
        "CHECK(coverage_percent >= 0 AND coverage_percent <= 100)",
        "Policy coverage percentage must be between 0 and 100.",
    )
    _copay_range = models.Constraint(
        "CHECK(copay_percent >= 0 AND copay_percent <= 100)",
        "Policy co-pay percentage must be between 0 and 100.",
    )
    _policy_amounts_nonnegative = models.Constraint(
        "CHECK(deductible_amount >= 0 AND annual_limit >= 0)",
        "Policy deductible and annual limit cannot be negative.",
    )
    _patient_state_idx = models.Index("(company_id, patient_id, state, end_date)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
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
        string="Patient Contact",
    )
    insurer_partner_id = fields.Many2one(
        "res.partner",
        string="Insurer / Payer",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('is_insurer', '=', True)]",
    )
    plan_id = fields.Many2one(
        "clinic.insurance.plan",
        string="Insurance Plan",
        required=True,
        check_company=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id), ('insurer_partner_id', '=', insurer_partner_id), ('state', '=', 'active')]",
    )

    policy_number = fields.Char(required=True, index=True, tracking=True)
    member_number = fields.Char(index=True, tracking=True)
    group_number = fields.Char(index=True)
    relationship_to_holder = fields.Selection(
        [
            ("self", "Self"),
            ("spouse", "Spouse"),
            ("child", "Child"),
            ("parent", "Parent"),
            ("other", "Other"),
        ],
        default="self",
        required=True,
    )
    policy_holder_name = fields.Char()

    start_date = fields.Date(required=True, tracking=True)
    end_date = fields.Date(tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("verified", "Verified"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    verification_reference = fields.Char()
    verified_at = fields.Datetime(readonly=True)
    verified_by_id = fields.Many2one("res.users", readonly=True)
    suspension_reason = fields.Char()
    cancellation_reason = fields.Char()

    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    coverage_percent = fields.Float(default=0.0, tracking=True)
    copay_percent = fields.Float(default=0.0, tracking=True)
    deductible_amount = fields.Monetary(currency_field="currency_id", default=0.0, tracking=True)
    annual_limit = fields.Monetary(
        currency_field="currency_id",
        default=0.0,
        help="Zero means no ClinicOne-enforced annual limit.",
    )

    authorization_required = fields.Boolean(default=True, tracking=True)
    authorization_valid_days = fields.Integer(default=30)
    eligibility_valid_days = fields.Integer(default=30)

    eligibility_check_ids = fields.One2many(
        "clinic.insurance.eligibility.check",
        "policy_id",
        string="Eligibility Checks",
        copy=False,
    )
    last_eligibility_check_id = fields.Many2one(
        "clinic.insurance.eligibility.check",
        compute="_compute_eligibility_snapshot",
        store=True,
    )
    eligibility_state = fields.Selection(
        [
            ("unknown", "Unknown"),
            ("eligible", "Eligible"),
            ("ineligible", "Ineligible"),
            ("expired", "Evidence Expired"),
        ],
        compute="_compute_eligibility_snapshot",
        store=True,
        index=True,
    )
    eligibility_valid_until = fields.Date(
        compute="_compute_eligibility_snapshot",
        store=True,
    )

    authorization_ids = fields.One2many(
        "clinic.insurance.authorization",
        "policy_id",
        string="Pre-Authorizations",
        copy=False,
    )
    claim_ids = fields.One2many(
        "clinic.insurance.claim",
        "policy_id",
        string="Insurance Claims",
        copy=False,
    )
    authorization_count = fields.Integer(compute="_compute_counts")
    claim_count = fields.Integer(compute="_compute_counts")
    eligibility_count = fields.Integer(compute="_compute_counts")

    settled_claim_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_financial_snapshot",
    )
    remaining_annual_limit = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_financial_snapshot",
    )
    currently_valid = fields.Boolean(
        compute="_compute_currently_valid",
        store=True,
        index=True,
    )
    notes = fields.Text()

    # Daily expiry cron changes state so the stored validity flag remains search-safe over time.
    @api.depends("state", "start_date", "end_date")
    def _compute_currently_valid(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.currently_valid = (
                record.state == "active"
                and bool(record.start_date)
                and record.start_date <= today
                and (not record.end_date or record.end_date >= today)
            )

    @api.depends(
        "eligibility_check_ids.state",
        "eligibility_check_ids.checked_at",
        "eligibility_check_ids.valid_until",
    )
    def _compute_eligibility_snapshot(self):
        today = fields.Date.context_today(self)
        for record in self:
            checks = record.eligibility_check_ids.sorted(
                key=lambda check: (check.checked_at or fields.Datetime.to_datetime("1970-01-01 00:00:00"), check.id),
                reverse=True,
            )
            latest = checks[:1]
            record.last_eligibility_check_id = latest.id if latest else False
            record.eligibility_valid_until = latest.valid_until if latest else False

            if not latest:
                record.eligibility_state = "unknown"
            elif latest.state == "eligible":
                if latest.valid_until and latest.valid_until < today:
                    record.eligibility_state = "expired"
                else:
                    record.eligibility_state = "eligible"
            elif latest.state == "ineligible":
                record.eligibility_state = "ineligible"
            else:
                record.eligibility_state = "unknown"

    def _compute_counts(self):
        for record in self:
            record.authorization_count = len(record.authorization_ids)
            record.claim_count = len(record.claim_ids)
            record.eligibility_count = len(record.eligibility_check_ids)

    # Annual utilization is a management snapshot from settled Billing-owned claims, never a second ledger.
    def _compute_financial_snapshot(self):
        for record in self:
            settled_claims = record.claim_ids.filtered(lambda claim: claim.state == "settled")
            settled = sum(settled_claims.mapped("insurer_payable_amount"))
            record.settled_claim_amount = settled
            record.remaining_annual_limit = (
                max(record.annual_limit - settled, 0.0)
                if record.annual_limit
                else 0.0
            )

    @api.onchange("plan_id")
    def _onchange_plan(self):
        for record in self:
            plan = record.plan_id
            if not plan:
                continue
            record.company_id = plan.company_id
            record.insurer_partner_id = plan.insurer_partner_id
            record.coverage_percent = plan.default_coverage_percent
            record.copay_percent = plan.default_copay_percent
            record.deductible_amount = plan.default_deductible_amount
            record.annual_limit = plan.annual_limit
            record.authorization_required = plan.authorization_required_default
            record.authorization_valid_days = plan.authorization_valid_days
            record.eligibility_valid_days = plan.eligibility_valid_days

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            plan = self.env["clinic.insurance.plan"].browse(vals.get("plan_id"))
            if plan.exists():
                vals.setdefault("company_id", plan.company_id.id)
                vals.setdefault("insurer_partner_id", plan.insurer_partner_id.id)
                vals.setdefault("coverage_percent", plan.default_coverage_percent)
                vals.setdefault("copay_percent", plan.default_copay_percent)
                vals.setdefault("deductible_amount", plan.default_deductible_amount)
                vals.setdefault("annual_limit", plan.annual_limit)
                vals.setdefault("authorization_required", plan.authorization_required_default)
                vals.setdefault("authorization_valid_days", plan.authorization_valid_days)
                vals.setdefault("eligibility_valid_days", plan.eligibility_valid_days)

            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.insurance.policy")
                    or "/"
                )
        return super().create(vals_list)

    @api.constrains(
        "company_id",
        "patient_id",
        "plan_id",
        "insurer_partner_id",
        "authorization_valid_days",
        "eligibility_valid_days",
    )
    def _check_policy_scope(self):
        for record in self:
            if record.patient_id.company_id and record.patient_id.company_id != record.company_id:
                raise ValidationError(_("Patient and Insurance Policy must belong to the same company."))
            if record.plan_id.company_id != record.company_id:
                raise ValidationError(_("Insurance Plan and Policy company must match."))
            if record.plan_id.insurer_partner_id != record.insurer_partner_id:
                raise ValidationError(_("Insurance Policy payer must match the selected Plan payer."))
            if record.authorization_valid_days < 0 or record.eligibility_valid_days < 0:
                raise ValidationError(_("Policy validity-day settings cannot be negative."))

    def write(self, vals):
        system_fields = {"state", "verified_at", "verified_by_id"}
        core_fields = {
            "patient_id",
            "company_id",
            "insurer_partner_id",
            "plan_id",
            "policy_number",
            "start_date",
            "end_date",
        }
        if system_fields.intersection(vals) and not self.env.context.get("insurance_transition"):
            raise AccessError(_("Use Insurance Policy workflow actions to change status."))
        if core_fields.intersection(vals):
            for record in self:
                if record.state not in ("draft", "verified"):
                    raise UserError(_("Core Insurance Policy identity can only be edited in Draft or Verified."))

        coverage_fields = {
            "coverage_percent",
            "copay_percent",
            "deductible_amount",
            "annual_limit",
            "authorization_required",
            "authorization_valid_days",
            "eligibility_valid_days",
        }
        if coverage_fields.intersection(vals):
            for record in self:
                if record.state not in ("draft", "verified") and not self.env.user.has_group(
                    "clinic_insurance_authorization.group_clinic_insurance_manager"
                ):
                    raise AccessError(
                        _("Only an Insurance Manager can change coverage terms after Policy activation.")
                    )
        return super().write(vals)

    def action_verify(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can verify Policies."),
        )
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only Draft Policies can be verified."))
            if record.plan_id.state != "active":
                raise UserError(_("The selected Insurance Plan must be Active."))
            if not record.policy_number:
                raise UserError(_("Policy Number is required."))
            record.with_context(insurance_transition=True).write({
                "state": "verified",
                "verified_at": fields.Datetime.now(),
                "verified_by_id": self.env.user.id,
            })
        return True

    # Activation is deliberately separate from verification so payer evidence and coverage dates remain auditable.
    def action_activate(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can activate Policies."),
        )
        today = fields.Date.context_today(self)
        for record in self:
            if record.state != "verified":
                raise UserError(_("Verify the Policy before activation."))
            if record.start_date > today or (record.end_date and record.end_date < today):
                raise UserError(_("Policy coverage dates do not include today."))
            record.with_context(insurance_transition=True).write({"state": "active"})

            # Preserve the existing res.partner insurance_policy_id ownership
            # introduced upstream; populate it only when compatible and empty.
            partner = record.partner_id
            if partner and "insurance_policy_id" in partner._fields and not partner.insurance_policy_id:
                partner.insurance_policy_id = record.id
        return True

    def action_suspend(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_manager",
            _("Only an Insurance Manager can suspend Policies."),
        )
        for record in self:
            if record.state != "active":
                raise UserError(_("Only Active Policies can be suspended."))
            if not record.suspension_reason:
                raise UserError(_("Suspension Reason is required."))
            record.with_context(insurance_transition=True).write({"state": "suspended"})
        return True

    def action_cancel(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_manager",
            _("Only an Insurance Manager can cancel Policies."),
        )
        for record in self:
            if record.state == "cancelled":
                continue
            if not record.cancellation_reason:
                raise UserError(_("Cancellation Reason is required."))
            record.with_context(insurance_transition=True).write({"state": "cancelled"})
        return True

    def action_mark_expired(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can expire Policies."),
        )
        self.with_context(insurance_transition=True).write({"state": "expired"})
        return True

    def action_new_eligibility_check(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Eligibility Check"),
            "res_model": "clinic.insurance.eligibility.check",
            "view_mode": "form",
            "context": {
                "default_policy_id": self.id,
                "default_company_id": self.company_id.id,
                "default_branch_id": self.branch_id.id,
            },
        }

    def action_new_authorization(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Insurance Pre-Authorization"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "form",
            "context": {
                "default_policy_id": self.id,
                "default_patient_id": self.patient_id.id,
                "default_company_id": self.company_id.id,
                "default_branch_id": self.branch_id.id,
            },
        }

    def action_view_eligibility(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Eligibility Checks"),
            "res_model": "clinic.insurance.eligibility.check",
            "view_mode": "list,form",
            "domain": [("policy_id", "=", self.id)],
        }

    def action_view_authorizations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pre-Authorizations"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "list,form",
            "domain": [("policy_id", "=", self.id)],
        }

    def action_view_claims(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Claims"),
            "res_model": "clinic.insurance.claim",
            "view_mode": "list,form",
            "domain": [("policy_id", "=", self.id)],
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

    @api.model
    def _cron_expire_policies(self):
        today = fields.Date.context_today(self)
        expired = self.sudo().search([
            ("state", "in", ("verified", "active", "suspended")),
            ("end_date", "!=", False),
            ("end_date", "<", today),
        ])
        if expired:
            expired.with_context(insurance_transition=True).write({"state": "expired"})

