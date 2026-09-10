
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class BookingRoom(models.Model):
    """Treatment Session extension of the clinic_booking room authority."""

    _inherit = "booking.room"

    treatment_session_ids = fields.One2many("clinic.treatment.session", "room_id", string="Treatment Sessions")
    treatment_session_count = fields.Integer(compute="_compute_session_statistics")
    sessions_today_count = fields.Integer(compute="_compute_session_statistics")
    sessions_in_use_count = fields.Integer(compute="_compute_session_statistics")
    next_session_id = fields.Many2one("clinic.treatment.session", compute="_compute_next_session")
    occupancy_state = fields.Selection([
        ("available", "Available"), ("scheduled", "Scheduled"), ("in_use", "In Use")
    ], compute="_compute_occupancy_state")
    occupancy_state_label = fields.Char(compute="_compute_occupancy_state")

    def _today_bounds(self):
        today = fields.Date.context_today(self)
        start = fields.Datetime.to_datetime(today)
        return start, fields.Datetime.add(start, days=1)

    def _compute_session_statistics(self):
        start, end = self._today_bounds()
        Session = self.env["clinic.treatment.session"]
        for room in self:
            base = [("room_id", "=", room.id)]
            room.treatment_session_count = Session.search_count(base)
            room.sessions_today_count = Session.search_count(base + [
                ("start_datetime", ">=", start), ("start_datetime", "<", end),
                ("state", "not in", ("cancelled", "no_show")),
            ])
            room.sessions_in_use_count = Session.search_count(base + [("state", "=", "in_progress")])

    def _compute_next_session(self):
        now = fields.Datetime.now()
        Session = self.env["clinic.treatment.session"]
        for room in self:
            room.next_session_id = Session.search([
                ("room_id", "=", room.id),
                ("state", "in", ("draft", "confirmed")),
                ("start_datetime", ">=", now),
            ], order="start_datetime, id", limit=1)

    @api.depends("treatment_session_ids.state", "treatment_session_ids.start_datetime", "treatment_session_ids.end_datetime")
    def _compute_occupancy_state(self):
        now = fields.Datetime.to_datetime(fields.Datetime.now())
        for room in self:
            sessions = room.treatment_session_ids
            in_use = any(
                s.state == "in_progress" and s.start_datetime
                and fields.Datetime.to_datetime(s.start_datetime) <= now
                and (not s.end_datetime or now < fields.Datetime.to_datetime(s.end_datetime))
                for s in sessions
            )
            if in_use:
                room.occupancy_state = "in_use"; room.occupancy_state_label = _("In Use")
            elif any(
                s.state in ("draft", "confirmed") and s.start_datetime
                and fields.Datetime.to_datetime(s.start_datetime) >= now
                for s in sessions
            ):
                room.occupancy_state = "scheduled"; room.occupancy_state_label = _("Scheduled")
            else:
                room.occupancy_state = "available"; room.occupancy_state_label = _("Available")

    def is_available(
        self,
        start_dt=None,
        end_dt=None,
        ignore_booking_id=None,
        consider_capacity=True,
        ignore_session_ids=None,
        **kwargs,
    ):
        """Preserve clinic_booking API, then add Treatment Session overlap.

        19.0.2.0.2 exposed only ``ignore_session_ids`` and therefore rejected
        valid owner calls carrying ``ignore_booking_id=...``.
        """
        self.ensure_one()

        # Owner keyword contract is start_dt/end_dt. Preserve the historical
        # Treatment Session keyword names as compatibility aliases.
        if start_dt is None and "start_datetime" in kwargs:
            start_dt = kwargs.pop("start_datetime")
        if end_dt is None and "end_datetime" in kwargs:
            end_dt = kwargs.pop("end_datetime")
        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            raise TypeError("Unexpected room availability keyword(s): %s" % unexpected)

        if ignore_session_ids is None:
            if getattr(ignore_booking_id, "_name", None) == "clinic.treatment.session":
                ignore_session_ids = ignore_booking_id
                ignore_booking_id = None
            elif isinstance(ignore_booking_id, (list, tuple, set)):
                ignore_session_ids = ignore_booking_id
                ignore_booking_id = None

        if not super().is_available(
            start_dt,
            end_dt,
            ignore_booking_id=ignore_booking_id,
            consider_capacity=consider_capacity,
        ):
            return False

        if not start_dt or not end_dt:
            return False

        ignore_ids = []
        if ignore_session_ids:
            if hasattr(ignore_session_ids, "ids"):
                ignore_ids = list(ignore_session_ids.ids)
            elif isinstance(ignore_session_ids, (list, tuple, set)):
                ignore_ids = list(ignore_session_ids)
            elif isinstance(ignore_session_ids, int):
                ignore_ids = [ignore_session_ids]

        domain = [
            ("room_id", "=", self.id),
            ("state", "in", ("draft", "confirmed", "in_progress")),
            ("id", "not in", ignore_ids),
            ("start_datetime", "<", end_dt),
            ("end_datetime", ">", start_dt),
        ]
        return self.env["clinic.treatment.session"].search_count(domain) == 0

    def get_occupancy_summary(self):
        self.ensure_one()
        return {
            "room_id": self.id, "room_name": self.display_name,
            "occupancy_state": self.occupancy_state,
            "occupancy_state_label": self.occupancy_state_label,
            "treatment_session_count": self.treatment_session_count,
            "sessions_today_count": self.sessions_today_count,
            "sessions_in_use_count": self.sessions_in_use_count,
            "next_session_id": self.next_session_id.id if self.next_session_id else False,
        }

    def action_view_treatment_sessions(self):
        self.ensure_one()
        action = self.env.ref("clinic_treatment_session.action_clinic_treatment_session").read()[0]
        action["domain"] = [("room_id", "=", self.id)]
        action["context"] = {"default_room_id": self.id}
        return action

    def action_view_today_treatment_sessions(self):
        self.ensure_one()
        start, end = self._today_bounds()
        action = self.action_view_treatment_sessions()
        action["domain"] = [
            ("room_id", "=", self.id), ("start_datetime", ">=", start),
            ("start_datetime", "<", end), ("state", "!=", "cancelled"),
        ]
        return action
