from odoo import fields, models, _
from odoo.exceptions import UserError


class ClinicMarketingCampaignAudience(models.Model):
    """Patient audience building and readiness checks for Marketing Campaigns."""

    _inherit = "clinic.marketing.campaign"

    # Candidate selection remains separate from delivery so staff can inspect
    # and rebuild the audience before any message is queued.
    def _candidate_patients(self):
        self.ensure_one()
        patients = self.segment_id._candidate_patients()
        if self.branch_id:
            patients = patients.filtered(
                lambda patient: patient.partner_id.branch_id == self.branch_id
            )
        return patients

    def _recipient_snapshot_vals(self, patient):
        self.ensure_one()
        partner = patient.partner_id
        Preference = self.env["clinic.marketing.preference"]
        preference = Preference._find_for_partner(partner, self.company_id)
        require_explicit = self.company_id.clinic_marketing_require_explicit_consent

        email = partner.email or patient.email
        raw_mobile = patient.mobile or partner.phone or patient.phone
        mobile = self.env["clinic.marketing.message"]._normalize_destination(
            raw_mobile,
            self.company_id,
        )

        email_allowed = bool(self.send_email and email)
        whatsapp_allowed = bool(self.send_whatsapp and mobile)

        if preference:
            email_allowed = email_allowed and preference._channel_allowed(
                "email",
                require_explicit=require_explicit,
            )
            whatsapp_allowed = whatsapp_allowed and preference._channel_allowed(
                "whatsapp",
                require_explicit=require_explicit,
            )
        elif require_explicit:
            email_allowed = False
            whatsapp_allowed = False

        reasons = []
        if preference and preference.do_not_contact:
            reasons.append(_("Do Not Contact"))
        if self.send_email and not email:
            reasons.append(_("No email address"))
        elif self.send_email and not email_allowed:
            reasons.append(_("Email consent not available"))
        if self.send_whatsapp and not mobile:
            reasons.append(_("No usable WhatsApp number"))
        elif self.send_whatsapp and not whatsapp_allowed:
            reasons.append(_("WhatsApp consent not available"))

        included = email_allowed or whatsapp_allowed
        return {
            "patient_id": patient.id,
            "preference_id": preference.id if preference else False,
            "email": email or False,
            "mobile": mobile or False,
            "inclusion_state": "included" if included else "excluded",
            "exclusion_reason": "; ".join(reasons) if reasons and not included else False,
            "email_allowed": email_allowed,
            "whatsapp_allowed": whatsapp_allowed,
            "email_delivery_state": "pending" if email_allowed else "not_applicable",
        }

    def action_prepare_audience(self):
        self.ensure_one()
        self._require_coordinator()
        self._check_branch_policy()
        if self.state not in ("draft", "planning"):
            raise UserError(_("Audience can only be prepared before Campaign readiness."))
        if self.segment_id.state != "active":
            raise UserError(_("Activate the Marketing Segment before preparing an audience."))

        patients = self._candidate_patients()
        max_audience = self.company_id.clinic_marketing_max_audience or 50000
        if len(patients) > max_audience:
            raise UserError(
                _(
                    "Segment returned %(count)s patients, above the company "
                    "maximum of %(limit)s. Refine the Segment first."
                ) % {"count": len(patients), "limit": max_audience}
            )

        self.recipient_ids.with_context(marketing_audience_build=True).unlink()
        self.message_ids.with_context(marketing_message_build=True).unlink()

        commands = [
            (0, 0, self._recipient_snapshot_vals(patient))
            for patient in patients
        ]
        self.with_context(
            marketing_audience_build=True,
            marketing_campaign_transition=True,
        ).write({
            "recipient_ids": commands,
            "state": "planning",
        })
        return True

    def _validate_ready(self):
        self.ensure_one()
        self._check_branch_policy()
        if not self.included_count:
            raise UserError(_("Campaign has no eligible included recipients."))
        if self.send_email:
            if not self.email_subject or not self.email_body_html:
                raise UserError(_("Email Subject and Email Body are required."))
            if not self.email_recipient_count:
                raise UserError(_("No recipients are eligible for Email."))
        if self.send_whatsapp:
            if not self.whatsapp_body:
                raise UserError(_("WhatsApp Message is required."))
            if not self.whatsapp_recipient_count:
                raise UserError(_("No recipients are eligible for WhatsApp."))
        if self.promotion_id:
            today = fields.Date.context_today(self)
            if self.promotion_id.state != "active":
                raise UserError(_("Campaign Promotion must be Active."))
            if self.promotion_id.valid_to and self.promotion_id.valid_to < today:
                raise UserError(_("Campaign Promotion is expired."))
        return True

    def action_mark_ready(self):
        self.ensure_one()
        self._require_coordinator()
        if self.state != "planning":
            raise UserError(_("Prepare the audience before marking Campaign Ready."))
        self._validate_ready()
        self.with_context(marketing_campaign_transition=True).write({
            "state": "ready",
        })
        return True

