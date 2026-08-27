from odoo import fields, models, _
from odoo.exceptions import UserError


class ClinicIncidentWorkflow(models.Model):
    """Incident lifecycle with explicit enterprise compliance gates."""

    _inherit = "clinic.incident"

    def action_report(self):
        self._require_reporter()
        for incident in self:
            if incident.state != "draft":
                raise UserError(_("Only a Draft Incident can be reported."))
            if not incident.description:
                raise UserError(_("Incident Narrative is required."))

            now = fields.Datetime.now()
            due = incident._default_due_dates(reference=now)
            incident.with_context(incident_transition=True).write({
                "state": "reported",
                "reported_at": now,
                **due,
            })
            incident._log_timeline(
                "state",
                _("Incident Reported"),
                from_state="draft",
                to_state="reported",
            )

            owner = incident.case_owner_id or self.env.user
            incident.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Incident triage"),
                user_id=owner.id,
                date_deadline=(
                    fields.Date.to_date(incident.triage_due_at)
                    if incident.triage_due_at
                    else fields.Date.today()
                ),
            )
        return True

    def action_start_triage(self):
        self._require_investigator()
        for incident in self:
            if incident.state != "reported":
                raise UserError(
                    _("Only a Reported Incident can enter Triage.")
                )
            if not incident.case_owner_id:
                incident.case_owner_id = self.env.user.id

            incident.with_context(incident_transition=True).write({
                "state": "triage",
            })
            incident._log_timeline(
                "state",
                _("Triage Started"),
                from_state="reported",
                to_state="triage",
            )
        return True

    def action_review_reportability(self):
        self._require_investigator()
        for incident in self:
            if incident.state not in (
                "reported",
                "triage",
                "investigation",
                "action_plan",
            ):
                raise UserError(
                    _(
                        "Reportability can only be reviewed on an active "
                        "Incident."
                    )
                )
            incident.with_context(incident_transition=True).write({
                "reportability_reviewed": True,
            })
            incident._log_timeline(
                "regulatory",
                _("Reportability Reviewed"),
                _("Regulatory reporting required: %(required)s") % {
                    "required": (
                        _("Yes")
                        if incident.regulatory_required
                        else _("No")
                    ),
                },
            )
        return True

    def action_start_investigation(self):
        self._require_investigator()
        for incident in self:
            if incident.state != "triage":
                raise UserError(
                    _("Only an Incident in Triage can enter Investigation.")
                )
            if (
                incident.needs_regulatory_review
                and not incident.reportability_reviewed
            ):
                raise UserError(
                    _(
                        "Complete the regulatory reportability review before "
                        "starting Investigation."
                    )
                )

            incident.with_context(incident_transition=True).write({
                "state": "investigation",
            })
            incident._log_timeline(
                "state",
                _("Investigation Started"),
                from_state="triage",
                to_state="investigation",
            )

            if not incident.investigation_ids:
                self.env["clinic.incident.investigation"].create({
                    "incident_id": incident.id,
                    "methodology": "five_whys",
                    "lead_user_id": (
                        incident.case_owner_id.id
                        or self.env.user.id
                    ),
                })
        return True

    def action_move_to_action_plan(self):
        self._require_investigator()
        for incident in self:
            if incident.state != "investigation":
                raise UserError(
                    _(
                        "Only an Incident in Investigation can enter "
                        "Action Plan."
                    )
                )

            if (
                incident.category_id.requires_investigation
                and not incident.completed_investigation_count
            ):
                raise UserError(
                    _(
                        "Complete at least one structured Investigation before "
                        "moving to Action Plan."
                    )
                )

            completed = incident.investigation_ids.filtered(
                lambda investigation:
                investigation.state == "completed"
            )
            if completed and not incident.root_cause_summary:
                incident.with_context(incident_transition=True).write({
                    "root_cause_summary": completed[-1].root_cause,
                })

            incident.with_context(incident_transition=True).write({
                "state": "action_plan",
            })
            incident._log_timeline(
                "state",
                _("Action Plan Started"),
                from_state="investigation",
                to_state="action_plan",
            )
        return True

    def action_move_to_verification(self):
        self._require_investigator()
        for incident in self:
            if incident.state != "action_plan":
                raise UserError(
                    _(
                        "Only an Incident in Action Plan can enter "
                        "Verification."
                    )
                )

            active_actions = incident.action_ids.filtered(
                lambda action: action.state != "cancelled"
            )
            if incident.category_id.requires_capa and not active_actions:
                raise UserError(
                    _(
                        "This Incident Category requires at least one CAPA "
                        "before Verification."
                    )
                )

            incomplete = active_actions.filtered(
                lambda action:
                action.state not in ("done", "verified")
            )
            if incomplete:
                raise UserError(
                    _(
                        "Complete every active CAPA before entering "
                        "Verification."
                    )
                )

            incident.with_context(incident_transition=True).write({
                "state": "verification",
            })
            incident._log_timeline(
                "state",
                _("Verification Started"),
                from_state="action_plan",
                to_state="verification",
            )
        return True

    def action_mark_regulator_reported(self):
        self._require_manager()
        for incident in self:
            if not incident.regulatory_required:
                raise UserError(
                    _(
                        "This Incident is not marked as requiring "
                        "regulatory reporting."
                    )
                )
            if not incident.regulator_body:
                raise UserError(
                    _("Specify the Regulatory Body before marking reported.")
                )
            if not incident.regulator_reference:
                raise UserError(
                    _(
                        "Specify the Regulatory Reference before marking "
                        "reported."
                    )
                )

            incident.with_context(incident_transition=True).write({
                "reportability_reviewed": True,
                "regulator_reported_at": fields.Datetime.now(),
            })
            incident._log_timeline(
                "regulatory",
                _("Regulator Reporting Recorded"),
                _("%(body)s / %(reference)s") % {
                    "body": incident.regulator_body,
                    "reference": incident.regulator_reference,
                },
            )
        return True

    def action_close(self):
        self._require_manager()
        for incident in self:
            if incident.state != "verification":
                raise UserError(
                    _("Only an Incident in Verification can be closed.")
                )
            if not incident.resolution_summary:
                raise UserError(
                    _("Resolution Summary is required before closing.")
                )

            active_actions = incident.action_ids.filtered(
                lambda action: action.state != "cancelled"
            )
            unverified = active_actions.filtered(
                lambda action: action.state != "verified"
            )
            if unverified:
                raise UserError(
                    _("Every active CAPA must be Verified before closing.")
                )

            if (
                incident.category_id.requires_investigation
                and not incident.completed_investigation_count
            ):
                raise UserError(
                    _("A completed Investigation is required before closing.")
                )

            if (
                incident.regulatory_required
                and not incident.regulator_reported_at
            ):
                raise UserError(
                    _(
                        "Record regulator reporting evidence before closing "
                        "this reportable Incident."
                    )
                )

            now = fields.Datetime.now()
            incident.with_context(incident_transition=True).write({
                "state": "closed",
                "closed_at": now,
                "closed_by_id": self.env.user.id,
            })
            incident._log_timeline(
                "state",
                _("Incident Closed"),
                from_state="verification",
                to_state="closed",
            )
        return True

    def action_cancel(self):
        self._require_manager()
        for incident in self:
            if incident.state in ("closed", "cancelled"):
                continue
            if not (incident.cancellation_reason or "").strip():
                raise UserError(
                    _(
                        "Cancellation Reason is required before cancelling "
                        "an Incident."
                    )
                )

            old_state = incident.state
            incident.with_context(incident_transition=True).write({
                "state": "cancelled",
            })
            incident._log_timeline(
                "state",
                _("Incident Cancelled"),
                incident.cancellation_reason,
                from_state=old_state,
                to_state="cancelled",
            )
        return True
