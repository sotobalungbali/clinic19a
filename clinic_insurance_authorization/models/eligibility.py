from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicInsuranceEligibilityCheck(models.Model):
    """Persistent insurance eligibility evidence for a patient Policy."""

    _name = "clinic.insurance.eligibility.check"
    _description = "Clinic Insurance Eligibility Check"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.insurance.company.mixin"]
    _order = "checked_at desc, id desc"
    _check_company_auto = True

    _validity_order = models.Constraint(
        "CHECK(valid_until IS NULL OR checked_date IS NULL OR checked_date <= valid_until)",
        "Eligibility validity date cannot be earlier than the check date.",
    )
    _policy_state_idx = models.Index("(company_id, policy_id, state, valid_until)")
    # Insurance desks frequently review all current eligibility evidence for a
    # patient, not only a single Policy; keep that operational queue indexed.
    _patient_state_idx = models.Index("(company_id, patient_id, state, valid_until)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    policy_id = fields.Many2one(
        "clinic.insurance.policy",
        required=True,
        check_company=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    patient_id = fields.Many2one(
        related="policy_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one(
        related="policy_id.partner_id",
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

    requested_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    checked_at = fields.Datetime(readonly=True, tracking=True)
    checked_date = fields.Date(compute="_compute_checked_date", store=True)
    valid_until = fields.Date(tracking=True, index=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending"),
            ("eligible", "Eligible"),
            ("ineligible", "Ineligible"),
            ("error", "Error"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    verification_method = fields.Selection(
        [
            ("internal", "Internal Policy Validation"),
            ("portal", "Payer Portal"),
            ("phone", "Phone / Call Center"),
            ("email", "Email"),
            ("api", "API / EDI"),
            ("other", "Other"),
        ],
        default="internal",
        required=True,
        tracking=True,
    )
    external_reference = fields.Char(index=True)
    coverage_status_text = fields.Char()
    response_code = fields.Char()
    response_message = fields.Text()
    error_message = fields.Text()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_insurance_eligibility_attachment_rel",
        "eligibility_id",
        "attachment_id",
        string="Eligibility Evidence",
    )

    @api.depends("checked_at")
    def _compute_checked_date(self):
        for record in self:
            record.checked_date = (
                fields.Date.to_date(record.checked_at) if record.checked_at else False
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            policy = self.env["clinic.insurance.policy"].browse(vals.get("policy_id"))
            if policy.exists():
                vals.setdefault("company_id", policy.company_id.id)
                vals.setdefault("branch_id", policy.branch_id.id)
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.insurance.eligibility.check")
                    or "/"
                )
        return super().create(vals_list)

    @api.constrains("policy_id", "company_id")
    def _check_policy_company(self):
        for record in self:
            if record.policy_id.company_id != record.company_id:
                raise ValidationError(_("Eligibility Check and Insurance Policy company must match."))

    def write(self, vals):
        system_fields = {"state", "checked_at"}
        scope_fields = {"policy_id", "company_id", "branch_id"}
        if system_fields.intersection(vals) and not self.env.context.get("insurance_transition"):
            raise AccessError(_("Use Eligibility workflow actions to change status."))
        if scope_fields.intersection(vals):
            for record in self:
                if record.state not in ("draft", "cancelled"):
                    raise UserError(_("Eligibility scope can only be edited in Draft or Cancelled."))
        return super().write(vals)

    # Internal validation confirms ClinicOne Policy/date consistency only; it never pretends an external payer API was contacted.
    def action_check_internal(self):
        """Perform deterministic policy/date checks without pretending to contact a payer."""
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can run eligibility checks."),
        )
        today = fields.Date.context_today(self)
        for record in self:
            policy = record.policy_id
            eligible = (
                policy.state == "active"
                and policy.start_date <= today
                and (not policy.end_date or policy.end_date >= today)
            )
            valid_days = policy.eligibility_valid_days or 0
            record.with_context(insurance_transition=True).write({
                "checked_at": fields.Datetime.now(),
                "valid_until": today + timedelta(days=valid_days),
                "state": "eligible" if eligible else "ineligible",
                "verification_method": "internal",
                "coverage_status_text": (
                    _("Policy is active and within coverage dates.")
                    if eligible
                    else _("Policy is not active or outside coverage dates.")
                ),
                "response_code": "INTERNAL-ELIGIBLE" if eligible else "INTERNAL-INELIGIBLE",
            })
        return True

    def action_mark_pending(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can submit eligibility checks."),
        )
        self.with_context(insurance_transition=True).write({"state": "pending"})
        return True

    # Manual payer decisions require Adjudicator authority and create persistent eligibility evidence.
    def action_mark_eligible(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_adjudicator",
            _("Only Insurance Adjudicators can record payer eligibility decisions."),
        )
        today = fields.Date.context_today(self)
        for record in self:
            valid_days = record.policy_id.eligibility_valid_days or 0
            record.with_context(insurance_transition=True).write({
                "state": "eligible",
                "checked_at": fields.Datetime.now(),
                "valid_until": record.valid_until or today + timedelta(days=valid_days),
            })
        return True

    def action_mark_ineligible(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_adjudicator",
            _("Only Insurance Adjudicators can record payer eligibility decisions."),
        )
        self.with_context(insurance_transition=True).write({
            "state": "ineligible",
            "checked_at": fields.Datetime.now(),
        })
        return True

    def action_mark_error(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can mark eligibility errors."),
        )
        for record in self:
            if not record.error_message:
                raise UserError(_("Error Message is required."))
            record.with_context(insurance_transition=True).write({
                "state": "error",
                "checked_at": fields.Datetime.now(),
            })
        return True

    def action_cancel(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_coordinator",
            _("Only Insurance staff can cancel eligibility checks."),
        )
        self.with_context(insurance_transition=True).write({"state": "cancelled"})
        return True

    def action_open_policy(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Policy"),
            "res_model": "clinic.insurance.policy",
            "view_mode": "form",
            "res_id": self.policy_id.id,
        }

    @api.model
    def _cron_expire_eligibility(self):
        today = fields.Date.context_today(self)
        expired = self.sudo().search([
            ("state", "=", "eligible"),
            ("valid_until", "!=", False),
            ("valid_until", "<", today),
        ])
        if expired:
            expired.with_context(insurance_transition=True).write({"state": "expired"})

