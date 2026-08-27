# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicAuditPolicy(models.Model):
    _name = "clinic.audit.policy"
    _description = "Clinic Audit Policy"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, company_id, branch_id, model_name, name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("suspended", "Suspended"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=False,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
        help="Primary company for new policies. Empty preserves legacy global/multi-company policies.",
    )
    # Legacy many-company contract retained for upgrade compatibility.
    company_ids = fields.Many2many(
        "res.company",
        "clinic_audit_policy_company_rel",
        "policy_id",
        "company_id",
        string="Legacy Companies",
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        check_company=True,
        index=True,
        tracking=True,
    )
    model_id = fields.Many2one(
        "ir.model",
        required=False,
        ondelete="set null",
        index=True,
        tracking=True,
        domain="[('transient', '=', False)]",
        help="Legacy-compatible nullable target; new policies must select a model before activation.",
    )
    model_name = fields.Char(
        related="model_id.model",
        store=True,
        index=True,
        readonly=True,
    )
    model = fields.Char(
        related="model_id.model",
        store=True,
        readonly=True,
        string="Legacy Model",
    )

    audit_create = fields.Boolean(default=True, tracking=True)
    audit_write = fields.Boolean(default=True, tracking=True)
    audit_unlink = fields.Boolean(default=True, tracking=True)
    capture_mode = fields.Selection(
        [
            ("metadata", "Metadata Only"),
            ("changed", "Changed Fields"),
        ],
        default="changed",
        required=True,
        tracking=True,
    )
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
        required=True,
        tracking=True,
    )
    auto_review_unlink = fields.Boolean(
        string="Open Review on Delete",
        default=True,
        tracking=True,
    )

    include_field_ids = fields.Many2many(
        "ir.model.fields",
        "clinic_aud_pol_inc_rel",
        "policy_id",
        "field_id",
        string="Included Fields",
    )
    exclude_field_ids = fields.Many2many(
        "ir.model.fields",
        "clinic_aud_pol_exc_rel",
        "policy_id",
        "field_id",
        string="Excluded Fields",
    )
    mask_field_ids = fields.Many2many(
        "ir.model.fields",
        "clinic_aud_pol_mask_rel",
        "policy_id",
        "field_id",
        string="Always Mask",
    )

    # Legacy governance fields retained from the unfinished historical addon.
    trigger = fields.Selection(
        [
            ("create", "Create"),
            ("write", "Write"),
            ("unlink", "Unlink"),
            ("state", "State Change"),
            ("access", "Access"),
            ("export", "Export"),
        ],
        string="Legacy Trigger",
    )
    domain = fields.Text()
    reason_required = fields.Boolean(default=False)
    approval_required = fields.Boolean(default=False)
    approver_ids = fields.Many2many(
        "res.users",
        "clinic_audit_policy_user_rel",
        "policy_id",
        "user_id",
    )
    notify_group_ids = fields.Many2many(
        "res.groups",
        "clinic_audit_policy_groups_rel",
        "policy_id",
        "group_id",
    )
    activity_type_id = fields.Many2one("mail.activity.type")
    forbidden_field_ids = fields.Many2many(
        "ir.model.fields",
        "clinic_audit_policy_forbid_field_rel",
        "policy_id",
        "field_id",
    )
    forbidden_fields = fields.Char()
    masked_field_ids = fields.Many2many(
        "ir.model.fields",
        "clinic_audit_policy_mask_field_rel",
        "policy_id",
        "field_id",
    )
    severity_override = fields.Boolean(default=False)
    severity_value = fields.Selection(
        [(x, x.title()) for x in ("low", "medium", "high", "critical")]
    )
    retention_override = fields.Boolean(default=False)
    retention_days = fields.Integer(default=365)
    mail_template_id = fields.Many2one("mail.template")
    notes = fields.Text()

    _name_company_model_unique = models.Constraint(
        "UNIQUE(name, company_id, model_id)",
        "Policy names must be unique for the same company and model.",
    )

    @api.constrains("branch_id", "company_id")
    def _check_branch_company(self):
        for rec in self:
            if rec.branch_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(
                    _("Policy branch must belong to the selected company.")
                )

    @api.constrains(
        "include_field_ids",
        "exclude_field_ids",
        "mask_field_ids",
        "model_id",
    )
    def _check_field_models(self):
        for rec in self:
            selected = (
                rec.include_field_ids
                | rec.exclude_field_ids
                | rec.mask_field_ids
            )
            if selected.filtered(lambda field: field.model_id != rec.model_id):
                raise ValidationError(
                    _("All policy fields must belong to the policy model.")
                )

    def action_activate(self):
        for rec in self:
            if not rec.model_id:
                raise ValidationError(_("Select a target model before activating an audit policy."))
        self.write({"state": "active", "active": True})
        return True

    def action_suspend(self):
        self.write({"state": "suspended"})
        return True

    def action_reset_draft(self):
        self.write({"state": "draft"})
        return True

    def action_open_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Audit Events"),
            "res_model": "clinic.audit.event",
            "view_mode": "list,form",
            "domain": [("policy_id", "=", self.id)],
        }
