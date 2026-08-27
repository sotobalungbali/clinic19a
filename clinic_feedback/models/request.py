import secrets
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicFeedbackRequest(models.Model):
    """Tokenized invitation that connects a patient journey source to a Survey."""

    _name = "clinic.feedback.request"
    _description = "Clinic Patient Feedback Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.feedback.company.mixin"]
    _order = "request_date desc, id desc"
    _check_company_auto = True

    _token_unique = models.Constraint(
        "UNIQUE(access_token)",
        "Feedback Request access token must be unique.",
    )
    _expiry_positive = models.Constraint(
        "CHECK(expiry_days >= 1)",
        "Feedback Request validity must be at least one day.",
    )
    _patient_state_idx = models.Index("(company_id, patient_id, state, request_date)")
    _source_idx = models.Index("(company_id, source_type, booking_id, queue_id, encounter_id, postcare_plan_id)")
    _expiry_idx = models.Index("(company_id, state, expires_at)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    survey_id = fields.Many2one(
        "clinic.feedback.survey",
        string="Survey",
        ondelete="restrict",
        check_company=True,
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient / Contact",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('is_company', '=', False)]",
    )
    patient_card_id = fields.Many2one(
        "clinic.patient",
        string="Patient Card",
        compute="_compute_patient_card",
        store=True,
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
        tracking=True,
        index=True,
    )
    booking_id = fields.Many2one(
        "booking.booking",
        ondelete="set null",
        index=True,
    )
    queue_id = fields.Many2one(
        "clinic.queue",
        string="Queue Visit",
        ondelete="set null",
        index=True,
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        ondelete="set null",
        index=True,
    )
    postcare_plan_id = fields.Many2one(
        "clinic.postcare.plan",
        string="Post-Care Plan",
        ondelete="set null",
        index=True,
        check_company=True,
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
        domain="[('company_id', '=', company_id)]",
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        ondelete="set null",
        index=True,
    )

    access_token = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: secrets.token_urlsafe(24),
        index=True,
    )
    access_path = fields.Char(compute="_compute_access_url")
    access_url = fields.Char(compute="_compute_access_url")

    request_date = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        index=True,
    )
    expiry_days = fields.Integer(default=14)
    expires_at = fields.Datetime(
        compute="_compute_expires_at",
        store=True,
        index=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("ready", "Ready"),
            ("sent", "Sent"),
            ("opened", "Opened"),
            ("submitted", "Submitted"),
            ("expired", "Expired"),
            ("revoked", "Revoked"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    is_expired = fields.Boolean(
        compute="_compute_is_expired",
        store=True,
        index=True,
    )

    sent_at = fields.Datetime(readonly=True, tracking=True)
    opened_at = fields.Datetime(readonly=True)
    submitted_at = fields.Datetime(readonly=True)
    reminder_count = fields.Integer(default=0, readonly=True)
    last_reminder_at = fields.Datetime(readonly=True)
    last_mail_id = fields.Many2one("mail.mail", readonly=True, copy=False)

    feedback_id = fields.Many2one(
        "clinic.feedback",
        string="Submitted Feedback",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    internal_note = fields.Text()

    @api.depends("patient_id", "company_id")
    # Patient Card is a convenience snapshot; res.partner remains the invitation/contact identity.
    def _compute_patient_card(self):
        Patient = self.env["clinic.patient"]
        for record in self:
            record.patient_card_id = Patient.search([
                ("partner_id", "=", record.patient_id.id),
                ("company_id", "=", record.company_id.id),
            ], limit=1)

    @api.depends("request_date", "expiry_days")
    def _compute_expires_at(self):
        for record in self:
            if record.request_date and record.expiry_days:
                record.expires_at = (
                    fields.Datetime.to_datetime(record.request_date)
                    + timedelta(days=record.expiry_days)
                )
            else:
                record.expires_at = False

    @api.depends("state")
    def _compute_is_expired(self):
        for record in self:
            record.is_expired = record.state == "expired"

    # Public URLs are token-based and contain no patient identifiers.
    @api.depends("access_token")
    def _compute_access_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url",
            default="http://localhost:8069",
        )
        for record in self:
            record.access_path = (
                f"/clinic/feedback/{record.access_token}"
                if record.access_token
                else False
            )
            record.access_url = (
                base.rstrip("/") + record.access_path
                if record.access_path
                else False
            )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)

            # Infer source context first. This is especially important for the
            # already-installed Queue hook, which creates clinic.feedback.request
            # with queue_id/patient_id/company_id but knows nothing about addon 27.
            source = False
            if vals.get("booking_id"):
                source = self.env["booking.booking"].browse(vals["booking_id"])
                if source.exists():
                    vals.setdefault("source_type", "booking")
                    vals.setdefault("patient_id", source.patient_id.id)
                    vals.setdefault("company_id", source.company_id.id)
                    vals.setdefault("doctor_id", source.doctor_id.id or False)
                    vals.setdefault("treatment_id", source.treatment_id.id or False)
            elif vals.get("queue_id"):
                source = self.env["clinic.queue"].browse(vals["queue_id"])
                if source.exists():
                    vals.setdefault("source_type", "queue")
                    vals.setdefault("patient_id", source.patient_id.id or False)
                    vals.setdefault("company_id", source.company_id.id)
                    vals.setdefault("treatment_id", source.treatment_id.id or False)
            elif vals.get("encounter_id"):
                source = self.env["clinic.encounter"].browse(vals["encounter_id"])
                if source.exists():
                    vals.setdefault("source_type", "encounter")
                    vals.setdefault("patient_id", source.partner_id.id)
                    vals.setdefault("company_id", source.company_id.id)
                    vals.setdefault("doctor_id", source.doctor_id.id or False)
                    vals.setdefault("treatment_id", source.treatment_id.id or False)
            elif vals.get("postcare_plan_id"):
                source = self.env["clinic.postcare.plan"].browse(vals["postcare_plan_id"])
                if source.exists():
                    vals.setdefault("source_type", "postcare")
                    vals.setdefault("patient_id", source.partner_id.id)
                    vals.setdefault("company_id", source.company_id.id)
                    vals.setdefault("doctor_id", source.doctor_id.id or False)
                    vals.setdefault("staff_id", source.responsible_staff_id.id or False)
                    vals.setdefault("treatment_id", source.treatment_id.id or False)

            if source and "branch_id" in source._fields and source.branch_id:
                vals.setdefault("branch_id", source.branch_id.id)

            company = self.env["res.company"].browse(
                vals.get("company_id")
            ) or self.env.company

            if not vals.get("survey_id"):
                default_survey = company.clinic_feedback_default_survey_id
                if default_survey and default_survey.state == "active":
                    vals["survey_id"] = default_survey.id

            if vals.get("survey_id") and not vals.get("expiry_days"):
                survey = self.env["clinic.feedback.survey"].browse(vals["survey_id"])
                vals["expiry_days"] = survey.default_request_expiry_days or 14

            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.feedback.request")
                    or "/"
                )

            vals.setdefault("access_token", secrets.token_urlsafe(24))
            prepared.append(vals)

        return super().create(prepared)

    @api.constrains(
        "company_id",
        "branch_id",
        "survey_id",
        "patient_id",
        "booking_id",
        "queue_id",
        "encounter_id",
        "postcare_plan_id",
        "doctor_id",
        "staff_id",
    )
    def _check_request_scope(self):
        self._check_feedback_branch_company()
        for record in self:
            if record.survey_id and record.survey_id.company_id != record.company_id:
                raise ValidationError(_("Survey and Feedback Request company must match."))
            if record.doctor_id and record.doctor_id.company_id != record.company_id:
                raise ValidationError(_("Doctor and Feedback Request company must match."))
            if record.staff_id and record.staff_id.company_id != record.company_id:
                raise ValidationError(_("Staff and Feedback Request company must match."))

            if record.booking_id:
                if record.booking_id.company_id != record.company_id:
                    raise ValidationError(_("Booking and Feedback Request company must match."))
                if record.booking_id.patient_id != record.patient_id:
                    raise ValidationError(_("Booking belongs to a different patient/contact."))

            if record.queue_id:
                if record.queue_id.company_id != record.company_id:
                    raise ValidationError(_("Queue and Feedback Request company must match."))
                if record.queue_id.patient_id and record.queue_id.patient_id != record.patient_id:
                    raise ValidationError(_("Queue belongs to a different patient/contact."))

            if record.encounter_id:
                if record.encounter_id.company_id != record.company_id:
                    raise ValidationError(_("Encounter and Feedback Request company must match."))
                if record.encounter_id.partner_id != record.patient_id:
                    raise ValidationError(_("Encounter belongs to a different patient/contact."))

            if record.postcare_plan_id:
                if record.postcare_plan_id.company_id != record.company_id:
                    raise ValidationError(_("Post-Care Plan and Feedback Request company must match."))
                if record.postcare_plan_id.partner_id != record.patient_id:
                    raise ValidationError(_("Post-Care Plan belongs to a different patient/contact."))

    def write(self, vals):
        workflow_fields = {
            "state",
            "sent_at",
            "opened_at",
            "submitted_at",
            "reminder_count",
            "last_reminder_at",
            "feedback_id",
            "last_mail_id",
        }
        if workflow_fields.intersection(vals) and not self.env.context.get("feedback_transition"):
            raise AccessError(
                _("Use Feedback Request workflow actions to update status/audit evidence.")
            )
        scope_fields = {
            "survey_id",
            "patient_id",
            "company_id",
            "branch_id",
            "source_type",
            "booking_id",
            "queue_id",
            "encounter_id",
            "postcare_plan_id",
            "doctor_id",
            "staff_id",
            "treatment_id",
        }
        if scope_fields.intersection(vals):
            for record in self:
                if record.state not in ("draft", "ready"):
                    raise UserError(
                        _("Feedback Request scope can only be changed before the invitation is sent.")
                    )
        return super().write(vals)

    def action_prepare(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_coordinator",
            _("Only a Feedback Coordinator can prepare Requests."),
        )
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only Draft Feedback Requests can be prepared."))
            if not record.survey_id or record.survey_id.state != "active":
                raise UserError(_("Select an Active Feedback Survey before preparing the Request."))
            record.with_context(feedback_transition=True).write({"state": "ready"})
        return True

    def _get_mail_template(self):
        return self.env.ref(
            "clinic_feedback.mail_template_feedback_request",
            raise_if_not_found=False,
        )

    # Email is the only automated outbound channel implemented before future Marketing/API addons exist.
    def action_send(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_coordinator",
            _("Only a Feedback Coordinator can send Requests."),
        )
        template = self._get_mail_template()
        if not template:
            raise UserError(_("Feedback invitation email template is not configured."))

        for record in self:
            if record.state == "draft":
                record.action_prepare()
            if record.state not in ("ready", "sent", "opened"):
                raise UserError(_("This Feedback Request cannot be sent in its current state."))
            if not record.patient_id.email:
                raise UserError(_("Patient/contact has no email address."))

            mail_id = template.sudo().send_mail(
                record.id,
                force_send=True,
                email_values={"email_to": record.patient_id.email},
            )
            next_state = "opened" if record.state == "opened" else "sent"
            record.with_context(feedback_transition=True).write({
                "state": next_state,
                "sent_at": record.sent_at or fields.Datetime.now(),
                "last_mail_id": mail_id or False,
            })
            record.message_post(
                body=_("Feedback invitation sent to %s.") % record.patient_id.email
            )
        return True

    def action_send_reminder(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_coordinator",
            _("Only a Feedback Coordinator can send reminders."),
        )
        for record in self:
            if record.state not in ("sent", "opened"):
                raise UserError(_("Reminders are available only for Sent/Opened Requests."))
            if record.expires_at and record.expires_at < fields.Datetime.now():
                raise UserError(_("This Feedback Request is already past its expiry date."))
            record.action_send()
            record.with_context(feedback_transition=True).write({
                "reminder_count": record.reminder_count + 1,
                "last_reminder_at": fields.Datetime.now(),
            })
        return True

    def action_open_public(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.access_url,
            "target": "new",
        }

    def action_revoke(self):
        self._feedback_require_group(
            "clinic_feedback.group_feedback_manager",
            _("Only a Feedback Manager can revoke Requests."),
        )
        for record in self:
            if record.state == "submitted":
                raise UserError(_("Submitted Feedback Requests cannot be revoked."))
            record.with_context(feedback_transition=True).write({"state": "revoked"})
        return True

    def action_mark_opened(self):
        # Public token access runs sudo; state/audit change still uses the
        # explicit transition context to prevent arbitrary RPC writes.
        for record in self:
            if record.state in ("expired", "revoked", "submitted"):
                continue
            vals = {"state": "opened"}
            if not record.opened_at:
                vals["opened_at"] = fields.Datetime.now()
            record.with_context(feedback_transition=True).write(vals)
        return True

    # Public submission validates token lifecycle before creating immutable canonical evidence.
    def submit_public(
        self,
        overall_rating,
        nps_score=None,
        would_recommend=None,
        feedback_type="satisfaction",
        comment=None,
        answer_values=None,
        anonymous_public=False,
    ):
        self.ensure_one()
        if self.state in ("expired", "revoked"):
            raise UserError(_("This Feedback Request is no longer available."))
        if self.state == "submitted":
            return self.feedback_id
        if self.expires_at and self.expires_at < fields.Datetime.now():
            self.with_context(feedback_transition=True).write({"state": "expired"})
            raise UserError(_("This Feedback Request has expired."))
        if not self.survey_id or self.survey_id.state != "active":
            raise UserError(_("This Feedback Survey is not currently available."))

        feedback = self.env["clinic.feedback"].sudo().create_from_request(
            self,
            overall_rating=overall_rating,
            nps_score=nps_score,
            would_recommend=would_recommend,
            feedback_type=feedback_type,
            comment=comment,
            answer_values=answer_values or {},
            anonymous_public=anonymous_public,
        )
        self.with_context(feedback_transition=True).write({
            "state": "submitted",
            "submitted_at": fields.Datetime.now(),
            "feedback_id": feedback.id,
        })
        return feedback

    @api.model
    def sudo_find_by_token(self, token):
        if not token:
            return self.browse()
        return self.sudo().search([("access_token", "=", token)], limit=1)

    @api.model
    # Expiry is persisted as workflow state so search filters remain deterministic and searchable.
    def _cron_expire_requests(self):
        now = fields.Datetime.now()
        requests = self.sudo().search([
            ("state", "in", ("draft", "ready", "sent", "opened")),
            ("expires_at", "!=", False),
            ("expires_at", "<", now),
        ])
        if requests:
            requests.with_context(feedback_transition=True).write({"state": "expired"})
        return True
