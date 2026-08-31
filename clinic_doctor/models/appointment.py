

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
    patient_id = fields.Many2one(
        "clinic.patient",
        ondelete="set null",
        index=True,
        help="Linked ClinicOne patient for this appointment."
    )
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
    # treatment_session_id = fields.Many2one(
    #     "clinic.procedure.session",
    #     ondelete="set null",
    #     help="Treatment session created from this appointment (if available)."
    # )
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
    # queue_token_id = fields.Many2one(
    #     "clinic.queue.token",
    #     ondelete="set null",
    #     help="Queue token created/linked at check-in (if Queue module is installed)."
    # )

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
    _check_start_end = models.Constraint(
        "CHECK (start < end)",
        "End time must be greater than start time.",
    )

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

    # def action_check_in(self):
    #     """
    #     Move to Checked In and optionally create/link a queue token.
    #     """
    #     for rec in self:
    #         if rec.state not in ("confirmed", "checked_in"):
    #             raise UserError(_("Only confirmed appointments can be checked in."))
    #         rec.state = "checked_in"
    #         rec.message_post(body=_("Patient checked in."))

    #         # Create queue token if queue module is available and no token linked yet
    #         if "clinic.queue.token" in self.env and not rec.queue_token_id:
    #             token_vals = {
    #                 "name": False,  # let sequence assign
    #                 "company_id": rec.company_id.id,
    #                 "partner_id": rec.partner_id.id,
    #                 "doctor_id": rec.doctor_id.id,
    #                 "room_id": rec.room_id.id if rec.room_id else False,
    #                 "scheduled_start": rec.start,
    #                 "scheduled_end": rec.end,
    #                 "source": "appointment",
    #             }
    #             Token = self.env["clinic.queue.token"].sudo()
    #             token = Token.create(token_vals)
    #             rec.queue_token_id = token.id

    #         rec._post_check_in_integrations_hook()
    #     return True

    # def action_start_treatment(self):
    #     for rec in self:
    #         if rec.state not in ("checked_in", "in_treatment"):
    #             raise UserError(_("Appointment must be checked in before starting treatment."))
    #         rec.state = "in_treatment"
    #         rec.message_post(body=_("Treatment started."))
    #         rec._post_start_treatment_integrations_hook()
    #     return True

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

    # def _post_start_treatment_integrations_hook(self):
    #     """
    #     Example:
    #       - Create treatment session shell if not exists
    #     """
    #     # If treatment module is available and no session yet, create one
    #     if "clinic.procedure.session" in self.env:
    #         for rec in self.filtered(lambda r: not r.treatment_session_id):
    #             vals = {
    #                 "name": _("Session for %s") % (rec.name or rec.partner_id.display_name),
    #                 "doctor_id": rec.doctor_id.id,
    #                 "partner_id": rec.partner_id.id,
    #                 "appointment_id": rec.id if "appointment_id" in self.env["clinic.procedure.session"]._fields else False,
    #                 "specialty_id": rec.specialty_id.id if rec.specialty_id else False,
    #                 "room_id": rec.room_id.id if rec.room_id and "room_id" in self.env["clinic.procedure.session"]._fields else False,
    #                 "company_id": rec.company_id.id,
    #                 "state": "in_progress" if "state" in self.env["clinic.procedure.session"]._fields else False,
    #             }
    #             sess = self.env["clinic.procedure.session"].sudo().create(vals)
    #             rec.treatment_session_id = sess.id
    #     return True

    def _post_done_integrations_hook(self):
        """
        Example:
          - Finalize treatment session
          - Create invoice / post journal entries
          - Award membership points
        """
        for rec in self:
            # Close a treatment session only when a downstream addon actually
            # provides the optional field.  The base doctor addon must not
            # dereference an absent optional integration field.
            if "treatment_session_id" in rec._fields:
                treatment_session = rec["treatment_session_id"]
                if treatment_session and "state" in treatment_session._fields:
                    treatment_session.sudo().write({"state": "done"})
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
    @api.depends("name", "doctor_id", "partner_id", "start")
    def _compute_display_name(self):
        """Preserve ClinicOne appointment labels through the Odoo 19 display-name API."""
        for rec in self:
            doc = rec.doctor_id.display_name if rec.doctor_id else _("Doctor")
            pat = rec.partner_id.display_name if rec.partner_id else _("Patient")
            when = fields.Datetime.to_string(rec.start) if rec.start else "?"
            rec.display_name = f"{rec.name or '/'} — {doc} × {pat} — {when}"

    def name_get(self):
        """Compatibility wrapper for existing ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        domain = list(domain or [])
        if name:
            domain = ["|", ("name", operator, name), ("reason", operator, name)] + domain
        recs = self.search(domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]

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

