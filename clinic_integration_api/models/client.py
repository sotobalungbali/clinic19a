# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicApiClient(models.Model):
    """Governance record that binds an Odoo service user to API policy.

    The bearer API token itself remains owned by Odoo. This model stores only
    authorization policy and operational telemetry, never a copy of the token.
    """

    _name = "clinic.api.client"
    _description = "Clinic API Client"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, id"
    _check_company_auto = True

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "API client code must be unique.",
    )
    _service_user_unique = models.Constraint(
        "UNIQUE(user_id)",
        "Each Odoo service user can be linked to only one API client.",
    )
    _rpm_positive = models.Constraint(
        "CHECK(requests_per_minute > 0)",
        "Requests per minute must be greater than zero.",
    )
    _ttl_positive = models.Constraint(
        "CHECK(idempotency_ttl_hours > 0)",
        "Idempotency TTL must be greater than zero.",
    )

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(default="New", readonly=True, copy=False, index=True, tracking=True)
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("suspended", "Suspended")],
        default="draft", required=True, tracking=True, index=True,
    )
    active = fields.Boolean(default=True)
    user_id = fields.Many2one(
        "res.users", required=True, ondelete="restrict", tracking=True,
        domain="[('share', '=', False)]",
        help="Odoo service user whose bearer API token authenticates requests.",
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        index=True, tracking=True,
    )
    allowed_company_ids = fields.Many2many(
        "res.company", "api_cli_company_rel", "client_id", "company_id",
        string="Allowed Companies",
        help="Additional narrowing. Odoo service-user company access still applies.",
    )
    branch_ids = fields.Many2many(
        "clinic.branch", "api_cli_branch_rel", "client_id", "branch_id",
        string="Allowed Branches",
        domain="[('company_id', 'in', allowed_company_ids)]",
    )
    scope_ids = fields.Many2many(
        "clinic.api.scope", "api_cli_scope_rel", "client_id", "scope_id",
        string="Scopes", required=True,
    )
    requests_per_minute = fields.Integer(default=120)
    idempotency_ttl_hours = fields.Integer(default=24)
    last_used_at = fields.Datetime(readonly=True)
    request_count = fields.Integer(compute="_compute_counts")
    idempotency_count = fields.Integer(compute="_compute_counts")
    request_log_ids = fields.One2many("clinic.api.request.log", "client_id", string="Recent Requests")
    idempotency_ids = fields.One2many("clinic.api.idempotency", "client_id", string="Idempotency Records")
    notes = fields.Text()

    @api.depends("request_log_ids", "idempotency_ids")
    def _compute_counts(self):
        RequestLog = self.env["clinic.api.request.log"].sudo()
        Idempotency = self.env["clinic.api.idempotency"].sudo()
        for rec in self:
            rec.request_count = RequestLog.search_count([("client_id", "=", rec.id)])
            rec.idempotency_count = Idempotency.search_count([("client_id", "=", rec.id)])

    @api.constrains("company_id", "allowed_company_ids", "branch_ids", "user_id")
    def _check_scope_consistency(self):
        for rec in self:
            companies = rec.allowed_company_ids or rec.company_id
            if rec.company_id not in companies:
                raise ValidationError(_("Primary company must be included in Allowed Companies."))
            invalid_branches = rec.branch_ids.filtered(lambda b: b.company_id not in companies)
            if invalid_branches:
                raise ValidationError(_("Every allowed branch must belong to an allowed company."))
            if rec.user_id and any(company not in rec.user_id.company_ids for company in companies):
                raise ValidationError(_("The service user must have access to every allowed company."))

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("allowed_company_ids"):
                vals["allowed_company_ids"] = [(6, 0, [vals["company_id"]])]
            if not vals.get("code") or vals.get("code") == "New":
                vals["code"] = sequence.next_by_code("clinic.api.client") or "API"
        return super().create(vals_list)

    def _require_manager(self):
        if not self.env.user.has_group("clinic_integration_api.group_api_manager"):
            raise AccessError(_("Clinic Integration API Manager access is required."))

    def action_activate(self):
        self._require_manager()
        for rec in self:
            if not rec.scope_ids:
                raise ValidationError(_("Configure at least one API scope before activation."))
            if not rec.user_id.active or rec.user_id.share:
                raise ValidationError(_("The service user must be an active internal Odoo user."))
            rec.state = "active"
        return True

    def action_suspend(self):
        self._require_manager()
        self.write({"state": "suspended"})
        return True

    def action_reset_to_draft(self):
        self._require_manager()
        self.write({"state": "draft"})
        return True

    def action_view_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("API Requests"),
            "res_model": "clinic.api.request.log", "view_mode": "list,form",
            "domain": [("client_id", "=", self.id)],
            "context": {"default_client_id": self.id},
        }

    def action_view_idempotency(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Idempotency Records"),
            "res_model": "clinic.api.idempotency", "view_mode": "list,form",
            "domain": [("client_id", "=", self.id)],
            "context": {"default_client_id": self.id},
        }
