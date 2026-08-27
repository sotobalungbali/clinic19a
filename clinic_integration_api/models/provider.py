# -*- coding: utf-8 -*-
import hashlib
import ipaddress
import json
import secrets
import socket
import ssl
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urljoin, urlsplit

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class _NoRedirect(urlrequest.HTTPRedirectHandler):
    """Refuse redirects so an approved hostname cannot redirect to an internal host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ClinicApiProvider(models.Model):
    _name = "clinic.api.provider"
    _description = "Clinic Integration Provider"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "company_id, provider_type, sequence, name"
    _check_company_auto = True

    _company_code_unique = models.Constraint(
        "UNIQUE(company_id, code)",
        "Provider code must be unique per company.",
    )
    _timeout_range = models.Constraint(
        "CHECK(timeout_seconds BETWEEN 1 AND 60)",
        "Provider timeout must be between 1 and 60 seconds.",
    )

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True, tracking=True)
    sequence = fields.Integer(default=10)
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("suspended", "Suspended")],
        default="draft", required=True, tracking=True, index=True,
    )
    active = fields.Boolean(default=True)
    provider_type = fields.Selection(
        [("whatsapp", "WhatsApp Gateway"), ("telemedicine", "Telemedicine"),
         ("billing", "Billing Gateway"), ("generic", "Generic Webhook")],
        required=True, tracking=True, index=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        index=True, tracking=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch", domain="[('company_id', '=', company_id)]", index=True,
        help="Optional branch-specific provider. Empty means company-wide fallback.",
    )
    service_user_id = fields.Many2one(
        "res.users", required=True, ondelete="restrict", domain="[('share', '=', False)]",
        default=lambda self: self.env.user,
        help="Business operations triggered by inbound webhooks run with this user's ACLs and record rules.",
    )
    base_url = fields.Char(required=True)
    outbound_path = fields.Char(default="/messages")
    meeting_path = fields.Char(default="/meetings")
    auth_mode = fields.Selection(
        [("none", "No Authentication"), ("bearer", "Bearer Token"), ("header", "Custom Header")],
        default="bearer", required=True,
    )
    auth_header = fields.Char(default="X-API-Key")
    timeout_seconds = fields.Integer(default=15)
    allow_private_network = fields.Boolean(
        groups="clinic_integration_api.group_api_manager",
        help="Permit private/reserved network destinations. Keep disabled for internet providers.",
    )
    credential_configured = fields.Boolean(compute="_compute_credential_configured")
    webhook_key = fields.Char(default=lambda self: secrets.token_urlsafe(24), copy=False, readonly=True, index=True)
    inbound_token_digest = fields.Char(copy=False, readonly=True, groups="clinic_integration_api.group_api_manager")
    inbound_token_configured = fields.Boolean(compute="_compute_inbound_token_configured")
    last_test_at = fields.Datetime(readonly=True)
    last_test_status = fields.Char(readonly=True)
    subscription_count = fields.Integer(compute="_compute_counts")
    delivery_count = fields.Integer(compute="_compute_counts")
    subscription_ids = fields.One2many("clinic.api.webhook.subscription", "provider_id", string="Subscriptions")
    notes = fields.Text()

    @api.depends("auth_mode")
    def _compute_credential_configured(self):
        Params = self.env["ir.config_parameter"].sudo()
        for rec in self:
            rec.credential_configured = rec.auth_mode == "none" or bool(Params.get_param(rec._secret_param_key()))

    @api.depends("inbound_token_digest")
    def _compute_inbound_token_configured(self):
        for rec in self:
            rec.inbound_token_configured = bool(rec.inbound_token_digest)

    @api.depends("subscription_ids")
    def _compute_counts(self):
        Delivery = self.env["clinic.api.webhook.delivery"].sudo()
        for rec in self:
            rec.subscription_count = len(rec.subscription_ids)
            rec.delivery_count = Delivery.search_count([("provider_id", "=", rec.id)])

    @api.constrains("branch_id", "company_id", "service_user_id")
    def _check_company_scope(self):
        for rec in self:
            if rec.branch_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(_("Provider branch must belong to provider company."))
            if rec.service_user_id and rec.company_id not in rec.service_user_id.company_ids:
                raise ValidationError(_("Webhook service user must have access to provider company."))

    @api.constrains("base_url", "allow_private_network")
    def _check_base_url(self):
        for rec in self:
            rec._validate_destination(rec.base_url)

    def _require_manager(self):
        if not self.env.user.has_group("clinic_integration_api.group_api_manager"):
            raise AccessError(_("Clinic Integration API Manager access is required."))

    def _secret_param_key(self):
        self.ensure_one()
        return f"clinic_integration_api.provider.{self.id}.secret"

    def _get_outbound_secret(self):
        self.ensure_one()
        return self.env["ir.config_parameter"].sudo().get_param(self._secret_param_key()) or ""

    def set_outbound_secret(self, secret):
        self.ensure_one()
        self._require_manager()
        secret = (secret or "").strip()
        if self.auth_mode != "none" and not secret:
            raise ValidationError(_("Credential value is required for the selected authentication mode."))
        self.env["ir.config_parameter"].sudo().set_param(self._secret_param_key(), secret)
        return True

    def rotate_inbound_token(self):
        self.ensure_one()
        self._require_manager()
        token = secrets.token_urlsafe(40)
        self.inbound_token_digest = hashlib.sha256(token.encode()).hexdigest()
        return token

    def verify_inbound_token(self, token):
        self.ensure_one()
        if not token or not self.inbound_token_digest:
            return False
        digest = hashlib.sha256(token.encode()).hexdigest()
        return secrets.compare_digest(digest, self.inbound_token_digest)

    def _validate_destination(self, url):
        self.ensure_one()
        parsed = urlsplit((url or "").strip())
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValidationError(_("Provider endpoint must use an absolute HTTPS URL."))
        if parsed.username or parsed.password:
            raise ValidationError(_("Credentials must not be embedded in provider URLs."))
        if self.allow_private_network:
            return True
        try:
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
        except OSError as exc:
            raise ValidationError(_("Provider hostname cannot be resolved: %s") % exc) from exc
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved, ip.is_unspecified)):
                raise ValidationError(_("Private, local, or reserved provider destinations are blocked by default."))
        return True

    def _full_url(self, path=""):
        self.ensure_one()
        base = self.base_url.rstrip("/") + "/"
        path = (path or "").lstrip("/")
        url = urljoin(base, path)
        if urlsplit(url).hostname != urlsplit(base).hostname:
            raise ValidationError(_("Provider path must stay on the configured provider host."))
        self._validate_destination(url)
        return url

    def _post_json(self, path, payload):
        """Bounded outbound JSON transport owned by the integration layer."""
        self.ensure_one()
        if self.state != "active":
            raise UserError(_("Provider must be Active before outbound delivery."))
        url = self._full_url(path)
        body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
        if len(body) > 1024 * 1024:
            raise ValidationError(_("Outbound payload exceeds the 1 MiB provider limit."))
        headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "ClinicOne/19 Integration API"}
        secret = self._get_outbound_secret()
        if self.auth_mode == "bearer":
            if not secret:
                raise UserError(_("Provider bearer credential is not configured."))
            headers["Authorization"] = f"Bearer {secret}"
        elif self.auth_mode == "header":
            if not secret:
                raise UserError(_("Provider header credential is not configured."))
            headers[self.auth_header or "X-API-Key"] = secret
        opener = urlrequest.build_opener(_NoRedirect(), urlrequest.HTTPSHandler(context=ssl.create_default_context()))
        req = urlrequest.Request(url, data=body, headers=headers, method="POST")
        try:
            with opener.open(req, timeout=self.timeout_seconds) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise UserError(_("Provider response exceeds the 64 KiB safety limit."))
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
                return response.status, parsed
        except urlerror.HTTPError as exc:
            raw = exc.read(4096).decode("utf-8", errors="replace")
            raise UserError(_("Provider returned HTTP %(status)s: %(body)s", status=exc.code, body=raw[:1000])) from exc
        except (urlerror.URLError, TimeoutError, OSError) as exc:
            raise UserError(_("Provider connection failed: %s") % exc) from exc

    def action_validate_endpoint(self):
        """Validate HTTPS/DNS destination policy without sending business data."""
        self._require_manager()
        for rec in self:
            rec._validate_destination(rec.base_url)
            rec.write({"last_test_at": fields.Datetime.now(), "last_test_status": _("Endpoint validation passed")})
        return True

    def action_open_credential_wizard(self):
        self.ensure_one()
        self._require_manager()
        return {
            "type": "ir.actions.act_window", "name": _("Set Provider Credential"),
            "res_model": "clinic.api.provider.credential.wizard", "view_mode": "form",
            "target": "new", "context": {"default_provider_id": self.id},
        }

    def action_rotate_inbound_token(self):
        self.ensure_one()
        token = self.rotate_inbound_token()
        wizard = self.env["clinic.api.webhook.token.wizard"].create({"provider_id": self.id, "token": token})
        return {
            "type": "ir.actions.act_window", "name": _("New Inbound Webhook Token"),
            "res_model": wizard._name, "res_id": wizard.id, "view_mode": "form", "target": "new",
        }

    def action_activate(self):
        self._require_manager()
        for rec in self:
            rec._validate_destination(rec.base_url)
            if rec.auth_mode != "none" and not rec._get_outbound_secret():
                raise ValidationError(_("Configure provider credential before activation."))
            rec.state = "active"
        return True

    def action_suspend(self):
        self._require_manager(); self.write({"state": "suspended"}); return True

    def action_reset_to_draft(self):
        self._require_manager(); self.write({"state": "draft"}); return True

    def action_view_subscriptions(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Webhook Subscriptions"), "res_model": "clinic.api.webhook.subscription", "view_mode": "list,form", "domain": [("provider_id", "=", self.id)], "context": {"default_provider_id": self.id}}

    def action_view_deliveries(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Webhook Deliveries"), "res_model": "clinic.api.webhook.delivery", "view_mode": "list,form", "domain": [("provider_id", "=", self.id)]}

    def unlink(self):
        self._require_manager()
        Params = self.env["ir.config_parameter"].sudo()
        keys = [rec._secret_param_key() for rec in self]
        result = super().unlink()
        for key in keys:
            Params.set_param(key, "")
        return result
