# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicAnalyticsScopeMixin(models.AbstractModel):
    """Company/branch scope contract shared by analytics evidence models."""

    _name = "clinic.analytics.scope.mixin"
    _description = "Clinic Analytics Scope Mixin"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        string="Branch",
        check_company=True,
        index=True,
        domain="[('company_id', '=', company_id)]",
    )

    @api.constrains("company_id", "branch_id")
    def _check_branch_company(self):
        for rec in self:
            if rec.branch_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(
                    _("Analytics Branch must belong to the selected Company.")
                )

    def _ensure_scope_authorized(self):
        """Fail closed for analyst-generated evidence outside assigned branch scope."""
        if self.env.su:
            return True

        is_manager = self.env.user.has_group(
            "clinic_analytics.group_analytics_manager"
        )
        for rec in self:
            if rec.company_id not in self.env.user.company_ids:
                raise AccessError(
                    _("You are not allowed to analyze the selected company.")
                )
            if not rec.branch_id and not is_manager:
                raise AccessError(
                    _(
                        "Company-wide analytics require Analytics Manager access. "
                        "Analysts must select an allowed branch."
                    )
                )
            if (
                rec.branch_id
                and not is_manager
                and rec.branch_id not in self.env.user.allowed_branch_ids
            ):
                raise AccessError(
                    _("The selected Branch is not in your allowed branch scope.")
                )
        return True
