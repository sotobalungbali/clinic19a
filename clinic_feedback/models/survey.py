from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicFeedbackSurvey(models.Model):
    """Reusable satisfaction questionnaire with governed activation."""

    _name = "clinic.feedback.survey"
    _description = "Clinic Feedback Satisfaction Survey"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.feedback.company.mixin"]
    _order = "sequence, name, id"
    _check_company_auto = True

    _code_company_unique = models.Constraint(
        "UNIQUE(company_id, code)",
        "Feedback Survey code must be unique per company.",
    )
    _company_state_idx = models.Index("(company_id, state, sequence)")

    name = fields.Char(required=True, tracking=True, index=True)
    code = fields.Char(required=True, tracking=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    survey_type = fields.Selection(
        [
            ("satisfaction", "Patient Satisfaction"),
            ("booking", "Booking Experience"),
            ("encounter", "Clinical Encounter"),
            ("postcare", "Post-Care Experience"),
            ("doctor", "Doctor Experience"),
            ("facility", "Facility Experience"),
        ],
        default="satisfaction",
        required=True,
        tracking=True,
        index=True,
    )
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

    title = fields.Char(required=True)
    introduction_html = fields.Html(sanitize=True)
    thank_you_html = fields.Html(sanitize=True)
    require_overall_rating = fields.Boolean(default=True)
    ask_nps = fields.Boolean(
        string="Ask NPS (0-10)",
        default=True,
    )
    ask_recommendation = fields.Boolean(default=True)
    ask_comment = fields.Boolean(default=True)
    default_request_expiry_days = fields.Integer(default=14)

    question_ids = fields.One2many(
        "clinic.feedback.question",
        "survey_id",
        string="Survey Questions",
        copy=True,
    )
    question_count = fields.Integer(compute="_compute_counts")
    request_count = fields.Integer(compute="_compute_counts")
    response_count = fields.Integer(compute="_compute_counts")

    @api.constrains("default_request_expiry_days")
    def _check_expiry_days(self):
        for record in self:
            if record.default_request_expiry_days < 1:
                raise ValidationError(
                    _("Feedback Survey request expiry must be at least one day.")
                )

    @api.onchange("code")
    def _onchange_code(self):
        for record in self:
            if record.code:
                record.code = record.code.strip().upper()

    def _compute_counts(self):
        Request = self.env["clinic.feedback.request"]
        Feedback = self.env["clinic.feedback"]
        for record in self:
            record.question_count = len(record.question_ids)
            record.request_count = Request.search_count([("survey_id", "=", record.id)])
            record.response_count = Feedback.search_count([("survey_id", "=", record.id)])

    def write(self, vals):
        if "state" in vals and not self.env.context.get("feedback_transition"):
            raise AccessError(_("Use Feedback Survey workflow actions to change status."))
        if self.filtered(lambda rec: rec.state == "active") and {
            "company_id",
            "code",
            "survey_type",
        }.intersection(vals):
            raise UserError(
                _("Archive an Active Survey before changing its core identity.")
            )
        return super().write(vals)

    # Activation freezes the survey identity used by future patient invitations.
    def action_activate(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_manager",
            _("Only a Feedback Manager can activate Surveys."),
        )
        for record in self:
            if not record.title:
                raise UserError(_("Survey Title is required before activation."))
            record.with_context(feedback_transition=True).write({"state": "active"})
        return True

    def action_archive(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_manager",
            _("Only a Feedback Manager can archive Surveys."),
        )
        self.with_context(feedback_transition=True).write({"state": "archived"})
        return True

    def action_reset_to_draft(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_manager",
            _("Only a Feedback Manager can reset Surveys."),
        )
        self.with_context(feedback_transition=True).write({"state": "draft"})
        return True

    def action_view_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Feedback Requests"),
            "res_model": "clinic.feedback.request",
            "view_mode": "list,form",
            "domain": [("survey_id", "=", self.id)],
            "context": {
                "default_survey_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    # Response navigation always opens canonical clinic.feedback records, not a parallel survey engine.
    def action_view_feedback(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Feedback Responses"),
            "res_model": "clinic.feedback",
            "view_mode": "list,form",
            "domain": [("survey_id", "=", self.id)],
        }


class ClinicFeedbackQuestion(models.Model):
    """Structured survey question used by the public and back-office forms."""

    _name = "clinic.feedback.question"
    _description = "Clinic Feedback Survey Question"
    _order = "survey_id, sequence, id"
    _check_company_auto = True

    _weight_nonnegative = models.Constraint(
        "CHECK(weight >= 0)",
        "Feedback Question weight cannot be negative.",
    )
    _survey_sequence_idx = models.Index("(survey_id, sequence, active)")

    survey_id = fields.Many2one(
        "clinic.feedback.survey",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="survey_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    name = fields.Char(string="Question", required=True)
    code = fields.Char(required=True, index=True)
    question_type = fields.Selection(
        [
            ("rating_1_5", "Rating 1-5"),
            ("nps_0_10", "NPS 0-10"),
            ("yes_no", "Yes / No"),
            ("text", "Free Text"),
        ],
        default="rating_1_5",
        required=True,
        index=True,
    )
    category = fields.Selection(
        [
            ("overall", "Overall"),
            ("care", "Care Quality"),
            ("doctor", "Doctor"),
            ("staff", "Staff"),
            ("waiting", "Waiting Time"),
            ("facility", "Facility"),
            ("communication", "Communication"),
            ("postcare", "Post-Care"),
            ("other", "Other"),
        ],
        default="overall",
        required=True,
    )
    required = fields.Boolean(default=False)
    weight = fields.Float(default=1.0)
    help_text = fields.Char()

    @api.onchange("code")
    def _onchange_code(self):
        for record in self:
            if record.code:
                record.code = record.code.strip().upper()

    @api.constrains("survey_id", "code")
    def _check_unique_code_per_survey(self):
        for record in self:
            if not record.code:
                continue
            duplicate = self.search_count([
                ("survey_id", "=", record.survey_id.id),
                ("code", "=", record.code),
                ("id", "!=", record.id),
            ])
            if duplicate:
                raise ValidationError(
                    _("Question Code must be unique within each Feedback Survey.")
                )

    def action_open_survey(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Feedback Survey"),
            "res_model": "clinic.feedback.survey",
            "view_mode": "form",
            "res_id": self.survey_id.id,
        }
