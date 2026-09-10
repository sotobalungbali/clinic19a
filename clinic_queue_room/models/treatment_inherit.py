
# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18/19 CE)
# File: models/treatment_inherit.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicTreatment(models.Model):
    """
    Extend base clinic.treatment with Queue/Room/Device integrations and
    commercial/analytic hooks. Kept soft-coupled to allow optional addons.
    """
    _inherit = "clinic.treatment"

    # -------------------------------------------------------------------------
    # Core Links to Queue / Token / Room
    # -------------------------------------------------------------------------
    queue_id = fields.Many2one(
        comodel_name="clinic.queue",
        string="Queue",
        index=True,
        help="Linked queue where this treatment is being served."
    )
    token_id = fields.Many2one(
        comodel_name="clinic.queue.token",
        string="Token",
        index=True,
        help="Token associated with this treatment (if any)."
    )
    room_id = fields.Many2one(
        comodel_name="clinic.room",
        string="Room",
        index=True,
        help="Current room allocated to deliver this treatment."
    )
    room_assignment_id = fields.Many2one(
        comodel_name="clinic.room.assignment",
        string="Room Assignment",
        index=True,
        help="Room assignment record for this treatment (if any)."
    )

    # Subject mirrors (if base already has them, Odoo will merge definitions)
    patient_id = fields.Many2one(
        comodel_name="res.partner",
        string="Patient",
        index=True,
        help="Patient receiving the treatment."
    )
    doctor_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Doctor",
        index=True,
        domain=[("is_doctor", "=", True)],
        help="Doctor in charge of the treatment."
    )

    # -------------------------------------------------------------------------
    # Stage/State Mirrors from Queue
    # -------------------------------------------------------------------------
    queue_stage_id = fields.Many2one(
        comodel_name="clinic.queue.stage",
        string="Queue Stage",
        compute="_compute_queue_mirrors",
        store=True,
        help="Operational stage of the linked queue."
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
        help="Operational status of the linked queue."
    )

    # -------------------------------------------------------------------------
    # Timing (Clinic-side procedure timestamps)
    # -------------------------------------------------------------------------
    checkin_time = fields.Datetime(
        string="Check-in Time",
        help="Patient check-in time for this treatment (mirrors queue if linked)."
    )
    clinic_start_at = fields.Datetime(
        string="Procedure Start (Clinic)",
        help="Start time when the clinical procedure begins."
    )
    clinic_end_at = fields.Datetime(
        string="Procedure End (Clinic)",
        help="End time when the clinical procedure completes."
    )
    # Derived metrics
    waiting_duration_min = fields.Float(
        string="Waiting Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from check-in to procedure start."
    )
    procedure_duration_min = fields.Float(
        string="Procedure Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from procedure start to end."
    )
    total_visit_duration_min = fields.Float(
        string="Total Visit Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from check-in to procedure end."
    )

    # -------------------------------------------------------------------------
    # Device & Room Type Policies (soft-coupled)
    # -------------------------------------------------------------------------
    required_device_ids = fields.Many2many(
        comodel_name="clinic.device",
        relation="clinic_treatment_required_device_rel",
        column1="treatment_id",
        column2="device_id",
        string="Required Devices",
        help="Devices required to perform this treatment."
    )
    optional_device_ids = fields.Many2many(
        comodel_name="clinic.device",
        relation="clinic_treatment_optional_device_rel",
        column1="treatment_id",
        column2="device_id",
        string="Optional Devices",
        help="Devices recommended for this treatment."
    )
    used_device_ids = fields.Many2many(
        comodel_name="clinic.device",
        relation="clinic_treatment_used_device_rel",
        column1="treatment_id",
        column2="device_id",
        string="Devices Used",
        help="Devices actually used during the procedure."
    )
    preferred_room_type_id = fields.Many2one(
        comodel_name="clinic.room.type",
        string="Preferred Room Type",
        help="Preferred room type to perform this treatment."
    )

    # -------------------------------------------------------------------------
    # Commercial / Accounting Hooks (soft-coupled)
    # -------------------------------------------------------------------------
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sales Order",
        index=True,
        help="Sales Order associated with this treatment (if any)."
    )
    sale_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Sales Order Line",
        help="Sales order line created for this treatment (if any)."
    )
    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Customer Invoice",
        domain=[("move_type", "=", "out_invoice")],
        help="Invoice created for this treatment (if any)."
    )
    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytic Account",
        help="Analytic account to track this treatment's revenue/cost."
    )
    billable = fields.Boolean(
        string="Billable",
        default=True,
        help="If enabled, this treatment can be billed to the customer."
    )

    # Planned consumables (allow service/consu/product; domain safe across versions)
    planned_product_ids = fields.Many2many(
        comodel_name="product.product",
        relation="clinic_treatment_planned_product_rel",
        column1="treatment_id",
        column2="product_id",
        string="Planned Consumables",
        help="Consumables expected to be used during the procedure.",
        # Aman lintas versi: cek 'type' di product.product atau fallback ke product_tmpl_id.type
        domain=["|", ("type", "in", ["service", "consu", "product"]),
                     ("product_tmpl_id.type", "in", ["service", "consu", "product"])],
    )

    # Convenience flags
    has_active_queue = fields.Boolean(
        string="Has Active Queue",
        compute="_compute_flags",
        help="True if linked queue is Waiting / In Progress / On Hold."
    )
    is_in_procedure = fields.Boolean(
        string="In Procedure",
        compute="_compute_flags",
        help="True if the procedure has started and not ended."
    )

    # -------------------------------------------------------------------------
    # Optional cross-module pointers (soft-coupled; only active if addons exist)
    # -------------------------------------------------------------------------
    membership_id = fields.Many2one(
        comodel_name="clinic.membership",
        string="Membership",
        help="Membership used by this treatment (if any)."
    )
    insurance_policy_id = fields.Many2one(
        comodel_name="clinic.insurance.policy",
        string="Insurance Policy",
        help="Insurance policy used for this treatment (if any)."
    )
    authorization_id = fields.Many2one(
        comodel_name="clinic.insurance.authorization",
        string="Insurance Authorization",
        help="Insurance authorization for this treatment (if required)."
    )
    telemedicine_session_id = fields.Many2one(
        comodel_name="clinic.telemedicine.session",
        string="Telemedicine Session",
        help="Telemedicine session linked to this treatment (if any)."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends(
        "queue_id",
        "queue_id.stage_id",
        "queue_id.state",
        "queue_id.room_id",
        "queue_id.room_assignment_id",
        "queue_id.token_id",
        "queue_id.checkin_time",
    )
    def _compute_queue_mirrors(self):
        for rec in self:
            q = rec.queue_id
            rec.queue_stage_id = q.stage_id.id if q else False
            rec.queue_state = q.state if q else False
            if q:
                # Mirror links for quick filters
                rec.room_id = q.room_id.id if q.room_id else rec.room_id
                rec.room_assignment_id = q.room_assignment_id.id if q.room_assignment_id else rec.room_assignment_id
                rec.token_id = q.token_id.id if q.token_id else rec.token_id
                if q.checkin_time and not rec.checkin_time:
                    rec.checkin_time = q.checkin_time

    @api.depends("checkin_time", "clinic_start_at", "clinic_end_at")
    def _compute_durations(self):
        for rec in self:
            def minutes(a, b):
                if not a or not b:
                    return 0.0
                delta = fields.Datetime.to_datetime(b) - fields.Datetime.to_datetime(a)
                return round(max(delta.total_seconds() / 60.0, 0.0), 2)

            rec.waiting_duration_min = minutes(rec.checkin_time, rec.clinic_start_at)
            rec.procedure_duration_min = minutes(rec.clinic_start_at, rec.clinic_end_at)
            rec.total_visit_duration_min = minutes(rec.checkin_time, rec.clinic_end_at)

    @api.depends("queue_state", "clinic_start_at", "clinic_end_at")
    def _compute_flags(self):
        for rec in self:
            rec.has_active_queue = rec.queue_state in ("waiting", "in_progress", "on_hold")
            rec.is_in_procedure = bool(rec.clinic_start_at and not rec.clinic_end_at)

    # -------------------------------------------------------------------------
    # VALIDATIONS
    # -------------------------------------------------------------------------
    @api.constrains("doctor_id")
    def _check_doctor_flag(self):
        for rec in self:
            if rec.doctor_id and not getattr(rec.doctor_id, "is_doctor", False):
                raise ValidationError(_("Assigned Doctor must be a doctor (is_doctor = True)."))

    def _check_required_devices_present(self):
        """
        Ensure required devices are available in the selected room before starting.
        """
        for rec in self:
            if not rec.room_id or not rec.required_device_ids:
                continue
            have = set(rec.room_id.device_ids.ids) if "device_ids" in rec.room_id._fields else set()
            missing = set(rec.required_device_ids.ids) - have
            if missing:
                names = self.env["clinic.device"].browse(list(missing)).mapped("name")
                raise ValidationError(_("Room '%s' is missing required devices: %s")
                                      % (rec.room_id.display_name, ", ".join(names)))

    # -------------------------------------------------------------------------
    # ONCHANGES
    # -------------------------------------------------------------------------
    @api.onchange("queue_id")
    def _onchange_queue_id(self):
        """
        Keep treatment aligned with key data from queue when linked/changed.
        """
        if self.queue_id:
            if self.queue_id.patient_id and not self.patient_id:
                self.patient_id = self.queue_id.patient_id.id
            if self.queue_id.doctor_id and not self.doctor_id:
                self.doctor_id = self.queue_id.doctor_id.id
            if self.queue_id.room_id and not self.room_id:
                self.room_id = self.queue_id.room_id.id
            if self.queue_id.room_assignment_id and not self.room_assignment_id:
                self.room_assignment_id = self.queue_id.room_assignment_id.id
            if self.queue_id.checkin_time and not self.checkin_time:
                self.checkin_time = self.queue_id.checkin_time

    # -------------------------------------------------------------------------
    # BUSINESS ACTIONS — Treatment ↔ Queue / Room / Device
    # -------------------------------------------------------------------------
    def action_attach_queue(self, queue_id):
        """
        Attach an existing queue to this treatment.
        """
        self.ensure_one()
        q = self.env["clinic.queue"].browse(queue_id)
        if not q.exists():
            raise UserError(_("Queue does not exist."))
        self.queue_id = q.id
        # Mirror
        if q.patient_id and not self.patient_id:
            self.patient_id = q.patient_id.id
        if q.doctor_id and not self.doctor_id:
            self.doctor_id = q.doctor_id.id
        if q.room_id and not self.room_id:
            self.room_id = q.room_id.id
        if q.room_assignment_id and not self.room_assignment_id:
            self.room_assignment_id = q.room_assignment_id.id
        if q.token_id and not self.token_id:
            self.token_id = q.token_id.id
        if q.checkin_time and not self.checkin_time:
            self.checkin_time = q.checkin_time
        return True

    def action_assign_room(self, room_id):
        """
        Assign room through queue helper, then mirror to treatment.
        """
        self.ensure_one()
        if not self.queue_id:
            raise UserError(_("Please link or create a Queue first."))
        assignment_id = self.queue_id.action_assign_room(room_id)
        # Mirror
        self.room_id = self.queue_id.room_id.id if self.queue_id.room_id else self.room_id
        self.room_assignment_id = self.queue_id.room_assignment_id.id if self.queue_id.room_assignment_id else self.room_assignment_id
        return assignment_id

    def action_release_room(self):
        self.ensure_one()
        if self.queue_id:
            self.queue_id.action_release_room()
        return True

    def action_start_procedure(self):
        """
        Start procedure:
        - Validate room/device policies
        - Ensure queue exists (create minimal if missing)
        - Start queue (moves stage/state to In Progress)
        - Set clinic_start_at if not set
        """
        for rec in self:
            # Validate policy
            rec._check_required_devices_present()

            # Ensure queue exists
            if not rec.queue_id:
                q_vals = {
                    "patient_id": rec.patient_id.id if rec.patient_id else False,
                    "doctor_id": rec.doctor_id.id if rec.doctor_id else False,
                    "treatment_id": rec.id,
                    "company_id": rec.company_id.id if "company_id" in rec._fields and rec.company_id else rec.env.company.id,
                    "queue_type": getattr(rec, "queue_type", False) or "treatment",
                    "channel": "walkin",
                    "priority": "1",
                    "checkin_time": rec.checkin_time or fields.Datetime.now(),
                }
                q = self.env["clinic.queue"].create({k: v for k, v in q_vals.items()
                                                     if v or k in ("company_id", "queue_type", "channel", "checkin_time")})
                rec.queue_id = q.id

            # Assign current room if present
            if rec.room_id and not rec.queue_id.room_id:
                try:
                    rec.queue_id.action_assign_room(rec.room_id.id)
                except Exception as e:
                    rec.message_post(body=_("Auto-assign room failed: %s") % e)

            # Start queue & set start timestamp
            try:
                rec.queue_id.action_start()
            except Exception as e:
                rec.message_post(body=_("Queue start failed: %s") % e)

            if not rec.clinic_start_at:
                rec.clinic_start_at = rec.queue_id.start_time or fields.Datetime.now()
            if not rec.checkin_time:
                rec.checkin_time = rec.queue_id.checkin_time or fields.Datetime.now()
        return True

    def action_pause_procedure(self):
        """
        Pause by moving queue to On Hold.
        """
        for rec in self:
            if rec.queue_id:
                rec.queue_id.action_hold()
        return True

    def action_resume_procedure(self):
        """
        Resume by moving queue back to In Progress.
        """
        for rec in self:
            if rec.queue_id:
                rec.queue_id.action_resume()
        return True

    def action_finish_procedure(self):
        """
        Finish procedure:
        - Set clinic_end_at
        - Mark queue done (if not already)
        """
        for rec in self:
            if not rec.clinic_end_at:
                rec.clinic_end_at = fields.Datetime.now()
            if rec.queue_id and rec.queue_id.state not in ("done", "cancelled", "no_show"):
                try:
                    rec.queue_id.action_done()
                except Exception as e:
                    rec.message_post(body=_("Unable to mark queue done: %s") % e)
        return True

    def action_cancel_procedure(self, reason=None):
        for rec in self:
            if rec.queue_id and rec.queue_id.state not in ("done", "cancelled", "no_show"):
                try:
                    rec.queue_id.action_cancel(reason=reason)
                except Exception as e:
                    rec.message_post(body=_("Unable to cancel queue: %s") % e)
        return True

    def action_log_devices_used(self, device_ids):
        """
        Add devices used (Many2many update). Accept list/int.
        """
        self.ensure_one()
        if not device_ids:
            return True
        ids_ = device_ids if isinstance(device_ids, (list, tuple)) else [device_ids]
        self.used_device_ids = [(4, d) for d in ids_]
        return True

    # -------------------------------------------------------------------------
    # BILLING HOOKS (optional utilities; executed by pricing/billing automations)
    # -------------------------------------------------------------------------
    def prepare_so_line_vals(self, product_id=None, price_unit=0.0, qty=1.0, description=None):
        """
        Prepare a Sales Order Line vals for this treatment.
        Actual creation is handled by clinic_billing/clinic_pricing modules.
        """
        self.ensure_one()
        if not self.billable:
            return {}
        name = description or (self.display_name or _("Treatment"))
        return {
            "product_id": product_id or (getattr(self, "product_id", False) and self.product_id.id) or False,
            "product_uom_qty": qty or 1.0,
            "price_unit": price_unit or 0.0,
            "name": name,
            "analytic_account_id": self.analytic_account_id.id if self.analytic_account_id else False,
        }

    # -------------------------------------------------------------------------
    # UI HELPERS
    # -------------------------------------------------------------------------
    def action_view_queue(self):
        self.ensure_one()
        if not self.queue_id:
            raise UserError(_("No queue is linked to this treatment."))
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
            raise UserError(_("No room assignment is linked to this treatment."))
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
    # CRUD OVERRIDES (light)
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            # Auto-fill patient/doctor/check-in from linked queue if present
            if rec.queue_id:
                if rec.queue_id.patient_id and not rec.patient_id:
                    rec.patient_id = rec.queue_id.patient_id.id
                if rec.queue_id.doctor_id and not rec.doctor_id:
                    rec.doctor_id = rec.queue_id.doctor_id.id
                if rec.queue_id.checkin_time and not rec.checkin_time:
                    rec.checkin_time = rec.queue_id.checkin_time
        return recs

    def write(self, vals):
        res = super().write(vals)
        # If clinic_start_at set via write, ensure queue is started for consistency
        for rec in self:
            if "clinic_start_at" in vals and rec.clinic_start_at and rec.queue_id:
                try:
                    if rec.queue_id.state in ("waiting", "on_hold"):
                        rec.queue_id.action_start()
                except Exception as e:
                    rec.message_post(body=_("Queue start from treatment failed: %s") % e)
        return res
