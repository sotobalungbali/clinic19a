# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18/19 CE)
# File: models/clinic_queue_ticket.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicQueueTicket(models.Model):
    _name = "clinic.queue.ticket"
    _description = "Clinic Queue Ticket"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "issue_time desc, id desc"
    _rec_name = "display_name"

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Ticket Number",
        readonly=True,
        copy=False,
        index=True,
        help="Auto-generated ticket number from sequence.",
    )
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda s: s.env.company,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Core Links
    # -------------------------------------------------------------------------
    queue_id = fields.Many2one(
        "clinic.queue",
        string="Queue",
        index=True,
        help="Queue item associated with this ticket.",
    )
    token_id = fields.Many2one(
        "clinic.queue.token",
        string="Token",
        index=True,
        help="Queue token (e.g., daily running number) bound to this ticket.",
    )
    channel_id = fields.Many2one(
        "clinic.queue.channel",
        string="Channel",
        index=True,
        help="Channel through which this ticket is issued (Walk-in/Booking/Kiosk/etc.).",
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        index=True,
        help="Patient for whom the ticket is issued.",
    )
    doctor_id = fields.Many2one(
        "hr.employee",
        string="Doctor",
        domain=[("is_doctor", "=", True)],
        index=True,
        help="Assigned doctor (if already known at ticket time).",
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        index=True,
        help="Linked appointment, if the ticket is generated from scheduling.",
    )
    visit_id = fields.Many2one(
        "clinic.queue.visit",
        string="Visit",
        index=True,
        help="Linked visit, when applicable.",
    )
    room_id = fields.Many2one(
        "clinic.room",
        string="Room",
        index=True,
        help="Room intended/used for this ticket (optional).",
    )
    room_assignment_id = fields.Many2one(
        "clinic.room.assignment",
        string="Room Assignment",
        index=True,
        help="Room assignment related to this ticket (optional).",
    )

    # -------------------------------------------------------------------------
    # Ticket lifecycle & validity
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("issued", "Issued"),
            ("used", "Used"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        string="Status",
        default="issued",
        index=True,
        tracking=True,
        help="Ticket lifecycle status.",
    )

    issue_time = fields.Datetime(
        string="Issue Time",
        default=lambda s: fields.Datetime.now(),
        index=True,
        tracking=True,
    )
    valid_until = fields.Datetime(
        string="Valid Until",
        help="Optional validity time. If set and elapsed, the ticket becomes Expired.",
    )
    is_valid = fields.Boolean(
        string="Is Valid",
        compute="_compute_is_valid",
        help="True if ticket is in Issued state and not past the Valid Until time (if any).",
    )

    # who issued
    issued_by_user_id = fields.Many2one(
        "res.users",
        string="Issued By",
        default=lambda s: s.env.user,
        readonly=True,
        help="User who issued the ticket.",
    )

    # printing/metadata (no hard dependency to any report)
    print_count = fields.Integer(
        string="Print Count",
        default=0,
        help="Number of times this ticket has been printed.",
    )
    note = fields.Text(string="Note")

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    _ticket_company_uniq = models.Constraint(
        "unique(company_id, name)",
        "Ticket Number must be unique per company.",
    )

    @api.constrains("doctor_id")
    def _check_doctor_flag(self):
        for rec in self:
            if rec.doctor_id and not getattr(rec.doctor_id, "is_doctor", False):
                raise ValidationError(_("Assigned Doctor must have 'Is a Doctor' enabled."))

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------
    @api.depends("name", "patient_id")
    def _compute_display_name(self):
        for rec in self:
            p = rec.patient_id.display_name if rec.patient_id else ""
            rec.display_name = f"{rec.name or _('Ticket')} - {p}" if p else (rec.name or _("Ticket"))

    @api.depends("state", "valid_until")
    def _compute_is_valid(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != "issued":
                rec.is_valid = False
            elif rec.valid_until and now > rec.valid_until:
                rec.is_valid = False
            else:
                rec.is_valid = True

    # -------------------------------------------------------------------------
    # Onchanges (mirror helpful fields)
    # -------------------------------------------------------------------------
    @api.onchange("queue_id")
    def _onchange_queue_fill(self):
        q = self.queue_id
        if not q:
            return
        if q.patient_id and not self.patient_id:
            self.patient_id = q.patient_id.id
        if q.doctor_id and not self.doctor_id:
            self.doctor_id = q.doctor_id.id
        if q.channel_id and not self.channel_id:
            self.channel_id = q.channel_id.id
        if q.room_id and not self.room_id:
            self.room_id = q.room_id.id
        if q.room_assignment_id and not self.room_assignment_id:
            self.room_assignment_id = q.room_assignment_id.id
        if q.visit_id and not self.visit_id and "visit_id" in q._fields:
            self.visit_id = q.visit_id.id

    @api.onchange("token_id")
    def _onchange_token_fill(self):
        t = self.token_id
        if not t:
            return
        # If the ticket has no number yet, try to display token's human label
        if not self.name and t.display_number:
            self.name = t.display_number
        if t.channel_id and not self.channel_id:
            self.channel_id = t.channel_id.id

    # -------------------------------------------------------------------------
    # Business Actions
    # -------------------------------------------------------------------------
    def action_mark_used(self):
        """Mark ticket as used. If a queue exists but is not linked, link this ticket to it."""
        for rec in self:
            if rec.state in ("cancelled", "expired"):
                raise UserError(_("Cannot mark a cancelled/expired ticket as used."))
            if rec.valid_until and fields.Datetime.now() > rec.valid_until:
                rec.state = "expired"
                raise UserError(_("Ticket is already expired."))
            rec.state = "used"
            if rec.queue_id and hasattr(rec.queue_id, "token_id") and not rec.queue_id.token_id:
                rec.queue_id.token_id = rec.token_id.id if rec.token_id else False
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "used":
                raise UserError(_("Cannot cancel a ticket that has been used."))
            rec.state = "cancelled"
            if reason:
                rec.message_post(body=_("Ticket cancelled. Reason: %s") % reason)
        return True

    def action_reissue(self):
        """Re-issue a new ticket (clone essential data) and cancel the current one."""
        new_vals = []
        for rec in self:
            if rec.state == "used":
                raise UserError(_("Cannot re-issue from a used ticket."))
            nv = {
                "company_id": rec.company_id.id,
                "patient_id": rec.patient_id.id if rec.patient_id else False,
                "doctor_id": rec.doctor_id.id if rec.doctor_id else False,
                "channel_id": rec.channel_id.id if rec.channel_id else False,
                "queue_id": rec.queue_id.id if rec.queue_id else False,
                "appointment_id": rec.appointment_id.id if rec.appointment_id else False,
                "visit_id": rec.visit_id.id if rec.visit_id else False,
                "room_id": rec.room_id.id if rec.room_id else False,
                "room_assignment_id": rec.room_assignment_id.id if rec.room_assignment_id else False,
                "note": rec.note,
            }
            new_vals.append(nv)
        new_tickets = self.create(new_vals)
        self.action_cancel(reason=_("Re-issued to %s") % ", ".join(new_tickets.mapped("name")))
        return {
            "type": "ir.actions.act_window",
            "name": _("New Tickets"),
            "res_model": "clinic.queue.ticket",
            "view_mode": "list,form",
            "domain": [("id", "in", new_tickets.ids)],
        }

    def action_print(self):
        """Try print via a report if available; otherwise just increase print count."""
        report = self.env.ref("clinic_queue_room.report_clinic_queue_ticket", raise_if_not_found=False)
        if report:
            for rec in self:
                rec.print_count = (rec.print_count or 0) + 1
            return report.report_action(self)
        # Fallback: no report defined
        for rec in self:
            rec.print_count += 1
            rec.message_post(body=_("Ticket printed (no report template configured)."))
        return True

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = []
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("name"):
                vals["name"] = (
                    self.env["ir.sequence"].sudo().next_by_code("clinic.queue.ticket")
                    or False
                )
            if not vals.get("issue_time"):
                vals["issue_time"] = fields.Datetime.now()
            # inherit mirrors from queue if provided
            qid = vals.get("queue_id")
            if qid:
                q = self.env["clinic.queue"].browse(qid)
                if q.exists():
                    vals.setdefault("patient_id", q.patient_id.id if q.patient_id else False)
                    vals.setdefault("doctor_id", q.doctor_id.id if q.doctor_id else False)
                    vals.setdefault("channel_id", q.channel_id.id if q.channel_id else False)
            # inherit channel from token if missing
            if not vals.get("channel_id") and vals.get("token_id"):
                t = self.env["clinic.queue.token"].browse(vals["token_id"])
                if t.exists() and t.channel_id:
                    vals["channel_id"] = t.channel_id.id
            records.append(vals)
        recs = super().create(records)
        # fill name if sequence was not configured
        for r in recs.filtered(lambda x: not x.name):
            r.name = f"T-{r.id:05d}"
        return recs

    def write(self, vals):
        res = super().write(vals)
        # keep back references in queue if useful
        if "queue_id" in vals and vals["queue_id"]:
            for rec in self.filtered(lambda r: r.queue_id and "ticket_id" in r.queue_id._fields):
                if not rec.queue_id.ticket_id:
                    rec.queue_id.ticket_id = rec.id
        return res
