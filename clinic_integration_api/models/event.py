# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicApiEvent(models.Model):
    _name = "clinic.api.event"
    _description = "Clinic Integration Event"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one("clinic.branch", domain="[('company_id', '=', company_id)]", index=True)
    event_type_id = fields.Many2one("clinic.api.event.type", required=True, ondelete="restrict", index=True)
    model_name = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    state = fields.Selection([("draft", "Draft"), ("queued", "Queued"), ("processing", "Processing"), ("done", "Done"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="draft", required=True, tracking=True, index=True)
    payload_json = fields.Text(required=True, groups="clinic_integration_api.group_api_manager")
    available_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    attempt_count = fields.Integer(readonly=True)
    error_message = fields.Char(readonly=True, groups="clinic_integration_api.group_api_manager")
    delivery_count = fields.Integer(compute="_compute_delivery_count")
    delivery_ids = fields.One2many("clinic.api.webhook.delivery", "event_id", string="Deliveries")

    @api.depends("delivery_ids")
    def _compute_delivery_count(self):
        for rec in self: rec.delivery_count = len(rec.delivery_ids)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = seq.next_by_code("clinic.api.event") or "EVT"
        return super().create(vals_list)

    def _require_manager(self):
        if not self.env.user.has_group("clinic_integration_api.group_api_manager"):
            raise AccessError(_("Clinic Integration API Manager access is required."))

    def action_queue(self):
        """Materialize eligible outbound deliveries and place the event in the queue."""
        self._require_manager()
        for rec in self:
            if rec.state not in ("draft", "failed"):
                raise UserError(_("Only Draft or Failed events can be queued."))
            rec._create_deliveries()
            rec.state = "queued"
        return True

    def _create_deliveries(self):
        Delivery = self.env["clinic.api.webhook.delivery"].sudo()
        Subscription = self.env["clinic.api.webhook.subscription"].sudo()
        for rec in self:
            domain = [("state", "=", "active"), ("company_id", "=", rec.company_id.id), ("event_type_ids", "in", rec.event_type_id.id)]
            subscriptions = Subscription.search(domain)
            if rec.branch_id:
                subscriptions = subscriptions.filtered(lambda s: not s.branch_id or s.branch_id == rec.branch_id)
            else:
                subscriptions = subscriptions.filtered(lambda s: not s.branch_id)
            for sub in subscriptions:
                exists = Delivery.search_count([("event_id", "=", rec.id), ("subscription_id", "=", sub.id)])
                if not exists:
                    Delivery.create({"event_id": rec.id, "subscription_id": sub.id})
        return True

    def action_cancel(self):
        self._require_manager(); self.filtered(lambda r: r.state not in ("done", "cancelled")).write({"state": "cancelled"}); return True

    def action_retry(self):
        self._require_manager()
        for rec in self:
            if rec.state not in ("failed", "done"):
                raise UserError(_("Retry is only available for Failed or Done events."))
            rec.delivery_ids.filtered(lambda d: d.state in ("failed", "dead")).action_retry()
            rec.state = "queued"
        return True

    def action_view_deliveries(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Webhook Deliveries"), "res_model": "clinic.api.webhook.delivery", "view_mode": "list,form", "domain": [("event_id", "=", self.id)]}
