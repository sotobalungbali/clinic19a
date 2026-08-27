from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


INCIDENT_TYPES = [
    ("clinical_adverse", "Clinical Adverse Event"),
    ("medication", "Medication Safety"),
    ("device", "Device / Equipment"),
    ("fall", "Patient Fall"),
    ("infection", "Infection Prevention"),
    ("privacy", "Privacy / Information Security"),
    ("staff_safety", "Staff Safety"),
    ("facility", "Facility / Environment"),
    ("telemedicine", "Telemedicine"),
    ("service", "Service / Communication"),
    ("operational", "Operational"),
    ("other", "Other"),
]

SEVERITIES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]


class ClinicIncidentCategory(models.Model):
    """Configurable incident taxonomy and default response targets."""

    _name = "clinic.incident.category"
    _description = "Clinic Incident Category"
    _order = "sequence, name, id"
    _check_company_auto = True

    _code_company_unique = models.Constraint(
        "UNIQUE(code, company_id)",
        "Incident Category code must be unique per company.",
    )
    _sla_nonnegative = models.Constraint(
        "CHECK(triage_target_hours >= 0 AND investigation_target_hours >= 0 "
        "AND action_plan_target_hours >= 0)",
        "Incident response targets cannot be negative.",
    )
    _company_active_idx = models.Index("(company_id, active, incident_type)")

    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, index=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        help=(
            "Leave empty for a shared ClinicOne category. Company-specific "
            "categories can be maintained where governance differs."
        ),
    )
    incident_type = fields.Selection(
        INCIDENT_TYPES,
        required=True,
        default="other",
        index=True,
    )
    default_severity = fields.Selection(
        SEVERITIES,
        required=True,
        default="medium",
        index=True,
    )
    requires_investigation = fields.Boolean(default=True)
    requires_capa = fields.Boolean(string="Requires CAPA", default=True)
    requires_regulatory_review = fields.Boolean(
        string="Regulatory Review",
        default=False,
        help=(
            "Requires reportability review. It does not mean an external "
            "regulatory report has been sent."
        ),
    )

    triage_target_hours = fields.Integer(default=24)
    investigation_target_hours = fields.Integer(default=120)
    action_plan_target_hours = fields.Integer(default=168)

    description = fields.Text()
    response_guidance = fields.Text(
        help=(
            "Operational guidance only. It does not replace clinical judgment, "
            "law, regulation, or clinic policy."
        ),
    )

    @api.constrains("code", "company_id")
    def _check_global_code_uniqueness(self):
        """PostgreSQL UNIQUE allows multiple NULL company values; close that gap."""
        for category in self:
            if category.company_id:
                continue
            duplicate = self.search_count([
                ("id", "!=", category.id),
                ("company_id", "=", False),
                ("code", "=", category.code),
            ])
            if duplicate:
                raise ValidationError(
                    _("Shared Incident Category code must be unique.")
                )

    def _check_company_scope(self, company):
        self.ensure_one()
        if self.company_id and self.company_id != company:
            raise ValidationError(
                _("Incident Category belongs to another company.")
            )
        return True
