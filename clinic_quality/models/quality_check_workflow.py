from odoo import fields, models, _
from odoo.exceptions import UserError

from .scope_mixin import (
    QUALITY_CHECK_GENERATE_TOKEN,
    QUALITY_CHECK_TRANSITION_TOKEN,
)


class ClinicQualityCheckWorkflow(models.Model):
    """Lifecycle actions for executable Quality Checks."""

    _inherit = "clinic.quality.check"

    def _generate_control_lines(self):
        for check in self:
            if check.line_ids:
                continue

            template_lines = check.template_id.line_ids.filtered(
                "active"
            )
            if not template_lines:
                raise UserError(
                    _("The Quality Template has no active controls.")
                )

            values = []
            for line in template_lines:
                values.append({
                    "check_id": check.id,
                    "template_line_id": line.id,
                    "sequence": line.sequence,
                    "control_code": line.control_code,
                    "requirement": line.requirement,
                    "guidance": line.guidance,
                    "evidence_required": line.evidence_required,
                    "critical": line.critical,
                    "weight": line.weight,
                })

            self.env["clinic.quality.check.line"].with_context(
                quality_check_generate=QUALITY_CHECK_GENERATE_TOKEN
            ).create(values)
        return True

    def action_start(self):
        self._quality_require_inspector()

        for check in self:
            if check.state != "draft":
                raise UserError(
                    _("Only a Draft Quality Check can be started.")
                )
            if check.template_id.state != "active":
                raise UserError(
                    _("The Quality Template is no longer Active.")
                )

            check._generate_control_lines()
            check.with_context(
                quality_check_transition=QUALITY_CHECK_TRANSITION_TOKEN
            ).write({
                "state": "in_progress",
                "started_at": fields.Datetime.now(),
            })
            check.message_post(
                body=_("Quality Check started by %s.")
                % self.env.user.display_name
            )
        return True

    def action_submit_review(self):
        self._quality_require_inspector()

        for check in self:
            if check.state != "in_progress":
                raise UserError(
                    _(
                        "Only an In Progress Quality Check "
                        "can be submitted."
                    )
                )

            if check.pending_count:
                raise UserError(
                    _(
                        "Resolve all Pending controls before "
                        "submitting for review."
                    )
                )

            for line in check.line_ids:
                line._validate_quality_evidence()

            reviewer = (
                check.reviewed_by_user_id
                or check.company_id.clinic_quality_default_approver_id
            )
            if not reviewer:
                raise UserError(
                    _(
                        "Assign a Reviewer / Approver before "
                        "submitting the Quality Check."
                    )
                )

            check.with_context(
                quality_check_transition=QUALITY_CHECK_TRANSITION_TOKEN
            ).write({
                "state": "review",
                "reviewed_by_user_id": reviewer.id,
                "submitted_at": fields.Datetime.now(),
            })

            check.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Review Quality Check %s") % check.name,
                user_id=reviewer.id,
            )
            check.message_post(
                body=_("Quality Check submitted for review.")
            )
        return True

    def action_return_to_progress(self):
        self._quality_require_approver()

        for check in self:
            if check.state != "review":
                raise UserError(
                    _("Only a Check in Review can be returned.")
                )

            check.with_context(
                quality_check_transition=QUALITY_CHECK_TRANSITION_TOKEN
            ).write({
                "state": "in_progress",
                "submitted_at": False,
            })
            check.message_post(
                body=_(
                    "Quality Check returned for correction by %s."
                ) % self.env.user.display_name
            )
        return True

    def action_create_incidents_for_failed_lines(self):
        self._quality_require_approver()

        for check in self:
            if check.state not in ("review", "closed"):
                raise UserError(
                    _(
                        "Incident escalation is available from "
                        "Review/Closed Quality Checks."
                    )
                )
            failed = check.line_ids.filtered(
                lambda line:
                line.result == "fail"
                and not line.incident_count
            )
            for line in failed:
                line.action_create_incident()
        return check.action_open_incidents()

    def action_close(self):
        self._quality_require_approver()

        for check in self:
            if check.state != "review":
                raise UserError(
                    _("Only a Quality Check in Review can be closed.")
                )

            if (
                check.overall_result
                in ("nonconforming", "critical_nonconformity")
                and not (check.review_summary or "").strip()
            ):
                raise UserError(
                    _(
                        "Review Summary is required for a "
                        "nonconforming Quality Check."
                    )
                )

            if (
                check.company_id.clinic_quality_require_incident_critical
            ):
                missing_incident = check.line_ids.filtered(
                    lambda line:
                    line.result == "fail"
                    and line.critical
                    and not line.incident_count
                )
                if missing_incident:
                    raise UserError(
                        _(
                            "Critical failed controls must be escalated "
                            "to Incident cases before closing."
                        )
                    )

            check.with_context(
                quality_check_transition=QUALITY_CHECK_TRANSITION_TOKEN
            ).write({
                "state": "closed",
                "closed_at": fields.Datetime.now(),
                "closed_by_user_id": self.env.user.id,
            })
            check.message_post(
                body=_(
                    "Quality Check closed by %(user)s with result %(result)s "
                    "and score %(score).2f%%."
                ) % {
                    "user": self.env.user.display_name,
                    "result": dict(
                        check._fields["overall_result"].selection
                    ).get(check.overall_result),
                    "score": check.compliance_score,
                }
            )
        return True

    def action_cancel(self):
        self._quality_require_manager()

        for check in self:
            if check.state in ("closed", "cancelled"):
                continue
            if not (check.cancellation_reason or "").strip():
                raise UserError(
                    _("Cancellation Reason is required.")
                )

            check.with_context(
                quality_check_transition=QUALITY_CHECK_TRANSITION_TOKEN
            ).write({
                "state": "cancelled",
            })
            check.message_post(
                body=_(
                    "Quality Check cancelled by %(user)s. Reason: %(reason)s"
                ) % {
                    "user": self.env.user.display_name,
                    "reason": check.cancellation_reason,
                }
            )
        return True
