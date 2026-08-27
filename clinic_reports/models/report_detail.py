from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicReportDetail(models.Model):
    """Generic traceable detail snapshot that never owns the source transaction."""

    _name = "clinic.report.detail"
    _description = "Clinic Report Detail Snapshot"
    _order = "run_id, event_date desc, sequence, id"
    _check_company_auto = True

    _run_date_idx = models.Index("(run_id, event_date, source_model, source_res_id)")
    _company_dimension_idx = models.Index("(company_id, patient_id, doctor_id, staff_id)")

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
    event_date = fields.Datetime(index=True)
    reference = fields.Char(index=True)
    label = fields.Char(required=True)
    state_label = fields.Char(index=True)

    source_model = fields.Char(index=True)
    source_res_id = fields.Integer(index=True)
    source_display_name = fields.Char()

    partner_id = fields.Many2one("res.partner", index=True)
    patient_id = fields.Many2one("clinic.patient", index=True)
    doctor_id = fields.Many2one("clinic.doctor", index=True)
    staff_id = fields.Many2one("clinic.staff", index=True)
    treatment_id = fields.Many2one("clinic.treatment", index=True)
    room_id = fields.Many2one("clinic.room", index=True)

    amount = fields.Monetary(currency_field="currency_id")
    quantity = fields.Float()
    duration_minutes = fields.Float()
    rating = fields.Float()
    note = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        # Detail rows are report snapshots.  They may be generated only by the
        # engine under sudo with the internal report_generation marker.
        if not (self.env.su and self.env.context.get("report_generation")):
            raise AccessError(
                _("Report Details can only be created by the reporting engine.")
            )
        return super().create(vals_list)

    def write(self, vals):
        if not (self.env.su and self.env.context.get("report_generation")):
            raise AccessError(
                _("Report Detail snapshots are engine-owned and immutable by RPC.")
            )
        return super().write(vals)

    def unlink(self):
        if not (self.env.su and self.env.context.get("report_generation")):
            raise AccessError(_("Report Details can only be removed by regeneration."))
        return super().unlink()

    def action_open_source(self):
        self.ensure_one()
        if not self.source_model or not self.source_res_id:
            raise UserError(_("This Detail row has no source record."))
        if self.source_model not in self.env.registry:
            raise UserError(
                _("Source model %s is not available.") % self.source_model
            )

        source = self.env[self.source_model].browse(self.source_res_id).exists()
        if not source:
            raise UserError(_("The source record no longer exists."))

        if hasattr(source, "check_access"):
            source.check_access("read")

        return {
            "type": "ir.actions.act_window",
            "name": self.source_display_name or self.label,
            "res_model": self.source_model,
            "view_mode": "form",
            "res_id": source.id,
        }

    def action_open_run(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Report Run"),
            "res_model": "clinic.report.run",
            "view_mode": "form",
            "res_id": self.run_id.id,
        }
