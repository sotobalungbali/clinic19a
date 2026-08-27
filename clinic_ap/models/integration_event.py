import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ClinicAPIntegrationEvent(models.Model):
    _name = "clinic.ap.integration.event"
    _description = "Clinic AP Integration Event"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    _event_key_unique = models.Constraint(
        "UNIQUE(event_key)",
        "AP integration event key must be unique.",
    )

    event_key = fields.Char(required=True, copy=False, index=True)
    event_type = fields.Char(required=True, index=True)
    ap_id = fields.Many2one("clinic.ap", ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    payload_json = fields.Text()
    state = fields.Selection(
        [("pending", "Pending"), ("processed", "Processed"), ("failed", "Failed")],
        default="pending",
        required=True,
        index=True,
    )
    attempt_count = fields.Integer(default=0)
    last_error = fields.Text()
    processed_at = fields.Datetime()

    @api.model
    def create_event(self, event_type, ap, payload=None):
        key = f"{event_type}:{ap.id}:{fields.Datetime.now()}:{self.env.uid}"
        return self.create({
            "event_key": key,
            "event_type": event_type,
            "ap_id": ap.id,
            "company_id": ap.company_id.id,
            "payload_json": json.dumps(payload or {}, default=str, sort_keys=True),
        })

    def action_mark_processed(self):
        self.write({
            "state": "processed",
            "processed_at": fields.Datetime.now(),
            "last_error": False,
        })
        return True

    def action_retry(self):
        for rec in self:
            if rec.attempt_count >= 3:
                raise UserError(_("Maximum AP integration retry attempts reached."))
            rec.write({
                "state": "pending",
                "attempt_count": rec.attempt_count + 1,
                "last_error": False,
            })
        return True

    @api.model
    def _cron_retry_pending(self):
        # Outbox delivery is intentionally delegated to downstream modules.
        # This cron only keeps the bounded lifecycle explicit.
        return True
