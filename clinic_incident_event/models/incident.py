from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .category import INCIDENT_TYPES, SEVERITIES


INCIDENT_STATES = [
    ("draft", "Draft"),
    ("reported", "Reported"),
    ("triage", "Triage"),
    ("investigation", "Investigation"),
    ("action_plan", "Action Plan"),
    ("verification", "Verification"),
    ("closed", "Closed"),
    ("cancelled", "Cancelled"),
]

CLASSIFICATIONS = [
    ("near_miss", "Near Miss"),
    ("no_harm", "No Harm Incident"),
    ("adverse_event", "Adverse Event"),
    ("sentinel", "Sentinel Event"),
    ("operational", "Operational / Non-Clinical"),
]

HARM_LEVELS = [
    ("none", "No Harm"),
    ("minor", "Minor Harm"),
    ("moderate", "Moderate Harm"),
    ("severe", "Severe Harm"),
    ("death", "Death"),
]

RECURRENCE_RISKS = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]


class ClinicIncident(models.Model):
    """Central Incident/Compliance case.

    Existing clinical Adverse Event ownership remains in `clinic_encounter`.
    This model provides cross-functional incident investigation, CAPA,
    compliance evidence, and source provenance.
    """

    _name = "clinic.incident"
    _description = "Clinic Incident / Event"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "occurred_at desc, severity desc, id desc"
    _check_company_auto = True

    _adverse_event_unique = models.Constraint(
        "UNIQUE(adverse_event_id)",
        "An Adverse Event can be linked to only one Incident case.",
    )
    _company_state_idx = models.Index(
        "(company_id, state, occurred_at, severity)"
    )

    name = fields.Char(
        string="Incident Reference",
        required=True,
        default="/",
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
    )
    title = fields.Char(required=True, index=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    allowed_branch_ids = fields.Many2many(
        "clinic.branch",
        compute="_compute_allowed_branch_ids",
        string="Allowed Branches",
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        domain="[('id', 'in', allowed_branch_ids)]",
        index=True,
        tracking=True,
        check_company=True,
    )
    category_id = fields.Many2one(
        "clinic.incident.category",
        required=True,
        domain=(
            "['&', ('active', '=', True), '|', "
            "('company_id', '=', False), ('company_id', '=', company_id)]"
        ),
        index=True,
        tracking=True,
    )

    incident_type = fields.Selection(
        INCIDENT_TYPES,
        required=True,
        default="other",
        index=True,
        tracking=True,
    )
    classification = fields.Selection(
        CLASSIFICATIONS,
        required=True,
        default="operational",
        index=True,
        tracking=True,
    )
    severity = fields.Selection(
        SEVERITIES,
        required=True,
        default="medium",
        index=True,
        tracking=True,
    )
    harm_level = fields.Selection(
        HARM_LEVELS,
        default="none",
        required=True,
        index=True,
        tracking=True,
    )
    recurrence_risk = fields.Selection(
        RECURRENCE_RISKS,
        default="low",
        required=True,
        index=True,
        tracking=True,
    )

    state = fields.Selection(
        INCIDENT_STATES,
        default="draft",
        required=True,
        readonly=True,
        index=True,
        tracking=True,
    )

    occurred_at = fields.Datetime(
        string="Occurred At",
        required=True,
        default=fields.Datetime.now,
        index=True,
        tracking=True,
        help="Historical Clinic Staff contract field.",
    )
    detected_at = fields.Datetime(index=True)
    reported_at = fields.Datetime(readonly=True, index=True)

    reported_by_user_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    reported_by_staff_id = fields.Many2one(
        "clinic.staff",
        string="Reporter Staff",
        ondelete="set null",
        index=True,
    )
    case_owner_id = fields.Many2one(
        "res.users",
        string="Case Owner",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    reviewer_id = fields.Many2one(
        "res.users",
        string="Reviewer / Approver",
        ondelete="set null",
        index=True,
        tracking=True,
    )

    patient_id = fields.Many2one(
        "clinic.patient",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        related="patient_id.partner_id",
        string="Patient Contact",
        store=True,
        readonly=True,
        index=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    involved_staff_ids = fields.Many2many(
        "clinic.staff",
        "clinic_incident_staff_rel",
        "incident_id",
        "staff_id",
        string="Involved Staff",
        help="Historical Clinic Staff contract field.",
    )
    room_id = fields.Many2one(
        "clinic.room",
        ondelete="set null",
        index=True,
    )

    encounter_id = fields.Many2one(
        "clinic.encounter",
        ondelete="set null",
        index=True,
    )
    adverse_event_id = fields.Many2one(
        "clinic.adverse.event",
        string="Source Adverse Event",
        ondelete="restrict",
        index=True,
        help=(
            "Existing clinical Adverse Event remains owned by clinic_encounter. "
            "This Incident adds central compliance governance."
        ),
    )
    booking_id = fields.Many2one(
        "booking.booking",
        ondelete="set null",
        index=True,
    )
    queue_id = fields.Many2one(
        "clinic.queue",
        ondelete="set null",
        index=True,
    )
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration",
        string="eMAR Administration",
        ondelete="set null",
        index=True,
    )
    telemedicine_session_id = fields.Many2one(
        "clinic.telemedicine.session",
        ondelete="set null",
        index=True,
    )
    telemedicine_thread_id = fields.Many2one(
        "clinic.telemedicine.thread",
        ondelete="set null",
        index=True,
    )
    feedback_escalation_id = fields.Many2one(
        "clinic.feedback.escalation",
        ondelete="set null",
        index=True,
    )

    description = fields.Html(
        string="Incident Narrative",
        required=True,
        help="Factual description of what happened.",
    )
    immediate_action = fields.Text(
        string="Immediate / Containment Action",
    )
    patient_impact = fields.Text()
    reporter_note = fields.Text()
    root_cause_summary = fields.Text(readonly=True)
    resolution_summary = fields.Text()

    regulatory_required = fields.Boolean(
        string="Regulatory Reporting Required",
        tracking=True,
    )
    reportability_reviewed = fields.Boolean(
        string="Reportability Reviewed",
        readonly=True,
        tracking=True,
    )
    regulator_body = fields.Char()
    regulator_reference = fields.Char(index=True)
    regulator_reported_at = fields.Datetime(readonly=True, index=True)

    triage_due_at = fields.Datetime(readonly=True, index=True)
    investigation_due_at = fields.Datetime(readonly=True, index=True)
    action_plan_due_at = fields.Datetime(readonly=True, index=True)

    closed_at = fields.Datetime(readonly=True)
    closed_by_id = fields.Many2one("res.users", readonly=True)
    cancellation_reason = fields.Text()

    investigation_ids = fields.One2many(
        "clinic.incident.investigation",
        "incident_id",
        string="Investigations",
        readonly=True,
    )
    action_ids = fields.One2many(
        "clinic.incident.action",
        "incident_id",
        string="Corrective / Preventive Actions",
        readonly=True,
    )
    timeline_ids = fields.One2many(
        "clinic.incident.timeline",
        "incident_id",
        string="Timeline",
        readonly=True,
    )

    investigation_count = fields.Integer(
        compute="_compute_counts",
        store=True,
    )
    completed_investigation_count = fields.Integer(
        compute="_compute_counts",
        store=True,
    )
    action_count = fields.Integer(
        compute="_compute_counts",
        store=True,
    )
    open_action_count = fields.Integer(
        compute="_compute_counts",
        store=True,
    )
    timeline_count = fields.Integer(
        compute="_compute_counts",
        store=True,
    )
    is_overdue = fields.Boolean(compute="_compute_is_overdue")
    is_serious = fields.Boolean(
        compute="_compute_risk_flags",
        store=True,
        index=True,
    )
    needs_regulatory_review = fields.Boolean(
        compute="_compute_risk_flags",
        store=True,
        index=True,
    )

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_allowed_branch_ids(self):
        Branch = self.env["clinic.branch"].sudo()
        user = self.env.user
        for incident in self:
            company = incident.company_id or self.env.company
            allowed = user.sudo().allowed_branch_ids.filtered(
                lambda branch: branch.company_id == company
            )
            if not allowed:
                allowed = Branch.search([
                    ("company_id", "=", company.id),
                ])
            incident.allowed_branch_ids = allowed

    @api.depends(
        "investigation_ids",
        "investigation_ids.state",
        "action_ids",
        "action_ids.state",
        "timeline_ids",
    )
    def _compute_counts(self):
        for incident in self:
            incident.investigation_count = len(incident.investigation_ids)
            incident.completed_investigation_count = len(
                incident.investigation_ids.filtered(
                    lambda investigation:
                    investigation.state == "completed"
                )
            )
            incident.action_count = len(incident.action_ids)
            incident.open_action_count = len(
                incident.action_ids.filtered(
                    lambda action:
                    action.state not in ("verified", "cancelled")
                )
            )
            incident.timeline_count = len(incident.timeline_ids)

    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for incident in self:
            due = False
            if incident.state in ("reported", "triage"):
                due = incident.triage_due_at
            elif incident.state == "investigation":
                due = incident.investigation_due_at
            elif incident.state == "action_plan":
                due = incident.action_plan_due_at
            incident.is_overdue = bool(due and due < now)

    @api.depends(
        "severity",
        "classification",
        "harm_level",
        "category_id.requires_regulatory_review",
        "regulatory_required",
    )
    def _compute_risk_flags(self):
        for incident in self:
            serious = bool(
                incident.severity in ("high", "critical")
                or incident.classification == "sentinel"
                or incident.harm_level in ("severe", "death")
            )
            incident.is_serious = serious
            incident.needs_regulatory_review = bool(
                serious
                or incident.regulatory_required
                or incident.category_id.requires_regulatory_review
            )

    @api.onchange("category_id")
    def _onchange_category_id(self):
        for incident in self:
            category = incident.category_id
            if not category:
                continue
            incident.incident_type = category.incident_type
            incident.severity = category.default_severity
            if category.requires_regulatory_review:
                incident.regulatory_required = True

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            company = (
                self.env["res.company"].browse(vals.get("company_id")).exists()
                or self.env.company
            )

            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.incident")
                    or "/"
                )

            if not vals.get("reported_by_staff_id"):
                reporter_staff = self.env["clinic.staff"].search([
                    ("partner_id", "=", self.env.user.partner_id.id),
                    ("company_id", "=", company.id),
                ], limit=1)
                if reporter_staff:
                    vals["reported_by_staff_id"] = reporter_staff.id

            if (
                not vals.get("case_owner_id")
                and company.clinic_incident_default_case_owner_id
            ):
                vals["case_owner_id"] = (
                    company.clinic_incident_default_case_owner_id.id
                )

            category = self.env["clinic.incident.category"].browse(
                vals.get("category_id")
            ).exists()
            if category:
                category._check_company_scope(company)
                vals.setdefault("incident_type", category.incident_type)
                vals.setdefault("severity", category.default_severity)
                if category.requires_regulatory_review:
                    vals["regulatory_required"] = True

            if (
                company.policy_branch_scope_incident_event
                and not vals.get("branch_id")
            ):
                branch = self._default_incident_branch(
                    company,
                    patient_id=vals.get("patient_id"),
                )
                if branch:
                    vals["branch_id"] = branch.id

            prepared.append(vals)

        records = super().create(prepared)
        records._check_scope_consistency()
        for incident in records:
            incident._log_timeline(
                "created",
                _("Incident Created"),
                _("Incident case created by %(user)s.") % {
                    "user": self.env.user.display_name,
                },
            )
        return records

    def write(self, vals):
        vals = dict(vals)

        if (
            not self.env.su
            and self.filtered(
                lambda incident:
                incident.state not in ("draft", "reported")
            )
            and not self.env.user.has_group(
                "clinic_incident_event.group_incident_investigator"
            )
        ):
            raise AccessError(
                _(
                    "Incident Investigator access is required to edit a case "
                    "after Triage has started."
                )
            )

        if (
            "state" in vals
            and not self.env.context.get("incident_transition")
        ):
            raise AccessError(
                _("Use Incident workflow actions to change status.")
            )

        if self.filtered(
            lambda incident:
            incident.state in ("closed", "cancelled")
        ) and not self.env.context.get("incident_transition"):
            allowed = {"active"}
            if not set(vals).issubset(allowed):
                raise AccessError(
                    _("Closed or Cancelled Incident cases are read-only.")
                )

        identity_fields = {
            "company_id",
            "branch_id",
            "patient_id",
            "encounter_id",
            "adverse_event_id",
            "booking_id",
            "queue_id",
            "emar_administration_id",
            "telemedicine_session_id",
            "telemedicine_thread_id",
            "feedback_escalation_id",
            "occurred_at",
        }
        if (
            identity_fields.intersection(vals)
            and self.filtered(
                lambda incident:
                incident.state not in ("draft", "reported")
            )
            and not self.env.context.get("incident_transition")
        ):
            raise AccessError(
                _(
                    "Incident identity/source fields are locked after "
                    "the case enters Triage."
                )
            )

        result = super().write(vals)
        self._check_scope_consistency()
        return result

    def unlink(self):
        if not self.env.su:
            self._require_manager()
            if self.filtered(
                lambda incident:
                incident.state not in ("draft", "cancelled")
            ):
                raise UserError(
                    _(
                        "Only Draft or Cancelled Incident cases may be deleted. "
                        "Preserve compliance evidence otherwise."
                    )
                )
        return super().unlink()
