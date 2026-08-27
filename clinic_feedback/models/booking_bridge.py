from odoo import api, fields, models, _


class BookingFeedbackLink(models.Model):
    """Extend, never redefine, the Booking-owned feedback invitation model."""

    _inherit = "booking.feedback.link"

    feedback_survey_id = fields.Many2one(
        "clinic.feedback.survey",
        string="Clinic Feedback Survey",
        check_company=True,
        ondelete="set null",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    clinic_feedback_id = fields.Many2one(
        "clinic.feedback",
        string="Canonical Feedback",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if not vals.get("feedback_survey_id") and vals.get("booking_id"):
                booking = self.env["booking.booking"].browse(vals["booking_id"])
                if booking.exists():
                    survey = booking.company_id.clinic_feedback_default_survey_id
                    if survey and survey.state == "active":
                        vals["feedback_survey_id"] = survey.id
            prepared.append(vals)
        return super().create(prepared)

    # Booking super() always writes the legacy response first; canonical sync is strictly additive.
    def action_submit_feedback(
        self,
        rating_value=None,
        comment=None,
        would_recommend=None,
        nps_score=None,
        feedback_type="satisfaction",
        answer_values=None,
        anonymous_public=False,
    ):
        # Preserve the complete Booking lifecycle/content write first. Canonical
        # synchronization is additive and never replaces clinic_booking ownership.
        result = super().action_submit_feedback(
            rating_value=rating_value,
            comment=comment,
            would_recommend=would_recommend,
        )
        for link in self:
            if link.state != "submitted" or link.clinic_feedback_id:
                continue
            feedback = self.env["clinic.feedback"].sudo().create_from_booking_link(
                link,
                nps_score=nps_score,
                feedback_type=feedback_type,
                answer_values=answer_values or {},
                anonymous_public=anonymous_public,
            )
            if feedback:
                link.clinic_feedback_id = feedback.id
        return result

    def action_open_clinic_feedback(self):
        self.ensure_one()
        if not self.clinic_feedback_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Canonical Patient Feedback"),
            "res_model": "clinic.feedback",
            "view_mode": "form",
            "res_id": self.clinic_feedback_id.id,
        }
