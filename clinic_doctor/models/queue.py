
# -*- coding: utf-8 -*-
# File: clinic_doctor/models/queue.py
# Module: clinic_doctor
#
# ClinicOne — Queue integration bridges (Odoo 19 CE ready)
#
# Scope
# -----
# - Extend clinic.queue.token to link with clinic.appointment and compute KPIs.
# - Provide helpers/actions to create/link/open appointments from tokens.
# - Add queue counters on clinic.doctor for quick navigation.
#
# Notes
# -----
# * This file assumes the core queue models live in `clinic_queue_room`.
# * We do not redefine states/fields that already exist in queue models.
# * All cross-module links are optional and guarded by presence checks.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


# -----------------------------------------------------------------------------
# EXTEND: clinic.queue.token
# -----------------------------------------------------------------------------
class ClinicQueueToken(models.Model):
    _inherit = "clinic.queue.token"

    # Link the token to a ClinicOne appointment (optional)
    appointment_id = fields.Many2one(
        "clinic.appointment",
        ondelete="set null",
        index=True,
        help="Linked appointment that originated or consumed this token."
    )

    # Convenience mirrors (derived if not provided by base model)
    doctor_display = fields.Char(
        compute="_compute_presenters",
        store=False,
        help="Display label of the linked doctor."
    )
    patient_display = fields.Char(
        compute="_compute_presenters",
        store=False,
        help="Display label of the linked patient."
    )
    room_display = fields.Char(
        compute="_compute_presenters",
        store=False,
        help="Display label of the linked room."
    )

    # KPI times in seconds (best-effort, using whatever timestamps the queue model has)
    wait_time_sec = fields.Integer(
        compute="_compute_time_kpis",
        store=False,
        help="Estimated waiting time in seconds (check-in to service start)."
    )
    service_time_sec = fields.Integer(
        compute="_compute_time_kpis",
        store=False,
        help="Estimated service time in seconds (service start to end)."
    )
    total_time_sec = fields.Integer(
        compute="_compute_time_kpis",
        store=False,
        help="Total time in seconds (check-in to end)."
    )

    # -------------------------------------------------------------------------
    # PRESENTATION COMPUTES
    # -------------------------------------------------------------------------
    def _safe_get(self, rec, fname, default=False):
        """Return rec.<fname> iff field exists, else default."""
        return getattr(rec, fname) if fname in rec._fields else default

    def _compute_presenters(self):
        """
        Prefer values from appointment (if linked), else from native token fields (if present).
        """
        for rec in self:
            # Doctor
            doc_name = ""
            if rec.appointment_id and rec.appointment_id.doctor_id:
                doc_name = rec.appointment_id.doctor_id.display_name
            elif self._safe_get(rec, "doctor_id"):
                doc_name = rec.doctor_id.display_name
            rec.doctor_display = doc_name or ""

            # Patient
            pat_name = ""
            if rec.appointment_id and rec.appointment_id.partner_id:
                pat_name = rec.appointment_id.partner_id.display_name
            elif self._safe_get(rec, "partner_id"):
                pat_name = rec.partner_id.display_name
            rec.patient_display = pat_name or ""

            # Room
            room_name = ""
            if rec.appointment_id and rec.appointment_id.room_id:
                room_name = rec.appointment_id.room_id.display_name
            elif self._safe_get(rec, "room_id"):
                room_name = rec.room_id.display_name
            rec.room_display = room_name or ""

    # -------------------------------------------------------------------------
    # TIME KPI COMPUTES
    # -------------------------------------------------------------------------
    def _compute_time_kpis(self):
        """
        Heuristics:
        - Check-in time  : token.checkin_time if present, else create_date
        - Service start  : token.service_start or called_time or in_service_at
        - Service end    : token.service_end or done_time or write_date (if state is done)
        """
        now = fields.Datetime.now()
        for rec in self:
            # checkin
            checkin = (
                self._safe_get(rec, "checkin_time") or
                rec.create_date
            )
            # start
            start = (
                self._safe_get(rec, "service_start") or
                self._safe_get(rec, "called_time") or
                self._safe_get(rec, "in_service_at")
            )
            # end
            end = (
                self._safe_get(rec, "service_end") or
                self._safe_get(rec, "done_time")
            )

            # infer end if in terminal state without explicit end time
            state = self._safe_get(rec, "state")
            if not end and state in ("done", "cancel", "canceled", "closed"):
                end = rec.write_date

            # compute seconds
            wait = 0
            service = 0
            total = 0

            if checkin:
                start_eff = start or now
                wait = int((start_eff - checkin).total_seconds())

            if start:
                end_eff = end or now
                service = int((end_eff - start).total_seconds())

            if checkin:
                end_eff = end or now
                total = int((end_eff - checkin).total_seconds())

            rec.wait_time_sec = max(0, wait)
            rec.service_time_sec = max(0, service)
            rec.total_time_sec = max(0, total)

    # -------------------------------------------------------------------------
    # CONSTRAINTS & ALIGNMENT WITH APPOINTMENT
    # -------------------------------------------------------------------------
    @api.constrains("appointment_id")
    def _check_alignment_with_appointment(self):
        """
        Best-effort consistency checks:
        - doctor alignment (if token has doctor_id)
        - room alignment (if both sides have room and not empty)
        - time window overlap (if token stores scheduled window)
        """
        for rec in self:
            appt = rec.appointment_id
            if not appt:
                continue

            # Doctor alignment
            if self._safe_get(rec, "doctor_id") and appt.doctor_id and rec.doctor_id.id != appt.doctor_id.id:
                raise ValidationError(_("Queue token doctor does not match the appointment doctor."))

            # Room alignment (soft fail if one side missing)
            if self._safe_get(rec, "room_id") and appt.room_id and rec.room_id and rec.room_id.id != appt.room_id.id:
                raise ValidationError(_("Queue token room does not match the appointment room."))

            # Time overlap using scheduled window if exists on token
            sched_start = self._safe_get(rec, "scheduled_start")
            sched_end = self._safe_get(rec, "scheduled_end")
            if sched_start and sched_end and appt.start and appt.end:
                overlap = not (appt.end <= sched_start or appt.start >= sched_end)
                if not overlap:
                    raise ValidationError(_("Queue token scheduled window does not overlap the appointment window."))

    # -------------------------------------------------------------------------
    # HELPERS / ACTIONS
    # -------------------------------------------------------------------------
    def action_open_appointment(self):
        """Open the linked appointment (or show a toast if none)."""
        self.ensure_one()
        if not self.appointment_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Appointment"),
                    "message": _("This token is not linked to an appointment."),
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Appointment"),
            "res_model": "clinic.appointment",
            "view_mode": "form",
            "res_id": self.appointment_id.id,
            "target": "current",
        }

    def action_create_appointment(self):
        """
        Create an appointment pre-filled from the token context.
        This action requires clinic.appointment.
        """
        self.ensure_one()
        if "clinic.appointment" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Appointment module is not installed."),
                           "sticky": False},
            }

        ctx = {
            "default_company_id": getattr(self, "company_id", False) and self.company_id.id or False,
        }

        # Fill from token fields if present
        if self._safe_get(self, "doctor_id") and self.doctor_id:
            ctx["default_doctor_id"] = self.doctor_id.id
        if self._safe_get(self, "room_id") and self.room_id:
            ctx["default_room_id"] = self.room_id.id
        if self._safe_get(self, "partner_id") and self.partner_id:
            ctx["default_partner_id"] = self.partner_id.id
        if self._safe_get(self, "specialty_id") and self.specialty_id:
            ctx["default_specialty_id"] = self.specialty_id.id
        if self._safe_get(self, "scheduled_start"):
            ctx["default_start"] = self.scheduled_start
        if self._safe_get(self, "scheduled_end"):
            ctx["default_end"] = self.scheduled_end
        # Link back to slot if token already holds it (some deployments)
        if self._safe_get(self, "slot_id") and self.slot_id:
            ctx["default_slot_id"] = self.slot_id.id

        return {
            "type": "ir.actions.act_window",
            "name": _("Create Appointment"),
            "res_model": "clinic.appointment",
            "view_mode": "form",
            "target": "current",
            "context": ctx,
        }

    def action_link_to_existing_appointment(self):
        """
        Open a search window to link an existing appointment. Use a domain filtered
        by doctor/patient/time if available.
        """
        self.ensure_one()
        if "clinic.appointment" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Appointment module is not installed."),
                           "sticky": False},
            }
        domain = []
        if self._safe_get(self, "doctor_id") and self.doctor_id:
            domain += [("doctor_id", "=", self.doctor_id.id)]
        if self._safe_get(self, "partner_id") and self.partner_id:
            domain += [("partner_id", "=", self.partner_id.id)]
        if self._safe_get(self, "scheduled_start") and self._safe_get(self, "scheduled_end"):
            domain += [
                ("start", "<", self.scheduled_end),
                ("end", ">", self.scheduled_start),
            ]
        return {
            "type": "ir.actions.act_window",
            "name": _("Select Appointment"),
            "res_model": "clinic.appointment",
            "view_mode": "tree,form,calendar",
            "domain": domain,
            "target": "current",
            "context": {
                "default_doctor_id": self._safe_get(self, "doctor_id") and self.doctor_id.id or False,
                "default_partner_id": self._safe_get(self, "partner_id") and self.partner_id.id or False,
            },
        }

    # Optional utility: link programmatically (used by other modules)
    def link_to_appointment(self, appointment):
        """
        Programmatically link this token to an appointment and align key fields.
        """
        self.ensure_one()
        if not appointment:
            return False
        vals = {"appointment_id": appointment.id}
        # align key fields when available (best-effort)
        if self._safe_get(self, "doctor_id") and appointment.doctor_id:
            vals["doctor_id"] = appointment.doctor_id.id
        if self._safe_get(self, "room_id") and appointment.room_id:
            vals["room_id"] = appointment.room_id.id
        if self._safe_get(self, "partner_id") and appointment.partner_id:
            vals["partner_id"] = appointment.partner_id.id
        if self._safe_get(self, "scheduled_start") and appointment.start:
            vals["scheduled_start"] = appointment.start
        if self._safe_get(self, "scheduled_end") and appointment.end:
            vals["scheduled_end"] = appointment.end
        self.sudo().write(vals)
        return True


