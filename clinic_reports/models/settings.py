from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company reporting defaults without owning transaction/report semantics."""

    _inherit = "res.company"

    clinic_reports_default_window_days = fields.Integer(
        string="Default Report Window (Days)",
        default=30,
    )
    clinic_reports_default_detail_limit = fields.Integer(
        string="Default Report Detail Limit",
        default=500,
    )
    clinic_reports_auto_finalize_scheduled = fields.Boolean(
        string="Auto-Finalize Successful Scheduled Reports",
        default=False,
    )
    clinic_reports_retention_days = fields.Integer(
        string="Report Retention Guidance (Days)",
        default=730,
        help="Governance guidance only. Finalized report snapshots are never auto-deleted by addon 28.",
    )

    @api.constrains(
        "clinic_reports_default_window_days",
        "clinic_reports_default_detail_limit",
        "clinic_reports_retention_days",
    )
    # Company defaults govern generation ergonomics only; they never redefine report KPI semantics.
    def _check_report_settings(self):
        for company in self:
            if company.clinic_reports_default_window_days < 1:
                raise ValidationError(
                    _("Default Report Window must be at least one day.")
                )
            if not 1 <= company.clinic_reports_default_detail_limit <= 10000:
                raise ValidationError(
                    _("Default Report Detail Limit must be between 1 and 10,000 rows.")
                )
            if company.clinic_reports_retention_days < 1:
                raise ValidationError(
                    _("Report Retention Guidance must be at least one day.")
                )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clinic_reports_default_window_days = fields.Integer(
        related="company_id.clinic_reports_default_window_days",
        readonly=False,
    )
    clinic_reports_default_detail_limit = fields.Integer(
        related="company_id.clinic_reports_default_detail_limit",
        readonly=False,
    )
    clinic_reports_auto_finalize_scheduled = fields.Boolean(
        related="company_id.clinic_reports_auto_finalize_scheduled",
        readonly=False,
    )
    clinic_reports_retention_days = fields.Integer(
        related="company_id.clinic_reports_retention_days",
        readonly=False,
    )

