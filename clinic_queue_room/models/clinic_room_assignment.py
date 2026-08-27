# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18 CE)
# File: models/clinic_room_assignment.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicRoomAssignment(models.Model):
    _name = "clinic.room.assignment"
    _description = "Clinic Room Assignment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "assigned_at desc, id desc"
    _rec_name = "name"

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Assignment Reference",
        default="New",
        copy=False,
        index=True,
        tracking=True,
        help="Unique reference for this room assignment. Generated from a sequence."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive this assignment record."
    )

    # -------------------------------------------------------------------------
    # Scoping
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company responsible for this assignment."
    )

    # -------------------------------------------------------------------------
    # Core Links
    # -------------------------------------------------------------------------
    room_id = fields.Many2one(
        comodel_name="clinic.room",
        string="Room",
        required=True,
        index=True,
        tracking=True,
        help="Room to which the queue is assigned."
    )
    queue_id = fields.Many2one(
        comodel_name="clinic.queue",
        string="Queue",
        required=True,
        index=True,
        tracking=True,
        help="Queue entry assigned to the room."
    )

    # Denormalized helpers (for reporting/search)
    room_type_id = fields.Many2one(
        comodel_name="clinic.room.type",
        string="Room Type",
        related="room_id.room_type_id",
        store=True,
        readonly=True,
        help="Room type of the assigned room."
    )
    patient_id = fields.Many2one(
        comodel_name="res.partner",
        string="Patient",
        related="queue_id.patient_id",
        store=True,
        index=True,
        readonly=True,
        help="Patient from the queue."
    )
    doctor_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Doctor",
        related="queue_id.doctor_id",
        store=True,
        index=True,
        readonly=True,
        help="Doctor handling the queue."
    )
    treatment_id = fields.Many2one(
        comodel_name="clinic.treatment",
        string="Treatment",
        related="queue_id.treatment_id",
        store=True,
        index=True,
        readonly=True,
        help="Treatment planned/performed for the queue."
    )

    # -------------------------------------------------------------------------
    # Assignment Lifecycle
    # -------------------------------------------------------------------------
    assigned_at = fields.Datetime(
        string="Assigned At",
        default=lambda self: fields.Datetime.now(),
        required=True,
        tracking=True,
        help="Timestamp when the queue was assigned to the room."
    )
    assigned_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Assigned By",
        default=lambda self: self.env.user,
        help="User who created the assignment."
    )
    assigned_via = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("auto", "Auto"),
            ("token", "Token"),
            ("kiosk", "Kiosk"),
            ("api", "API"),
        ],
        string="Assigned Via",
        default="manual",
        help="How this assignment was created."
    )

    # Service timing (optional but useful per-room, in addition to queue timings)
    service_start_at = fields.Datetime(
        string="Service Start At",
        tracking=True,
        help="Timestamp when the service actually started in this room."
    )
    service_end_at = fields.Datetime(
        string="Service End At",
        tracking=True,
        help="Timestamp when the service ended in this room."
    )

    released_at = fields.Datetime(
        string="Released At",
        index=True,
        tracking=True,
        help="Timestamp when the room was released from this assignment."
    )
    release_reason = fields.Selection(
        selection=[
            ("completed", "Completed"),
            ("moved", "Moved/Transferred"),
            ("cancelled", "Cancelled"),
            ("timeout", "Timeout"),
            ("other", "Other"),
        ],
        string="Release Reason",
        help="Reason for releasing this room from the assignment."
    )
    released_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Released By",
        help="User who released the room."
    )

    # State (stored for quick filtering; derived from timestamps)
    state = fields.Selection(
        selection=[
            ("assigned", "Assigned"),
            ("in_service", "In Service"),
            ("released", "Released"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="assigned",
        index=True,
        tracking=True,
        help="Operational state of the room assignment."
    )

    # -------------------------------------------------------------------------
    # Devices Used (integration with clinic.device)
    # -------------------------------------------------------------------------
    device_ids = fields.Many2many(
        comodel_name="clinic.device", # comodel_name="clinic.device",
        relation="clinic_room_assignment_device_rel",
        column1="assignment_id",
        column2="device_id",
        string="Devices Used",
        help="Devices used during this assignment."
    )

    # -------------------------------------------------------------------------
    # Commercial / Accounting Hooks (optional)
    # -------------------------------------------------------------------------
    surcharge_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Surcharge Product",
        help="Optional product to charge for room usage; defaults from room/room type."
    )
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sales Order",
        index=True,
        help="Sales Order to which surcharge lines may be added."
    )
    sale_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Sales Order Line",
        help="Sales Order line created for the surcharge, if any."
    )
    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Customer Invoice",
        domain=[("move_type", "=", "out_invoice")],
        help="Invoice that includes the surcharge for this assignment, if any."
    )
    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytic Account",
        help="Analytic account for tracking cost/revenue of this assignment."
    )
    billable = fields.Boolean(
        string="Billable",
        default=False,
        help="If enabled, this assignment is intended to create a surcharge line."
    )

    # -------------------------------------------------------------------------
    # Notes
    # -------------------------------------------------------------------------
    notes = fields.Text(
        string="Notes",
        help="Internal notes about this assignment."
    )

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------
    wait_before_service_min = fields.Float(
        string="Waiting Before Service (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from 'Assigned At' to 'Service Start At'."
    )
    service_duration_min = fields.Float(
        string="Service Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from 'Service Start At' to 'Service End At'."
    )
    occupancy_duration_min = fields.Float(
        string="Occupancy Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from 'Assigned At' to 'Released At' (or Now if still active)."
    )
    is_active_assignment = fields.Boolean(
        string="Is Active Assignment",
        compute="_compute_is_active",
        help="True if assignment is not yet released."
    )

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------
    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "Assignment Reference must be unique per company.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("released_at")
    def _compute_is_active(self):
        for rec in self:
            rec.is_active_assignment = not bool(rec.released_at)

    @api.depends("assigned_at", "service_start_at", "service_end_at", "released_at")
    def _compute_durations(self):
        for rec in self:
            def minutes(a, b):
                if not a or not b:
                    return 0.0
                delta = fields.Datetime.to_datetime(b) - fields.Datetime.to_datetime(a)
                return round(max(delta.total_seconds() / 60.0, 0.0), 2)

            rec.wait_before_service_min = minutes(rec.assigned_at, rec.service_start_at)
            rec.service_duration_min = minutes(rec.service_start_at, rec.service_end_at)

            end_ref = rec.released_at or fields.Datetime.now()
            rec.occupancy_duration_min = minutes(rec.assigned_at, end_ref)

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("room_id")
    def _onchange_room_id(self):
        """Pull optional commercial defaults without assuming sibling fields exist.

        ``clinic_room_device`` is already a frozen upstream addon.  Its current
        ``clinic.room`` / ``clinic.room.type`` contract does not guarantee room
        surcharge or analytic fields, so this addon must soft-read those
        optional hooks instead of dereferencing them unconditionally.
        """
        room = self.room_id
        if not room:
            return

        room_type = room.room_type_id
        if not self.surcharge_product_id:
            if "surcharge_product_id" in room._fields and room.surcharge_product_id:
                self.surcharge_product_id = room.surcharge_product_id
            elif (
                room_type
                and "surcharge_product_id" in room_type._fields
                and room_type.surcharge_product_id
            ):
                self.surcharge_product_id = room_type.surcharge_product_id

        if not self.analytic_account_id:
            if "analytic_account_id" in room._fields and room.analytic_account_id:
                self.analytic_account_id = room.analytic_account_id
            elif (
                room_type
                and "analytic_account_id" in room_type._fields
                and room_type.analytic_account_id
            ):
                self.analytic_account_id = room_type.analytic_account_id

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("room_id", "released_at")
    def _check_room_capacity(self):
        """Enforce the frozen Clinic Room booking policy and capacity contract.

        ``clinic.room`` exposes ``booking_policy`` (exclusive/shared/
        queue_based) and ``capacity``.  Earlier queue code assumed an
        ``allow_multi_patient`` field that does not exist in the frozen room
        addon; using the canonical fields here keeps ownership in the upstream
        addon without reopening it.
        """
        for rec in self:
            if not rec.room_id or rec.released_at:
                continue

            room = rec.room_id.sudo()
            dom = [
                ("id", "!=", rec.id),
                ("room_id", "=", room.id),
                ("released_at", "=", False),
                ("active", "=", True),
            ]
            current_total = self.search_count(dom) + 1
            capacity = max(room.capacity or 1, 1)
            booking_policy = room.booking_policy or "exclusive"

            if booking_policy == "exclusive" and current_total > 1:
                raise ValidationError(
                    _("Room '%s' uses an exclusive booking policy and already has an active patient.")
                    % room.display_name
                )
            if booking_policy != "exclusive" and current_total > capacity:
                raise ValidationError(
                    _("Room '%(room)s' capacity exceeded: %(cur)d > %(cap)d.")
                    % {
                        "room": room.display_name,
                        "cur": current_total,
                        "cap": capacity,
                    }
                )

    @api.constrains("queue_id", "released_at", "active")
    def _check_single_active_assignment_per_queue(self):
        """
        A queue must not have more than one active assignment at the same time.
        """
        for rec in self:
            if not rec.queue_id or rec.released_at:
                continue
            dom = [
                ("id", "!=", rec.id),
                ("queue_id", "=", rec.queue_id.id),
                ("released_at", "=", False),
                ("active", "=", True),
            ]
            if self.search_count(dom):
                raise ValidationError(_("Queue '%s' already has an active room assignment.") % rec.queue_id.display_name)

    @api.constrains("service_start_at", "service_end_at", "assigned_at", "released_at")
    def _check_time_sequence(self):
        for rec in self:
            if rec.service_start_at and rec.assigned_at and rec.service_start_at < rec.assigned_at:
                raise ValidationError(_("Service Start cannot be earlier than Assigned At."))
            if rec.service_end_at and rec.service_start_at and rec.service_end_at < rec.service_start_at:
                raise ValidationError(_("Service End cannot be earlier than Service Start."))
            if rec.released_at and rec.assigned_at and rec.released_at < rec.assigned_at:
                raise ValidationError(_("Released At cannot be earlier than Assigned At."))

    # -------------------------------------------------------------------------
    # CREATE / WRITE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        # Prepare refs and defaults
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("assigned_at"):
                vals["assigned_at"] = fields.Datetime.now()
            # Sequence for name
            if not vals.get("name") or vals.get("name") == "New":
                seq = self.env["ir.sequence"].next_by_code("clinic.room.assignment") \
                      or self.env["ir.sequence"].next_by_code("clinicone.clinical.room.assignment") \
                      or _("New")
                vals["name"] = seq
        records = super().create(vals_list)

        # Post-create hooks: link queue, bump room status, subscribe participants
        for rec in records:
            rec._link_queue_and_room()
            rec._ensure_room_status_on_assign()
            rec._auto_subscribe_partners()

        return records

    def write(self, vals):
        res = super().write(vals)

        # Reflect important changes
        for rec in self:
            # When released, set state and room status
            if "released_at" in vals and rec.released_at:
                if rec.state != "cancelled":
                    rec.state = "released"
                rec._ensure_room_status_on_release()
            # When service_start_at set, state becomes in_service
            if "service_start_at" in vals and rec.service_start_at:
                rec.state = "in_service"
                # Start the queue if still waiting/on_hold
                if rec.queue_id and rec.queue_id.state in ("waiting", "on_hold"):
                    try:
                        rec.queue_id.action_start()
                    except Exception as e:
                        rec.message_post(body=_("Queue start failed: %s") % e)
            # When service_end_at set, optionally mark queue done (do not force)
            if "service_end_at" in vals and rec.service_end_at:
                # leave finalization to queue flow; can be automated via server action
                pass

        return res

    # -------------------------------------------------------------------------
    # INTERNAL HOOKS
    # -------------------------------------------------------------------------
    def _link_queue_and_room(self):
        """Ensure queue points to this room and assignment if such fields exist."""
        for rec in self:
            q = rec.queue_id
            if not q or not q.exists():
                continue
            vals = {}
            if "room_id" in q._fields and not q.room_id:
                vals["room_id"] = rec.room_id.id
            if "room_assignment_id" in q._fields:
                vals["room_assignment_id"] = rec.id
            if vals:
                q.write(vals)

    def _active_assignment_count_for_room(self, room):
        """Return active assignment count using this addon's own canonical pivot."""
        return self.search_count(
            [
                ("room_id", "=", room.id),
                ("state", "in", ["assigned", "in_service"]),
                ("released_at", "=", False),
            ]
        )

    def _ensure_room_status_on_assign(self):
        """Mark an available room occupied without requiring sibling-addon helpers."""
        for rec in self:
            room = rec.room_id
            if room and "status" in room._fields and room.status == "available":
                room.write({"status": "occupied"})

    def _ensure_room_status_on_release(self):
        """Return the room to Available when the last active assignment is released."""
        for rec in self:
            room = rec.room_id
            if not room or "status" not in room._fields:
                continue
            if self._active_assignment_count_for_room(room) == 0 and room.status == "occupied":
                room.write({"status": "available"})

    def _auto_subscribe_partners(self):
        """Subscribe patient (and doctor user) to chatter for context awareness."""
        for rec in self:
            subs = []
            if rec.patient_id and not rec.patient_id.partner_share:
                subs.append(rec.patient_id.id)
            if rec.doctor_id and rec.doctor_id.user_id and rec.doctor_id.user_id.partner_id:
                subs.append(rec.doctor_id.user_id.partner_id.id)
            if subs:
                rec.message_subscribe(partner_ids=list(set(subs)))

    # -------------------------------------------------------------------------
    # BUSINESS ACTIONS
    # -------------------------------------------------------------------------
    def action_mark_service_start(self):
        for rec in self:
            if rec.service_start_at:
                continue
            rec.write({"service_start_at": fields.Datetime.now(), "state": "in_service"})
            # Start queue if needed
            if rec.queue_id and rec.queue_id.state in ("waiting", "on_hold"):
                try:
                    rec.queue_id.action_start()
                except Exception as e:
                    rec.message_post(body=_("Queue start failed: %s") % e)
        return True

    def action_mark_service_end(self):
        for rec in self:
            if not rec.service_start_at:
                # allow marking end without start, but warn
                rec.message_post(body=_("Service end recorded without a prior start timestamp."))
            rec.write({"service_end_at": fields.Datetime.now()})
        return True

    def action_release(self, reason="completed", set_cleaning=None):
        """
        Release the room from this assignment now.
        Optionally move the room to 'cleaning' (default if policy requires) or 'available'.
        """
        for rec in self:
            if rec.released_at:
                continue
            rec.write({
                "released_at": fields.Datetime.now(),
                "released_by_id": self.env.user.id,
                "release_reason": reason or "completed",
                "state": "released" if rec.state != "cancelled" else rec.state,
            })
            # Keep room status aligned using the assignment pivot owned here.
            room = rec.room_id
            rec._ensure_room_status_on_release()
            # Inform queue
            if rec.queue_id:
                rec.queue_id.message_post(body=_("Released from room <b>%s</b>.") % (room.display_name or room.name))
        return True

    def action_cancel(self):
        for rec in self:
            if rec.released_at:
                # already released; mark as cancelled for bookkeeping
                rec.write({"state": "cancelled"})
                continue
            rec.write({
                "state": "cancelled",
                "released_at": fields.Datetime.now(),
                "released_by_id": self.env.user.id,
                "release_reason": "cancelled",
            })
            rec._ensure_room_status_on_release()
        return True

    def action_transfer(self, target_room_id):
        """
        Transfer the assignment to another room:
        - Release current
        - Create a new assignment with same queue in target room
        """
        self.ensure_one()
        target_room = self.env["clinic.room"].browse(target_room_id)
        if not target_room.exists():
            raise UserError(_("Target room does not exist."))
        if target_room.company_id and target_room.company_id != self.company_id:
            raise ValidationError(_("Target room must belong to the same company."))
        if "status" in target_room._fields and target_room.status in ("maintenance", "closed"):
            raise UserError(_("Target room is not operationally available."))
        capacity = max(target_room.capacity or 1, 1)
        booking_policy = target_room.booking_policy or "exclusive"
        active_count = self._active_assignment_count_for_room(target_room)
        if booking_policy == "exclusive" and active_count:
            raise UserError(_("Target room uses an exclusive booking policy and is already occupied."))
        if booking_policy != "exclusive" and active_count >= capacity:
            raise UserError(_("Target room has reached its configured capacity."))

        # Optional commercial defaults are soft-coupled.  The frozen room
        # addon does not guarantee these fields on room or room type.
        target_room_type = target_room.room_type_id
        surcharge_product = False
        if "surcharge_product_id" in target_room._fields and target_room.surcharge_product_id:
            surcharge_product = target_room.surcharge_product_id
        elif (
            target_room_type
            and "surcharge_product_id" in target_room_type._fields
            and target_room_type.surcharge_product_id
        ):
            surcharge_product = target_room_type.surcharge_product_id

        analytic_account = False
        if "analytic_account_id" in target_room._fields and target_room.analytic_account_id:
            analytic_account = target_room.analytic_account_id
        elif (
            target_room_type
            and "analytic_account_id" in target_room_type._fields
            and target_room_type.analytic_account_id
        ):
            analytic_account = target_room_type.analytic_account_id

        # Release current
        self.action_release(reason="moved", set_cleaning=None)

        # Create new assignment
        new_vals = {
            "room_id": target_room.id,
            "queue_id": self.queue_id.id,
            "company_id": self.company_id.id,
            "assigned_via": "manual",
            "device_ids": [(6, 0, self.device_ids.ids)],
            "surcharge_product_id": surcharge_product.id if surcharge_product else False,
            "analytic_account_id": analytic_account.id if analytic_account else False,
        }
        new_assignment = self.create(new_vals)
        return new_assignment.id

    # -------------------------------------------------------------------------
    # BILLING HOOK (optional utility; invoked by automations in billing module)
    # -------------------------------------------------------------------------
    def prepare_surcharge_line_vals(self, partner_id=None, price_unit=0.0, quantity=1.0):
        """
        Prepare vals for a Sales Order Line to bill room surcharge.
        (Actual creation is handled by clinic_billing/clinic_pricing automations.)
        """
        self.ensure_one()
        if not self.billable or not self.surcharge_product_id:
            return {}
        return {
            "product_id": self.surcharge_product_id.id,
            "product_uom_qty": quantity or 1.0,
            "price_unit": price_unit or 0.0,
            "name": _("%s — Room Surcharge (%s)") % (self.room_id.display_name, self.name),
            "customer_lead": 0.0,
            "analytic_account_id": self.analytic_account_id.id if self.analytic_account_id else False,
        }

    # -------------------------------------------------------------------------
    # DISPLAY (Odoo 19)
    # -------------------------------------------------------------------------
    @api.depends("name", "room_id", "room_id.name", "patient_id", "patient_id.name")
    def _compute_display_name(self):
        for rec in self:
            label = rec.name or _("Assignment")
            parts = [label]
            if rec.room_id:
                parts.append(f"[{rec.room_id.display_name}]")
            if rec.patient_id:
                parts.append(f"— {rec.patient_id.display_name}")
            rec.display_name = " ".join(parts)

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        domain = domain or []
        criteria = []
        if name:
            criteria = ["|", ("name", operator, name), ("room_id.name", operator, name)]
        recs = self.search(domain + criteria, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# -----------------------------------------------------------------------------
# Backward-compatibility alias (legacy model name)
# Keep while other modules still reference 'clinicone.clinical.room.assignment'
# -----------------------------------------------------------------------------
# class LegacyCliniconeClinicalRoomAssignment(models.Model):
#     _name = "clinicone.clinical.room.assignment"
#     _inherit = "clinic.room.assignment"
#     _description = "Clinic Room Assignment (Legacy Alias)"
#     _register = False
