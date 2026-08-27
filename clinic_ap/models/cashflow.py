from calendar import monthrange
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicCashflow(models.Model):
    _name = "clinic.cashflow"
    _description = "Clinic Cashflow Projection"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "as_of_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, default=lambda self: _("Cashflow Projection"))
    as_of_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    horizon_days = fields.Integer(default=90, required=True)
    granularity = fields.Selection(
        [("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")],
        default="weekly",
        required=True,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    include_ap = fields.Boolean(default=True)
    include_ap_refunds = fields.Boolean(default=True)
    include_ar = fields.Boolean(default=True)
    include_ar_refunds = fields.Boolean(default=True)
    starting_balance = fields.Monetary(currency_field="currency_id", default=0.0)
    state = fields.Selection(
        [("draft", "Draft"), ("generated", "Generated"), ("archived", "Archived")],
        default="draft",
        tracking=True,
    )
    is_pinned = fields.Boolean(string="Auto Refresh")
    last_refreshed_at = fields.Datetime(readonly=True)
    bucket_ids = fields.One2many("clinic.cashflow.bucket", "cashflow_id", copy=False)
    adjustment_ids = fields.One2many("clinic.cashflow.adjustment", "cashflow_id", copy=True)

    total_inflow = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    total_outflow = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    total_net = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    ending_balance = fields.Monetary(compute="_compute_totals", currency_field="currency_id")

    @api.depends("bucket_ids.inflow_amount", "bucket_ids.outflow_amount", "bucket_ids.net_amount", "starting_balance")
    def _compute_totals(self):
        for rec in self:
            rec.total_inflow = sum(rec.bucket_ids.mapped("inflow_amount"))
            rec.total_outflow = sum(rec.bucket_ids.mapped("outflow_amount"))
            rec.total_net = rec.total_inflow - rec.total_outflow
            rec.ending_balance = rec.starting_balance + rec.total_net

    @api.constrains("horizon_days")
    def _check_horizon(self):
        for rec in self:
            if rec.horizon_days <= 0 or rec.horizon_days > 730:
                raise ValidationError(_("Cashflow horizon must be between 1 and 730 days."))

    def _frames(self):
        self.ensure_one()
        current = self.as_of_date
        end = self.as_of_date + timedelta(days=self.horizon_days - 1)
        frames = []
        while current <= end:
            if self.granularity == "daily":
                frame_end = current
            elif self.granularity == "weekly":
                frame_end = min(current + timedelta(days=6), end)
            else:
                frame_end = min(
                    current.replace(day=monthrange(current.year, current.month)[1]),
                    end,
                )
            frames.append((current, frame_end))
            current = frame_end + timedelta(days=1)
        return frames

    def action_refresh(self):
        for rec in self:
            rec._refresh()
        return True

    def _refresh(self):
        self.ensure_one()
        self.bucket_ids.unlink()
        buckets = []
        for start, end in self._frames():
            buckets.append(self.env["clinic.cashflow.bucket"].create({
                "cashflow_id": self.id,
                "company_id": self.company_id.id,
                "date_from": start,
                "date_to": end,
                "label": f"{start} — {end}",
            }))

        Move = self.env["account.move"]
        move_types = []
        if self.include_ap:
            move_types.append("in_invoice")
        if self.include_ap_refunds:
            move_types.append("in_refund")
        if self.include_ar:
            move_types.append("out_invoice")
        if self.include_ar_refunds:
            move_types.append("out_refund")

        moves = Move.search([
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", tuple(move_types)),
            ("state", "=", "posted"),
            ("amount_residual", "!=", 0),
            ("invoice_date_due", ">=", self.as_of_date),
            ("invoice_date_due", "<=", self.as_of_date + timedelta(days=self.horizon_days - 1)),
        ])
        for move in moves:
            bucket = next((b for b in buckets if b.date_from <= move.invoice_date_due <= b.date_to), False)
            if not bucket:
                continue
            amount = move.amount_residual
            if move.currency_id != self.currency_id:
                amount = move.currency_id._convert(
                    amount,
                    self.currency_id,
                    self.company_id,
                    move.invoice_date or self.as_of_date,
                )
            direction = "outflow" if move.move_type in ("in_invoice", "out_refund") else "inflow"
            self.env["clinic.cashflow.detail"].create({
                "cashflow_id": self.id,
                "bucket_id": bucket.id,
                "company_id": self.company_id.id,
                "name": move.display_name,
                "source_type": move.move_type,
                "move_id": move.id,
                "partner_id": move.partner_id.id,
                "date_effective": move.invoice_date_due,
                "direction": direction,
                "amount": amount,
            })

        for adj in self.adjustment_ids:
            bucket = next((b for b in buckets if b.date_from <= adj.date <= b.date_to), False)
            if bucket:
                self.env["clinic.cashflow.detail"].create({
                    "cashflow_id": self.id,
                    "bucket_id": bucket.id,
                    "company_id": self.company_id.id,
                    "name": adj.name,
                    "source_type": "adjustment",
                    "adjustment_id": adj.id,
                    "date_effective": adj.date,
                    "direction": adj.direction,
                    "amount": adj.amount,
                })

        running = self.starting_balance
        for bucket in buckets:
            bucket._recompute_amounts()
            running += bucket.net_amount
            bucket.cumulative_balance = running
        self.write({"state": "generated", "last_refreshed_at": fields.Datetime.now()})

    def action_archive(self):
        self.write({"state": "archived", "is_pinned": False})
        return True

    def action_view_buckets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Cashflow Buckets"),
            "res_model": "clinic.cashflow.bucket",
            "view_mode": "list,form",
            "domain": [("cashflow_id", "=", self.id)],
            "context": {"create": False},
        }

    @api.model
    def _cron_refresh_pinned(self):
        for rec in self.search([("is_pinned", "=", True), ("state", "!=", "archived")]):
            rec.as_of_date = fields.Date.context_today(rec)
            rec._refresh()
        return True


