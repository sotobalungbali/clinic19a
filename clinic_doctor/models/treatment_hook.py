
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
