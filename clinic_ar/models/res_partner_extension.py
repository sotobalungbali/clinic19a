# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    ar_credit_limit = fields.Monetary(string="AR Credit Limit", currency_field="ar_currency_id", company_dependent=True)
    ar_allow_overlimit = fields.Boolean(string="Allow Over-limit", company_dependent=True, default=False)
    ar_on_hold = fields.Boolean(string="Credit On Hold", company_dependent=True, default=False, tracking=True)
    ar_on_hold_reason = fields.Char(string="On Hold Reason", company_dependent=True)
    ar_overdue_guard_days = fields.Integer(string="Block if Overdue > (days)", company_dependent=True, default=0)
    ar_preferred_channel = fields.Selection([
        ("email", "Email"), ("whatsapp", "WhatsApp"), ("sms", "SMS"),
        ("portal", "Portal"), ("call", "Call"), ("letter", "Letter"),
    ], string="Preferred AR Channel", company_dependent=True, default="email")
    ar_statement_opt_out = fields.Boolean(string="Opt-out of Statements", company_dependent=True, default=False)
    ar_last_statement_date = fields.Date(readonly=True)

    ar_currency_id = fields.Many2one("res.currency", compute="_compute_ar_metrics")
    ar_outstanding = fields.Monetary(currency_field="ar_currency_id", compute="_compute_ar_metrics")
    ar_overdue = fields.Monetary(currency_field="ar_currency_id", compute="_compute_ar_metrics")
    ar_has_overdue = fields.Boolean(compute="_compute_ar_metrics")
    ar_open_invoices_count = fields.Integer(compute="_compute_ar_metrics")
    ar_aging_current = fields.Monetary(currency_field="ar_currency_id", compute="_compute_ar_metrics")
    ar_aging_1_30 = fields.Monetary(currency_field="ar_currency_id", compute="_compute_ar_metrics")
    ar_aging_31_60 = fields.Monetary(currency_field="ar_currency_id", compute="_compute_ar_metrics")
    ar_aging_61_90 = fields.Monetary(currency_field="ar_currency_id", compute="_compute_ar_metrics")
    ar_aging_90_plus = fields.Monetary(currency_field="ar_currency_id", compute="_compute_ar_metrics")
    ar_next_followup_date = fields.Date(compute="_compute_ar_metrics")
    ar_payments_count = fields.Integer(compute="_compute_aux_counts")
    ar_followups_count = fields.Integer(compute="_compute_aux_counts")
    ar_statements_count = fields.Integer(compute="_compute_aux_counts")

    @api.depends_context("company")
    def _compute_ar_metrics(self):
        company = self.env.company
        currency = company.currency_id
        Invoice = self.env["clinic.ar.invoice"]
        Followup = self.env["clinic.ar.followup"]
        for partner in self:
            commercial = partner.commercial_partner_id
            invoices = Invoice.search([
                ("partner_id", "=", commercial.id),
                ("company_id", "=", company.id),
                ("state", "=", "posted"),
                ("amount_residual", ">", 0.0),
            ])
            buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0}
            for inv in invoices:
                buckets[inv.aging_bucket or "current"] += inv.amount_residual
            overdue = invoices.filtered("is_overdue")
            next_fu = Followup.search([
                ("partner_id", "=", commercial.id),
                ("company_id", "=", company.id),
                ("state", "=", "scheduled"),
            ], order="scheduled_date, id", limit=1)
            partner.ar_currency_id = currency
            partner.ar_outstanding = currency.round(sum(invoices.mapped("amount_residual")))
            partner.ar_overdue = currency.round(sum(overdue.mapped("amount_residual")))
            partner.ar_has_overdue = bool(overdue)
            partner.ar_open_invoices_count = len(invoices)
            partner.ar_aging_current = currency.round(buckets["current"])
            partner.ar_aging_1_30 = currency.round(buckets["1_30"])
            partner.ar_aging_31_60 = currency.round(buckets["31_60"])
            partner.ar_aging_61_90 = currency.round(buckets["61_90"])
            partner.ar_aging_90_plus = currency.round(buckets["90_plus"])
            partner.ar_next_followup_date = next_fu.scheduled_date if next_fu else False

    @api.depends_context("company")
    def _compute_aux_counts(self):
        company = self.env.company
        Payment = self.env["clinic.ar.payment"]
        Followup = self.env["clinic.ar.followup"]
        Statement = self.env["clinic.ar.statement"]
        for partner in self:
            commercial = partner.commercial_partner_id
            common = [("partner_id", "=", commercial.id), ("company_id", "=", company.id)]
            partner.ar_payments_count = Payment.search_count(common)
            partner.ar_followups_count = Followup.search_count(common)
            partner.ar_statements_count = Statement.search_count(common)

    @api.constrains("ar_credit_limit", "ar_overdue_guard_days")
    def _check_ar_policy_values(self):
        for rec in self:
            if rec.ar_credit_limit < 0:
                raise ValidationError(_("AR Credit Limit cannot be negative."))
            if rec.ar_overdue_guard_days < 0:
                raise ValidationError(_("AR overdue guard days cannot be negative."))

    def ensure_ar_can_post(self, new_amount=0.0):
        for partner in self:
            commercial = partner.commercial_partner_id
            if commercial.ar_on_hold:
                raise UserError(_("Customer %(customer)s is on AR credit hold: %(reason)s", customer=commercial.display_name, reason=commercial.ar_on_hold_reason or _("No reason recorded")))
            if commercial.ar_allow_overlimit:
                continue
            if commercial.ar_credit_limit and commercial.ar_outstanding + new_amount > commercial.ar_credit_limit:
                raise UserError(_("Posting would exceed the customer's AR credit limit."))
            guard = commercial.ar_overdue_guard_days
            if guard:
                very_overdue = self.env["clinic.ar.invoice"].search_count([
                    ("partner_id", "=", commercial.id),
                    ("company_id", "=", self.env.company.id),
                    ("state", "=", "posted"),
                    ("amount_residual", ">", 0.0),
                    ("days_overdue", ">", guard),
                ])
                if very_overdue:
                    raise UserError(_("Customer has AR invoices overdue beyond the configured guard period."))
        return True

    def action_view_ar_invoices(self):
        self.ensure_one()
        return self.env["clinic.ar.invoice"].search([("partner_id", "=", self.commercial_partner_id.id)])._get_records_action(name=_("AR Invoices"))

    def action_view_ar_payments(self):
        self.ensure_one()
        return self.env["clinic.ar.payment"].search([("partner_id", "=", self.commercial_partner_id.id)])._get_records_action(name=_("AR Receipts"))

    def action_view_ar_followups(self):
        self.ensure_one()
        return self.env["clinic.ar.followup"].search([("partner_id", "=", self.commercial_partner_id.id)])._get_records_action(name=_("AR Follow-ups"))

    def action_view_ar_statements(self):
        self.ensure_one()
        return self.env["clinic.ar.statement"].search([("partner_id", "=", self.commercial_partner_id.id)])._get_records_action(name=_("AR Statements"))

    def action_create_ar_statement(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("New AR Statement"),
            "res_model": "clinic.ar.statement", "view_mode": "form", "target": "current",
            "context": {"default_partner_id": self.commercial_partner_id.id, "default_company_id": self.env.company.id},
        }

    def action_toggle_ar_hold(self):
        for rec in self:
            rec.ar_on_hold = not rec.ar_on_hold
            if not rec.ar_on_hold:
                rec.ar_on_hold_reason = False
        return True



