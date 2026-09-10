
# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18/19 CE)
# File: models/clinic_queue.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicQueue(models.Model):
    _name = "clinic.queue"
    _description = "Clinical Queue"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, checkin_time asc, id asc"

    channel_id = fields.Many2one(
        comodel_name='clinic.queue.channel',
        string='Queue Channel',
        index=True,
        ondelete='restrict',
        help='Channel (kiosk/desk/department) that this queue item belongs to.'
    )

    # -------------------------------------------------------------------------
    # Identity & Display
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Queue Reference",
        default="New",
        copy=False,
        index=True,
        tracking=True,
        help="Internal reference generated from a sequence (e.g., Q-000123).",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Ordering helper for lists/dashboards (lower appears first).",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive this queue record.",
    )

    # -------------------------------------------------------------------------
    # Company / Type / Channel / Priority
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        help="Company scope for this queue.",
    )
    queue_type = fields.Selection(
        selection=[
            ("general", "General"),
            ("treatment", "Treatment"),
            ("procedure", "Procedure"),
            ("telemedicine", "Telemedicine"),
            ("vip", "VIP"),
        ],
        string="Queue Type",
        required=True,
        default="general",
        index=True,
        help="Functional category of this queue; used to fetch default stage/policies.",
    )
    channel = fields.Selection(
        selection=[
            ("walkin", "Walk-in"),
            ("online", "Online"),
            ("referral", "Referral"),
            ("telemedicine", "Telemedicine"),
            ("vip", "VIP"),
        ],
        string="Intake Channel",
        required=True,
        default="walkin",
        index=True,
        help="How this queue was created.",
    )
    priority = fields.Selection(
        selection=[("0", "Low"), ("1", "Normal"), ("2", "High"), ("3", "Urgent")],
        string="Priority",
        default="1",
        index=True,
        tracking=True,
        help="Priority level used for calling/order decisions.",
    )

    # -------------------------------------------------------------------------
    # Subject & Clinical Links (integrations across ClinicOne)
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        comodel_name="res.partner",
        string="Patient",
        required=False,
        index=True,
        tracking=True,
        domain=[("is_company", "=", False)],
        help="Patient in the queue.",
    )
    doctor_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Doctor",
        index=True,
        domain=[("is_doctor", "=", True)],
        help="Assigned doctor (if any).",
    )
    treatment_id = fields.Many2one(
        comodel_name="clinic.treatment",
        string="Treatment",
        index=True,
        help="Planned/selected treatment for this queue.",
    )
    appointment_id = fields.Many2one(
        comodel_name="clinic.appointment",
        string="Appointment",
        index=True,
        help="Linked appointment if the queue originates from an appointment.",
    )
    # booking_id = fields.Many2one(
    #     comodel_name="booking.booking",
    #     string="Booking",
    #     index=True,
    #     help="Linked booking if the queue originates from the booking module.",
    # )
    token_id = fields.Many2one(
        comodel_name="clinic.queue.token",
        string="Token",
        index=True,
        help="Token record (kiosk/frontdesk) that created this queue.",
    )

    # Extended cross-module hooks (optional / soft-coupled)
    # membership_id = fields.Many2one(
    #     comodel_name="clinic.membership",
    #     string="Membership",
    #     help="Patient membership (if any).",
    # )
    # insurance_policy_id = fields.Many2one(
    #     comodel_name="clinic.insurance.policy",
    #     string="Insurance Policy",
    #     help="Insurance policy used for the visit (if applicable).",
    # )
    # authorization_id = fields.Many2one(
    #     comodel_name="clinic.insurance.authorization",
    #     string="Insurance Authorization",
    #     help="Insurance authorization for this queue (if required).",
    # )
    # telemedicine_session_id = fields.Many2one(
    #     comodel_name="clinic.telemedicine.session",
    #     string="Telemedicine Session",
    #     help="Linked telemedicine session (if any).",
    # )
    # feedback_request_id = fields.Many2one(
    #     comodel_name="clinic.feedback.request",
    #     string="Feedback Request",
    #     help="Feedback request created after service completion.",
    # )

    # Commercial / Accounting / Inventory (hooks)
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sales Order",
        index=True,
        help="Sales Order associated with this queue (if any).",
    )
    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Customer Invoice",
        domain=[("move_type", "=", "out_invoice")],
        help="Invoice generated for this queue (if any).",
    )
    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytic Account",
        help="Analytic account to track revenue/cost from this queue.",
    )
    planned_product_ids = fields.Many2many(
        comodel_name="product.product",
        relation="clinic_queue_planned_product_rel",
        column1="queue_id",
        column2="product_id",
        string="Planned Consumables",
        help="Consumables expected to be used during treatment.",
    )

    # -------------------------------------------------------------------------
    # Rooming (integration with Room & Assignment)
    # -------------------------------------------------------------------------
    room_id = fields.Many2one(
        comodel_name="clinic.room",
        string="Room",
        index=True,
        help="Current room (if assigned).",
    )
    room_assignment_id = fields.Many2one(
        comodel_name="clinic.room.assignment",
        string="Room Assignment",
        help="Current active room assignment record (if any).",
    )

    # -------------------------------------------------------------------------
    # Stage / State
    # -------------------------------------------------------------------------
    stage_id = fields.Many2one(
        comodel_name="clinic.queue.stage",
        string="Stage",
        index=True,
        tracking=True,
        help="Operational stage with policies and hooks.",
    )
    state = fields.Selection(
        selection=[
            ("waiting", "Waiting"),
            ("in_progress", "In Progress"),
            ("on_hold", "On Hold"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
            ("no_show", "No Show"),
        ],
        string="Status",
        default="waiting",
        required=True,
        index=True,
        tracking=True,
        help="Operational status kept in sync with the selected stage.",
    )

    # -------------------------------------------------------------------------
    # Timings
    # -------------------------------------------------------------------------
    checkin_time = fields.Datetime(
        string="Check-in Time",
        required=True,
        default=lambda self: fields.Datetime.now(),
        index=True,
        tracking=True,
        help="Timestamp when the patient checked in / queue was created.",
    )
    start_time = fields.Datetime(
        string="Service Start Time",
        tracking=True,
        help="Timestamp when service started.",
    )
    end_time = fields.Datetime(
        string="Service End Time",
        tracking=True,
        help="Timestamp when service finished.",
    )
    waiting_duration_min = fields.Float(
        string="Waiting Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from Check-in to Service Start.",
    )
    service_duration_min = fields.Float(
        string="Service Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from Service Start to Service End.",
    )
    total_duration_min = fields.Float(
        string="Total Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from Check-in to Service End (or Now if ongoing).",
    )

    # -------------------------------------------------------------------------
    # SLA Hints / Escalations (driven by stage)
    # -------------------------------------------------------------------------
    sla_wait_target_min = fields.Float(
        string="SLA Target: Waiting (min)",
        compute="_compute_sla_targets",
        help="Target waiting time taken from the stage configuration.",
    )
    sla_service_target_min = fields.Float(
        string="SLA Target: Service (min)",
        compute="_compute_sla_targets",
        help="Target service time taken from the stage configuration.",
    )
    sla_wait_breached = fields.Boolean(
        string="SLA Waiting Breached",
        compute="_compute_sla_breaches",
        help="True if waiting duration exceeds the stage's waiting SLA.",
    )
    sla_service_breached = fields.Boolean(
        string="SLA Service Breached",
        compute="_compute_sla_breaches",
        help="True if service duration exceeds the stage's service SLA.",
    )

    # -------------------------------------------------------------------------
    # Notes
    # -------------------------------------------------------------------------
    notes = fields.Text(
        string="Notes",
        help="Internal notes regarding this queue entry.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("checkin_time", "start_time", "end_time")
    def _compute_durations(self):
        for rec in self:
            def minutes(a, b):
                if not a or not b:
                    return 0.0
                delta = fields.Datetime.to_datetime(b) - fields.Datetime.to_datetime(a)
                return round(max(delta.total_seconds() / 60.0, 0.0), 2)

            now = fields.Datetime.now()
            rec.waiting_duration_min = minutes(rec.checkin_time, rec.start_time)
            service_end_ref = rec.end_time or now
            rec.service_duration_min = minutes(rec.start_time, service_end_ref)
            total_end_ref = rec.end_time or now
            rec.total_duration_min = minutes(rec.checkin_time, total_end_ref)

    @api.depends("stage_id")
    def _compute_sla_targets(self):
        for rec in self:
            rec.sla_wait_target_min = rec.stage_id.sla_target_wait_min or 0.0
            rec.sla_service_target_min = rec.stage_id.sla_target_service_min or 0.0

    @api.depends(
        "sla_wait_target_min", "sla_service_target_min",
        "waiting_duration_min", "service_duration_min",
        "state"
    )
    def _compute_sla_breaches(self):
        for rec in self:
            # Consider breaches only for active states
            active_states = {"waiting", "in_progress", "on_hold"}
            rec.sla_wait_breached = bool(
                rec.state in active_states and rec.sla_wait_target_min > 0.0 and rec.waiting_duration_min > rec.sla_wait_target_min
            )
            rec.sla_service_breached = bool(
                rec.state in active_states and rec.sla_service_target_min > 0.0 and rec.service_duration_min > rec.sla_service_target_min
            )

    # -------------------------------------------------------------------------
    # ONCHANGES
    # -------------------------------------------------------------------------
    @api.onchange("stage_id")
    def _onchange_stage_id(self):
        """Keep 'state' aligned with stage's mapped state and warn for requirements."""
        for rec in self:
            if rec.stage_id:
                mapped = rec.stage_id.mapped_state_value() if hasattr(rec.stage_id, "mapped_state_value") else rec.stage_id.code
                if mapped:
                    rec.state = mapped
                # Soft UI warning if requirements are not met; hard checks are in write/move
                try:
                    rec.stage_id.validate_requirements(rec)
                except ValidationError as e:
                    return {
                        "warning": {
                            "title": _("Stage Requirements"),
                            "message": str(e),
                        }
                    }

    # -------------------------------------------------------------------------
    # CREATE / WRITE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        - Sequence for name (code 'clinic.queue', with legacy fallback).
        - Default stage based on (company, queue_type).
        - Auto-subscribe patient & doctor to chatter.
        """
        Stage = self.env["clinic.queue.stage"]
        for vals in vals_list:
            # Company, channel defaults
            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("channel", "walkin")
            vals.setdefault("queue_type", "general")
            # Name/sequence
            if not vals.get("name") or vals.get("name") == "New":
                seq = self.env["ir.sequence"].next_by_code("clinic.queue") \
                      or self.env["ir.sequence"].next_by_code("clinicone.clinical.queue") \
                      or _("New")
                vals["name"] = seq
            # Default stage
            if not vals.get("stage_id"):
                default_stage = Stage.get_default_stage(
                    company_id=vals["company_id"],
                    queue_type=vals.get("queue_type") or "general",
                )
                vals["stage_id"] = default_stage.id if default_stage else False
            # Default state from stage
            if vals.get("stage_id") and not vals.get("state"):
                stg = Stage.browse(vals["stage_id"])
                vals["state"] = stg.mapped_state_value() if hasattr(stg, "mapped_state_value") else stg.code or "waiting"
            # Check-in
            vals.setdefault("checkin_time", fields.Datetime.now())

        records = super().create(vals_list)

        # Auto-subscribe chatter participants
        for rec in records:
            subs = []
            if rec.patient_id and not rec.patient_id.partner_share:
                subs.append(rec.patient_id.id)
            if rec.doctor_id and rec.doctor_id.user_id and rec.doctor_id.user_id.partner_id:
                subs.append(rec.doctor_id.user_id.partner_id.id)
            if subs:
                rec.message_subscribe(partner_ids=list(set(subs)))

        return records

    def write(self, vals):
        """
        - Enforce stage requirements.
        - Run exit/enter hooks when stage changes.
        - Enforce locks (e.g., lock_patient_change).
        - Keep state aligned with stage.
        """
        stage_changed = "stage_id" in vals
        old_stage_map = {rec.id: rec.stage_id for rec in self} if stage_changed else {}
        res = super().write(vals)

        # Locks and requirements
        for rec in self:
            # Lock patient change?
            if old_stage_map and "patient_id" in vals:
                stg = old_stage_map.get(rec.id)
                if stg and getattr(stg, "lock_patient_change", False) and rec.patient_id.id != vals["patient_id"]:
                    raise ValidationError(_("Changing patient in stage '%s' is not allowed.") % stg.name)

            # Stage change hooks & state sync
            if stage_changed:
                old_stage = old_stage_map.get(rec.id)
                new_stage = rec.stage_id
                if new_stage:
                    # Validate before entering
                    new_stage.validate_requirements(rec)
                    # Exit old
                    if old_stage and hasattr(old_stage, "_run_on_exit_hooks"):
                        try:
                            old_stage._run_on_exit_hooks(rec)
                        except Exception as e:
                            rec.message_post(body=_("Stage exit hooks failed: %s") % e)
                    # Enter new
                    if hasattr(new_stage, "_run_on_enter_hooks"):
                        try:
                            new_stage._run_on_enter_hooks(rec)
                        except Exception as e:
                            rec.message_post(body=_("Stage enter hooks failed: %s") % e)
                    # Align state with mapped state
                    mapped = new_stage.mapped_state_value() if hasattr(new_stage, "mapped_state_value") else new_stage.code
                    if mapped and rec.state != mapped:
                        super(ClinicQueue, rec).write({"state": mapped})

        return res

    # -------------------------------------------------------------------------
    # VALIDATIONS
    # -------------------------------------------------------------------------
    @api.constrains("start_time", "end_time", "checkin_time")
    def _check_time_order(self):
        for rec in self:
            if rec.start_time and rec.checkin_time and rec.start_time < rec.checkin_time:
                raise ValidationError(_("Service Start Time cannot be earlier than Check-in Time."))
            if rec.end_time and rec.start_time and rec.end_time < rec.start_time:
                raise ValidationError(_("Service End Time cannot be earlier than Service Start Time."))

    # -------------------------------------------------------------------------
    # BUSINESS HELPERS — Stage navigation
    # -------------------------------------------------------------------------
    def _find_stage_by_mapped_state(self, mapped_state):
        """Find a suitable stage with the given mapped_state for this queue."""
        self.ensure_one()
        Stage = self.env["clinic.queue.stage"]
        # Prefer a next-stage from current
        if self.stage_id and self.stage_id.next_stage_ids:
            candidate = self.stage_id.next_stage_ids.filtered(
                lambda s: (s.company_id == self.company_id)
                and (s.queue_type == self.queue_type)
                and ((s.mapped_state or s.code) == mapped_state)
                and s.active
            )
            if candidate:
                return candidate.sorted(lambda s: (s.sequence, s.id))[0]
        # Fallback: any active stage in scope
        domain = [
            ("company_id", "=", self.company_id.id),
            ("queue_type", "=", self.queue_type),
            ("active", "=", True),
        ]
        # Odoo 19 domain operators are prefix tokens, not a nested
        # three-item condition tuple. The previous shape
        # ("|", condition_a, condition_b) was parsed as one condition and Odoo
        # attempted `.lower()` on condition_a (a tuple).
        rec = Stage.search(
            domain + [
                "|",
                ("mapped_state", "=", mapped_state),
                ("code", "=", mapped_state),
            ],
            limit=1,
            order="sequence asc, id asc",
        )
        return rec or self.stage_id

    def _move_to_mapped_state(self, mapped_state):
        """Move to a stage whose mapped_state equals the requested value (validates hooks)."""
        self.ensure_one()
        target = self._find_stage_by_mapped_state(mapped_state)
        if not target:
            # if no suitable stage, update state only (last resort)
            super(ClinicQueue, self).write({"state": mapped_state})
            return True
        self.write({"stage_id": target.id})  # write() will run validations and sync 'state'
        return True

    # -------------------------------------------------------------------------
    # ACTIONS — Lifecycle
    # -------------------------------------------------------------------------
    def action_start(self):
        for rec in self:
            # Validate stage requirements first
            if rec.stage_id:
                rec.stage_id.validate_requirements(rec)
            vals = {"start_time": rec.start_time or fields.Datetime.now()}
            rec.write(vals)  # may call write hooks
            rec._move_to_mapped_state("in_progress")
        return True

    def action_hold(self):
        for rec in self:
            rec._move_to_mapped_state("on_hold")
        return True

    def action_resume(self):
        for rec in self:
            rec._move_to_mapped_state("in_progress")
        return True

    def action_done(self):
        for rec in self:
            if not rec.end_time:
                rec.write({"end_time": fields.Datetime.now()})
            rec._move_to_mapped_state("done")
            # Optional: create feedback request automatically
            try:
                if (
                    "feedback_request_id" in rec._fields
                    and not rec.feedback_request_id
                    and self.env.get("clinic.feedback.request")
                ):
                    FeedbackRequest = self.env["clinic.feedback.request"]
                    vals = {
                        "patient_id": rec.patient_id.id if rec.patient_id else False,
                        "queue_id": rec.id if "queue_id" in FeedbackRequest._fields else False,
                        "company_id": rec.company_id.id if "company_id" in FeedbackRequest._fields else False,
                    }
                    rec.feedback_request_id = FeedbackRequest.create(
                        {key: value for key, value in vals.items() if value}
                    ).id
            except Exception as e:
                rec.message_post(body=_("Auto-create feedback request failed: %s") % e)
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec._move_to_mapped_state("cancelled")
            # release any active room assignment
            try:
                rec.action_release_room()
            except Exception:
                pass
        return True

    def action_no_show(self):
        for rec in self:
            rec._move_to_mapped_state("no_show")
        return True

    # -------------------------------------------------------------------------
    # ACTIONS — Rooming (delegates to room / assignment models)
    # -------------------------------------------------------------------------
    def action_assign_room(self, room_id):
        """Assign this queue through the canonical clinic.room.assignment pivot."""
        self.ensure_one()
        room = self.env["clinic.room"].browse(room_id).exists()
        if not room:
            raise UserError(_("Target room does not exist."))
        if room.company_id and room.company_id != self.company_id:
            raise ValidationError(_("Queue and room must belong to the same company."))
        if "status" in room._fields and room.status in ("maintenance", "closed"):
            raise UserError(_("The selected room is not operationally available."))

        active_assignment = self.env["clinic.room.assignment"].search(
            [
                ("queue_id", "=", self.id),
                ("state", "in", ["assigned", "in_service"]),
                ("released_at", "=", False),
            ],
            limit=1,
        )
        if active_assignment:
            if active_assignment.room_id == room:
                return active_assignment.id
            active_assignment.action_release(reason="moved")

        assignment = self.env["clinic.room.assignment"].create(
            {
                "queue_id": self.id,
                "room_id": room.id,
                "company_id": self.company_id.id,
                "patient_id": self.patient_id.id if self.patient_id else False,
                "doctor_id": self.doctor_id.id if self.doctor_id else False,
                "treatment_id": self.treatment_id.id if self.treatment_id else False,
                "assigned_via": "manual",
            }
        )
        self.invalidate_recordset()
        return assignment.id

    def action_open_room_assignment(self):
        """Open the active room assignment or a prefilled assignment form."""
        self.ensure_one()
        assignment = self.room_assignment_id
        action = {
            "type": "ir.actions.act_window",
            "name": _("Room Assignment"),
            "res_model": "clinic.room.assignment",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_queue_id": self.id,
                "default_company_id": self.company_id.id,
                "default_patient_id": self.patient_id.id if self.patient_id else False,
                "default_doctor_id": self.doctor_id.id if self.doctor_id else False,
                "default_treatment_id": self.treatment_id.id if self.treatment_id else False,
            },
        }
        if assignment:
            action["res_id"] = assignment.id
        return action

    def action_release_room(self):
        """Release the current active room assignment without depending on room helpers."""
        for rec in self:
            assignment = rec.room_assignment_id
            if not assignment and rec.room_id:
                assignment = self.env["clinic.room.assignment"].search(
                    [
                        ("queue_id", "=", rec.id),
                        ("room_id", "=", rec.room_id.id),
                        ("state", "in", ["assigned", "in_service"]),
                        ("released_at", "=", False),
                    ],
                    limit=1,
                )
            if assignment:
                assignment.action_release(reason="completed")
            rec.write({"room_id": False, "room_assignment_id": False})
        return True

    # -------------------------------------------------------------------------
    # SLA Escalation (utility; cron/automation may call this)
    # -------------------------------------------------------------------------
    def action_check_and_escalate_sla(self):
        """
        Create escalation activities if SLA is breached and the stage is configured.
        Intended to be called from a scheduled action.
        """
        for rec in self:
            stg = rec.stage_id
            if not stg:
                continue
            # Waiting SLA breach
            if rec.sla_wait_breached and stg.activity_type_id:
                rec._create_escalation_activity(stg.activity_type_id, _("Waiting time SLA breached"))
            # Service SLA breach
            if rec.sla_service_breached and stg.activity_type_id:
                rec._create_escalation_activity(stg.activity_type_id, _("Service time SLA breached"))
        return True

    def _create_escalation_activity(self, activity_type, summary):
        """Create activities for escalation groups/users configured on the stage."""
        self.ensure_one()
        stg = self.stage_id
        if not stg:
            return False
        vals_common = {
            "res_id": self.id,
            "res_model_id": self.env["ir.model"]._get_id(self._name),
            "activity_type_id": activity_type.id,
            "summary": summary,
            "date_deadline": fields.Date.context_today(self),
            "user_id": False,  # assign to followers or specific users below
        }
        # For groups: assign to users in those groups
        users = self.env["res.users"].browse()
        if stg.escalate_group_ids:
            users |= self.env["res.users"].search([("groups_id", "in", stg.escalate_group_ids.ids)])
        if stg.escalate_user_ids:
            users |= stg.escalate_user_ids
        users = users.filtered(lambda u: u.active)

        Activity = self.env["mail.activity"]
        if users:
            for u in users:
                vals = dict(vals_common, user_id=u.id)
                Activity.create(vals)
        else:
            # fallback: unassigned activity
            Activity.create(vals_common)
        # Notify in chatter
        self.message_post(body=_("SLA escalation created: %s") % summary)
        return True

    # -------------------------------------------------------------------------
    # DISPLAY & SEARCH (Odoo 19)
    # -------------------------------------------------------------------------
    @api.depends("name", "token_id", "token_id.code", "patient_id", "patient_id.name")
    def _compute_display_name(self):
        for rec in self:
            label = rec.name or _("Queue")
            if rec.token_id and rec.token_id.code:
                label = f"{label} [{rec.token_id.code}]"
            if rec.patient_id:
                label = f"{label} — {rec.patient_id.display_name}"
            rec.display_name = label

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        domain = domain or []
        criteria = []
        if name:
            criteria = [
                "|", "|",
                ("name", operator, name),
                ("token_id.code", operator, name),
                ("patient_id.name", operator, name),
            ]
        recs = self.search(domain + criteria, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# -----------------------------------------------------------------------------
# Backward-compatibility alias (legacy model name)
# Keep while other modules still reference 'clinicone.clinical.queue'
# -----------------------------------------------------------------------------
# class LegacyCliniconeClinicalQueue(models.Model):
#     _name = "clinicone.clinical.queue"
#     _inherit = "clinic.queue"
#     _description = "Clinical Queue (Legacy Alias)"
#     _register = False
