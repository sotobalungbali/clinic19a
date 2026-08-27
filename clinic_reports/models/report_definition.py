from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


REPORT_FAMILY_SELECTION = [
    ("financial", "Financial"),
    ("operational", "Operational"),
    ("clinical", "Clinical"),
]

REPORT_KEY_SELECTION = [
    ("fin_revenue", "Revenue & Billing Summary"),
    ("fin_receivables", "Accounts Receivable Aging"),
    ("fin_payables", "Accounts Payable Summary"),
    ("fin_cashflow", "Finance Cash Flow"),
    ("fin_accounting", "Accounting Activity"),
    ("fin_tax", "Indonesia Tax Reporting"),
    ("fin_insurance", "Insurance Authorization & Claims"),
    ("ops_booking", "Booking Performance"),
    ("ops_queue", "Queue Performance"),
    ("ops_room", "Room Utilization"),
    ("ops_inventory", "Clinical Inventory Usage"),
    ("ops_membership", "Membership Activity"),
    ("ops_wallet", "Patient Wallet Activity"),
    ("clinical_encounter", "Clinical Encounter Activity"),
    ("clinical_procedure", "Procedure Performance"),
    ("clinical_triage", "Triage & Vitals"),
    ("clinical_adverse", "Adverse Event Activity"),
    ("clinical_postcare", "Post-Care Outcomes"),
    ("clinical_feedback", "Patient Satisfaction & Feedback"),
]

REPORT_KEY_FAMILY = {
    key: (
        "financial"
        if key.startswith("fin_")
        else "operational"
        if key.startswith("ops_")
        else "clinical"
    )
    for key, _label in REPORT_KEY_SELECTION
}

REPORT_KEYS_WITH_AUTHORITATIVE_BRANCH = {
    "fin_revenue",
    "fin_receivables",
    "fin_payables",
    "fin_cashflow",
    "fin_accounting",
    "fin_tax",
    "fin_insurance",
    "ops_inventory",
    "clinical_postcare",
    "clinical_feedback",
}


class ClinicReportDefinition(models.Model):
    """Governed report catalog; report semantics are code-owned and auditable."""

    _name = "clinic.report.definition"
    _description = "Clinic Report Definition"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "family, sequence, name, id"

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "Report Definition code must be unique.",
    )
    _key_unique = models.Constraint(
        "UNIQUE(report_key)",
        "Each built-in Report Key can have only one definition.",
    )
    _family_sequence_idx = models.Index("(family, state, sequence)")

    name = fields.Char(required=True, tracking=True, index=True)
    code = fields.Char(required=True, tracking=True, index=True)
    family = fields.Selection(
        REPORT_FAMILY_SELECTION,
        required=True,
        tracking=True,
        index=True,
    )
    report_key = fields.Selection(
        REPORT_KEY_SELECTION,
        required=True,
        tracking=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
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
    active = fields.Boolean(default=True)

    description = fields.Text()
    methodology = fields.Html(
        string="Methodology / KPI Definition",
        sanitize=True,
        help="Human-readable explanation of the source models and KPI semantics.",
    )
    default_detail_limit = fields.Integer(default=500)
    allow_branch_filter = fields.Boolean(default=True)
    include_details_by_default = fields.Boolean(default=True)

    run_ids = fields.One2many(
        "clinic.report.run",
        "definition_id",
        string="Report Runs",
    )
    run_count = fields.Integer(compute="_compute_counts")
    schedule_count = fields.Integer(compute="_compute_counts")

    @api.constrains("family", "report_key")
    # Report Key and Family are one semantic contract; mismatches would corrupt navigation and governance.
    def _check_report_family(self):
        for record in self:
            expected = REPORT_KEY_FAMILY.get(record.report_key)
            if expected and record.family != expected:
                raise ValidationError(
                    _(
                        "Report Key %(key)s belongs to the %(family)s family."
                    )
                    % {
                        "key": record.report_key,
                        "family": expected,
                    }
                )

    @api.constrains("report_key", "allow_branch_filter")
    def _check_authoritative_branch_support(self):
        # Branch support is semantic, not a UI preference. Unsupported reports
        # must never be configured to guess a branch from Patient/Room context.
        for record in self:
            if (
                record.allow_branch_filter
                and record.report_key not in REPORT_KEYS_WITH_AUTHORITATIVE_BRANCH
            ):
                raise ValidationError(
                    _(
                        "Report %(report)s has no authoritative Branch path in "
                        "the current ClinicOne source contract."
                    )
                    % {"report": record.display_name}
                )

    @api.constrains("default_detail_limit")
    def _check_detail_limit(self):
        for record in self:
            if not 1 <= record.default_detail_limit <= 10000:
                raise ValidationError(
                    _("Default Detail Limit must be between 1 and 10,000 rows.")
                )

    @api.onchange("code")
    def _onchange_code(self):
        for record in self:
            if record.code:
                record.code = record.code.strip().upper()

    def _compute_counts(self):
        Schedule = self.env["clinic.report.schedule"]
        for record in self:
            record.run_count = len(record.run_ids)
            record.schedule_count = Schedule.search_count(
                [("definition_id", "=", record.id)]
            )

    def write(self, vals):
        if "state" in vals and not self.env.context.get("report_definition_transition"):
            raise AccessError(
                _("Use Report Definition workflow actions to change status.")
            )
        if self.filtered(lambda rec: rec.state == "active") and {
            "code",
            "family",
            "report_key",
        }.intersection(vals):
            raise UserError(
                _("Archive or reset an active Report Definition before changing its semantic identity.")
            )
        return super().write(vals)

    def action_activate(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group(
            "clinic_reports.group_reports_manager"
        ):
            raise AccessError(_("Only a Reports Manager can activate definitions."))
        self.with_context(report_definition_transition=True).write({"state": "active"})
        return True

    def action_archive(self):
        if not self.env.su and not self.env.user.has_group(
            "clinic_reports.group_reports_manager"
        ):
            raise AccessError(_("Only a Reports Manager can archive definitions."))
        self.with_context(report_definition_transition=True).write(
            {"state": "archived"}
        )
        return True

    def action_reset_to_draft(self):
        if not self.env.su and not self.env.user.has_group(
            "clinic_reports.group_reports_manager"
        ):
            raise AccessError(_("Only a Reports Manager can reset definitions."))
        self.with_context(report_definition_transition=True).write(
            {"state": "draft"}
        )
        return True

    # Definitions launch the wizard; they never execute source mutations directly.
    def action_generate_report(self):
        self.ensure_one()
        if self.state != "active":
            raise UserError(_("Only Active Report Definitions can be generated."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Generate Report"),
            "res_model": "clinic.report.generate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_definition_id": self.id,
                "default_company_id": self.env.company.id,
                "default_include_details": self.include_details_by_default,
                "default_detail_limit": self.default_detail_limit,
            },
        }

    def action_view_runs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Report Runs"),
            "res_model": "clinic.report.run",
            "view_mode": "list,form",
            "domain": [("definition_id", "=", self.id)],
            "context": {"default_definition_id": self.id},
        }

    def action_view_schedules(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Report Schedules"),
            "res_model": "clinic.report.schedule",
            "view_mode": "list,form",
            "domain": [("definition_id", "=", self.id)],
            "context": {"default_definition_id": self.id},
        }
