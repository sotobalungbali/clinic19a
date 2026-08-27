
# -*- coding: utf-8 -*-
# File: clinic_doctor/models/appointment.py
# Module: clinic_doctor
#
# ClinicOne — Appointment (Odoo 19 CE ready)
#
# Purpose
# -------
# End-to-end appointment lifecycle for medical aesthetics clinics:
# - Draft → Confirmed → Checked In → In Treatment → Done
# - Terminal branches: Canceled, No-show
# - Works with doctor availability slots, rooms, specialties, queue, billing, treatment, portal
#
# Design
# ------
# * No hard depends on non-core modules. Optional integrations guarded by `"model" in self.env`
#   and field presence checks (e.g., `"slot_id" in self.env['clinic.appointment']._fields`).
# * Uses res.partner as mandatory patient identity; `clinic.patient` is optional.
# * Datetimes stored in UTC; display can use user's or doctor's TZ in views.
#
# Notes
# -----
# - All field labels/help/messages are in English (product requirement).
# - For slot capacity accounting, this model links to `clinic.availability.slot` via `slot_id`
#   (if present). Slot computes reserved/available seats by counting non-terminal appointments.

from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


APPT_STATES = [
    ("draft", "Draft"),
    ("confirmed", "Confirmed"),
    ("checked_in", "Checked In"),
    ("in_treatment", "In Treatment"),
    ("done", "Done"),
    ("no_show", "No-show"),
    ("canceled", "Canceled"),
]

APPT_TYPES = [
    ("consultation", "Consultation"),
    ("treatment", "Treatment"),
    ("follow_up", "Follow-up"),
    ("other", "Other"),
]

BOOKING_CHANNELS = [
    ("walk_in", "Walk-in"),
    ("phone", "Phone"),
    ("portal", "Portal"),
    ("referral", "Referral"),
    ("other", "Other"),
]


