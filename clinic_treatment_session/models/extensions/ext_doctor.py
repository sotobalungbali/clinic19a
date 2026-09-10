
# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    """Historical employee/provider Treatment Session workload extension."""

    _inherit = "hr.employee"

    treatment_session_ids = fields.One2many("clinic.treatment.session", "clinic_doctor_id")
    treatment_session_count = fields.Integer(compute="_compute_treatment_statistics")
    sessions_today_count = fields.Integer(compute="_compute_treatment_statistics")
    sessions_in_progress_count = fields.Integer(compute="_compute_treatment_statistics")
    last_session_id = fields.Many2one("clinic.treatment.session", compute="_compute_treatment_statistics")
    next_session_id = fields.Many2one("clinic.treatment.session", compute="_compute_treatment_statistics")
    last_session_date = fields.Datetime(compute="_compute_treatment_statistics")
    next_session_date = fields.Datetime(compute="_compute_treatment_statistics")

    def _compute_treatment_statistics(self):
        today = fields.Date.context_today(self)
        start = fields.Datetime.to_datetime(today); end = fields.Datetime.add(start, days=1)
        now = fields.Datetime.now(); Session = self.env["clinic.treatment.session"]
        for rec in self:
            base = [("clinic_doctor_id", "=", rec.id)]
            rec.treatment_session_count = Session.search_count(base)
            rec.sessions_today_count = Session.search_count(base + [
                ("start_datetime", ">=", start), ("start_datetime", "<", end),
                ("state", "not in", ("cancelled", "no_show")),
            ])
            rec.sessions_in_progress_count = Session.search_count(base + [("state", "=", "in_progress")])
            last = Session.search(base + [("state", "=", "done"), ("start_datetime", "<=", now)], order="start_datetime desc, id desc", limit=1)
            nxt = Session.search(base + [("state", "in", ("draft", "confirmed", "in_progress")), ("start_datetime", ">=", now)], order="start_datetime, id", limit=1)
            rec.last_session_id = last; rec.last_session_date = last.start_datetime if last else False
            rec.next_session_id = nxt; rec.next_session_date = nxt.start_datetime if nxt else False

    def action_view_treatment_sessions(self):
        self.ensure_one()
        action = self.env.ref("clinic_treatment_session.action_clinic_treatment_session").read()[0]
        action["domain"] = [("clinic_doctor_id", "=", self.id)]
        return action

    def action_view_today_treatment_sessions(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        start = fields.Datetime.to_datetime(today); end = fields.Datetime.add(start, days=1)
        action = self.action_view_treatment_sessions()
        action["domain"] = [("clinic_doctor_id", "=", self.id), ("start_datetime", ">=", start), ("start_datetime", "<", end)]
        return action

    def get_treatment_statistics(self):
        Session = self.env["clinic.treatment.session"]
        results = []
        for rec in self:
            base = [("clinic_doctor_id", "=", rec.id)]
            results.append({
                "doctor_id": rec.id, "doctor_name": rec.display_name,
                "total_sessions": Session.search_count(base),
                "total_done": Session.search_count(base + [("state", "=", "done")]),
                "total_no_show": Session.search_count(base + [("state", "=", "no_show")]),
                "total_cancelled": Session.search_count(base + [("state", "=", "cancelled")]),
            })
        return results if len(self) > 1 else (results[0] if results else {})
