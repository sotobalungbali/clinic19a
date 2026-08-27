# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/treatment_inherit.py
#
# Purpose
# -------
# Extend clinic.treatment with booking-oriented capabilities:
# - Default duration & buffers for appointments created from the treatment
# - Preferred rooms/resources/channel/policy suggestions
# - Compatibility helpers with booking.resource & booking.room
# - Booking statistics and quick actions
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking     : booking header uses treatment_id
# - booking.room        : preferred rooms for this treatment
# - booking.resource    : preferred resources; compatibility via allowed_treatment_ids on resource
# - booking.channel     : default booking channel suggestion
# - booking.policy      : default booking policy suggestion
# - account/product     : do not redefine pricing/product here; we only reference if present
#
# Notes
# -----
# - All user-facing strings are in English (per project requirement).
# - No hard dependency to sibling modules beyond those declared by clinic_booking.
# - Guards with hasattr / environment checks to avoid crashes if some modules are absent.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class ClinicTreatment(models.Model):
    _inherit = "clinic.treatment"

    # -------------------------------------------------------------------------
    # BOOKING DEFAULTS (safe field names prefixed with 'booking_')
    # -------------------------------------------------------------------------
    booking_default_duration_minutes = fields.Integer(
        string="Default Duration (min)",
        default=60,
        help="Suggested appointment duration when creating a booking from this treatment.",
        tracking=True,
    )
    booking_buffer_before_minutes = fields.Integer(
        string="Buffer Before (min)",
        default=0,
        help="Preparation time reserved before a session of this treatment.",
        tracking=True,
    )
    booking_buffer_after_minutes = fields.Integer(
        string="Buffer After (min)",
        default=0,
        help="Cleaning/reset time reserved after a session of this treatment.",
        tracking=True,
    )

    booking_default_channel_id = fields.Many2one(
        "booking.channel",
        string="Default Booking Channel",
        help="Channel to prefill when making a booking for this treatment.",
        tracking=True,
    )
    booking_default_policy_id = fields.Many2one(
        "booking.policy",
        string="Default Booking Policy",
        help="Policy to prefill when making a booking for this treatment.",
        tracking=True,
    )
    # booking_default_room_ids = fields.Many2many(
    #     "booking.room",
    #     "treatment_booking_room_rel",
    #     "room_id",
    #     string="Preferred Rooms",
    #     help="Rooms commonly used for this treatment. Used as suggestions when booking.",
    # )

    # booking_default_resource_ids = fields.Many2many(
    #     "booking.resource",
    #     "treatment_booking_resource_rel",
    #     "resource_id",
    #     string="Preferred Resources",
    #     help="Devices/tools typically required for this treatment.",
    # )
    # ⬇⬇⬇ FIX: hapus relation/column1/column2 agar tidak ada 'inverse_id' yang disalahpahami
    booking_default_room_ids = fields.Many2many(
        "booking.room",
        string="Preferred Rooms",
        help="Rooms commonly used for this treatment. Used as suggestions when booking.",
    )
    booking_default_resource_ids = fields.Many2many(
        "booking.resource",
        string="Preferred Resources",
        help="Devices/tools typically required for this treatment.",
    )
    # Optional compatibility constraint to certain doctors (kept soft; may not exist in base)
    # allowed_doctor_ids = fields.Many2many(
    #     "clinic.doctor",
    #     "treatment_allowed_doctor_rel",
    #     "doctor_id",
    #     string="Allowed Doctors",
    #     help="If set, only these doctors are considered compatible for this treatment.",
    # )
    allowed_doctor_ids = fields.Many2many(
        "clinic.doctor",
        string="Allowed Doctors",
        help="If set, only these doctors are considered compatible for this treatment.",
    )
    # ⬆⬆⬆ FIX END

    # Contraindications / internal notes for booking staff
    booking_contraindication_note = fields.Text(
        string="Contraindications / Notes",
        help="Internal notes for staff about contraindications, preparation, or special requirements.",
    )

    # -------------------------------------------------------------------------
    # STATS / LINKS
    # -------------------------------------------------------------------------
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_booking_stats",
        help="Number of active bookings referencing this treatment.",
    )
    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_booking",
        help="Most recently created booking for this treatment.",
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("booking_default_duration_minutes", "booking_buffer_before_minutes", "booking_buffer_after_minutes")
    def _check_booking_numbers(self):
        for rec in self:
            if rec.booking_default_duration_minutes is not None and rec.booking_default_duration_minutes <= 0:
                raise ValidationError(_("Default Duration must be greater than 0 minutes."))
            if rec.booking_buffer_before_minutes is not None and rec.booking_buffer_before_minutes < 0:
                raise ValidationError(_("Buffer Before must be 0 or a positive number."))
            if rec.booking_buffer_after_minutes is not None and rec.booking_buffer_after_minutes < 0:
                raise ValidationError(_("Buffer After must be 0 or a positive number."))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_booking_stats(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count([
                ("treatment_id", "=", rec.id),
                ("active", "=", True),
            ])

    def _compute_last_booking(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            last = Booking.search([("treatment_id", "=", rec.id)], order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False

    # -------------------------------------------------------------------------
    # ONCHANGE — KEEP DEFAULTS CONSISTENT
    # -------------------------------------------------------------------------
    @api.onchange("booking_default_resource_ids")
    def _onchange_booking_default_resource_ids(self):
        """
        Auto-clean preferred resources that are marked incompatible with this treatment.
        booking.resource has field 'allowed_treatment_ids'. Keep only resources where:
        - allowed_treatment_ids is empty or includes this treatment.
        """
        for rec in self:
            if not rec.booking_default_resource_ids:
                continue
            cleaned = rec.booking_default_resource_ids
            # Filter by resource.allowed_treatment_ids compatibility if field exists
            cleaned = cleaned.filtered(lambda r: not hasattr(r, "allowed_treatment_ids") or not r.allowed_treatment_ids or rec in r.allowed_treatment_ids)
            if cleaned != rec.booking_default_resource_ids:
                rec.booking_default_resource_ids = cleaned
                return {
                    "warning": {
                        "title": _("Resource Compatibility"),
                        "message": _(
                            "Some preferred resources were removed because they are not compatible with this treatment."
                        ),
                    }
                }
        return {}

    @api.onchange("allowed_doctor_ids")
    def _onchange_allowed_doctor_ids(self):
        """
        Informational: warn if allowed_doctor_ids conflicts with any doctor's own policy,
        but do not hard-block here (validations are done at booking time).
        """
        # Kept as placeholder hook; actual cross-model validation occurs when assigning doctor on booking.
        return {}

    # -------------------------------------------------------------------------
    # HELPERS — APPLY DEFAULTS TO BOOKING
    # -------------------------------------------------------------------------
    def apply_defaults_to_booking_vals(self, vals=None, start_dt=None, end_dt=None, doctor_id=None):
        """
        Return dict of booking values prefilled from this treatment.
        Caller can merge this with manual inputs before create().

        Intended keys:
          - treatment_id, channel_id, policy_id
          - room_id (first preferred room) and resource_ids (all preferred)
          - duration (only as guidance; booking derives end from start + duration)
        """
        self.ensure_one()
        vals = dict(vals or {})
        vals.setdefault("treatment_id", self.id)

        # Prefill channel/policy if not already set
        if self.booking_default_channel_id and not vals.get("channel_id"):
            vals["channel_id"] = self.booking_default_channel_id.id
        if self.booking_default_policy_id and not vals.get("policy_id"):
            vals["policy_id"] = self.booking_default_policy_id.id

        # Preferred room (take the first one as default)
        if self.booking_default_room_ids and not vals.get("room_id"):
            vals["room_id"] = self.booking_default_room_ids[0].id

        # Preferred resources (all)
        if self.booking_default_resource_ids and not vals.get("resource_ids"):
            # Filter by compatibility with selected doctor if given and resource has allowed_doctor_ids
            resources = self.booking_default_resource_ids
            if doctor_id:
                resources = resources.filtered(lambda r: not hasattr(r, "allowed_doctor_ids") or not r.allowed_doctor_ids or doctor_id in r.allowed_doctor_ids.ids)
            vals["resource_ids"] = [(6, 0, resources.ids)]

        # Timing suggestion (if caller wants to compute end from start)
        if start_dt and not vals.get("start_datetime"):
            vals["start_datetime"] = fields.Datetime.to_string(start_dt)
        if end_dt and not vals.get("end_datetime"):
            # If end given, use it. Otherwise, compute from default duration if start provided.
            vals["end_datetime"] = fields.Datetime.to_string(end_dt)
        elif start_dt and self.booking_default_duration_minutes:
            vals["end_datetime"] = fields.Datetime.to_string(
                fields.Datetime.from_string(vals["start_datetime"]) + timedelta(minutes=int(self.booking_default_duration_minutes))
            )

        return vals

    def filter_resources_for_doctor(self, resources, doctor):
        """
        Utility: filter a recordset of booking.resource by doctor compatibility
        and treatment compatibility if those fields exist.
        """
        self.ensure_one()
        if not resources:
            return resources
        res = resources
        # Doctor compatibility
        if doctor and hasattr(resources[:1], "allowed_doctor_ids"):
            res = res.filtered(lambda r: not r.allowed_doctor_ids or doctor in r.allowed_doctor_ids)
        # Treatment compatibility
        if hasattr(resources[:1], "allowed_treatment_ids"):
            res = res.filtered(lambda r: not r.allowed_treatment_ids or self in r.allowed_treatment_ids)
        return res

    # -------------------------------------------------------------------------
    # ACTIONS — NAVIGATION / QUICK BOOK
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        """
        Open bookings filtered by this treatment.
        """
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity,pivot,graph",
            "domain": [("treatment_id", "=", self.id)],
            "context": {
                "default_treatment_id": self.id,
                "default_channel_id": self.booking_default_channel_id.id if self.booking_default_channel_id else False,
                "default_policy_id": self.booking_default_policy_id.id if self.booking_default_policy_id else False,
                "default_room_id": self.booking_default_room_ids[:1].id if self.booking_default_room_ids else False,
                "default_resource_ids": [(6, 0, self.booking_default_resource_ids.ids)] if self.booking_default_resource_ids else False,
            },
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action

    def action_new_booking(self):
        """
        Open a new booking form prefilled with this treatment's defaults.
        """
        self.ensure_one()
        ctx = {
            "default_treatment_id": self.id,
            "default_channel_id": self.booking_default_channel_id.id if self.booking_default_channel_id else False,
            "default_policy_id": self.booking_default_policy_id.id if self.booking_default_policy_id else False,
            "default_room_id": self.booking_default_room_ids[:1].id if self.booking_default_room_ids else False,
            "default_resource_ids": [(6, 0, self.booking_default_resource_ids.ids)] if self.booking_default_resource_ids else False,
        }
        return {
            "name": _("New Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "context": ctx,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # VALIDATION UTILITIES (CAN DOCTOR PERFORM?)
    # -------------------------------------------------------------------------
    def check_doctor_allowed(self, doctor):
        """
        Return (bool, reason) whether a doctor is allowed for this treatment,
        considering both treatment.allowed_doctor_ids and doctor.allowed_treatment_ids (if present).
        """
        self.ensure_one()
        if not doctor:
            return (True, _("No doctor provided — cannot validate."))
        # Treatment-side constraint
        if self.allowed_doctor_ids and doctor not in self.allowed_doctor_ids:
            return (False, _("Doctor is not included in treatment's allowed doctors."))
        # Doctor-side constraint (if model has this field)
        if hasattr(doctor, "allowed_treatment_ids") and doctor.allowed_treatment_ids:
            if self not in doctor.allowed_treatment_ids:
                return (False, _("Treatment is not included in doctor's allowed treatments."))
        return (True, _("Allowed."))