class ClinicAppointment(models.Model):
    _name = "clinic.appointment"
    _description = "Clinic Appointment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start asc, doctor_id, id"

    # -------------------------------------------------------------------------
    # IDENTITY & SCOPE
    # -------------------------------------------------------------------------
    name = fields.Char(
        tracking=True,
        index=True,
        help="Appointment reference. If empty, a sequence will be assigned on creation."
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company to which this appointment belongs."
    )
    state = fields.Selection(
        APPT_STATES,
        default="draft",
        index=True,
        tracking=True,
        help="Lifecycle state of the appointment."
    )
    appointment_type = fields.Selection(
        APPT_TYPES,
        default="consultation",
        index=True,
        help="Type/category of the appointment."
    )
    booking_channel = fields.Selection(
        BOOKING_CHANNELS,
        default="other",
        help="How this appointment was created (walk-in, phone, portal, etc.)."
    )
    color = fields.Integer(
        help="Color index for calendar/kanban visualization."
    )

    # -------------------------------------------------------------------------
    # LINKED ENTITIES
    # -------------------------------------------------------------------------
    doctor_id = fields.Many2one(
        "clinic.doctor",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Doctor in charge of this appointment."
    )
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Patient contact for this appointment."
    )
    # patient_id = fields.Many2one(
    #     "clinic.patient",
    #     ondelete="set null",
    #     index=True,
    #     help="Linked patient if Clinic Patient module is installed."
    # )
    slot_id = fields.Many2one(
        "clinic.availability.slot",
        ondelete="set null",
        index=True,
        help="Availability slot used for this appointment (if created from a slot)."
    )
    room_id = fields.Many2one(
        "clinic.room",
        ondelete="set null",
        index=True,
        help="Room reserved for this appointment (if onsite)."
    )
    specialty_id = fields.Many2one(
        "clinic.specialty",
        ondelete="set null",
        help="Specialty context for filtering, pricing, and routing."
    )
    telemedicine = fields.Boolean(
        default=False,
        help="If enabled, this appointment is telemedicine (virtual)."
    )

    # Optional downstream links (created by other modules)
    treatment_session_id = fields.Many2one(
        "clinic.procedure.session",
        ondelete="set null",
        help="Treatment session created from this appointment (if available)."
    )
    invoice_id = fields.Many2one(
        "account.move",
        ondelete="set null",
        help="Invoice linked to this appointment (if Billing/Accounting is installed)."
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        ondelete="set null",
        help="Sales Order linked to this appointment (if eCommerce/Sales is installed)."
    )
    queue_token_id = fields.Many2one(
        "clinic.queue.token",
        ondelete="set null",
        help="Queue token created/linked at check-in (if Queue module is installed)."
    )

    # -------------------------------------------------------------------------
    # TIME WINDOW (UTC storage)
    # -------------------------------------------------------------------------
    start = fields.Datetime(
        required=True,
        index=True,
        tracking=True,
        help="Appointment start (stored in UTC)."
    )
    end = fields.Datetime(
        required=True,
        index=True,
        tracking=True,
        help="Appointment end (stored in UTC). Must be greater than start."
    )
    duration_minutes = fields.Integer(
        compute="_compute_duration",
        store=False,
        help="Computed duration in minutes."
    )

    # UX helpers
    notes = fields.Text(
        help="Internal notes for the staff."
    )
    reason = fields.Char(
        help="Short reason for the visit (visible to staff)."
    )
    need_reschedule = fields.Boolean(
        default=False,
        help="Flag to indicate the appointment requires rescheduling (used by leave policies, etc.)."
    )

    # Policies
    allow_overlap = fields.Boolean(
        default=False,
        help="Allow overlapping appointments for the same doctor in this time window."
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _sql_constraints = [
        ("check_start_end", "CHECK(start < end)", "End time must be greater than start time."),
    ]

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_duration(self):
        for rec in self:
            if rec.start and rec.end:
                delta = rec.end - rec.start
                rec.duration_minutes = int(delta.total_seconds() // 60)
            else:
                rec.duration_minutes = 0

    # -------------------------------------------------------------------------
    # ONCHANGES
    # -------------------------------------------------------------------------
    @api.onchange("slot_id")
    def _onchange_slot_id(self):
        """Auto-fill fields when a slot is selected."""
        for rec in self:
            s = rec.slot_id
            if not s:
                continue
            rec.doctor_id = s.doctor_id.id
            rec.start = s.start
            rec.end = s.end
            if "room_id" in s._fields:
                rec.room_id = s.room_id.id
            if "specialty_id" in s._fields:
                rec.specialty_id = s.specialty_id.id
            if "telemedicine" in s._fields:
                rec.telemedicine = bool(s.telemedicine)

    @api.onchange("doctor_id")
    def _onchange_doctor_id(self):
        """Pick a default room or specialty from the doctor if missing."""
        for rec in self:
            if rec.doctor_id and not rec.room_id and "default_room_id" in rec.doctor_id._fields:
                rec.room_id = rec.doctor_id.default_room_id.id or False

    # -------------------------------------------------------------------------
    # VALIDATIONS (POLICY)
    # -------------------------------------------------------------------------
    @api.constrains("doctor_id", "start", "end", "slot_id", "room_id", "specialty_id", "telemedicine", "company_id")
    def _check_policy(self):
        Param = self.env["ir.config_parameter"].sudo()
        prevent_overlap = Param.get_param("clinic_doctor.prevent_doctor_overlap", "True") == "True"
        enforce_room_policy = Param.get_param("clinic_doctor.enforce_room_specialty", "True") == "True"

        for rec in self:
            # Room specialty policy
            if enforce_room_policy and rec.room_id and "allowed_specialty_ids" in rec.room_id._fields:
                allowed = rec.room_id.allowed_specialty_ids
                if allowed and rec.specialty_id and rec.specialty_id not in allowed:
                    raise ValidationError(_(
                        "Specialty '%(spec)s' is not allowed in room '%(room)s'.",
                        spec=rec.specialty_id.display_name,
                        room=rec.room_id.display_name,
                    ))
            # Slot alignment
            if rec.slot_id:
                s = rec.slot_id
                if s.doctor_id.id != rec.doctor_id.id:
                    raise ValidationError(_("Selected slot belongs to a different doctor."))
                if s.start != rec.start or s.end != rec.end:
                    raise ValidationError(_("Appointment window must match the selected slot window."))
                if "room_id" in s._fields and s.room_id and rec.room_id and s.room_id.id != rec.room_id.id:
                    raise ValidationError(_("Appointment room must match the selected slot room."))
                if "telemedicine" in s._fields and bool(s.telemedicine) != bool(rec.telemedicine):
                    # soft policy — warn via onchange would be nicer; keep strict here for data consistency
                    raise ValidationError(_("Appointment telemedicine flag must match the selected slot."))

            # Doctor leave overlap (skip if leave model absent)
            if "clinic.doctor.leave" in self.env and rec.start and rec.end:
                has_leave = self.env["clinic.doctor.leave"].search_count([
                    ("doctor_id", "=", rec.doctor_id.id),
                    ("state", "=", "approve"),
                    ("date_from", "<", rec.end),
                    ("date_to", ">", rec.start),
                ], limit=1)
                if has_leave:
                    raise ValidationError(_("Appointment overlaps an approved doctor leave."))

            # Overlap with other appointments of the same doctor
            if prevent_overlap and not rec.allow_overlap and rec.start and rec.end:
                dom = [
                    ("id", "!=", rec.id),
                    ("doctor_id", "=", rec.doctor_id.id),
                    ("state", "not in", ["canceled", "no_show"]),
                    ("start", "<", rec.end),
                    ("end", ">", rec.start),
                ]
                if self.search_count(dom):
                    raise ValidationError(_("Overlapping appointments are not allowed for this doctor."))

    # -------------------------------------------------------------------------
    # CREATE/WRITE/DELETE OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_doctor.seq_clinic_appointment", raise_if_not_found=False)
        records = self.browse()
        for vals in vals_list:
            # Assign sequence if empty
            if not vals.get("name"):
                if seq:
                    vals["name"] = seq._next()
                else:
                    vals["name"] = self.env["ir.sequence"].next_by_code("clinic.appointment") or "/"

            # Default specialty/room from slot if present (safety for RPC/API creations)
            slot_id = vals.get("slot_id")
            if slot_id:
                Slot = self.env["clinic.availability.slot"].browse(slot_id)
                if Slot.exists():
                    vals.setdefault("start", Slot.start)
                    vals.setdefault("end", Slot.end)
                    vals.setdefault("doctor_id", Slot.doctor_id.id)
                    if "room_id" in Slot._fields and Slot.room_id:
                        vals.setdefault("room_id", Slot.room_id.id)
                    if "specialty_id" in Slot._fields and Slot.specialty_id:
                        vals.setdefault("specialty_id", Slot.specialty_id.id)
                    if "telemedicine" in Slot._fields:
                        vals.setdefault("telemedicine", bool(Slot.telemedicine))

            # Multi-company guard
            if vals.get("doctor_id") and not vals.get("company_id"):
                vals["company_id"] = self.env["clinic.doctor"].browse(vals["doctor_id"]).company_id.id

            record = super(ClinicAppointment, self).create(vals)
            records |= record

            # Auto-subscribe patient & doctor to chatter
            subs = []
            if record.partner_id:
                subs.append(record.partner_id.id)
            if record.doctor_id and record.doctor_id.partner_id:
                subs.append(record.doctor_id.partner_id.id)
            if subs:
                record.message_subscribe(partner_ids=list(set(subs)))

            # Hooks for other modules
            record._post_create_integrations_hook()

        return records

    def write(self, vals):
        # When changing key fields, we may need to re-check policies or clear flags
        res = super().write(vals)
        for rec in self:
            # If rescheduled, clear no-show/reschedule flags and notify slot
            if any(k in vals for k in ("start", "end", "slot_id", "room_id", "doctor_id")):
                rec.need_reschedule = False
            rec._post_write_integrations_hook(vals)
        return res

    def unlink(self):
        # Prevent deleting non-terminal appointments; use cancel instead
        non_terminal = self.filtered(lambda a: a.state not in ("canceled", "done", "no_show"))
        if non_terminal:
            raise UserError(_("You cannot delete non-terminal appointments. Cancel them instead."))
        for rec in self:
            rec._pre_unlink_integrations_hook()
        return super().unlink()

    # -------------------------------------------------------------------------
    # STATE MACHINE — ACTIONS
    # -------------------------------------------------------------------------
    def _check_slot_capacity_or_raise(self):
        """
        Ensure that the selected slot has available seats for a new/confirmed appointment.
        Only enforced if slot_id is set and slot model is installed.
        """
        for rec in self:
            s = rec.slot_id
            if not s:
                continue
            # The slot model computes available seats from appointment counts + manual_reserved.
            s.invalidate_recordset()  # refresh computed values
            if hasattr(s, "available_seats") and s.available_seats <= 0:
                raise UserError(_("Selected slot has no available seats."))

    def _check_lead_time_or_raise(self):
        """
        Enforce doctor's lead-time policy on confirmation if configured.
        """
        Param = self.env["ir.config_parameter"].sudo()
        enforce = Param.get_param("clinic_doctor.enforce_lead_time", "True") == "True"
        if not enforce:
            return
        now = fields.Datetime.now()
        for rec in self:
            if not rec.start or not rec.doctor_id:
                continue
            # Minimum lead time (hours)
            min_h = getattr(rec.doctor_id, "min_lead_time_hours", 0) or 0
            if min_h and rec.start < (now + timedelta(hours=min_h)):
                raise UserError(_("This appointment violates the doctor's minimum lead time."))
            # Maximum lead time (days)
            max_d = getattr(rec.doctor_id, "max_lead_time_days", 0) or 0
            if max_d and rec.start > (now + timedelta(days=max_d)):
                raise UserError(_("This appointment exceeds the doctor's maximum lead-time window."))

    def action_confirm(self):
        for rec in self:
            if rec.state not in ("draft", "confirmed"):
                # idempotent: allow reconfirm
                continue
            rec._check_slot_capacity_or_raise()
            rec._check_lead_time_or_raise()
            rec.state = "confirmed"
            rec.message_post(body=_("Appointment confirmed."))
            rec._post_confirm_integrations_hook()
        return True

    def action_check_in(self):
        """
        Move to Checked In and optionally create/link a queue token.
        """
        for rec in self:
            if rec.state not in ("confirmed", "checked_in"):
                raise UserError(_("Only confirmed appointments can be checked in."))
            rec.state = "checked_in"
            rec.message_post(body=_("Patient checked in."))

            # Create queue token if queue module is available and no token linked yet
            if "clinic.queue.token" in self.env and not rec.queue_token_id:
                token_vals = {
                    "name": False,  # let sequence assign
                    "company_id": rec.company_id.id,
                    "partner_id": rec.partner_id.id,
                    "doctor_id": rec.doctor_id.id,
                    "room_id": rec.room_id.id if rec.room_id else False,
                    "scheduled_start": rec.start,
                    "scheduled_end": rec.end,
                    "source": "appointment",
                }
                Token = self.env["clinic.queue.token"].sudo()
                token = Token.create(token_vals)
                rec.queue_token_id = token.id

            rec._post_check_in_integrations_hook()
        return True

    def action_start_treatment(self):
        for rec in self:
            if rec.state not in ("checked_in", "in_treatment"):
                raise UserError(_("Appointment must be checked in before starting treatment."))
            rec.state = "in_treatment"
            rec.message_post(body=_("Treatment started."))
            rec._post_start_treatment_integrations_hook()
        return True

    def action_done(self):
        """
        Finish the appointment. Optionally create a treatment session and/or an invoice
        via hooks implemented by other modules.
        """
        for rec in self:
            if rec.state not in ("in_treatment", "confirmed", "checked_in"):
                raise UserError(_("Only an active appointment can be marked as done."))
            rec.state = "done"
            rec.message_post(body=_("Appointment marked as done."))
            rec._post_done_integrations_hook()
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "canceled":
                continue
            rec.state = "canceled"
            if reason:
                rec.message_post(body=_("Appointment canceled: %s") % reason)
            else:
                rec.message_post(body=_("Appointment canceled."))
            rec._post_cancel_integrations_hook()
        return True

    def action_mark_no_show(self):
        for rec in self:
            if rec.state in ("done", "canceled", "no_show"):
                continue
            rec.state = "no_show"
            rec.message_post(body=_("Patient did not show up."))
            rec._post_no_show_integrations_hook()
        return True

    def action_reschedule(self, new_start, new_end, new_slot_id=False, new_room_id=False):
        """
        Reschedule to a new window (and optionally a new slot/room). Intended to be called
        by wizards or server actions.
        """
        for rec in self:
            if rec.state in ("done", "canceled"):
                raise UserError(_("You cannot reschedule a completed or canceled appointment."))
            vals = {
                "start": new_start,
                "end": new_end,
                "need_reschedule": False,
            }
            if new_slot_id:
                vals["slot_id"] = new_slot_id
            if new_room_id:
                vals["room_id"] = new_room_id
            rec.write(vals)
            rec.message_post(body=_("Appointment rescheduled."))
        return True

    # -------------------------------------------------------------------------
    # HOOKS FOR BRIDGE MODULES (override in child modules)
    # -------------------------------------------------------------------------
    def _post_create_integrations_hook(self):
        """
        Example override points:
          - clinic_marketing: create UTM/analytics entries
          - clinic_booking: sync portal reservation
          - clinic_finance: pre-authorize payments or deposit
        """
        return True

    def _post_write_integrations_hook(self, vals):
        """
        Example:
          - Invalidate pricing/availability caches
          - Notify external channels (webhooks)
        """
        return True

    def _pre_unlink_integrations_hook(self):
        """
        Example:
          - Cleanup downstream references (webhooks, external IDs)
        """
        return True

    def _post_confirm_integrations_hook(self):
        """
        Example:
          - Reserve inventory (consumables) for upcoming treatment
          - Send confirmation emails/SMS (mail templates)
        """
        return True

    def _post_check_in_integrations_hook(self):
        """
        Example:
          - Trigger room display (kiosk) update
          - Notify doctor device (push)
        """
        return True

    def _post_start_treatment_integrations_hook(self):
        """
        Example:
          - Create treatment session shell if not exists
        """
        # If treatment module is available and no session yet, create one
        if "clinic.procedure.session" in self.env:
            for rec in self.filtered(lambda r: not r.treatment_session_id):
                vals = {
                    "name": _("Session for %s") % (rec.name or rec.partner_id.display_name),
                    "doctor_id": rec.doctor_id.id,
                    "partner_id": rec.partner_id.id,
                    "appointment_id": rec.id if "appointment_id" in self.env["clinic.procedure.session"]._fields else False,
                    "specialty_id": rec.specialty_id.id if rec.specialty_id else False,
                    "room_id": rec.room_id.id if rec.room_id and "room_id" in self.env["clinic.procedure.session"]._fields else False,
                    "company_id": rec.company_id.id,
                    "state": "in_progress" if "state" in self.env["clinic.procedure.session"]._fields else False,
                }
                sess = self.env["clinic.procedure.session"].sudo().create(vals)
                rec.treatment_session_id = sess.id
        return True

    def _post_done_integrations_hook(self):
        """
        Example:
          - Finalize treatment session
          - Create invoice / post journal entries
          - Award membership points
        """
        for rec in self:
            # Close treatment session (if model/field exists)
            if rec.treatment_session_id and "state" in rec.treatment_session_id._fields:
                rec.treatment_session_id.sudo().write({"state": "done"})
            # Auto-invoice (demo behavior) if billing is present and no invoice yet
            if not rec.invoice_id and "account.move" in self.env:
                Param = self.env["ir.config_parameter"].sudo()
                auto_invoice = Param.get_param("clinic_doctor.auto_invoice_on_done", "False") == "True"
                if auto_invoice:
                    inv = self._create_simple_invoice_for_appointment(rec)
                    if inv:
                        rec.invoice_id = inv.id
        return True

    def _post_cancel_integrations_hook(self):
        """
        Example:
          - Release inventory
          - Return deposit, notify patient
        """
        return True

    def _post_no_show_integrations_hook(self):
        """
        Example:
          - Apply no-show fee
          - Update KPIs
        """
        return True

    # -------------------------------------------------------------------------
    # BILLING HELPERS (DEMO/SIMPLE)
    # -------------------------------------------------------------------------
    def _create_simple_invoice_for_appointment(self, appt):
        """
        Minimal example to create an invoice with a single line referencing the appointment.
        Real implementations should use Pricing/Package modules instead.
        """
        if "account.move" not in self.env:
            return False
        if not appt.partner_id:
            return False

        # Pick a default product (fallback) if pricing module not present
        product = None
        if "clinic.treatment.pricelist.item" in self.env:
            item = self.env["clinic.treatment.pricelist.item"].search(
                [("specialty_id", "=", appt.specialty_id.id)] if appt.specialty_id else [],
                limit=1
            )
            product = item.product_id if item and "product_id" in item._fields else None

        if not product and "product.product" in self.env:
            product = self.env["product.product"].search([], limit=1)

        if not product:
            return False  # cannot create invoice without a product

        Move = self.env["account.move"].sudo()
        Line = self.env["account.move.line"].sudo()

        move_vals = {
            "move_type": "out_invoice",
            "partner_id": appt.partner_id.id,
            "invoice_origin": appt.name,
            "invoice_payment_reference": appt.name,
            "invoice_date": fields.Date.context_today(self),
            "company_id": appt.company_id.id,
            "invoice_line_ids": [],
        }
        inv = Move.create(move_vals)
        Line.create({
            "move_id": inv.id,
            "product_id": product.id,
            "name": _("Appointment: %s") % (appt.name or appt.display_name),
            "quantity": 1.0,
            "price_unit": product.lst_price if "lst_price" in product._fields else 0.0,
            "tax_ids": [(6, 0, product.taxes_id.ids if "taxes_id" in product._fields else [])],
        })
        return inv

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            doc = rec.doctor_id.display_name if rec.doctor_id else _("Doctor")
            pat = rec.partner_id.display_name if rec.partner_id else _("Patient")
            when = fields.Datetime.to_string(rec.start) if rec.start else "?"
            label = f"{rec.name or '/'} — {doc} × {pat} — {when}"
            res.append((rec.id, label))
        return res

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=80):
        args = args or []
        domain = []
        if name:
            domain = ["|", ("name", operator, name), ("reason", operator, name)]
        recs = self.search(domain + args, limit=limit)
        return recs.name_get()

    # dari patient_link.py \\\///
    @api.onchange("partner_id")
    def _onchange_partner_bind_patient(self):
        """
        When a partner is chosen, bind the patient record automatically if:
          - There is exactly one patient with that partner
          - Or system parameter allows auto-create when none exists
        """
        Param = self.env["ir.config_parameter"].sudo()
        auto_create = Param.get_param("clinic_doctor.auto_create_patient_on_appointment", "False") == "True"

        for rec in self:
            if not rec.partner_id:
                rec.patient_id = False
                continue
            Patient = self.env["clinic.patient"]
            candidates = Patient.search([("partner_id", "=", rec.partner_id.id)], limit=2)
            if len(candidates) == 1:
                rec.patient_id = candidates.id
            elif len(candidates) == 0 and auto_create:
                # Create patient shell linked to this partner
                patient = Patient.create({
                    "name": rec.partner_id.name,
                    "partner_id": rec.partner_id.id,
                    "company_id": rec.company_id.id if rec.company_id else self.env.company.id,
                })
                rec.patient_id = patient.id
            else:
                # multiple candidates — do nothing, let user choose
                rec.patient_id = False

    @api.constrains("partner_id", "patient_id")
    def _check_partner_patient_consistency(self):
        """
        Ensure appointment.partner_id matches patient.partner_id (if patient is set).
        """
        for rec in self:
            if rec.patient_id and rec.partner_id and rec.patient_id.partner_id and rec.patient_id.partner_id != rec.partner_id:
                raise ValidationError(_("Appointment contact does not match the selected patient."))
    # dari patient_link.py ///\\\

# -*- coding: utf-8 -*-
# File: clinic_doctor/models/availability.py
# Module: clinic_doctor
#
# ClinicOne — Availability Slot (Odoo 19 CE ready)
#
# Purpose
# -------
# Concrete, bookable time window for a doctor (optionally bound to a room & specialty).
# Supports:
# - Capacity per slot (+ manual reserved seats)
# - State machine (open/reserved/booked/blocked/closed)
# - Optional buffers (before/after) and telemedicine flag
# - Cross-module counters (appointments, queue, devices) via guarded env checks
# - Helper actions (create appointment, block/unblock, reserve/release)
#
# Notes
# -----
# * All labels/help/messages use English.
# * Multi-company aware.
# * Timezone display uses Doctor's user tz (or company tz) for UX fields.
# * Designed to be generated from clinic.schedule.rule, but can be created ad-hoc.

from datetime import timedelta
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


SLOT_STATES = [
    ("open", "Open"),
    ("reserved", "Reserved"),   # partially or fully reserved (manual or via draft appointment)
    ("booked", "Booked"),       # fully booked (capacity reached)
    ("blocked", "Blocked"),     # intentionally blocked (maintenance/cleanup/hold)
    ("closed", "Closed"),       # past/archived or administratively closed
]


class ClinicAvailabilitySlot(models.Model):
    _name = "clinic.availability.slot"
    _description = "Availability Slot"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start asc, doctor_id, id"
    _rec_name = "display_name"

    # -------------------------------------------------------------------------
    # CORE LINKS & SCOPE
    # -------------------------------------------------------------------------
    doctor_id = fields.Many2one(
        "clinic.doctor",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
        help="Doctor available for this time window."
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company to which this slot belongs."
    )

    # Optional context links
    room_id = fields.Many2one(
        "clinic.room",
        ondelete="set null",
        index=True,
        help="Room associated with this slot (when onsite)."
    )
    specialty_id = fields.Many2one(
        "clinic.specialty",
        ondelete="set null",
        index=True,
        help="Specialty context used for filtering and eligibility checks."
    )

    # Window & properties (UTC storage)
    start = fields.Datetime(
        required=True,
        index=True,
        tracking=True,
        help="Slot start time (stored in UTC)."
    )
    end = fields.Datetime(
        required=True,
        index=True,
        tracking=True,
        help="Slot end time (stored in UTC)."
    )
    duration_minutes = fields.Integer(
        compute="_compute_duration",
        store=False,
        help="Duration in minutes (computed from start/end)."
    )

    state = fields.Selection(
        SLOT_STATES,
        default="open",
        index=True,
        tracking=True,
        help="Lifecycle state of the slot."
    )
    capacity = fields.Integer(
        default=1,
        tracking=True,
        help="Maximum number of concurrent patients allowed in this slot."
    )
    # manual reservation seats (independent from appointments, used when appointment module is absent)
    manual_reserved = fields.Integer(
        default=0,
        help="Manually reserved seats in this slot (in addition to appointment reservations)."
    )

    # Optional buffers & flags (aligns with schedule_rule and other modules)
    buffer_before_min = fields.Integer(
        default=0,
        help="Preparation buffer (minutes) before the slot."
    )
    buffer_after_min = fields.Integer(
        default=0,
        help="Cleanup buffer (minutes) after the slot."
    )
    telemedicine = fields.Boolean(
        default=False,
        help="If enabled, this slot is dedicated to telemedicine (virtual) sessions."
    )

    # Reason for blocking (when state = blocked)
    block_reason = fields.Char(
        help="Optional reason/explanation when this slot is blocked."
    )

    # -------------------------------------------------------------------------
    # KPIs & COUNTERS (computed via read_group if the related models are installed)
    # -------------------------------------------------------------------------
    appointment_count = fields.Integer(
        compute="_compute_counters",
        store=False,
        help="Total appointments linked to this slot (if the appointment model exposes slot linkage)."
    )
    appointment_open_count = fields.Integer(
        compute="_compute_counters",
        store=False,
        help="Non-terminal appointments linked to this slot."
    )
    queue_token_count = fields.Integer(
        compute="_compute_counters",
        store=False,
        help="Queue tokens linked/overlapping this slot (if queue module is installed)."
    )
    device_count = fields.Integer(
        compute="_compute_counters",
        store=False,
        help="Devices mapped to the room during this window (if device module is installed)."
    )
    reserved_seats = fields.Integer(
        compute="_compute_reserved_seats",
        store=False,
        help="Total reserved seats = manual_reserved + appointment reservations (if available)."
    )
    available_seats = fields.Integer(
        compute="_compute_reserved_seats",
        store=False,
        help="Remaining seats available for booking (not less than zero)."
    )

    # -------------------------------------------------------------------------
    # UX PRESENTATION (localized labels, non-stored)
    # -------------------------------------------------------------------------
    display_name = fields.Char(
        compute="_compute_display_name",
        store=False
    )
    tz_name = fields.Char(
        compute="_compute_tz_name",
        store=False,
        help="Timezone name used for localizing display labels."
    )
    start_local = fields.Char(
        compute="_compute_local_labels",
        store=False,
        help="Start time localized to the user's/doctor's timezone (string)."
    )
    end_local = fields.Char(
        compute="_compute_local_labels",
        store=False,
        help="End time localized to the user's/doctor's timezone (string)."
    )

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _sql_constraints = [
        ("check_start_end", "CHECK(start < end)", "End time must be greater than Start time."),
        ("uniq_doctor_window_company_room",
         "unique(doctor_id, company_id, start, end, room_id)",
         "A duplicate slot exists for the same doctor, room, and time window."),
    ]

    # -------------------------------------------------------------------------
    # BASIC CONSTRAINTS & ONCHANGES
    # -------------------------------------------------------------------------
    @api.constrains("capacity", "manual_reserved")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity < 1:
                raise ValidationError(_("Capacity must be at least 1."))
            if rec.manual_reserved < 0:
                raise ValidationError(_("Manual reserved seats cannot be negative."))
            if rec.manual_reserved > rec.capacity:
                raise ValidationError(_("Manual reserved seats cannot exceed capacity."))

    @api.constrains("doctor_id", "room_id", "specialty_id")
    def _check_room_specialty_policy(self):
        """
        If room enforces allowed_specialty_ids, ensure the specialty is allowed.
        This is a soft rule in many clinics; convert to 'Warning' in views if needed.
        """
        for rec in self:
            room = rec.room_id
            if not room:
                continue
            if "allowed_specialty_ids" in room._fields and room.allowed_specialty_ids:
                if rec.specialty_id and rec.specialty_id.id not in room.allowed_specialty_ids.ids:
                    raise ValidationError(_(
                        "Specialty '%(spec)s' is not allowed in room '%(room)s'.",
                        spec=rec.specialty_id.display_name,
                        room=room.display_name,
                    ))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_duration(self):
        for rec in self:
            if rec.start and rec.end:
                delta = rec.end - rec.start
                rec.duration_minutes = int(delta.total_seconds() // 60)
            else:
                rec.duration_minutes = 0

    def _compute_tz_name(self):
        for rec in self:
            tzname = False
            # 1) Doctor's user tz
            if rec.doctor_id and rec.doctor_id.user_id and rec.doctor_id.user_id.tz:
                tzname = rec.doctor_id.user_id.tz
            # 2) Company tz
            elif rec.company_id and rec.company_id.partner_id and rec.company_id.partner_id.tz:
                tzname = rec.company_id.partner_id.tz
            # 3) Fallback
            rec.tz_name = tzname or "UTC"

    def _localize_dt(self, dt, tzname):
        if not dt:
            return False
        tz = timezone(tzname)
        # as Odoo stores naive UTC, localize assuming UTC then convert
        dt_utc = UTC.localize(dt)
        return dt_utc.astimezone(tz)

    def _compute_local_labels(self):
        for rec in self:
            if not rec.start or not rec.end:
                rec.start_local = ""
                rec.end_local = ""
                continue
            tzname = rec.tz_name or "UTC"
            s_local = rec._localize_dt(rec.start, tzname)
            e_local = rec._localize_dt(rec.end, tzname)
            rec.start_local = s_local.strftime("%Y-%m-%d %H:%M")
            rec.end_local = e_local.strftime("%Y-%m-%d %H:%M")

    def _compute_display_name(self):
        for rec in self:
            doc = rec.doctor_id.display_name if rec.doctor_id else _("Unknown Doctor")
            room = rec.room_id.display_name if rec.room_id else _("No Room")
            mode = _("Telemedicine") if rec.telemedicine else _("Onsite")
            rec.display_name = f"{doc} — {rec.start_local} → {rec.end_local} ({mode}, {room})"

    def _compute_counters(self):
        ids = self.ids or []
        app_map = {sid: 0 for sid in ids}
        app_open_map = {sid: 0 for sid in ids}
        queue_map = {sid: 0 for sid in ids}
        dev_map = {sid: 0 for sid in ids}

        # Appointments (optional): requires clinic.appointment having M2O 'slot_id'
        # if ids and "clinic.appointment" in self.env and "slot_id" in self.env["clinic.appointment"]._fields:
        #     App = self.env["clinic.appointment"]
        #     groups_all = App.read_group(
        #         [("slot_id", "in", ids)],
        #         ["slot_id"],
        #         ["slot_id"],
        #     )
        #     app_map.update({g["slot_id"][0]: g["slot_id_count"] for g in groups_all})
        #     groups_open = App.read_group(
        #         [("slot_id", "in", ids), ("state", "not in", ["canceled", "done", "no_show"])],
        #         ["slot_id"],
        #         ["slot_id"],
        #     )
        #     app_open_map.update({g["slot_id"][0]: g["slot_id_count"] for g in groups_open})

        # Queue tokens (optional): link by slot_id if provided, else by window overlap
        if ids and "clinic.queue.token" in self.env:
            Token = self.env["clinic.queue.token"]
            if "slot_id" in Token._fields:
                groups_q = Token.read_group(
                    [("slot_id", "in", ids)],
                    ["slot_id"],
                    ["slot_id"],
                )
                queue_map.update({g["slot_id"][0]: g["slot_id_count"] for g in groups_q})
            else:
                # Overlap by window if slot linkage not present
                for rec in self:
                    queue_map[rec.id] = Token.search_count([
                        ("room_id", "=", rec.room_id.id) if rec.room_id else ("id", "!=", 0),
                        ("scheduled_start", "<", rec.end),
                        ("scheduled_end", ">", rec.start),
                    ])

        # Devices (optional): count devices bound to the room (not time-aware)
        if ids and "clinic.device" in self.env and self:
            groups_d = self.env["clinic.device"].read_group(
                [("room_id", "in", self.mapped("room_id").ids)],
                ["room_id"],
                ["room_id"],
            )
            tmp = {g["room_id"][0]: g["room_id_count"] for g in groups_d}
            for rec in self:
                dev_map[rec.id] = tmp.get(rec.room_id.id, 0)

        for rec in self:
            rec.appointment_count = app_map.get(rec.id, 0)
            rec.appointment_open_count = app_open_map.get(rec.id, 0)
            rec.queue_token_count = queue_map.get(rec.id, 0)
            rec.device_count = dev_map.get(rec.id, 0)

    def _compute_reserved_seats(self):
        ids = self.ids or []
        app_res_map = {sid: 0 for sid in ids}
        # if ids and "clinic.appointment" in self.env and "slot_id" in self.env["clinic.appointment"]._fields:
        #     # Count only active bookings
        #     groups = self.env["clinic.appointment"].read_group(
        #         [("slot_id", "in", ids), ("state", "not in", ["canceled", "no_show"])],
        #         ["slot_id"],
        #         ["slot_id"],
        #     )
        #     app_res_map.update({g["slot_id"][0]: g["slot_id_count"] for g in groups})

        for rec in self:
            reserved = (rec.manual_reserved or 0) + app_res_map.get(rec.id, 0)
            rec.reserved_seats = reserved
            rem = (rec.capacity or 0) - reserved
            rec.available_seats = max(0, rem)

    # -------------------------------------------------------------------------
    # BUSINESS POLICY CHECKS
    # -------------------------------------------------------------------------
    def _check_doctor_leave_overlap(self):
        """Return a map id->bool whether slot overlaps any doctor leave."""
        res = {sid: False for sid in self.ids}
        if "clinic.doctor.leave" not in self.env:
            return res
        Leave = self.env["clinic.doctor.leave"]
        for rec in self:
            has = Leave.search_count([
                ("doctor_id", "=", rec.doctor_id.id),
                ("date_from", "<", rec.end),
                ("date_to", ">", rec.start),
            ], limit=1)
            res[rec.id] = bool(has)
        return res

    # def _check_appointment_overlap(self):
    #     """Return a map id->bool whether slot overlaps any non-terminal appointment."""
    #     res = {sid: False for sid in self.ids}
    #     if "clinic.appointment" not in self.env:
    #         return res
    #     App = self.env["clinic.appointment"]
    #     for rec in self:
    #         has = App.search_count([
    #             ("doctor_id", "=", rec.doctor_id.id),
    #             ("state", "not in", ["canceled", "done", "no_show"]),
    #             ("start", "<", rec.end),
    #             ("end", ">", rec.start),
    #         ], limit=1)
    #         res[rec.id] = bool(has)
    #     return res

    # -------------------------------------------------------------------------
    # STATE MACHINE / TRANSITIONS
    # -------------------------------------------------------------------------
    def _update_state_from_capacity(self):
        """Auto-advance state based on seats."""
        for rec in self:
            if rec.state in ("blocked", "closed"):
                continue
            if rec.available_seats <= 0:
                rec.state = "booked"
            elif rec.reserved_seats > 0:
                rec.state = "reserved"
            else:
                rec.state = "open"

    def action_block(self):
        """Block the slot (with optional reason in context 'block_reason')."""
        for rec in self:
            if rec.state == "closed":
                raise UserError(_("Closed slots cannot be blocked."))
            rec.state = "blocked"
            reason = (self.env.context or {}).get("block_reason")
            if reason:
                rec.block_reason = reason
        return True

    def action_unblock(self):
        """Reopen a previously blocked slot."""
        for rec in self:
            if rec.state != "blocked":
                continue
            rec.state = "open"
            rec.block_reason = False
            rec._update_state_from_capacity()
        return True

    def action_close(self):
        """Administratively close this slot (e.g., at end of day)."""
        for rec in self:
            rec.state = "closed"
        return True

    def action_reopen(self):
        """Reopen a closed slot if still valid."""
        for rec in self:
            if rec.end and rec.end < fields.Datetime.now():
                raise UserError(_("You cannot reopen a past slot."))
            rec.state = "open"
            rec._update_state_from_capacity()
        return True

    def action_reserve_seats(self, qty=1):
        """Manually reserve seats (when appointment module is not used)."""
        if qty <= 0:
            raise UserError(_("Quantity must be a positive integer."))
        for rec in self:
            if rec.state in ("blocked", "closed"):
                raise UserError(_("Cannot reserve seats on blocked/closed slots."))
            if rec.available_seats < qty:
                raise UserError(_("Not enough available seats to reserve."))
            rec.manual_reserved += qty
            rec._update_state_from_capacity()
        return True

    def action_release_seats(self, qty=1):
        """Release manual reservations."""
        if qty <= 0:
            raise UserError(_("Quantity must be a positive integer."))
        for rec in self:
            if rec.manual_reserved < qty:
                raise UserError(_("Cannot release more seats than reserved."))
            rec.manual_reserved -= qty
            rec._update_state_from_capacity()
        return True

    # -------------------------------------------------------------------------
    # BOOKING HELPERS
    # -------------------------------------------------------------------------
    # def action_create_appointment(self):
    #     """
    #     Open appointment form pre-filled with this slot data.
    #     Requires clinic.appointment; if slot_id is supported, it will be set.
    #     """
    #     self.ensure_one()
    #     model_name = "clinic.appointment"
    #     if model_name not in self.env:
    #         return {
    #             "type": "ir.actions.client",
    #             "tag": "display_notification",
    #             "params": {"title": _("Not Available"),
    #                        "message": _("Appointment module is not installed."),
    #                        "sticky": False},
    #         }
    #     ctx = {
    #         "default_doctor_id": self.doctor_id.id,
    #         "default_start": self.start,
    #         "default_end": self.end,
    #         "default_company_id": self.company_id.id,
    #     }
    #     if self.room_id and "room_id" in self.env[model_name]._fields:
    #         ctx["default_room_id"] = self.room_id.id
    #     if self.specialty_id and "specialty_id" in self.env[model_name]._fields:
    #         ctx["default_specialty_id"] = self.specialty_id.id
    #     if "slot_id" in self.env[model_name]._fields:
    #         ctx["default_slot_id"] = self.id

    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Create Appointment"),
    #         "res_model": model_name,
    #         "view_mode": "form",
    #         "target": "current",
    #         "context": ctx,
    #     }

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Auto-correct states after creation
        records._update_state_from_capacity()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._update_state_from_capacity()
        return res

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, rec.display_name or _("Availability Slot")))
        return res


