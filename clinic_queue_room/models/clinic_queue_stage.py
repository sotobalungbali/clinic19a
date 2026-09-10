
# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18 CE)
# File: models/clinic_queue_stage.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicQueueStage(models.Model):
    _name = "clinic.queue.stage"
    _description = "Queue Stage"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"

    # -------------------------------------------------------------------------
    # Identity & Display
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Stage Name",
        required=True,
        index=True,
        tracking=True,
        help="Human-friendly name of the queue stage (e.g., Waiting, In Progress, Done).",
    )
    code = fields.Selection(
        selection=[
            ("waiting", "Waiting"),
            ("in_progress", "In Progress"),
            ("on_hold", "On Hold"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
            ("no_show", "No Show"),
        ],
        string="Technical Code",
        required=True,
        tracking=True,
        help=(
            "Technical code used by automations and cross-module integrations. "
            "Should map 1:1 with the operational queue state."
        ),
    )
    mapped_state = fields.Selection(
        selection=[
            ("waiting", "Waiting"),
            ("in_progress", "In Progress"),
            ("on_hold", "On Hold"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
            ("no_show", "No Show"),
        ],
        string="Mapped Operational State",
        required=True,
        help="Operational queue.state that this stage represents. Normally identical to Technical Code.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower value appears first. Used to order Kanban/statusbar stages."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive this stage. Archived stages are hidden from selection."
    )
    color = fields.Integer(
        string="Color Index",
        help="Color index used for Kanban cards and stage headers."
    )
    fold = fields.Boolean(
        string="Fold in Kanban",
        help="If enabled, this stage's Kanban column is folded (collapsed) by default."
    )

    # -------------------------------------------------------------------------
    # Company Scope & Typing
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company scope for this stage. Each company can have its own configuration."
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
        help="Categorize queues to different flows. Each type may apply different defaults and policies."
    )
    is_default = fields.Boolean(
        string="Default Stage",
        help="If enabled, new queues of this type will start in this stage by default (per company)."
    )

    # -------------------------------------------------------------------------
    # Policies & Requirements
    # -------------------------------------------------------------------------
    require_room = fields.Boolean(
        string="Require Room",
        help="If enabled, a room must be assigned before entering this stage."
    )
    require_doctor = fields.Boolean(
        string="Require Doctor",
        help="If enabled, a doctor must be assigned before entering this stage."
    )
    require_treatment = fields.Boolean(
        string="Require Treatment",
        help="If enabled, a treatment must be selected before entering this stage."
    )
    lock_patient_change = fields.Boolean(
        string="Lock Patient Change",
        help="If enabled, changing the patient while in this stage is not allowed."
    )
    lock_room_change_when_started = fields.Boolean(
        string="Lock Room Change When Started",
        help="If enabled, once service has started, the room cannot be changed in this stage."
    )

    # Preferred defaults for auto-assignment
    room_type_id = fields.Many2one(
        comodel_name="clinic.room.type",
        string="Preferred Room Type",
        help="Preferred room type for auto-assign when entering this stage."
    )

    auto_assign_room = fields.Boolean(
        string="Auto-Assign Room",
        help="If enabled, the system will try to auto-assign an available room when entering this stage."
    )
    auto_assign_doctor = fields.Boolean(
        string="Auto-Assign Doctor",
        help="If enabled, the system will try to auto-assign a doctor according to scheduling and availability."
    )
    auto_create_procedure_session = fields.Boolean(
        string="Auto-Create Procedure Session",
        help="If enabled, a procedure/treatment session will be created upon entering this stage."
    )

    # -------------------------------------------------------------------------
    # SLA / Escalation / Hooks
    # -------------------------------------------------------------------------
    sla_target_wait_min = fields.Float(
        string="SLA Target: Waiting (min)",
        help="Target waiting time from check-in until service start for queues in this stage."
    )
    sla_target_service_min = fields.Float(
        string="SLA Target: Service (min)",
        help="Target service time from start until completion for queues in this stage."
    )
    activity_type_id = fields.Many2one(
        comodel_name="mail.activity.type",
        string="Escalation Activity Type",
        help="Activity type created for escalation when SLA is breached."
    )
    escalate_group_ids = fields.Many2many(
        comodel_name="res.groups",
        relation="clinic_queue_stage_escalate_group_rel",
        column1="stage_id",
        column2="group_id",
        string="Escalate to Groups",
        help="Security groups to be notified/assigned when SLA is breached."
    )
    escalate_user_ids = fields.Many2many(
        comodel_name="res.users",
        relation="clinic_queue_stage_escalate_user_rel",
        column1="stage_id",
        column2="user_id",
        string="Escalate to Users",
        help="Specific users to be notified/assigned when SLA is breached."
    )
    mail_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="On Enter: Mail Template",
        help="If set, send this email/notification when a queue enters this stage."
    )
    mail_template_exit_id = fields.Many2one(
        comodel_name="mail.template",
        string="On Exit: Mail Template",
        help="If set, send this email/notification when a queue exits this stage."
    )
    server_action_id = fields.Many2one(
        comodel_name="ir.actions.server",
        string="On Enter: Server Action",
        help="Server action to run automatically when a queue enters this stage."
    )
    server_action_exit_id = fields.Many2one(
        comodel_name="ir.actions.server",
        string="On Exit: Server Action",
        help="Server action to run automatically when a queue exits this stage."
    )

    # -------------------------------------------------------------------------
    # Transitions & WIP Control
    # -------------------------------------------------------------------------
    next_stage_ids = fields.Many2many(
        comodel_name="clinic.queue.stage",
        relation="clinic_queue_stage_transition_rel",
        column1="from_stage_id",
        column2="to_stage_id",
        string="Allowed Next Stages",
        help="Whitelist of stages that queues are allowed to move to from this stage."
    )
    wip_limit = fields.Integer(
        string="WIP Limit",
        default=0,
        help="Work-In-Progress limit for this stage. 0 means unlimited."
    )
    active_queue_count = fields.Integer(
        string="Active Queue Count",
        compute="_compute_active_queue_count",
        help="Number of active queues currently in this stage (per company)."
    )
    is_wip_exceeded = fields.Boolean(
        string="WIP Exceeded",
        compute="_compute_is_wip_exceeded",
        help="Indicates whether the WIP limit is currently exceeded."
    )

    # -------------------------------------------------------------------------
    # Computes (optimized with read_group)
    # -------------------------------------------------------------------------
    @api.depends("company_id")
    def _compute_active_queue_count(self):
        """
        Count active queues in this stage using read_group for efficiency.
        Active states: waiting, in_progress, on_hold.
        """
        stage_ids = self.ids
        for rec in self:
            rec.active_queue_count = 0

        Queue = self.env["clinic.queue"] if "clinic.queue" in self.env else self.env["clinicone.clinical.queue"]
        if not stage_ids:
            return

        rows = Queue._read_group(
            domain=[
                ("active", "=", True),
                ("stage_id", "in", stage_ids),
                ("state", "in", ["waiting", "in_progress", "on_hold"]),
            ],
            groupby=["stage_id"],
            aggregates=["__count"],
        )
        mapped = {stage.id: count for stage, count in rows if stage}
        for stage in self:
            stage.active_queue_count = int(mapped.get(stage.id, 0))

    @api.depends("wip_limit", "active_queue_count")
    def _compute_is_wip_exceeded(self):
        for rec in self:
            rec.is_wip_exceeded = bool(rec.wip_limit and rec.wip_limit > 0 and rec.active_queue_count > rec.wip_limit)

    # -------------------------------------------------------------------------
    # Onchange helpers
    # -------------------------------------------------------------------------
    @api.onchange("code")
    def _onchange_code(self):
        for rec in self:
            if rec.code and not rec.mapped_state:
                rec.mapped_state = rec.code

    @api.onchange("is_default", "queue_type", "company_id")
    def _onchange_is_default(self):
        """UI hint only; server-side enforcement is in _enforce_unique_default()."""
        for rec in self:
            if rec.is_default and rec.queue_type and rec.company_id:
                domain = [
                    ("id", "!=", rec.id),
                    ("is_default", "=", True),
                    ("queue_type", "=", rec.queue_type),
                    ("company_id", "=", rec.company_id.id),
                    ("active", "=", True),
                ]
                if self.search_count(domain):
                    return {
                        "warning": {
                            "title": _("Another Default Stage exists"),
                            "message": _(
                                "There is already a default stage for '%(type)s' in '%(company)s'. "
                                "Saving will replace it."
                            ) % {
                                "type": dict(self._fields["queue_type"].selection).get(rec.queue_type),
                                "company": rec.company_id.display_name,
                            }
                        }
                    }

    # -------------------------------------------------------------------------
    # Business Helpers (to be called by clinic.queue transitions)
    # -------------------------------------------------------------------------
    def validate_requirements(self, queue):
        """
        Validate whether the given queue can enter this stage.
        Raise ValidationError if not satisfied.
        """
        self.ensure_one()
        if self.require_room and not queue.room_id:
            raise ValidationError(_("A room must be assigned before entering stage '%s'.") % self.name)
        if self.require_doctor and not queue.doctor_id:
            raise ValidationError(_("A doctor must be assigned before entering stage '%s'.") % self.name)
        if self.require_treatment and not queue.treatment_id:
            raise ValidationError(_("A treatment must be selected before entering stage '%s'.") % self.name)
        # WIP guard (only when changing to this stage)
        if self.wip_limit and self.wip_limit > 0 and queue.stage_id != self:
            self._compute_active_queue_count()  # refresh
            if self.active_queue_count >= self.wip_limit:
                raise ValidationError(_("WIP limit for stage '%s' has been reached.") % self.name)
        return True

    def mapped_state_value(self):
        """Return the operational mapped state value (string)."""
        self.ensure_one()
        return self.mapped_state or self.code

    def get_default_stage(self, company_id=None, queue_type=None):
        """
        Return default stage record for a given (company, queue_type).
        If not found, fallback to first by sequence in that scope.
        """
        company = company_id or self.env.company.id
        qtype = queue_type or "general"
        Stage = self.sudo().with_company(company)
        rec = Stage.search([
            ("company_id", "=", company),
            ("queue_type", "=", qtype),
            ("is_default", "=", True),
            ("active", "=", True),
        ], limit=1, order="sequence asc, id asc")
        if rec:
            return rec
        # Fallback: first by sequence
        return Stage.search([
            ("company_id", "=", company),
            ("queue_type", "=", qtype),
            ("active", "=", True),
        ], limit=1, order="sequence asc, id asc")

    # -------------------------------------------------------------------------
    # Stage Enter / Exit Hooks (used by clinic.queue on transition)
    # -------------------------------------------------------------------------
    def _run_on_enter_hooks(self, queue):
        """
        Execute configured side-effects when a queue enters this stage:
        - Auto-assign room/doctor
        - Auto-create procedure session
        - Run server action
        - Send mail template
        """
        self.ensure_one()
        # Auto-assign room (best-effort, skip errors to not block flow unless required)
        if self.auto_assign_room and not queue.room_id:
            try:
                self._auto_assign_room(queue)
            except Exception as e:
                if self.require_room:
                    raise
                queue.message_post(body=_("Auto-assign room failed: %s") % e)

        # Auto-assign doctor
        if self.auto_assign_doctor and not queue.doctor_id:
            try:
                self._auto_assign_doctor(queue)
            except Exception as e:
                if self.require_doctor:
                    raise
                queue.message_post(body=_("Auto-assign doctor failed: %s") % e)

        # Auto-create procedure session
        # if self.auto_create_procedure_session and not queue.procedure_session_id and queue.treatment_id:
        #     try:
        #         self._auto_create_procedure_session(queue)
        #     except Exception as e:
        #         queue.message_post(body=_("Auto-create procedure session failed: %s") % e)

        # Run server action (enter)
        if self.server_action_id:
            self.server_action_id.with_context(active_id=queue.id, active_model=queue._name).run()

        # Send mail (enter)
        if self.mail_template_id:
            self.mail_template_id.sudo().send_mail(queue.id, force_send=True)

    def _run_on_exit_hooks(self, queue):
        """
        Execute configured side-effects when a queue exits this stage:
        - Run server action (exit)
        - Send mail template (exit)
        """
        self.ensure_one()
        if self.server_action_exit_id:
            self.server_action_exit_id.with_context(active_id=queue.id, active_model=queue._name).run()
        if self.mail_template_exit_id:
            self.mail_template_exit_id.sudo().send_mail(queue.id, force_send=True)

    # -------------------------------------------------------------------------
    # Internals: Auto-assign helpers (can be overridden by other modules)
    # -------------------------------------------------------------------------
    def _auto_assign_room(self, queue):
        """
        Pick an available room, optionally filtered by room_type_id.
        Expected fields on clinic.room:
            - status in ('available', 'occupied', 'cleaning', 'maintenance')
            - company_id
            - room_type_id (optional)
        """
        self.ensure_one()
        Room = self.env["clinic.room"]
        dom = [
            ("company_id", "=", queue.company_id.id),
            ("status", "=", "available"),
            ("active", "=", True),
        ]
        if self.room_type_id:
            dom.append(("room_type_id", "=", self.room_type_id.id))

        room = Room.search(dom, limit=1, order="sequence asc, id asc") if "sequence" in Room._fields else Room.search(dom, limit=1)
        if not room:
            raise UserError(_("No available room found for stage '%s'.") % self.name)
        queue.write({"room_id": room.id})

    def _auto_assign_doctor(self, queue):
        """
        Basic doctor assignment. Expected (by integration):
            - hr.employee has boolean field is_doctor (from clinic_doctor)
            - Optional: scheduling/availability can be implemented by overriding this method
        """
        self.ensure_one()
        Doctor = self.env["hr.employee"]
        dom = [
            ("company_id", "=", queue.company_id.id),
            ("is_doctor", "=", True),
            ("active", "=", True),
        ]
        # Hints: prefer appointment's doctor if any
        preferred_id = getattr(queue.appointment_id, "doctor_id", False) and queue.appointment_id.doctor_id.id or False
        if preferred_id:
            queue.write({"doctor_id": preferred_id})
            return
        doctor = Doctor.search(dom, limit=1, order="name asc, id asc")
        if not doctor:
            raise UserError(_("No doctor available for company '%s'.") % queue.company_id.display_name)
        queue.write({"doctor_id": doctor.id})

    # def _auto_create_procedure_session(self, queue):
    #     """
    #     Create a procedure/treatment session record (provided by clinic_treatment or related module).
    #     Expected model name: clinic.procedure.session (configurable across implementations).
    #     """
    #     SessionModel = (
    #         self.env.get("clinic.procedure.session")
    #         or self.env.get("clinicone.procedure.session")  # legacy fallback
    #     )
    #     if not SessionModel:
    #         raise UserError(_("Procedure Session model is not available. Please install clinic_treatment."))
    #     vals = {
    #         "name": _("Session for %s") % (queue.name or queue.patient_id.display_name),
    #         "queue_id": queue.id if "queue_id" in SessionModel._fields else False,
    #         "patient_id": queue.patient_id.id if "patient_id" in SessionModel._fields else False,
    #         "doctor_id": queue.doctor_id.id if "doctor_id" in SessionModel._fields else False,
    #         "treatment_id": queue.treatment_id.id if "treatment_id" in SessionModel._fields else False,
    #         "company_id": queue.company_id.id if "company_id" in SessionModel._fields else False,
    #     }
    #     session = SessionModel.create({k: v for k, v in vals.items() if v or k not in vals})
    #     if "procedure_session_id" in queue._fields:
    #         queue.procedure_session_id = session.id

    # -------------------------------------------------------------------------
    # CRUD Overrides
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._enforce_unique_default()
        # Prevent self-transition on creation
        for rec in records:
            if rec.id in rec.next_stage_ids.ids:
                raise ValidationError(_("A stage cannot transition to itself. Remove the self-reference."))
        return records

    def write(self, vals):
        res = super().write(vals)
        # Default enforcement
        if any(k in vals for k in ("is_default", "queue_type", "company_id", "active")):
            for rec in self:
                rec._enforce_unique_default()
        # Prevent self-transition
        if "next_stage_ids" in vals:
            for rec in self:
                if rec.id in rec.next_stage_ids.ids:
                    raise ValidationError(_("A stage cannot transition to itself. Remove the self-reference."))
        return res

    # -------------------------------------------------------------------------
    # Internal Utilities
    # -------------------------------------------------------------------------
    def _enforce_unique_default(self):
        """Ensure only one default stage per (company, queue_type)."""
        for rec in self:
            if rec.active and rec.is_default:
                domain = [
                    ("id", "!=", rec.id),
                    ("company_id", "=", rec.company_id.id),
                    ("queue_type", "=", rec.queue_type),
                    ("is_default", "=", True),
                    ("active", "=", True),
                ]
                others = self.search(domain)
                if others:
                    others.write({"is_default": False})

    # -------------------------------------------------------------------------
    # Display & Search (Odoo 19)
    # -------------------------------------------------------------------------
    @api.depends("name", "queue_type")
    def _compute_display_name(self):
        type_map = dict(self._fields["queue_type"].selection)
        for rec in self:
            label = rec.name or _("Queue Stage")
            if rec.queue_type:
                label = f"{label} [{type_map.get(rec.queue_type, rec.queue_type)}]"
            rec.display_name = label

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        domain = domain or []
        criteria = []
        if name:
            criteria = ["|", ("name", operator, name), ("code", operator, name)]
        recs = self.search(domain + criteria, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]

    # -------------------------------------------------------------------------
    # Constraints & SQL
    # -------------------------------------------------------------------------
    @api.constrains("wip_limit")
    def _check_wip_limit(self):
        for rec in self:
            if rec.wip_limit is not None and rec.wip_limit < 0:
                raise ValidationError(_("WIP Limit cannot be negative."))

    @api.constrains("name", "company_id", "queue_type")
    def _check_unique_name_per_company_type(self):
        for rec in self:
            if not rec.name:
                continue
            domain = [
                ("id", "!=", rec.id),
                ("name", "=", rec.name),
                ("company_id", "=", rec.company_id.id),
                ("queue_type", "=", rec.queue_type),
            ]
            if self.search_count(domain):
                raise ValidationError(_("Stage Name must be unique per Company and Queue Type."))

    @api.constrains("code", "mapped_state")
    def _check_code_mapped_alignment(self):
        for rec in self:
            # Keep soft difference allowed, but block inconsistent 'done/cancel/no_show' vs mapped
            terminal = {"done", "cancelled", "no_show"}
            if (rec.code in terminal) != (rec.mapped_state in terminal):
                raise ValidationError(
                    _("Technical Code and Mapped Operational State must both be terminal or both be non-terminal.")
                )

    _code_company_type_unique = models.Constraint(
        "unique(code, company_id, queue_type)",
        "Technical Code must be unique per Company and Queue Type.",
    )


# -----------------------------------------------------------------------------
# Backward-compatibility alias (legacy model name)
# Keep while other modules still reference 'clinicone.clinical.queue.stage'
# -----------------------------------------------------------------------------
# class LegacyCliniconeClinicalQueueStage(models.Model):
#     _name = "clinicone.clinical.queue.stage"
#     _inherit = "clinic.queue.stage"
#     _description = "Queue Stage (Legacy Alias)"
#     _register = False
