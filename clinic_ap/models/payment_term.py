from datetime import timedelta
from calendar import monthrange

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    ap_active = fields.Boolean(string="AP Policy Active")
    ap_code = fields.Char(string="AP Policy Code")
    ap_eom_policy = fields.Selection(
        [
            ("none", "None"),
            ("eom", "End of Month"),
            ("eom_next", "End of Next Month"),
            ("dom", "Specific Day of Month"),
        ],
        default="none",
        string="AP Due-Date Policy",
    )
    ap_due_day = fields.Integer(string="Specific Day")
    ap_early_discount_percent = fields.Float(string="AP Early Discount (%)")
    ap_early_discount_days = fields.Integer(string="AP Early Discount Window (Days)")
    ap_grace_days = fields.Integer(string="AP Grace Days")
    ap_late_fee_percent = fields.Float(string="AP Late Fee (%)")
    ap_late_fee_fixed = fields.Monetary(string="AP Fixed Late Fee", currency_field="currency_id")
    ap_min_due_amount = fields.Monetary(string="AP Minimum Due", currency_field="currency_id")

    @api.constrains("ap_due_day", "ap_early_discount_percent", "ap_late_fee_percent")
    def _check_ap_policy(self):
        for term in self:
            if term.ap_eom_policy == "dom" and not (1 <= (term.ap_due_day or 0) <= 31):
                raise ValidationError(_("Specific AP due day must be between 1 and 31."))
            for value in (term.ap_early_discount_percent, term.ap_late_fee_percent):
                if value < 0 or value > 100:
                    raise ValidationError(_("AP percentage values must be between 0 and 100."))

    def _base_ap_schedule(self, value, date_ref, currency):
        self.ensure_one()
        date_ref = fields.Date.to_date(date_ref) or fields.Date.context_today(self)
        company = self.company_id or self.env.company
        company_currency = company.currency_id
        company_value = currency._convert(value, company_currency, company, date_ref)
        terms = self._compute_terms(
            date_ref=date_ref,
            currency=currency,
            company=company,
            tax_amount=0.0,
            tax_amount_currency=0.0,
            untaxed_amount=company_value,
            untaxed_amount_currency=value,
            sign=1,
        )
        schedule = [
            {"due_date": line["date"], "amount": line["foreign_amount"]}
            for line in terms["line_ids"]
        ]
        return schedule

    def ap_compute_schedule(self, value, date_ref=None, currency=None):
        self.ensure_one()
        date_ref = fields.Date.to_date(date_ref) or fields.Date.context_today(self)
        currency = currency or self.currency_id or self.env.company.currency_id
        schedule = self._base_ap_schedule(value, date_ref, currency)

        if self.ap_active and schedule and self.ap_eom_policy != "none":
            last = schedule[-1]
            due = fields.Date.to_date(last["due_date"])
            if self.ap_eom_policy == "eom":
                last["due_date"] = due.replace(day=monthrange(due.year, due.month)[1])
            elif self.ap_eom_policy == "eom_next":
                next_month = (due.replace(day=28) + timedelta(days=4)).replace(day=1)
                last["due_date"] = next_month.replace(day=monthrange(next_month.year, next_month.month)[1])
            elif self.ap_eom_policy == "dom":
                target = due
                day = min(self.ap_due_day, monthrange(target.year, target.month)[1])
                if target.day > day:
                    target = (target.replace(day=28) + timedelta(days=4)).replace(day=1)
                    day = min(self.ap_due_day, monthrange(target.year, target.month)[1])
                last["due_date"] = target.replace(day=day)

        if self.ap_active and self.ap_min_due_amount and len(schedule) > 1:
            normalized = []
            for item in schedule:
                if normalized and item["amount"] < self.ap_min_due_amount:
                    normalized[-1]["amount"] = currency.round(normalized[-1]["amount"] + item["amount"])
                else:
                    normalized.append(dict(item))
            schedule = normalized

        for item in schedule:
            item["amount"] = currency.round(item["amount"])
        return schedule

    def ap_compute_due_date(self, value=1.0, date_ref=None, currency=None):
        schedule = self.ap_compute_schedule(value, date_ref, currency)
        return max((item["due_date"] for item in schedule), default=fields.Date.to_date(date_ref) or fields.Date.context_today(self))

    def ap_get_early_discount_window(self, date_ref=None):
        self.ensure_one()
        if not self.ap_active or not self.ap_early_discount_percent or not self.ap_early_discount_days:
            return False
        start = fields.Date.to_date(date_ref) or fields.Date.context_today(self)
        return {"until": start + timedelta(days=self.ap_early_discount_days), "percent": self.ap_early_discount_percent}

    def ap_compute_early_payment_amount(self, value, date_ref=None, currency=None):
        window = self.ap_get_early_discount_window(date_ref)
        if not window:
            return False
        currency = currency or self.currency_id or self.env.company.currency_id
        discount = currency.round(value * window["percent"] / 100.0)
        return {
            "pay_until": window["until"],
            "discount_amount": discount,
            "net_amount": currency.round(value - discount),
        }

    def ap_compute_late_fee(self, principal_amount, due_date, paid_date=None, currency=None):
        self.ensure_one()
        due = fields.Date.to_date(due_date)
        paid = fields.Date.to_date(paid_date) or fields.Date.context_today(self)
        currency = currency or self.currency_id or self.env.company.currency_id
        if not self.ap_active or not due:
            return {"applies": False, "late_fee": 0.0, "cutoff": due}
        cutoff = due + timedelta(days=self.ap_grace_days or 0)
        if paid <= cutoff:
            return {"applies": False, "late_fee": 0.0, "cutoff": cutoff}
        fee = (principal_amount or 0.0) * (self.ap_late_fee_percent or 0.0) / 100.0
        fee += self.ap_late_fee_fixed or 0.0
        return {"applies": bool(fee), "late_fee": currency.round(fee), "cutoff": cutoff}

