from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ClinicQueue(models.Model):
    """Activate the live Queue feedback hook without moving Queue ownership."""

    _inherit = "clinic.queue"

    feedback_request_id = fields.Many2one(
        "clinic.feedback.request",
        string="Feedback Request",
        ondelete="set null",
        copy=False,
        help="Request created by the existing Queue completion hook.",
    )

    def action_open_feedback_request(self):
        self.ensure_one()
        if not self.feedback_request_id:
            raise UserError(_("This Queue has no Feedback Request yet."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Feedback Request"),
            "res_model": "clinic.feedback.request",
            "view_mode": "form",
            "res_id": self.feedback_request_id.id,
        }


class BookingBooking(models.Model):
    """Add canonical Feedback Request navigation while preserving Booking feedback links."""

    _inherit = "booking.booking"

    clinic_feedback_request_ids = fields.One2many(
        "clinic.feedback.request",
        "booking_id",
        string="Clinic Feedback Requests",
    )
    clinic_feedback_request_count = fields.Integer(
        compute="_compute_clinic_feedback_counts"
    )
    clinic_feedback_response_count = fields.Integer(
        compute="_compute_clinic_feedback_counts"
    )

    def _compute_clinic_feedback_counts(self):
        Feedback = self.env["clinic.feedback"]
        for record in self:
            record.clinic_feedback_request_count = len(
                record.clinic_feedback_request_ids
            )
            record.clinic_feedback_response_count = Feedback.search_count([
                ("booking_id", "=", record.id),
            ])

    # Explicit Booking request creation coexists with the older Booking-owned feedback-link workflow.
    def action_create_clinic_feedback_request(self):
        self.ensure_one()
        if self.state != "done":
            raise UserError(
                _("Feedback Requests are normally created after a completed Booking.")
            )
        existing = self.clinic_feedback_request_ids.filtered(
            lambda request: request.state not in ("expired", "revoked")
        )[:1]
        request = existing or self.env["clinic.feedback.request"].create({
            "booking_id": self.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Feedback Request"),
            "res_model": "clinic.feedback.request",
            "view_mode": "form",
            "res_id": request.id,
        }

    def action_open_clinic_feedback_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Booking Feedback Requests"),
            "res_model": "clinic.feedback.request",
            "view_mode": "list,form",
            "domain": [("booking_id", "=", self.id)],
            "context": {"default_booking_id": self.id},
        }


class ClinicEncounter(models.Model):
    """Link completed clinical Encounters to satisfaction requests."""

    _inherit = "clinic.encounter"

    feedback_request_ids = fields.One2many(
        "clinic.feedback.request",
        "encounter_id",
        string="Feedback Requests",
    )
    feedback_request_count = fields.Integer(
        compute="_compute_feedback_request_count"
    )
    feedback_response_count = fields.Integer(
        compute="_compute_feedback_request_count"
    )

    def _compute_feedback_request_count(self):
        Feedback = self.env["clinic.feedback"]
        for record in self:
            record.feedback_request_count = len(record.feedback_request_ids)
            record.feedback_response_count = Feedback.search_count([
                ("encounter_id", "=", record.id),
            ])

    # Encounter completion remains upstream-owned; this action only creates a downstream invitation.
    def action_create_feedback_request(self):
        self.ensure_one()
        if self.state != "done":
            raise UserError(
                _("Feedback Requests are normally created after the Encounter is Done.")
            )
        existing = self.feedback_request_ids.filtered(
            lambda request: request.state not in ("expired", "revoked")
        )[:1]
        request = existing or self.env["clinic.feedback.request"].create({
            "encounter_id": self.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Feedback Request"),
            "res_model": "clinic.feedback.request",
            "view_mode": "form",
            "res_id": request.id,
        }

    def action_open_feedback_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Encounter Feedback Requests"),
            "res_model": "clinic.feedback.request",
            "view_mode": "list,form",
            "domain": [("encounter_id", "=", self.id)],
            "context": {"default_encounter_id": self.id},
        }


class ClinicPostcarePlan(models.Model):
    """Collect experience feedback after the Post-Care episode completes."""

    _inherit = "clinic.postcare.plan"

    feedback_request_ids = fields.One2many(
        "clinic.feedback.request",
        "postcare_plan_id",
        string="Feedback Requests",
    )
    feedback_request_count = fields.Integer(
        compute="_compute_feedback_request_count"
    )
    feedback_response_count = fields.Integer(
        compute="_compute_feedback_request_count"
    )

    def _compute_feedback_request_count(self):
        Feedback = self.env["clinic.feedback"]
        for record in self:
            record.feedback_request_count = len(record.feedback_request_ids)
            record.feedback_response_count = Feedback.search_count([
                ("postcare_plan_id", "=", record.id),
            ])

    def action_create_feedback_request(self):
        self.ensure_one()
        if self.state not in ("completed", "closed"):
            raise UserError(
                _("Feedback Requests are normally created after Post-Care completion.")
            )
        existing = self.feedback_request_ids.filtered(
            lambda request: request.state not in ("expired", "revoked")
        )[:1]
        request = existing or self.env["clinic.feedback.request"].create({
            "postcare_plan_id": self.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Feedback Request"),
            "res_model": "clinic.feedback.request",
            "view_mode": "form",
            "res_id": request.id,
        }

    def action_open_feedback_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Feedback Requests"),
            "res_model": "clinic.feedback.request",
            "view_mode": "list,form",
            "domain": [("postcare_plan_id", "=", self.id)],
            "context": {"default_postcare_plan_id": self.id},
        }


class ClinicPatient(models.Model):
    """Patient-card feedback navigation across every journey source."""

    _inherit = "clinic.patient"

    clinic_feedback_count = fields.Integer(
        compute="_compute_clinic_feedback_counts"
    )
    clinic_feedback_open_escalation_count = fields.Integer(
        compute="_compute_clinic_feedback_counts"
    )
    clinic_feedback_avg_rating = fields.Float(
        compute="_compute_clinic_feedback_counts",
        digits=(16, 2),
    )

    def _compute_clinic_feedback_counts(self):
        Feedback = self.env["clinic.feedback"]
        Escalation = self.env["clinic.feedback.escalation"]
        for patient in self:
            feedback = Feedback.search([
                ("patient_id", "=", patient.partner_id.id),
                ("company_id", "=", patient.company_id.id),
            ])
            patient.clinic_feedback_count = len(feedback)
            patient.clinic_feedback_avg_rating = (
                sum([value for value in feedback.mapped("overall_rating") if value > 0])
                / len([value for value in feedback.mapped("overall_rating") if value > 0])
                if any(value > 0 for value in feedback.mapped("overall_rating"))
                else 0.0
            )
            patient.clinic_feedback_open_escalation_count = Escalation.search_count([
                ("patient_id", "=", patient.partner_id.id),
                ("company_id", "=", patient.company_id.id),
                ("state", "not in", ("resolved", "cancelled")),
            ])

    def action_open_clinic_feedback(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Feedback"),
            "res_model": "clinic.feedback",
            "view_mode": "list,form",
            "domain": [
                ("patient_id", "=", self.partner_id.id),
                ("company_id", "=", self.company_id.id),
            ],
        }


class ClinicDoctor(models.Model):
    """Doctor experience rollups use canonical Feedback plus unsynchronized legacy Booking responses."""

    _inherit = "clinic.doctor"

    clinic_feedback_count = fields.Integer(compute="_compute_clinic_feedback_metrics")
    clinic_feedback_avg_rating = fields.Float(
        compute="_compute_clinic_feedback_metrics",
        digits=(16, 2),
    )
    clinic_feedback_nps = fields.Float(
        string="NPS",
        compute="_compute_clinic_feedback_metrics",
        digits=(16, 2),
        help="Net Promoter Score: percentage of Promoters minus percentage of Detractors.",
    )

    def _compute_clinic_feedback_metrics(self):
        Feedback = self.env["clinic.feedback"]
        Legacy = self.env["booking.feedback.link"]
        for doctor in self:
            canonical = Feedback.search([
                ("doctor_id", "=", doctor.id),
            ])
            orphan = Legacy.search([
                ("doctor_id", "=", doctor.id),
                ("state", "=", "submitted"),
                ("clinic_feedback_id", "=", False),
            ])

            ratings = [value for value in canonical.mapped("overall_rating") if value > 0]
            for link in orphan:
                try:
                    value = int(link.rating_value or 0)
                except (TypeError, ValueError):
                    value = 0
                if value:
                    ratings.append(value)

            nps_values = [
                value for value in canonical.mapped("nps_score") if value >= 0
            ]
            promoters = len([value for value in nps_values if value >= 9])
            detractors = len([value for value in nps_values if value <= 6])

            doctor.clinic_feedback_count = len(canonical) + len(orphan)
            doctor.clinic_feedback_avg_rating = (
                sum(ratings) / len(ratings) if ratings else 0.0
            )
            doctor.clinic_feedback_nps = (
                ((promoters - detractors) / len(nps_values)) * 100.0
                if nps_values
                else 0.0
            )

    def action_open_clinic_feedback(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Doctor Feedback"),
            "res_model": "clinic.feedback",
            "view_mode": "list,form",
            "domain": [("doctor_id", "=", self.id)],
        }


class ClinicStaff(models.Model):
    """Service/staff satisfaction rollups without changing Staff master ownership."""

    _inherit = "clinic.staff"

    clinic_feedback_ids = fields.One2many(
        "clinic.feedback",
        "staff_id",
        string="Patient Feedback",
    )
    clinic_feedback_count = fields.Integer(compute="_compute_clinic_feedback_metrics")
    clinic_feedback_avg_rating = fields.Float(
        compute="_compute_clinic_feedback_metrics",
        digits=(16, 2),
    )

    def _compute_clinic_feedback_metrics(self):
        for staff in self:
            feedback = staff.clinic_feedback_ids
            staff.clinic_feedback_count = len(feedback)
            staff.clinic_feedback_avg_rating = (
                sum([value for value in feedback.mapped("overall_rating") if value > 0])
                / len([value for value in feedback.mapped("overall_rating") if value > 0])
                if any(value > 0 for value in feedback.mapped("overall_rating"))
                else 0.0
            )

    def action_open_clinic_feedback(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Staff Feedback"),
            "res_model": "clinic.feedback",
            "view_mode": "list,form",
            "domain": [("staff_id", "=", self.id)],
        }


class ResPartner(models.Model):
    """Preserve Booking's existing feedback summary while adding all canonical sources."""

    _inherit = "res.partner"

    # Partner statistics avoid double counting by excluding legacy links already canonicalized.
    def _compute_feedback_stats(self):
        Feedback = self.env["clinic.feedback"]
        Legacy = self.env["booking.feedback.link"]
        for partner in self:
            canonical = Feedback.search([("patient_id", "=", partner.id)])
            orphan = Legacy.search([
                ("patient_id", "=", partner.id),
                ("state", "=", "submitted"),
                ("clinic_feedback_id", "=", False),
            ])

            ratings = [value for value in canonical.mapped("overall_rating") if value > 0]
            for link in orphan:
                try:
                    value = int(link.rating_value or 0)
                except (TypeError, ValueError):
                    value = 0
                if value:
                    ratings.append(value)

            partner.feedback_count = len(canonical) + len(orphan)
            partner.feedback_avg_rating = (
                sum(ratings) / len(ratings) if ratings else 0.0
            )


class ClinicFeedbackRequestAutomation(models.Model):
    """Opt-in automation is owned by Feedback, not by Encounter/Post-Care workflow."""

    _inherit = "clinic.feedback.request"

    @api.model
    # Automation is opt-in, lookback-bounded and idempotent by source record.
    def _cron_auto_create_requests(self):
        now = fields.Datetime.now()
        companies = self.env["res.company"].sudo().search([
            "|",
            ("clinic_feedback_auto_from_encounter", "=", True),
            ("clinic_feedback_auto_from_postcare", "=", True),
        ])

        for company in companies:
            lookback = max(company.clinic_feedback_source_lookback_days or 2, 1)
            threshold = now - timedelta(days=lookback)

            if company.clinic_feedback_auto_from_encounter:
                encounters = self.env["clinic.encounter"].sudo().search([
                    ("company_id", "=", company.id),
                    ("state", "=", "done"),
                    ("date_end", "!=", False),
                    ("date_end", ">=", threshold),
                ])
                for encounter in encounters:
                    existing = self.search_count([
                        ("encounter_id", "=", encounter.id),
                        ("state", "not in", ("expired", "revoked")),
                    ])
                    if existing:
                        continue
                    request = self.create({"encounter_id": encounter.id})
                    if (
                        company.clinic_feedback_auto_send
                        and request.survey_id
                        and request.patient_id.email
                    ):
                        try:
                            request.action_send()
                        except UserError as exc:
                            request.message_post(
                                body=_("Automatic Feedback invitation was not sent: %s")
                                % str(exc)
                            )

            if company.clinic_feedback_auto_from_postcare:
                plans = self.env["clinic.postcare.plan"].sudo().search([
                    ("company_id", "=", company.id),
                    ("state", "in", ("completed", "closed")),
                    ("completed_at", "!=", False),
                    ("completed_at", ">=", threshold),
                ])
                for plan in plans:
                    existing = self.search_count([
                        ("postcare_plan_id", "=", plan.id),
                        ("state", "not in", ("expired", "revoked")),
                    ])
                    if existing:
                        continue
                    request = self.create({"postcare_plan_id": plan.id})
                    if (
                        company.clinic_feedback_auto_send
                        and request.survey_id
                        and request.patient_id.email
                    ):
                        try:
                            request.action_send()
                        except UserError as exc:
                            request.message_post(
                                body=_("Automatic Feedback invitation was not sent: %s")
                                % str(exc)
                            )
        return True
