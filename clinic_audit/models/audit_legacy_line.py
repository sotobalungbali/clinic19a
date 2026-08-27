# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicAuditLegacyLogLine(models.Model):
    """Historical field-level evidence retained for database compatibility."""

    _name = "clinic.audit.log.line"
    _description = "Clinic Audit Legacy Log Line"
    _order = "id asc"
    _rec_name = "field_label"

    log_id = fields.Many2one(
        "clinic.audit.log",
        string="Audit Log",
        required=True,
        index=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        related="log_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )
    field_name = fields.Char(required=True, index=True)
    field_label = fields.Char()
    field_type = fields.Char()
    before = fields.Text(string="Before (JSON)")
    after = fields.Text(string="After (JSON)")
    before_short = fields.Char(compute="_compute_helpers")
    after_short = fields.Char(compute="_compute_helpers")
    change_kind = fields.Selection(
        [
            ("created", "Created"),
            ("updated", "Updated"),
            ("deleted", "Deleted"),
            ("other", "Other"),
        ],
        compute="_compute_helpers",
    )
    delta_size = fields.Integer(compute="_compute_helpers")
    json_valid = fields.Boolean(compute="_compute_helpers")

    @api.depends("before", "after")
    def _compute_helpers(self):
        for rec in self:
            before = (rec.before or "").strip()
            after = (rec.after or "").strip()
            rec.before_short = before[:177] + "..." if len(before) > 180 else before
            rec.after_short = after[:177] + "..." if len(after) > 180 else after
            if not before and after:
                rec.change_kind = "created"
            elif before and not after:
                rec.change_kind = "deleted"
            elif before and after and before != after:
                rec.change_kind = "updated"
            else:
                rec.change_kind = "other"
            rec.delta_size = abs(len(after) - len(before))
            rec.json_valid = self._is_json(before) and self._is_json(after)

    @staticmethod
    def _is_json(value):
        if not value:
            return True
        try:
            json.loads(value)
            return True
        except Exception:
            return False

    def to_python(self):
        result = []
        for rec in self:
            def load(value):
                try:
                    return json.loads(value) if value else None
                except Exception:
                    return value
            result.append({
                "id": rec.id,
                "log_id": rec.log_id.id,
                "field_name": rec.field_name,
                "field_label": rec.field_label,
                "field_type": rec.field_type,
                "before": load(rec.before),
                "after": load(rec.after),
                "change_kind": rec.change_kind,
                "delta_size": rec.delta_size,
            })
        return result

    def action_open_log(self):
        self.ensure_one()
        if not self.log_id:
            raise UserError(_("This line is not attached to an audit log."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Legacy Audit Log"),
            "res_model": "clinic.audit.log",
            "res_id": self.log_id.id,
            "view_mode": "form",
        }

    @api.model_create_multi
    def create(self, vals_list):
        if not (
            self.env.su
            or self.env.context.get("clinic_audit_legacy_internal")
            or self.env.context.get("clinic_audit_legacy_import")
        ):
            raise AccessError(_("Legacy audit lines can only be created by trusted internal producers."))
        normalized = []
        for incoming in vals_list:
            vals = dict(incoming)
            for key in ("before", "after"):
                if isinstance(vals.get(key), (dict, list, tuple)):
                    vals[key] = json.dumps(vals[key], ensure_ascii=False, separators=(",", ":"), default=str)
                elif key in vals and vals[key] is not None and not isinstance(vals[key], str):
                    vals[key] = str(vals[key])
            if vals.get("field_name") and not vals.get("field_label"):
                vals["field_label"] = vals["field_name"].replace("_", " ").title()
            normalized.append(vals)
        return super().create(normalized)

    def write(self, vals):
        raise AccessError(_("Legacy audit lines are immutable."))

    def unlink(self):
        raise AccessError(_("Legacy audit lines are immutable."))
