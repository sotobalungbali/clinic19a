# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicARFollowupLevel(models.Model):
    _name = "clinic.ar.followup.level"
    _description = "Accounts Receivable Follow-up Level"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    delay_days = fields.Integer(
        default=0,
        required=True,
        help="Days after invoice due date when this level becomes due.",
    )
    reminder_type = fields.Selection(
        [
            ("email", "Email"),
            ("call", "Call"),
            ("letter", "Letter"),
            ("portal", "Portal"),
            ("sms", "SMS"),
            ("whatsapp", "WhatsApp"),
        ],
        default="email",
        required=True,
    )
    template_id = fields.Many2one(
        "mail.template",
        string="Email Template",
        domain="[('model', 'in', ('clinic.ar.followup', 'clinic.ar.invoice', 'res.partner'))]",
    )
    activity_type_id = fields.Many2one("mail.activity.type")
    description = fields.Text()
    active = fields.Boolean(default=True)

    _name_company_unique = models.Constraint(
        "UNIQUE (name, company_id)",
        "Follow-up Level name must be unique per company.",
    )

    @api.constrains("delay_days")
    def _check_delay_days(self):
        for rec in self:
            if rec.delay_days < 0:
                raise ValidationError(_("Delay Days cannot be negative."))


class ClinicARFollowup(models.Model):
    _name = "clinic.ar.followup"
    _description = "Accounts Receivable Follow-up"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "scheduled_date asc, id asc"
    _check_company_auto = True

    name = fields.Char(
        string="Follow-up Number",
        default="/",
        required=True,
        readonly=True,
        copy=False,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    invoice_id = fields.Many2one(
        "clinic.ar.invoice",
        required=True,
        ondelete="cascade",
        check_company=True,
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        related="invoice_id.partner_id",
        store=True,
        index=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        related="invoice_id.patient_id",
        store=True,
        index=True,
    )
    level_id = fields.Many2one(
        "clinic.ar.followup.level",
        required=True,
        check_company=True,
        index=True,
    )
    level_sequence = fields.Integer(related="level_id.sequence", store=True)
    booking_id = fields.Many2one(
        "booking.booking",
        related="invoice_id.booking_id",
        store=True,
    )
    treatment_session_id = fields.Many2one(
        "clinic.treatment.session",
        related="invoice_id.treatment_session_id",
        store=True,
    )
    membership_id = fields.Many2one(
        "membership.contract",
        related="invoice_id.membership_id",
        store=True,
    )

    scheduled_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        index=True,
        tracking=True,
    )
    sent_date = fields.Datetime(readonly=True)
    next_scheduled_date = fields.Date(readonly=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("sent", "Sent"),
            ("skipped", "Skipped"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    reminder_type = fields.Selection(
        related="level_id.reminder_type",
        store=True,
    )
    template_id = fields.Many2one(
        "mail.template",
        related="level_id.template_id",
        store=True,
    )
    activity_type_id = fields.Many2one(
        "mail.activity.type",
        related="level_id.activity_type_id",
        store=True,
    )
    days_overdue_at_schedule = fields.Integer(readonly=True)
    amount_residual_at_schedule = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="invoice_id.currency_id",
        store=True,
    )
    user_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
    )
    note = fields.Text()
    times_sent = fields.Integer(readonly=True)
    last_error = fields.Char(readonly=True)

    _name_company_unique = models.Constraint(
        "UNIQUE (name, company_id)",
        "Follow-up Number must be unique per company.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") in (False, "/", "New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("clinic.ar.followup") or "/"
            if vals.get("invoice_id"):
                invoice = self.env["clinic.ar.invoice"].browse(vals["invoice_id"])
                vals.setdefault("company_id", invoice.company_id.id)
        return super().create(vals_list)

    @api.constrains("invoice_id", "level_id", "company_id")
    def _check_scope(self):
        for rec in self:
            if rec.invoice_id.company_id != rec.company_id:
                raise ValidationError(_("Follow-up and AR Invoice company must match."))
            if rec.level_id.company_id != rec.company_id:
                raise ValidationError(_("Follow-up Level and Follow-up company must match."))

    def action_schedule(self):
        for rec in self:
            if rec.invoice_id.state != "posted":
                raise UserError(_("Only posted AR Invoices can be followed up."))
            if rec.invoice_id.amount_residual <= 0:
                raise UserError(_("This AR Invoice is already settled."))
            as_of = fields.Date.context_today(rec)
            rec.write({
                "state": "scheduled",
                "days_overdue_at_schedule": max(
                    (as_of - (rec.invoice_id.due_date or as_of)).days,
                    0,
                ),
                "amount_residual_at_schedule": rec.invoice_id.amount_residual,
            })
        return True

    def action_send(self):
        for rec in self:
            if rec.state not in {"scheduled", "failed"}:
                raise UserError(_("Only scheduled or failed follow-ups can be sent."))
            if rec.invoice_id.amount_residual <= 0:
                rec.state = "done"
                continue
            try:
                if rec.reminder_type == "email":
                    rec._send_email()
                else:
                    rec._schedule_manual_activity()
                rec.write({
                    "state": "sent",
                    "sent_date": fields.Datetime.now(),
                    "times_sent": rec.times_sent + 1,
                    "last_error": False,
                })
                rec._schedule_next_level()
                rec.invoice_id._emit_event("followup.sent")
                rec.message_post(body=_("AR Follow-up sent or queued for manual execution."))
            except Exception as exc:
                rec.write({"state": "failed", "last_error": str(exc)})
                raise
        return True

    def _send_email(self):
        self.ensure_one()
        template = self.template_id
        if template:
            template.send_mail(self.id, force_send=True)
            return True
        if not self.partner_id.email:
            raise UserError(_("Customer email address is missing."))
        body = _(
            "<p>Dear %(name)s,</p>"
            "<p>This is a reminder for AR Invoice <strong>%(invoice)s</strong>. "
            "The current outstanding amount is <strong>%(amount).2f</strong>.</p>",
            name=self.partner_id.display_name,
            invoice=self.invoice_id.name,
            amount=self.invoice_id.amount_residual,
        )
        self.env["mail.mail"].create({
            "subject": _("Payment Reminder - %s") % self.invoice_id.name,
            "body_html": body,
            "email_to": self.partner_id.email,
        }).send()
        return True

    def _schedule_manual_activity(self):
        self.ensure_one()
        activity_type = self.activity_type_id or self.env.ref(
            "mail.mail_activity_data_todo",
            raise_if_not_found=False,
        )
        if not activity_type:
            raise UserError(_("No activity type is available for manual AR follow-up."))
        self.activity_schedule(
            activity_type.id,
            summary=_("AR Follow-up: %s") % self.invoice_id.name,
            note=_(
                "Channel: %(channel)s. Outstanding: %(amount).2f",
                channel=self.reminder_type,
                amount=self.invoice_id.amount_residual,
            ),
            user_id=self.user_id.id,
            date_deadline=fields.Date.context_today(self),
        )
        return True

    def _schedule_next_level(self):
        self.ensure_one()
        next_level = self.env["clinic.ar.followup.level"].search([
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
            ("sequence", ">", self.level_sequence),
        ], order="sequence, id", limit=1)
        if not next_level:
            self.next_scheduled_date = False
            return False
        due = self.invoice_id.due_date or fields.Date.context_today(self)
        scheduled = due + timedelta(days=next_level.delay_days)
        self.next_scheduled_date = scheduled
        self.create({
            "invoice_id": self.invoice_id.id,
            "level_id": next_level.id,
            "scheduled_date": scheduled,
        }).action_schedule()
        return True

    def action_skip(self):
        self.write({"state": "skipped"})
        return True

    def action_done(self):
        self.write({"state": "done"})
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_open_invoice(self):
        self.ensure_one()
        return self.invoice_id._get_records_action(name=_("AR Invoice"))

    @api.model
    def _cron_process_due_followups(self):
        today = fields.Date.context_today(self)
        due = self.search([
            ("state", "=", "scheduled"),
            ("scheduled_date", "<=", today),
        ], order="scheduled_date, id", limit=200)
        for followup in due:
            if followup.invoice_id.amount_residual <= 0:
                followup.state = "done"
                continue
            try:
                followup.action_send()
            except Exception:
                # action_send records the error and rolls back only its own transaction on cron boundary.
                continue
        return True

