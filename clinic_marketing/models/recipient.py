from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicMarketingRecipient(models.Model):
    """Immutable-per-launch audience evidence for one Campaign and Patient."""

    _name = "clinic.marketing.recipient"
    _description = "Clinic Marketing Campaign Recipient"
    _order = "campaign_id, inclusion_state, partner_id, id"
    _check_company_auto = True

    _campaign_patient_unique = models.Constraint(
        "UNIQUE(campaign_id, patient_id)",
        "A Patient can appear only once in a Marketing Campaign audience snapshot.",
    )
    _campaign_status_idx = models.Index(
        "(campaign_id, inclusion_state, email_allowed, whatsapp_allowed)"
    )

    campaign_id = fields.Many2one(
        "clinic.marketing.campaign",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="campaign_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    branch_id = fields.Many2one(
        related="campaign_id.branch_id",
        store=True,
        readonly=True,
        index=True,
    )
    segment_id = fields.Many2one(
        related="campaign_id.segment_id",
        store=True,
        readonly=True,
        index=True,
    )
    promotion_id = fields.Many2one(
        related="campaign_id.promotion_id",
        store=True,
        readonly=True,
        index=True,
    )

    patient_id = fields.Many2one(
        "clinic.patient",
        required=True,
        ondelete="restrict",
        index=True,
    )
    partner_id = fields.Many2one(
        related="patient_id.partner_id",
        store=True,
        readonly=True,
        index=True,
    )
    preference_id = fields.Many2one(
        "clinic.marketing.preference",
        ondelete="set null",
        index=True,
    )

    email = fields.Char(readonly=True)
    mobile = fields.Char(readonly=True)
    record_count = fields.Integer(
        string="Recipients",
        default=1,
        readonly=True,
        help="Stable measure used by Marketing Pivot/Graph analysis.",
    )
    inclusion_state = fields.Selection(
        [
            ("included", "Included"),
            ("excluded", "Excluded"),
        ],
        required=True,
        default="excluded",
        index=True,
    )
    exclusion_reason = fields.Char(readonly=True)

    email_allowed = fields.Boolean(readonly=True, index=True)
    whatsapp_allowed = fields.Boolean(readonly=True, index=True)

    email_delivery_state = fields.Selection(
        [
            ("not_applicable", "Not Applicable"),
            ("pending", "Pending"),
            ("outgoing", "Outgoing"),
            ("processing", "Processing"),
            ("sent", "Delivered"),
            ("opened", "Opened"),
            ("replied", "Replied"),
            ("bounced", "Bounced"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="not_applicable",
        required=True,
        readonly=True,
        index=True,
    )
    email_failure_reason = fields.Text(readonly=True)

    whatsapp_message_ids = fields.One2many(
        "clinic.marketing.message",
        "recipient_id",
        string="WhatsApp Messages",
        readonly=True,
    )
    whatsapp_state = fields.Selection(
        [
            ("not_applicable", "Not Applicable"),
            ("queued", "Queued"),
            ("opened", "Opened"),
            ("sent", "Sent"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        compute="_compute_whatsapp_state",
        store=True,
        index=True,
    )

    @api.depends("whatsapp_message_ids", "whatsapp_message_ids.state")
    def _compute_whatsapp_state(self):
        priority = {
            "failed": 5,
            "sent": 4,
            "opened": 3,
            "queued": 2,
            "cancelled": 1,
        }
        for record in self:
            if not record.whatsapp_allowed:
                record.whatsapp_state = "not_applicable"
                continue
            states = record.whatsapp_message_ids.mapped("state")
            record.whatsapp_state = (
                max(states, key=lambda state: priority.get(state, 0))
                if states
                else "queued"
            )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("marketing_audience_build"):
            raise AccessError(
                _("Campaign Recipient snapshots can only be built by the Campaign engine.")
            )
        return super().create(vals_list)

    # Recipient identity/eligibility is frozen after audience preparation; only delivery evidence may be synchronized later.
    def write(self, vals):
        mutable_delivery = {
            "email_delivery_state",
            "email_failure_reason",
        }
        if not (
            self.env.context.get("marketing_audience_build")
            or (
                self.env.context.get("marketing_delivery_sync")
                and set(vals).issubset(mutable_delivery)
            )
        ):
            raise AccessError(
                _("Campaign Recipient snapshots are immutable outside controlled delivery synchronization.")
            )
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("marketing_audience_build"):
            raise AccessError(
                _("Campaign Recipient snapshots can only be rebuilt by the Campaign engine.")
            )
        return super().unlink()

    @api.constrains("patient_id", "company_id", "preference_id")
    def _check_patient_scope(self):
        for record in self:
            if record.patient_id.company_id != record.company_id:
                raise ValidationError(_("Recipient Patient belongs to another company."))
            if (
                record.preference_id
                and record.preference_id.partner_id != record.partner_id
            ):
                raise ValidationError(_("Recipient preference belongs to another patient."))

    def action_open_patient(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Card"),
            "res_model": "clinic.patient",
            "view_mode": "form",
            "res_id": self.patient_id.id,
        }

    def action_open_preference(self):
        self.ensure_one()
        if not self.preference_id:
            raise UserError(_("No Marketing Preference is recorded for this patient."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Marketing Preference"),
            "res_model": "clinic.marketing.preference",
            "view_mode": "form",
            "res_id": self.preference_id.id,
        }

    def action_open_campaign(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Marketing Campaign"),
            "res_model": "clinic.marketing.campaign",
            "view_mode": "form",
            "res_id": self.campaign_id.id,
        }

    def action_open_whatsapp_messages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("WhatsApp Messages"),
            "res_model": "clinic.marketing.message",
            "view_mode": "list,form",
            "domain": [("recipient_id", "=", self.id)],
        }

