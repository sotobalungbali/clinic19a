from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicIncidentQualityBridge(models.Model):
    """Add Quality provenance to addon-34 Incident without moving ownership."""

    _inherit = "clinic.incident"

    _quality_line_uniq = models.Constraint(
        "UNIQUE(quality_check_line_id)",
        "A Quality Control failure can be linked to only one Incident case.",
    )

    quality_check_id = fields.Many2one(
        "clinic.quality.check",
        string="Source Quality Check",
        ondelete="restrict",
        index=True,
    )
    quality_check_line_id = fields.Many2one(
        "clinic.quality.check.line",
        string="Source Quality Control",
        ondelete="restrict",
        index=True,
    )
    quality_sop_id = fields.Many2one(
        related="quality_check_id.template_id.sop_id",
        string="Governing Quality SOP",
        store=True,
        readonly=True,
        index=True,
    )

    @api.constrains(
        "quality_check_id",
        "quality_check_line_id",
        "company_id",
        "branch_id",
    )
    def _check_quality_incident_source(self):
        for incident in self:
            check = incident.quality_check_id
            line = incident.quality_check_line_id

            if line and not check:
                raise ValidationError(
                    _("Quality Control source requires a Quality Check source.")
                )
            if line and line.check_id != check:
                raise ValidationError(
                    _("Quality Control does not belong to the linked Quality Check.")
                )
            if check and check.company_id != incident.company_id:
                raise ValidationError(
                    _("Quality Check and Incident companies must match.")
                )
            if (
                check
                and check.branch_id
                and incident.branch_id
                and check.branch_id != incident.branch_id
            ):
                raise ValidationError(
                    _("Quality Check and Incident Branches must match.")
                )

    def action_open_quality_check(self):
        self.ensure_one()
        if not self.quality_check_id:
            raise UserError(_("This Incident has no source Quality Check."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Source Quality Check"),
            "res_model": "clinic.quality.check",
            "view_mode": "form",
            "res_id": self.quality_check_id.id,
        }

    def action_open_quality_control(self):
        self.ensure_one()
        if not self.quality_check_line_id:
            raise UserError(_("This Incident has no source Quality Control."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Source Quality Control"),
            "res_model": "clinic.quality.check.line",
            "view_mode": "form",
            "res_id": self.quality_check_line_id.id,
        }
