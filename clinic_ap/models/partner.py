from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    _ap_vendor_credit_limit_non_negative = models.Constraint(
        "CHECK(ap_vendor_credit_limit >= 0)",
        "AP vendor exposure limit must be non-negative.",
    )

    is_vendor_ap = fields.Boolean(string="Clinic AP Vendor")
    ap_preferred_currency_id = fields.Many2one("res.currency", string="Preferred AP Currency")
    ap_default_purchase_journal_id = fields.Many2one(
        "account.journal",
        string="Default AP Purchase Journal",
        check_company=True,
        domain="[('type', 'in', ('purchase', 'general'))]",
    )
    ap_preferred_payment_journal_id = fields.Many2one(
        "account.journal",
        string="Preferred AP Payment Journal",
        check_company=True,
        domain="[('type', 'in', ('bank', 'cash', 'credit'))]",
    )
    ap_vendor_credit_limit = fields.Monetary(
        string="AP Vendor Exposure Limit",
        currency_field="ap_company_currency_id",
        default=0.0,
    )
    ap_allow_over_exposure = fields.Boolean(string="Allow Over AP Exposure")
    ap_vendor_on_hold = fields.Boolean(string="AP On Hold", tracking=True)
    ap_vendor_hold_reason = fields.Char(string="AP Hold Reason")
    ap_grace_period_days = fields.Integer(string="AP Grace Days", default=0)
    ap_risk_score = fields.Integer(string="AP Risk Score", default=0)
    ap_risk_grade = fields.Selection(
        [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
        compute="_compute_ap_risk_grade",
        string="AP Risk Grade",
    )

    ap_company_currency_id = fields.Many2one("res.currency", compute="_compute_ap_company_currency")
    ap_payable_outstanding = fields.Monetary(currency_field="ap_company_currency_id", compute="_compute_ap_kpis")
    ap_payable_overdue = fields.Monetary(currency_field="ap_company_currency_id", compute="_compute_ap_kpis")
    ap_open_count = fields.Integer(compute="_compute_ap_kpis")
    ap_vendor_bill_count = fields.Integer(compute="_compute_ap_kpis")

    @api.depends_context("company")
    def _compute_ap_company_currency(self):
        for partner in self:
            partner.ap_company_currency_id = self.env.company.currency_id

    @api.depends("ap_risk_score")
    def _compute_ap_risk_grade(self):
        for partner in self:
            score = partner.ap_risk_score or 0
            partner.ap_risk_grade = "A" if score < 25 else "B" if score < 50 else "C" if score < 75 else "D"

    def _compute_ap_kpis(self):
        Move = self.env["account.move"]
        AP = self.env["clinic.ap"]
        today = fields.Date.context_today(self)
        for partner in self:
            commercial = partner.commercial_partner_id
            bills = Move.search([
                ("company_id", "=", self.env.company.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "posted"),
                ("commercial_partner_id", "=", commercial.id),
                ("amount_residual", "!=", 0),
            ])
            outstanding = 0.0
            overdue = 0.0
            for bill in bills:
                sign = -1.0 if bill.move_type == "in_refund" else 1.0
                amount = sign * bill.amount_residual
                if bill.currency_id != self.env.company.currency_id:
                    amount = bill.currency_id._convert(
                        amount,
                        self.env.company.currency_id,
                        self.env.company,
                        bill.invoice_date or today,
                    )
                outstanding += amount
                due = bill.invoice_date_due
                if due and due < today:
                    overdue += amount
            partner.ap_payable_outstanding = outstanding
            partner.ap_payable_overdue = overdue
            partner.ap_open_count = AP.search_count([
                ("company_id", "=", self.env.company.id),
                ("vendor_id", "child_of", commercial.id),
                ("state", "not in", ("paid", "cancelled")),
            ])
            partner.ap_vendor_bill_count = len(bills)

    @api.constrains("ap_risk_score", "ap_grace_period_days")
    def _check_ap_partner_policy(self):
        for partner in self:
            if not (0 <= (partner.ap_risk_score or 0) <= 100):
                raise ValidationError(_("AP risk score must be between 0 and 100."))
            if partner.ap_grace_period_days < 0:
                raise ValidationError(_("AP grace days cannot be negative."))

    def action_view_clinic_ap(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Accounts Payable"),
            "res_model": "clinic.ap",
            "view_mode": "list,form",
            "domain": [("vendor_id", "child_of", self.commercial_partner_id.id)],
            "context": {"default_vendor_id": self.id},
        }

