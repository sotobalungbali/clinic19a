




"""Stable demo-key registry without modifying every ClinicOne business model."""

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..services.constants import (
    REFERENCE_OWNERSHIP_SELECTION,
    REFERENCE_STATUS_SELECTION,
    RESET_POLICY_SELECTION,
)

_DEMO_KEY_RE = re.compile(r"^DEMO-[A-Z0-9][A-Z0-9._-]*$")


class ClinicDemoReference(models.Model):
    _name = "clinic.demo.reference"
    _description = "ClinicOne Demo Reference"
    _rec_name = "demo_key"
    _order = "id desc"

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
    demo_key = fields.Char(required=True, index=True)
    generator_key = fields.Char(required=True, index=True)
    scenario_key = fields.Char(index=True)

    model_name = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    display_name = fields.Char()
    business_reference = fields.Char(index=True)

    ownership_kind = fields.Selection(
        REFERENCE_OWNERSHIP_SELECTION,
        required=True,
        default="created",
        index=True,
    )
    reset_sequence = fields.Integer(
        default=100,
        index=True,
        help="Higher values reset first. Domain generators may override this to preserve child-first ordering.",
    )
    reset_policy_snapshot = fields.Selection(
        RESET_POLICY_SELECTION,
        required=True,
        index=True,
    )
    record_status = fields.Selection(
        REFERENCE_STATUS_SELECTION,
        required=True,
        default="bound",
        index=True,
    )
    last_checked_at = fields.Datetime()
    last_reset_at = fields.Datetime()
    note = fields.Text()

    _run_demo_key_unique = models.Constraint(
        "UNIQUE(run_id, demo_key)",
        "A demo key must be unique within one Demo Run.",
    )
    _positive_res_id = models.Constraint(
        "CHECK(res_id > 0)",
        "A Demo Reference must point to a positive database record ID.",
    )

    @api.constrains("demo_key")
    def _check_demo_key_format(self):
        for reference in self:
            if not _DEMO_KEY_RE.match(reference.demo_key or ""):
                raise ValidationError(
                    "Demo keys must start with DEMO- and contain only uppercase letters, "
                    "numbers, dots, underscores, or hyphens."
                )

    def get_record(self):
        """Resolve the pointed record without bypassing normal record access."""
        self.ensure_one()
        try:
            model = self.env[self.model_name]
        except KeyError:
            return False
        return model.browse(self.res_id).exists()

    def action_refresh_record_status(self):
        """Refresh registry existence status without altering the business record."""
        from ..services.reference_service import DemoReferenceService

        service = DemoReferenceService(self.env)
        for reference in self:
            record = service._existing_record(reference)
            reference.write({
                "record_status": "bound" if record else "missing",
                "last_checked_at": fields.Datetime.now(),
            })
        return True

    def action_open_record(self):
        """Open the exact Golden Journey record; never use a fuzzy business search."""
        self.ensure_one()
        record = self.get_record()
        if not record:
            raise ValidationError(
                f"The record for demo key {self.demo_key} no longer exists."
            )
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name or self.demo_key,
            "res_model": self.model_name,
            "view_mode": "form",
            "res_id": self.res_id,
            "target": "current",
        }









