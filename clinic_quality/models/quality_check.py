from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .scope_mixin import QUALITY_CHECK_TRANSITION_TOKEN


QUALITY_CHECK_STATES = [
    ("draft", "Draft"),
    ("in_progress", "In Progress"),
    ("review", "Review"),
    ("closed", "Closed"),
    ("cancelled", "Cancelled"),
]

QUALITY_RESULTS = [
    ("pending", "Pending"),
    ("conforming", "Conforming"),
    ("nonconforming", "Nonconforming"),
    ("critical_nonconformity", "Critical Nonconformity"),
    ("not_scored", "Not Scored"),
]


class ClinicQualityCheck(models.Model):
    """Executable compliance check with immutable closed evidence."""

    _name = "clinic.quality.check"
    _description = "Clinic Quality Compliance Check"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.quality.scope.mixin",
    ]
    _order = "planned_date desc, id desc"
    _check_company_auto = True

    _target_range = models.Constraint(
        "CHECK(target_score >= 0 AND target_score <= 100)",
        "Quality Check Target Score must be between 0 and 100.",
    )
    _company_state_idx = models.Index(
        "(company_id, state, planned_date, overall_result)"
    )
    _template_state_idx = models.Index(
        "(template_id, state, planned_date)"
    )

    name = fields.Char(
        string="Quality Check Reference",
        required=True,
        default="/",
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
    )
    title = fields.Char(
        required=True,
        index=True,
        tracking=True,
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    template_id = fields.Many2one(
        "clinic.quality.check.template",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    sop_version_id = fields.Many2one(
        "clinic.quality.sop.version",
        string="Governing SOP Version",
        ondelete="restrict",
        readonly=True,
        index=True,
    )
    schedule_id = fields.Many2one(
        "clinic.quality.schedule",
        ondelete="set null",
        readonly=True,
        index=True,
    )

    state = fields.Selection(
        QUALITY_CHECK_STATES,
        default="draft",
        required=True,
        readonly=True,
        index=True,
        tracking=True,
    )
    target_score = fields.Float(
        string="Compliance Target (%)",
        required=True,
        readonly=True,
        tracking=True,
    )
    overall_result = fields.Selection(
        QUALITY_RESULTS,
        compute="_compute_quality_results",
        store=True,
        index=True,
    )
    compliance_score = fields.Float(
        compute="_compute_quality_results",
        store=True,
        string="Compliance Score (%)",
    )
    evaluated_count = fields.Integer(
        compute="_compute_quality_results",
        store=True,
    )
    pass_count = fields.Integer(
        compute="_compute_quality_results",
        store=True,
    )
    fail_count = fields.Integer(
        compute="_compute_quality_results",
        store=True,
    )
    critical_fail_count = fields.Integer(
        compute="_compute_quality_results",
        store=True,
    )
    pending_count = fields.Integer(
        compute="_compute_quality_results",
        store=True,
    )
    observation_count = fields.Integer(
        compute="_compute_quality_results",
        store=True,
    )

    planned_date = fields.Date(
        required=True,
        default=fields.Date.today,
        index=True,
        tracking=True,
    )
    started_at = fields.Datetime(readonly=True)
    submitted_at = fields.Datetime(readonly=True)
    closed_at = fields.Datetime(readonly=True)

    performed_by_user_id = fields.Many2one(
        "res.users",
        string="Inspector",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        tracking=True,
    )
    reviewed_by_user_id = fields.Many2one(
        "res.users",
        string="Reviewer / Approver",
        index=True,
        tracking=True,
    )
    closed_by_user_id = fields.Many2one(
        "res.users",
        readonly=True,
    )

    note = fields.Text(
        string="Check Notes",
    )
    review_summary = fields.Text()
    cancellation_reason = fields.Text()

    line_ids = fields.One2many(
        "clinic.quality.check.line",
        "check_id",
        string="Quality Controls",
    )
    incident_ids = fields.One2many(
        "clinic.incident",
        "quality_check_id",
        string="Incident Cases",
        readonly=True,
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count",
    )

    @api.depends(
        "line_ids.result",
        "line_ids.weight",
        "line_ids.critical",
        "target_score",
    )
    def _compute_quality_results(self):
        for check in self:
            lines = check.line_ids
            pending = lines.filtered(
                lambda line: line.result == "pending"
            )
            passed = lines.filtered(
                lambda line: line.result == "pass"
            )
            failed = lines.filtered(
                lambda line: line.result == "fail"
            )
            observations = lines.filtered(
                lambda line: line.result == "observation"
            )
            evaluated = passed | failed

            denominator = sum(evaluated.mapped("weight"))
            numerator = sum(passed.mapped("weight"))
            score = (
                numerator / denominator * 100.0
                if denominator
                else 0.0
            )

            if pending:
                result = "pending"
            elif failed.filtered("critical"):
                result = "critical_nonconformity"
            elif failed:
                result = "nonconforming"
            elif evaluated:
                result = (
                    "conforming"
                    if score >= check.target_score
                    else "nonconforming"
                )
            else:
                result = "not_scored"

            check.pending_count = len(pending)
            check.pass_count = len(passed)
            check.fail_count = len(failed)
            check.critical_fail_count = len(
                failed.filtered("critical")
            )
            check.observation_count = len(observations)
            check.evaluated_count = len(evaluated)
            check.compliance_score = score
            check.overall_result = result

    def _compute_incident_count(self):
        for check in self:
            check.incident_count = len(check.incident_ids)

    @api.model_create_multi
    def create(self, vals_list):
        self._quality_require_inspector()

        prepared = []
        for original in vals_list:
            vals = dict(original)
            template = self.env[
                "clinic.quality.check.template"
            ].browse(vals.get("template_id")).exists()

            if not template or template.state != "active":
                raise ValidationError(
                    _("A valid Active Quality Template is required.")
                )

            company = template.company_id
            vals["company_id"] = company.id
            vals.setdefault("scope_type", template.scope_type)
            vals.setdefault(
                "target_score",
                template.target_score,
            )
            vals.setdefault(
                "sop_version_id",
                template.sop_version_id.id
                if template.sop_version_id
                else False,
            )
            vals.setdefault(
                "reviewed_by_user_id",
                company.clinic_quality_default_approver_id.id
                if company.clinic_quality_default_approver_id
                else False,
            )
            vals.setdefault(
                "title",
                _("%(template)s — %(date)s") % {
                    "template": template.name,
                    "date": vals.get("planned_date")
                    or fields.Date.today(),
                },
            )

            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.quality.check")
                    or "/"
                )

            prepared.append(vals)

        checks = super().create(prepared)
        checks._check_quality_check_contract()
        return checks

    def write(self, vals):
        vals = dict(vals)

        transition_fields = {
            "state",
            "started_at",
            "submitted_at",
            "closed_at",
            "closed_by_user_id",
        }
        if (
            transition_fields.intersection(vals)
            and not self.env.context.get("quality_check_transition") is QUALITY_CHECK_TRANSITION_TOKEN
        ):
            raise AccessError(
                _("Use Quality Check workflow actions to change lifecycle.")
            )

        if self.filtered(
            lambda check:
            check.state in ("closed", "cancelled")
        ) and not self.env.context.get("quality_check_transition") is QUALITY_CHECK_TRANSITION_TOKEN:
            allowed = {"active"}
            if not set(vals).issubset(allowed):
                raise AccessError(
                    _("Closed/Cancelled Quality Checks are read-only.")
                )

        identity_fields = {
            "company_id",
            "branch_id",
            "template_id",
            "sop_version_id",
            "schedule_id",
            "scope_type",
            "room_id",
            "staff_id",
            "doctor_id",
            "stock_lot_id",
            "treatment_id",
            "planned_date",
            "target_score",
        }
        if (
            identity_fields.intersection(vals)
            and self.filtered(
                lambda check: check.state != "draft"
            )
            and not self.env.context.get("quality_check_transition") is QUALITY_CHECK_TRANSITION_TOKEN
        ):
            raise AccessError(
                _(
                    "Quality Check scope/template identity is locked "
                    "after work starts."
                )
            )

        if not self.env.context.get("quality_check_transition") is QUALITY_CHECK_TRANSITION_TOKEN:
            self._quality_require_inspector()

        result = super().write(vals)
        self._check_quality_check_contract()
        return result

    def unlink(self):
        self._quality_require_manager()

        if self.filtered(
            lambda check:
            check.state not in ("draft", "cancelled")
        ):
            raise UserError(
                _(
                    "Only Draft/Cancelled Quality Checks may be deleted. "
                    "Preserve governed evidence otherwise."
                )
            )
        return super().unlink()

    @api.constrains(
        "template_id",
        "sop_version_id",
        "company_id",
        "branch_id",
        "scope_type",
        "performed_by_user_id",
        "reviewed_by_user_id",
        "target_score",
    )
    def _check_quality_check_contract(self):
        for check in self:
            check._check_quality_scope()

            if check.template_id.company_id != check.company_id:
                raise ValidationError(
                    _("Quality Template belongs to another company.")
                )

            if (
                check.company_id.policy_branch_scope_incident_event
                and not check.branch_id
            ):
                raise ValidationError(
                    _(
                        "This company requires Branch scope for Incident "
                        "governance. Select a Quality Branch so a future "
                        "nonconformity can be escalated safely."
                    )
                )

            if check.scope_type != check.template_id.scope_type:
                raise ValidationError(
                    _(
                        "Quality Check Scope Type must match "
                        "the Template Scope Type."
                    )
                )

            if check.template_id.branch_ids and not check.branch_id:
                raise ValidationError(
                    _(
                        "This Template is Branch-restricted. "
                        "Select one of its Applicable Branches."
                    )
                )
            if (
                check.template_id.branch_ids
                and check.branch_id not in check.template_id.branch_ids
            ):
                raise ValidationError(
                    _(
                        "Quality Check Branch is not within "
                        "the Template applicability."
                    )
                )

            if (
                check.sop_version_id
                and check.template_id.sop_version_id
                and check.sop_version_id
                != check.template_id.sop_version_id
            ):
                raise ValidationError(
                    _(
                        "Quality Check SOP Version must match "
                        "the activated Template snapshot."
                    )
                )

            for role_name, user in (
                (_("Inspector"), check.performed_by_user_id),
                (_("Reviewer / Approver"), check.reviewed_by_user_id),
            ):
                if user and check.company_id not in user.company_ids:
                    raise ValidationError(
                        _(
                            "%(role)s does not have access "
                            "to the Quality Check company."
                        ) % {"role": role_name}
                    )

            if check.performed_by_user_id and not check.performed_by_user_id.has_group(
                "clinic_quality.group_quality_inspector"
            ):
                raise ValidationError(
                    _("Inspector must belong to the Quality Inspector role.")
                )
            if check.reviewed_by_user_id and not check.reviewed_by_user_id.has_group(
                "clinic_quality.group_quality_approver"
            ):
                raise ValidationError(
                    _(
                        "Reviewer / Approver must belong to the "
                        "Quality Approver role."
                    )
                )

            if not 0.0 <= check.target_score <= 100.0:
                raise ValidationError(
                    _("Compliance Target must be between 0 and 100.")
                )