# -*- coding: utf-8 -*-
# File: clinic_doctor/models/doctor.py
# Module: clinic_doctor
#
# Core model for Doctor Management & Scheduling in ClinicOne (Odoo 19 CE ready).
#
# Design goals:
# - Keep this core model lean and stable; avoid hard dependencies on non-core apps.
# - Use res.partner as the primary identity (contacts, portal, comms).
# - Room awareness is provided via clinic_queue_room (clinic.room).
# - Rich, but optional, cross-module integrations via guarded env checks and hook methods.
#
# Notes:
# - HR/Payroll linkage is provided by the bridge module "clinic_doctor_hr" (employee_id, strict mode, sync).
# - Treatment/Billing/Inventory/etc. may extend this model or consume it; we keep optional references via actions/hooks.
# - All strings are in English per the product requirement.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicDoctor(models.Model):
    _name = "clinic.doctor"
    _description = "Doctor"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, id"

    # -------------------------------------------------------------------------
    # CORE LINKS & IDENTITY
    # -------------------------------------------------------------------------
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Linked contact for this doctor. The contact should represent an individual person."
    )
    user_id = fields.Many2one(
        "res.users",
        ondelete="set null",
        tracking=True,
        help="Optional system user associated with the doctor for calendar/portal/back-office access."
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
        help="Company that this doctor belongs to."
    )

    # Mirror partner's name for fast search/sort
    name = fields.Char(
        related="partner_id.name",
        store=True,
        readonly=True,
        help="Display name of the doctor (mirrors the linked contact's name)."
    )

    # Professional identity
    license_no = fields.Char(
        required=True,
        index=True,
        tracking=True,
        help="Professional license number of the doctor; must be unique per company."
    )
    license_authority = fields.Char(
        help="Issuing authority/board of the professional license."
    )
    specialty_ids = fields.Many2many(
        "clinic.specialty",
        "clinic_doctor_specialty_rel",   # relation table must match the one used in clinic.specialty
        "doctor_id",
        "specialty_id",
        string="Specialties",
        help="Medical specialties practiced by this doctor."
    )
    seniority_level = fields.Selection(
        [
            ("resident", "Resident"),
            ("junior", "Junior"),
            ("senior", "Senior"),
            ("consultant", "Consultant"),
        ],
        default="junior",
        tracking=True,
        help="Seniority level used for scheduling priority, pricing policies, or reporting."
    )

    # Profile flags (kept generic to avoid hard depends)
    allow_portal_booking = fields.Boolean(
        default=False,
        help="If enabled, the doctor can be exposed for patient self-service booking on the portal."
    )
    telemedicine_enabled = fields.Boolean(
        default=False,
        help="If enabled, the doctor supports telemedicine/remote consultations."
    )
    rating_enabled = fields.Boolean(
        default=False,
        help="If enabled and rating module(s) are installed, patients can submit ratings for the doctor."
    )

    # -------------------------------------------------------------------------
    # CONTACT (RELATED FROM PARTNER) & PRESENTATION
    # -------------------------------------------------------------------------
    work_email = fields.Char(related="partner_id.email", string="Email", store=True, readonly=True)
    work_phone = fields.Char(related="partner_id.phone", string="Phone", store=True, readonly=True)
    mobile = fields.Char(related="partner_id.mobile", string="Mobile", store=True, readonly=True)
    street = fields.Char(related="partner_id.street", store=True, readonly=True)
    city = fields.Char(related="partner_id.city", store=True, readonly=True)
    state_id = fields.Many2one(related="partner_id.state_id", store=True, readonly=True)
    zip = fields.Char(related="partner_id.zip", store=True, readonly=True)
    country_id = fields.Many2one(related="partner_id.country_id", store=True, readonly=True)
    image_1920 = fields.Image(related="partner_id.image_1920", readonly=True)
    color = fields.Integer(
        help="Color index used in kanban/calendar views to visually distinguish doctors."
    )
    notes = fields.Text(
        help="Internal notes such as credentials, languages, or procedure preferences."
    )

    # -------------------------------------------------------------------------
    # SCHEDULING & AVAILABILITY
    # -------------------------------------------------------------------------
    calendar_id = fields.Many2one(
        "resource.calendar",
        string="Working Hours",
        help="Working hours template used to compute default availability patterns."
    )
    default_room_id = fields.Many2one(
        "clinic.room",
        ondelete="set null",
        help="Preferred room for this doctor when scheduling appointments or treatments."
    )
    capacity_per_slot = fields.Integer(
        default=1,
        tracking=True,
        help="Maximum number of concurrent patients allowed per time slot for this doctor."
    )
    min_lead_time_hours = fields.Integer(
        default=0,
        help="Minimum lead time (in hours) required before a new booking can be made."
    )
    max_lead_time_days = fields.Integer(
        default=180,
        help="Maximum lead time (in days) allowed for future bookings."
    )

    schedule_rule_ids = fields.One2many(
        "clinic.schedule.rule",
        "doctor_id",
        string="Schedule Rules",
        help="Weekly/recurring templates that generate concrete availability slots."
    )
    availability_slot_ids = fields.One2many(
        "clinic.availability.slot",
        "doctor_id",
        string="Availability Slots",
        help="Concrete generated availability slots ready for booking."
    )
    leave_ids = fields.One2many(
        "clinic.doctor.leave",
        "doctor_id",
        string="Leaves",
        help="Leaves/holidays/blackout periods during which the doctor is not available."
    )

    # High-level state & next availability
    availability_state = fields.Selection(
        [
            ("available", "Available"),
            ("on_leave", "On Leave"),
            ("inactive", "Inactive"),
            ("unknown", "Unknown"),
        ],
        compute="_compute_availability_state",
        store=False,
        help="High-level availability indicator for quick triage and scheduling."
    )
    next_available_slot = fields.Datetime(
        compute="_compute_next_available_slot",
        store=False,
        help="Next available time slot for this doctor (server time)."
    )

    # -------------------------------------------------------------------------
    # APPOINTMENT & TREATMENT INTEGRATIONS (COUNTERS)
    # -------------------------------------------------------------------------
    # appointment_ids = fields.One2many(
    #     "clinic.appointment",
    #     "doctor_id",
    #     string="Appointments",
    #     help="Appointments linked to this doctor."
    # )
    # appointment_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of appointments for this doctor (all states)."
    # )
    # open_appointment_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of non-closed appointments (e.g., draft/confirmed/checked-in/in-treatment)."
    # )
    # treatment_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of treatment sessions associated to this doctor (if the model exists)."
    # )

    # Optional KPI placeholders (other modules may update/write these)
    kpi_utilization_rate = fields.Float(
        digits=(16, 2),
        help="Utilization rate (%) within the configured reporting window (maintained by reports/jobs)."
    )
    kpi_no_show_rate = fields.Float(
        digits=(16, 2),
        help="No-show rate (%) within the configured reporting window (maintained by reports/jobs)."
    )
    
    # dari patient_link.py \\\///
    patient_ids = fields.Many2many(
        "clinic.patient",
        "clinic_patient_doctor_rel",      # same M2M table
        "doctor_id",
        "patient_id",
        string="Patients",
        help="Patients that marked this doctor as preferred (or primary)."
    )
    patient_count = fields.Integer(
        compute="_compute_patient_count",
        store=False,
        help="Number of patients that prefer this doctor."
    )

    def _compute_patient_count(self):
        for rec in self:
            rec.patient_count = len(rec.patient_ids)

    def action_view_patients(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patients"),
            "res_model": "clinic.patient",
            "view_mode": "tree,form,kanban",
            "domain": [("id", "in", self.patient_ids.ids)],
            "target": "current",
        }

    def action_view_primary_patients(self):
        """Open patients for whom this doctor is the primary doctor."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Primary Patients"),
            "res_model": "clinic.patient",
            "view_mode": "tree,form,kanban",
            "domain": [("primary_doctor_id", "=", self.id)],
            "target": "current",
        }
    # dari patient_link.py ///\\\

    # dari file queue.py \\\///
    queue_waiting_count = fields.Integer(
        compute="_compute_queue_counts",
        store=False,
        help="Number of waiting queue tokens for this doctor."
    )
    queue_in_service_count = fields.Integer(
        compute="_compute_queue_counts",
        store=False,
        help="Number of in-service queue tokens for this doctor."
    )
    last_queue_token_id = fields.Many2one(
        "clinic.queue.token",
        compute="_compute_queue_counts",
        store=False,
        help="Most recent queue token for this doctor."
    )

    def _compute_queue_counts(self):
        Token = self.env["clinic.queue.token"] if "clinic.queue.token" in self.env else False
        for rec in self:
            rec.queue_waiting_count = 0
            rec.queue_in_service_count = 0
            rec.last_queue_token_id = False
            if not Token or "doctor_id" not in Token._fields:
                continue

            dom_base = [("doctor_id", "=", rec.id)]
            # Waiting: states that represent belum dipanggil/menunggu
            dom_wait = dom_base + [("state", "in", ["new", "waiting", "queued", "called"])] if "state" in Token._fields else dom_base
            # In service
            dom_srv = dom_base + [("state", "in", ["in_service", "serving"])] if "state" in Token._fields else dom_base

            rec.queue_waiting_count = Token.search_count(dom_wait)
            rec.queue_in_service_count = Token.search_count(dom_srv)

            # Last token (by write_date/create_date)
            token_last = Token.search(dom_base, order="write_date desc, create_date desc", limit=1)
            rec.last_queue_token_id = token_last.id if token_last else False

    # Actions (open tokens by state)
    def action_view_queue_tokens(self):
        self.ensure_one()
        if "clinic.queue.token" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Queue module is not installed."),
                           "sticky": False},
            }
        domain = [("doctor_id", "=", self.id)]
        return {
            "type": "ir.actions.act_window",
            "name": _("Queue Tokens"),
            "res_model": "clinic.queue.token",
            "view_mode": "tree,form,kanban",
            "domain": domain,
            "target": "current",
            "context": {"search_default_doctor_id": self.id},
        }

    def action_view_waiting_tokens(self):
        self.ensure_one()
        if "clinic.queue.token" not in self.env:
            return {"type": "ir.actions.client", "tag": "display_notification",
                    "params": {"title": _("Not Available"), "message": _("Queue module is not installed."), "sticky": False}}
        domain = [("doctor_id", "=", self.id)]
        if "state" in self.env["clinic.queue.token"]._fields:
            domain += [("state", "in", ["new", "waiting", "queued", "called"])]
        return {
            "type": "ir.actions.act_window",
            "name": _("Waiting Tokens"),
            "res_model": "clinic.queue.token",
            "view_mode": "tree,form,kanban",
            "domain": domain,
            "target": "current",
        }

    def action_view_in_service_tokens(self):
        self.ensure_one()
        if "clinic.queue.token" not in self.env:
            return {"type": "ir.actions.client", "tag": "display_notification",
                    "params": {"title": _("Not Available"), "message": _("Queue module is not installed."), "sticky": False}}
        domain = [("doctor_id", "=", self.id)]
        if "state" in self.env["clinic.queue.token"]._fields:
            domain += [("state", "in", ["in_service", "serving"])]
        return {
            "type": "ir.actions.act_window",
            "name": _("In-service Tokens"),
            "res_model": "clinic.queue.token",
            "view_mode": "tree,form,kanban",
            "domain": domain,
            "target": "current",
        }
    # dari file queue.py ///\\\

    # -------------------------------------------------------------------------
    # LIFECYCLE
    # -------------------------------------------------------------------------
    active = fields.Boolean(
        default=True,
        help="Deactivating a doctor hides it from selection and new scheduling, "
             "but preserves historical data."
    )

    _sql_constraints = [
        ("license_company_uniq", "unique(license_no, company_id)",
         "License number must be unique per company."),
        ("partner_company_uniq", "unique(partner_id, company_id)",
         "A doctor for the same contact already exists in this company."),
    ]

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    # @api.depends("appointment_ids.state")
    # def _compute_counts(self):
    #     """Compute appointment/treatment counters via read_group (fast & safe)."""
    #     Appointment = self.env["clinic.appointment"]

    #     # All appointments
    #     groups_all = Appointment.read_group(
    #         [("doctor_id", "in", self.ids)],
    #         ["doctor_id"],
    #         ["doctor_id"],
    #     )
    #     count_all_map = {g["doctor_id"][0]: g["doctor_id_count"] for g in groups_all}

    #     # Open appointments (exclude terminal states)
    #     groups_open = Appointment.read_group(
    #         [("doctor_id", "in", self.ids), ("state", "not in", ["canceled", "done", "no_show"])],
    #         ["doctor_id"],
    #         ["doctor_id"],
    #     )
    #     count_open_map = {g["doctor_id"][0]: g["doctor_id_count"] for g in groups_open}

    #     # Treatment sessions (optional model)
    #     treatment_map = {}
    #     if "clinic.procedure.session" in self.env:
    #         t_groups = self.env["clinic.procedure.session"].read_group(
    #             [("doctor_id", "in", self.ids)], ["doctor_id"], ["doctor_id"]
    #         )
    #         treatment_map = {g["doctor_id"][0]: g["doctor_id_count"] for g in t_groups}

    #     for rec in self:
    #         rec.appointment_count = count_all_map.get(rec.id, 0)
    #         rec.open_appointment_count = count_open_map.get(rec.id, 0)
    #         rec.treatment_count = treatment_map.get(rec.id, 0)

    def _compute_next_available_slot(self):
        """Find the earliest open availability slot from now."""
        Slot = self.env["clinic.availability.slot"]
        now = fields.Datetime.now()
        for rec in self:
            next_slot = Slot.search([
                ("doctor_id", "=", rec.id),
                ("state", "=", "open"),
                ("start", ">=", now),
            ], order="start asc", limit=1)
            rec.next_available_slot = next_slot.start if next_slot else False

    def _compute_availability_state(self):
        """Coarse availability based on active flag, overlapping leave, and presence of schedule/slots."""
        now = fields.Datetime.now()
        for rec in self:
            if not rec.active:
                rec.availability_state = "inactive"
                continue
            # On leave if any leave covers now
            leave_now = rec.leave_ids.filtered(
                lambda l: (not l.date_from or l.date_from <= now) and (not l.date_to or l.date_to >= now)
            )
            if leave_now:
                rec.availability_state = "on_leave"
            elif not rec.schedule_rule_ids and not rec.availability_slot_ids:
                rec.availability_state = "unknown"
            else:
                rec.availability_state = "available"

    # -------------------------------------------------------------------------
    # PY CONSTRAINTS & ONCHANGES
    # -------------------------------------------------------------------------
    @api.constrains("capacity_per_slot")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity_per_slot < 1:
                raise ValidationError(_("Capacity per slot must be at least 1."))

    @api.constrains("min_lead_time_hours", "max_lead_time_days")
    def _check_lead_times(self):
        for rec in self:
            if rec.min_lead_time_hours < 0:
                raise ValidationError(_("Minimum lead time cannot be negative."))
            if rec.max_lead_time_days < 0:
                raise ValidationError(_("Maximum lead time cannot be negative."))

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id and self.partner_id.is_company:
            return {
                "warning": {
                    "title": _("Contact is a Company"),
                    "message": _("The linked contact is a company. "
                                 "It is recommended to use an individual contact for a doctor.")
                }
            }

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Mark partner as doctor if the custom flag exists on res.partner
            if rec.partner_id and "is_doctor" in rec.partner_id._fields:
                rec.partner_id.sudo().write({"is_doctor": True})

            # Auto-subscribe the associated user/partner for chatter
            partner_ids = []
            if rec.partner_id:
                partner_ids.append(rec.partner_id.id)
            if rec.user_id and rec.user_id.partner_id:
                partner_ids.append(rec.user_id.partner_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))

            # Hook for bridge modules (e.g., HR auto-create, marketing profile, etc.)
            rec._post_create_integrations_hook()
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            # Keep partner doctor flag in sync if present
            if rec.partner_id and "is_doctor" in rec.partner_id._fields:
                rec.partner_id.sudo().write({"is_doctor": True})

            # Let bridge modules react to updates (sync to employee, pricing cache, etc.)
            rec._post_write_integrations_hook(vals)
        return res

    # def unlink(self):
    #     # Prevent deletion when linked to any (non-canceled) appointment to keep integrity
    #     blocked = self.env["clinic.appointment"].search_count([
    #         ("doctor_id", "in", self.ids),
    #         ("state", "!=", "canceled"),
    #     ])
    #     if blocked:
    #         raise UserError(_(
    #             "You cannot delete a doctor that has related appointments. "
    #             "Consider deactivating the doctor instead."
    #         ))

    #     # Give bridges a chance to clean downstream references
    #     for rec in self:
    #         rec._pre_unlink_integrations_hook()

    #     return super().unlink()

    # -------------------------------------------------------------------------
    # INTEGRATION HOOKS (to be overridden by bridge modules)
    # -------------------------------------------------------------------------
    def _post_create_integrations_hook(self):
        """
        Hook for bridge modules to react after Doctor creation.
        Example bridges:
          - clinic_doctor_hr: auto-create hr.employee, enforce strict HR policy.
          - clinic_marketing: initialize UTM/segments, opt-ins.
          - clinic_portal: set portal access or welcome message.
        """
        # Intentionally empty in core. Bridges may override.
        return True

    def _post_write_integrations_hook(self, vals):
        """
        Hook for bridge modules to react to Doctor updates.
        Example bridges:
          - Sync user/employee data.
          - Invalidate availability caches or pricing caches.
        """
        # Intentionally empty in core. Bridges may override.
        return True

    def _pre_unlink_integrations_hook(self):
        """
        Hook for bridge modules to clean related resources before deletion.
        Example bridges:
          - Remove marketing subscriptions or external identities.
        """
        # Intentionally empty in core. Bridges may override.
        return True

    # -------------------------------------------------------------------------
    # ACTIONS (UI HELPERS)
    # -------------------------------------------------------------------------
    # def action_view_appointments(self):
    #     """Open the doctor's appointments."""
    #     self.ensure_one()
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Appointments"),
    #         "res_model": "clinic.appointment",
    #         "view_mode": "calendar,tree,form,pivot,graph",
    #         "domain": [("doctor_id", "=", self.id)],
    #         "context": {
    #             "default_doctor_id": self.id,
    #         },
    #         "target": "current",
    #     }

    def action_view_schedule_rules(self):
        """Open schedule rules for this doctor."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Schedule Rules"),
            "res_model": "clinic.schedule.rule",
            "view_mode": "tree,form,calendar",
            "domain": [("doctor_id", "=", self.id)],
            "context": {"default_doctor_id": self.id},
            "target": "current",
        }

    def action_view_availability(self):
        """Open availability slots for this doctor."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Availability"),
            "res_model": "clinic.availability.slot",
            "view_mode": "calendar,tree,form",
            "domain": [("doctor_id", "=", self.id)],
            "context": {"default_doctor_id": self.id},
            "target": "current",
        }

    def action_view_next_available_slot(self):
        """Jump to calendar filtered on the next available slot."""
        self.ensure_one()
        domain = [("doctor_id", "=", self.id)]
        if self.next_available_slot:
            domain.append(("start", ">=", self.next_available_slot))
        return {
            "type": "ir.actions.act_window",
            "name": _("Next Availability"),
            "res_model": "clinic.availability.slot",
            "view_mode": "calendar,tree,form",
            "domain": domain,
            "target": "current",
        }

    def action_view_leaves(self):
        """Open the doctor's leaves/blackouts."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Leaves"),
            "res_model": "clinic.doctor.leave",
            "view_mode": "tree,form,calendar",
            "domain": [("doctor_id", "=", self.id)],
            "context": {"default_doctor_id": self.id},
            "target": "current",
        }

    def action_view_treatments(self):
        """Open treatments handled by this doctor (if the model exists)."""
        self.ensure_one()
        model_name = "clinic.procedure.session"
        if model_name not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Not Available"),
                    "message": _("Treatment module is not installed."),
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Treatment Sessions"),
            "res_model": model_name,
            "view_mode": "tree,form,kanban,pivot,graph",
            "domain": [("doctor_id", "=", self.id)],
            "target": "current",
        }

    def action_quick_create_appointment(self):
        """
        Open the quick create appointment wizard (if available).
        """
        self.ensure_one()
        model_name = "clinic.quick.create.appointment.wizard"
        if model_name not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Wizard Not Installed"),
                    "message": _("Quick Create Appointment wizard is not available."),
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Quick Create Appointment"),
            "res_model": model_name,
            "view_mode": "form",
            "target": "new",
            "context": {"default_doctor_id": self.id},
        }

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            display = rec.name or _("Unnamed")
            if rec.license_no:
                display = f"{display} [{rec.license_no}]"
            res.append((rec.id, display))
        return res

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=80):
        """Improve search by license number and partner name."""
        args = args or []
        domain = []
        if name:
            domain = ["|", ("license_no", operator, name), ("name", operator, name)]
        records = self.search(domain + args, limit=limit)
        return records.name_get()


# -*- coding: utf-8 -*-
# File: clinic_doctor/models/leave.py
# Module: clinic_doctor
#
# ClinicOne — Doctor Leave / Blackout (Odoo 19 CE ready)
#
# Purpose
# -------
# Manage doctor leaves/blackout windows which affect:
# - Schedule Rule generation (rules skip occurrences that hit leaves)
# - Availability Slots (block/close/delete-open policy on approval)
# - Appointments (optional: notify/cancel/flag for reschedule)
# - Calendar leaves (optional: propagate to resource calendar)
# - HR leave (optional: sync to hr.leave via clinic_doctor_hr bridge)
#
# Notes
# -----
# * All labels/help/messages in English.
# * Uses mail.thread/activity for collaboration & audit trail.
# * Multi-company aware.
# * Safe cross-module behavior via presence checks and config parameters.

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


LEAVE_STATE = [
    ("draft", "Draft"),
    ("confirm", "Confirmed"),
    ("approve", "Approved"),
    ("refuse", "Refused"),
    ("cancel", "Cancelled"),
]

LEAVE_REASON = [
    ("vacation", "Vacation / Annual Leave"),
    ("sick", "Sick Leave"),
    ("training", "Training / Conference"),
    ("personal", "Personal Matters"),
    ("maintenance", "Facility Maintenance"),
    ("other", "Other"),
]

SLOT_POLICY = [
    ("block", "Block overlapping slots"),
    ("close", "Close overlapping slots"),
    ("delete_open", "Delete open & empty slots only"),
]

APPOINTMENT_POLICY = [
    ("notify", "Notify & flag for reschedule"),
    ("cancel", "Cancel overlapping appointments"),
    ("nothing", "Do nothing"),
]


class ClinicDoctorLeave(models.Model):
    _name = "clinic.doctor.leave"
    _description = "Doctor Leave / Blackout"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from asc, doctor_id, id"

    # -------------------------------------------------------------------------
    # IDENTITY & SCOPE
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Subject",
        tracking=True,
        help="Short description of the leave (e.g., Annual Leave, Sick Leave)."
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
        help="Doctor who is on leave."
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company this leave belongs to."
    )
    reason = fields.Selection(
        LEAVE_REASON,
        default="other",
        tracking=True,
        help="Purpose/category of the leave."
    )
    details = fields.Text(
        string="Details",
        help="Additional information about the leave."
    )
    color = fields.Integer(
        help="Color index for quick visual reference in list/kanban views."
    )

    # -------------------------------------------------------------------------
    # TIME WINDOW (UTC naive datetimes, as per Odoo storage)
    # -------------------------------------------------------------------------
    date_from = fields.Datetime(
        required=True,
        tracking=True,
        index=True,
        help="Leave start (stored in UTC)."
    )
    date_to = fields.Datetime(
        required=True,
        tracking=True,
        index=True,
        help="Leave end (stored in UTC). Must be greater than start."
    )
    duration_hours = fields.Float(
        compute="_compute_duration_hours",
        store=False,
        help="Duration of the leave in hours (computed)."
    )

    # -------------------------------------------------------------------------
    # POLICIES (what to do when leave is approved)
    # -------------------------------------------------------------------------
    slot_policy = fields.Selection(
        SLOT_POLICY,
        default="block",
        help="How to handle overlapping availability slots when the leave is approved."
    )
    appointment_policy = fields.Selection(
        APPOINTMENT_POLICY,
        default="notify",
        help="How to handle overlapping appointments when the leave is approved."
    )
    apply_to_rooms = fields.Boolean(
        default=True,
        help="When true, the slot policy is applied irrespective of room assignment."
    )

    # -------------------------------------------------------------------------
    # STATE
    # -------------------------------------------------------------------------
    state = fields.Selection(
        LEAVE_STATE,
        default="draft",
        tracking=True,
        index=True,
        help="Workflow state of the leave."
    )
    active = fields.Boolean(
        default=True,
        help="Disable to hide this leave from standard views without removing history."
    )

    # -------------------------------------------------------------------------
    # COMPUTES & CONSTRAINTS
    # -------------------------------------------------------------------------
    def _compute_duration_hours(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to > rec.date_from:
                delta = rec.date_to - rec.date_from
                rec.duration_hours = round(delta.total_seconds() / 3600.0, 2)
            else:
                rec.duration_hours = 0.0

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if not rec.date_from or not rec.date_to:
                raise ValidationError(_("Both start and end datetimes are required."))
            if rec.date_to <= rec.date_from:
                raise ValidationError(_("End datetime must be greater than start datetime."))

    @api.constrains("doctor_id", "date_from", "date_to", "state")
    def _check_overlap_with_other_leaves(self):
        """
        Avoid overlapping *active* leaves for the same doctor (except Cancelled/Refused).
        """
        for rec in self:
            if not rec.doctor_id or not rec.date_from or not rec.date_to:
                continue
            dom = [
                ("id", "!=", rec.id),
                ("doctor_id", "=", rec.doctor_id.id),
                ("state", "in", ["draft", "confirm", "approve"]),  # active-ish
                ("date_from", "<", rec.date_to),
                ("date_to", ">", rec.date_from),
            ]
            if self.search_count(dom):
                raise ValidationError(_("Overlapping leaves are not allowed for the same doctor."))

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or dict(LEAVE_REASON).get(rec.reason, "Leave")
            label = f"{label} — {rec.doctor_id.display_name}" if rec.doctor_id else label
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # HELPERS — DOMAINS & LOOKUPS
    # -------------------------------------------------------------------------
    def _domain_slots_overlap(self):
        """
        Domain for availability slots overlapping this leave's window.
        Will be guarded by presence check when used.
        """
        self.ensure_one()
        dom = [
            ("doctor_id", "=", self.doctor_id.id),
            ("start", "<", self.date_to),
            ("end", ">", self.date_from),
        ]
        if not self.apply_to_rooms and "room_id" in self.env["clinic.availability.slot"]._fields:
            dom.append(("room_id", "=", False))
        return dom

    def _domain_appointments_overlap(self):
        """
        Domain for appointments overlapping this leave's window (non-terminal).
        """
        self.ensure_one()
        dom = [
            ("doctor_id", "=", self.doctor_id.id),
            ("state", "not in", ["canceled", "done", "no_show"]),
            ("start", "<", self.date_to),
            ("end", ">", self.date_from),
        ]
        return dom

    # -------------------------------------------------------------------------
    # APPLY EFFECTS (SLOTS, APPOINTMENTS, CALENDAR, HR)
    # -------------------------------------------------------------------------
    def _apply_on_slots(self):
        """
        Apply slot policy to overlapping availability slots:
            - block:      set state=blocked & reason
            - close:      set state=closed
            - delete_open: delete only if no active bookings/reservations
        Safe-guarded if 'clinic.availability.slot' is absent.
        """
        if "clinic.availability.slot" not in self.env:
            return {"affected": 0, "deleted": 0}

        Slot = self.env["clinic.availability.slot"].sudo()
        affected = deleted = 0

        for rec in self:
            dom = rec._domain_slots_overlap()
            slots = Slot.search(dom)
            if not slots:
                continue

            if rec.slot_policy == "block":
                # Only block if not already closed; set reason
                for s in slots:
                    if s.state != "closed":
                        s.write({"state": "blocked", "block_reason": _("Doctor on leave")})
                        affected += 1

            elif rec.slot_policy == "close":
                for s in slots:
                    if s.state != "closed":
                        s.write({"state": "closed"})
                        affected += 1

            # elif rec.slot_policy == "delete_open":
                # Delete only open slots with no reservations/appointments
                # for s in slots:
                #     # If appointment linkage exists, ensure no open/active appointments
                #     if "clinic.appointment" in self.env and "slot_id" in self.env["clinic.appointment"]._fields:
                #         has_appt = bool(self.env["clinic.appointment"].search_count(
                #             [("slot_id", "=", s.id), ("state", "not in", ["canceled", "no_show"])]
                #         ))
                #         if has_appt:
                #             continue
                #     # Also ensure no manual reserved seats
                #     if s.state in ("open", "reserved") and (s.manual_reserved or 0) == 0:
                #         s.unlink()
                #         deleted += 1

        return {"affected": affected, "deleted": deleted}

    def _apply_on_appointments(self):
        """
        Apply appointment policy on overlapping appointments:
            - notify: message_post + (set need_reschedule if field exists)
            - cancel: set state='canceled' (if field exists), else message_post
            - nothing: skip
        """
        # if "clinic.appointment" not in self.env:
        #     return {"notified": 0, "canceled": 0, "flagged": 0}

        # App = self.env["clinic.appointment"].sudo()
        notified = canceled = flagged = 0

        # for rec in self:
        #     appts = App.search(rec._domain_appointments_overlap())
        #     for a in appts:
        #         if rec.appointment_policy == "notify":
        #             a.message_post(body=_("Appointment impacted by doctor leave: %s") % (rec.name or rec.reason))
        #             notified += 1
        #             if "need_reschedule" in a._fields:
        #                 a.write({"need_reschedule": True})
        #                 flagged += 1

        #         elif rec.appointment_policy == "cancel":
        #             if "state" in a._fields:
        #                 a.write({"state": "canceled"})
        #                 canceled += 1
        #             else:
        #                 a.message_post(body=_("Canceled due to doctor leave: %s") % (rec.name or rec.reason))
        #                 notified += 1

        #         else:  # nothing
        #             continue

        return {"notified": notified, "canceled": canceled, "flagged": flagged}

    def _apply_calendar_leave(self):
        """
        Optionally create a resource calendar leave entry for the doctor's calendar.
        Controlled by system parameter: clinic_doctor.propagate_calendar_leave = True/False
        """
        Param = self.env["ir.config_parameter"].sudo()
        propagate = Param.get_param("clinic_doctor.propagate_calendar_leave", "True") == "True"
        if not propagate:
            return False

        # Needs a calendar on doctor
        for rec in self:
            cal = rec.doctor_id.calendar_id
            if not cal or "resource.calendar.leaves" not in self.env:
                continue
            CalLeave = self.env["resource.calendar.leaves"].sudo()
            CalLeave.create({
                "name": rec.name or _("Doctor Leave"),
                "company_id": rec.company_id.id,
                "calendar_id": cal.id,
                "date_from": rec.date_from,
                "date_to": rec.date_to,
            })
        return True

    def _apply_hr_leave(self):
        """
        Optionally create hr.leave for the linked employee (bridge clinic_doctor_hr).
        Controlled by system parameter: clinic_doctor.sync_hr_leave = True/False
        Safely guarded if HR not installed or doctor has no employee link.
        """
        Param = self.env["ir.config_parameter"].sudo()
        sync_hr = Param.get_param("clinic_doctor.sync_hr_leave", "False") == "True"
        if not sync_hr or "hr.leave" not in self.env:
            return False

        for rec in self:
            # bridge provides doctor.employee_id
            if "employee_id" not in rec.doctor_id._fields or not rec.doctor_id.employee_id:
                continue
            vals = {
                "name": rec.name or _("Doctor Leave"),
                "employee_id": rec.doctor_id.employee_id.id,
                "request_date_from": fields.Date.to_date(rec.date_from),
                "request_date_to": fields.Date.to_date(rec.date_to),
                # hr.leave uses date_from/date_to (datetime) on records too; safest is to set both
                "date_from": rec.date_from,
                "date_to": rec.date_to,
                "holiday_status_id": self._get_default_hr_leave_type(),
            }
            self.env["hr.leave"].sudo().create(vals)
        return True

    def _get_default_hr_leave_type(self):
        """
        Helper: choose a default hr.leave type (holiday_status_id).
        Best-effort: pick first type or map by reason if you have such mapping in your HR module.
        """
        if "hr.leave.type" not in self.env:
            return False
        LeaveType = self.env["hr.leave.type"].sudo()
        lt = LeaveType.search([], limit=1)
        return lt.id if lt else False

    # -------------------------------------------------------------------------
    # WORKFLOW ACTIONS
    # -------------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            if rec.state != "draft":
                continue
            rec.state = "confirm"
        return True

    def action_approve(self):
        """
        On approval:
          - Apply effects on slots and appointments (according to policy)
          - Optionally create calendar leave
          - Optionally sync HR leave
        """
        results = []
        for rec in self:
            if rec.state not in ("draft", "confirm"):
                continue
            # Apply effects
            slot_res = rec._apply_on_slots()
            appt_res = rec._apply_on_appointments()
            rec._apply_calendar_leave()
            rec._apply_hr_leave()

            rec.state = "approve"
            # Build user feedback
            msg = _(
                "Leave approved and applied.\n"
                "Slots affected: %(a)s, deleted: %(d)s\n"
                "Appointments notified: %(n)s, canceled: %(c)s, flagged: %(f)s",
                a=slot_res.get("affected", 0),
                d=slot_res.get("deleted", 0),
                n=appt_res.get("notified", 0),
                c=appt_res.get("canceled", 0),
                f=appt_res.get("flagged", 0),
            )
            rec.message_post(body=msg)
            results.append((rec.id, msg))

        # Optional: surface a toast
        if results:
            last = results[-1][1]
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Doctor Leave"), "message": last, "sticky": False},
            }
        return True

    def action_refuse(self):
        for rec in self:
            if rec.state in ("approve",):
                # Business choice: allow refuse after approve? If not, raise:
                raise UserError(_("You cannot refuse a leave that is already approved."))
            rec.state = "refuse"
        return True

    def action_cancel(self):
        """
        Cancel the leave:
          - Optionally reopen previously-blocked slots that have no other conflicts.
            (Best-effort heuristic: only those with block_reason='Doctor on leave' and within window)
        """
        if "clinic.availability.slot" in self.env:
            Slot = self.env["clinic.availability.slot"].sudo()
            for rec in self:
                slots = Slot.search([
                    ("doctor_id", "=", rec.doctor_id.id),
                    ("start", "<", rec.date_to),
                    ("end", ">", rec.date_from),
                    ("state", "=", "blocked"),
                    ("block_reason", "=", _("Doctor on leave")),
                ])
                for s in slots:
                    # Reopen only if capacity allows and no active appointment makes it booked
                    s.write({"state": "open", "block_reason": False})
                    s._update_state_from_capacity()
        for rec in self:
            rec.state = "cancel"
        return True

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = "draft"
        return True

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Autoname if not provided
        for rec in records:
            if not rec.name:
                label = dict(LEAVE_REASON).get(rec.reason, "Leave")
                rec.name = f"{label} — {rec.doctor_id.display_name}"
        return records

    def write(self, vals):
        # If window changes after approval, re-apply slot/appointment effects
        reapply = False
        if any(k in vals for k in ("date_from", "date_to", "slot_policy", "appointment_policy")):
            reapply = True
        res = super().write(vals)
        if reapply:
            for rec in self.filtered(lambda r: r.state == "approve"):
                slot_res = rec._apply_on_slots()
                appt_res = rec._apply_on_appointments()
                rec.message_post(body=_(
                    "Leave window/policy updated.\n"
                    "Slots affected: %(a)s, deleted: %(d)s\n"
                    "Appointments notified: %(n)s, canceled: %(c)s, flagged: %(f)s",
                    a=slot_res.get("affected", 0),
                    d=slot_res.get("deleted", 0),
                    n=appt_res.get("notified", 0),
                    c=appt_res.get("canceled", 0),
                    f=appt_res.get("flagged", 0),
                ))
        return res

    def unlink(self):
        # Business rule: prevent deleting approved leaves to preserve audit log
        if any(rec.state == "approve" for rec in self):
            raise UserError(_("You cannot delete an approved leave. Cancel it instead to preserve history."))
        return super().unlink()


# -*- coding: utf-8 -*-
# File: clinic_doctor/models/patient_link.py
# Module: clinic_doctor
#
# ClinicOne — Doctor ↔ Patient linkage (Odoo 19 CE ready)
#
# Scope
# -----
# 1) Extend clinic.patient:
#    - Primary Doctor & Preferred Doctors (M2M)
#    - Appointment KPIs (counts, last/upcoming, no-show)
#    - Quick actions (view/book with doctor)
# 2) Extend clinic.doctor:
#    - Backlink M2M to patients + counter & action
# 3) Extend clinic.appointment (lightweight):
#    - Onchange to auto-bind patient by partner
#    - Policy: partner-patient consistency, optional auto-create patient
#
# Notes
# -----
# * All strings are in English (product requirement).
# * Multi-company aware (doctor <-> patient relations are scoped by company surface
#   via domains/actions dan kebijakan operasional).
# * Optional features guarded by config parameters (see docstrings).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# -----------------------------------------------------------------------------
# EXTEND: clinic.patient
# -----------------------------------------------------------------------------
class ClinicPatient(models.Model):
    _inherit = "clinic.patient"

    # -------------------------------------------------------------------------
    # DOCTOR PREFERENCES & LINKS
    # -------------------------------------------------------------------------
    primary_doctor_id = fields.Many2one(
        "clinic.doctor",
        ondelete="set null",
        index=True,
        tracking=True,
        help="Primary doctor responsible for this patient."
    )
    preferred_doctor_ids = fields.Many2many(
        "clinic.doctor",
        "clinic_patient_doctor_rel",      # shared M2M table with doctor-side backlink
        "patient_id",
        "doctor_id",
        string="Preferred Doctors",
        help="Preferred doctors for this patient."
    )

    # Optional specialty preference (helps routing & pricing; not enforced)
    preferred_specialty_id = fields.Many2one(
        "clinic.specialty",
        ondelete="set null",
        help="Preferred specialty for this patient (optional)."
    )

    # -------------------------------------------------------------------------
    # APPOINTMENT INSIGHTS (KPIs & NAVIGATION)
    # -------------------------------------------------------------------------
    appointment_count = fields.Integer(
        compute="_compute_appointment_kpis",
        store=False,
        help="Total number of appointments for this patient."
    )
    open_appointment_count = fields.Integer(
        compute="_compute_appointment_kpis",
        store=False,
        help="Number of non-terminal appointments (draft/confirmed/checked-in/in-treatment)."
    )
    no_show_count = fields.Integer(
        compute="_compute_appointment_kpis",
        store=False,
        help="Number of no-show appointments."
    )
    last_appointment_id = fields.Many2one(
        "clinic.appointment",
        compute="_compute_appointment_kpis",
        store=False,
        help="Most recent completed appointment for this patient."
    )
    upcoming_appointment_id = fields.Many2one(
        "clinic.appointment",
        compute="_compute_appointment_kpis",
        store=False,
        help="Nearest upcoming appointment for this patient."
    )

    # Convenience mirrors for UI (from primary doctor)
    next_available_slot_primary_doctor = fields.Datetime(
        compute="_compute_primary_doctor_mirrors",
        store=False,
        help="Next available slot of the primary doctor (if availability module is installed)."
    )
    primary_doctor_room = fields.Many2one(
        "clinic.room",
        compute="_compute_primary_doctor_mirrors",
        store=False,
        help="Default room of the primary doctor, if any."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_appointment_kpis(self):
        """
        Compute appointment KPIs via read_group for performance.
        """
        ids = self.ids or []
        if not ids or "clinic.appointment" not in self.env:
            for rec in self:
                rec.appointment_count = 0
                rec.open_appointment_count = 0
                rec.no_show_count = 0
                rec.last_appointment_id = False
                rec.upcoming_appointment_id = False
            return

        App = self.env["clinic.appointment"]

        # all appointments
        g_all = App.read_group(
            [("patient_id", "in", ids)],
            ["patient_id"],
            ["patient_id"],
        )
        map_all = {g["patient_id"][0]: g["patient_id_count"] for g in g_all}

        # open appointments
        g_open = App.read_group(
            [("patient_id", "in", ids), ("state", "not in", ["canceled", "done", "no_show"])],
            ["patient_id"],
            ["patient_id"],
        )
        map_open = {g["patient_id"][0]: g["patient_id_count"] for g in g_open}

        # no-show
        g_ns = App.read_group(
            [("patient_id", "in", ids), ("state", "=", "no_show")],
            ["patient_id"],
            ["patient_id"],
        )
        map_ns = {g["patient_id"][0]: g["patient_id_count"] for g in g_ns}

        # last done & upcoming (per-record search for clarity)
        now = fields.Datetime.now()
        for rec in self:
            rec.appointment_count = map_all.get(rec.id, 0)
            rec.open_appointment_count = map_open.get(rec.id, 0)
            rec.no_show_count = map_ns.get(rec.id, 0)

            last_done = App.search(
                [("patient_id", "=", rec.id), ("state", "=", "done")],
                order="end desc", limit=1
            )
            rec.last_appointment_id = last_done.id if last_done else False

            upcoming = App.search(
                [("patient_id", "=", rec.id), ("start", ">=", now), ("state", "not in", ["canceled", "no_show"])],
                order="start asc", limit=1
            )
            rec.upcoming_appointment_id = upcoming.id if upcoming else False

    def _compute_primary_doctor_mirrors(self):
        for rec in self:
            doc = rec.primary_doctor_id
            if doc:
                # Next availability (if availability model exists)
                if "clinic.availability.slot" in self.env:
                    slot = self.env["clinic.availability.slot"].search([
                        ("doctor_id", "=", doc.id),
                        ("state", "=", "open") if "state" in self.env["clinic.availability.slot"]._fields else ("id", "!=", 0),
                        ("start", ">=", fields.Datetime.now()),
                    ], order="start asc", limit=1)
                    rec.next_available_slot_primary_doctor = slot.start if slot else False
                else:
                    rec.next_available_slot_primary_doctor = False
                # Default room mirror (if present on doctor)
                rec.primary_doctor_room = getattr(doc, "default_room_id", False) and doc.default_room_id.id or False
            else:
                rec.next_available_slot_primary_doctor = False
                rec.primary_doctor_room = False

    # -------------------------------------------------------------------------
    # ONCHANGES & CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.onchange("primary_doctor_id")
    def _onchange_primary_doctor_id(self):
        for rec in self:
            if rec.primary_doctor_id and rec.primary_doctor_id not in rec.preferred_doctor_ids:
                # Keep primary contained within preferred as soft policy
                rec.preferred_doctor_ids = [(4, rec.primary_doctor_id.id)]

    @api.constrains("primary_doctor_id")
    def _check_primary_doctor_company(self):
        """
        Optional soft guard: In multi-company setups, warn when primary doctor belongs
        to a different company than the patient's company (if such field exists).
        We only post a message to avoid friction.
        """
        for rec in self:
            if rec.primary_doctor_id and rec.company_id and rec.primary_doctor_id.company_id != rec.company_id:
                rec.message_post(body=_(
                    "Primary doctor is assigned from a different company (%s). "
                    "Please ensure this is intended."
                ) % rec.primary_doctor_id.company_id.display_name)

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_appointments(self):
        """Open all appointments of this patient."""
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
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_book_with_primary_doctor(self):
        """
        Open appointment form pre-filled with patient & primary doctor.
        If no primary doctor, open with patient only.
        """
        self.ensure_one()
        if "clinic.appointment" not in self.env:
            return {"type": "ir.actions.client", "tag": "display_notification",
                    "params": {"title": _("Not Available"),
                               "message": _("Appointment module is not installed."),
                               "sticky": False}}
        ctx = {
            "default_patient_id": self.id,
            "default_partner_id": self.partner_id.id if "partner_id" in self._fields and self.partner_id else False,
            "default_company_id": self.company_id.id if "company_id" in self._fields else False,
        }
        if self.primary_doctor_id:
            ctx["default_doctor_id"] = self.primary_doctor_id.id
            # Preselect room/specialty if available
            if "default_room_id" in self.primary_doctor_id._fields and self.primary_doctor_id.default_room_id:
                ctx["default_room_id"] = self.primary_doctor_id.default_room_id.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Book Appointment"),
            "res_model": "clinic.appointment",
            "view_mode": "form",
            "target": "current",
            "context": ctx,
        }

    def action_view_preferred_doctors(self):
        """Open preferred doctors of this patient."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Preferred Doctors"),
            "res_model": "clinic.doctor",
            "view_mode": "tree,form,kanban,calendar",
            "domain": [("id", "in", self.preferred_doctor_ids.ids)],
            "target": "current",
        }


