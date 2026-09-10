
# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    """Historical patient/contact Treatment Session history extension."""

    _inherit = "res.partner"

    treatment_session_ids = fields.One2many("clinic.treatment.session", "patient_id")
    treatment_session_count = fields.Integer(compute="_compute_treatment_session_statistics")
    last_session_id = fields.Many2one("clinic.treatment.session", compute="_compute_treatment_session_statistics")
    last_session_date = fields.Datetime(compute="_compute_treatment_session_statistics")
    next_session_id = fields.Many2one("clinic.treatment.session", compute="_compute_treatment_session_statistics")
    next_session_date = fields.Datetime(compute="_compute_treatment_session_statistics")

    def _is_patient_partner(self):
        self.ensure_one()
        return bool(getattr(self, "is_patient", False))

    def _base_session_domain(self):
        self.ensure_one()
        return [("patient_id", "=", self.id)]

    def _compute_treatment_session_statistics(self):
        now = fields.Datetime.now()
        Session = self.env["clinic.treatment.session"]
        for rec in self:
            domain = rec._base_session_domain()
            rec.treatment_session_count = Session.search_count(domain)
            last = Session.search(domain + [("state", "=", "done"), ("start_datetime", "<=", now)], order="start_datetime desc, id desc", limit=1)
            nxt = Session.search(domain + [("state", "in", ("draft", "confirmed", "in_progress")), ("start_datetime", ">=", now)], order="start_datetime, id", limit=1)
            rec.last_session_id = last; rec.last_session_date = last.start_datetime if last else False
            rec.next_session_id = nxt; rec.next_session_date = nxt.start_datetime if nxt else False

    def action_view_treatment_sessions(self):
        self.ensure_one()
        action = self.env.ref("clinic_treatment_session.action_clinic_treatment_session").read()[0]
        action["domain"] = self._base_session_domain()
        return action

    def action_view_treatment_history(self):
        self.ensure_one()
        action = self.action_view_treatment_sessions()
        action["domain"] = self._base_session_domain() + [("state", "in", ("done", "no_show", "cancelled"))]
        return action

    def get_treatment_statistics(self, since_date=False):
        Session = self.env["clinic.treatment.session"]
        results = []
        since_dt = fields.Datetime.to_datetime(since_date) if since_date else False
        for rec in self:
            domain = rec._base_session_domain()
            if since_dt:
                domain.append(("start_datetime", ">=", since_dt))
            groups = Session.read_group(domain, ["state", "id:count"], ["state"], lazy=False)
            counts = {g["state"]: g.get("state_count", 0) for g in groups}
            results.append({
                "patient_id": rec.id, "patient_name": rec.display_name,
                "total_sessions": sum(counts.values()),
                "total_done": counts.get("done", 0),
                "total_no_show": counts.get("no_show", 0),
                "total_cancelled": counts.get("cancelled", 0),
                "total_upcoming": sum(counts.get(s, 0) for s in ("draft", "confirmed", "in_progress")),
                "last_session_id": rec.last_session_id.id if rec.last_session_id else False,
                "next_session_id": rec.next_session_id.id if rec.next_session_id else False,
            })
        return results if len(self) > 1 else (results[0] if results else {})
