# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class ClinicAuditEventLine(models.Model):
    _name = "clinic.audit.event.line"
    _description = "Clinic Audit Event Field Change"
    _order = "event_id desc, id"
    _check_company_auto = True

    event_id = fields.Many2one(
        "clinic.audit.event",
        required=True,
        index=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        related="event_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )
    branch_id = fields.Many2one(
        related="event_id.branch_id",
        store=True,
        index=True,
        readonly=True,
    )
    field_name = fields.Char(required=True, index=True, readonly=True)
    field_label = fields.Char(readonly=True)
    field_type = fields.Char(readonly=True)

    old_value = fields.Text(readonly=True)
    new_value = fields.Text(readonly=True)
    old_digest = fields.Char(readonly=True, index=True)
    new_digest = fields.Char(readonly=True, index=True)
    masked = fields.Boolean(default=False, readonly=True)

    _field_per_event_unique = models.Constraint(
        "UNIQUE(event_id, field_name)",
        "A field may only appear once in a single audit event.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not (
            self.env.su
            or self.env.context.get("clinic_audit_internal")
            or self.env.context.get("clinic_audit_legacy_import")
        ):
            raise AccessError(
                _("Audit event lines can only be created by the internal audit service.")
            )
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Audit event lines are immutable."))

    def unlink(self):
        raise AccessError(_("Audit event lines are immutable."))

    def action_open_event(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Audit Event"),
            "res_model": "clinic.audit.event",
            "res_id": self.event_id.id,
            "view_mode": "form",
        }