# -----------------------------------------------------------------------------
# EXTEND: clinic.doctor (backlink & actions) # dipindah ke file doctor.py masih dalam 1 addon
# -----------------------------------------------------------------------------
# class ClinicDoctor(models.Model):
#     _inherit = "clinic.doctor"

#     patient_ids = fields.Many2many(
#         "clinic.patient",
#         "clinic_patient_doctor_rel",      # same M2M table
#         "doctor_id",
#         "patient_id",
#         string="Patients",
#         help="Patients that marked this doctor as preferred (or primary)."
#     )
#     patient_count = fields.Integer(
#         compute="_compute_patient_count",
#         store=False,
#         help="Number of patients that prefer this doctor."
#     )

#     def _compute_patient_count(self):
#         for rec in self:
#             rec.patient_count = len(rec.patient_ids)

#     def action_view_patients(self):
#         self.ensure_one()
#         return {
#             "type": "ir.actions.act_window",
#             "name": _("Patients"),
#             "res_model": "clinic.patient",
#             "view_mode": "tree,form,kanban",
#             "domain": [("id", "in", self.patient_ids.ids)],
#             "target": "current",
#         }

#     def action_view_primary_patients(self):
#         """Open patients for whom this doctor is the primary doctor."""
#         self.ensure_one()
#         return {
#             "type": "ir.actions.act_window",
#             "name": _("Primary Patients"),
#             "res_model": "clinic.patient",
#             "view_mode": "tree,form,kanban",
#             "domain": [("primary_doctor_id", "=", self.id)],
#             "target": "current",
#         }


