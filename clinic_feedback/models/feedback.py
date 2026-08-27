from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicFeedback(models.Model):
    """Canonical patient satisfaction response across all ClinicOne sources."""

    _name = "clinic.feedback"
    _description = "Clinic Patient Feedback"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.feedback.company.mixin"]
    _order = "submitted_at desc, id desc"
    _check_company_auto = True

    _request_unique = models.Constraint(
        "UNIQUE(request_id)",
        "A Feedback Request can have only one canonical Feedback response.",
    )
    _booking_link_unique = models.Constraint(
        "UNIQUE(booking_feedback_link_id)",
        "A Booking Feedback Link can have only one canonical Feedback response.",
    )
    _rating_range = models.Constraint(
        "CHECK(overall_rating >= 0 AND overall_rating <= 5)",
        "Overall Rating must be between 1 and 5, or 0 when the Survey does not require it.",
    )
    _nps_range = models.Constraint(
        "CHECK(nps_score >= -1 AND nps_score <= 10)",
        "NPS Score must be between 0 and 10, or -1 when not provided.",
    )
    _patient_state_idx = models.Index("(company_id, patient_id, state, submitted_at)")
    _doctor_idx = models.Index("(company_id, doctor_id, state, submitted_at)")
    _staff_idx = models.Index("(company_id, staff_id, state, submitted_at)")
    _rating_idx = models.Index("(company_id, overall_rating, nps_class, submitted_at)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True)
    request_id = fields.Many2one(
        "clinic.feedback.request",
        ondelete="set null",
        index=True,
        copy=False,
    )
    booking_feedback_link_id = fields.Many2one(
        "booking.feedback.link",
        string="Booking Feedback Link",
        ondelete="set null",
        index=True,
        copy=False,
    )
    survey_id = fields.Many2one(
        "clinic.feedback.survey",
        required=True,
        ondelete="restrict",
        check_company=True,
        index=True,
    )

    patient_id = fields.Many2one(
        "res.partner",
        string="Patient / Contact",
        required=True,
        ondelete="restrict",
        index=True,
    )
    patient_card_id = fields.Many2one(
        "clinic.patient",
        string="Patient Card",
        ondelete="set null",
        index=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        ondelete="set null",
        index=True,
        check_company=True,
    )
    staff_id = fields.Many2one(
        "clinic.staff",
        string="Responsible Staff",
        ondelete="set null",
        index=True,
        check_company=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        ondelete="set null",
        index=True,
    )

    source_type = fields.Selection(
        [
            ("manual", "Manual"),
            ("booking", "Booking"),
            ("queue", "Queue"),
            ("encounter", "Encounter"),
            ("postcare", "Post-Care"),
        ],
        default="manual",
        required=True,
        index=True,
        tracking=True,
    )
    booking_id = fields.Many2one("booking.booking", ondelete="set null", index=True)
    queue_id = fields.Many2one("clinic.queue", ondelete="set null", index=True)
    encounter_id = fields.Many2one("clinic.encounter", ondelete="set null", index=True)
    postcare_plan_id = fields.Many2one(
        "clinic.postcare.plan",
        ondelete="set null",
        index=True,
        check_company=True,
    )

    feedback_type = fields.Selection(
        [
            ("satisfaction", "Satisfaction"),
            ("compliment", "Compliment"),
            ("suggestion", "Suggestion"),
            ("complaint", "Complaint"),
        ],
        default="satisfaction",
        required=True,
        tracking=True,
        index=True,
    )
    overall_rating = fields.Integer(
        string="Overall Rating (1-5)",
        default=0,
        tracking=True,
        index=True,
        help="0 means not collected by this Survey; patient-facing ratings use 1-5.",
    )
    satisfaction_percent = fields.Float(
        compute="_compute_scores",
        store=True,
        index=True,
    )
    nps_score = fields.Integer(
        string="NPS Score (0-10)",
        default=-1,
        tracking=True,
    )
    nps_class = fields.Selection(
        [
            ("not_applicable", "Not Provided"),
            ("detractor", "Detractor"),
            ("passive", "Passive"),
            ("promoter", "Promoter"),
        ],
        compute="_compute_scores",
        store=True,
        index=True,
    )
    would_recommend = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No"),
            ("na", "Prefer not to say"),
        ],
        default="na",
        tracking=True,
    )
    comment = fields.Text()
    anonymous_public = fields.Boolean(
        string="Hide My Name in Public Use",
        default=False,
        help="Internal authorized staff still retain source traceability for service recovery.",
    )

    answer_ids = fields.One2many(
        "clinic.feedback.answer",
        "feedback_id",
        string="Survey Answers",
        copy=False,
    )
    answer_count = fields.Integer(compute="_compute_counts")
    escalation_ids = fields.One2many(
        "clinic.feedback.escalation",
        "feedback_id",
        string="Escalations",
        copy=False,
    )
    escalation_count = fields.Integer(compute="_compute_counts")
    open_escalation_count = fields.Integer(compute="_compute_counts")

    needs_escalation = fields.Boolean(
        compute="_compute_needs_escalation",
        store=True,
        index=True,
    )
    escalation_reason = fields.Char(
        compute="_compute_needs_escalation",
        store=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("under_review", "Under Review"),
            ("escalated", "Escalated"),
            ("closed", "Closed"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    submitted_at = fields.Datetime(readonly=True, tracking=True)
    reviewed_at = fields.Datetime(readonly=True)
    reviewer_id = fields.Many2one("res.users", readonly=True)
    review_note = fields.Text()
    closed_at = fields.Datetime(readonly=True)
    closed_by_id = fields.Many2one("res.users", readonly=True)

    @api.depends("overall_rating", "nps_score")
    # Satisfaction and NPS classes are stored analytic dimensions for later Reports/Dashboard addons.
    def _compute_scores(self):
        for record in self:
            record.satisfaction_percent = (
                float(record.overall_rating or 0) * 20.0
            )
            if record.nps_score < 0:
                record.nps_class = "not_applicable"
            elif record.nps_score <= 6:
                record.nps_class = "detractor"
            elif record.nps_score <= 8:
                record.nps_class = "passive"
            else:
                record.nps_class = "promoter"

    @api.depends(
        "feedback_type",
        "overall_rating",
        "nps_score",
        "would_recommend",
        "company_id.clinic_feedback_low_rating_threshold",
        "company_id.clinic_feedback_nps_escalation_threshold",
    )
    # Escalation signals are service-recovery policy, not clinical diagnosis or Incident creation.
    def _compute_needs_escalation(self):
        for record in self:
            reasons = []
            rating_threshold = (
                record.company_id.clinic_feedback_low_rating_threshold or 2
            )
            nps_threshold = (
                record.company_id.clinic_feedback_nps_escalation_threshold or 6
            )

            if record.feedback_type == "complaint":
                reasons.append(_("Patient classified the response as a complaint."))
            if record.overall_rating and record.overall_rating <= rating_threshold:
                reasons.append(
                    _("Overall rating is at/below the configured escalation threshold.")
                )
            if 0 <= record.nps_score <= nps_threshold:
                reasons.append(
                    _("NPS score is at/below the configured escalation threshold.")
                )
            if record.would_recommend == "no":
                reasons.append(_("Patient would not recommend the clinic."))

            record.needs_escalation = bool(reasons)
            record.escalation_reason = " ".join(reasons)

    def _compute_counts(self):
        for record in self:
            record.answer_count = len(record.answer_ids)
            record.escalation_count = len(record.escalation_ids)
            record.open_escalation_count = len(
                record.escalation_ids.filtered(
                    lambda escalation:
                        escalation.state not in ("resolved", "cancelled")
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            company = self.env["res.company"].browse(
                vals.get("company_id")
            ) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.feedback")
                    or "/"
                )
            prepared.append(vals)
        return super().create(prepared)

    @api.constrains(
        "company_id",
        "branch_id",
        "survey_id",
        "patient_id",
        "patient_card_id",
        "doctor_id",
        "staff_id",
    )
    def _check_feedback_scope(self):
        self._check_feedback_branch_company()
        for record in self:
            if record.survey_id.company_id != record.company_id:
                raise ValidationError(_("Survey and Feedback company must match."))
            if record.patient_card_id:
                if record.patient_card_id.company_id != record.company_id:
                    raise ValidationError(_("Patient Card and Feedback company must match."))
                if record.patient_card_id.partner_id != record.patient_id:
                    raise ValidationError(_("Patient Card belongs to a different contact."))
            if record.doctor_id and record.doctor_id.company_id != record.company_id:
                raise ValidationError(_("Doctor and Feedback company must match."))
            if record.staff_id and record.staff_id.company_id != record.company_id:
                raise ValidationError(_("Staff and Feedback company must match."))

    def write(self, vals):
        workflow_fields = {
            "state",
            "submitted_at",
            "reviewed_at",
            "reviewer_id",
            "closed_at",
            "closed_by_id",
        }
        if workflow_fields.intersection(vals) and not self.env.context.get("feedback_transition"):
            raise AccessError(_("Use Feedback workflow actions to change status/audit fields."))

        evidence_fields = {
            "survey_id",
            "patient_id",
            "patient_card_id",
            "doctor_id",
            "staff_id",
            "treatment_id",
            "source_type",
            "booking_id",
            "queue_id",
            "encounter_id",
            "postcare_plan_id",
            "feedback_type",
            "overall_rating",
            "nps_score",
            "would_recommend",
            "comment",
            "anonymous_public",
        }
        if evidence_fields.intersection(vals):
            for record in self:
                if record.state not in ("draft",):
                    raise UserError(
                        _("Submitted patient Feedback evidence is immutable; use review notes and escalation workflow.")
                    )
        return super().write(vals)

    @api.model
    # Canonicalization snapshots journey context so later source edits cannot rewrite submitted patient evidence.
    def create_from_request(
        self,
        request_record,
        overall_rating,
        nps_score=None,
        would_recommend=None,
        feedback_type="satisfaction",
        comment=None,
        answer_values=None,
        anonymous_public=False,
    ):
        """Create a canonical response from a validated tokenized request."""
        request_record.ensure_one()

        rating = 0
        if overall_rating not in (None, "", False):
            try:
                rating = int(overall_rating)
            except (TypeError, ValueError):
                raise UserError(_("Overall Rating must be a number from 1 to 5."))
            if rating not in (1, 2, 3, 4, 5):
                raise UserError(_("Overall Rating must be between 1 and 5."))
        elif request_record.survey_id.require_overall_rating:
            raise UserError(_("Overall Rating is required for this Feedback Survey."))

        nps = -1
        if nps_score not in (None, "", False):
            try:
                nps = int(nps_score)
            except (TypeError, ValueError):
                raise UserError(_("NPS Score must be a number from 0 to 10."))
            if not 0 <= nps <= 10:
                raise UserError(_("NPS Score must be between 0 and 10."))

        recommendation = would_recommend or "na"
        if recommendation not in ("yes", "no", "na"):
            raise UserError(_("Invalid recommendation value."))

        feedback = self.create({
            "request_id": request_record.id,
            "survey_id": request_record.survey_id.id,
            "patient_id": request_record.patient_id.id,
            "patient_card_id": request_record.patient_card_id.id or False,
            "doctor_id": request_record.doctor_id.id or False,
            "staff_id": request_record.staff_id.id or False,
            "treatment_id": request_record.treatment_id.id or False,
            "company_id": request_record.company_id.id,
            "branch_id": request_record.branch_id.id or False,
            "source_type": request_record.source_type,
            "booking_id": request_record.booking_id.id or False,
            "queue_id": request_record.queue_id.id or False,
            "encounter_id": request_record.encounter_id.id or False,
            "postcare_plan_id": request_record.postcare_plan_id.id or False,
            "feedback_type": feedback_type,
            "overall_rating": rating,
            "nps_score": nps,
            "would_recommend": recommendation,
            "comment": comment,
            "anonymous_public": bool(anonymous_public),
        })

        feedback._create_structured_answers(answer_values or {})
        feedback.action_submit()
        return feedback

    @api.model
    # Legacy Booking feedback remains valid even when no canonical Survey has been configured yet.
    def create_from_booking_link(
        self,
        link,
        nps_score=None,
        feedback_type="satisfaction",
        answer_values=None,
        anonymous_public=False,
    ):
        """Synchronize Booking-owned submitted feedback into canonical Feedback."""
        link.ensure_one()
        if link.clinic_feedback_id:
            return link.clinic_feedback_id

        survey = (
            link.feedback_survey_id
            or link.company_id.clinic_feedback_default_survey_id
        )
        if not survey or survey.state != "active":
            # Preserve legacy Booking submission even when addon 27 has not yet
            # been configured with a default Survey.
            return self.browse()

        try:
            rating = int(link.rating_value or 0)
        except (TypeError, ValueError):
            rating = 0

        if rating not in (1, 2, 3, 4, 5):
            # The legacy Booking model allows submission without a rating.
            # Preserve that behavior. Canonicalization is still possible when
            # the selected Survey explicitly does not require Overall Rating.
            if survey.require_overall_rating:
                return self.browse()
            rating = 0

        nps = -1
        if nps_score not in (None, "", False):
            try:
                nps = int(nps_score)
            except (TypeError, ValueError):
                raise UserError(_("NPS Score must be a number from 0 to 10."))
            if not 0 <= nps <= 10:
                raise UserError(_("NPS Score must be between 0 and 10."))

        patient_card = self.env["clinic.patient"].search([
            ("partner_id", "=", link.patient_id.id),
            ("company_id", "=", link.company_id.id),
        ], limit=1)

        feedback = self.create({
            "booking_feedback_link_id": link.id,
            "survey_id": survey.id,
            "patient_id": link.patient_id.id,
            "patient_card_id": patient_card.id or False,
            "doctor_id": link.doctor_id.id or False,
            "treatment_id": link.treatment_id.id or False,
            "company_id": link.company_id.id,
            "source_type": "booking",
            "booking_id": link.booking_id.id,
            "feedback_type": feedback_type,
            "overall_rating": rating,
            "nps_score": nps,
            "would_recommend": link.would_recommend or "na",
            "comment": link.comment,
            "anonymous_public": bool(anonymous_public),
        })
        feedback._create_structured_answers(answer_values or {})
        feedback.action_submit()
        return feedback

    # Answers are normalized by question type before becoming immutable submission evidence.
    def _create_structured_answers(self, answer_values):
        Answer = self.env["clinic.feedback.answer"].sudo()
        for feedback in self:
            for question in feedback.survey_id.question_ids.filtered("active"):
                raw_value = answer_values.get(str(question.id))
                if raw_value in (None, ""):
                    if question.required:
                        raise UserError(
                            _("Please answer the required question: %s") % question.name
                        )
                    continue

                vals = {
                    "feedback_id": feedback.id,
                    "question_id": question.id,
                }
                if question.question_type in ("rating_1_5", "nps_0_10"):
                    try:
                        numeric = int(raw_value)
                    except (TypeError, ValueError):
                        raise UserError(_("Invalid numeric answer for %s.") % question.name)
                    maximum = 5 if question.question_type == "rating_1_5" else 10
                    minimum = 1 if question.question_type == "rating_1_5" else 0
                    if not minimum <= numeric <= maximum:
                        raise UserError(
                            _("Answer for %s must be between %s and %s.")
                            % (question.name, minimum, maximum)
                        )
                    vals["numeric_value"] = numeric
                elif question.question_type == "yes_no":
                    value = str(raw_value).lower()
                    if value not in ("yes", "no"):
                        raise UserError(_("Invalid Yes/No answer for %s.") % question.name)
                    vals["boolean_value"] = value == "yes"
                else:
                    vals["text_value"] = str(raw_value)

                Answer.create(vals)

    # One open service-recovery case is created automatically per triggering response path.
    def _ensure_escalation(self):
        Escalation = self.env["clinic.feedback.escalation"]
        for feedback in self:
            if not feedback.needs_escalation:
                continue
            existing = feedback.escalation_ids.filtered(
                lambda escalation:
                    escalation.state not in ("resolved", "cancelled")
            )[:1]
            if existing:
                continue
            severity = (
                "critical"
                if feedback.overall_rating == 1 and feedback.feedback_type == "complaint"
                else "high"
                if feedback.overall_rating <= 2 or feedback.feedback_type == "complaint"
                else "medium"
            )
            Escalation.create({
                "feedback_id": feedback.id,
                "severity": severity,
                "reason": feedback.escalation_reason
                or _("Patient Feedback requires service-recovery review."),
                "owner_staff_id": (
                    feedback.company_id.clinic_feedback_default_owner_staff_id.id
                    or feedback.staff_id.id
                    or False
                ),
            })

    def action_submit(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_reviewer",
            _("Only a Feedback Reviewer can manually submit canonical Feedback."),
        )
        for feedback in self:
            if feedback.state != "draft":
                continue
            feedback.with_context(feedback_transition=True).write({
                "state": "submitted",
                "submitted_at": fields.Datetime.now(),
            })
            feedback._ensure_escalation()
        return True

    def action_start_review(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_reviewer",
            _("Only a Feedback Reviewer can start review."),
        )
        for feedback in self:
            if feedback.state not in ("submitted", "escalated"):
                raise UserError(_("Only Submitted/Escalated Feedback can enter review."))
            feedback.with_context(feedback_transition=True).write({
                "state": "under_review",
                "reviewed_at": feedback.reviewed_at or fields.Datetime.now(),
                "reviewer_id": self.env.user.id,
            })
        return True

    def action_escalate(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_reviewer",
            _("Only a Feedback Reviewer can escalate Feedback."),
        )
        for feedback in self:
            feedback._ensure_escalation()
            open_escalations = feedback.escalation_ids.filtered(
                lambda escalation:
                    escalation.state not in ("resolved", "cancelled")
            )
            if not open_escalations:
                self.env["clinic.feedback.escalation"].create({
                    "feedback_id": feedback.id,
                    "severity": "medium",
                    "reason": _("Manual service-recovery escalation."),
                    "owner_staff_id": (
                        feedback.company_id.clinic_feedback_default_owner_staff_id.id
                        or feedback.staff_id.id
                        or False
                    ),
                })
            feedback.with_context(feedback_transition=True).write({"state": "escalated"})
        return True

    # Closing Feedback is backend-blocked while any service-recovery escalation remains open.
    def action_close(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_reviewer",
            _("Only a Feedback Reviewer can close Feedback."),
        )
        for feedback in self:
            open_escalations = feedback.escalation_ids.filtered(
                lambda escalation:
                    escalation.state not in ("resolved", "cancelled")
            )
            if open_escalations:
                raise UserError(_("Resolve/cancel open Feedback Escalations before closing."))
            feedback.with_context(feedback_transition=True).write({
                "state": "closed",
                "closed_at": fields.Datetime.now(),
                "closed_by_id": self.env.user.id,
            })
        return True

    def action_view_escalations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Feedback Escalations"),
            "res_model": "clinic.feedback.escalation",
            "view_mode": "list,form",
            "domain": [("feedback_id", "=", self.id)],
            "context": {"default_feedback_id": self.id},
        }

    def action_open_source(self):
        self.ensure_one()
        source = {
            "booking": ("booking.booking", self.booking_id),
            "queue": ("clinic.queue", self.queue_id),
            "encounter": ("clinic.encounter", self.encounter_id),
            "postcare": ("clinic.postcare.plan", self.postcare_plan_id),
        }.get(self.source_type)
        if not source or not source[1]:
            raise UserError(_("No source record is linked to this Feedback."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Feedback Source"),
            "res_model": source[0],
            "view_mode": "form",
            "res_id": source[1].id,
        }

    def action_print_summary(self):
        self.ensure_one()
        return self.env.ref(
            "clinic_feedback.action_report_feedback_summary"
        ).report_action(self)


class ClinicFeedbackAnswer(models.Model):
    """Immutable structured answer belonging to one canonical Feedback response."""

    _name = "clinic.feedback.answer"
    _description = "Clinic Feedback Survey Answer"
    _order = "feedback_id, question_id, id"
    _check_company_auto = True

    _feedback_question_unique = models.Constraint(
        "UNIQUE(feedback_id, question_id)",
        "Each Survey Question can have only one answer per Feedback response.",
    )
    _feedback_idx = models.Index("(feedback_id, question_id)")

    feedback_id = fields.Many2one(
        "clinic.feedback",
        required=True,
        ondelete="cascade",
        index=True,
    )
    question_id = fields.Many2one(
        "clinic.feedback.question",
        required=True,
        ondelete="restrict",
        index=True,
    )
    survey_id = fields.Many2one(
        related="feedback_id.survey_id",
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="feedback_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    numeric_value = fields.Float()
    boolean_value = fields.Boolean()
    text_value = fields.Text()
    display_value = fields.Char(
        compute="_compute_display_value",
        store=True,
    )

    @api.depends(
        "question_id.question_type",
        "numeric_value",
        "boolean_value",
        "text_value",
    )
    def _compute_display_value(self):
        for answer in self:
            if answer.question_id.question_type in ("rating_1_5", "nps_0_10"):
                answer.display_value = (
                    str(int(answer.numeric_value))
                    if answer.numeric_value == int(answer.numeric_value)
                    else str(answer.numeric_value)
                )
            elif answer.question_id.question_type == "yes_no":
                answer.display_value = _("Yes") if answer.boolean_value else _("No")
            else:
                answer.display_value = answer.text_value or ""

    @api.model_create_multi
    def create(self, vals_list):
        # Manual draft editing remains possible for Reviewers, but once the
        # canonical Feedback is submitted no RPC client may append new evidence.
        for vals in vals_list:
            feedback = self.env["clinic.feedback"].browse(vals.get("feedback_id"))
            if feedback.exists() and feedback.state != "draft":
                raise AccessError(
                    _("Submitted Feedback Answers are immutable and cannot be appended.")
                )
        return super().create(vals_list)

    @api.constrains("feedback_id", "question_id")
    def _check_question_survey(self):
        for answer in self:
            if answer.question_id.survey_id != answer.feedback_id.survey_id:
                raise ValidationError(
                    _("Survey Answer question must belong to the Feedback Survey.")
                )

    def write(self, vals):
        if self.filtered(lambda answer: answer.feedback_id.state != "draft"):
            raise AccessError(_("Submitted Feedback Answers are immutable."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda answer: answer.feedback_id.state != "draft"):
            raise AccessError(_("Submitted Feedback Answers cannot be deleted."))
        return super().unlink()

    def action_open_feedback(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Feedback"),
            "res_model": "clinic.feedback",
            "view_mode": "form",
            "res_id": self.feedback_id.id,
        }