# -----------------------------------------------------------------------------
# EXTEND: clinic.queue (optional aggregate helpers)
# -----------------------------------------------------------------------------
class ClinicQueue(models.Model):
    _inherit = "clinic.queue"

    doctor_count = fields.Integer(
        compute="_compute_doctor_count",
        store=False,
        help="Number of distinct doctors currently represented in this queue (best-effort)."
    )

    def _compute_doctor_count(self):
        for rec in self:
            cnt = 0
            if "clinic.queue.token" in self.env:
                Token = self.env["clinic.queue.token"]
                token_domain = [("queue_id", "=", rec.id)]
                # filter out terminal tokens if state is present
                if "state" in Token._fields:
                    token_domain += [("state", "not in", ["done", "canceled", "cancel", "closed"])]
                doc_ids = Token.search(token_domain).mapped("doctor_id") if "doctor_id" in Token._fields else []
                cnt = len(set(doc_ids))
            rec.doctor_count = cnt


# -----------------------------------------------------------------------------
# EXTEND: clinic.doctor (queue counters & shortcuts) # pindah ke file doctor.py
# -----------------------------------------------------------------------------
# class ClinicDoctor(models.Model):
#     _inherit = "clinic.doctor"

#     queue_waiting_count = fields.Integer(
#         compute="_compute_queue_counts",
#         store=False,
#         help="Number of waiting queue tokens for this doctor."
#     )
#     queue_in_service_count = fields.Integer(
#         compute="_compute_queue_counts",
#         store=False,
#         help="Number of in-service queue tokens for this doctor."
#     )
#     last_queue_token_id = fields.Many2one(
#         "clinic.queue.token",
#         compute="_compute_queue_counts",
#         store=False,
#         help="Most recent queue token for this doctor."
#     )