# -----------------------------------------------------------------------------
# EXTEND: clinic.appointment (partner ↔ patient consistency)
# -----------------------------------------------------------------------------
# class ClinicAppointment(models.Model):
#     _inherit = "clinic.appointment"

#     # NOTE: field patient_id is already defined in clinic_doctor/models/appointment.py.
#     # Here we only add consistency guards and convenience behavior.

#     @api.onchange("partner_id")
#     def _onchange_partner_bind_patient(self):
#         """
#         When a partner is chosen, bind the patient record automatically if:
#           - There is exactly one patient with that partner
#           - Or system parameter allows auto-create when none exists
#         """
#         Param = self.env["ir.config_parameter"].sudo()
#         auto_create = Param.get_param("clinic_doctor.auto_create_patient_on_appointment", "False") == "True"

#         for rec in self:
#             if not rec.partner_id:
#                 rec.patient_id = False
#                 continue
#             Patient = self.env["clinic.patient"]
#             candidates = Patient.search([("partner_id", "=", rec.partner_id.id)], limit=2)
#             if len(candidates) == 1:
#                 rec.patient_id = candidates.id
#             elif len(candidates) == 0 and auto_create:
#                 # Create patient shell linked to this partner
#                 patient = Patient.create({
#                     "name": rec.partner_id.name,
#                     "partner_id": rec.partner_id.id,
#                     "company_id": rec.company_id.id if rec.company_id else self.env.company.id,
#                 })
#                 rec.patient_id = patient.id
#             else:
#                 # multiple candidates — do nothing, let user choose
#                 rec.patient_id = False

#     @api.constrains("partner_id", "patient_id")
#     def _check_partner_patient_consistency(self):
#         """
#         Ensure appointment.partner_id matches patient.partner_id (if patient is set).
#         """
#         for rec in self:
#             if rec.patient_id and rec.partner_id and rec.patient_id.partner_id and rec.patient_id.partner_id != rec.partner_id:
#                 raise ValidationError(_("Appointment contact does not match the selected patient."))


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


