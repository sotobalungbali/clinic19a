from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicPostcareProtocol(models.Model):
    """Reusable post-treatment instruction and timed follow-up template."""

    _name = "clinic.postcare.protocol"
    _description = "Clinic Post-Care Protocol"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.postcare.company.mixin"]
    _order = "sequence, name, id"
    _check_company_auto = True

    _code_company_unique = models.Constraint(
        "UNIQUE(company_id, code)",
        "Post-Care Protocol code must be unique per company.",
    )
    _default_days_nonnegative = models.Constraint(
        "CHECK(default_duration_days >= 0)",
        "Default Post-Care duration cannot be negative.",
    )
    _company_state_idx = models.Index("(company_id, state, sequence)")

    name = fields.Char(required=True, tracking=True, index=True)
    code = fields.Char(required=True, tracking=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    risk_level = fields.Selection(
        [
            ("routine", "Routine"),
            ("moderate", "Moderate"),
            ("high", "High"),
        ],
        default="routine",
        required=True,
        tracking=True,
    )

    treatment_catalog_ids = fields.Many2many(
        "clinic.treatment.catalog",
        "clinic_postcare_protocol_treatment_rel",
        "protocol_id",
        "treatment_catalog_id",
        string="Treatment Catalogs",
    )
    procedure_catalog_ids = fields.Many2many(
        "clinic.procedure.catalog",
        "clinic_postcare_protocol_procedure_rel",
        "protocol_id",
        "procedure_catalog_id",
        string="Procedure Catalogs",
    )
    care_protocol_id = fields.Many2one(
        "clinic.care.protocol",
        string="Care Protocol",
        check_company=True,
        ondelete="set null",
    )

    default_assignee_id = fields.Many2one(
        "clinic.staff",
        string="Default Follow-up Staff",
        check_company=True,
        domain="[('company_id', '=', company_id), ('is_active', '=', True)]",
    )
    default_duration_days = fields.Integer(default=14)
    auto_generate_tasks = fields.Boolean(default=True)
    instruction_html = fields.Html(
        string="Patient Post-Care Instructions",
        sanitize=True,
    )
    warning_signs_html = fields.Html(
        string="Warning Signs / When to Contact Clinic",
        sanitize=True,
    )
    emergency_instruction_html = fields.Html(
        string="Urgent / Emergency Instruction",
        sanitize=True,
        help="Patient-facing escalation wording. This is guidance only and does not replace clinical assessment.",
    )
    internal_note = fields.Text()

    step_ids = fields.One2many(
        "clinic.postcare.protocol.step",
        "protocol_id",
        string="Follow-up Steps",
        copy=True,
    )
    step_count = fields.Integer(compute="_compute_counts")
    plan_count = fields.Integer(compute="_compute_counts")

    @api.onchange("code")
    def _onchange_code_upper(self):
        for record in self:
            if record.code:
                record.code = record.code.strip().upper()

    @api.constrains("company_id", "default_assignee_id", "care_protocol_id")
    def _check_protocol_scope(self):
        for record in self:
            if record.default_assignee_id and record.default_assignee_id.company_id != record.company_id:
                raise ValidationError(_("Default Post-Care Staff must belong to the Protocol company."))
            if record.care_protocol_id and record.care_protocol_id.company_id != record.company_id:
                raise ValidationError(_("Care Protocol and Post-Care Protocol company must match."))

    def _compute_counts(self):
        Plan = self.env["clinic.postcare.plan"]
        for record in self:
            record.step_count = len(record.step_ids)
            record.plan_count = Plan.search_count([("protocol_id", "=", record.id)])

    def write(self, vals):
        if "state" in vals and not self.env.context.get("postcare_transition"):
            raise AccessError(_("Use Post-Care Protocol workflow actions to change status."))
        if self.filtered(lambda rec: rec.state == "active") and {
            "company_id",
            "code",
        }.intersection(vals):
            raise UserError(_("Archive an Active Protocol before changing its core identity."))
        return super().write(vals)

    # Activation freezes the Protocol identity used by future patient plans.
    def action_activate(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_manager",
            _("Only a Post-Care Manager can activate Protocols."),
        )
        for record in self:
            if not record.instruction_html and not record.step_ids:
                raise UserError(_("Add patient instructions or at least one follow-up step before activation."))
            record.with_context(postcare_transition=True).write({"state": "active"})
        return True

    def action_archive(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_manager",
            _("Only a Post-Care Manager can archive Protocols."),
        )
        self.with_context(postcare_transition=True).write({"state": "archived"})
        return True

    def action_reset_to_draft(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_manager",
            _("Only a Post-Care Manager can reset Protocols."),
        )
        self.with_context(postcare_transition=True).write({"state": "draft"})
        return True

    def action_view_plans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Plans"),
            "res_model": "clinic.postcare.plan",
            "view_mode": "list,form",
            "domain": [("protocol_id", "=", self.id)],
            "context": {"default_protocol_id": self.id, "default_company_id": self.company_id.id},
        }

    @api.model
    # Resolution prefers clinically specific mappings before any company-wide fallback.
    def resolve_protocol(
        self,
        company,
        treatment_catalog=False,
        procedure_catalogs=False,
        care_protocol=False,
    ):
        """Resolve specific protocol first, then company default, then generic active protocol."""
        company = company or self.env.company
        candidates = self.search([
            ("company_id", "=", company.id),
            ("state", "=", "active"),
            ("active", "=", True),
        ], order="sequence, id")

        if treatment_catalog:
            exact = candidates.filtered(lambda rec: treatment_catalog in rec.treatment_catalog_ids)
            if exact:
                return exact[:1]

        procedure_catalogs = procedure_catalogs or self.env["clinic.procedure.catalog"]
        if procedure_catalogs:
            exact = candidates.filtered(
                lambda rec: bool(rec.procedure_catalog_ids & procedure_catalogs)
            )
            if exact:
                return exact[:1]

        if care_protocol:
            exact = candidates.filtered(lambda rec: rec.care_protocol_id == care_protocol)
            if exact:
                return exact[:1]

        default = company.clinic_postcare_default_protocol_id
        if default and default.state == "active":
            return default

        generic = candidates.filtered(
            lambda rec:
                not rec.treatment_catalog_ids
                and not rec.procedure_catalog_ids
                and not rec.care_protocol_id
        )
        return generic[:1]


