from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company-scoped post-care automation and clinical attention thresholds."""

    _inherit = "res.company"

    clinic_postcare_default_protocol_id = fields.Many2one(
        "clinic.postcare.protocol",
        string="Default Post-Care Protocol",
        check_company=True,
    )
    clinic_postcare_default_assignee_id = fields.Many2one(
        "clinic.staff",
        string="Default Post-Care Staff",
        check_company=True,
    )
    clinic_postcare_auto_create_from_encounter = fields.Boolean(
        string="Auto-Create Post-Care from Completed Encounters",
        default=False,
    )
    clinic_postcare_auto_create_lookback_days = fields.Integer(
        string="Auto-Creation Lookback (Days)",
        default=2,
    )
    clinic_postcare_pain_red_flag_threshold = fields.Integer(
        string="Pain Attention Threshold (0-10)",
        default=8,
        help="Operational attention threshold only; it does not constitute diagnosis.",
    )

    @api.constrains(
        "clinic_postcare_default_protocol_id",
        "clinic_postcare_default_assignee_id",
        "clinic_postcare_auto_create_lookback_days",
        "clinic_postcare_pain_red_flag_threshold",
    )
    # Company-level constraints keep automation defaults inside the active company boundary.
    def _check_postcare_settings(self):
        for company in self:
            protocol = company.clinic_postcare_default_protocol_id
            staff = company.clinic_postcare_default_assignee_id
            if protocol and protocol.company_id != company:
                raise ValidationError(_("Default Post-Care Protocol must belong to this company."))
            if staff and staff.company_id != company:
                raise ValidationError(_("Default Post-Care Staff must belong to this company."))
            if company.clinic_postcare_auto_create_lookback_days < 1:
                raise ValidationError(_("Post-Care auto-creation lookback must be at least one day."))
            if not 0 <= company.clinic_postcare_pain_red_flag_threshold <= 10:
                raise ValidationError(_("Pain attention threshold must be between 0 and 10."))


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clinic_postcare_default_protocol_id = fields.Many2one(
        related="company_id.clinic_postcare_default_protocol_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    clinic_postcare_default_assignee_id = fields.Many2one(
        related="company_id.clinic_postcare_default_assignee_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('is_active', '=', True)]",
    )
    clinic_postcare_auto_create_from_encounter = fields.Boolean(
        related="company_id.clinic_postcare_auto_create_from_encounter",
        readonly=False,
    )
    clinic_postcare_auto_create_lookback_days = fields.Integer(
        related="company_id.clinic_postcare_auto_create_lookback_days",
        readonly=False,
    )
    clinic_postcare_pain_red_flag_threshold = fields.Integer(
        related="company_id.clinic_postcare_pain_red_flag_threshold",
        readonly=False,
    )
