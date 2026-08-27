from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


EMAIL_TRACE_MAP = {
    "outgoing": "outgoing",
    "process": "processing",
    "pending": "sent",
    "sent": "sent",
    "open": "opened",
    "reply": "replied",
    "bounce": "bounced",
    "error": "failed",
    "cancel": "cancelled",
}


class ClinicMarketingCampaignDelivery(models.Model):
    """Native Email Marketing delegation and WhatsApp delivery synchronization."""

    _inherit = "clinic.marketing.campaign"

    # Delivery is deliberately isolated from audience construction. Odoo owns
    # Email dispatch/tracking; ClinicOne stores campaign provenance and maps
    # native trace evidence back to immutable patient recipient snapshots.
    def _ensure_utm_campaign(self):
        self.ensure_one()
        if not self.utm_campaign_id:
            # Odoo 19 UTM Campaign has both required technical name and
            # user-facing title semantics; set both explicitly for deterministic
            # creation across native quick-create/form behavior.
            utm = self.env["utm.campaign"].create({
                "name": self.name,
                "title": self.name,
            })
            self.with_context(marketing_campaign_transition=True).write({
                "utm_campaign_id": utm.id,
            })
        return self.utm_campaign_id

    def _ensure_email_mailing(self):
        self.ensure_one()
        if not self.send_email:
            return self.env["mailing.mailing"]
        if self.email_mailing_id:
            return self.email_mailing_id

        utm = self._ensure_utm_campaign()
        domain = [
            ("clinic_marketing_recipient_ids.campaign_id", "=", self.id),
            ("clinic_marketing_recipient_ids.inclusion_state", "=", "included"),
            ("clinic_marketing_recipient_ids.email_allowed", "=", True),
        ]
        values = {
            "subject": self.email_subject,
            "preview": self.email_preview or False,
            "body_arch": self.email_body_html,
            "mailing_model_id": self.env["ir.model"]._get_id("res.partner"),
            "mailing_domain": repr(domain),
            "mailing_type": "mail",
            "campaign_id": utm.id,
            "user_id": self.owner_id.id,
            "use_exclusion_list": True,
            "clinic_marketing_campaign_id": self.id,
        }
        if self.email_from:
            values["email_from"] = self.email_from
        if self.planned_at and self.planned_at > fields.Datetime.now():
            values.update({
                "schedule_type": "scheduled",
                "schedule_date": self.planned_at,
            })

        mailing = self.env["mailing.mailing"].create(values)
        self.with_context(marketing_campaign_transition=True).write({
            "email_mailing_id": mailing.id,
        })
        return mailing

    def _build_whatsapp_messages(self):
        self.ensure_one()
        if not self.send_whatsapp:
            return self.env["clinic.marketing.message"]

        if self.message_ids:
            return self.message_ids

        values = []
        for recipient in self.recipient_ids.filtered(
            lambda line:
            line.inclusion_state == "included" and line.whatsapp_allowed
        ):
            values.append({
                "campaign_id": self.id,
                "recipient_id": recipient.id,
                "destination": recipient.mobile,
                "body": self.whatsapp_body,
                "scheduled_at": self.planned_at or fields.Datetime.now(),
            })
        return self.env["clinic.marketing.message"].with_context(
            marketing_message_build=True
        ).create(values)

    def action_launch(self):
        self.ensure_one()
        self._require_manager()
        if self.state != "ready":
            raise UserError(_("Only a Ready Campaign can be launched."))
        self._validate_ready()

        if self.send_email:
            mailing = self._ensure_email_mailing()
            mailing.action_put_in_queue()

        if self.send_whatsapp:
            self._build_whatsapp_messages()

        self.with_context(marketing_campaign_transition=True).write({
            "state": "running",
            "launched_at": fields.Datetime.now(),
        })
        return True

    def action_sync_delivery(self):
        # Interactive delivery synchronization writes Recipient evidence and
        # therefore requires Coordinator authority. Cron executes under sudo.
        if not self.env.su:
            self._require_coordinator()

        for campaign in self:
            if campaign.email_mailing_id:
                traces = self.env["mailing.trace"].search([
                    ("mass_mailing_id", "=", campaign.email_mailing_id.id),
                    ("model", "=", "res.partner"),
                ])
                trace_by_partner = defaultdict(list)
                for trace in traces:
                    trace_by_partner[trace.res_id].append(trace)

                for recipient in campaign.recipient_ids.filtered("email_allowed"):
                    partner_traces = trace_by_partner.get(recipient.partner_id.id, [])
                    if not partner_traces:
                        continue
                    trace = sorted(
                        partner_traces,
                        key=lambda item: item.id,
                        reverse=True,
                    )[0]
                    recipient.with_context(marketing_delivery_sync=True).write({
                        "email_delivery_state": EMAIL_TRACE_MAP.get(
                            trace.trace_status,
                            "pending",
                        ),
                        "email_failure_reason": trace.failure_reason or False,
                    })
        return True

    def _delivery_complete(self):
        self.ensure_one()
        email_done = (
            not self.send_email
            or (
                self.email_mailing_id
                and self.email_mailing_id.state == "done"
            )
        )
        whatsapp_done = (
            not self.send_whatsapp
            or not self.message_ids.filtered(
                lambda message: message.state in ("queued", "opened")
            )
        )
        return bool(email_done and whatsapp_done)

    def action_complete(self):
        self.ensure_one()
        self._require_manager()
        self.action_sync_delivery()
        if self.state != "running":
            raise UserError(_("Only a Running Campaign can be completed."))
        if not self._delivery_complete():
            raise UserError(
                _("Campaign still has pending Email or WhatsApp delivery.")
            )
        self.with_context(marketing_campaign_transition=True).write({
            "state": "completed",
            "completed_at": fields.Datetime.now(),
        })
        return True

    def action_cancel(self):
        self._require_manager()
        for campaign in self:
            if campaign.email_mailing_id and campaign.email_mailing_id.state in (
                "draft",
                "in_queue",
            ):
                campaign.email_mailing_id.action_cancel()

            pending = campaign.message_ids.filtered(
                lambda message: message.state in ("queued", "opened")
            )
            if pending:
                pending.with_context(marketing_message_transition=True).write({
                    "state": "cancelled",
                })

        self.with_context(marketing_campaign_transition=True).write({
            "state": "cancelled",
        })
        return True

    def action_reset_to_draft(self):
        self.ensure_one()
        self._require_manager()
        if self.state not in ("cancelled", "completed"):
            raise UserError(_("Only Cancelled or Completed Campaigns can be reset."))
        if self.email_mailing_id and self.email_mailing_id.state not in ("draft",):
            raise UserError(
                _("A Campaign with a sent/queued native Mailing cannot be reset in place.")
            )

        self.recipient_ids.with_context(marketing_audience_build=True).unlink()
        self.message_ids.with_context(marketing_message_build=True).unlink()
        self.with_context(marketing_campaign_transition=True).write({
            "state": "draft",
            "launched_at": False,
            "completed_at": False,
            "email_mailing_id": False,
        })
        return True

    def action_open_recipients(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Campaign Audience"),
            "res_model": "clinic.marketing.recipient",
            "view_mode": "list,form,pivot,graph",
            "domain": [("campaign_id", "=", self.id)],
        }

    def action_open_whatsapp_messages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("WhatsApp Messages"),
            "res_model": "clinic.marketing.message",
            "view_mode": "list,form",
            "domain": [("campaign_id", "=", self.id)],
        }

    def action_open_email_mailing(self):
        self.ensure_one()
        if not self.email_mailing_id:
            raise UserError(_("No native Email Mailing has been created yet."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Odoo Email Mailing"),
            "res_model": "mailing.mailing",
            "view_mode": "form",
            "res_id": self.email_mailing_id.id,
        }

    def action_open_segment(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Marketing Segment"),
            "res_model": "clinic.marketing.segment",
            "view_mode": "form",
            "res_id": self.segment_id.id,
        }

    def action_open_promotion(self):
        self.ensure_one()
        if not self.promotion_id:
            raise UserError(_("This Campaign has no Promotion."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Marketing Promotion"),
            "res_model": "clinic.marketing.promotion",
            "view_mode": "form",
            "res_id": self.promotion_id.id,
        }

    @api.model
    def _cron_sync_running_campaigns(self):
        campaigns = self.sudo().search([
            ("state", "=", "running"),
        ], limit=200)
        for campaign in campaigns:
            try:
                with self.env.cr.savepoint():
                    campaign.action_sync_delivery()
                    if campaign._delivery_complete():
                        campaign.with_context(
                            marketing_campaign_transition=True
                        ).write({
                            "state": "completed",
                            "completed_at": fields.Datetime.now(),
                        })
            except Exception:
                # Cron must isolate campaigns; a single provider/mailing problem
                # must not become an endless retry loop for every campaign.
                continue
        return True

