# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18/19 CE)
# File: models/clinic_queue_visit.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicQueueVisit(models.Model):
    _name = "clinic.queue.visit"
    _description = "Clinic Queue Visit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_time desc, id desc"
    _rec_name = "display_name"

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Visit Number",
        readonly=True,
        copy=False,
        index=True,
        help="Auto-generated visit number from sequence."
    )
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda s: s.env.company,
        index=True
    )

    # -------------------------------------------------------------------------
    # Core links
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        index=True,
        help="Patient for this visit."
    )
    doctor_id = fields.Many2one(
        "hr.employee",
        string="Doctor",
        index=True,
        domain=[("is_doctor", "=", True)],
        help="Doctor in charge of this visit."
    )
    queue_id = fields.Many2one(
        "clinic.queue",
        string="Queue",
        index=True,
        help="Queue item associated with this visit."
    )
    token_id = fields.Many2one(
        "clinic.queue.token",
        string="Token",
        index=True,
        help="Token associated with this visit (if any)."
    )
    channel_id = fields.Many2one(
        "clinic.queue.channel",
        string="Channel",
        index=True,
        help="Channel through which this visit is created (Walk-in/Booking/Kiosk/etc.)."
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        index=True,
        help="Appointment linked to this visit, if any."
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        index=True,
        help="Treatment record linked to this visit, if any."
    )
    room_id = fields.Many2one(
        "clinic.room",
        string="Room",
        index=True,
        help="Room used for this visit."
    )
    room_assignment_id = fields.Many2one(
        "clinic.room.assignment",
        string="Room Assignment",
        index=True,
        help="Room assignment used for this visit (if allocated)."
    )

    # -------------------------------------------------------------------------
    # Timing & status
    # -------------------------------------------------------------------------
    checkin_time = fields.Datetime(
        string="Check-in Time",
        tracking=True,
        help="Time when the patient checked in."
    )
    start_time = fields.Datetime(
        string="Start Time",
        tracking=True,
        help="Clinical procedure start time."
    )
    end_time = fields.Datetime(
        string="End Time",
        tracking=True,
        help="Clinical procedure end time."
    )

    state = fields.Selection(
        [
            ("planned", "Planned"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
            ("no_show", "No Show"),
        ],
        string="Status",
        default="planned",
        tracking=True,
        index=True,
        help="Visit operational status."
    )

    waiting_duration_min = fields.Float(
        string="Waiting Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from check-in to start."
    )
    service_duration_min = fields.Float(
        string="Service Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from start to end."
    )
    total_duration_min = fields.Float(
        string="Total Duration (min)",
        compute="_compute_durations",
        store=True,
        help="Minutes from check-in to end."
    )

    # -------------------------------------------------------------------------
    # Commercial hooks (soft-coupled)
    # -------------------------------------------------------------------------
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sales Order",
        help="Sales Order associated with this visit (if any)."
    )
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Sales Order Line",
        help="Sales Order line for this visit (if any)."
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Customer Invoice",
        domain=[("move_type", "=", "out_invoice")],
        help="Invoice created for this visit (if any)."
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        help="Analytic account to track revenue/cost for this visit."
    )
    billable = fields.Boolean(
        string="Billable",
        default=True,
        help="Enable if this visit should be billed."
    )

    used_product_ids = fields.Many2many(
        "product.product",
        relation="clinic_visit_used_product_rel",
        column1="visit_id",
        column2="product_id",
        string="Products Used",
        help="Products/consumables/services used in this visit.",
        domain=["|", ("type", "in", ["service", "consu", "product"]),
                     ("product_tmpl_id.type", "in", ["service", "consu", "product"])],
    )

    # -------------------------------------------------------------------------
    # Notes
    # -------------------------------------------------------------------------
    notes = fields.Text(string="Notes")
    internal_note = fields.Text(string="Internal Note")

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    _visit_number_company_uniq = models.Constraint(
        "unique(company_id, name)",
        "Visit Number must be unique per company.",
    )

    @api.constrains("doctor_id")
    def _check_doctor_flag(self):
        for rec in self:
            if rec.doctor_id and not getattr(rec.doctor_id, "is_doctor", False):
                raise ValidationError(_("Assigned Doctor must have 'Is a Doctor' enabled."))

    @api.constrains("start_time", "end_time")
    def _check_time_order(self):
        for rec in self:
            if rec.start_time and rec.end_time and rec.end_time < rec.start_time:
                raise ValidationError(_("End Time cannot be earlier than Start Time."))

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------
    @api.depends("name", "patient_id")
    def _compute_display_name(self):
        for rec in self:
            p = rec.patient_id.display_name if rec.patient_id else ""
            rec.display_name = f"{rec.name or _('Visit')} - {p}" if p else (rec.name or _("Visit"))

    @api.depends("checkin_time", "start_time", "end_time")
    def _compute_durations(self):
        def minutes(a, b):
            if not a or not b:
                return 0.0
            delta = fields.Datetime.to_datetime(b) - fields.Datetime.to_datetime(a)
            return round(max(delta.total_seconds() / 60.0, 0.0), 2)

        for rec in self:
            rec.waiting_duration_min = minutes(rec.checkin_time, rec.start_time)
            rec.service_duration_min = minutes(rec.start_time, rec.end_time)
            rec.total_duration_min = minutes(rec.checkin_time, rec.end_time)

    # -------------------------------------------------------------------------
    # Onchanges (mirrors)
    # -------------------------------------------------------------------------
    @api.onchange("queue_id")
    def _onchange_queue_mirrors(self):
        if not self.queue_id:
            return
        q = self.queue_id
        if q.patient_id and not self.patient_id:
            self.patient_id = q.patient_id.id
        if q.doctor_id and not self.doctor_id:
            self.doctor_id = q.doctor_id.id
        if q.token_id and not self.token_id:
            self.token_id = q.token_id.id
        if q.room_id and not self.room_id:
            self.room_id = q.room_id.id
        if q.room_assignment_id and not self.room_assignment_id:
            self.room_assignment_id = q.room_assignment_id.id
        if q.channel_id and not self.channel_id:
            self.channel_id = q.channel_id.id
        if q.checkin_time and not self.checkin_time:
            self.checkin_time = q.checkin_time

    # -------------------------------------------------------------------------
    # Business actions
    # -------------------------------------------------------------------------
    def action_start(self):
        """Mark visit In Progress and start the queue if needed."""
        for rec in self:
            if rec.state in ("done", "cancelled", "no_show"):
                raise UserError(_("Cannot start a visit that is already finished/cancelled/no-show."))
            rec.state = "in_progress"
            if not rec.start_time:
                rec.start_time = fields.Datetime.now()
            # ensure a queue exists
            if not rec.queue_id:
                q_vals = {
                    "patient_id": rec.patient_id.id if rec.patient_id else False,
                    "doctor_id": rec.doctor_id.id if rec.doctor_id else False,
                    "company_id": rec.company_id.id,
                    "token_id": rec.token_id.id if rec.token_id else False,
                    "channel_id": rec.channel_id.id if rec.channel_id else False,
                    "checkin_time": rec.checkin_time or fields.Datetime.now(),
                    "queue_type": "visit",
                }
                q = self.env["clinic.queue"].create({k: v for k, v in q_vals.items() if v or k in ("company_id", "queue_type", "checkin_time")})
                rec.queue_id = q.id
            # start queue
            try:
                if hasattr(rec.queue_id, "action_start"):
                    rec.queue_id.action_start()
            except Exception as e:
                rec.message_post(body=_("Queue start failed: %s") % e)
        return True

    def action_finish(self):
        """Finish the visit and mark queue done."""
        for rec in self:
            if rec.state in ("cancelled", "no_show"):
                raise UserError(_("Cannot finish a cancelled/no-show visit."))
            rec.state = "done"
            if not rec.end_time:
                rec.end_time = fields.Datetime.now()
            if rec.queue_id and getattr(rec.queue_id, "state", None) not in ("done", "cancelled", "no_show"):
                try:
                    rec.queue_id.action_done()
                except Exception as e:
                    rec.message_post(body=_("Unable to mark queue done: %s") % e)
        return True

    def action_cancel(self, reason=None):
        """Cancel visit (and queue if appropriate)."""
        for rec in self:
            rec.state = "cancelled"
            if rec.queue_id and getattr(rec.queue_id, "state", None) not in ("done", "cancelled", "no_show"):
                try:
                    rec.queue_id.action_cancel(reason=reason)
                except Exception as e:
                    rec.message_post(body=_("Unable to cancel queue: %s") % e)
        return True

    def action_no_show(self):
        """Mark no-show and cancel queue."""
        for rec in self:
            rec.state = "no_show"
            if rec.queue_id and getattr(rec.queue_id, "state", None) not in ("done", "cancelled", "no_show"):
                try:
                    rec.queue_id.action_no_show()
                except Exception as e:
                    rec.message_post(body=_("Unable to mark queue as no-show: %s") % e)
        return True

    def action_view_queue(self):
        self.ensure_one()
        if not self.queue_id:
            raise UserError(_("No queue linked to this visit."))
        action = self.env.ref("clinic_queue_room.action_clinic_queue_form", raise_if_not_found=False)
        if action:
            data = action.read()[0]
            data.update({"res_id": self.queue_id.id, "view_mode": "form"})
            return data
        return {
            "type": "ir.actions.act_window",
            "name": _("Queue"),
            "res_model": "clinic.queue",
            "view_mode": "form,list,kanban",
            "res_id": self.queue_id.id,
        }

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = []
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("name"):
                # fall back to 'V-<id>' after create if sequence is unavailable
                vals["name"] = (
                    self.env["ir.sequence"].sudo().next_by_code("clinic.queue.visit")
                    or False
                )
            # mirror channel from queue if not provided
            if not vals.get("channel_id") and vals.get("queue_id"):
                q = self.env["clinic.queue"].browse(vals["queue_id"])
                if q.exists() and q.channel_id:
                    vals["channel_id"] = q.channel_id.id
            recs.append(vals)
        records = super().create(recs)
        # fill name if sequence was missing
        for r in records.filtered(lambda x: not x.name):
            r.name = f"V-{r.id:05d}"
        return records

    def write(self, vals):
        res = super().write(vals)
        # keep queue mirrors in sync if needed
        for rec in self:
            if rec.queue_id:
                if rec.patient_id and hasattr(rec.queue_id, "patient_id") and not rec.queue_id.patient_id:
                    rec.queue_id.patient_id = rec.patient_id.id
                if rec.doctor_id and hasattr(rec.queue_id, "doctor_id") and not rec.queue_id.doctor_id:
                    rec.queue_id.doctor_id = rec.doctor_id.id
                if rec.channel_id and hasattr(rec.queue_id, "channel_id") and not rec.queue_id.channel_id:
                    rec.queue_id.channel_id = rec.channel_id.id
        return res
