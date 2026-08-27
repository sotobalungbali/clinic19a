# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicARStatement(models.Model):
    _name = "clinic.ar.statement"
    _description = "Accounts Receivable Statement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "statement_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(default="/", required=True, readonly=True, copy=False, index=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True, tracking=True)
    currency_id = fields.Many2one("res.currency", required=True, related="company_id.currency_id", store=True, readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer", required=True, check_company=True, index=True, tracking=True)
    patient_id = fields.Many2one("clinic.patient", string="Patient", check_company=True, index=True)
    statement_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    date_from = fields.Date(string="Period From")
    date_to = fields.Date(string="Period To", default=fields.Date.context_today)
    include_paid = fields.Boolean(default=False)
    line_ids = fields.One2many("clinic.ar.statement.line", "statement_id", string="Statement Lines", copy=False)
    opening_balance = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    debit_total = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    credit_total = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    closing_balance = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    overdue_balance = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    state = fields.Selection([
        ("draft", "Draft"),
        ("generated", "Generated"),
        ("sent", "Sent"),
        ("cancelled", "Cancelled"),
    ], default="draft", required=True, index=True, tracking=True)
    sent_at = fields.Datetime(readonly=True, copy=False)
    note = fields.Text()

    _name_company_unique = models.Constraint(
        "UNIQUE (name, company_id)",
        "AR Statement Number must be unique per company.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "/") in (False, "/", "New"):
                vals["name"] = seq.next_by_code("clinic.ar.statement") or "/"
        return super().create(vals_list)

    @api.depends("line_ids.debit", "line_ids.credit", "line_ids.residual", "line_ids.is_overdue")
    def _compute_totals(self):
        for rec in self:
            rec.opening_balance = sum(rec.line_ids.filtered("is_opening").mapped("residual"))
            rec.debit_total = sum(rec.line_ids.mapped("debit"))
            rec.credit_total = sum(rec.line_ids.mapped("credit"))
            rec.closing_balance = sum(rec.line_ids.mapped("residual"))
            rec.overdue_balance = sum(rec.line_ids.filtered("is_overdue").mapped("residual"))

    @api.constrains("date_from", "date_to", "statement_date")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("Statement Period From cannot be after Period To."))
            if rec.date_to and rec.statement_date and rec.date_to > rec.statement_date:
                raise ValidationError(_("Period To cannot be after Statement Date."))

    def write(self, vals):
        if {"partner_id", "company_id", "date_from", "date_to", "include_paid", "line_ids"}.intersection(vals):
            if any(rec.state in {"sent", "cancelled"} for rec in self):
                raise UserError(_("Sent or cancelled statements are immutable."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state != "draft" for rec in self):
            raise UserError(_("Only draft statements can be deleted."))
        return super().unlink()

    def action_generate(self):
        for rec in self:
            if rec.state not in {"draft", "generated"}:
                raise UserError(_("Only draft/generated statements can be regenerated."))
            domain = [
                ("partner_id", "=", rec.partner_id.commercial_partner_id.id),
                ("company_id", "=", rec.company_id.id),
                ("state", "=", "posted"),
            ]
            if rec.date_from:
                domain.append(("invoice_date", ">=", rec.date_from))
            if rec.date_to:
                domain.append(("invoice_date", "<=", rec.date_to))
            if not rec.include_paid:
                domain.append(("amount_residual", ">", 0.0))
            invoices = self.env["clinic.ar.invoice"].search(domain, order="invoice_date, id")
            rec.with_context(clinic_ar_statement_generation=True).line_ids = [Command.clear()] + [
                Command.create({
                    "invoice_id": inv.id,
                    "document_date": inv.invoice_date,
                    "due_date": inv.due_date,
                    "reference": inv.name,
                    "description": inv.billing_id.display_name if inv.billing_id else inv.display_name,
                    "debit": inv.amount_total,
                    "credit": inv.amount_paid,
                    "residual": inv.amount_residual,
                    "is_overdue": inv.is_overdue,
                })
                for inv in invoices
            ]
            rec.state = "generated"
            rec.message_post(body=_("AR statement regenerated from posted AR invoices."))
        return True

    def action_send(self):
        for rec in self:
            if rec.state != "generated":
                raise UserError(_("Generate the statement before marking it sent."))
            if rec.partner_id.ar_statement_opt_out:
                raise UserError(_("This customer has opted out of AR statements."))
            rec.write({"state": "sent", "sent_at": fields.Datetime.now()})
            rec.partner_id.ar_last_statement_date = rec.statement_date
            rec.message_post(body=_("AR statement marked as sent."))
            rec._emit_event("statement.sent")
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state != "cancelled").write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state != "cancelled":
                raise UserError(_("Only cancelled statements can be reset to draft."))
            rec.state = "draft"
        return True

    def action_open_customer(self):
        self.ensure_one()
        return self.partner_id._get_records_action(name=_("Statement Customer"))

    def _emit_event(self, event_type):
        for rec in self:
            self.env["clinic.ar.integration.event"].sudo().enqueue(
                event_type=event_type,
                record=rec,
                company=rec.company_id,
                payload={
                    "statement_id": rec.id,
                    "name": rec.name,
                    "partner_id": rec.partner_id.id,
                    "closing_balance": rec.closing_balance,
                    "overdue_balance": rec.overdue_balance,
                    "state": rec.state,
                },
            )


class ClinicARStatementLine(models.Model):
    _name = "clinic.ar.statement.line"
    _description = "Accounts Receivable Statement Line"
    _order = "document_date, id"
    _check_company_auto = True

    statement_id = fields.Many2one("clinic.ar.statement", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="statement_id.company_id", store=True, index=True)
    currency_id = fields.Many2one("res.currency", related="statement_id.currency_id", store=True)
    partner_id = fields.Many2one("res.partner", related="statement_id.partner_id", store=True, index=True)
    invoice_id = fields.Many2one("clinic.ar.invoice", check_company=True, index=True, ondelete="restrict")
    document_date = fields.Date(index=True)
    due_date = fields.Date(index=True)
    reference = fields.Char(index=True)
    description = fields.Char()
    debit = fields.Monetary(currency_field="currency_id")
    credit = fields.Monetary(currency_field="currency_id")
    residual = fields.Monetary(currency_field="currency_id")
    is_overdue = fields.Boolean(index=True)
    is_opening = fields.Boolean(default=False)

    def _check_managed_mutation(self):
        if self.env.context.get("clinic_ar_statement_generation"):
            return True
        if self.env.is_superuser() or self.env.user.has_group("clinic_ar.group_clinic_ar_manager"):
            return True
        raise UserError(_("Statement lines are generated by the Statement workflow and cannot be edited directly."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_managed_mutation()
        return super().create(vals_list)

    def write(self, vals):
        self._check_managed_mutation()
        return super().write(vals)

    def unlink(self):
        self._check_managed_mutation()
        return super().unlink()

    def action_open_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("This statement line has no AR Invoice."))
        return self.invoice_id._get_records_action(name=_("AR Invoice"))