class ClinicCashflowBucket(models.Model):
    _name = "clinic.cashflow.bucket"
    _description = "Clinic Cashflow Bucket"
    _order = "date_from, id"
    _check_company_auto = True

    _cashflow_period_unique = models.Constraint(
        "UNIQUE(cashflow_id, date_from, date_to)",
        "Cashflow bucket date range must be unique within the projection.",
    )

    cashflow_id = fields.Many2one("clinic.cashflow", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    label = fields.Char(required=True)
    detail_ids = fields.One2many("clinic.cashflow.detail", "bucket_id", copy=False)
    inflow_amount = fields.Monetary(currency_field="currency_id", readonly=True)
    outflow_amount = fields.Monetary(currency_field="currency_id", readonly=True)
    net_amount = fields.Monetary(currency_field="currency_id", readonly=True)
    cumulative_balance = fields.Monetary(currency_field="currency_id", readonly=True)
    inflow_count = fields.Integer(readonly=True)
    outflow_count = fields.Integer(readonly=True)

    def _recompute_amounts(self):
        for bucket in self:
            inflow = bucket.detail_ids.filtered(lambda d: d.direction == "inflow")
            outflow = bucket.detail_ids.filtered(lambda d: d.direction == "outflow")
            bucket.write({
                "inflow_amount": sum(inflow.mapped("amount")),
                "outflow_amount": sum(outflow.mapped("amount")),
                "net_amount": sum(inflow.mapped("amount")) - sum(outflow.mapped("amount")),
                "inflow_count": len(inflow),
                "outflow_count": len(outflow),
            })

    def action_view_details(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Cashflow Details"),
            "res_model": "clinic.cashflow.detail",
            "view_mode": "list,form",
            "domain": [("bucket_id", "=", self.id)],
            "context": {"create": False},
        }


class ClinicCashflowDetail(models.Model):
    _name = "clinic.cashflow.detail"
    _description = "Clinic Cashflow Detail"
    _order = "date_effective, id"
    _check_company_auto = True

    cashflow_id = fields.Many2one("clinic.cashflow", required=True, ondelete="cascade", index=True)
    bucket_id = fields.Many2one("clinic.cashflow.bucket", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    name = fields.Char(required=True)
    source_type = fields.Selection(
        [
            ("in_invoice", "Vendor Bill"),
            ("in_refund", "Vendor Refund"),
            ("out_invoice", "Customer Invoice"),
            ("out_refund", "Customer Refund"),
            ("adjustment", "Manual Adjustment"),
        ],
        required=True,
    )
    move_id = fields.Many2one("account.move", check_company=True, ondelete="cascade")
    adjustment_id = fields.Many2one("clinic.cashflow.adjustment", ondelete="cascade")
    partner_id = fields.Many2one("res.partner")
    date_effective = fields.Date(required=True)
    direction = fields.Selection([("inflow", "Inflow"), ("outflow", "Outflow")], required=True)
    amount = fields.Monetary(currency_field="currency_id", required=True)

    def action_view_source(self):
        self.ensure_one()
        target = self.move_id or self.adjustment_id
        if not target:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Cashflow Source"),
            "res_model": target._name,
            "view_mode": "form",
            "res_id": target.id,
            "context": {"create": False},
        }


class ClinicCashflowAdjustment(models.Model):
    _name = "clinic.cashflow.adjustment"
    _description = "Clinic Cashflow Adjustment"
    _order = "date, id"
    _check_company_auto = True

    _amount_positive = models.Constraint(
        "CHECK(amount > 0)",
        "Cashflow adjustment amount must be greater than zero.",
    )

    cashflow_id = fields.Many2one("clinic.cashflow", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="cashflow_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    name = fields.Char(required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    direction = fields.Selection([("inflow", "Inflow"), ("outflow", "Outflow")], required=True, default="outflow")
    amount = fields.Monetary(currency_field="currency_id", required=True)
    res_model = fields.Char(string="Source Model")
    res_id = fields.Integer(string="Source ID")
    notes = fields.Char()
