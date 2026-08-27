import re
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicMarketingMessage(models.Model):
    """Governed WhatsApp outreach queue.

    Addon 32 owns message intent/evidence, not a third-party gateway connector.
    Future `clinic_integration_api` may override `_dispatch_via_gateway()`.
    """

    _name = "clinic.marketing.message"
    _description = "Clinic Marketing WhatsApp Message"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "scheduled_at, id"
    _check_company_auto = True

    _campaign_recipient_unique = models.Constraint(
        "UNIQUE(campaign_id, recipient_id)",
        "Only one WhatsApp message is allowed per recipient and campaign.",
    )
    _queue_idx = models.Index("(company_id, state, scheduled_at)")

    campaign_id = fields.Many2one(
        "clinic.marketing.campaign",
        required=True,
        ondelete="cascade",
        index=True,
    )
    recipient_id = fields.Many2one(
        "clinic.marketing.recipient",
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
    patient_id = fields.Many2one(
        related="recipient_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one(
        related="recipient_id.partner_id",
        store=True,
        readonly=True,
        index=True,
    )
    destination = fields.Char(required=True, readonly=True)
    body = fields.Text(required=True)
    scheduled_at = fields.Datetime(default=fields.Datetime.now, index=True)
    state = fields.Selection(
        [
            ("queued", "Queued"),
            ("opened", "Opened in WhatsApp"),
            ("sent", "Sent"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="queued",
        required=True,
        readonly=True,
        tracking=True,
        index=True,
    )
    opened_at = fields.Datetime(readonly=True)
    sent_at = fields.Datetime(readonly=True)
    failure_reason = fields.Text(readonly=True)
    provider_reference = fields.Char(
        readonly=True,
        help="Reserved for a future provider bridge / clinic_integration_api.",
    )
    whatsapp_url = fields.Char(compute="_compute_whatsapp_url")

    @api.depends("destination", "body")
    def _compute_whatsapp_url(self):
        for record in self:
            phone = record.destination or ""
            record.whatsapp_url = (
                f"https://wa.me/{phone}?text={quote(record.body or '')}"
                if phone
                else False
            )

    @api.model
    def _normalize_destination(self, raw_phone, company):
        digits = re.sub(r"\D+", "", raw_phone or "")
        if not digits:
            return False
        if digits.startswith("0") and company.country_id.phone_code:
            return f"{company.country_id.phone_code}{digits[1:]}"
        return digits

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("marketing_message_build"):
            raise AccessError(
                _("WhatsApp campaign messages can only be created by the Campaign engine.")
            )
        return super().create(vals_list)

    def write(self, vals):
        allowed = {
            "state",
            "opened_at",
            "sent_at",
            "failure_reason",
            "provider_reference",
        }
        if not (
            self.env.context.get("marketing_message_transition")
            and set(vals).issubset(allowed)
        ):
            raise AccessError(
                _("Use WhatsApp message workflow actions to change delivery state.")
            )
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("marketing_message_build"):
            raise AccessError(
                _("WhatsApp messages can only be rebuilt by the Campaign engine.")
            )
        return super().unlink()

    @api.constrains("campaign_id", "recipient_id", "destination")
    def _check_scope(self):
        for record in self:
            if record.recipient_id.campaign_id != record.campaign_id:
                raise ValidationError(_("WhatsApp Recipient belongs to another Campaign."))
            if not record.recipient_id.whatsapp_allowed:
                raise ValidationError(
                    _("WhatsApp message cannot be created for a recipient without WhatsApp permission.")
                )
            if not record.destination:
                raise ValidationError(_("WhatsApp destination is required."))

    # Provider transport is an explicit extension seam so addon 32 stays installable without future integration_api.
    def _dispatch_via_gateway(self):
        """Provider-neutral extension hook.

        Return a provider reference on success. The base addon deliberately
        returns False because automated WhatsApp gateway ownership belongs to the
        later `clinic_integration_api` layer.
        """
        self.ensure_one()
        return False

    def action_open_whatsapp(self):
        self.ensure_one()
        if self.state not in ("queued", "opened"):
            raise UserError(_("Only queued/opened messages can be opened in WhatsApp."))
        if not self.whatsapp_url:
            raise UserError(_("A valid WhatsApp destination is required."))

        if self.state == "queued":
            self.with_context(marketing_message_transition=True).write({
                "state": "opened",
                "opened_at": fields.Datetime.now(),
            })

        return {
            "type": "ir.actions.act_url",
            "url": self.whatsapp_url,
            "target": "new",
        }

    def action_dispatch_gateway(self):
        self.ensure_one()
        if self.state not in ("queued", "opened"):
            raise UserError(_("Only queued/opened messages can be dispatched."))
        provider_ref = self._dispatch_via_gateway()
        if not provider_ref:
            raise UserError(
                _(
                    "No automated WhatsApp gateway is installed. Use Open WhatsApp "
                    "for manual dispatch, or let clinic_integration_api override "
                    "the provider transport hook later."
                )
            )
        self.with_context(marketing_message_transition=True).write({
            "state": "sent",
            "sent_at": fields.Datetime.now(),
            "provider_reference": str(provider_ref),
            "failure_reason": False,
        })
        return True

    def action_mark_sent(self):
        self.with_context(marketing_message_transition=True).write({
            "state": "sent",
            "sent_at": fields.Datetime.now(),
            "failure_reason": False,
        })
        return True

    def action_mark_failed(self):
        self.with_context(marketing_message_transition=True).write({
            "state": "failed",
            "failure_reason": _("Marked failed by marketing operator."),
        })
        return True

    def action_cancel(self):
        self.with_context(marketing_message_transition=True).write({
            "state": "cancelled",
        })
        return True


    @api.model
    # Queue processing is bounded and record-isolated; provider failures are persisted per message rather than aborting the batch.
    def _cron_dispatch_due(self):
        companies = self.env["res.company"].sudo().search([
            ("clinic_marketing_whatsapp_transport", "=", "extension"),
        ])
        if not companies:
            return True

        due = self.sudo().search([
            ("company_id", "in", companies.ids),
            ("state", "=", "queued"),
            ("scheduled_at", "<=", fields.Datetime.now()),
        ], order="scheduled_at, id", limit=200)

        for message in due:
            try:
                with self.env.cr.savepoint():
                    provider_ref = message._dispatch_via_gateway()
                    if provider_ref:
                        message.with_context(
                            marketing_message_transition=True
                        ).write({
                            "state": "sent",
                            "sent_at": fields.Datetime.now(),
                            "provider_reference": str(provider_ref),
                            "failure_reason": False,
                        })
            except Exception as exc:
                message.with_context(
                    marketing_message_transition=True
                ).write({
                    "state": "failed",
                    "failure_reason": str(exc),
                })
        return True

    def action_open_patient(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Card"),
            "res_model": "clinic.patient",
            "view_mode": "form",
            "res_id": self.patient_id.id,
        }