class ClinicPostcareProtocolStep(models.Model):
    """Timed step that becomes a concrete patient Post-Care Task."""

    _name = "clinic.postcare.protocol.step"
    _description = "Clinic Post-Care Protocol Step"
    _order = "protocol_id, sequence, id"
    _check_company_auto = True

    _delay_nonnegative = models.Constraint(
        "CHECK(delay_days >= 0 AND delay_hours >= 0 AND response_due_hours >= 0 AND escalation_after_hours >= 0)",
        "Post-Care timing values cannot be negative.",
    )
    _protocol_sequence_idx = models.Index("(protocol_id, sequence, active)")

    protocol_id = fields.Many2one(
        "clinic.postcare.protocol",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="protocol_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    name = fields.Char(required=True)
    task_type = fields.Selection(
        [
            ("instruction", "Care Instruction"),
            ("reminder", "Reminder"),
            ("checkin", "Patient Check-in"),
            ("call", "Follow-up Call"),
            ("medication", "Medication Follow-up"),
            ("wound", "Wound / Recovery Review"),
            ("review", "Clinical Review"),
        ],
        default="reminder",
        required=True,
        index=True,
    )
    channel = fields.Selection(
        [
            ("email", "Email"),
            ("phone", "Phone"),
            ("internal", "Internal Task"),
            ("manual", "Manual Contact"),
        ],
        default="email",
        required=True,
    )
    delay_days = fields.Integer(default=1)
    delay_hours = fields.Integer(default=0)
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Important"), ("2", "Urgent"), ("3", "Very Urgent")],
        default="0",
        required=True,
    )
    assignee_id = fields.Many2one(
        "clinic.staff",
        string="Assigned Staff",
        check_company=True,
        domain="[('company_id', '=', company_id), ('is_active', '=', True)]",
    )

    instruction_html = fields.Html(sanitize=True)
    requires_response = fields.Boolean(default=False)
    response_due_hours = fields.Integer(default=24)
    auto_send = fields.Boolean(
        default=True,
        help="Only Email steps are sent automatically. Phone/Internal/Manual steps become staff work items.",
    )
    escalate_if_overdue = fields.Boolean(default=True)
    escalation_after_hours = fields.Integer(default=24)
    escalation_severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
    )

    @api.constrains("assignee_id", "company_id", "channel", "auto_send")
    def _check_step_scope(self):
        for record in self:
            if record.assignee_id and record.assignee_id.company_id != record.company_id:
                raise ValidationError(_("Post-Care Step assignee must belong to the same company."))
            if record.auto_send and record.channel != "email":
                # Prevent the system from pretending an external/manual channel was delivered.
                raise ValidationError(_("Automatic sending is only supported for Email steps."))

    def action_open_protocol(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Protocol"),
            "res_model": "clinic.postcare.protocol",
            "view_mode": "form",
            "res_id": self.protocol_id.id,
        }
