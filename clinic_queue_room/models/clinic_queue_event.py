# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18/19 CE)
# File: models/clinic_queue_event.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicQueueEvent(models.Model):
    _name = "clinic.queue.event"
    _description = "Queue Event"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_datetime desc, id desc"
    _rec_name = "name"

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Event Reference",
        default="New",
        copy=False,
        index=True,
        tracking=True,
        help="Internal reference generated from a sequence (e.g., QE-000123)."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive this event."
    )

    # -------------------------------------------------------------------------
    # Scoping
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        help="Company scope of this event."
    )

    # -------------------------------------------------------------------------
    # Primary Links
    # -------------------------------------------------------------------------
    queue_id = fields.Many2one(
        comodel_name="clinic.queue",
        string="Queue",
        index=True,
        help="Queue entry related to this event."
    )
    token_id = fields.Many2one(
        comodel_name="clinic.queue.token",
        string="Token",
        index=True,
        help="Token related to this event (if any)."
    )
    room_id = fields.Many2one(
        comodel_name="clinic.room",
        string="Room",
        index=True,
        help="Room involved in this event (if any)."
    )
    room_assignment_id = fields.Many2one(
        comodel_name="clinic.room.assignment",
        string="Room Assignment",
        index=True,
        help="Room assignment involved in this event (if any)."
    )

    # Denormalized patient/doctor (fast filters)
    patient_id = fields.Many2one(
        comodel_name="res.partner",
        string="Patient",
        index=True,
        help="Patient at the time of this event."
    )
    doctor_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Doctor",
        index=True,
        help="Doctor at the time of this event."
    )

    # -------------------------------------------------------------------------
    # Event Typing
    # -------------------------------------------------------------------------
    category = fields.Selection(
        selection=[
            ("lifecycle", "Lifecycle"),
            ("stage", "Stage"),
            ("state", "State"),
            ("room", "Room"),
            ("token", "Token"),
            ("sla", "SLA"),
            ("billing", "Billing"),
            ("integration", "Integration"),
            ("system", "System"),
            ("security", "Security"),
            ("other", "Other"),
        ],
        string="Category",
        required=True,
        default="lifecycle",
        index=True,
        help="High-level category for this event."
    )
    event_type = fields.Selection(
        selection=[
            # Lifecycle / generic
            ("create", "Created"),
            ("update", "Updated"),
            ("delete", "Deleted"),

            # Stage / State
            ("stage_enter", "Stage Enter"),
            ("stage_exit", "Stage Exit"),
            ("state_change", "State Change"),

            # Rooming
            ("assign_room", "Assign Room"),
            ("release_room", "Release Room"),
            ("transfer_room", "Transfer Room"),

            # Doctor / Treatment
            ("doctor_assign", "Doctor Assigned"),
            ("doctor_unassign", "Doctor Unassigned"),
            ("treatment_set", "Treatment Set"),

            # Token
            ("token_issue", "Token Issued"),
            ("token_call", "Token Called"),
            ("token_skip", "Token Skipped"),
            ("token_serve", "Token Served"),
            ("token_cancel", "Token Cancelled"),

            # SLA
            ("sla_wait_breached", "SLA Waiting Breached"),
            ("sla_service_breached", "SLA Service Breached"),

            # Billing / Feedback
            ("billing_created", "Billing Created"),
            ("billing_invoiced", "Billing Invoiced"),
            ("feedback_requested", "Feedback Requested"),

            # Notes / Errors
            ("note", "Note"),
            ("error", "Error"),
        ],
        string="Event Type",
        required=True,
        default="note",
        index=True,
        help="Specific type of this event."
    )
    severity = fields.Selection(
        selection=[
            ("info", "Info"),
            ("warning", "Warning"),
            ("error", "Error"),
        ],
        string="Severity",
        required=True,
        default="info",
        index=True,
        help="Severity level of this event."
    )

    # -------------------------------------------------------------------------
    # Stage/State Snapshots (before/after)
    # -------------------------------------------------------------------------
    old_stage_id = fields.Many2one(
        comodel_name="clinic.queue.stage",
        string="Old Stage",
        help="Stage before the transition."
    )
    new_stage_id = fields.Many2one(
        comodel_name="clinic.queue.stage",
        string="New Stage",
        help="Stage after the transition."
    )
    old_state = fields.Selection(
        selection=[
            ("waiting", "Waiting"),
            ("in_progress", "In Progress"),
            ("on_hold", "On Hold"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
            ("no_show", "No Show"),
        ],
        string="Old State",
        help="State before the transition."
    )
    new_state = fields.Selection(
        selection=[
            ("waiting", "Waiting"),
            ("in_progress", "In Progress"),
            ("on_hold", "On Hold"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
            ("no_show", "No Show"),
        ],
        string="New State",
        help="State after the transition."
    )

    # -------------------------------------------------------------------------
    # Timing & Metrics (snapshot at event time)
    # -------------------------------------------------------------------------
    event_datetime = fields.Datetime(
        string="Event Time",
        required=True,
        default=lambda self: fields.Datetime.now(),
        index=True,
        tracking=True,
        help="Timestamp of this event."
    )
    waiting_duration_min_at_event = fields.Float(
        string="Waiting Duration at Event (min)",
        help="Waiting minutes at the time of this event (Check-in → Start)."
    )
    service_duration_min_at_event = fields.Float(
        string="Service Duration at Event (min)",
        help="Service minutes at the time of this event (Start → End or now)."
    )
    total_duration_min_at_event = fields.Float(
        string="Total Duration at Event (min)",
        help="Total minutes at the time of this event (Check-in → End or now)."
    )

    # -------------------------------------------------------------------------
    # Actor / Origin (who/what caused the event)
    # -------------------------------------------------------------------------
    actor_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Actor (User)",
        default=lambda self: self.env.user,
        help="User who triggered this event (if any)."
    )
    actor_employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Actor (Employee)",
        help="Employee who triggered this event (if any)."
    )
    source_model = fields.Char(
        string="Source Model",
        help="Model name that initiated this event (e.g., clinic.queue, clinic.room.assignment)."
    )
    source_res_id = fields.Integer(
        string="Source Record ID",
        help="Record ID of the source model that initiated this event."
    )
    res_model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Source Model (Ref)",
        help="Technical reference to the source model."
    )
    ip_address = fields.Char(
        string="IP Address",
        help="Optional IP address (e.g., kiosk/device) that triggered the event."
    )
    display_channel = fields.Char(
        string="Display Channel",
        help="Optional signage or display channel involved in this event."
    )
    kiosk_ref = fields.Char(
        string="Kiosk Reference",
        help="External kiosk reference (if issued from a kiosk)."
    )

    # -------------------------------------------------------------------------
    # Message & Payload
    # -------------------------------------------------------------------------
    summary = fields.Char(
        string="Summary",
        help="Short summary to display in feeds or dashboards (single line)."
    )
    details = fields.Text(
        string="Details",
        help="Optional detailed description or diagnostic information."
    )
    payload_json = fields.Text(
        string="Payload (JSON)",
        help="Optional JSON payload (as text) containing additional structured data."
    )

    # -------------------------------------------------------------------------
    # SQL
    # -------------------------------------------------------------------------
    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "Event Reference must be unique per company.",
    )

    # -------------------------------------------------------------------------
    # CREATE/WRITE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Default company
            vals.setdefault("company_id", self.env.company.id)
            # Sequence for name
            if not vals.get("name") or vals.get("name") == "New":
                seq = self.env["ir.sequence"].next_by_code("clinic.queue.event") \
                      or self.env["ir.sequence"].next_by_code("clinicone.clinical.queue.event") \
                      or _("New")
                vals["name"] = seq
            # Denormalize patient/doctor from queue at create time
            qid = vals.get("queue_id")
            if qid:
                q = self.env["clinic.queue"].browse(qid)
                vals.setdefault("patient_id", q.patient_id.id if q and q.exists() else False)
                vals.setdefault("doctor_id", q.doctor_id.id if q and q.exists() else False)
                # take duration snapshots
                w, s, t = self._compute_queue_durations_snapshot(q)
                vals.setdefault("waiting_duration_min_at_event", w)
                vals.setdefault("service_duration_min_at_event", s)
                vals.setdefault("total_duration_min_at_event", t)
            # Link ir.model reference if provided
            sm = vals.get("source_model")
            if sm and not vals.get("res_model_id"):
                try:
                    vals["res_model_id"] = self.env["ir.model"]._get_id(sm)
                except Exception:
                    pass
        recs = super().create(vals_list)
        # Minimal chatter post for visibility (optional)
        for r in recs:
            try:
                if r.queue_id:
                    r.queue_id.message_post(
                        body=_("Event: <b>%s</b> — %s") % (r.event_type or "-", r.summary or r.details or r.name)
                    )
            except Exception:
                # do not fail event creation due to chatter
                pass
        return recs

    def write(self, vals):
        return super().write(vals)

    # -------------------------------------------------------------------------
    # COMPUTE HELPERS
    # -------------------------------------------------------------------------
    @api.model
    def _compute_queue_durations_snapshot(self, queue):
        """
        Snapshot waiting/service/total duration (in minutes) at event time.
        """
        def minutes(a, b):
            if not a or not b:
                return 0.0
            delta = fields.Datetime.to_datetime(b) - fields.Datetime.to_datetime(a)
            return round(max(delta.total_seconds() / 60.0, 0.0), 2)

        now = fields.Datetime.now()
        w = minutes(queue.checkin_time, queue.start_time)
        s = minutes(queue.start_time, queue.end_time or now)
        t = minutes(queue.checkin_time, queue.end_time or now)
        return w, s, t

    # -------------------------------------------------------------------------
    # BUSINESS: Logging Shortcuts (to be called by other models / server actions)
    # -------------------------------------------------------------------------
    @api.model
    def log_generic(self, queue_id=None, category="other", event_type="note",
                    summary=None, details=None, severity="info", **kwargs):
        """
        Generic logger. Accepts flexible kwargs:
        - token_id, room_id, room_assignment_id
        - old_stage_id/new_stage_id, old_state/new_state
        - source_model, source_res_id, payload_json, ip_address, kiosk_ref, display_channel
        - actor_user_id/actor_employee_id
        """
        vals = {
            "queue_id": queue_id,
            "category": category,
            "event_type": event_type,
            "summary": summary or "",
            "details": details or "",
            "severity": severity or "info",
        }
        # copy supported kwargs directly
        allowed = {
            "token_id", "room_id", "room_assignment_id",
            "old_stage_id", "new_stage_id",
            "old_state", "new_state",
            "source_model", "source_res_id", "payload_json",
            "ip_address", "kiosk_ref", "display_channel",
            "actor_user_id", "actor_employee_id",
            "company_id", "event_datetime",
        }
        for k in allowed:
            if k in kwargs:
                vals[k] = kwargs[k]
        return self.create(vals)

    @api.model
    def log_stage_change(self, queue, old_stage, new_stage, **kwargs):
        return self.log_generic(
            queue_id=queue.id if queue else False,
            category="stage",
            event_type="stage_enter" if new_stage else "stage_exit",
            summary=_("Stage changed: %s → %s") % (
                old_stage.display_name if old_stage else "-",
                new_stage.display_name if new_stage else "-"
            ),
            old_stage_id=old_stage.id if old_stage else False,
            new_stage_id=new_stage.id if new_stage else False,
            old_state=(old_stage.mapped_state or old_stage.code) if old_stage else False,
            new_state=(new_stage.mapped_state or new_stage.code) if new_stage else False,
            **kwargs
        )

    @api.model
    def log_state_change(self, queue, old_state, new_state, **kwargs):
        return self.log_generic(
            queue_id=queue.id if queue else False,
            category="state",
            event_type="state_change",
            summary=_("State changed: %s → %s") % (old_state or "-", new_state or "-"),
            old_state=old_state,
            new_state=new_state,
            **kwargs
        )

    @api.model
    def log_room_assignment(self, queue, room, assignment, action="assign", **kwargs):
        etype = {"assign": "assign_room", "release": "release_room", "transfer": "transfer_room"}.get(action, "assign_room")
        action_label = dict(assign=_("Assigned"), release=_("Released"), transfer=_("Transferred")).get(action, _("Assigned"))
        return self.log_generic(
            queue_id=queue.id if queue else False,
            category="room",
            event_type=etype,
            summary=_("%s room: %s") % (action_label, room.display_name if room else "-"),
            room_id=room.id if room else False,
            room_assignment_id=assignment.id if assignment else False,
            **kwargs
        )

    @api.model
    def log_token_action(self, token, action="token_issue", **kwargs):
        labels = {
            "token_issue": _("Token issued"),
            "token_call": _("Token called"),
            "token_skip": _("Token skipped"),
            "token_serve": _("Token served"),
            "token_cancel": _("Token cancelled"),
        }
        return self.log_generic(
            queue_id=getattr(token, "queue_id", False) and token.queue_id.id or False,
            category="token",
            event_type=action,
            summary=labels.get(action, action.replace("_", " ").title()),
            token_id=token.id if token and token.exists() else False,
            **kwargs
        )

    @api.model
    def log_sla_breach(self, queue, which="wait", **kwargs):
        lbl = _("Waiting time SLA breached") if which == "wait" else _("Service time SLA breached")
        et = "sla_wait_breached" if which == "wait" else "sla_service_breached"
        return self.log_generic(
            queue_id=queue.id if queue else False,
            category="sla",
            event_type=et,
            summary=lbl,
            severity="warning",
            **kwargs
        )

    @api.model
    def log_billing(self, queue, event="billing_created", **kwargs):
        labels = dict(billing_created=_("Billing created"), billing_invoiced=_("Billing invoiced"))
        return self.log_generic(
            queue_id=queue.id if queue else False,
            category="billing",
            event_type=event,
            summary=labels.get(event, event.replace("_", " ").title()),
            **kwargs
        )

    @api.model
    def log_feedback_requested(self, queue, feedback_request, **kwargs):
        return self.log_generic(
            queue_id=queue.id if queue else False,
            category="integration",
            event_type="feedback_requested",
            summary=_("Feedback requested"),
            source_model=feedback_request._name if feedback_request else "clinic.feedback.request",
            source_res_id=feedback_request.id if feedback_request else False,
            **kwargs
        )

    # -------------------------------------------------------------------------
    # ACTIONS (UI helpers)
    # -------------------------------------------------------------------------
    def action_view_queue(self):
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

    def action_view_room_assignment(self):
        self.ensure_one()
        if not self.room_assignment_id:
            return False
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
    # DISPLAY (Odoo 19)
    # -------------------------------------------------------------------------
    @api.depends("name", "event_type", "queue_id", "queue_id.name")
    def _compute_display_name(self):
        for rec in self:
            label = rec.name or _("Event")
            if rec.event_type:
                label = f"{label} [{rec.event_type}]"
            if rec.queue_id:
                label = f"{label} — {rec.queue_id.display_name}"
            rec.display_name = label

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        domain = domain or []
        criteria = []
        if name:
            criteria = ["|", ("name", operator, name), ("summary", operator, name)]
        recs = self.search(domain + criteria, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# -----------------------------------------------------------------------------
# Backward-compatibility alias (legacy model name)
# Keep while other modules still reference 'clinicone.clinical.queue.event'
# -----------------------------------------------------------------------------
# class LegacyCliniconeClinicalQueueEvent(models.Model):
#     _name = "clinicone.clinical.queue.event"
#     _inherit = "clinic.queue.event"
#     _description = "Queue Event (Legacy Alias)"
#     _register = False
