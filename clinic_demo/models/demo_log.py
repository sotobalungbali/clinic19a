




"""Structured, operator-visible log for demo generation and validation."""

from odoo import fields, models


class ClinicDemoLog(models.Model):
    _name = "clinic.demo.log"
    _description = "ClinicOne Demo Log"
    _order = "logged_at desc, id desc"

    run_id = fields.Many2one(
        "clinic.demo.run",
        required=True,
        index=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="run_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )
    checkpoint_id = fields.Many2one(
        "clinic.demo.checkpoint",
        index=True,
        ondelete="set null",
    )
    logged_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    level = fields.Selection(
        [
            ("debug", "Debug"),
            ("info", "Info"),
            ("warning", "Warning"),
            ("error", "Error"),
        ],
        required=True,
        default="info",
        index=True,
    )
    phase_key = fields.Char(index=True)
    generator_key = fields.Char(index=True)
    scenario_key = fields.Char(index=True)
    operation = fields.Char(index=True)
    model_name = fields.Char(index=True)
    demo_key = fields.Char(index=True)
    message = fields.Text(required=True)
    exception_class = fields.Char()
    traceback_excerpt = fields.Text()


    def action_open_run(self):
        """Navigate back to the owning Demo Control Center run."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.run_id.display_name,
            "res_model": "clinic.demo.run",
            "view_mode": "form",
            "res_id": self.run_id.id,
            "target": "current",
        }


    def action_open_log(self):
        """Open this exact service-managed record from an embedded One2many row."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Demo Log",
            "res_model": "clinic.demo.log",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }
























