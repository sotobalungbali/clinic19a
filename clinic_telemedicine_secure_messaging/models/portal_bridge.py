from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class ClinicPortalProfile(models.Model):
    """Explicit feature grants layered on the frozen Clinic Portal profile."""

    _inherit = "clinic.portal.profile"

    allow_telemedicine_access = fields.Boolean(
        string="Allow Teleconsultation Access",
        default=False,
        help=(
            "Explicitly grants the patient access to their own Telemedicine "
            "Session list/detail/join routes."
        ),
    )
    allow_secure_messaging = fields.Boolean(
        string="Allow Secure Messaging",
        default=False,
        help=(
            "Explicitly grants the patient access to exact-patient Secure "
            "Messaging routes."
        ),
    )
    telemedicine_session_count = fields.Integer(
        compute="_compute_telemedicine_counts"
    )
    secure_thread_count = fields.Integer(
        compute="_compute_telemedicine_counts"
    )

    @api.depends(
        "partner_id",
        "company_id",
        "state",
        "allow_telemedicine_access",
        "allow_secure_messaging",
    )
    def _compute_telemedicine_counts(self):
        Session = self.env["clinic.telemedicine.session"].sudo()
        Thread = self.env["clinic.telemedicine.thread"].sudo()
        for profile in self:
            profile.telemedicine_session_count = 0
            profile.secure_thread_count = 0
            if profile.state != "active":
                continue
            if profile.allow_telemedicine_access:
                profile.telemedicine_session_count = Session.search_count(
                    profile._portal_telemedicine_session_domain()
                )
            if profile.allow_secure_messaging:
                profile.secure_thread_count = Thread.search_count(
                    profile._portal_secure_thread_domain()
                )

    def write(self, vals):
        feature_fields = {
            "allow_telemedicine_access",
            "allow_secure_messaging",
        }
        if feature_fields.intersection(vals) and not self.env.su:
            allowed = (
                self.env.user.has_group(
                    "clinic_telemedicine_secure_messaging.group_telemedicine_manager"
                )
                or self.env.user.has_group(
                    "clinic_portal.group_patient_portal_manager"
                )
            )
            if not allowed:
                raise AccessError(
                    _(
                        "Telemedicine Portal feature grants require a "
                        "Telemedicine Manager or Patient Portal Manager."
                    )
                )
        return super().write(vals)

    def action_enable_telemedicine_access(self):
        self._require_telemedicine_access_manager()
        self.write({"allow_telemedicine_access": True})
        return True

    def action_disable_telemedicine_access(self):
        self._require_telemedicine_access_manager()
        self.write({"allow_telemedicine_access": False})
        return True

    def action_enable_secure_messaging(self):
        self._require_telemedicine_access_manager()
        self.write({"allow_secure_messaging": True})
        return True

    def action_disable_secure_messaging(self):
        self._require_telemedicine_access_manager()
        self.write({"allow_secure_messaging": False})
        return True

    def _require_telemedicine_access_manager(self):
        if self.env.su:
            return True
        if not (
            self.env.user.has_group(
                "clinic_telemedicine_secure_messaging.group_telemedicine_manager"
            )
            or self.env.user.has_group(
                "clinic_portal.group_patient_portal_manager"
            )
        ):
            raise AccessError(
                _(
                    "Telemedicine Portal feature grants require a "
                    "Telemedicine Manager or Patient Portal Manager."
                )
            )
        return True

    def _portal_telemedicine_session_domain(self):
        self.ensure_one()
        return [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
        ]

    def _portal_secure_thread_domain(self):
        self.ensure_one()
        return [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "!=", "archived"),
        ]

    def _portal_telemedicine_counts(self):
        self.ensure_one()
        values = {
            "clinic_telemedicine_session_count": 0,
            "clinic_secure_thread_count": 0,
        }
        if self.state != "active":
            return values

        if self.allow_telemedicine_access:
            values["clinic_telemedicine_session_count"] = self.env[
                "clinic.telemedicine.session"
            ].sudo().search_count(
                self._portal_telemedicine_session_domain()
            )

        if self.allow_secure_messaging:
            values["clinic_secure_thread_count"] = self.env[
                "clinic.telemedicine.thread"
            ].sudo().search_count(
                self._portal_secure_thread_domain()
            )
        return values

    def _portal_summary_counts(self):
        values = super()._portal_summary_counts()
        values.update(self._portal_telemedicine_counts())
        return values

    def action_open_telemedicine_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Teleconsultations"),
            "res_model": "clinic.telemedicine.session",
            "view_mode": "kanban,list,form",
            "domain": self._portal_telemedicine_session_domain(),
        }

    def action_open_secure_threads(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Secure Threads"),
            "res_model": "clinic.telemedicine.thread",
            "view_mode": "kanban,list,form",
            "domain": self._portal_secure_thread_domain(),
        }

