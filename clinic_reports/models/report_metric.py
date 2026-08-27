from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicReportMetric(models.Model):
    """Normalized KPI row consumed by Reports today and Dashboard later."""

    _name = "clinic.report.metric"
    _description = "Clinic Report Metric"
    _order = "run_id, sequence, id"
    _check_company_auto = True

    _run_code_unique = models.Constraint(
        "UNIQUE(run_id, code)",
        "Metric Code must be unique within a Report Run.",
    )
    _run_sequence_idx = models.Index("(run_id, sequence, metric_type)")

    run_id = fields.Many2one(
        "clinic.report.run",
        required=True,
        ondelete="cascade",
        index=True,
    )
    definition_id = fields.Many2one(
        related="run_id.definition_id",
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="run_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    branch_id = fields.Many2one(
        related="run_id.branch_id",
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="run_id.currency_id",
        store=True,
        readonly=True,
    )

    sequence = fields.Integer(default=10)
    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    metric_type = fields.Selection(
        [
            ("count", "Count"),
            ("amount", "Amount"),
            ("percentage", "Percentage"),
            ("duration", "Duration (Minutes)"),
            ("score", "Score"),
            ("quantity", "Quantity"),
            ("number", "Number"),
        ],
        default="number",
        required=True,
        index=True,
    )
    value = fields.Float(required=True, default=0.0)
    display_value = fields.Char(
        compute="_compute_display_value",
        store=True,
    )
    note = fields.Char()

    @api.depends("metric_type", "value", "currency_id")
    def _compute_display_value(self):
        for record in self:
            if record.metric_type == "amount":
                symbol = record.currency_id.symbol or ""
                record.display_value = f"{symbol} {record.value:,.2f}".strip()
            elif record.metric_type == "percentage":
                record.display_value = f"{record.value:,.2f}%"
            elif record.metric_type == "duration":
                record.display_value = f"{record.value:,.2f} min"
            elif record.metric_type in ("count", "quantity"):
                record.display_value = f"{record.value:,.0f}"
            else:
                record.display_value = f"{record.value:,.2f}"

    @api.model_create_multi
    def create(self, vals_list):
        # Metrics are deterministic engine output, never user-maintained master data.
        if not (self.env.su and self.env.context.get("report_generation")):
            raise AccessError(
                _("Report Metrics can only be created by the reporting engine.")
            )
        return super().create(vals_list)

    @api.constrains("run_id", "company_id")
    def _check_run_company(self):
        for record in self:
            if record.company_id != record.run_id.company_id:
                raise ValidationError(_("Metric and Report Run company must match."))

    def write(self, vals):
        # Even Draft/Ready output is engine-owned. Finalization adds governance,
        # but it is not the only protection against manual KPI manipulation.
        if not (self.env.su and self.env.context.get("report_generation")):
            raise AccessError(_("Report Metrics are engine-owned and immutable by RPC."))
        return super().write(vals)

    def unlink(self):
        if not (self.env.su and self.env.context.get("report_generation")):
            raise AccessError(_("Report Metrics can only be removed by regeneration."))
        return super().unlink()

    def action_open_run(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Report Run"),
            "res_model": "clinic.report.run",
            "view_mode": "form",
            "res_id": self.run_id.id,
        }
