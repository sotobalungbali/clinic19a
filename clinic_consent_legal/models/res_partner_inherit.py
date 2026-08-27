
# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/res_partner_inherit.py
#
# Extends res.partner with Consent & Legal capabilities for ClinicOne (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# Key capabilities:
# - One2many relations to patient consents and guardian-consents
# - Portal deep link to patient's consents
# - Metrics: total/pending/signed counts, last consent references
# - Smart actions: open all/pending/signed consents, open portal, request a new consent,
#   bulk send reminders for pending consents
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # RELATIONS
    # -------------------------------------------------------------------------
    consent_form_ids = fields.One2many(
        "clinic.consent.form",
        "patient_id",
        string="Consents (as Patient)",
        help="All consent records where this contact is the Patient."
    )

    consent_guardian_form_ids = fields.One2many(
        "clinic.consent.form",
        "guardian_partner_id",
        string="Consents (as Guardian/Representative)",
        help="All consent records where this contact signed as Guardian or Representative."
    )

    # -------------------------------------------------------------------------
    # METRICS
    # -------------------------------------------------------------------------
    consent_count = fields.Integer(
        string="Total Consents",
        compute="_compute_consent_metrics",
        help="Total number of consents related to this partner (as Patient)."
    )

    consent_pending_count = fields.Integer(
        string="Pending Consents",
        compute="_compute_consent_metrics",
        help="Number of consents waiting for signature (as Patient)."
    )

    consent_signed_count = fields.Integer(
        string="Signed Consents",
        compute="_compute_consent_metrics",
        help="Number of signed consents (as Patient)."
    )

    consent_guardian_count = fields.Integer(
        string="Guardian Consents",
        compute="_compute_consent_metrics",
        help="Number of consents where this partner is a Guardian/Representative."
    )

    last_consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Last Consent",
        compute="_compute_consent_last",
        help="Most recently created consent for this partner (as Patient)."
    )

    last_consent_signed_on = fields.Datetime(
        string="Last Signed On",
        compute="_compute_consent_last",
        help="Signature time of the most recently signed consent (as Patient)."
    )

    # -------------------------------------------------------------------------
    # PORTAL / PREFERENCES
    # -------------------------------------------------------------------------
    consent_portal_url = fields.Char(
        string="Consents Portal URL",
        compute="_compute_consent_portal_url",
        help="Direct portal URL for this patient to review/sign their consents."
    )

    consent_portal_opt_out = fields.Boolean(
        string="Opt-out of Portal Consent",
        help="If enabled, this contact prefers not to use the portal for consent signing."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _company_domain(self):
        """Helper: domain restricting to the partner's company (if applicable)."""
        # In multi-company setups, limit by allowed companies of current env.
        companies = self.env.companies.ids
        return [("company_id", "in", companies)]

    def _compute_consent_metrics(self):
        Consent = self.env["clinic.consent.form"].sudo()
        for partner in self:
            if partner.is_company:
                # Typically consents are tied to individuals; still compute if used otherwise
                patient_domain = [("patient_id", "=", partner.id)]
            else:
                patient_domain = [("patient_id", "=", partner.id)]

            guardian_domain = [("guardian_partner_id", "=", partner.id)]

            # Apply multi-company filter
            patient_domain += self._company_domain()
            guardian_domain += self._company_domain()

            total = Consent.search_count(patient_domain)
            pending = Consent.search_count(patient_domain + [("state", "=", "to_sign")])
            signed = Consent.search_count(patient_domain + [("state", "=", "signed")])
            guardian_total = Consent.search_count(guardian_domain)

            partner.consent_count = total
            partner.consent_pending_count = pending
            partner.consent_signed_count = signed
            partner.consent_guardian_count = guardian_total

    def _compute_consent_last(self):
        Consent = self.env["clinic.consent.form"].sudo()
        for partner in self:
            domain = [("patient_id", "=", partner.id)] + self._company_domain()
            last = Consent.search(domain, order="create_date desc, id desc", limit=1)
            partner.last_consent_id = last.id or False

            last_signed = Consent.search(
                domain + [("state", "=", "signed")],
                order="signature_datetime desc, write_date desc, id desc",
                limit=1,
            )
            partner.last_consent_signed_on = last_signed.signature_datetime if last_signed else False

    def _compute_consent_portal_url(self):
        for partner in self:
            # Deep-link to a filtered consent list on the patient portal.
            # A portal controller can read partner_id querystring to filter.
            partner.consent_portal_url = f"/my/consents?partner_id={partner.id}"

    # -------------------------------------------------------------------------
    # ACTIONS (SMART BUTTONS)
    # These actions return ir.actions for UI; views are expected in this addon.
    # -------------------------------------------------------------------------
    def action_view_consents_as_patient(self):
        """Open consents where this partner is the Patient."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consents (Patient)"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": [("patient_id", "=", self.id)] + self._company_domain(),
            "context": {"search_default_group_by_state": 1, "default_patient_id": self.id},
        }

    def action_view_consents_as_guardian(self):
        """Open consents where this partner is the Guardian/Representative."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consents (Guardian/Representative)"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": [("guardian_partner_id", "=", self.id)] + self._company_domain(),
            "context": {"search_default_group_by_state": 1, "default_guardian_partner_id": self.id},
        }

    def action_view_all_related_consents(self):
        """Open both patient and guardian consents for this partner."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("All Related Consents"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": ["|",
                       ("patient_id", "=", self.id),
                       ("guardian_partner_id", "=", self.id)] + self._company_domain(),
            "context": {"search_default_group_by_state": 1, "default_patient_id": self.id},
        }

    def action_view_pending_consents(self):
        """Open pending consents (Waiting for Signature) for this partner."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pending Consents"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": [("patient_id", "=", self.id), ("state", "=", "to_sign")] + self._company_domain(),
            "context": {"default_patient_id": self.id},
        }

    def action_view_signed_consents(self):
        """Open signed consents for this partner."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Signed Consents"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": [("patient_id", "=", self.id), ("state", "=", "signed")] + self._company_domain(),
            "context": {"default_patient_id": self.id},
        }

    def action_open_portal_consents(self):
        """Open patient consents in the portal (new tab)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.consent_portal_url,
            "target": "new",
        }

    def action_request_new_consent(self):
        """
        Open the Consent Template list (Published) to create a new Consent for this partner.
        The template form will use context to prefill patient and allow 'Create Consent' flow.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent Templates"),
            "res_model": "clinic.consent.template",
            "view_mode": "list,form",
            "domain": [
                ("legal_governed", "=", True),
                ("state", "=", "published"),
            ] + self._company_domain(),
            "context": {
                "default_legal_governed": True,
                "default_scope": "treatment_general",
                "default_applicability": "generic",
                "clinic_consent_create_context": {
                    "patient_id": self.id,
                    # Optionally prefill treatment/doctor if you open from those records
                },
            },
            "target": "current",
        }

    def action_send_consent_reminders(self, days=3):
        """
        Bulk-send reminders for pending consents for selected partners.
        Schedules activities on each pending consent.
        """
        Consent = self.env["clinic.consent.form"].sudo()
        total = 0
        for partner in self:
            domain = [
                ("patient_id", "=", partner.id),
                ("state", "=", "to_sign"),
            ] + partner._company_domain()
            pending = Consent.search(domain)
            for c in pending:
                c.action_send_reminder(days=days)
                total += 1
        if not total:
            return False
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reminders Scheduled"),
                "message": _("%s reminder(s) have been scheduled for pending consents.") % total,
                "sticky": False,
            },
        }

    # -------------------------------------------------------------------------
    # QUICK HELPERS FOR OTHER MODULES
    # -------------------------------------------------------------------------
    def has_pending_consent(self):
        """Return True if the partner has at least one 'to_sign' consent."""
        self.ensure_one()
        Consent = self.env["clinic.consent.form"].sudo()
        return bool(Consent.search_count(
            [("patient_id", "=", self.id), ("state", "=", "to_sign")] + self._company_domain()
        ))

    def get_latest_signed_consent(self):
        """Return the latest signed consent record for this partner (or False)."""
        self.ensure_one()
        Consent = self.env["clinic.consent.form"].sudo()
        return Consent.search(
            [("patient_id", "=", self.id), ("state", "=", "signed")] + self._company_domain(),
            order="signature_datetime desc, write_date desc, id desc",
            limit=1,
        )

    # -------------------------------------------------------------------------
    # ONCHANGE (optional quality-of-life)
    # -------------------------------------------------------------------------
    @api.onchange("consent_portal_opt_out")
    def _onchange_consent_portal_opt_out(self):
        """
        Optional UX behavior: show a friendly message if user opts out of portal.
        Controllers and business logic should honor this preference where applicable.
        """
        if self.consent_portal_opt_out:
            return {
                "warning": {
                    "title": _("Portal Opt-out Enabled"),
                    "message": _(
                        "This contact opts out of portal-based consent signing. "
                        "Consider in-clinic signing flows instead."
                    ),
                }
            }
        return {}
