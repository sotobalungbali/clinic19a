# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18/19 CE)
# File: models/appointment_inherit.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicAppointment(models.Model):
    _inherit = "clinic.appointment"

    # -------------------------------------------------------------------------
    # Core Links to Queue/Token/Room
    # -------------------------------------------------------------------------
    queue_id = fields.Many2one(
        comodel_name="clinic.queue",
        string="Queue",
        index=True,
        help="Linked queue created from this appointment."
    )
    token_id = fields.Many2one(
        comodel_name="clinic.queue.token",
        string="Token",
        index=True,
        help="Token issued for this appointment (if any)."
    )
    room_id = fields.Many2one(
        comodel_name="clinic.room",
        string="Room",
        index=True,
        help="Current room allocated for this appointment (comes from queue/assignment)."
    )
    room_assignment_id = fields.Many2one(
        comodel_name="clinic.room.assignment",
        string="Room Assignment",
        index=True,
        help="Room assignment record related to this appointment (if any)."
    )

    # Mirrors from Queue (fast filters in appointment list)
    queue_stage_id = fields.Many2one(
        comodel_name="clinic.queue.stage",
        string="Queue Stage",
        compute="_compute_queue_mirrors",
        store=True,
        help="Current operational stage of the linked queue."
    )
    queue_state = fields.Selection(
        selection=[
            ("waiting", "Waiting"),
            ("in_progress", "In Progress"),
            ("on_hold", "On Hold"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
            ("no_show", "No Show"),
        ],
        string="Queue State",
        compute="_compute_queue_mirrors",
        store=True,
        help="Current status of the linked queue."
    )

    # -------------------------------------------------------------------------
    # Check-in / Service timestamps (independen di level appointment)
    # -------------------------------------------------------------------------
    checkin_time = fields.Datetime(
        string="Check-in Time",
        help="Timestamp when the patient checked in for this appointment."
    )
    clinic_service_start_at = fields.Datetime(
        string="Service Start (Clinic)",
        help="Service start time recorded from clinic queue workflow."
    )
    clinic_service_end_at = fields.Datetime(
        string="Service End (Clinic)",
        help="Service end time recorded from clinic queue workflow."
    )
    checkout_time = fields.Datetime(
        string="Checkout Time",
        help="Timestamp when the patient checked out after finishing the service."
    )

    # -------------------------------------------------------------------------
    # Metrics (derived)
    # -------------------------------------------------------------------------
    waiting_duration_min = fields.Float(
        string="Waiting Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from check-in to service start."
    )
    service_duration_min = fields.Float(
        string="Service Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from service start to service end."
    )
    total_visit_duration_min = fields.Float(
        string="Total Visit Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from check-in to checkout/service end."
    )

    # Convenience flags
    is_checked_in = fields.Boolean(
        string="Checked-in",
        compute="_compute_flags",
        help="True if check-in time is set."
    )
    has_active_queue = fields.Boolean(
        string="Has Active Queue",
        compute="_compute_flags",
        help="True if the linked queue is in Waiting / In Progress / On Hold."
    )

    # -------------------------------------------------------------------------
    # Cross-module soft integrations (optional pointers)
    # -------------------------------------------------------------------------
    membership_id = fields.Many2one(
        comodel_name="clinic.membership",
        string="Membership",
        help="Membership used by this appointment (if any)."
    )
    insurance_policy_id = fields.Many2one(
        comodel_name="clinic.insurance.policy",
        string="Insurance Policy",
        help="Insurance policy used for this appointment (if any)."
    )
    authorization_id = fields.Many2one(
        comodel_name="clinic.insurance.authorization",
        string="Insurance Authorization",
        help="Insurance authorization for this appointment (if required)."
    )
    telemedicine_session_id = fields.Many2one(
        comodel_name="clinic.telemedicine.session",
        string="Telemedicine Session",
        help="Telemedicine session linked to this appointment (if any)."
    )

    # -------------------------------------------------------------------------
    # Field helpers (compat layer for various appointment base modules)
    # -------------------------------------------------------------------------
    # Standardize accessors to appointment's own subject fields; many bases use these names already:
    patient_id = fields.Many2one(  # if original model already has 'patient_id', Odoo will merge definitions
        comodel_name="res.partner",
        string="Patient",
        index=True,
        help="Patient scheduled for this appointment."
    )
    doctor_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Doctor",
        index=True,
        domain=[("is_doctor", "=", True)],
        help="Doctor in charge for this appointment."
    )
    treatment_id = fields.Many2one(
        comodel_name="clinic.treatment",
        string="Treatment",
        index=True,
        help="Planned treatment for this appointment (if known)."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("queue_id", "queue_id.stage_id", "queue_id.state", "queue_id.room_id", "queue_id.room_assignment_id")
    def _compute_queue_mirrors(self):
        for rec in self:
            q = rec.queue_id
            rec.queue_stage_id = q.stage_id.id if q else False
            rec.queue_state = q.state if q else False
            if q:
                # Keep room links mirrored for quick filters
                rec.room_id = q.room_id.id if q.room_id else rec.room_id
                rec.room_assignment_id = q.room_assignment_id.id if q.room_assignment_id else rec.room_assignment_id

    @api.depends("checkin_time", "clinic_service_start_at", "clinic_service_end_at", "checkout_time")
    def _compute_durations(self):
        for rec in self:
            def minutes(a, b):
                if not a or not b:
                    return 0.0
                delta = fields.Datetime.to_datetime(b) - fields.Datetime.to_datetime(a)
                return round(max(delta.total_seconds() / 60.0, 0.0), 2)

            # waiting: checkin -> service start
            rec.waiting_duration_min = minutes(rec.checkin_time, rec.clinic_service_start_at)
            # service: start -> end
            rec.service_duration_min = minutes(rec.clinic_service_start_at, rec.clinic_service_end_at)
            # total: checkin -> checkout or service end
            end_ref = rec.checkout_time or rec.clinic_service_end_at
            rec.total_visit_duration_min = minutes(rec.checkin_time, end_ref)

    @api.depends("checkin_time", "queue_state")
    def _compute_flags(self):
        for rec in self:
            rec.is_checked_in = bool(rec.checkin_time)
            rec.has_active_queue = rec.queue_state in ("waiting", "in_progress", "on_hold")

    # -------------------------------------------------------------------------
    # VALIDATIONS
    # -------------------------------------------------------------------------
    @api.constrains("doctor_id")
    def _check_doctor_flag(self):
        for rec in self:
            if rec.doctor_id and not getattr(rec.doctor_id, "is_doctor", False):
                raise ValidationError(_("Assigned Doctor must be a doctor (is_doctor = True)."))

    # -------------------------------------------------------------------------
    # ONCHANGES
    # -------------------------------------------------------------------------
    @api.onchange("queue_id")
    def _onchange_queue_id(self):
        """
        When queue is linked/changed, mirror essential fields so Appointment stays in sync visually.
        """
        if self.queue_id:
            if not self.checkin_time:
                # if queue already has checkin, mirror it
                if "checkin_time" in self.queue_id._fields and self.queue_id.checkin_time:
                    self.checkin_time = self.queue_id.checkin_time
            if self.queue_id.room_id and not self.room_id:
                self.room_id = self.queue_id.room_id.id
            if self.queue_id.room_assignment_id and not self.room_assignment_id:
                self.room_assignment_id = self.queue_id.room_assignment_id.id
            if self.queue_id.patient_id and not self.patient_id:
                self.patient_id = self.queue_id.patient_id.id
            if self.queue_id.doctor_id and not self.doctor_id:
                self.doctor_id = self.queue_id.doctor_id.id
            if self.queue_id.treatment_id and not self.treatment_id:
                self.treatment_id = self.queue_id.treatment_id.id

    # -------------------------------------------------------------------------
    # BUSINESS ACTIONS — Appointment ↔ Queue / Token / Room
    # -------------------------------------------------------------------------
    def action_check_in(self):
        """
        Mark appointment as checked-in and ensure a queue exists/ready.
        """
        for rec in self:
            # set checkin time if not set
            if not rec.checkin_time:
                rec.checkin_time = fields.Datetime.now()

            # Ensure queue exists
            if not rec.queue_id:
                rec._action_create_queue_from_appointment()
            else:
                # if queue exists but still not in waiting/in_progress, try set to waiting
                if rec.queue_id.state not in ("waiting", "in_progress", "on_hold"):
                    try:
                        # move to a stage/state compatible with waiting
                        rec.queue_id._move_to_mapped_state("waiting")
                    except Exception as e:
                        rec.message_post(body=_("Failed to move queue to 'Waiting': %s") % e)
        return True

    def action_check_out(self):
        """
        Mark appointment as checked-out. If queue exists and is done, ok;
        otherwise try to complete queue.
        """
        for rec in self:
            rec.checkout_time = fields.Datetime.now()
            if rec.queue_id:
                if rec.queue_id.state not in ("done", "cancelled", "no_show"):
                    try:
                        # If service_end is not set on queue, finishing queue will set it
                        rec.queue_id.action_done()
                    except Exception as e:
                        rec.message_post(body=_("Unable to mark queue done on checkout: %s") % e)
        return True

    def action_issue_token(self):
        """
        Issue a token for this appointment.
        """
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_("Please set Patient on the appointment first."))
        Token = self.env["clinic.queue.token"]
        vals = {
            "patient_id": self.patient_id.id,
            "appointment_id": self.id,
            "company_id": self.company_id.id if "company_id" in self._fields and self.company_id else self.env.company.id,
            "queue_type": getattr(self, "queue_type", False) or "general",
            "channel": "online" if getattr(self, "is_telemedicine", False) else "walkin",
            "priority": "1",
            "doctor_id": self.doctor_id.id if self.doctor_id else False,
            "treatment_id": self.treatment_id.id if self.treatment_id else False,
            "state": "issued",
        }
        tok = Token.create({k: v for k, v in vals.items() if v or k in ("company_id", "queue_type", "channel")})
        self.token_id = tok.id
        # Open token
        act = self.env.ref("clinic_queue_room.action_clinic_queue_token_form", raise_if_not_found=False)
        if act:
            data = act.read()[0]
            data.update({"res_id": tok.id, "view_mode": "form"})
            return data
        return True

    def action_create_queue(self):
        """
        Manually create and open a queue from this appointment (if not yet created).
        """
        self.ensure_one()
        return self._action_create_queue_from_appointment(open_form=True)

    # Internal helper for queue creation
    def _action_create_queue_from_appointment(self, open_form=False):
        self.ensure_one()
        if self.queue_id:
            return self._action_view_queue()

        if not self.patient_id:
            raise UserError(_("Please set Patient on the appointment first."))

        Queue = self.env["clinic.queue"]
        vals = {
            "patient_id": self.patient_id.id,
            "doctor_id": self.doctor_id.id if self.doctor_id else False,
            "treatment_id": self.treatment_id.id if self.treatment_id else False,
            "appointment_id": self.id,
            "company_id": self.company_id.id if "company_id" in self._fields and self.company_id else self.env.company.id,
            "queue_type": getattr(self, "queue_type", False) or "general",
            "channel": "telemedicine" if getattr(self, "is_telemedicine", False) else "online",
            "priority": "1",
            # check-in mirrors appointment check-in if exists
            "checkin_time": self.checkin_time or fields.Datetime.now(),
        }
        q = Queue.create({k: v for k, v in vals.items() if v or k in ("company_id", "queue_type", "channel", "checkin_time")})
        self.queue_id = q.id

        # run stage enter hooks safely
        try:
            if q.stage_id and hasattr(q.stage_id, "_run_on_enter_hooks"):
                q.stage_id._run_on_enter_hooks(q)
        except Exception as e:
            q.message_post(body=_("Stage enter hooks failed: %s") % e)

        # Open queue form if requested
        if open_form:
            return self._action_view_queue()
        return True

    def action_assign_room(self, room_id):
        """
        Assign selected room via queue helper. Creates a room.assignment.
        """
        self.ensure_one()
        if not self.queue_id:
            raise UserError(_("Please create the Queue first before assigning a room."))
        assignment_id = self.queue_id.action_assign_room(room_id=room_id)
        # mirror links
        self.room_id = self.queue_id.room_id.id if self.queue_id.room_id else self.room_id
        self.room_assignment_id = self.queue_id.room_assignment_id.id if self.queue_id.room_assignment_id else self.room_assignment_id
        return assignment_id

    def action_release_room(self):
        self.ensure_one()
        if not self.queue_id or not self.queue_id.room_id:
            return True
        self.queue_id.action_release_room()
        # mirrors will be recomputed by dependency on queue
        return True

    def action_start_service(self):
        """
        Start service from appointment context (delegates to queue).
        """
        self.ensure_one()
        if not self.queue_id:
            self._action_create_queue_from_appointment()
        # queue start
        self.queue_id.action_start()
        # mirror timestamps
        self.clinic_service_start_at = self.queue_id.start_time or fields.Datetime.now()
        # set checkin if still empty
        if not self.checkin_time:
            self.checkin_time = self.queue_id.checkin_time or fields.Datetime.now()
        return True

    def action_finish_service(self):
        """
        Finish service from appointment context (delegates to queue).
        """
        self.ensure_one()
        if not self.queue_id:
            raise UserError(_("No queue is linked to this appointment."))
        self.queue_id.action_done()
        self.clinic_service_end_at = self.queue_id.end_time or fields.Datetime.now()
        # auto checkout if not yet
        if not self.checkout_time:
            self.checkout_time = fields.Datetime.now()
        return True

    def action_cancel_queue(self, reason=None):
        self.ensure_one()
        if self.queue_id:
            self.queue_id.action_cancel(reason=reason)
        return True

    def action_mark_no_show(self):
        self.ensure_one()
        if self.queue_id:
            self.queue_id.action_no_show()
        return True

    # -------------------------------------------------------------------------
    # UI Actions (open related)
    # -------------------------------------------------------------------------
    def _action_view_queue(self):
        self.ensure_one()
        if not self.queue_id:
            return False
        act = self.env.ref("clinic_queue_room.action_clinic_queue_form", raise_if_not_found=False)
        if act:
            data = act.read()[0]
            data.update({"res_id": self.queue_id.id, "view_mode": "form"})
            return data
        return {
            "type": "ir.actions.act_window",
            "name": _("Queue"),
            "res_model": "clinic.queue",
            "view_mode": "form,list,kanban",
            "res_id": self.queue_id.id,
            "target": "current",
        }

    def action_view_token(self):
        self.ensure_one()
        if not self.token_id:
            raise UserError(_("No token is linked to this appointment."))
        act = self.env.ref("clinic_queue_room.action_clinic_queue_token_form", raise_if_not_found=False)
        if act:
            data = act.read()[0]
            data.update({"res_id": self.token_id.id, "view_mode": "form"})
            return data
        return {
            "type": "ir.actions.act_window",
            "name": _("Token"),
            "res_model": "clinic.queue.token",
            "view_mode": "form,list",
            "res_id": self.token_id.id,
            "target": "current",
        }

    def action_view_room_assignment(self):
        self.ensure_one()
        if not self.room_assignment_id:
            raise UserError(_("No room assignment is linked to this appointment."))
        act = self.env.ref("clinic_queue_room.action_clinic_room_assignment_form", raise_if_not_found=False)
        if act:
            data = act.read()[0]
            data.update({"res_id": self.room_assignment_id.id, "view_mode": "form"})
            return data
        return {
            "type": "ir.actions.act_window",
            "name": _("Room Assignment"),
            "res_model": "clinic.room.assignment",
            "view_mode": "form,list",
            "res_id": self.room_assignment_id.id,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # CROSS-MODULE HOOKS (optional, safe to fail)
    # -------------------------------------------------------------------------
    def _post_finish_feedback(self):
        """
        Optional hook to create a feedback request after service finish.
        If 'clinic.feedback.request' exists and provides M2O to patient/queue.
        """
        FR = self.env.get("clinic.feedback.request")
        if not FR or not self.queue_id:
            return
        try:
            vals = {
                "patient_id": self.patient_id.id if self.patient_id else False,
                "queue_id": self.queue_id.id if "queue_id" in FR._fields else False,
                "company_id": self.company_id.id if "company_id" in self._fields and self.company_id else False,
            }
            FR.create({k: v for k, v in vals.items() if v})
        except Exception as e:
            self.message_post(body=_("Auto-create feedback request failed: %s") % e)

    # Optionally call the hook at finish; comment out if not needed
    def write(self, vals):
        res = super().write(vals)
        # If service just ended but no checkout yet, we can trigger feedback creation
        for rec in self:
            if "clinic_service_end_at" in vals and rec.clinic_service_end_at and not vals.get("checkout_time"):
                try:
                    rec._post_finish_feedback()
                except Exception:
                    pass
        return res
