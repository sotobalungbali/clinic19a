from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError



class ClinicMarketingCampaign(models.Model):
    """ClinicOne campaign orchestration over patient segments and native email."""

    _name = "clinic.marketing.campaign"
    _description = "Clinic Marketing Campaign"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_at desc, id desc"
    _check_company_auto = True

    _code_company_unique = models.Constraint(
        "UNIQUE(company_id, code)",
        "Marketing Campaign code must be unique per company.",
    )
    _company_state_idx = models.Index(
        "(company_id, state, branch_id, planned_at)"
    )

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(
        default="/",
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        domain="[('company_id', '=', company_id)]",
        index=True,
        tracking=True,
    )
    owner_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        domain="[('share', '=', False)]",
        tracking=True,
    )
    segment_id = fields.Many2one(
        "clinic.marketing.segment",
        required=True,
        ondelete="restrict",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
        tracking=True,
    )
    promotion_id = fields.Many2one(
        "clinic.marketing.promotion",
        ondelete="restrict",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
        tracking=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("planning", "Audience Prepared"),
            ("ready", "Ready"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
        index=True,
    )
    planned_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        index=True,
    )
    launched_at = fields.Datetime(readonly=True, index=True)
    completed_at = fields.Datetime(readonly=True, index=True)
    objective = fields.Text()

    send_email = fields.Boolean(default=True, tracking=True)
    send_whatsapp = fields.Boolean(default=False, tracking=True)

    email_subject = fields.Char()
    email_preview = fields.Char()
    email_body_html = fields.Html(
        sanitize="email_outgoing",
        sanitize_output_method="html",
    )
    email_from = fields.Char()
    email_mailing_id = fields.Many2one(
        "mailing.mailing",
        string="Odoo Email Mailing",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    utm_campaign_id = fields.Many2one(
        "utm.campaign",
        string="UTM Campaign",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    whatsapp_body = fields.Text()
    whatsapp_transport = fields.Selection(
        related="company_id.clinic_marketing_whatsapp_transport",
        readonly=True,
    )

    recipient_ids = fields.One2many(
        "clinic.marketing.recipient",
        "campaign_id",
        string="Audience Snapshot",
        copy=False,
    )
    message_ids = fields.One2many(
        "clinic.marketing.message",
        "campaign_id",
        string="WhatsApp Messages",
        copy=False,
    )

    recipient_count = fields.Integer(
        compute="_compute_recipient_counts",
        store=True,
    )
    included_count = fields.Integer(
        compute="_compute_recipient_counts",
        store=True,
    )
    excluded_count = fields.Integer(
        compute="_compute_recipient_counts",
        store=True,
    )
    email_recipient_count = fields.Integer(
        compute="_compute_recipient_counts",
        store=True,
    )
    whatsapp_recipient_count = fields.Integer(
        compute="_compute_recipient_counts",
        store=True,
    )
    whatsapp_queued_count = fields.Integer(compute="_compute_message_counts")
    whatsapp_sent_count = fields.Integer(compute="_compute_message_counts")
    whatsapp_failed_count = fields.Integer(compute="_compute_message_counts")

    email_sent_count = fields.Integer(
        related="email_mailing_id.sent",
        readonly=True,
    )
    email_opened_ratio = fields.Float(
        related="email_mailing_id.opened_ratio",
        readonly=True,
    )
    email_clicked_ratio = fields.Float(
        related="email_mailing_id.clicks_ratio",
        readonly=True,
    )
    email_bounced_ratio = fields.Float(
        related="email_mailing_id.bounced_ratio",
        readonly=True,
    )
    email_replied_ratio = fields.Float(
        related="email_mailing_id.replied_ratio",
        readonly=True,
    )

    @api.depends(
        "recipient_ids",
        "recipient_ids.inclusion_state",
        "recipient_ids.email_allowed",
        "recipient_ids.whatsapp_allowed",
    )
    def _compute_recipient_counts(self):
        for record in self:
            recipients = record.recipient_ids
            record.recipient_count = len(recipients)
            record.included_count = len(
                recipients.filtered(lambda line: line.inclusion_state == "included")
            )
            record.excluded_count = len(
                recipients.filtered(lambda line: line.inclusion_state == "excluded")
            )
            record.email_recipient_count = len(
                recipients.filtered(
                    lambda line:
                    line.inclusion_state == "included" and line.email_allowed
                )
            )
            record.whatsapp_recipient_count = len(
                recipients.filtered(
                    lambda line:
                    line.inclusion_state == "included" and line.whatsapp_allowed
                )
            )

    def _compute_message_counts(self):
        for record in self:
            record.whatsapp_queued_count = len(
                record.message_ids.filtered(
                    lambda msg: msg.state in ("queued", "opened")
                )
            )
            record.whatsapp_sent_count = len(
                record.message_ids.filtered(lambda msg: msg.state == "sent")
            )
            record.whatsapp_failed_count = len(
                record.message_ids.filtered(lambda msg: msg.state == "failed")
            )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            company = self.env["res.company"].browse(
                vals.get("company_id")
            ) or self.env.company
            if vals.get("code") in (False, "/"):
                vals["code"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.marketing.campaign")
                    or "/"
                )
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if "state" in vals and not self.env.context.get("marketing_campaign_transition"):
            raise AccessError(_("Use Campaign workflow actions to change status."))

        protected = {
            "company_id",
            "branch_id",
            "segment_id",
            "promotion_id",
            "send_email",
            "send_whatsapp",
            "email_subject",
            "email_body_html",
            "whatsapp_body",
        }
        if (
            self.filtered(lambda campaign: campaign.state in ("ready", "running", "completed"))
            and protected.intersection(vals)
            and not self.env.context.get("marketing_campaign_transition")
        ):
            raise AccessError(
                _("Campaign scope/content is locked once the Campaign is Ready.")
            )
        return super().write(vals)

    @api.constrains(
        "company_id",
        "branch_id",
        "segment_id",
        "promotion_id",
        "send_email",
        "send_whatsapp",
    )
    def _check_campaign_scope(self):
        for campaign in self:
            if campaign.branch_id and campaign.branch_id.company_id != campaign.company_id:
                raise ValidationError(_("Campaign Branch must belong to its company."))
            if campaign.segment_id.company_id != campaign.company_id:
                raise ValidationError(_("Campaign Segment belongs to another company."))
            if campaign.promotion_id and campaign.promotion_id.company_id != campaign.company_id:
                raise ValidationError(_("Campaign Promotion belongs to another company."))
            if (
                campaign.branch_id
                and campaign.segment_id.branch_id
                and campaign.segment_id.branch_id != campaign.branch_id
            ):
                raise ValidationError(_("Campaign Branch conflicts with Segment Branch."))
            if (
                campaign.branch_id
                and campaign.promotion_id.branch_id
                and campaign.promotion_id.branch_id != campaign.branch_id
            ):
                raise ValidationError(_("Campaign Branch conflicts with Promotion Branch."))
            if not campaign.send_email and not campaign.send_whatsapp:
                raise ValidationError(_("Select at least one Campaign communication channel."))

    def _require_coordinator(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_marketing.group_marketing_coordinator"
        ):
            raise AccessError(_("Marketing Coordinator access is required."))
        return True

    def _require_manager(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_marketing.group_marketing_manager"
        ):
            raise AccessError(_("Marketing Manager access is required."))
        return True

    def _check_branch_policy(self):
        self.ensure_one()
        if (
            self.branch_id
            and "policy_branch_scope_marketing" in self.company_id._fields
            and not self.company_id.policy_branch_scope_marketing
        ):
            raise UserError(
                _(
                    "Branch-scoped Marketing is disabled by the Company Branch policy. "
                    "Remove the Branch or enable policy_branch_scope_marketing."
                )
            )
        return True

