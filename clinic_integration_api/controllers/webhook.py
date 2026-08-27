# -*- coding: utf-8 -*-
import logging

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 1024 * 1024


class ClinicIntegrationWebhookController(http.Controller):
    """Provider callback endpoint authenticated independently from browser/API sessions."""

    @http.route("/api/clinic/v1/webhooks/<string:webhook_key>", type="http", auth="public", methods=["POST"], csrf=False, save_session=False)
    def inbound_webhook(self, webhook_key, **kwargs):
        provider = request.env["clinic.api.provider"].sudo().search([
            ("webhook_key", "=", webhook_key), ("state", "=", "active"), ("active", "=", True)
        ], limit=1)
        if not provider:
            return request.make_json_response({"ok": False, "error": {"code": "not_found", "message": "Webhook endpoint not found."}}, status=404)
        token = request.httprequest.headers.get("X-Clinic-Webhook-Token", "")
        if not provider.verify_inbound_token(token):
            return request.make_json_response({"ok": False, "error": {"code": "unauthorized", "message": "Invalid webhook token."}}, status=401)
        if (request.httprequest.content_length or 0) > MAX_BODY_BYTES:
            return request.make_json_response({"ok": False, "error": {"code": "payload_too_large", "message": "Webhook body exceeds 1 MiB."}}, status=413)
        payload = request.httprequest.get_json(silent=True)
        if not isinstance(payload, dict):
            return request.make_json_response({"ok": False, "error": {"code": "invalid_json", "message": "Webhook body must be a JSON object."}}, status=400)
        headers = {key: value for key, value in request.httprequest.headers.items() if key.lower() not in ("authorization", "cookie", "x-clinic-webhook-token")}
        try:
            if provider.provider_type == "billing":
                if provider.code not in ("midtrans", "xendit", "stripe"):
                    raise ValidationError(_("Billing provider code must be midtrans, xendit, or stripe."))
                Tx = request.env["clinic.billing.gateway.tx"].with_user(provider.service_user_id).with_company(provider.company_id)
                Tx.process_webhook(provider.code, payload, headers=headers)
            service = request.env["clinic.api.service"]
            event_type = request.env["clinic.api.event.type"].sudo().search([("code", "=", "provider.webhook.received")], limit=1)
            if event_type:
                event = request.env["clinic.api.event"].sudo().create({
                    "company_id": provider.company_id.id,
                    "branch_id": provider.branch_id.id or False,
                    "event_type_id": event_type.id,
                    "model_name": provider._name,
                    "res_id": provider.id,
                    "payload_json": __import__("json").dumps({"provider": provider.code, "payload": payload}, default=str, separators=(",", ":")),
                    "state": "done",
                })
            return request.make_json_response({"ok": True, "accepted": True}, status=202)
        except (AccessError, ValidationError, UserError) as exc:
            return request.make_json_response({"ok": False, "error": {"code": "webhook_rejected", "message": str(exc)}}, status=400)
        except Exception:
            _logger.exception("Unexpected ClinicOne provider webhook failure for provider %s", provider.id)
            return request.make_json_response({"ok": False, "error": {"code": "internal_error", "message": "Webhook processing failed."}}, status=500)
