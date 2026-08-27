from datetime import timedelta

from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicTelemedicineSessionWorkflow(models.Model):
    """Teleconsultation workflow, readiness, provider and join controls."""

    _inherit = "clinic.telemedicine.session"

    def _require_clinician(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_telemedicine_secure_messaging.group_telemedicine_clinician"
        ):
            raise AccessError(_("Telemedicine Clinician access is required."))
        return True

    def _require_manager(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_telemedicine_secure_messaging.group_telemedicine_manager"
        ):
            raise AccessError(_("Telemedicine Manager access is required."))
        return True

    def _validate_operational_readiness(self):
        self.ensure_one()
        self._check_source_consistency()

        if not self.doctor_id.telemedicine_enabled:
            raise UserError(
                _("The selected Doctor is not enabled for Telemedicine.")
            )

        if (
            self.branch_id
            and "policy_branch_scope_telemedicine" in self.company_id._fields
            and not self.company_id.policy_branch_scope_telemedicine
        ):
            raise UserError(
                _(
                    "Branch-scoped Telemedicine is disabled by Company policy. "
                    "Remove the Branch or enable the branch policy."
                )
            )

        if (
            self.company_id.clinic_telemedicine_require_signed_consent
            and (
                not self.consent_form_id
                or self.consent_form_id.state != "signed"
            )
        ):
            raise UserError(
                _(
                    "A signed Telemedicine Consent is required before this "
                    "session can become Ready."
                )
            )
        return True

    def action_schedule(self):
        self._require_clinician()
        for session in self:
            if session.state != "draft":
                raise UserError(_("Only Draft sessions can be scheduled."))
            session._validate_operational_readiness()

            if session.company_id.clinic_telemedicine_auto_create_thread:
                session._ensure_secure_thread()

            session.with_context(
                telemedicine_session_transition=True
            ).write({"state": "scheduled"})
        return True

    def _provision_meeting_via_provider(self):
        """Provider-neutral extension hook for future clinic_integration_api.

        Return a dictionary containing at least:
        `meeting_url`; optionally `provider_reference`.
        The base addon returns an empty dictionary and never fabricates success.
        """
        self.ensure_one()
        return {}

    def action_provision_meeting(self):
        self.ensure_one()
        self._require_clinician()
        if self.provider_mode != "provider_hook":
            raise UserError(
                _("This Session is configured for a Manual HTTPS Meeting URL.")
            )
        payload = self._provision_meeting_via_provider() or {}
        meeting_url = payload.get("meeting_url")
        if not meeting_url:
            raise UserError(
                _(
                    "No Telemedicine meeting provider is installed. "
                    "Use Manual HTTPS Meeting URL, or let a future "
                    "clinic_integration_api provider override the provisioning hook."
                )
            )
        self._validate_https_url(meeting_url)
        self.write({
            "meeting_url": meeting_url,
            "provider_reference": payload.get("provider_reference") or False,
        })
        return True

    def action_mark_ready(self):
        self._require_clinician()
        for session in self:
            if session.state != "scheduled":
                raise UserError(
                    _("Only Scheduled sessions can be marked Ready.")
                )
            session._validate_operational_readiness()

            if not session.meeting_url and session.provider_mode == "provider_hook":
                session.action_provision_meeting()
            if not session.meeting_url:
                raise UserError(
                    _("Provide a secure HTTPS Meeting URL before marking Ready.")
                )

            session._validate_https_url(session.meeting_url)
            session._ensure_secure_thread()
            session.with_context(
                telemedicine_session_transition=True
            ).write({"state": "ready"})
        return True

    def action_start(self):
        self._require_clinician()
        for session in self:
            if session.state != "ready":
                raise UserError(_("Only a Ready Session can be started."))
            session.with_context(
                telemedicine_session_transition=True
            ).write({
                "state": "in_progress",
                "started_at": fields.Datetime.now(),
            })
        return True

    def action_complete(self):
        self._require_clinician()
        for session in self:
            if session.state != "in_progress":
                raise UserError(
                    _("Only an In-Progress Session can be completed.")
                )
            session.with_context(
                telemedicine_session_transition=True
            ).write({
                "state": "completed",
                "ended_at": fields.Datetime.now(),
            })
        return True

    def action_cancel(self):
        self._require_clinician()
        for session in self:
            if session.state in ("completed", "cancelled", "no_show"):
                continue
            session.with_context(
                telemedicine_session_transition=True
            ).write({
                "state": "cancelled",
                "cancelled_at": fields.Datetime.now(),
                "cancellation_reason": _(
                    "Cancelled by %(user)s"
                ) % {"user": self.env.user.display_name},
            })
        return True

    def action_mark_no_show(self):
        self._require_clinician()
        for session in self:
            if session.state not in ("scheduled", "ready"):
                raise UserError(
                    _("Only Scheduled or Ready sessions can be marked No Show.")
                )
            session.with_context(
                telemedicine_session_transition=True
            ).write({
                "state": "no_show",
                "ended_at": fields.Datetime.now(),
            })
        return True

    def _patient_join_allowed(self, now=None):
        self.ensure_one()
        now = now or fields.Datetime.now()

        if (
            self.state not in ("ready", "in_progress")
            or not self.meeting_url
            or not self.scheduled_start
            or not self.scheduled_end
        ):
            return False

        early = self.company_id.clinic_telemedicine_early_join_minutes or 15
        late = self.company_id.clinic_telemedicine_late_join_minutes or 60
        earliest = self.scheduled_start - timedelta(minutes=early)
        latest = self.scheduled_end + timedelta(minutes=late)
        return earliest <= now <= latest

    def _record_patient_join(self):
        self.ensure_one()
        portal_partner_id = self.env.context.get(
            "telemedicine_portal_partner_id"
        )
        portal_user_id = self.env.context.get(
            "telemedicine_portal_user_id"
        )
        if not (
            self.env.context.get("telemedicine_patient_join")
            and portal_partner_id == self.partner_id.id
            and portal_user_id
        ):
            raise AccessError(
                _("Patient join evidence requires a controlled exact-patient Portal action.")
            )
        if not self.patient_joined_at:
            self.write({"patient_joined_at": fields.Datetime.now()})
        return True

    def action_join_meeting(self):
        self.ensure_one()
        self._require_clinician()
        if self.state not in ("ready", "in_progress"):
            raise UserError(
                _("The meeting can only be opened when the Session is Ready or In Progress.")
            )
        if not self.meeting_url:
            raise UserError(_("No Meeting URL is configured."))
        self._validate_https_url(self.meeting_url)
        if not self.host_joined_at:
            self.with_context(telemedicine_host_join=True).write({
                "host_joined_at": fields.Datetime.now(),
            })
        return {
            "type": "ir.actions.act_url",
            "url": self.meeting_url,
            "target": "new",
        }

