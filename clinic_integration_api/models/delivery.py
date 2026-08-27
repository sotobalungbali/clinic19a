# -*- coding: utf-8 -*-
from datetime import timedelta
import hashlib
import hmac
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicApiWebhookDelivery(models.Model):
    _name = "clinic.api.webhook.delivery"
    _description = "Clinic Webhook Delivery"
    _order = "next_attempt_at, id"
    _check_company_auto = True

    _event_subscription_unique = models.Constraint("UNIQUE(event_id, subscription_id)", "Only one delivery may exist per event and subscription.")

    event_id = fields.Many2one("clinic.api.event", required=True, ondelete="cascade", index=True, check_company=True)
    subscription_id = fields.Many2one("clinic.api.webhook.subscription", required=True, ondelete="cascade", index=True, check_company=True)
    provider_id = fields.Many2one(related="subscription_id.provider_id", store=True, index=True)
    company_id = fields.Many2one(related="subscription_id.company_id", store=True, index=True)
    branch_id = fields.Many2one(related="subscription_id.branch_id", store=True, index=True)
    state = fields.Selection([("pending", "Pending"), ("processing", "Processing"), ("delivered", "Delivered"), ("failed", "Failed"), ("dead", "Dead Letter")], default="pending", required=True, index=True)
    attempt_count = fields.Integer(default=0, readonly=True)
    next_attempt_at = fields.Datetime(default=fields.Datetime.now, index=True)
    delivered_at = fields.Datetime(readonly=True)
    status_code = fields.Integer(readonly=True)
    provider_reference = fields.Char(readonly=True)
    response_excerpt = fields.Text(readonly=True, groups="clinic_integration_api.group_api_manager")
    error_message = fields.Char(readonly=True, groups="clinic_integration_api.group_api_manager")


    @api.constrains("event_id", "subscription_id")
    def _check_delivery_scope(self):
        """Reject manually created evidence that crosses company/branch scope."""
        for rec in self:
            if rec.event_id.company_id != rec.subscription_id.company_id:
                raise UserError(_("Event and webhook subscription must belong to the same company."))
            event_branch = rec.event_id.branch_id
            subscription_branch = rec.subscription_id.branch_id
            if subscription_branch and event_branch != subscription_branch:
                raise UserError(_("Branch-specific subscription does not match the event branch."))

    def _require_manager(self):
        if not self.env.user.has_group("clinic_integration_api.group_api_manager"):
            raise AccessError(_("Clinic Integration API Manager access is required."))

    def _payload(self):
        self.ensure_one()
        event = self.event_id
        payload = json.loads(event.sudo().payload_json or "{}")
        return {"event_id": event.name, "event_type": event.event_type_id.code, "model": event.model_name, "record_id": event.res_id, "occurred_at": fields.Datetime.to_string(event.create_date), "data": payload}

    def _attempt_delivery(self):
        self.ensure_one()
        if self.state not in ("pending", "failed"):
            return False
        event = self.event_id
        sub = self.subscription_id
        provider = self.provider_id
        if event.state == "cancelled" or sub.state != "active" or provider.state != "active":
            return False
        payload = self._payload()
        self.write({"state": "processing", "attempt_count": self.attempt_count + 1})
        try:
            # HMAC signing is additive. Provider authentication remains independent.
            if sub.signing_enabled:
                secret = provider._get_outbound_secret()
                canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
                payload["signature"] = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest() if secret else ""
            status, response = provider._post_json(sub.endpoint_path, payload)
            self.write({"state": "delivered", "status_code": status, "delivered_at": fields.Datetime.now(), "response_excerpt": json.dumps(response, default=str)[:4000], "error_message": False, "provider_reference": str(response.get("id") or response.get("reference") or "") if isinstance(response, dict) else False})
            if all(delivery.state == "delivered" for delivery in event.delivery_ids):
                event.sudo().write({"state": "done", "error_message": False})
            return True
        except Exception as exc:
            max_attempts = sub.max_attempts
            is_dead = self.attempt_count >= max_attempts
            delay = sub.backoff_seconds * (2 ** max(0, self.attempt_count - 1))
            self.write({"state": "dead" if is_dead else "failed", "error_message": str(exc)[:500], "next_attempt_at": fields.Datetime.now() + timedelta(seconds=min(delay, 86400))})
            event.sudo().write({"state": "failed", "error_message": str(exc)[:500]})
            return False

    def action_retry(self):
        """Start a fresh bounded retry cycle for failed/dead-letter evidence."""
        self._require_manager()
        for rec in self:
            if rec.state not in ("failed", "dead"):
                raise UserError(_("Only Failed or Dead Letter deliveries can be retried."))
            rec.write({"state": "pending", "attempt_count": 0, "next_attempt_at": fields.Datetime.now(), "error_message": False})
            rec.event_id.sudo().write({"state": "queued", "error_message": False})
        return True

    def action_open_event(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Integration Event"), "res_model": "clinic.api.event", "res_id": self.event_id.id, "view_mode": "form"}

    @api.model
    def _cron_dispatch(self, limit=100):
        domain = [("state", "in", ("pending", "failed")), ("next_attempt_at", "<=", fields.Datetime.now())]
        records = self.sudo().search(domain, order="next_attempt_at, id", limit=limit)
        self.env["ir.cron"]._commit_progress(remaining=len(records))
        processed = 0
        for rec in records:
            locked = rec.try_lock_for_update().filtered_domain(domain)
            if not locked:
                continue
            locked._attempt_delivery(); processed += 1
            if not self.env["ir.cron"]._commit_progress(1):
                break
        return processed
