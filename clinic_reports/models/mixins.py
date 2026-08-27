from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicReportCompanyMixin(models.AbstractModel):
    """Company/branch boundary shared by report runs and schedules."""

    _name = "clinic.report.company.mixin"
    _description = "Clinic Reports Company and Branch Mixin"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        string="Branch",
        domain="[('company_id', '=', company_id)]",
        index=True,
    )

    @api.constrains("company_id", "branch_id")
    def _check_report_branch_company(self):
        for record in self:
            if record.branch_id and record.branch_id.company_id != record.company_id:
                raise ValidationError(
                    _("Report Branch must belong to the selected company.")
                )
            if (
                record.branch_id
                and "policy_branch_scope_reports" in record.company_id._fields
                and not record.company_id.policy_branch_scope_reports
            ):
                raise ValidationError(
                    _(
                        "Branch-specific Reports are disabled by the current "
                        "Clinic Branch company policy."
                    )
                )

    def _reports_require_group(self, xmlid, message=None):
        if self.env.su:
            return True
        if not self.env.user.has_group(xmlid):
            raise AccessError(
                message or _("You do not have permission for this reporting operation.")
            )
        return True

    # Source domains are built from authoritative company/branch/date fields only.
    def _report_domain(
        self,
        model_name,
        date_field=None,
        date_from=None,
        date_to=None,
        extra=None,
        branch_path=None,
    ):
        """Build a safe source domain using only fields the source actually owns."""
        self.ensure_one()
        Model = self.env[model_name]
        domain = list(extra or [])

        if "company_id" in Model._fields:
            domain.append(("company_id", "=", self.company_id.id))

        if self.branch_id:
            if "branch_id" in Model._fields:
                domain.append(("branch_id", "=", self.branch_id.id))
            elif branch_path:
                domain.append((branch_path, "=", self.branch_id.id))
            else:
                raise ValidationError(
                    _(
                        "Report %s cannot apply Branch %s because source model %s "
                        "has no authoritative branch field/path."
                    )
                    % (
                        self.definition_id.display_name
                        if "definition_id" in self._fields and self.definition_id
                        else self.display_name,
                        self.branch_id.display_name,
                        model_name,
                    )
                )

        if date_field and date_field in Model._fields:
            field = Model._fields[date_field]
            if field.type == "datetime":
                if date_from:
                    start = datetime.combine(
                        fields.Date.to_date(date_from),
                        time.min,
                    )
                    domain.append((date_field, ">=", fields.Datetime.to_string(start)))
                if date_to:
                    end = datetime.combine(
                        fields.Date.to_date(date_to),
                        time.max,
                    )
                    domain.append((date_field, "<=", fields.Datetime.to_string(end)))
            else:
                if date_from:
                    domain.append((date_field, ">=", date_from))
                if date_to:
                    domain.append((date_field, "<=", date_to))

        return domain

    def _source_display_name(self, record):
        if not record:
            return ""
        return (
            record.display_name
            if "display_name" in record._fields
            else str(record.id)
        )
