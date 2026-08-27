from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .scope_mixin import QUALITY_TEMPLATE_TRANSITION_TOKEN


QUALITY_INCIDENT_TYPES = [
    ("clinical_adverse", "Clinical Adverse Event"),
    ("medication", "Medication Safety"),
    ("device", "Device / Equipment"),
    ("fall", "Patient Fall"),
    ("infection", "Infection Prevention"),
    ("privacy", "Privacy / Information Security"),
    ("staff_safety", "Staff Safety"),
    ("facility", "Facility / Environment"),
    ("telemedicine", "Telemedicine"),
    ("service", "Service / Communication"),
    ("operational", "Operational"),
    ("other", "Other"),
]

QUALITY_TEMPLATE_STATES = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("retired", "Retired"),
]


class ClinicQualityCheckTemplate(models.Model):
    """Governed reusable compliance-check definition."""

    _name = "clinic.quality.check.template"
    _description = "Clinic Quality Check Template"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.quality.security.mixin",
    ]
    _order = "code, name, id"
    _check_company_auto = True

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)",
        "Quality Check Template Code must be unique per company.",
    )
    _threshold_range = models.Constraint(
        "CHECK(target_score >= 0 AND target_score <= 100)",
        "Compliance Target Score must be between 0 and 100.",
    )
    _company_state_idx = models.Index(
        "(company_id, state, scope_type)"
    )

    name = fields.Char(
        required=True,
        index=True,
        tracking=True,
    )
    code = fields.Char(
        required=True,
        index=True,
        tracking=True,
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_ids = fields.Many2many(
        "clinic.branch",
        "clinic_quality_tpl_branch_rel",
        "template_id",
        "branch_id",
        string="Applicable Branches",
        help="Leave empty for company-wide applicability.",
    )
    state = fields.Selection(
        QUALITY_TEMPLATE_STATES,
        default="draft",
        required=True,
        readonly=True,
        index=True,
        tracking=True,
    )

    sop_id = fields.Many2one(
        "clinic.quality.sop",
        string="Governing SOP",
        ondelete="restrict",
        index=True,
    )
    sop_version_id = fields.Many2one(
        "clinic.quality.sop.version",
        string="Approved SOP Version",
        ondelete="restrict",
        index=True,
        readonly=True,
        help=(
            "Frozen when the template is activated so future checks can prove "
            "which approved SOP version governed the controls."
        ),
    )

    scope_type = fields.Selection(
        [
            ("organization", "Organization / Clinic"),
            ("branch", "Branch"),
            ("room", "Room"),
            ("staff", "Staff"),
            ("doctor", "Doctor"),
            ("inventory_lot", "Inventory Lot / Batch"),
            ("treatment", "Treatment / Service"),
        ],
        required=True,
        default="organization",
        index=True,
        tracking=True,
    )
    target_score = fields.Float(
        string="Compliance Target (%)",
        required=True,
        default=lambda self: (
            self.env.company.clinic_quality_default_pass_threshold
        ),
        tracking=True,
    )
    failure_incident_type = fields.Selection(
        QUALITY_INCIDENT_TYPES,
        string="Incident Type for Escalated Failure",
        default="operational",
        required=True,
        tracking=True,
    )
    require_evidence_on_failure = fields.Boolean(
        default=True,
        help=(
            "When enabled, every failed control requires an Evidence Note "
            "before the Quality Check can be submitted for review."
        ),
    )

    objective = fields.Text()
    instructions = fields.Text()
    reference = fields.Char(
        help="Optional policy, regulation, accreditation or internal reference."
    )

    line_ids = fields.One2many(
        "clinic.quality.check.template.line",
        "template_id",
        string="Controls",
    )
    check_ids = fields.One2many(
        "clinic.quality.check",
        "template_id",
        string="Quality Checks",
        readonly=True,
    )
    schedule_ids = fields.One2many(
        "clinic.quality.schedule",
        "template_id",
        string="Schedules",
        readonly=True,
    )

    line_count = fields.Integer(
        compute="_compute_quality_counts",
    )
    check_count = fields.Integer(
        compute="_compute_quality_counts",
    )
    schedule_count = fields.Integer(
        compute="_compute_quality_counts",
    )

    @api.depends("line_ids", "check_ids", "schedule_ids")
    def _compute_quality_counts(self):
        for template in self:
            template.line_count = len(template.line_ids)
            template.check_count = len(template.check_ids)
            template.schedule_count = len(template.schedule_ids)

    @api.model_create_multi
    def create(self, vals_list):
        self._quality_require_manager()

        prepared = []
        for original in vals_list:
            vals = dict(original)
            company = (
                self.env["res.company"]
                .browse(vals.get("company_id"))
                .exists()
                or self.env.company
            )
            vals.setdefault(
                "target_score",
                company.clinic_quality_default_pass_threshold,
            )
            prepared.append(vals)

        records = super().create(prepared)
        records._check_template_scope()
        return records

    def write(self, vals):
        vals = dict(vals)

        if (
            "state" in vals
            or "active" in vals
            or "sop_version_id" in vals
        ) and not self.env.context.get("quality_template_transition") is QUALITY_TEMPLATE_TRANSITION_TOKEN:
            raise AccessError(
                _("Use Quality Template workflow actions to change lifecycle.")
            )

        material_fields = {
            "name",
            "code",
            "company_id",
            "branch_ids",
            "sop_id",
            "scope_type",
            "target_score",
            "failure_incident_type",
            "require_evidence_on_failure",
            "objective",
            "instructions",
            "reference",
        }
        if (
            material_fields.intersection(vals)
            and self.filtered(
                lambda template: template.state != "draft"
            )
            and not self.env.context.get("quality_template_transition") is QUALITY_TEMPLATE_TRANSITION_TOKEN
        ):
            raise AccessError(
                _(
                    "Active/Retired Quality Templates are governed snapshots. "
                    "Create a new Draft template revision instead."
                )
            )

        if not self.env.context.get("quality_template_transition") is QUALITY_TEMPLATE_TRANSITION_TOKEN:
            self._quality_require_manager()

        result = super().write(vals)
        self._check_template_scope()
        return result

    def unlink(self):
        self._quality_require_manager()

        if self.filtered(
            lambda template:
            template.state != "draft"
            or template.check_ids
            or template.schedule_ids
        ):
            raise UserError(
                _(
                    "Only an unused Draft Quality Template may be deleted. "
                    "Retire governed templates instead."
                )
            )
        return super().unlink()

    @api.constrains(
        "company_id",
        "branch_ids",
        "sop_id",
        "sop_version_id",
        "target_score",
    )
    def _check_template_scope(self):
        for template in self:
            invalid_branches = template.branch_ids.filtered(
                lambda branch:
                branch.company_id != template.company_id
            )
            if invalid_branches:
                raise ValidationError(
                    _("All Template Branches must belong to the Template company.")
                )

            if (
                template.sop_id
                and template.sop_id.company_id != template.company_id
            ):
                raise ValidationError(
                    _("Governing SOP belongs to another company.")
                )

            if template.sop_version_id:
                if template.sop_version_id.sop_id != template.sop_id:
                    raise ValidationError(
                        _("Approved SOP Version does not belong to the Governing SOP.")
                    )
                if template.sop_version_id.state != "approved":
                    raise ValidationError(
                        _("Quality Template may reference only an Approved SOP Version.")
                    )

            if not 0.0 <= template.target_score <= 100.0:
                raise ValidationError(
                    _("Compliance Target must be between 0 and 100.")
                )

    def action_activate(self):
        self._quality_require_manager()

        for template in self:
            if template.state != "draft":
                raise UserError(
                    _("Only a Draft Quality Template can be activated.")
                )
            if not template.line_ids:
                raise UserError(
                    _("Add at least one Quality Control before activation.")
                )

            version = template.sop_version_id
            if template.sop_id:
                version = version or template.sop_id.current_version_id
                if not version or version.state != "approved":
                    raise UserError(
                        _(
                            "The Governing SOP must have an Approved current "
                            "version before Template activation."
                        )
                    )

            template.with_context(
                quality_template_transition=QUALITY_TEMPLATE_TRANSITION_TOKEN
            ).write({
                "state": "active",
                "active": True,
                "sop_version_id": version.id if version else False,
            })
            template.message_post(
                body=_("Quality Template activated by %s.")
                % self.env.user.display_name
            )
        return True

    def action_retire(self):
        self._quality_require_manager()

        for template in self:
            if template.state == "retired":
                continue

            active_schedules = template.schedule_ids.filtered(
                lambda schedule: schedule.state == "active"
            )
            if active_schedules:
                raise UserError(
                    _(
                        "Pause or retire active Quality Schedules before "
                        "retiring this Template."
                    )
                )

            template.with_context(
                quality_template_transition=QUALITY_TEMPLATE_TRANSITION_TOKEN
            ).write({
                "state": "retired",
                # Retired templates remain visible as governed history.
                "active": True,
            })
            template.message_post(
                body=_("Quality Template retired by %s.")
                % self.env.user.display_name
            )
        return True

    def action_new_check(self):
        self.ensure_one()
        self._quality_require_inspector()

        if self.state != "active":
            raise UserError(
                _("Only an Active Quality Template can create a Check.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("New Quality Check"),
            "res_model": "clinic.quality.check",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_template_id": self.id,
                "default_company_id": self.company_id.id,
                "default_scope_type": self.scope_type,
                "default_sop_version_id": (
                    self.sop_version_id.id
                    if self.sop_version_id
                    else False
                ),
            },
        }

    def action_open_checks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quality Checks"),
            "res_model": "clinic.quality.check",
            "view_mode": "kanban,list,form,pivot,graph",
            "domain": [("template_id", "=", self.id)],
            "context": {"default_template_id": self.id},
        }

    def action_open_schedules(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quality Schedules"),
            "res_model": "clinic.quality.schedule",
            "view_mode": "list,form",
            "domain": [("template_id", "=", self.id)],
            "context": {"default_template_id": self.id},
        }

    def action_open_sop(self):
        self.ensure_one()
        if not self.sop_id:
            raise UserError(_("This Quality Template has no Governing SOP."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Governing SOP"),
            "res_model": "clinic.quality.sop",
            "view_mode": "form",
            "res_id": self.sop_id.id,
        }


class ClinicQualityCheckTemplateLine(models.Model):
    """Governed control definition copied into each executable Quality Check."""

    _name = "clinic.quality.check.template.line"
    _description = "Clinic Quality Check Template Control"
    _inherit = "clinic.quality.security.mixin"
    _order = "sequence, control_code, id"
    _check_company_auto = True

    _template_control_uniq = models.Constraint(
        "UNIQUE(template_id, control_code)",
        "Control Code must be unique within the Quality Template.",
    )
    _weight_positive = models.Constraint(
        "CHECK(weight > 0)",
        "Quality Control Weight must be greater than zero.",
    )
    _template_seq_idx = models.Index(
        "(template_id, sequence, active)"
    )

    template_id = fields.Many2one(
        "clinic.quality.check.template",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="template_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    control_code = fields.Char(
        required=True,
        index=True,
    )
    requirement = fields.Text(
        required=True,
    )
    guidance = fields.Text()
    evidence_required = fields.Boolean(
        help="Require evidence text/attachment regardless of Pass/Fail result."
    )
    critical = fields.Boolean(
        help=(
            "A failed critical control can require Incident escalation before "
            "the Quality Check may close."
        )
    )
    weight = fields.Float(
        default=1.0,
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        self._quality_require_manager()

        for vals in vals_list:
            template = self.env[
                "clinic.quality.check.template"
            ].browse(vals.get("template_id")).exists()
            if not template or template.state != "draft":
                raise UserError(
                    _("Controls can be added only to a Draft Quality Template.")
                )

        return super().create(vals_list)

    def write(self, vals):
        self._quality_require_manager()
        if self.filtered(
            lambda line: line.template_id.state != "draft"
        ):
            raise AccessError(
                _("Controls on an Active/Retired Template are immutable.")
            )
        return super().write(vals)

    def unlink(self):
        self._quality_require_manager()
        if self.filtered(
            lambda line: line.template_id.state != "draft"
        ):
            raise UserError(
                _("Controls can be deleted only from a Draft Quality Template.")
            )
        return super().unlink()

    @api.constrains("template_id", "company_id", "weight")
    def _check_template_line_scope(self):
        for line in self:
            if line.company_id != line.template_id.company_id:
                raise ValidationError(
                    _("Control company does not match its Quality Template.")
                )
            if line.weight <= 0:
                raise ValidationError(
                    _("Control Weight must be greater than zero.")
                )

    def action_open_template(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quality Check Template"),
            "res_model": "clinic.quality.check.template",
            "view_mode": "form",
            "res_id": self.template_id.id,
        }
