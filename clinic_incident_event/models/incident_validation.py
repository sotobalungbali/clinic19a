from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicIncidentValidation(models.Model):
    """Incident scope, company, branch, SLA, security and timeline helpers."""

    _inherit = "clinic.incident"

    def _allowed_incident_branches(self, company):
        """Return the user's allowed branches using Clinic Branch semantics."""
        self.ensure_one()
        user = self.env.user.sudo()
        allowed = user.allowed_branch_ids.filtered(
            lambda branch: branch.company_id == company
        )
        if not allowed:
            allowed = self.env["clinic.branch"].sudo().search([
                ("company_id", "=", company.id),
            ])
        return allowed

    @api.model
    def _default_incident_branch(self, company, patient_id=False):
        """Resolve a branch only when the Company policy requires branch scope."""
        if not company.policy_branch_scope_incident_event:
            return self.env["clinic.branch"]

        user = self.env.user.sudo()
        allowed = user.allowed_branch_ids.filtered(
            lambda branch: branch.company_id == company
        )
        if not allowed:
            allowed = self.env["clinic.branch"].sudo().search([
                ("company_id", "=", company.id),
            ])

        context_branch_id = self.env.context.get("branch_id")
        if context_branch_id:
            context_branch = self.env["clinic.branch"].browse(
                int(context_branch_id)
            ).exists()
            if (
                context_branch
                and context_branch.company_id == company
                and context_branch in allowed
            ):
                return context_branch

        if (
            user.working_branch_id
            and user.working_branch_id.company_id == company
            and user.working_branch_id in allowed
        ):
            return user.working_branch_id

        if patient_id:
            patient = self.env["clinic.patient"].browse(patient_id).exists()
            patient_branch = (
                patient.partner_id.branch_id
                if patient and patient.partner_id
                else False
            )
            if (
                patient_branch
                and patient_branch.company_id == company
                and patient_branch in allowed
            ):
                return patient_branch

        if (
            company.default_branch_id
            and company.default_branch_id in allowed
        ):
            return company.default_branch_id

        return allowed[:1]

    @api.constrains(
        "company_id",
        "branch_id",
        "category_id",
        "patient_id",
        "doctor_id",
        "reported_by_staff_id",
        "case_owner_id",
        "reviewer_id",
        "involved_staff_ids",
        "encounter_id",
        "adverse_event_id",
        "booking_id",
        "queue_id",
        "emar_administration_id",
        "telemedicine_session_id",
        "telemedicine_thread_id",
        "feedback_escalation_id",
    )
    def _check_scope_consistency(self):
        for incident in self:
            incident.category_id._check_company_scope(incident.company_id)

            if (
                incident.company_id.policy_branch_scope_incident_event
                and not incident.branch_id
            ):
                raise ValidationError(
                    _(
                        "Branch is required because Incident/Event branch scope "
                        "is enabled for this company."
                    )
                )

            if (
                incident.branch_id
                and not incident.company_id.policy_branch_scope_incident_event
            ):
                raise ValidationError(
                    _(
                        "Branch must be empty because Incident/Event branch "
                        "scope is disabled for this company."
                    )
                )

            if (
                incident.branch_id
                and incident.branch_id.company_id != incident.company_id
            ):
                raise ValidationError(
                    _("Incident Branch belongs to another company.")
                )

            if (
                incident.branch_id
                and not self.env.su
                and incident.branch_id
                not in incident._allowed_incident_branches(incident.company_id)
            ):
                raise AccessError(
                    _("You are not allowed to use this Incident Branch.")
                )

            if (
                incident.reported_by_staff_id
                and incident.reported_by_staff_id.company_id
                and incident.reported_by_staff_id.company_id
                != incident.company_id
            ):
                raise ValidationError(
                    _("Reporter Staff belongs to another company.")
                )

            for role_name, user in (
                (_("Case Owner"), incident.case_owner_id),
                (_("Reviewer / Approver"), incident.reviewer_id),
            ):
                if user and incident.company_id not in user.company_ids:
                    raise ValidationError(
                        _(
                            "%(role)s does not have access to the Incident company."
                        ) % {"role": role_name}
                    )

            if (
                incident.patient_id
                and incident.patient_id.company_id != incident.company_id
            ):
                raise ValidationError(
                    _("Incident Patient belongs to another company.")
                )

            if (
                incident.doctor_id
                and incident.doctor_id.company_id != incident.company_id
            ):
                raise ValidationError(
                    _("Incident Doctor belongs to another company.")
                )

            for staff in incident.involved_staff_ids:
                if (
                    staff.company_id
                    and staff.company_id != incident.company_id
                ):
                    raise ValidationError(
                        _("An involved Staff member belongs to another company.")
                    )

            if incident.encounter_id:
                if incident.encounter_id.company_id != incident.company_id:
                    raise ValidationError(
                        _("Linked Encounter belongs to another company.")
                    )
                if (
                    incident.patient_id
                    and incident.encounter_id.patient_id != incident.patient_id
                ):
                    raise ValidationError(
                        _("Linked Encounter belongs to another Patient.")
                    )

            if incident.adverse_event_id:
                adverse = incident.adverse_event_id
                if adverse.company_id != incident.company_id:
                    raise ValidationError(
                        _("Linked Adverse Event belongs to another company.")
                    )
                if (
                    incident.patient_id
                    and adverse.patient_id != incident.patient_id
                ):
                    raise ValidationError(
                        _("Linked Adverse Event belongs to another Patient.")
                    )

            if incident.booking_id:
                booking = incident.booking_id
                if booking.company_id != incident.company_id:
                    raise ValidationError(
                        _("Linked Booking belongs to another company.")
                    )
                if (
                    incident.partner_id
                    and booking.patient_id != incident.partner_id
                ):
                    raise ValidationError(
                        _("Linked Booking belongs to another Patient Contact.")
                    )

            if incident.queue_id:
                queue = incident.queue_id
                if queue.company_id != incident.company_id:
                    raise ValidationError(
                        _("Linked Queue belongs to another company.")
                    )
                if (
                    incident.partner_id
                    and queue.patient_id != incident.partner_id
                ):
                    raise ValidationError(
                        _("Linked Queue belongs to another Patient Contact.")
                    )

            if incident.emar_administration_id:
                administration = incident.emar_administration_id
                if administration.company_id != incident.company_id:
                    raise ValidationError(
                        _("Linked eMAR Administration belongs to another company.")
                    )
                if (
                    incident.patient_id
                    and administration.patient_id != incident.patient_id
                ):
                    raise ValidationError(
                        _("Linked eMAR Administration belongs to another Patient.")
                    )

            if incident.telemedicine_session_id:
                session = incident.telemedicine_session_id
                if session.company_id != incident.company_id:
                    raise ValidationError(
                        _("Linked Telemedicine Session belongs to another company.")
                    )
                if (
                    incident.patient_id
                    and session.patient_id != incident.patient_id
                ):
                    raise ValidationError(
                        _("Linked Telemedicine Session belongs to another Patient.")
                    )
                if (
                    incident.branch_id
                    and session.branch_id
                    and session.branch_id != incident.branch_id
                ):
                    raise ValidationError(
                        _("Telemedicine Session belongs to another Branch.")
                    )

            if incident.telemedicine_thread_id:
                thread = incident.telemedicine_thread_id
                if thread.company_id != incident.company_id:
                    raise ValidationError(
                        _("Linked Secure Thread belongs to another company.")
                    )
                if (
                    incident.patient_id
                    and thread.patient_id != incident.patient_id
                ):
                    raise ValidationError(
                        _("Linked Secure Thread belongs to another Patient.")
                    )
                if (
                    incident.branch_id
                    and thread.branch_id
                    and thread.branch_id != incident.branch_id
                ):
                    raise ValidationError(
                        _("Secure Thread belongs to another Branch.")
                    )

            if incident.feedback_escalation_id:
                escalation = incident.feedback_escalation_id
                if escalation.company_id != incident.company_id:
                    raise ValidationError(
                        _("Linked Feedback Escalation belongs to another company.")
                    )
                if (
                    incident.partner_id
                    and escalation.patient_id != incident.partner_id
                ):
                    raise ValidationError(
                        _(
                            "Linked Feedback Escalation belongs to another "
                            "Patient Contact."
                        )
                    )
                if (
                    incident.branch_id
                    and escalation.branch_id
                    and escalation.branch_id != incident.branch_id
                ):
                    raise ValidationError(
                        _("Feedback Escalation belongs to another Branch.")
                    )

    @api.constrains("occurred_at", "detected_at", "reported_at")
    def _check_dates(self):
        for incident in self:
            if (
                incident.detected_at
                and incident.occurred_at
                and incident.detected_at < incident.occurred_at
            ):
                raise ValidationError(
                    _("Detected At cannot be earlier than Occurred At.")
                )
            if (
                incident.reported_at
                and incident.occurred_at
                and incident.reported_at < incident.occurred_at
            ):
                raise ValidationError(
                    _("Reported At cannot be earlier than Occurred At.")
                )

    def _require_reporter(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_incident_event.group_incident_reporter"
        ):
            raise AccessError(_("Incident Reporter access is required."))
        return True

    def _require_investigator(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_incident_event.group_incident_investigator"
        ):
            raise AccessError(_("Incident Investigator access is required."))
        return True

    def _require_manager(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_incident_event.group_incident_manager"
        ):
            raise AccessError(_("Incident Manager access is required."))
        return True

    def _default_due_dates(self, reference=None):
        self.ensure_one()
        reference = reference or fields.Datetime.now()
        category = self.category_id
        return {
            "triage_due_at": (
                reference + timedelta(hours=category.triage_target_hours)
                if category.triage_target_hours
                else False
            ),
            "investigation_due_at": (
                reference
                + timedelta(hours=category.investigation_target_hours)
                if category.investigation_target_hours
                else False
            ),
            "action_plan_due_at": (
                reference + timedelta(hours=category.action_plan_target_hours)
                if category.action_plan_target_hours
                else False
            ),
        }

    def _log_timeline(
        self,
        event_type,
        title,
        note=False,
        from_state=False,
        to_state=False,
    ):
        Timeline = self.env["clinic.incident.timeline"].sudo()
        for incident in self:
            Timeline.with_context(
                incident_timeline_system=True
            ).create({
                "incident_id": incident.id,
                "event_type": event_type,
                "title": title,
                "note": note or False,
                "from_state": from_state or False,
                "to_state": to_state or False,
                "event_at": fields.Datetime.now(),
                "user_id": self.env.user.id,
            })
        return True
