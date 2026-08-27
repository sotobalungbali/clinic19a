# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - Audit Mixin (Abstract)

Abstract mixin:
- Shadow meta fields (created_by/on, last_modified_by/on) WITHOUT 'related',
  populated in create()/write() so it works on abstract models.
- Central _audit_log() with soft fallback to chatter if clinic.audit.log is absent.
- Hooks capture diffs and state transitions.
"""

import json
from datetime import date, datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html_escape


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def _get_model(env, model_name):
    try:
        return env[model_name]
    except Exception:
        return None


def _has_field(record_or_model, field_name):
    return hasattr(record_or_model, "_fields") and field_name in record_or_model._fields


def _jsonify(value):
    """Serialize values for audit payloads."""
    try:
        from odoo.models import BaseModel  # type: ignore
        if isinstance(value, BaseModel):
            if len(value) <= 1:
                rec = value[:1]
                return rec and {"id": rec.id, "name": rec.display_name} or None
            return [{"id": r.id, "name": r.display_name} for r in value]
    except Exception:
        pass

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, (bool, int, float, str)) or value is None:
        return value

    return str(value)


def _safe_dumps(obj):
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps(str(obj), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Abstract Mixin
# ---------------------------------------------------------------------------
class ClinicEmarAuditMixin(models.AbstractModel):
    _name = "clinic.emar.mixin.audit"
    _description = "ClinicOne eMAR Audit Mixin (Abstract)"
    _abstract = True

    # Shadow meta (bukan related, supaya aman di abstract model)
    created_by_id = fields.Many2one(
        "res.users",
        string="Created By",
        readonly=True,
        index=True,
        copy=False,
        help="Shadow of create_uid for search/groupby convenience.",
    )
    created_on = fields.Datetime(
        string="Created On",
        readonly=True,
        index=True,
        copy=False,
        help="Shadow of create_date.",
    )
    last_modified_by_id = fields.Many2one(
        "res.users",
        string="Last Modified By",
        readonly=True,
        index=True,
        copy=False,
        help="Shadow of write_uid.",
    )
    last_modified_on = fields.Datetime(
        string="Last Modified On",
        readonly=True,
        index=True,
        copy=False,
        help="Shadow of write_date.",
    )

    audit_note = fields.Text(
        string="Audit Note",
        help="Internal, free-form notes for compliance, investigation, or context.",
    )
    audit_log_count = fields.Integer(
        string="Audit Log Count",
        compute="_compute_audit_log_count",
        help="Number of audit log entries associated with this record.",
    )

    # ----------------------------- Compute -----------------------------------
    def _compute_audit_log_count(self):
        Log = _get_model(self.env, "clinic.audit.log")
        for rec in self:
            if Log and _has_field(Log, "model") and _has_field(Log, "res_id"):
                rec.audit_log_count = Log.search_count([("model", "=", rec._name), ("res_id", "=", rec.id)])
            else:
                rec.audit_log_count = 0

    # ----------------------------- Helpers -----------------------------------
    def _audit_log(self, action, message=None, severity="info", changes=None, extra=None):
        """
        Create audit trail entries per record.

        action: "create" | "update" | "delete" | "state_change" | ...
        """
        Log = _get_model(self.env, "clinic.audit.log")
        actor = self.env.user

        if Log and _has_field(Log, "model") and _has_field(Log, "res_id"):
            def _filter_vals(vals):
                return {k: v for k, v in vals.items() if _has_field(Log, k)}

            for rec in self:
                payload = {
                    "action": action,
                    "message": message or "",
                    "changes": changes if isinstance(changes, (list, dict)) else None,
                    "extra": extra or {},
                }
                vals = {
                    "name": message or (action.capitalize()),
                    "model": rec._name,
                    "res_id": rec.id,
                    "actor_id": actor.id,
                    "severity": severity,
                    "data_json": _safe_dumps(payload),
                }
                if _has_field(rec, "company_id") and rec.company_id:
                    vals["company_id"] = rec.company_id.id
                try:
                    Log.create(_filter_vals(vals))
                except Exception:
                    if hasattr(rec, "message_post"):
                        body = "<b>[AUDIT]</b> %s<br/>%s" % (action, message or "")
                        if changes:
                            body += "<br/><small>%s</small>" % html_escape(_safe_dumps(changes))
                        rec.message_post(body=body)
            return True

        # Fallback ke chatter
        for rec in self:
            if hasattr(rec, "message_post"):
                body = "<b>[AUDIT]</b> %s<br/>%s" % (action, message or "")
                if changes:
                    body += "<br/><small>%s</small>" % html_escape(_safe_dumps(changes))
                try:
                    rec.message_post(body=body)
                except Exception:
                    pass
        return True

    def _collect_diffs_for_write(self, vals):
        """Hitung diffs sebelum write."""
        diffs = {}
        tracked_fields = [f for f in vals.keys() if f in self._fields]
        if not tracked_fields:
            return {rec.id: [] for rec in self}

        for rec in self:
            changes = []
            for field in tracked_fields:
                try:
                    old = rec[field]
                except Exception:
                    old = None
                if self._fields[field].type in ("one2many", "many2many"):
                    continue
                changes.append({
                    "field": field,
                    "old": _jsonify(old),
                    "new": _jsonify(vals.get(field)),
                })
            diffs[rec.id] = changes
        return diffs

    # ------------------------------ Actions ----------------------------------
    def action_view_audit_log(self):
        """Open related audit logs if 'clinic.audit.log' is available."""
        self.ensure_one()
        Log = _get_model(self.env, "clinic.audit.log")
        if not Log:
            raise UserError(_("Audit log model is not installed."))
        return {
            "name": _("Audit Logs"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.audit.log",
            "view_mode": "list,form",
            "domain": [("model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"search_default_group_by_severity": 1},
        }

    # ------------------------------ Hooks ------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        # Set shadow meta in the SAME write (no second write, no loop)
        now = fields.Datetime.now()
        uid = self.env.uid
        for vals in vals_list:
            vals.setdefault("created_by_id", uid)
            vals.setdefault("created_on", now)
            vals.setdefault("last_modified_by_id", uid)
            vals.setdefault("last_modified_on", now)

        records = super().create(vals_list)

        # Audit log (create)
        try:
            for rec, vals in zip(records, vals_list):
                clean_vals = {
                    k: _jsonify(v)
                    for k, v in vals.items()
                    if k in rec._fields and rec._fields[k].type not in ("binary", "one2many", "many2many")
                }
                rec._audit_log(
                    action="create",
                    message=_("Record created."),
                    severity="info",
                    changes=[{"field": k, "old": None, "new": v} for k, v in clean_vals.items()],
                )
        except Exception:
            pass
        return records

    def write(self, vals):
        # Inject shadow last_modified_* into the SAME write
        vals = dict(vals or {})
        vals["last_modified_by_id"] = self.env.uid
        vals["last_modified_on"] = fields.Datetime.now()

        # Collect diffs BEFORE write
        try:
            diffs = self._collect_diffs_for_write(vals)
        except Exception:
            diffs = {rec.id: [] for rec in self}

        # State snapshot for state_change audit
        old_states = {}
        if "state" in vals and "state" in self._fields:
            for rec in self:
                try:
                    old_states[rec.id] = rec.state
                except Exception:
                    old_states[rec.id] = None

        res = super().write(vals)

        # Audit log (update & state_change)
        try:
            for rec in self:
                rec_diffs = diffs.get(rec.id, [])
                for ch in rec_diffs:
                    field = ch["field"]
                    try:
                        ch["new"] = _jsonify(rec[field])
                    except Exception:
                        pass

                if rec_diffs:
                    rec._audit_log(
                        action="update",
                        message=_("Record updated."),
                        severity="info",
                        changes=rec_diffs,
                    )
                else:
                    rec._audit_log(
                        action="update",
                        message=_("Record updated."),
                        severity="info",
                    )

                if "state" in vals and "state" in rec._fields:
                    try:
                        old = old_states.get(rec.id)
                        new = rec.state
                        if old != new:
                            rec._audit_log(
                                action="state_change",
                                message=_("State changed from '%s' to '%s'.") % (old, new),
                                severity="info",
                                changes=[{"field": "state", "old": _jsonify(old), "new": _jsonify(new)}],
                            )
                    except Exception:
                        pass
        except Exception:
            pass

        return res

    def unlink(self):
        snapshot = []
        try:
            for rec in self:
                snapshot.append({"id": rec.id, "name": rec.display_name})
        except Exception:
            snapshot = [{"id": r.id} for r in self]

        try:
            for rec in self:
                rec._audit_log(
                    action="delete",
                    message=_("Record deleted."),
                    severity="warning",
                    extra={"records": snapshot},
                )
        except Exception:
            pass

        return super().unlink()
