from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ClinicAPAging(models.Model):
    _name = "clinic.ap.aging"
    _description = "Clinic AP Aging Snapshot"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "as_of_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, default=lambda self: _("AP Aging"))
    as_of_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    include_refunds = fields.Boolean(default=True)
    use_partner_grace = fields.Boolean(default=True)
    grace_days_override = fields.Integer(default=0)
    state = fields.Selection(
        [("draft", "Draft"), ("generated", "Generated"), ("archived", "Archived")],
        default="draft",
        tracking=True,
        required=True,
    )
    is_pinned = fields.Boolean(string="Auto Refresh")
    last_refreshed_at = fields.Datetime(readonly=True)
    line_ids = fields.One2many("clinic.ap.aging.line", "aging_id", copy=False)

    vendor_count = fields.Integer(compute="_compute_totals")
    invoice_count = fields.Integer(compute="_compute_totals")
    amount_outstanding = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    amount_overdue = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    amount_current = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    amount_1_30 = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    amount_31_60 = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    amount_61_90 = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    amount_90_plus = fields.Monetary(compute="_compute_totals", currency_field="currency_id")

    @api.depends(
        "line_ids.amount_outstanding",
        "line_ids.amount_overdue",
        "line_ids.amount_current",
        "line_ids.amount_1_30",
        "line_ids.amount_31_60",
        "line_ids.amount_61_90",
        "line_ids.amount_90_plus",
        "line_ids.invoice_count",
    )
    def _compute_totals(self):
        for rec in self:
            rec.vendor_count = len(rec.line_ids)
            rec.invoice_count = sum(rec.line_ids.mapped("invoice_count"))
            rec.amount_outstanding = sum(rec.line_ids.mapped("amount_outstanding"))
            rec.amount_overdue = sum(rec.line_ids.mapped("amount_overdue"))
            rec.amount_current = sum(rec.line_ids.mapped("amount_current"))
            rec.amount_1_30 = sum(rec.line_ids.mapped("amount_1_30"))
            rec.amount_31_60 = sum(rec.line_ids.mapped("amount_31_60"))
            rec.amount_61_90 = sum(rec.line_ids.mapped("amount_61_90"))
            rec.amount_90_plus = sum(rec.line_ids.mapped("amount_90_plus"))

    def action_refresh(self):
        for rec in self:
            rec._refresh_lines()
        return True

    def _refresh_lines(self):
        self.ensure_one()
        self.line_ids.unlink()
        Move = self.env["account.move"]
        domain = [
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ("in_invoice", "in_refund") if self.include_refunds else ("in_invoice",)),
            ("state", "=", "posted"),
            ("invoice_date", "<=", self.as_of_date),
            ("amount_residual", "!=", 0),
        ]
        bills = Move.search(domain)
        grouped = {}
        for bill in bills:
            vendor = bill.commercial_partner_id
            data = grouped.setdefault(vendor.id, {
                "vendor_id": vendor.id,
                "invoice_count": 0,
                "amount_outstanding": 0.0,
                "amount_overdue": 0.0,
                "amount_current": 0.0,
                "amount_1_30": 0.0,
                "amount_31_60": 0.0,
                "amount_61_90": 0.0,
                "amount_90_plus": 0.0,
                "max_days_overdue": 0,
            })
            sign = -1.0 if bill.move_type == "in_refund" else 1.0
            amount = sign * bill.amount_residual
            if bill.currency_id != self.currency_id:
                amount = bill.currency_id._convert(
                    amount,
                    self.currency_id,
                    self.company_id,
                    bill.invoice_date or self.as_of_date,
                )
            due = bill.invoice_date_due or bill.invoice_date or self.as_of_date
            grace = self.grace_days_override
            if self.use_partner_grace:
                grace = vendor.ap_grace_period_days or grace
            effective_due = due + timedelta(days=grace or 0)
            days = max((self.as_of_date - effective_due).days, 0)

            data["invoice_count"] += 1
            data["amount_outstanding"] += amount
            data["max_days_overdue"] = max(data["max_days_overdue"], days)
            if days <= 0:
                data["amount_current"] += amount
            else:
                data["amount_overdue"] += amount
                if days <= 30:
                    data["amount_1_30"] += amount
                elif days <= 60:
                    data["amount_31_60"] += amount
                elif days <= 90:
                    data["amount_61_90"] += amount
                else:
                    data["amount_90_plus"] += amount

        for values in grouped.values():
            values["aging_id"] = self.id
            values["company_id"] = self.company_id.id
            values["as_of_date"] = self.as_of_date
            self.env["clinic.ap.aging.line"].create(values)
        self.write({
            "state": "generated",
            "last_refreshed_at": fields.Datetime.now(),
        })

    def action_archive(self):
        self.write({"state": "archived", "is_pinned": False})
        return True

    def action_view_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("AP Aging Lines"),
            "res_model": "clinic.ap.aging.line",
            "view_mode": "list,form",
            "domain": [("aging_id", "=", self.id)],
            "context": {"create": False},
        }

    @api.model
    def _cron_refresh_pinned(self):
        for aging in self.search([("is_pinned", "=", True), ("state", "!=", "archived")]):
            aging.as_of_date = fields.Date.context_today(aging)
            aging._refresh_lines()
        return True


class ClinicAPAgingLine(models.Model):
    _name = "clinic.ap.aging.line"
    _description = "Clinic AP Aging Line"
    _order = "amount_overdue desc, vendor_id"
    _check_company_auto = True

    _aging_vendor_unique = models.Constraint(
        "UNIQUE(aging_id, vendor_id)",
        "A vendor can appear only once in the same AP aging snapshot.",
    )

    aging_id = fields.Many2one("clinic.ap.aging", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    as_of_date = fields.Date(required=True)
    vendor_id = fields.Many2one("res.partner", required=True, ondelete="restrict", index=True)
    invoice_count = fields.Integer()
    amount_outstanding = fields.Monetary(currency_field="currency_id")
    amount_overdue = fields.Monetary(currency_field="currency_id")
    amount_current = fields.Monetary(currency_field="currency_id")
    amount_1_30 = fields.Monetary(currency_field="currency_id")
    amount_31_60 = fields.Monetary(currency_field="currency_id")
    amount_61_90 = fields.Monetary(currency_field="currency_id")
    amount_90_plus = fields.Monetary(currency_field="currency_id")
    max_days_overdue = fields.Integer()

    def action_view_vendor_bills(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Open Vendor Bills"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("commercial_partner_id", "=", self.vendor_id.commercial_partner_id.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "posted"),
                ("amount_residual", "!=", 0),
            ],
            "context": {"create": False},
        }

    def action_view_vendor(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Vendor"),
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.vendor_id.id,
            "context": {"create": False},
        }

