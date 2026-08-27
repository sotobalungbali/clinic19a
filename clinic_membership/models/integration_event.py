

# -*- coding: utf-8 -*-
import json
import uuid

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MembershipIntegrationEvent(models.Model):
    """Transactional outbox for downstream ClinicOne financial/portal modules.

    ``clinic_membership`` is intentionally upstream of ``clinic_billing``.
    Therefore it publishes business events instead of importing downstream owner
    models. Billing/AR/Wallet/Portal/Marketing/Analytics may inherit this model
    later and override ``_dispatch_event``.
    """

    _name = "membership.integration.event"
    _description = "Membership Integration Event"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"

    MAX_ATTEMPTS = 3

    name = fields.Char(
        string="Event UID",
        required=True,
        copy=False,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
    )
    event_code = fields.Char(required=True, index=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    contract_id = fields.Many2one(
        "membership.contract", ondelete="set null", index=True
    )
    source_model = fields.Char(required=True, index=True)
    source_res_id = fields.Integer(required=True, index=True)
    source_reference = fields.Char(index=True)
    payload_json = fields.Text(default="{}")

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("processed", "Processed"),
            ("failed", "Failed"),
            ("ignored", "Ignored"),
        ],
        default="pending",
        required=True,
        index=True,
        tracking=True,
    )
    attempts = fields.Integer(default=0, readonly=True)
    last_attempt_on = fields.Datetime(readonly=True)
    processed_on = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)

    _uid_uniq = models.Constraint(
        "UNIQUE(name)",
        "Membership integration event UID must be unique.",
    )
    _attempts_non_negative = models.Constraint(
        "CHECK(attempts >= 0)",
        "Integration event attempts cannot be negative.",
    )

    @api.model
    def _json_dumps(self, payload):
        return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)

    def payload(self):
        self.ensure_one()
        try:
            return json.loads(self.payload_json or "{}")
        except (TypeError, ValueError):
            return {}

    def _dispatch_event(self):
        """Default outbox behavior: acknowledge.

        Downstream addons override this method if they need a durable side effect.
        """
        self.ensure_one()
        return True

    def action_process(self):
        max_attempts = self.MAX_ATTEMPTS
        for rec in self:
            if rec.state in ("processed", "ignored"):
                continue
            if rec.attempts >= max_attempts:
                raise UserError(
                    _("This event reached the bounded retry limit. Review its root cause before retrying.")
                )
            values = {
                "attempts": rec.attempts + 1,
                "last_attempt_on": fields.Datetime.now(),
            }
            try:
                with rec.env.cr.savepoint():
                    result = rec._dispatch_event()
                    if result is False:
                        raise UserError(_("Downstream dispatcher returned False."))
                values.update(
                    {
                        "state": "processed",
                        "processed_on": fields.Datetime.now(),
                        "last_error": False,
                    }
                )
            except Exception as exc:
                values.update({"state": "failed", "last_error": str(exc)})
            rec.write(values)
        return True

    def action_retry(self):
        for rec in self:
            if rec.state != "failed":
                raise UserError(_("Only Failed events can be retried."))
            if rec.attempts >= self.MAX_ATTEMPTS:
                raise UserError(
                    _("Bounded retry limit reached. A root-cause review is required.")
                )
            rec.write({"state": "pending", "last_error": False})
            rec.action_process()
        return True

    def action_ignore(self):
        for rec in self:
            if rec.state == "processed":
                raise UserError(_("Processed events cannot be ignored."))
            rec.write({"state": "ignored"})
        return True

    def action_view_source(self):
        self.ensure_one()
        if self.source_model not in self.env:
            raise UserError(_("Source model is not available in this database."))
        record = self.env[self.source_model].browse(self.source_res_id).exists()
        if not record:
            raise UserError(_("Source record no longer exists."))
        return {
            "type": "ir.actions.act_window",
            "name": self.source_reference or self.event_code,
            "res_model": self.source_model,
            "view_mode": "form",
            "res_id": record.id,
        }

    @api.model
    def cron_process_pending_events(self):
        events = self.search(
            [("state", "=", "pending"), ("attempts", "<", self.MAX_ATTEMPTS)],
            order="create_date asc, id asc",
            limit=100,
        )
        events.action_process()
        return True

