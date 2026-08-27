from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request


class ClinicFeedbackPortal(http.Controller):
    """Public token endpoint shared by canonical requests and legacy Booking links."""

    def _resolve_token(self, token):
        feedback_request = (
            request.env["clinic.feedback.request"]
            .sudo()
            .sudo_find_by_token(token)
        )
        if feedback_request:
            return "request", feedback_request

        booking_link = (
            request.env["booking.feedback.link"]
            .sudo()
            .sudo_find_by_token(token)
        )
        if booking_link:
            return "booking", booking_link

        return False, False

    @http.route(
        "/clinic/feedback/<string:token>",
        type="http",
        auth="public",
        website=True,
        methods=["GET", "POST"],
        csrf=True,
    )
    def feedback_form(self, token, **post):
        source_kind, source = self._resolve_token(token)
        if not source:
            return request.not_found()

        if source_kind == "request":
            if source.state in ("expired", "revoked"):
                return request.render(
                    "clinic_feedback.public_feedback_unavailable",
                    {"reason": _("This feedback link is no longer available.")},
                )
            if source.state == "submitted":
                return request.render(
                    "clinic_feedback.public_feedback_thank_you",
                    {"survey": source.survey_id},
                )
            survey = source.survey_id
            source.action_mark_opened()
        else:
            if source.state in ("expired", "revoked") or source.is_expired:
                return request.render(
                    "clinic_feedback.public_feedback_unavailable",
                    {"reason": _("This feedback link is no longer available.")},
                )
            if source.state == "submitted":
                return request.render(
                    "clinic_feedback.public_feedback_thank_you",
                    {
                        "survey": (
                            source.feedback_survey_id
                            or source.company_id.clinic_feedback_default_survey_id
                        )
                    },
                )
            survey = (
                source.feedback_survey_id
                or source.company_id.clinic_feedback_default_survey_id
            )
            source.action_mark_opened()

        if request.httprequest.method == "POST":
            try:
                answer_values = {}
                if survey:
                    for question in survey.question_ids.filtered("active"):
                        answer_values[str(question.id)] = post.get(
                            f"q_{question.id}"
                        )

                anonymous_public = post.get("anonymous_public") in (
                    "1",
                    "true",
                    "on",
                    "yes",
                )

                if source_kind == "request":
                    source.submit_public(
                        overall_rating=post.get("overall_rating"),
                        nps_score=post.get("nps_score"),
                        would_recommend=post.get("would_recommend"),
                        feedback_type=post.get("feedback_type") or "satisfaction",
                        comment=post.get("comment"),
                        answer_values=answer_values,
                        anonymous_public=anonymous_public,
                    )
                else:
                    source.action_submit_feedback(
                        rating_value=post.get("overall_rating"),
                        comment=post.get("comment"),
                        would_recommend=post.get("would_recommend"),
                        nps_score=post.get("nps_score"),
                        feedback_type=post.get("feedback_type") or "satisfaction",
                        answer_values=answer_values,
                        anonymous_public=anonymous_public,
                    )

                return request.render(
                    "clinic_feedback.public_feedback_thank_you",
                    {"survey": survey},
                )
            except UserError as exc:
                return request.render(
                    "clinic_feedback.public_feedback_form",
                    {
                        "source_kind": source_kind,
                        "source": source,
                        "survey": survey,
                        "token": token,
                        "error": str(exc),
                        "posted": post,
                    },
                )

        return request.render(
            "clinic_feedback.public_feedback_form",
            {
                "source_kind": source_kind,
                "source": source,
                "survey": survey,
                "token": token,
                "error": False,
                "posted": {},
            },
        )
