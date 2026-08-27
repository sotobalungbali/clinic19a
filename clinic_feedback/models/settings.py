from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company-specific satisfaction, escalation and automation policy."""

    _inherit = "res.company"

    clinic_feedback_default_survey_id = fields.Many2one(
        "clinic.feedback.survey",
        string="Default Feedback Survey",
        check_company=True,
    )
    clinic_feedback_default_owner_staff_id = fields.Many2one(
        "clinic.staff",
        string="Default Service-Recovery Owner",
        check_company=True,
    )

    clinic_feedback_low_rating_threshold = fields.Integer(
        string="Low Rating Escalation Threshold",
        default=2,
        help="Overall ratings at or below this 1-5 value require service-recovery review.",
    )
    clinic_feedback_nps_escalation_threshold = fields.Integer(
        string="NPS Escalation Threshold",
        default=6,
        help="NPS values at or below this 0-10 value require service-recovery review.",
    )
    clinic_feedback_escalation_sla_hours = fields.Integer(
        string="Service-Recovery SLA (Hours)",
        default=24,
    )

    clinic_feedback_auto_from_encounter = fields.Boolean(
        string="Auto-Create Requests from Completed Encounters",
        default=False,
    )
    clinic_feedback_auto_from_postcare = fields.Boolean(
        string="Auto-Create Requests from Completed Post-Care",
        default=False,
    )
    clinic_feedback_auto_send = fields.Boolean(
        string="Auto-Send Generated Requests",
        default=False,
        help="Uses email only. No SMS/WhatsApp/API delivery is implemented in addon 27.",
    )
    clinic_feedback_source_lookback_days = fields.Integer(
        string="Automation Lookback (Days)",
        default=2,
    )

    @api.constrains(
        "clinic_feedback_default_survey_id",
        "clinic_feedback_default_owner_staff_id",
        "clinic_feedback_low_rating_threshold",
        "clinic_feedback_nps_escalation_threshold",
        "clinic_feedback_escalation_sla_hours",
        "clinic_feedback_source_lookback_days",
    )
    # Company settings keep escalation policy and automation defaults inside the owning company.
    def _check_feedback_settings(self):
        for company in self:
            survey = company.clinic_feedback_default_survey_id
            staff = company.clinic_feedback_default_owner_staff_id

            if survey and survey.company_id != company:
                raise ValidationError(
                    _("Default Feedback Survey must belong to this company.")
                )
            if staff and staff.company_id != company:
                raise ValidationError(
                    _("Default Service-Recovery Owner must belong to this company.")
                )
            if not 1 <= company.clinic_feedback_low_rating_threshold <= 5:
                raise ValidationError(
                    _("Low Rating threshold must be between 1 and 5.")
                )
            if not 0 <= company.clinic_feedback_nps_escalation_threshold <= 10:
                raise ValidationError(
                    _("NPS escalation threshold must be between 0 and 10.")
                )
            if company.clinic_feedback_escalation_sla_hours < 1:
                raise ValidationError(
                    _("Service-Recovery SLA must be at least one hour.")
                )
            if company.clinic_feedback_source_lookback_days < 1:
                raise ValidationError(
                    _("Feedback automation lookback must be at least one day.")
                )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clinic_feedback_default_survey_id = fields.Many2one(
        related="company_id.clinic_feedback_default_survey_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    clinic_feedback_default_owner_staff_id = fields.Many2one(
        related="company_id.clinic_feedback_default_owner_staff_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('is_active', '=', True)]",
    )
    clinic_feedback_low_rating_threshold = fields.Integer(
        related="company_id.clinic_feedback_low_rating_threshold",
        readonly=False,
    )
    clinic_feedback_nps_escalation_threshold = fields.Integer(
        related="company_id.clinic_feedback_nps_escalation_threshold",
        readonly=False,
    )
    clinic_feedback_escalation_sla_hours = fields.Integer(
        related="company_id.clinic_feedback_escalation_sla_hours",
        readonly=False,
    )
    clinic_feedback_auto_from_encounter = fields.Boolean(
        related="company_id.clinic_feedback_auto_from_encounter",
        readonly=False,
    )
    clinic_feedback_auto_from_postcare = fields.Boolean(
        related="company_id.clinic_feedback_auto_from_postcare",
        readonly=False,
    )
    clinic_feedback_auto_send = fields.Boolean(
        related="company_id.clinic_feedback_auto_send",
        readonly=False,
    )
    clinic_feedback_source_lookback_days = fields.Integer(
        related="company_id.clinic_feedback_source_lookback_days",
        readonly=False,
    )