# -*- coding: utf-8 -*-
# File: clinic_doctor/models/res_partner_inherit.py
# Module: clinic_doctor
#
# ClinicOne — res.partner extensions for Doctor Management (Odoo 19 CE ready)
#
# Purpose
# -------
# - Flag a contact as a Doctor (is_doctor)
# - Show linked Doctor records (company-aware), counters & next availability
# - Quick actions to open/create doctor records
# - Optional cross-module counters (appointments, treatments) guarded by presence checks
#
# Notes
# -----
# - This file does NOT create hard dependencies on other ClinicOne modules.
# - All strings are in English (product requirement).
# - Multi-company aware: one partner can be a doctor in multiple companies via multiple clinic.doctor records.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # DOCTOR FLAG & LINKS
    # -------------------------------------------------------------------------
    is_doctor = fields.Boolean(
        string="Is a Doctor",
        help="Enable this to indicate that this contact is a doctor."
    )
    doctor_ids = fields.One2many(
        "clinic.doctor",
        "partner_id",
        string="Doctor Records",
        help="Doctor records referencing this contact (one per company)."
    )
    doctor_count = fields.Integer(
        compute="_compute_doctor_links",
        store=False,
        help="Number of doctor records linked to this contact."
    )
    doctor_current_company_id = fields.Many2one(
        "clinic.doctor",
        compute="_compute_doctor_links",
        store=False,
        string="Doctor (Current Company)",
        help="Doctor record for the current company, if any."
    )

    # Convenience mirrors for current company doctor
    doctor_license_no = fields.Char(
        compute="_compute_doctor_links",
        store=False,
        help="License number from the current company's doctor record."
    )
    doctor_seniority = fields.Selection(
        [
            ("resident", "Resident"),
            ("junior", "Junior"),
            ("senior", "Senior"),
            ("consultant", "Consultant"),
        ],
        compute="_compute_doctor_links",
        store=False,
        help="Seniority level from the current company's doctor record."
    )
    doctor_specialty_names = fields.Char(
        compute="_compute_doctor_links",
        store=False,
        help="Comma-separated specialty names from the current company's doctor record."
    )

    # -------------------------------------------------------------------------
    # DOCTOR-CENTRIC KPIs (CURRENT COMPANY CONTEXT)
    # -------------------------------------------------------------------------
    appointment_count_as_doctor = fields.Integer(
        compute="_compute_doctor_kpis",
        store=False,
        help="Number of appointments where this contact acts as the doctor (current company)."
    )
    open_appointment_count_as_doctor = fields.Integer(
        compute="_compute_doctor_kpis",
        store=False,
        help="Number of non-closed appointments for this doctor (current company)."
    )
    next_available_slot_as_doctor = fields.Datetime(
        compute="_compute_doctor_kpis",
        store=False,
        help="Next available slot for this doctor (current company), if the availability module is installed."
    )
    # treatment_session_count_as_doctor = fields.Integer(
    #     compute="_compute_doctor_kpis",
    #     store=False,
    #     help="Number of treatment sessions performed by this doctor (current company; if the model exists)."
    # )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_doctor_links(self):
        """
        Compute:
          - doctor_count
          - doctor_current_company_id
          - doctor_license_no, doctor_seniority, doctor_specialty_names
        """
        company = self.env.company
        for rec in self:
            docs = rec.doctor_ids
            rec.doctor_count = len(docs)
            # current company doctor (there should be 0..1 by uniqueness in clinic.doctor)
            cur = docs.filtered(lambda d: d.company_id == company)[:1]
            rec.doctor_current_company_id = cur.id if cur else False

            # mirrors
            if cur:
                rec.doctor_license_no = cur.license_no or ""
                rec.doctor_seniority = cur.seniority_level or False
                rec.doctor_specialty_names = ", ".join(cur.mapped("specialty_ids.complete_name"))
            else:
                rec.doctor_license_no = ""
                rec.doctor_seniority = False
                rec.doctor_specialty_names = ""

    def _compute_doctor_kpis(self):
        """
        Compute KPIs for the current company doctor context:
          - appointments (all & open)
          - next availability
          - treatment session count (optional)
        """
        # Batch map partner_id -> doctor_id for current company
        partner_to_doc = {}
        for p in self:
            d = p.doctor_ids.filtered(lambda r: r.company_id == self.env.company)[:1]
            partner_to_doc[p.id] = d.id if d else False

        # Pre-fill zeros
        for rec in self:
            rec.appointment_count_as_doctor = 0
            rec.open_appointment_count_as_doctor = 0
            rec.treatment_session_count_as_doctor = 0
            rec.next_available_slot_as_doctor = False

        # Appointments (optional)
        if "clinic.appointment" in self.env:
            App = self.env["clinic.appointment"]
            doc_ids = [d for d in partner_to_doc.values() if d]
            if doc_ids:
                # all appointments
                g_all = App.read_group(
                    [("doctor_id", "in", doc_ids)],
                    ["doctor_id"],
                    ["doctor_id"],
                )
                map_all = {g["doctor_id"][0]: g["doctor_id_count"] for g in g_all}
                # open appointments (exclude terminal states)
                g_open = App.read_group(
                    [("doctor_id", "in", doc_ids), ("state", "not in", ["canceled", "done", "no_show"])],
                    ["doctor_id"],
                    ["doctor_id"],
                )
                map_open = {g["doctor_id"][0]: g["doctor_id_count"] for g in g_open}
                # assign to partner
                for rec in self:
                    did = partner_to_doc.get(rec.id)
                    if did:
                        rec.appointment_count_as_doctor = map_all.get(did, 0)
                        rec.open_appointment_count_as_doctor = map_open.get(did, 0)

        # Treatment sessions (optional)
        # if "clinic.procedure.session" in self.env:
        #     Sess = self.env["clinic.procedure.session"]
        #     doc_ids = [d for d in partner_to_doc.values() if d]
        #     if doc_ids:
        #         g_ts = Sess.read_group(
        #             [("doctor_id", "in", doc_ids)],
        #             ["doctor_id"],
        #             ["doctor_id"],
        #         )
        #         map_ts = {g["doctor_id"][0]: g["doctor_id_count"] for g in g_ts}
        #         for rec in self:
        #             did = partner_to_doc.get(rec.id)
        #             if did:
        #                 rec.treatment_session_count_as_doctor = map_ts.get(did, 0)

        # Next availability (optional)
        if "clinic.availability.slot" in self.env:
            Slot = self.env["clinic.availability.slot"]
            now = fields.Datetime.now()
            for rec in self:
                did = partner_to_doc.get(rec.id)
                if not did:
                    continue
                slot = Slot.search([
                    ("doctor_id", "=", did),
                    ("state", "=", "open") if "state" in Slot._fields else ("id", "!=", 0),
                    ("start", ">=", now),
                ], order="start asc", limit=1)
                rec.next_available_slot_as_doctor = slot.start if slot else False

    # -------------------------------------------------------------------------
    # BEHAVIOR — KEEP FLAG & LINKS CONSISTENT
    # -------------------------------------------------------------------------
    def _toggle_is_doctor_effects(self, new_value):
        """
        When toggling is_doctor off, deactivate doctor records for the current company.
        When toggling on, do nothing (doctor records are created from Doctor module to ensure license completeness).
        Behavior can be tuned via system parameters:
          - clinic_doctor.deactivate_doctor_on_unflag = True/False (default True)
        """
        Param = self.env["ir.config_parameter"].sudo()
        deactivate = Param.get_param("clinic_doctor.deactivate_doctor_on_unflag", "True") == "True"

        for rec in self:
            if not new_value and deactivate:
                doctors = rec.doctor_ids.filtered(lambda d: d.company_id == self.env.company and d.active)
                for d in doctors:
                    d.active = False

    def write(self, vals):
        # Intercept is_doctor flips for behavior
        flip = "is_doctor" in vals
        res = super().write(vals)
        if flip:
            # Apply effects per record (vals['is_doctor'] is uniform for all in self)
            self._toggle_is_doctor_effects(bool(vals.get("is_doctor")))
        return res

    # -------------------------------------------------------------------------
    # QUICK ACTIONS
    # -------------------------------------------------------------------------
    def action_view_doctor_records(self):
        """
        Open clinic.doctor records linked to this partner.
        """
        self.ensure_one()
        if "clinic.doctor" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Doctor module is not installed."),
                           "sticky": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Doctor Records"),
            "res_model": "clinic.doctor",
            "view_mode": "tree,form,kanban",
            "domain": [("partner_id", "=", self.id)],
            "target": "current",
            "context": {
                "default_partner_id": self.id,
            },
        }

    def action_open_current_company_doctor(self):
        """
        Open the doctor record for the current company (if any),
        otherwise open the create form with defaults.
        """
        self.ensure_one()
        if "clinic.doctor" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Doctor module is not installed."),
                           "sticky": False},
            }
        doc = self.doctor_ids.filtered(lambda d: d.company_id == self.env.company)[:1]
        if doc:
            return {
                "type": "ir.actions.act_window",
                "name": _("Doctor"),
                "res_model": "clinic.doctor",
                "view_mode": "form",
                "res_id": doc.id,
                "target": "current",
            }
        # else open create form
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Doctor"),
            "res_model": "clinic.doctor",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.id,
                "default_company_id": self.env.company.id,
            },
        }

    def action_view_doctor_appointments(self):
        """
        Open appointments where this contact acts as a doctor (current company).
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
        # Resolve current company doctor
        doc = self.doctor_ids.filtered(lambda d: d.company_id == self.env.company)[:1]
        if not doc:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("No Doctor"),
                           "message": _("This contact has no doctor record in the current company."),
                           "sticky": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Appointments"),
            "res_model": "clinic.appointment",
            "view_mode": "calendar,tree,form,pivot,graph",
            "domain": [("doctor_id", "=", doc.id)],
            "target": "current",
        }

    def action_view_next_availability(self):
        """
        Show the next available slot for this doctor (current company), if availability model exists.
        """
        self.ensure_one()
        if "clinic.availability.slot" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Availability module is not installed."),
                           "sticky": False},
            }
        doc = self.doctor_ids.filtered(lambda d: d.company_id == self.env.company)[:1]
        if not doc:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("No Doctor"),
                           "message": _("This contact has no doctor record in the current company."),
                           "sticky": False},
            }
        domain = [("doctor_id", "=", doc.id)]
        if "state" in self.env["clinic.availability.slot"]._fields:
            domain += [("state", "=", "open")]
        if self.next_available_slot_as_doctor:
            domain += [("start", ">=", self.next_available_slot_as_doctor)]
        return {
            "type": "ir.actions.act_window",
            "name": _("Availability"),
            "res_model": "clinic.availability.slot",
            "view_mode": "calendar,tree,form",
            "domain": domain,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # OPTIONAL HR BRIDGE (READ-ONLY MIRRORS)
    # -------------------------------------------------------------------------
    hr_employee_id = fields.Many2one(
        "hr.employee",
        compute="_compute_hr_bridge",
        store=False,
        string="Employee (Bridge)",
        help="Employee record linked via clinic_doctor_hr bridge (if installed and configured)."
    )
    has_hr_employee = fields.Boolean(
        compute="_compute_hr_bridge",
        store=False,
        help="True if this contact is a doctor and has a linked employee via the HR bridge."
    )

    def _compute_hr_bridge(self):
        """
        Expose HR employee linkage if bridge is installed.
        The bridge typically places employee_id on clinic.doctor.
        """
        for rec in self:
            rec.hr_employee_id = False
            rec.has_hr_employee = False
            if "hr.employee" not in self.env or "clinic.doctor" not in self.env:
                continue
            # read from current company doctor
            doc = rec.doctor_ids.filtered(lambda d: d.company_id == self.env.company)[:1]
            if doc and "employee_id" in doc._fields and doc.employee_id:
                rec.hr_employee_id = doc.employee_id.id
                rec.has_hr_employee = True

    # -------------------------------------------------------------------------
    # CONVENIENCE: VALIDATION / HELPERS
    # -------------------------------------------------------------------------
    @api.constrains("is_company", "is_doctor")
    def _check_is_company_flag(self):
        """
        Soft policy: a doctor contact should ideally be an individual (person), not a company.
        Enforce as ValidationError if you want hard policy; here we only warn in chatter.
        """
        for rec in self:
            if rec.is_doctor and rec.is_company:
                # Post a message instead of blocking to avoid friction in data imports
                rec.message_post(body=_(
                    "This contact is flagged as a Doctor but is marked as a Company. "
                    "It is recommended to use an individual contact for doctors."
                ))

    # Public helper
    def get_current_company_doctor(self):
        """
        Return the clinic.doctor record for this partner in the current company, or False.
        """
        self.ensure_one()
        return self.doctor_ids.filtered(lambda d: d.company_id == self.env.company)[:1] or False



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


# -*- coding: utf-8 -*-
# File: clinic_doctor/models/schedule_rule.py
# Module: clinic_doctor
#
# ClinicOne — Schedule Rule (Odoo 19 CE ready)
#
# Purpose
# -------
# Weekly/recurring template that materializes concrete availability slots for doctors.
# The rule can target a doctor (required) and optionally a room & specialty. It supports:
# - Effective dates (date_start/date_end), week interval (e.g., every 2 weeks)
# - Float time in 24h format (start/end), slot duration, buffers
# - Capacity overrides per slot
# - Holiday/leave skipping (doctor leaves and resource calendar leaves)
# - Telemedicine-only rules
# - Holistic integration with other ClinicOne addons via guarded env checks
#
# Notes
# -----
# * All labels/help/messages use English (product requirement).
# * Timezone: rules are interpreted in a "local" timezone (rule_tz) and converted to UTC for storage.
#   Default tz is the doctor's user tz, else company tz, else 'UTC'.
# * This file assumes presence of `clinic.availability.slot` model for materialization.
#   If not installed, actions gracefully notify users.

from datetime import date, datetime, timedelta
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


WEEKDAY_SELECTION = [
    ("0", "Monday"),
    ("1", "Tuesday"),
    ("2", "Wednesday"),
    ("3", "Thursday"),
    ("4", "Friday"),
    ("5", "Saturday"),
    ("6", "Sunday"),
]


class ClinicScheduleRule(models.Model):
    _name = "clinic.schedule.rule"
    _description = "Doctor Schedule Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, doctor_id, weekday, start_time, id"

    # -------------------------------------------------------------------------
    # IDENTITY & SCOPE
    # -------------------------------------------------------------------------
    name = fields.Char(
        required=False,
        tracking=True,
        help="Friendly name for this rule. If left blank, a name is autogenerated."
    )
    sequence = fields.Integer(
        default=10,
        help="Display order."
    )
    active = fields.Boolean(
        default=True,
        help="Disable to stop generating availability from this rule."
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
        help="Company for which this rule is applicable."
    )

    # -------------------------------------------------------------------------
    # TARGETS
    # -------------------------------------------------------------------------
    doctor_id = fields.Many2one(
        "clinic.doctor",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
        help="Doctor this rule belongs to."
    )
    room_id = fields.Many2one(
        "clinic.room",
        ondelete="set null",
        index=True,
        help="Optional room target for this rule."
    )
    specialty_id = fields.Many2one(
        "clinic.specialty",
        ondelete="set null",
        help="Optional specialty context/filter for this rule."
    )
    telemedicine_only = fields.Boolean(
        default=False,
        help="If enabled, the rule generates telemedicine (virtual) slots only."
    )

    # -------------------------------------------------------------------------
    # RECURRENCE (WEEKLY)
    # -------------------------------------------------------------------------
    weekday = fields.Selection(
        WEEKDAY_SELECTION,
        required=True,
        default="0",
        help="Weekday for this recurring rule."
    )
    interval_weeks = fields.Integer(
        default=1,
        help="Repeat every N weeks (1=every week, 2=every other week, etc.)."
    )
    date_start = fields.Date(
        help="First date when this rule takes effect. If empty, starts immediately."
    )
    date_end = fields.Date(
        help="Last date (inclusive) when this rule applies. If empty, no end date."
    )

    # -------------------------------------------------------------------------
    # TIME WINDOW (FLOAT TIME IN 24H)
    # -------------------------------------------------------------------------
    start_time = fields.Float(
        required=True,
        help="Start time in 24h float format (e.g., 9.0 = 09:00, 13.5 = 13:30)."
    )
    end_time = fields.Float(
        required=True,
        help="End time in 24h float format (must be greater than Start time)."
    )
    slot_duration_min = fields.Integer(
        default=30,
        help="Duration of each availability slot in minutes."
    )
    buffer_before_min = fields.Integer(
        default=0,
        help="Optional preparation buffer before each slot (minutes)."
    )
    buffer_after_min = fields.Integer(
        default=0,
        help="Optional cleanup buffer after each slot (minutes)."
    )
    capacity_per_slot = fields.Integer(
        default=0,
        help="Capacity override per slot. Set 0 to inherit from the doctor's default capacity."
    )

    # Computed next run datetime (for UX/cron visibility)
    next_occurrence_utc = fields.Datetime(
        compute="_compute_next_occurrence",
        store=False,
        help="Next date-time when this rule is expected to produce availability (UTC)."
    )

    # -------------------------------------------------------------------------
    # POLICIES
    # -------------------------------------------------------------------------
    skip_on_doctor_leave = fields.Boolean(
        default=True,
        help="Skip slot generation if the doctor has a leave overlapping the occurrence."
    )
    skip_on_calendar_leave = fields.Boolean(
        default=True,
        help="Skip slot generation if the doctor's calendar has a leave overlapping the occurrence."
    )
    allow_overlap_slots = fields.Boolean(
        default=False,
        help="If enabled, the generator won't skip when overlapping availability slots already exist."
    )
    conflict_policy = fields.Selection(
        [
            ("skip", "Skip on Conflicts"),
            ("soft", "Soft Warn (still create)"),
        ],
        default="skip",
        help="How to react to conflicts with room restrictions or appointments during generation."
    )

    # Preferred timezone for rule interpretation (optional)
    rule_tz = fields.Char(
        help="Timezone used to interpret start/end times and compute occurrences. "
             "Defaults to Doctor's User timezone, else Company timezone, else UTC."
    )

    color = fields.Integer(help="Color index for quick visual reference in list view.")

    # -------------------------------------------------------------------------
    # CONSTRAINTS & ONCHANGES
    # -------------------------------------------------------------------------
    @api.constrains("start_time", "end_time")
    def _check_time_window(self):
        for rec in self:
            if rec.start_time is None or rec.end_time is None:
                raise ValidationError(_("Start time and End time are required."))
            if rec.start_time < 0 or rec.start_time >= 24 or rec.end_time <= 0 or rec.end_time > 24:
                raise ValidationError(_("Start/End times must be within [0, 24] hours."))
            if rec.end_time <= rec.start_time:
                raise ValidationError(_("End time must be greater than Start time."))

    @api.constrains("slot_duration_min", "buffer_before_min", "buffer_after_min", "capacity_per_slot")
    def _check_positive_values(self):
        for rec in self:
            if rec.slot_duration_min <= 0:
                raise ValidationError(_("Slot duration must be a positive integer."))
            if rec.buffer_before_min < 0 or rec.buffer_after_min < 0:
                raise ValidationError(_("Buffers cannot be negative."))
            if rec.capacity_per_slot < 0:
                raise ValidationError(_("Capacity per slot cannot be negative. Use 0 to inherit doctor capacity."))

    @api.constrains("interval_weeks")
    def _check_interval_weeks(self):
        for rec in self:
            if rec.interval_weeks <= 0:
                raise ValidationError(_("Interval (weeks) must be at least 1."))

    @api.constrains("date_start", "date_end")
    def _check_date_range(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("End date cannot be earlier than Start date."))

    @api.onchange("doctor_id", "weekday", "start_time", "end_time", "room_id", "telemedicine_only")
    def _onchange_autoname(self):
        for rec in self:
            if not rec.doctor_id or rec.start_time is None or rec.end_time is None:
                continue
            wd = dict(WEEKDAY_SELECTION).get(rec.weekday or "0", "Monday")
            label_room = rec.room_id.display_name if rec.room_id else _("No Room")
            label_mode = _("Telemedicine") if rec.telemedicine_only else _("Onsite")
            rec.name = _("%(doc)s — %(dow)s %(start)s–%(end)s (%(mode)s, %(room)s)") % {
                "doc": rec.doctor_id.display_name,
                "dow": wd,
                "start": rec._float_to_hhmm(rec.start_time),
                "end": rec._float_to_hhmm(rec.end_time),
                "mode": label_mode,
                "room": label_room,
            }

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_next_occurrence(self):
        now_utc = fields.Datetime.now()
        for rec in self:
            nxt = rec._find_next_occurrence(start_from=now_utc)
            rec.next_occurrence_utc = nxt

    # -------------------------------------------------------------------------
    # TIMEZONE & TIME HELPERS
    # -------------------------------------------------------------------------
    def _get_rule_tzname(self):
        """Choose the timezone used to interpret start/end times."""
        self.ensure_one()
        # 1) explicit rule_tz
        if self.rule_tz:
            return self.rule_tz
        # 2) doctor's user tz
        if self.doctor_id and self.doctor_id.user_id and self.doctor_id.user_id.tz:
            return self.doctor_id.user_id.tz
        # 3) company tz
        if self.company_id and self.company_id.partner_id and self.company_id.partner_id.tz:
            return self.company_id.partner_id.tz
        # 4) fallback
        return "UTC"

    @staticmethod
    def _float_to_hhmm(value):
        """Convert 13.5 → '13:30'."""
        hours = int(value)
        minutes = int(round((value - hours) * 60.0))
        return f"{hours:02d}:{minutes:02d}"

    @staticmethod
    def _hhmm_to_float(hhmm):
        """Convert '13:30' → 13.5."""
        hh, mm = hhmm.split(":")
        return float(int(hh)) + float(int(mm)) / 60.0

    def _compose_occurrence_local(self, base_date):
        """
        Build localized datetimes from base_date (a date in local tz) + float times.
        Returns (dt_start_local, dt_end_local) in the rule tz (tz-aware).
        """
        self.ensure_one()
        tzname = self._get_rule_tzname()
        tz = timezone(tzname)

        start_h = int(self.start_time)
        start_m = int(round((self.start_time - start_h) * 60))
        end_h = int(self.end_time)
        end_m = int(round((self.end_time - end_h) * 60))

        dt_start_local = tz.localize(datetime(base_date.year, base_date.month, base_date.day, start_h, start_m, 0))
        dt_end_local = tz.localize(datetime(base_date.year, base_date.month, base_date.day, end_h, end_m, 0))
        return dt_start_local, dt_end_local

    # -------------------------------------------------------------------------
    # OCCURRENCE GENERATION
    # -------------------------------------------------------------------------
    def _iter_occurrences(self, date_from, date_to):
        """
        Yield (start_utc, end_utc) datetimes for every matching weekday between date_from and date_to
        observing interval_weeks and date_start/date_end boundaries.
        """
        self.ensure_one()
        if not date_from or not date_to:
            return
        if date_to < date_from:
            return

        # Guard by rule-level date range
        eff_start = self.date_start or date_from
        eff_end = self.date_end or date_to
        if eff_end < date_from or eff_start > date_to:
            return

        # align the first candidate date to the selected weekday
        wd_target = int(self.weekday)
        # Start iterating from max(date_from, date_start)
        cur = max(date_from, eff_start)

        # Move cur to the target weekday
        delta_days = (wd_target - cur.weekday()) % 7
        cur = cur + timedelta(days=delta_days)

        tzname = self._get_rule_tzname()
        tz = timezone(tzname)

        # Compute week span in days
        span_days = self.interval_weeks * 7

        while cur <= min(date_to, eff_end):
            # build local-aware datetimes, then convert to UTC
            dt_start_local, dt_end_local = self._compose_occurrence_local(cur)
            start_utc = dt_start_local.astimezone(UTC).replace(tzinfo=None)
            end_utc = dt_end_local.astimezone(UTC).replace(tzinfo=None)
            yield (start_utc, end_utc)
            cur = cur + timedelta(days=span_days)

    # -------------------------------------------------------------------------
    # CONFLICTS & POLICIES
    # -------------------------------------------------------------------------
    def _has_doctor_leave_conflict(self, start_utc, end_utc):
        """Return True if the doctor has a leave overlapping the [start,end] window."""
        if not self.skip_on_doctor_leave or "clinic.doctor.leave" not in self.env:
            return False
        Leave = self.env["clinic.doctor.leave"]
        return bool(Leave.search_count([
            ("doctor_id", "=", self.doctor_id.id),
            ("date_from", "<", end_utc),
            ("date_to", ">", start_utc),
        ], limit=1))

    def _has_calendar_leave_conflict(self, start_utc, end_utc):
        """Return True if the doctor's calendar has a leave overlapping the [start,end] window."""
        if not self.skip_on_calendar_leave:
            return False
        cal = self.doctor_id.calendar_id
        if not cal or "resource.calendar.leaves" not in self.env:
            return False
        CalLeave = self.env["resource.calendar.leaves"]
        return bool(CalLeave.search_count([
            ("calendar_id", "=", cal.id),
            ("date_from", "<", end_utc),
            ("date_to", ">", start_utc),
        ], limit=1))

    def _room_allows_specialty(self):
        """Check room's allowed_specialty_ids policy (if any)."""
        if not self.room_id:
            return True
        # room inheritance provided by clinic_doctor adds allowed_specialty_ids
        if "allowed_specialty_ids" in self.room_id._fields and self.room_id.allowed_specialty_ids:
            if self.specialty_id and self.specialty_id.id in self.room_id.allowed_specialty_ids.ids:
                return True
            # If rule has no specialty, allow by default (room-level filter only applies if explicit).
            return False if self.specialty_id else True
        return True

    def _find_existing_slot(self, start_utc, end_utc):
        """Find an existing availability slot with the exact same window."""
        if "clinic.availability.slot" not in self.env:
            return False
        Slot = self.env["clinic.availability.slot"]
        domain = [
            ("doctor_id", "=", self.doctor_id.id),
            ("start", "=", start_utc),
            ("end", "=", end_utc),
        ]
        if self.room_id:
            domain.append(("room_id", "=", self.room_id.id))
        return Slot.search(domain, limit=1)

    def _has_overlapping_slot(self, start_utc, end_utc):
        """Return True if there is any overlapping availability slot (any state)."""
        if "clinic.availability.slot" not in self.env:
            return False
        Slot = self.env["clinic.availability.slot"]
        domain = [
            ("doctor_id", "=", self.doctor_id.id),
            ("start", "<", end_utc),
            ("end", ">", start_utc),
        ]
        if self.room_id:
            domain.append(("room_id", "=", self.room_id.id))
        return bool(Slot.search_count(domain, limit=1))

    # def _has_overlapping_appointment(self, start_utc, end_utc):
    #     """Return True if an appointment overlaps the window (non-terminal states)."""
    #     if "clinic.appointment" not in self.env:
    #         return False
    #     App = self.env["clinic.appointment"]
    #     domain = [
    #         ("doctor_id", "=", self.doctor_id.id),
    #         ("state", "not in", ["canceled", "done", "no_show"]),
    #         ("start", "<", end_utc),
    #         ("end", ">", start_utc),
    #     ]
    #     if self.room_id and "room_id" in App._fields:
    #         domain.append(("room_id", "=", self.room_id.id))
    #     return bool(App.search_count(domain, limit=1))

    # -------------------------------------------------------------------------
    # SLOT MATERIALIZATION
    # -------------------------------------------------------------------------
    def _prepare_slot_vals(self, start_utc, end_utc):
        """Map rule → clinic.availability.slot create values."""
        self.ensure_one()
        capacity = self.capacity_per_slot or self.doctor_id.capacity_per_slot or 1
        vals = {
            "doctor_id": self.doctor_id.id,
            "start": start_utc,
            "end": end_utc,
            "capacity": capacity,
            "state": "open",  # default state
            "company_id": self.company_id.id,
            "telemedicine": self.telemedicine_only if "telemedicine" in self.env["clinic.availability.slot"]._fields else False,
        }
        if self.room_id and "room_id" in self.env["clinic.availability.slot"]._fields:
            vals["room_id"] = self.room_id.id
        if self.specialty_id and "specialty_id" in self.env["clinic.availability.slot"]._fields:
            vals["specialty_id"] = self.specialty_id.id
        # Optional buffers if slot model supports them
        Slot = self.env["clinic.availability.slot"]
        if "buffer_before_min" in Slot._fields:
            vals["buffer_before_min"] = self.buffer_before_min
        if "buffer_after_min" in Slot._fields:
            vals["buffer_after_min"] = self.buffer_after_min
        return vals

    def _materialize_occurrence(self, start_utc, end_utc, results):
        """
        Create a sequence of slots of length slot_duration_min within [start,end],
        respecting buffers. Append report entries to `results`.
        """
        if "clinic.availability.slot" not in self.env:
            results["skipped_missing_model"] += 1
            return

        # Conflict: leaves
        skip_leave = self._has_doctor_leave_conflict(start_utc, end_utc) or self._has_calendar_leave_conflict(start_utc, end_utc)
        if skip_leave:
            results["skipped_leave"] += 1
            return

        # Conflict: room specialty policy
        if not self._room_allows_specialty():
            if self.conflict_policy == "skip":
                results["skipped_room_restrict"] += 1
                return
            results["soft_conflicts"].append(_("Room restriction ignored (soft policy)."))

        # Existing identical slot
        if self._find_existing_slot(start_utc, end_utc):
            results["skipped_existing"] += 1
            return

        # Overlapping slots
        if not self.allow_overlap_slots and self._has_overlapping_slot(start_utc, end_utc):
            results["skipped_overlap_slot"] += 1
            return

        # Appointments overlapping (avoid generating open slots that collide)
        # if self.conflict_policy == "skip" and self._has_overlapping_appointment(start_utc, end_utc):
        #     results["skipped_overlap_appt"] += 1
        #     return

        # Build micro-slots (slot_duration_min segments)
        cur = start_utc
        delta = timedelta(minutes=self.slot_duration_min)
        Slot = self.env["clinic.availability.slot"].sudo()
        created = 0

        while cur < end_utc:
            cur_end = min(end_utc, cur + delta)
            vals = self._prepare_slot_vals(cur, cur_end)
            Slot.create(vals)
            created += 1
            cur = cur_end

        results["created"] += created

    # Public API
    def generate_slots(self, date_from=None, date_to=None):
        """
        Materialize availability slots for this rule between date_from and date_to (both inclusive).
        If not provided, defaults to [today .. today + 30 days].
        Returns a summary dict.
        """
        self.ensure_one()
        if not self.active:
            raise UserError(_("This rule is inactive."))

        if date_from is None or date_to is None:
            today = fields.Date.context_today(self)
            date_from = date_from or today
            date_to = date_to or (today + timedelta(days=30))

        if not isinstance(date_from, date):
            raise UserError(_("date_from must be a date."))
        if not isinstance(date_to, date):
            raise UserError(_("date_to must be a date."))
        if date_to < date_from:
            raise UserError(_("date_to cannot be earlier than date_from."))

        results = {
            "created": 0,
            "skipped_leave": 0,
            "skipped_existing": 0,
            "skipped_overlap_slot": 0,
            "skipped_overlap_appt": 0,
            "skipped_missing_model": 0,
            "skipped_room_restrict": 0,
            "soft_conflicts": [],
        }

        for start_utc, end_utc in self._iter_occurrences(date_from, date_to):
            self._materialize_occurrence(start_utc, end_utc, results)

        return results

    # Batch API
    def batch_generate_slots(self, date_from=None, date_to=None):
        """
        Generate slots for all selected rules and return an aggregate summary.
        """
        summary = {
            "created": 0,
            "skipped_leave": 0,
            "skipped_existing": 0,
            "skipped_overlap_slot": 0,
            "skipped_overlap_appt": 0,
            "skipped_missing_model": 0,
            "skipped_room_restrict": 0,
            "soft_conflicts": [],
            "rules": {},
        }
        for rec in self:
            res = rec.generate_slots(date_from=date_from, date_to=date_to)
            summary["rules"][rec.id] = res
            for k in ("created", "skipped_leave", "skipped_existing", "skipped_overlap_slot",
                      "skipped_overlap_appt", "skipped_missing_model", "skipped_room_restrict"):
                summary[k] += res[k]
            summary["soft_conflicts"] += res["soft_conflicts"]
        return summary

    # Cron-friendly method (context may pass window)
    def cron_generate_slots(self):
        """
        Called by scheduler/cron with context keys:
            ctx['date_from'] (date) and ctx['date_to'] (date)
        Falls back to [today .. today+30] if not provided.
        """
        ctx = self.env.context or {}
        date_from = ctx.get("date_from")
        date_to = ctx.get("date_to")

        # Convert from strings if necessary
        if isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        rules = self.search([("active", "=", True)])
        return rules.batch_generate_slots(date_from=date_from, date_to=date_to)

    # UX Actions
    def action_generate_slots(self):
        """
        UI button: Generate slots for a selected period (reads context date range).
        """
        self.ensure_one()
        ctx = self.env.context or {}
        date_from = ctx.get("date_from")
        date_to = ctx.get("date_to")
        if isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        res = self.generate_slots(date_from=date_from, date_to=date_to)
        # Notify user
        msg = _(
            "Slot generation completed.\n"
            "Created: %(c)s\n"
            "Skipped (leave): %(l)s\n"
            "Skipped (existing): %(e)s\n"
            "Skipped (overlap slot): %(os)s\n"
            "Skipped (overlap appt): %(oa)s\n"
            "Skipped (missing model): %(mm)s\n"
            "Skipped (room restrict): %(rr)s\n"
            "Notes: %(notes)s",
            c=res["created"], l=res["skipped_leave"], e=res["skipped_existing"],
            os=res["skipped_overlap_slot"], oa=res["skipped_overlap_appt"],
            mm=res["skipped_missing_model"], rr=res["skipped_room_restrict"],
            notes=", ".join(res["soft_conflicts"]) or "-",
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Schedule Rule"), "message": msg, "sticky": False},
        }

    def action_view_generated_slots(self):
        """Open generated availability slots filtered by this rule's dimensions."""
        self.ensure_one()
        if "clinic.availability.slot" not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Not Available"),
                           "message": _("Availability model is not installed."),
                           "sticky": False},
            }
        domain = [("doctor_id", "=", self.doctor_id.id)]
        if self.room_id and "room_id" in self.env["clinic.availability.slot"]._fields:
            domain.append(("room_id", "=", self.room_id.id))
        if self.specialty_id and "specialty_id" in self.env["clinic.availability.slot"]._fields:
            domain.append(("specialty_id", "=", self.specialty_id.id))
        return {
            "type": "ir.actions.act_window",
            "name": _("Availability"),
            "res_model": "clinic.availability.slot",
            "view_mode": "calendar,tree,form",
            "domain": domain,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # NEXT OCCURRENCE FINDER
    # -------------------------------------------------------------------------
    def _find_next_occurrence(self, start_from=None):
        """
        Return the next occurrence datetime in UTC (start) after start_from (UTC naive),
        or False if none (due to date_end or inactive).
        """
        self.ensure_one()
        if not self.active:
            return False

        start_from = start_from or fields.Datetime.now()
        base_date = start_from.date()
        # Iterate up to a reasonable horizon (1 year) for safety
        horizon = base_date + timedelta(days=365)
        for start_utc, _end_utc in self._iter_occurrences(base_date, horizon):
            if start_utc >= start_from:
                return start_utc
        return False


# -*- coding: utf-8 -*-
# File: clinic_doctor/models/specialty.py
# Module: clinic_doctor
#
# ClinicOne — Specialty catalog (Odoo 19 CE ready)
#
# Purpose
# -------
# Centralized catalog of doctor specialties used across the ClinicOne suite:
# - Assign specialties to doctors
# - (Optionally) scope treatments/services/pricing by specialty
# - Support search, hierarchy, KPIs, and navigation actions
#
# Integration
# -----------
# This model is intentionally lightweight with *optional* cross-module hooks.
# It does NOT hard-depend on the other modules; instead it checks presence via `"model" in self.env`.
# Example optional integrations:
# - clinic_treatment:     clinic.treatment (M2O -> specialty_id) / clinic.procedure.session
# - clinic_pricing:       clinic.treatment.pricelist.item (M2O -> specialty_id), price rules by specialty
# - clinic_booking:       patient-facing booking filtered by specialty
# - clinic_inventory:     product(s) associated to a specialty (if implemented)
# - clinic_reports:       KPIs that aggregate by specialty
#
# Notes
# -----
# - All field labels, help, and messages are in English (product requirement).
# - Designed for multi-company environments with company-scoped uniqueness.
# - Uses mail.thread/activity for collaboration and auditability.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicSpecialty(models.Model):
    _name = "clinic.specialty"
    _description = "Doctor Specialty"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _parent_name = "parent_id"
    _parent_store = True
    _order = "sequence, complete_name, id"

    # -------------------------------------------------------------------------
    # IDENTITY & PRESENTATION
    # -------------------------------------------------------------------------
    name = fields.Char(
        required=True,
        tracking=True,
        translate=True,
        help="Specialty name, e.g., Dermatology, Aesthetic Medicine, Dentistry."
    )
    code = fields.Char(
        required=True,
        index=True,
        tracking=True,
        help="Short unique code for the specialty within the company, e.g., DERM, AESTH."
    )
    description = fields.Text(
        tracking=False,
        help="Internal description or notes about the scope of this specialty."
    )
    image_1920 = fields.Image(
        help="Optional icon or representative image for this specialty."
    )
    color = fields.Integer(
        help="Color index to visually distinguish specialties in list/kanban."
    )
    sequence = fields.Integer(
        default=10,
        help="Display order of specialties."
    )
    active = fields.Boolean(
        default=True,
        help="Disable a specialty to hide it from selection without deleting historical data."
    )

    # -------------------------------------------------------------------------
    # COMPANY SCOPE
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        help="Company that this specialty belongs to."
    )

    # -------------------------------------------------------------------------
    # HIERARCHY
    # -------------------------------------------------------------------------
    parent_id = fields.Many2one(
        "clinic.specialty",
        index=True,
        ondelete="restrict",
        help="Parent specialty in the hierarchy."
    )
    child_ids = fields.One2many(
        "clinic.specialty",
        "parent_id",
        string="Subspecialties",
        help="Subspecialties under this specialty."
    )
    parent_path = fields.Char(index=True)
    complete_name = fields.Char(
        compute="_compute_complete_name",
        store=True,
        help="Full hierarchical path, e.g., 'Aesthetics / Injectables'."
    )

    # -------------------------------------------------------------------------
    # RELATIONS
    # -------------------------------------------------------------------------
    # doctor_ids = fields.Many2many(
    #     "clinic.doctor",
    #     "clinic_doctor_specialty_rel",  # MUST match relation used by clinic.doctor.specialty_ids
    #     "specialty_id",
    #     "doctor_id",
    #     string="Doctors",
    #     help="Doctors that practice this specialty."
    # )
    # doctor_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of doctors linked to this specialty."
    # )

    # Optional: link to treatments (when Treatment module is present)
    # treatment_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of treatments linked to this specialty (if the model exists)."
    # )
    # treatment_session_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of treatment sessions linked to this specialty (if the model exists)."
    # )

    # Optional: link to pricing items (when Pricing module is present)
    # pricing_item_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of pricing items referencing this specialty (if the model exists)."
    # )

    # Optional: link to inventory products (when Inventory/Products-by-specialty is present)
    # product_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of products linked to this specialty (if your inventory module provides it)."
    # )

    # Optional: booking statistics (if booking/appointment adopts specialty dimension)
    # appointment_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of appointments associated with this specialty (if the model provides the link)."
    # )

    # KPIs placeholders (can be updated by reporting/cron jobs)
    kpi_monthly_revenue = fields.Monetary(
        currency_field="currency_id",
        help="Monthly revenue attributed to this specialty (populated by reporting jobs)."
    )
    kpi_monthly_volume = fields.Integer(
        help="Monthly count of services for this specialty (populated by reporting jobs)."
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id.id,
        help="Currency for KPI monetary values."
    )

    employee_ids = fields.Many2many(
        "hr.employee",
        relation="clinic_specialty_employee_rel",
        column1="specialty_id",   # mirror
        column2="employee_id",    # mirror
        string="Doctors",
    )

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)",
         "Specialty code must be unique per company."),
        ("name_company_uniq", "unique(name, company_id)",
         "Specialty name must be unique per company."),
    ]

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("name", "parent_id", "parent_id.complete_name")
    def _compute_complete_name(self):
        for rec in self:
            if rec.parent_id:
                parent = rec.parent_id.complete_name or rec.parent_id.name or ""
                rec.complete_name = "%s / %s" % (parent, rec.name or "")
            else:
                rec.complete_name = rec.name or ""

    # @api.depends(
    #     "doctor_ids",
    #     # One2many proxies are not explicitly declared to avoid hard depends; we compute via read_group when present
    # )
    # def _compute_counts(self):
    #     """Aggregate counts across optional modules if installed."""
    #     ids = self.ids or []
    #     # --- doctor_count via SQL on relation table (fast)
    #     doc_map = {sid: 0 for sid in ids}
    #     if ids:
    #         self.env.cr.execute("""
    #             SELECT specialty_id, COUNT(*)
    #               FROM clinic_doctor_specialty_rel
    #              WHERE specialty_id = ANY(%s)
    #           GROUP BY specialty_id
    #         """, [ids])
    #         for sid, cnt in self.env.cr.fetchall():
    #             doc_map[sid] = cnt

    #     # --- treatment_count (optional: clinic.treatment with M2O specialty_id)
    #     treat_map = {sid: 0 for sid in ids}
    #     if ids and "clinic.treatment" in self.env:
    #         groups = self.env["clinic.treatment"].read_group(
    #             [("specialty_id", "in", ids)],
    #             ["specialty_id"],
    #             ["specialty_id"],
    #         )
    #         treat_map.update({g["specialty_id"][0]: g["specialty_id_count"] for g in groups})

    #     # --- treatment_session_count (optional: clinic.procedure.session with M2O specialty_id)
    #     ts_map = {sid: 0 for sid in ids}
    #     if ids and "clinic.procedure.session" in self.env:
    #         groups = self.env["clinic.procedure.session"].read_group(
    #             [("specialty_id", "in", ids)],
    #             ["specialty_id"],
    #             ["specialty_id"],
    #         )
    #         ts_map.update({g["specialty_id"][0]: g["specialty_id_count"] for g in groups})

    #     # --- pricing_item_count (optional: clinic.treatment.pricelist.item with M2O specialty_id)
    #     price_map = {sid: 0 for sid in ids}
    #     if ids and "clinic.treatment.pricelist.item" in self.env:
    #         groups = self.env["clinic.treatment.pricelist.item"].read_group(
    #             [("specialty_id", "in", ids)],
    #             ["specialty_id"],
    #             ["specialty_id"],
    #         )
    #         price_map.update({g["specialty_id"][0]: g["specialty_id_count"] for g in groups})

    #     # --- product_count (optional: product.template with M2O specialty_id if module provides it)
    #     prod_map = {sid: 0 for sid in ids}
    #     # try both product.template and product.product integration variants
    #     if ids and "product.template" in self.env and "specialty_id" in self.env["product.template"]._fields:
    #         groups = self.env["product.template"].read_group(
    #             [("specialty_id", "in", ids)],
    #             ["specialty_id"],
    #             ["specialty_id"],
    #         )
    #         prod_map.update({g["specialty_id"][0]: g["specialty_id_count"] for g in groups})
    #     elif ids and "product.product" in self.env and "specialty_id" in self.env["product.product"]._fields:
    #         groups = self.env["product.product"].read_group(
    #             [("specialty_id", "in", ids)],
    #             ["specialty_id"],
    #             ["specialty_id"],
    #         )
    #         prod_map.update({g["specialty_id"][0]: g["specialty_id_count"] for g in groups})

    #     # --- appointment_count (optional: clinic.appointment with M2O specialty_id)
    #     appt_map = {sid: 0 for sid in ids}
    #     if ids and "clinic.appointment" in self.env and "specialty_id" in self.env["clinic.appointment"]._fields:
    #         groups = self.env["clinic.appointment"].read_group(
    #             [("specialty_id", "in", ids)],
    #             ["specialty_id"],
    #             ["specialty_id"],
    #         )
    #         appt_map.update({g["specialty_id"][0]: g["specialty_id_count"] for g in groups})

    #     for rec in self:
    #         sid = rec.id
    #         rec.doctor_count = doc_map.get(sid, 0)
    #         rec.treatment_count = treat_map.get(sid, 0)
    #         rec.treatment_session_count = ts_map.get(sid, 0)
    #         rec.pricing_item_count = price_map.get(sid, 0)
    #         rec.product_count = prod_map.get(sid, 0)
    #         rec.appointment_count = appt_map.get(sid, 0)

    # -------------------------------------------------------------------------
    # PY CONSTRAINTS & ONCHANGES
    # -------------------------------------------------------------------------
    @api.constrains("parent_id")
    def _check_recursion(self):
        if not self._check_m2o_recursion("parent_id"):
            raise ValidationError(_("You cannot create a recursive specialty hierarchy."))

    @api.constrains("code")
    def _check_code_format(self):
        for rec in self:
            if rec.code and " " in rec.code:
                # Format guideline for simplicity; change to regex if needed by policy
                raise ValidationError(_("Specialty code should not contain spaces."))

    @api.onchange("code")
    def _onchange_code(self):
        if self.code:
            self.code = self.code.strip().upper()

    # -------------------------------------------------------------------------
    # SEARCH UX
    # -------------------------------------------------------------------------
    @api.model
    def name_get(self):
        res = []
        for rec in self:
            label = rec.complete_name or rec.name or _("Unnamed")
            if rec.code:
                label = f"{label} [{rec.code}]"
            res.append((rec.id, label))
        return res

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        args = args or []
        domain = []
        if name:
            domain = ["|", ("code", operator, name), ("complete_name", operator, name)]
        recs = self.search(domain + args, limit=limit)
        return recs.name_get()

    # -------------------------------------------------------------------------
    # ACTIONS (NAVIGATION HELPERS)
    # -------------------------------------------------------------------------
    def action_view_doctors(self):
        """Open doctors associated with this specialty."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Doctors"),
            "res_model": "clinic.doctor",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": [("specialty_ids", "in", [self.id])],
            "context": {"search_default_specialty_id": self.id},
            "target": "current",
        }

    # def action_view_treatments(self):
    #     """Open treatments associated with this specialty (if model exists)."""
    #     self.ensure_one()
    #     if "clinic.treatment" not in self.env:
    #         return {
    #             "type": "ir.actions.client",
    #             "tag": "display_notification",
    #             "params": {
    #                 "title": _("Not Available"),
    #                 "message": _("Treatment module is not installed."),
    #                 "sticky": False,
    #             },
    #         }
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Treatments"),
    #         "res_model": "clinic.treatment",
    #         "view_mode": "tree,form,kanban,pivot,graph",
    #         "domain": [("specialty_id", "=", self.id)],
    #         "target": "current",
    #     }

    # def action_view_treatment_sessions(self):
    #     """Open treatment sessions associated with this specialty (if model exists)."""
    #     self.ensure_one()
    #     model_name = "clinic.procedure.session"
    #     if model_name not in self.env:
    #         return {
    #             "type": "ir.actions.client",
    #             "tag": "display_notification",
    #             "params": {
    #                 "title": _("Not Available"),
    #                 "message": _("Treatment Session model is not available."),
    #                 "sticky": False,
    #             },
    #         }
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Treatment Sessions"),
    #         "res_model": model_name,
    #         "view_mode": "list,form,kanban,pivot,graph",
    #         "domain": [("specialty_id", "=", self.id)],
    #         "target": "current",
    #     }

    def action_view_pricing_items(self):
        """Open pricing items for this specialty (if Pricing module exists)."""
        self.ensure_one()
        model_name = "clinic.treatment.pricelist.item"
        if model_name not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Not Available"),
                    "message": _("Pricing module is not installed."),
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Pricing Items"),
            "res_model": model_name,
            "view_mode": "tree,form,pivot,graph",
            "domain": [("specialty_id", "=", self.id)],
            "target": "current",
        }

    def action_view_products(self):
        """Open related products (if your Inventory/Products module provides specialty link)."""
        self.ensure_one()
        # Prefer product.template if available; else product.product
        if "product.template" in self.env and "specialty_id" in self.env["product.template"]._fields:
            return {
                "type": "ir.actions.act_window",
                "name": _("Products"),
                "res_model": "product.template",
                "view_mode": "tree,form,kanban,pivot,graph",
                "domain": [("specialty_id", "=", self.id)],
                "target": "current",
            }
        if "product.product" in self.env and "specialty_id" in self.env["product.product"]._fields:
            return {
                "type": "ir.actions.act_window",
                "name": _("Products"),
                "res_model": "product.product",
                "view_mode": "tree,form,kanban,pivot,graph",
                "domain": [("specialty_id", "=", self.id)],
                "target": "current",
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Not Available"),
                "message": _("Inventory/Products module with specialty linkage is not installed."),
                "sticky": False,
            },
        }

    # def action_view_appointments(self):
    #     """Open appointments associated with this specialty (if model provides the link)."""
    #     self.ensure_one()
    #     if "clinic.appointment" in self.env and "specialty_id" in self.env["clinic.appointment"]._fields:
    #         return {
    #             "type": "ir.actions.act_window",
    #             "name": _("Appointments"),
    #             "res_model": "clinic.appointment",
    #             "view_mode": "calendar,tree,form,pivot,graph",
    #             "domain": [("specialty_id", "=", self.id)],
    #             "target": "current",
    #         }
    #     return {
    #         "type": "ir.actions.client",
    #         "tag": "display_notification",
    #         "params": {
    #             "title": _("Not Available"),
    #             "message": _("Appointment model does not expose specialty linkage."),
    #             "sticky": False,
    #         },
    #     }


# -*- coding: utf-8 -*-
# File: clinic_doctor/models/treatment_hook.py
# Module: clinic_doctor
#
# ClinicOne — Treatment Bridge (Odoo 19 CE ready)
#
# Purpose
# -------
# Extend treatment models so that Treatment Sessions can be orchestrated from Doctor
# scheduling and Appointments:
#   - clinic.treatment       : add specialty linkage and defaults
#   - clinic.procedure.session:
#       * doctor/partner/patient linkage
#       * appointment/slot/room/specialty linkage
#       * time window & state machine
#       * policy checks (leave, overlap, room-specialty)
#       * actions & hooks for billing/consumables/reports
#
# Notes
# -----
# * All UI strings are in English (product requirement).
# * Cross-module access (pricing, inventory, queue, billing) is guarded by checks
#   like `"model" in self.env` and field-existence checks to keep the bridge robust.

from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# EXTEND: clinic.treatment (Catalog/Template)
# =============================================================================
class ClinicTreatment(models.Model):
    _inherit = "clinic.treatment"

    # Link each treatment template to a Specialty for filtering/routing
    specialty_id = fields.Many2one(
        "clinic.specialty",
        ondelete="set null",
        index=True,
        help="Primary specialty this treatment belongs to."
    )
    default_duration_min = fields.Integer(
        default=45,
        help="Default duration (in minutes) when creating a treatment session."
    )
    require_room = fields.Boolean(
        default=True,
        help="If enabled, a room must be set on the treatment session."
    )

    def action_view_sessions(self):
        """Open treatment sessions created from this treatment."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Treatment Sessions"),
            "res_model": "clinic.procedure.session",
            "view_mode": "tree,form,kanban,calendar,pivot,graph",
            "domain": [("treatment_id", "=", self.id)],
            "target": "current",
        }


