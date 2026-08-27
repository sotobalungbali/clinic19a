# -*- coding: utf-8 -*-
from urllib.parse import urlsplit
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicApiWebhookSubscription(models.Model):
    _name = "clinic.api.webhook.subscription"
    _description = "Clinic Webhook Subscription"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "company_id, provider_id, name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    state = fields.Selection([("draft", "Draft"), ("active", "Active"), ("suspended", "Suspended")], default="draft", required=True, tracking=True, index=True)
    active = fields.Boolean(default=True)
    provider_id = fields.Many2one("clinic.api.provider", required=True, ondelete="cascade", index=True, check_company=True)
    company_id = fields.Many2one(related="provider_id.company_id", store=True, index=True)
    branch_id = fields.Many2one(related="provider_id.branch_id", store=True, index=True)
    event_type_ids = fields.Many2many("clinic.api.event.type", "api_sub_event_type_rel", "subscription_id", "event_type_id", required=True)
    endpoint_path = fields.Char(required=True, default="/webhooks/clinicone")
    signing_enabled = fields.Boolean(default=True)
    max_attempts = fields.Integer(default=5)
    backoff_seconds = fields.Integer(default=60)
    delivery_count = fields.Integer(compute="_compute_delivery_count")
    delivery_ids = fields.One2many("clinic.api.webhook.delivery", "subscription_id", string="Delivery History")
    notes = fields.Text()

    _attempts_positive = models.Constraint("CHECK(max_attempts BETWEEN 1 AND 20)", "Max attempts must be between 1 and 20.")
    _backoff_positive = models.Constraint("CHECK(backoff_seconds BETWEEN 10 AND 86400)", "Backoff must be between 10 seconds and one day.")

    @api.depends("delivery_ids")
    def _compute_delivery_count(self):
        for rec in self: rec.delivery_count = len(rec.delivery_ids)

    @api.constrains("endpoint_path")
    def _check_endpoint_path(self):
        for rec in self:
            path = (rec.endpoint_path or "").strip()
            parsed = urlsplit(path)
            if not path.startswith("/") or parsed.scheme or parsed.netloc or path.startswith("//"):
                raise ValidationError(_("Webhook endpoint must be a relative path on the configured provider host."))

    def _require_manager(self):
        if not self.env.user.has_group("clinic_integration_api.group_api_manager"):
            raise AccessError(_("Clinic Integration API Manager access is required."))

    def action_activate(self):
        self._require_manager()
        for rec in self:
            if rec.provider_id.state != "active":
                raise ValidationError(_("Activate the provider before activating its webhook subscription."))
            if not rec.event_type_ids:
                raise ValidationError(_("Select at least one event type."))
            rec.state = "active"
        return True

    def action_suspend(self):
        self._require_manager(); self.write({"state": "suspended"}); return True

    def action_reset_to_draft(self):
        self._require_manager(); self.write({"state": "draft"}); return True

    def action_view_deliveries(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Delivery History"), "res_model": "clinic.api.webhook.delivery", "view_mode": "list,form", "domain": [("subscription_id", "=", self.id)]}