#     def _compute_queue_counts(self):
#         Token = self.env["clinic.queue.token"] if "clinic.queue.token" in self.env else False
#         for rec in self:
#             rec.queue_waiting_count = 0
#             rec.queue_in_service_count = 0
#             rec.last_queue_token_id = False
#             if not Token or "doctor_id" not in Token._fields:
#                 continue

#             dom_base = [("doctor_id", "=", rec.id)]
#             # Waiting: states that represent belum dipanggil/menunggu
#             dom_wait = dom_base + [("state", "in", ["new", "waiting", "queued", "called"])] if "state" in Token._fields else dom_base
#             # In service
#             dom_srv = dom_base + [("state", "in", ["in_service", "serving"])] if "state" in Token._fields else dom_base

#             rec.queue_waiting_count = Token.search_count(dom_wait)
#             rec.queue_in_service_count = Token.search_count(dom_srv)

#             # Last token (by write_date/create_date)
#             token_last = Token.search(dom_base, order="write_date desc, create_date desc", limit=1)
#             rec.last_queue_token_id = token_last.id if token_last else False

#     # Actions (open tokens by state)
#     def action_view_queue_tokens(self):
#         self.ensure_one()
#         if "clinic.queue.token" not in self.env:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {"title": _("Not Available"),
#                            "message": _("Queue module is not installed."),
#                            "sticky": False},
#             }
#         domain = [("doctor_id", "=", self.id)]
#         return {
#             "type": "ir.actions.act_window",
#             "name": _("Queue Tokens"),
#             "res_model": "clinic.queue.token",
#             "view_mode": "tree,form,kanban",
#             "domain": domain,
#             "target": "current",
#             "context": {"search_default_doctor_id": self.id},
#         }

#     def action_view_waiting_tokens(self):
#         self.ensure_one()
#         if "clinic.queue.token" not in self.env:
#             return {"type": "ir.actions.client", "tag": "display_notification",
#                     "params": {"title": _("Not Available"), "message": _("Queue module is not installed."), "sticky": False}}
#         domain = [("doctor_id", "=", self.id)]
#         if "state" in self.env["clinic.queue.token"]._fields:
#             domain += [("state", "in", ["new", "waiting", "queued", "called"])]
#         return {
#             "type": "ir.actions.act_window",
#             "name": _("Waiting Tokens"),
#             "res_model": "clinic.queue.token",
#             "view_mode": "tree,form,kanban",
#             "domain": domain,
#             "target": "current",
#         }

#     def action_view_in_service_tokens(self):
#         self.ensure_one()
#         if "clinic.queue.token" not in self.env:
#             return {"type": "ir.actions.client", "tag": "display_notification",
#                     "params": {"title": _("Not Available"), "message": _("Queue module is not installed."), "sticky": False}}
#         domain = [("doctor_id", "=", self.id)]
#         if "state" in self.env["clinic.queue.token"]._fields:
#             domain += [("state", "in", ["in_service", "serving"])]
#         return {
#             "type": "ir.actions.act_window",
#             "name": _("In-service Tokens"),
#             "res_model": "clinic.queue.token",
#             "view_mode": "tree,form,kanban",
#             "domain": domain,
#             "target": "current",
#         }
