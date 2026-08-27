from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicMarketingSegment(models.Model):
    """Reusable structured patient audience definition.

    Segments use explicit ClinicOne fields instead of arbitrary Python/domain
    expressions so marketing users cannot turn segmentation into a security
    bypass or an unmaintainable rules engine.
    """

    _name = "clinic.marketing.segment"
    _description = "Clinic Marketing Segment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"
    _check_company_auto = True

    _code_company_unique = models.Constraint(
        "UNIQUE(company_id, code)",
        "Marketing Segment code must be unique per company.",
    )
    _company_state_idx = models.Index("(company_id, state, branch_id, active)")

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        domain="[('company_id', '=', company_id)]",
        index=True,
        tracking=True,
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
    active = fields.Boolean(default=True)
    description = fields.Text()

    gender = fields.Selection(
        [
            ("any", "Any"),
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        default="any",
        required=True,
    )
    min_age = fields.Integer()
    max_age = fields.Integer()
    patient_stage_ids = fields.Many2many(
        "clinic.patient.stage",
        "clinic_marketing_segment_stage_rel",
        "segment_id",
        "stage_id",
        string="Patient Stages",
    )
    patient_tag_ids = fields.Many2many(
        "clinic.patient.tag",
        "clinic_marketing_segment_tag_rel",
        "segment_id",
        "tag_id",
        string="Patient Tags",
    )

    membership_filter = fields.Selection(
        [
            ("any", "Any Membership Status"),
            ("active", "Active Membership"),
            ("inactive", "No Active Membership"),
        ],
        default="any",
        required=True,
    )
    membership_plan_ids = fields.Many2many(
        "membership.plan",
        "clinic_marketing_segment_plan_rel",
        "segment_id",
        "plan_id",
        string="Membership Plans",
        domain="[('company_id', '=', company_id)]",
    )

    completed_booking_within_days = fields.Integer(
        string="Visited Within Last (Days)",
        help="0 means no recent-visit requirement.",
    )
    no_completed_booking_for_days = fields.Integer(
        string="No Completed Visit For At Least (Days)",
        help="0 means no inactivity requirement.",
    )
    feedback_filter = fields.Selection(
        [
            ("any", "Any Feedback"),
            ("promoter", "Latest NPS Promoter"),
            ("detractor", "Latest NPS Detractor"),
        ],
        default="any",
        required=True,
    )
    required_channel = fields.Selection(
        [
            ("any", "Any Available Channel"),
            ("email", "Email"),
            ("whatsapp", "WhatsApp"),
            ("both", "Email + WhatsApp"),
        ],
        default="any",
        required=True,
    )

    estimated_count = fields.Integer(
        compute="_compute_estimated_count",
        string="Estimated Patients",
    )
    campaign_count = fields.Integer(compute="_compute_campaign_count")

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if vals.get("code"):
                vals["code"] = vals["code"].strip().upper()
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)
        if "state" in vals and not self.env.context.get("marketing_segment_transition"):
            raise AccessError(_("Use Segment workflow actions to change status."))
        if vals.get("code"):
            vals["code"] = vals["code"].strip().upper()
        return super().write(vals)

    @api.constrains(
        "company_id",
        "branch_id",
        "min_age",
        "max_age",
        "completed_booking_within_days",
        "no_completed_booking_for_days",
    )
    def _check_segment_rules(self):
        for segment in self:
            if segment.branch_id and segment.branch_id.company_id != segment.company_id:
                raise ValidationError(_("Segment Branch must belong to its company."))
            if segment.min_age < 0 or segment.max_age < 0:
                raise ValidationError(_("Age criteria cannot be negative."))
            if segment.min_age and segment.max_age and segment.min_age > segment.max_age:
                raise ValidationError(_("Minimum Age cannot exceed Maximum Age."))
            if (
                segment.completed_booking_within_days < 0
                or segment.no_completed_booking_for_days < 0
            ):
                raise ValidationError(_("Visit-day criteria cannot be negative."))

    @api.depends(
        "company_id",
        "branch_id",
        "gender",
        "min_age",
        "max_age",
        "patient_stage_ids",
        "patient_tag_ids",
        "membership_filter",
        "membership_plan_ids",
        "completed_booking_within_days",
        "no_completed_booking_for_days",
        "feedback_filter",
        "required_channel",
        "state",
    )
    def _compute_estimated_count(self):
        for segment in self:
            segment.estimated_count = len(segment._candidate_patients())

    def _compute_campaign_count(self):
        Campaign = self.env["clinic.marketing.campaign"].sudo()
        for segment in self:
            segment.campaign_count = Campaign.search_count([
                ("segment_id", "=", segment.id),
            ])

    def _base_patient_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
        ]
        if self.gender != "any":
            domain.append(("gender", "=", self.gender))
        if self.patient_stage_ids:
            domain.append(("stage_id", "in", self.patient_stage_ids.ids))
        if self.patient_tag_ids:
            domain.append(("tag_ids", "in", self.patient_tag_ids.ids))
        if self.branch_id:
            domain.append(("partner_id.branch_id", "=", self.branch_id.id))

        # Age boundaries are derived from the Patient-owned birth_date using
        # relativedelta, which correctly handles leap years and avoids relying
        # on a stored age value becoming stale after a birthday.
        today = fields.Date.context_today(self)
        if self.min_age:
            domain.append((
                "birth_date",
                "<=",
                today - relativedelta(years=self.min_age),
            ))
        if self.max_age:
            domain.append((
                "birth_date",
                ">",
                today - relativedelta(years=self.max_age + 1),
            ))
        return domain

    # Membership filtering reads the owner contract only; Marketing never changes membership state.
    def _filter_membership(self, patients):
        self.ensure_one()
        if self.membership_filter == "any" and not self.membership_plan_ids:
            return patients

        Contract = self.env["membership.contract"].sudo()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("patient_id", "in", patients.ids),
            ("state", "=", "active"),
        ]
        if self.membership_plan_ids:
            domain.append(("plan_id", "in", self.membership_plan_ids.ids))
        active_patient_ids = set(Contract.search(domain).mapped("patient_id").ids)

        if self.membership_filter == "inactive":
            return patients.filtered(lambda patient: patient.id not in active_patient_ids)
        return patients.filtered(lambda patient: patient.id in active_patient_ids)

    # Visit behavior is derived from completed owner Bookings, never from draft/cancelled appointments.
    def _filter_booking_recency(self, patients):
        self.ensure_one()
        if not (
            self.completed_booking_within_days
            or self.no_completed_booking_for_days
        ):
            return patients

        Booking = self.env["booking.booking"].sudo()
        today = fields.Datetime.now()
        filtered = patients

        if self.completed_booking_within_days:
            cutoff = today - timedelta(days=self.completed_booking_within_days)
            recent_partner_ids = set(
                Booking.search([
                    ("company_id", "=", self.company_id.id),
                    ("patient_id", "in", patients.mapped("partner_id").ids),
                    ("state", "=", "done"),
                    ("start_datetime", ">=", cutoff),
                ]).mapped("patient_id").ids
            )
            filtered = filtered.filtered(
                lambda patient: patient.partner_id.id in recent_partner_ids
            )

        if self.no_completed_booking_for_days:
            cutoff = today - timedelta(days=self.no_completed_booking_for_days)
            recent_partner_ids = set(
                Booking.search([
                    ("company_id", "=", self.company_id.id),
                    ("patient_id", "in", filtered.mapped("partner_id").ids),
                    ("state", "=", "done"),
                    ("start_datetime", ">", cutoff),
                ]).mapped("patient_id").ids
            )
            filtered = filtered.filtered(
                lambda patient: patient.partner_id.id not in recent_partner_ids
            )

        return filtered

    # NPS segmentation uses the latest submitted/reviewed Feedback fact without editing Feedback ownership.
    def _filter_feedback(self, patients):
        self.ensure_one()
        if self.feedback_filter == "any":
            return patients

        Feedback = self.env["clinic.feedback"].sudo()
        keep_ids = set()
        for patient in patients:
            latest = Feedback.search([
                ("patient_id", "=", patient.partner_id.id),
                ("state", "in", ("submitted", "under_review", "closed", "escalated")),
            ], order="submitted_at desc, id desc", limit=1)
            if not latest:
                continue
            if self.feedback_filter == "promoter" and latest.nps_class == "promoter":
                keep_ids.add(patient.id)
            elif self.feedback_filter == "detractor" and latest.nps_class == "detractor":
                keep_ids.add(patient.id)
        return patients.filtered(lambda patient: patient.id in keep_ids)

    def _filter_channel_availability(self, patients):
        self.ensure_one()
        if self.required_channel == "any":
            return patients
        if self.required_channel == "email":
            return patients.filtered(lambda p: bool(p.partner_id.email or p.email))
        if self.required_channel == "whatsapp":
            return patients.filtered(
                lambda p: bool(p.mobile or p.partner_id.phone or p.phone)
            )
        return patients.filtered(
            lambda p: bool(p.partner_id.email or p.email)
            and bool(p.mobile or p.partner_id.phone or p.phone)
        )

    def _candidate_patients(self):
        self.ensure_one()
        if not self.company_id:
            return self.env["clinic.patient"]
        patients = self.env["clinic.patient"].sudo().search(
            self._base_patient_domain()
        )
        patients = self._filter_membership(patients)
        patients = self._filter_booking_recency(patients)
        patients = self._filter_feedback(patients)
        patients = self._filter_channel_availability(patients)
        return patients

    def action_activate(self):
        self.with_context(marketing_segment_transition=True).write({
            "state": "active",
            "active": True,
        })
        return True

    def action_archive(self):
        self.with_context(marketing_segment_transition=True).write({
            "state": "archived",
            "active": False,
        })
        return True

    def action_reset_to_draft(self):
        self.with_context(marketing_segment_transition=True).write({
            "state": "draft",
            "active": True,
        })
        return True

    def action_preview_patients(self):
        self.ensure_one()
        patients = self._candidate_patients()
        return {
            "type": "ir.actions.act_window",
            "name": _("Segment Patients"),
            "res_model": "clinic.patient",
            "view_mode": "list,form",
            "domain": [("id", "in", patients.ids)],
        }

    def action_open_campaigns(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Marketing Campaigns"),
            "res_model": "clinic.marketing.campaign",
            "view_mode": "list,form",
            "domain": [("segment_id", "=", self.id)],
        }

