




"""Machine-readable validation evidence for one Demo Run."""

from odoo import fields, models


class ClinicDemoValidationResult(models.Model):
    _name = "clinic.demo.validation.result"
    _description = "ClinicOne Demo Validation Result"
    _order = "severity desc, id"

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
    check_key = fields.Char(required=True, index=True)
    category = fields.Char(required=True, index=True)
    severity = fields.Selection(
        [
            ("info", "Info"),
            ("warning", "Warning"),
            ("error", "Error"),
            ("critical", "Critical"),
        ],
        required=True,
        default="info",
        index=True,
    )
    state = fields.Selection(
        [
            ("pass", "Pass"),
            ("warning", "Warning"),
            ("fail", "Fail"),
        ],
        required=True,
        index=True,
    )
    generator_key = fields.Char(index=True)
    scenario_key = fields.Char(index=True)
    model_name = fields.Char(index=True)
    demo_key = fields.Char(index=True)
    expected_value = fields.Text()
    actual_value = fields.Text()
    message = fields.Text(required=True)


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


    def action_open_validation(self):
        """Open this exact service-managed record from an embedded One2many row."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Validation Result",
            "res_model": "clinic.demo.validation.result",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }









