# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError


class ClinicMarketingMessageIntegration(models.Model):
    _inherit = "clinic.marketing.message"

    def _dispatch_via_gateway(self):
        """Fill the provider-neutral seam intentionally left by clinic_marketing."""
        self.ensure_one()
        branch = self.partner_id.branch_id if self.partner_id and "branch_id" in self.partner_id._fields else False
        provider = self.env["clinic.api.service"].find_provider("whatsapp", self.company_id, branch=branch)
        if not provider:
            return super()._dispatch_via_gateway()
        status, response = provider._post_json(provider.outbound_path, {
            "destination": self.destination,
            "message": self.body,
            "campaign_id": self.campaign_id.id,
            "message_id": self.id,
        })
        if status < 200 or status >= 300:
            raise UserError(_("WhatsApp provider did not accept the message."))
        if isinstance(response, dict):
            return response.get("id") or response.get("message_id") or response.get("reference") or f"HTTP-{status}"
        return f"HTTP-{status}"


class ClinicTelemedicineSessionIntegration(models.Model):
    _inherit = "clinic.telemedicine.session"

    def _provision_meeting_via_provider(self):
        """Fill the provider-neutral seam intentionally left by Telemedicine."""
        self.ensure_one()
        provider = self.env["clinic.api.service"].find_provider("telemedicine", self.company_id, branch=self.branch_id)
        if not provider:
            return super()._provision_meeting_via_provider()
        status, response = provider._post_json(provider.meeting_path, {
            "session_id": self.id,
            "reference": self.name,
            "patient_id": self.patient_id.id,
            "doctor_id": self.doctor_id.id,
            "scheduled_start": self.scheduled_start,
            "scheduled_end": self.scheduled_end,
        })
        if status < 200 or status >= 300 or not isinstance(response, dict):
            raise UserError(_("Telemedicine provider did not return a valid meeting response."))
        return {
            "meeting_url": response.get("meeting_url") or response.get("url"),
            "provider_reference": response.get("id") or response.get("reference"),
        }


class ClinicBillingGatewayTxIntegration(models.Model):
    _inherit = "clinic.billing.gateway.tx"

    @api.model
    def _match_tx_from_payload(self, provider, payload):
        """Provider-specific transaction locator required by clinic_billing.process_webhook()."""
        provider = (provider or "").lower().strip()
        payload = payload or {}
        obj = payload
        if provider == "stripe":
            obj = ((payload.get("data") or {}).get("object") or {})
        external_tx_id = (
            obj.get("transaction_id") or obj.get("id") or obj.get("payment_id")
            or obj.get("payment_request_id")
        )
        external_order_id = (
            obj.get("order_id") or obj.get("external_id") or obj.get("reference_id")
            or (obj.get("metadata") or {}).get("order_id")
        )
        domain = [("provider", "=", provider), ("company_id", "=", self.env.company.id)]
        if external_tx_id:
            tx = self.search(domain + [("external_tx_id", "=", str(external_tx_id))], limit=1)
            if tx: return tx
        if external_order_id:
            tx = self.search(domain + ["|", ("external_order_id", "=", str(external_order_id)), ("order_reference", "=", str(external_order_id))], limit=1)
            if tx: return tx
        reference = obj.get("external_reference") or obj.get("reference")
        if reference:
            return self.search(domain + [("external_reference", "=", str(reference))], limit=1)
        return self.browse()
