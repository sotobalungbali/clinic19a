from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicPostcareCheckin(models.Model):
    """Structured patient follow-up response; signals care attention, not diagnosis."""

    _name = "clinic.postcare.checkin"
    _description = "Clinic Post-Care Patient Check-in"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.postcare.company.mixin"]
    _order = "response_at desc, id desc"
    _check_company_auto = True

    _pain_range = models.Constraint(
        "CHECK(pain_score >= 0 AND pain_score <= 10)",
        "Pain score must be between 0 and 10.",
    )
    _plan_state_idx = models.Index("(company_id, plan_id, state, response_at)")
    _red_flag_idx = models.Index("(company_id, red_flag, state, response_at)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True)
    plan_id = fields.Many2one(
        "clinic.postcare.plan",
        required=True,
        check_company=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    task_id = fields.Many2one(
        "clinic.postcare.task",
        string="Follow-up Task",
        check_company=True,
        ondelete="set null",
        index=True,
        domain="[('plan_id', '=', plan_id)]",
    )
    patient_id = fields.Many2one(
        related="plan_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one(
        related="plan_id.partner_id",
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="plan_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    branch_id = fields.Many2one(
        related="plan_id.branch_id",
        store=True,
        readonly=True,
        index=True,
    )

    response_at = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True)
    channel = fields.Selection(
        [
            ("phone", "Phone"),
            ("email", "Email"),
            ("in_person", "In Person"),
            ("manual", "Manual Entry"),
        ],
        default="phone",
        required=True,
    )
    recorded_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("received", "Received"),
            ("reviewed", "Reviewed"),
            ("escalated", "Escalated"),
            ("closed", "Closed"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    wellbeing = fields.Selection(
        [
            ("improving", "Improving"),
            ("stable", "Stable"),
            ("concern", "Needs Attention"),
            ("red_flag", "Red-Flag Response"),
        ],
        default="stable",
        required=True,
        tracking=True,
    )
    pain_score = fields.Integer(default=0, tracking=True)
    fever_reported = fields.Boolean(tracking=True)
    unexpected_bleeding = fields.Boolean(tracking=True)
    breathing_concern = fields.Boolean(tracking=True)
    symptom_note = fields.Text()
    recovery_note = fields.Text()
    medication_note = fields.Text()

    manual_red_flag = fields.Boolean(
        string="Clinician Marks Red Flag",
        tracking=True,
    )
    red_flag = fields.Boolean(
        compute="_compute_red_flag",
        store=True,
        index=True,
    )
    red_flag_reason = fields.Text(compute="_compute_red_flag", store=True)

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_postcare_checkin_attachment_rel",
        "checkin_id",
        "attachment_id",
        string="Patient Evidence / Photos",
    )
    escalation_ids = fields.One2many(
        "clinic.postcare.escalation",
        "checkin_id",
        string="Escalations",
        copy=False,
    )
    escalation_count = fields.Integer(compute="_compute_escalation_count")

    @api.depends(
        "wellbeing",
        "pain_score",
        "fever_reported",
        "unexpected_bleeding",
        "breathing_concern",
        "manual_red_flag",
        "company_id.clinic_postcare_pain_red_flag_threshold",
    )
    # Attention signals support triage workflow; they are not diagnostic conclusions.
    def _compute_red_flag(self):
        for record in self:
            reasons = []
            threshold = (
                record.company_id.clinic_postcare_pain_red_flag_threshold or 8
            )
            if record.wellbeing == "red_flag":
                reasons.append(_("Patient response marked as red flag."))
            if record.pain_score >= threshold:
                reasons.append(
                    _("Pain score reached the configured attention threshold.")
                )
            if record.fever_reported:
                reasons.append(_("Fever was reported."))
            if record.unexpected_bleeding:
                reasons.append(_("Unexpected bleeding was reported."))
            if record.breathing_concern:
                reasons.append(_("Breathing concern was reported."))
            if record.manual_red_flag:
                reasons.append(_("Clinician manually marked this check-in as a red flag."))

            record.red_flag = bool(reasons)
            record.red_flag_reason = "\n".join(reasons)

    def _compute_escalation_count(self):
        for record in self:
            record.escalation_count = len(record.escalation_ids)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            plan = self.env["clinic.postcare.plan"].browse(vals.get("plan_id"))
            company = plan.company_id if plan.exists() else self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.postcare.checkin")
                    or "/"
                )
            prepared.append(vals)
        return super().create(prepared)

    @api.constrains("plan_id", "task_id", "company_id")
    def _check_checkin_scope(self):
        for record in self:
            if record.task_id and record.task_id.plan_id != record.plan_id:
                raise ValidationError(_("Check-in Task must belong to the same Post-Care Plan."))
            if record.plan_id.company_id != record.company_id:
                raise ValidationError(_("Check-in and Post-Care Plan company must match."))

    def write(self, vals):
        if "state" in vals and not self.env.context.get("postcare_transition"):
            raise AccessError(_("Use Check-in workflow actions to change status."))
        if self.filtered(lambda rec: rec.state in ("reviewed", "escalated", "closed")):
            protected = {
                "plan_id",
                "task_id",
                "patient_id",
                "response_at",
                "wellbeing",
                "pain_score",
                "fever_reported",
                "unexpected_bleeding",
                "breathing_concern",
                "manual_red_flag",
            }
            if protected.intersection(vals):
                raise UserError(_("Reviewed Post-Care clinical response evidence is immutable."))
        return super().write(vals)

    def action_mark_received(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_coordinator",
            _("Only Post-Care Coordinators can register received Check-ins."),
        )
        self.with_context(postcare_transition=True).write({"state": "received"})
        return True

    # Clinical review either closes routine evidence or routes attention signals into Escalation.
    def action_review(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_clinician",
            _("Only Post-Care Clinicians can review Check-ins."),
        )
        for record in self:
            if record.state not in ("draft", "received"):
                raise UserError(_("Only Draft/Received Check-ins can be reviewed."))
            if record.red_flag:
                record.action_escalate()
            else:
                record.with_context(postcare_transition=True).write({"state": "reviewed"})
                if record.task_id and record.task_id.response_required:
                    record.task_id.action_complete()
        return True

    # Escalation is internal to addon 26; future Incident integration is intentionally not assumed.
    def action_escalate(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_clinician",
            _("Only Post-Care Clinicians can escalate Check-ins."),
        )
        Escalation = self.env["clinic.postcare.escalation"]
        for record in self:
            existing = Escalation.search([
                ("checkin_id", "=", record.id),
                ("state", "not in", ("resolved", "cancelled")),
            ], limit=1)
            if not existing:
                Escalation.create({
                    "plan_id": record.plan_id.id,
                    "task_id": record.task_id.id or False,
                    "checkin_id": record.id,
                    "severity": "critical" if record.breathing_concern else "high",
                    "reason": record.red_flag_reason or _("Post-Care check-in needs clinical attention."),
                    "owner_staff_id": (
                        record.task_id.assignee_id.id
                        or record.plan_id.responsible_staff_id.id
                        or False
                    ),
                })
            record.with_context(postcare_transition=True).write({"state": "escalated"})
            if record.plan_id.state == "active":
                record.plan_id.with_context(postcare_transition=True).write({"state": "escalated"})
        return True

    def action_close(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_clinician",
            _("Only Post-Care Clinicians can close Check-ins."),
        )
        for record in self:
            open_escalations = record.escalation_ids.filtered(
                lambda esc: esc.state not in ("resolved", "cancelled")
            )
            if open_escalations:
                raise UserError(_("Resolve or cancel Check-in Escalations before closing."))
            record.with_context(postcare_transition=True).write({"state": "closed"})
        return True

    def action_open_plan(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Plan"),
            "res_model": "clinic.postcare.plan",
            "view_mode": "form",
            "res_id": self.plan_id.id,
        }