# =============================================================================
# EXTEND: clinic.procedure.session (Execution/Encounter)
# =============================================================================
SESSION_STATES = [
    ("draft", "Draft"),
    ("in_progress", "In Progress"),
    ("paused", "Paused"),
    ("done", "Done"),
    ("canceled", "Canceled"),
]


class ClinicTreatmentSession(models.Model):
    _inherit = "clinic.procedure.session"
    _order = "start asc, doctor_id, id"

    # -------------------------------------------------------------------------
    # LINKS & CONTEXT
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company that owns this treatment session."
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Doctor who performs this treatment session."
    )
    # Patient identity (both partner & patient where available)
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Patient contact for this session."
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        ondelete="set null",
        index=True,
        help="Linked patient record (if Patient module is installed)."
    )

    # Treatment template
    treatment_id = fields.Many2one(
        "clinic.treatment",
        required=True,
        ondelete="restrict",
        index=True,
        help="Treatment being executed during this session."
    )
    specialty_id = fields.Many2one(
        "clinic.specialty",
        ondelete="set null",
        index=True,
        help="Specialty context for this session; defaults from treatment or appointment."
    )

    # Appointment / Slot / Room
    appointment_id = fields.Many2one(
        "clinic.appointment",
        ondelete="set null",
        index=True,
        help="Appointment from which this session originates."
    )
    slot_id = fields.Many2one(
        "clinic.availability.slot",
        ondelete="set null",
        index=True,
        help="Availability slot allocated for this session."
    )
    room_id = fields.Many2one(
        "clinic.room",
        ondelete="set null",
        index=True,
        help="Treatment room used for this session."
    )
    telemedicine = fields.Boolean(
        default=False,
        help="If enabled, this session is conducted virtually (telemedicine)."
    )

    # -------------------------------------------------------------------------
    # TIMING & STATE
    # -------------------------------------------------------------------------
    start = fields.Datetime(
        required=True,
        index=True,
        tracking=True,
        help="Session start time (stored in UTC)."
    )
    end = fields.Datetime(
        required=True,
        index=True,
        tracking=True,
        help="Session end time (stored in UTC)."
    )
    duration_minutes = fields.Integer(
        compute="_compute_duration",
        store=False,
        help="Duration in minutes (computed from start/end)."
    )

    state = fields.Selection(
        SESSION_STATES,
        default="draft",
        index=True,
        tracking=True,
        help="Lifecycle state of this treatment session."
    )
    notes = fields.Text(help="Internal notes about the session.")
    color = fields.Integer(help="Color index for kanban/calendar.")

    # -------------------------------------------------------------------------
    # KPI/BRIDGE FIELDS (OPTIONAL INTEGRATIONS)
    # -------------------------------------------------------------------------
    invoice_id = fields.Many2one(
        "account.move",
        ondelete="set null",
        help="Invoice generated for this session (if Billing is installed)."
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        ondelete="set null",
        help="Sales Order generated for this session (if Sales/eCommerce is installed)."
    )
    queue_token_id = fields.Many2one(
        "clinic.queue.token",
        ondelete="set null",
        help="Queue token linked to this session (if Queue module is installed)."
    )

    # Consumables: aggregate counts if your Inventory/Consumable module exposes session linkage
    consumable_move_count = fields.Integer(
        compute="_compute_counters",
        store=False,
        help="Number of inventory moves/consumables associated to this session (if available)."
    )

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS & BASIC CONSTRAINTS
    # -------------------------------------------------------------------------
    _sql_constraints = [
        ("check_start_end", "CHECK(start < end)", "End time must be greater than start time."),
    ]

    @api.constrains("doctor_id", "room_id", "specialty_id")
    def _check_room_specialty_policy(self):
        """
        Enforce room's allowed specialties if configured (inherited in clinic_doctor).
        """
        for rec in self:
            if rec.room_id and "allowed_specialty_ids" in rec.room_id._fields and rec.room_id.allowed_specialty_ids:
                if rec.specialty_id and rec.specialty_id not in rec.room_id.allowed_specialty_ids:
                    raise ValidationError(_(
                        "Specialty '%(spec)s' is not allowed in room '%(room)s'.",
                        spec=rec.specialty_id.display_name, room=rec.room_id.display_name
                    ))

    @api.constrains("start", "end", "doctor_id", "room_id", "state")
    def _check_overlap_policy(self):
        """
        Avoid overlapping in-progress sessions for the same doctor/room (soft policy).
        """
        for rec in self:
            if not rec.start or not rec.end:
                continue
            # Overlap session by doctor
            dom = [
                ("id", "!=", rec.id),
                ("doctor_id", "=", rec.doctor_id.id),
                ("state", "not in", ["canceled", "done"]),
                ("start", "<", rec.end),
                ("end", ">", rec.start),
            ]
            if self.search_count(dom):
                raise ValidationError(_("Overlapping sessions for the same doctor are not allowed."))

            # Overlap by room (if set)
            if rec.room_id:
                dom_r = [
                    ("id", "!=", rec.id),
                    ("room_id", "=", rec.room_id.id),
                    ("state", "not in", ["canceled", "done"]),
                    ("start", "<", rec.end),
                    ("end", ">", rec.start),
                ]
                if self.search_count(dom_r):
                    raise ValidationError(_("Overlapping sessions for the same room are not allowed."))

    @api.constrains("doctor_id", "start", "end")
    def _check_doctor_leave_conflict(self):
        """
        Prevent sessions during approved doctor leaves.
        """
        if "clinic.doctor.leave" not in self.env:
            return
        Leave = self.env["clinic.doctor.leave"]
        for rec in self:
            has = Leave.search_count([
                ("doctor_id", "=", rec.doctor_id.id),
                ("state", "=", "approve"),
                ("date_from", "<", rec.end),
                ("date_to", ">", rec.start),
            ], limit=1)
            if has:
                raise ValidationError(_("Treatment session overlaps an approved doctor leave."))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_duration(self):
        for rec in self:
            if rec.start and rec.end:
                rec.duration_minutes = int((rec.end - rec.start).total_seconds() // 60)
            else:
                rec.duration_minutes = 0

    def _compute_counters(self):
        ids = self.ids or []
        cm_map = {sid: 0 for sid in ids}
        # Example: count consumables if your inventory module stores session linkage on stock.move
        if ids and "stock.move" in self.env and "treatment_session_id" in self.env["stock.move"]._fields:
            g = self.env["stock.move"].read_group(
                [("treatment_session_id", "in", ids)],
                ["treatment_session_id"],
                ["treatment_session_id"],
            )
            cm_map.update({x["treatment_session_id"][0]: x["treatment_session_id_count"] for x in g})
        for rec in self:
            rec.consumable_move_count = cm_map.get(rec.id, 0)

    # -------------------------------------------------------------------------
    # ONCHANGES
    # -------------------------------------------------------------------------
    @api.onchange("appointment_id")
    def _onchange_appointment_id(self):
        """
        Pull doctor/patient/room/specialty/time from appointment if set.
        """
        for rec in self:
            a = rec.appointment_id
            if not a:
                continue
            # Identity
            rec.doctor_id = a.doctor_id.id or rec.doctor_id
            rec.partner_id = a.partner_id.id or rec.partner_id
            if "patient_id" in a._fields and a.patient_id:
                rec.patient_id = a.patient_id.id
            # Context
            rec.specialty_id = a.specialty_id.id or rec.specialty_id
            rec.telemedicine = bool(getattr(a, "telemedicine", False))
            # Room & slot
            if "room_id" in a._fields and a.room_id:
                rec.room_id = a.room_id.id
            if "slot_id" in a._fields and a.slot_id:
                rec.slot_id = a.slot_id.id
            # Window
            rec.start = a.start or rec.start
            rec.end = a.end or rec.end
            # Treatment default duration: if end missing, use template duration
            if rec.start and not rec.end and rec.treatment_id and rec.treatment_id.default_duration_min:
                rec.end = rec.start + timedelta(minutes=rec.treatment_id.default_duration_min)

    @api.onchange("treatment_id")
    def _onchange_treatment_defaults(self):
        for rec in self:
            if rec.treatment_id:
                if not rec.specialty_id and rec.treatment_id.specialty_id:
                    rec.specialty_id = rec.treatment_id.specialty_id.id
                if rec.treatment_id.default_duration_min and rec.start and not rec.end:
                    rec.end = rec.start + timedelta(minutes=rec.treatment_id.default_duration_min)

    # -------------------------------------------------------------------------
    # STATE MACHINE
    # -------------------------------------------------------------------------
    def action_start(self):
        for rec in self:
            if rec.state not in ("draft", "paused"):
                raise UserError(_("Only draft or paused sessions can be started."))
            # If treatment requires a room, enforce it
            if rec.treatment_id.require_room and not rec.room_id:
                raise UserError(_("A room is required for this treatment session."))
            rec.state = "in_progress"
            rec.message_post(body=_("Treatment session started."))
            rec._post_state_change_hook("in_progress")
        return True

    def action_pause(self, reason=None):
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(_("Only in-progress sessions can be paused."))
            rec.state = "paused"
            if reason:
                rec.message_post(body=_("Treatment session paused: %s") % reason)
            else:
                rec.message_post(body=_("Treatment session paused."))
            rec._post_state_change_hook("paused")
        return True

    def action_resume(self):
        for rec in self:
            if rec.state != "paused":
                raise UserError(_("Only paused sessions can be resumed."))
            rec.state = "in_progress"
            rec.message_post(body=_("Treatment session resumed."))
            rec._post_state_change_hook("in_progress")
        return True

    def action_done(self):
        for rec in self:
            if rec.state not in ("in_progress", "paused"):
                raise UserError(_("Only an active session can be marked as done."))
            rec.state = "done"
            rec.message_post(body=_("Treatment session completed."))
            rec._post_state_change_hook("done")
            # Auto-invoice (optional demo): controlled by parameter
            Param = self.env["ir.config_parameter"].sudo()
            if Param.get_param("clinic_treatment.auto_invoice_on_session_done", "False") == "True":
                self._auto_invoice_if_possible(rec)
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "canceled":
                continue
            rec.state = "canceled"
            if reason:
                rec.message_post(body=_("Treatment session canceled: %s") % reason)
            else:
                rec.message_post(body=_("Treatment session canceled."))
            rec._post_state_change_hook("canceled")
        return True

    # -------------------------------------------------------------------------
    # ACTIONS / NAVIGATION
    # -------------------------------------------------------------------------
    def action_open_appointment(self):
        self.ensure_one()
        if not self.appointment_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("No Appointment"),
                           "message": _("This session is not linked to any appointment."),
                           "sticky": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Appointment"),
            "res_model": "clinic.appointment",
            "view_mode": "form",
            "res_id": self.appointment_id.id,
            "target": "current",
        }

    def action_view_consumables(self):
        """Open consumables used in this session (if your inventory app exposes linkage)."""
        self.ensure_one()
        if "stock.move" in self.env and "treatment_session_id" in self.env["stock.move"]._fields:
            return {
                "type": "ir.actions.act_window",
                "name": _("Consumables"),
                "res_model": "stock.move",
                "view_mode": "tree,form",
                "domain": [("treatment_session_id", "=", self.id)],
                "target": "current",
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Not Available"),
                       "message": _("Inventory integration for consumables is not installed."),
                       "sticky": False},
        }

    def action_create_invoice(self):
        """Create an invoice for this session (demo/simple)."""
        self.ensure_one()
        inv = self._auto_invoice_if_possible(self)
        if not inv:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Invoice"),
                           "message": _("Unable to create invoice: missing product or billing module."),
                           "sticky": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Invoice"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": inv.id,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # HOOKS & HELPERS
    # -------------------------------------------------------------------------
    def _post_state_change_hook(self, new_state):
        """
        Override in bridge modules to push webhooks, update dashboards, etc.
        """
        return True

    def _auto_invoice_if_possible(self, rec):
        """
        Minimal invoicing logic:
          - Pick product from pricing rules by specialty/treatment if available;
            else fallback to any product.
          - Create out-invoice for patient partner.
        """
        if "account.move" not in self.env or not rec.partner_id:
            return False

        product = None
        # Try pricing item by treatment first, then specialty
        if "clinic.treatment.pricelist.item" in self.env:
            Item = self.env["clinic.treatment.pricelist.item"]
            item = Item.search([("treatment_id", "=", rec.treatment_id.id)], limit=1) \
                or (rec.specialty_id and Item.search([("specialty_id", "=", rec.specialty_id.id)], limit=1))
            if item and "product_id" in item._fields:
                product = item.product_id
        # Fallback to any product
        if not product and "product.product" in self.env:
            product = self.env["product.product"].search([], limit=1)
        if not product:
            return False

        Move = self.env["account.move"].sudo()
        Line = self.env["account.move.line"].sudo()

        move = Move.create({
            "move_type": "out_invoice",
            "partner_id": rec.partner_id.id,
            "invoice_origin": rec.appointment_id.name if rec.appointment_id else rec.display_name or _("Treatment Session"),
            "invoice_date": fields.Date.context_today(self),
            "company_id": rec.company_id.id,
            "invoice_line_ids": [],
        })
        Line.create({
            "move_id": move.id,
            "product_id": product.id,
            "name": _("Treatment: %s") % (rec.treatment_id.display_name),
            "quantity": 1.0,
            "price_unit": product.lst_price if "lst_price" in product._fields else 0.0,
            "tax_ids": [(6, 0, product.taxes_id.ids if "taxes_id" in product._fields else [])],
        })
        rec.invoice_id = move.id
        return move

    # -------------------------------------------------------------------------
    # CREATE/WRITE OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        # Defaults cascading when minimal inputs provided
        for vals in vals_list:
            # company default from doctor
            if not vals.get("company_id") and vals.get("doctor_id"):
                vals["company_id"] = self.env["clinic.doctor"].browse(vals["doctor_id"]).company_id.id
            # start/end from appointment or treatment default
            if vals.get("appointment_id") and (not vals.get("start") or not vals.get("end")):
                app = self.env["clinic.appointment"].browse(vals["appointment_id"])
                if app.exists():
                    vals.setdefault("start", app.start)
                    vals.setdefault("end", app.end)
                    vals.setdefault("room_id", app.room_id.id if "room_id" in app._fields and app.room_id else False)
                    vals.setdefault("specialty_id", app.specialty_id.id if app.specialty_id else False)
                    vals.setdefault("slot_id", app.slot_id.id if "slot_id" in app._fields and app.slot_id else False)
                    vals.setdefault("telemedicine", bool(getattr(app, "telemedicine", False)))
                    vals.setdefault("partner_id", app.partner_id.id)
                    if "patient_id" in app._fields and app.patient_id:
                        vals.setdefault("patient_id", app.patient_id.id)
            if vals.get("treatment_id") and vals.get("start") and not vals.get("end"):
                t = self.env["clinic.treatment"].browse(vals["treatment_id"])
                if t.exists() and t.default_duration_min:
                    vals["end"] = vals["start"] + timedelta(minutes=t.default_duration_min)

            # specialty default from treatment
            if vals.get("treatment_id") and not vals.get("specialty_id"):
                t = self.env["clinic.treatment"].browse(vals["treatment_id"])
                if t.exists() and t.specialty_id:
                    vals["specialty_id"] = t.specialty_id.id

        recs = super().create(vals_list)

        # Chatter subscriptions: doctor & patient
        for rec in recs:
            subs = []
            if rec.partner_id:
                subs.append(rec.partner_id.id)
            if rec.doctor_id and rec.doctor_id.partner_id:
                subs.append(rec.doctor_id.partner_id.id)
            if subs:
                rec.message_subscribe(partner_ids=list(set(subs)))
        return recs

    def write(self, vals):
        res = super().write(vals)
        # If appointment changed, keep alignment
        for rec in self:
            if "appointment_id" in vals and rec.appointment_id:
                rec._onchange_appointment_id()
        return res

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            base = rec.treatment_id.display_name if rec.treatment_id else _("Treatment Session")
            doc = rec.doctor_id.display_name if rec.doctor_id else _("Doctor")
            pat = rec.partner_id.display_name if rec.partner_id else _("Patient")
            when = fields.Datetime.to_string(rec.start) if rec.start else "?"
            res.append((rec.id, f"{base} — {doc} × {pat} — {when}"))
        return res


