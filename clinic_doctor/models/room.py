
# -*- coding: utf-8 -*-
# File: clinic_doctor/models/room.py
# Module: clinic_doctor
#
# EXTENDS model: clinic.room  (defined in addon: clinic_queue_room)
#
# Purpose
# -------
# Add doctor- and specialty-centric context to rooms without creating circular dependencies:
# - Allowed specialties for a room
# - Preferred doctors for a room
# - Cross-module counters (devices, queue tokens, availability, appointments)
# - Helper methods & actions for scheduling/orchestration
#
# Notes
# -----
# * All labels/help/messages use English.
# * This file uses _inherit = "clinic.room" to keep clinic.room as the single source of truth.
# * No hard-dep to other ClinicOne addons: integrations are guarded by `"model" in self.env` checks.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicRoom(models.Model):
    _inherit = "clinic.room"

    # -------------------------------------------------------------------------
    # DOCTOR & SPECIALTY CONTEXT
    # -------------------------------------------------------------------------
    allowed_specialty_ids = fields.Many2many(
        "clinic.specialty",
        "clinic_room_specialty_rel",  # ensure unique & consistent relation table name in your DB
        "room_id",
        "specialty_id",
        string="Allowed Specialties",
        help="If set, the room can only be used for these specialties."
    )
    preferred_doctor_ids = fields.Many2many(
        "clinic.doctor",
        "clinic_room_doctor_rel",     # ensure unique & consistent relation table name in your DB
        "room_id",
        "doctor_id",
        string="Preferred Doctors",
        help="Optional list of doctors that primarily use this room."
    )

    # Convenience flags & counters
    is_restricted_by_specialty = fields.Boolean(
        compute="_compute_restriction_flags",
        store=False,
        help="Indicates whether the room is restricted by allowed specialties."
    )
    allowed_specialty_count = fields.Integer(
        compute="_compute_counts_ext",
        store=False,
        help="Number of allowed specialties for this room."
    )
    preferred_doctor_count = fields.Integer(
        compute="_compute_counts_ext",
        store=False,
        help="Number of preferred doctors for this room."
    )

    # -------------------------------------------------------------------------
    # AVAILABILITY & QUEUE (OPTIONAL INTEGRATIONS)
    # -------------------------------------------------------------------------
    next_available_slot = fields.Datetime(
        compute="_compute_next_available_slot_ext",
        store=False,
        help="Next available time slot for this room (server time). Computed from clinic.availability.slot if present."
    )
    open_slot_count = fields.Integer(
        compute="_compute_counts_ext",
        store=False,
        help="Number of open availability slots for this room (if availability model is present)."
    )
    appointment_count = fields.Integer(
        compute="_compute_counts_ext",
        store=False,
        help="Number of appointments scheduled in this room (if appointment model is present)."
    )
    open_appointment_count = fields.Integer(
        compute="_compute_counts_ext",
        store=False,
        help="Number of non-closed appointments in this room (if appointment model is present)."
    )
    device_count = fields.Integer(
        compute="_compute_counts_ext",
        store=False,
        help="Number of devices assigned to this room (if Room Device module is installed)."
    )
    current_queue_token_id = fields.Many2one(
        "clinic.queue.token",
        compute="_compute_queue_token",
        store=False,
        help="Active queue token currently assigned to this room (if queue module is installed)."
    )

    # Optional pricing context (surcharges/routing may be implemented in Pricing addon)
    surcharge_percent = fields.Float(
        default=0.0,
        help="Optional room surcharge percentage applied to services performed in this room."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_restriction_flags(self):
        for rec in self:
            rec.is_restricted_by_specialty = bool(rec.allowed_specialty_ids)

    def _compute_next_available_slot_ext(self):
        now = fields.Datetime.now()
        if "clinic.availability.slot" not in self.env:
            for rec in self:
                rec.next_available_slot = False
            return
        Slot = self.env["clinic.availability.slot"]
        for rec in self:
            slot = Slot.search([
                ("room_id", "=", rec.id),
                ("state", "=", "open"),
                ("start", ">=", now),
            ], order="start asc", limit=1)
            rec.next_available_slot = slot.start if slot else False

    @api.depends(
        "allowed_specialty_ids",
        "preferred_doctor_ids",
    )
    def _compute_counts_ext(self):
        ids = self.ids or []
        # Base M2M counts
        spec_map = {rid: 0 for rid in ids}
        doc_map = {rid: 0 for rid in ids}
        if ids:
            # allowed specialties
            self.env.cr.execute("""
                SELECT room_id, COUNT(*)
                  FROM clinic_room_specialty_rel
                 WHERE room_id = ANY(%s)
              GROUP BY room_id
            """, [ids])
            for rid, cnt in self.env.cr.fetchall():
                spec_map[rid] = cnt
            # preferred doctors
            self.env.cr.execute("""
                SELECT room_id, COUNT(*)
                  FROM clinic_room_doctor_rel
                 WHERE room_id = ANY(%s)
              GROUP BY room_id
            """, [ids])
            for rid, cnt in self.env.cr.fetchall():
                doc_map[rid] = cnt

        # Availability (optional)
        open_slot_map = {rid: 0 for rid in ids}
        if ids and "clinic.availability.slot" in self.env:
            groups = self.env["clinic.availability.slot"].read_group(
                [("room_id", "in", ids), ("state", "=", "open")],
                ["room_id"],
                ["room_id"],
            )
            open_slot_map.update({g["room_id"][0]: g["room_id_count"] for g in groups})

        # Appointments (optional)
        app_all_map = {rid: 0 for rid in ids}
        app_open_map = {rid: 0 for rid in ids}
        if ids and "clinic.appointment" in self.env:
            App = self.env["clinic.appointment"]
            groups_all = App.read_group(
                [("room_id", "in", ids)],
                ["room_id"],
                ["room_id"],
            )
            app_all_map.update({g["room_id"][0]: g["room_id_count"] for g in groups_all})
            groups_open = App.read_group(
                [("room_id", "in", ids), ("state", "not in", ["canceled", "done", "no_show"])],
                ["room_id"],
                ["room_id"],
            )
            app_open_map.update({g["room_id"][0]: g["room_id_count"] for g in groups_open})

        # Devices (optional: clinic.device or clinic.room.device.line)
        dev_map = {rid: 0 for rid in ids}
        if ids and "clinic.device" in self.env:
            groups_dev = self.env["clinic.device"].read_group(
                [("room_id", "in", ids)],
                ["room_id"],
                ["room_id"],
            )
            dev_map.update({g["room_id"][0]: g["room_id_count"] for g in groups_dev})
        elif ids and "clinic.room.device.line" in self.env:
            groups_dev = self.env["clinic.room.device.line"].read_group(
                [("room_id", "in", ids)],
                ["room_id"],
                ["room_id"],
            )
            dev_map.update({g["room_id"][0]: g["room_id_count"] for g in groups_dev})

        for rec in self:
            rid = rec.id
            rec.allowed_specialty_count = spec_map.get(rid, 0)
            rec.preferred_doctor_count = doc_map.get(rid, 0)
            rec.open_slot_count = open_slot_map.get(rid, 0)
            rec.appointment_count = app_all_map.get(rid, 0)
            rec.open_appointment_count = app_open_map.get(rid, 0)
            rec.device_count = dev_map.get(rid, 0)

    def _compute_queue_token(self):
        # Current active queue token (optional integration)
        if "clinic.queue.token" not in self.env:
            for rec in self:
                rec.current_queue_token_id = False
            return
        Token = self.env["clinic.queue.token"]
        now = fields.Datetime.now()
        for rec in self:
            token = Token.search([
                ("room_id", "=", rec.id),
                ("state", "in", ["waiting", "called", "in_service"]),
                ("scheduled_start", "<=", now),
            ], order="write_date desc", limit=1)
            rec.current_queue_token_id = token.id if token else False

    # -------------------------------------------------------------------------
    # CONSTRAINTS (POLICY)
    # -------------------------------------------------------------------------
    @api.constrains("preferred_doctor_ids", "allowed_specialty_ids")
    def _check_preferred_doctors_vs_allowed_specialties(self):
        """
        Policy: When allowed_specialty_ids is set, each preferred doctor must match at least one allowed specialty.
        Relax/remove if your business allows wider flexibility.
        """
        for rec in self:
            if rec.allowed_specialty_ids and rec.preferred_doctor_ids:
                allowed = set(rec.allowed_specialty_ids.ids)
                for doc in rec.preferred_doctor_ids:
                    if not allowed.intersection(set(doc.specialty_ids.ids)):
                        raise ValidationError(_(
                            "Preferred doctor %(doc)s does not match any of the allowed specialties "
                            "configured for room %(room)s.",
                            doc=doc.display_name,
                            room=rec.display_name,
                        ))

    # -------------------------------------------------------------------------
    # SCHEDULING HELPERS (USED BY APPOINTMENT/TREATMENT/BOOKING MODULES)
    # -------------------------------------------------------------------------
    def check_room_eligibility(self, doctor=None, specialty=None, start_dt=None, end_dt=None):
        """
        Business helper to validate if this room can be used under given constraints.

        :param doctor: clinic.doctor record (optional)
        :param specialty: clinic.specialty record (optional)
        :param start_dt: datetime (server-tz aware) — optional
        :param end_dt: datetime (server-tz aware) — optional
        :return: dict {'eligible': bool, 'reason': str or False}
        """
        self.ensure_one()
        # Specialty restriction
        if specialty and self.allowed_specialty_ids:
            if specialty.id not in self.allowed_specialty_ids.ids:
                return {"eligible": False, "reason": _("Room is restricted to specific specialties.")}
        # Preferred doctors hint (not a hard block; make it soft recommendation)
        if doctor and self.preferred_doctor_ids and doctor.id not in self.preferred_doctor_ids.ids:
            # soft warning; still eligible
            return {"eligible": True, "reason": _("Doctor is not in the preferred list for this room.")}
        # Slot availability (optional)
        if start_dt and end_dt and "clinic.availability.slot" in self.env:
            Slot = self.env["clinic.availability.slot"]
            # Check if an open slot covers the range; adjust logic if your slot model differs
            overlapping = Slot.search_count([
                ("room_id", "=", self.id),
                ("state", "=", "open"),
                ("start", "<=", start_dt),
                ("end", ">=", end_dt),
            ], limit=1)
            if not overlapping:
                return {"eligible": False, "reason": _("No open availability slot covers the requested time.")}
        return {"eligible": True, "reason": False}

    # -------------------------------------------------------------------------
    # ACTIONS (UI HELPERS)
    # -------------------------------------------------------------------------
    def action_view_allowed_specialties(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Allowed Specialties"),
            "res_model": "clinic.specialty",
            "view_mode": "tree,form,kanban",
            "domain": [("id", "in", self.allowed_specialty_ids.ids)],
            "target": "current",
        }

    def action_view_preferred_doctors(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Preferred Doctors"),
            "res_model": "clinic.doctor",
            "view_mode": "tree,form,kanban,calendar,pivot,graph",
            "domain": [("id", "in", self.preferred_doctor_ids.ids)],
            "target": "current",
        }

    def action_view_availability(self):
        self.ensure_one()
        if "clinic.availability.slot" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Availability module is not installed."),
                           "sticky": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Availability"),
            "res_model": "clinic.availability.slot",
            "view_mode": "calendar,tree,form",
            "domain": [("room_id", "=", self.id)],
            "context": {"default_room_id": self.id},
            "target": "current",
        }

    def action_view_appointments(self):
        self.ensure_one()
        if "clinic.appointment" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Appointment module is not installed."),
                           "sticky": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Appointments"),
            "res_model": "clinic.appointment",
            "view_mode": "calendar,tree,form,pivot,graph",
            "domain": [("room_id", "=", self.id)],
            "context": {"default_room_id": self.id},
            "target": "current",
        }

    def action_view_devices(self):
        """Open assigned devices if the device module is installed."""
        self.ensure_one()
        if "clinic.device" in self.env:
            return {
                "type": "ir.actions.act_window",
                "name": _("Room Devices"),
                "res_model": "clinic.device",
                "view_mode": "tree,form",
                "domain": [("room_id", "=", self.id)],
                "target": "current",
            }
        if "clinic.room.device.line" in self.env:
            return {
                "type": "ir.actions.act_window",
                "name": _("Room Devices"),
                "res_model": "clinic.room.device.line",
                "view_mode": "tree,form",
                "domain": [("room_id", "=", self.id)],
                "target": "current",
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Not Available"),
                       "message": _("Room Device module is not installed."),
                       "sticky": False},
        }

    def action_view_queue(self):
        """Open queue tokens for this room, if queue module is available."""
        self.ensure_one()
        if "clinic.queue.token" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Queue module is not installed."),
                           "sticky": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Queue Tokens"),
            "res_model": "clinic.queue.token",
            "view_mode": "tree,form,kanban",
            "domain": [("room_id", "=", self.id)],
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # INTEGRATION HOOKS (for bridge modules to override)
    # -------------------------------------------------------------------------
    def _post_create_room_hook(self):
        """
        Hook for bridge modules (pricing/maintenance/marketing) after room creation.
        """
        return True

    def _post_write_room_hook(self, vals):
        """
        Hook for bridge modules (pricing caches, availability recompute) on room update.
        """
        return True

    def _pre_unlink_room_hook(self):
        """
        Hook for bridge modules to cleanup downstream references before deletion.
        """
        return True

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES (ONLY TO FIRE HOOKS; CORE FIELDS LIVE IN clinic_queue_room)
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._post_create_room_hook()
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._post_write_room_hook(vals)
        return res

    def unlink(self):
        for rec in self:
            rec._pre_unlink_room_hook()
        return super().unlink()

    # -------------------------------------------------------------------------
    # DISPLAY (no override of name_get to respect base behavior, but add helper)
    # -------------------------------------------------------------------------
    def display_with_code(self):
        """Helper label 'Name [Code]' if 'code' exists on the base model."""
        self.ensure_one()
        name = getattr(self, "name", _("Unnamed"))
        code = getattr(self, "code", False)
        return f"{name} [{code}]" if code else name
