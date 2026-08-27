# -*- coding: utf-8 -*-

import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicAuditEvent(models.Model):
    """Authoritative immutable compliance evidence owned by addon #38."""

    _name = "clinic.audit.event"
    _description = "Clinic Audit Event"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Event #",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        readonly=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        string="Branch",
        check_company=True,
        index=True,
        readonly=True,
    )
    date_event = fields.Datetime(
        string="Event Time",
        required=True,
        default=fields.Datetime.now,
        index=True,
        readonly=True,
    )
    timestamp = fields.Datetime(
        string="Timestamp (Compatibility)",
        readonly=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        readonly=True,
    )

    ref_model = fields.Char(string="Resource Model", required=True, index=True, readonly=True)
    ref_res_id = fields.Integer(string="Resource ID", required=True, index=True, readonly=True)
    ref_display_name = fields.Char(string="Resource Snapshot", readonly=True)
    model_id = fields.Many2one("ir.model", string="Model Metadata", readonly=True, index=True)

    # Compatibility field vocabulary intentionally accepted by clinic.mixin.audit.
    model = fields.Char(string="Model (Compatibility)", index=True, readonly=True)
    res_model = fields.Char(string="Resource Model (Compatibility)", index=True, readonly=True)
    res_id = fields.Integer(string="Resource ID (Compatibility)", index=True, readonly=True)
    message = fields.Text(string="Message", readonly=True)

    action = fields.Selection(
        [
            ("create", "Create"),
            ("write", "Update"),
            ("unlink", "Delete"),
            ("state", "State Transition"),
            ("access", "Access"),
            ("export", "Export"),
            ("custom", "Custom"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
        index=True,
        readonly=True,
    )
    source = fields.Selection(
        [
            ("ui", "User Interface"),
            ("api", "API"),
            ("webhook", "Webhook"),
            ("import", "Import"),
            ("cron", "Scheduled Job"),
            ("system", "System"),
            ("legacy", "Legacy Import"),
            ("unknown", "Unknown"),
        ],
        required=True,
        default="unknown",
        index=True,
        readonly=True,
    )
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        required=True,
        default="medium",
        index=True,
        readonly=True,
    )
    summary = fields.Char(readonly=True)
    policy_id = fields.Many2one(
        "clinic.audit.policy",
        string="Policy",
        ondelete="set null",
        index=True,
        readonly=True,
    )
    correlation_id = fields.Char(index=True, readonly=True)
    changed_field_names = fields.Char(readonly=True)
    change_digest = fields.Char(readonly=True, index=True)

    legacy_model = fields.Char(readonly=True, index=True)
    legacy_res_id = fields.Integer(readonly=True, index=True)
    legacy_payload_digest = fields.Char(readonly=True, index=True)

    previous_hash = fields.Char(readonly=True, copy=False, index=True)
    event_fingerprint = fields.Char(readonly=True, copy=False, index=True)
    event_hash = fields.Char(readonly=True, copy=False, index=True)
    sealed = fields.Boolean(compute="_compute_sealed")

    line_ids = fields.One2many(
        "clinic.audit.event.line",
        "event_id",
        string="Field Changes",
        readonly=True,
        copy=False,
    )
    line_count = fields.Integer(compute="_compute_counts")
    review_ids = fields.Many2many(
        "clinic.audit.review",
        "clinic_aud_review_event_rel",
        "event_id",
        "review_id",
        string="Compliance Reviews",
        readonly=True,
    )
    review_count = fields.Integer(compute="_compute_counts")

    _event_hash_required = models.Constraint(
        "CHECK(event_hash IS NOT NULL AND event_hash <> '')",
        "Every audit event must be sealed with an event hash.",
    )
    _event_hash_company_unique = models.Constraint(
        "UNIQUE(company_id, event_hash)",
        "Audit event hashes must be unique within a company.",
    )

    @api.depends("event_hash", "event_fingerprint")
    def _compute_sealed(self):
        for rec in self:
            rec.sealed = bool(rec.event_hash and rec.event_fingerprint)

    @api.depends("line_ids", "review_ids")
    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.review_count = len(rec.review_ids)

    @api.model
    def _canonical_json(self, value):
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    @api.model
    def _normalize_action(self, value):
        value = (value or "other").strip().lower()
        return {
            "update": "write",
            "edit": "write",
            "delete": "unlink",
            "remove": "unlink",
            "stage": "state",
        }.get(value, value if value in {
            "create", "write", "unlink", "state", "access", "export", "custom", "other"
        } else "custom")

    @api.model
    def _resolve_target_scope(self, model_name, res_id):
        company = self.env.company
        branch = False
        display = False
        if model_name and res_id and model_name in self.env:
            try:
                target = self.env[model_name].sudo().browse(int(res_id)).exists()
                if target:
                    display = target.display_name
                    service = self.env["clinic.audit.service"]
                    company, branch = service._resolve_scope(target)
            except Exception:
                pass
        return company, branch, display

    @api.model
    def _canonical_payload_from_vals(self, vals):
        return {
            "company_id": vals.get("company_id"),
            "branch_id": vals.get("branch_id"),
            "date_event": str(vals.get("date_event") or ""),
            "user_id": vals.get("user_id"),
            "ref_model": vals.get("ref_model"),
            "ref_res_id": vals.get("ref_res_id"),
            "action": vals.get("action"),
            "source": vals.get("source"),
            "severity": vals.get("severity"),
            "summary": vals.get("summary") or "",
            "policy_id": vals.get("policy_id"),
            "correlation_id": vals.get("correlation_id") or "",
            "changed_field_names": vals.get("changed_field_names") or "",
            "change_digest": vals.get("change_digest") or "",
            "legacy_model": vals.get("legacy_model") or "",
            "legacy_res_id": vals.get("legacy_res_id") or 0,
            "legacy_payload_digest": vals.get("legacy_payload_digest") or "",
        }

    def _canonical_payload_from_record(self):
        self.ensure_one()
        return self._canonical_payload_from_vals({
            "company_id": self.company_id.id,
            "branch_id": self.branch_id.id if self.branch_id else False,
            "date_event": self.date_event,
            "user_id": self.user_id.id,
            "ref_model": self.ref_model,
            "ref_res_id": self.ref_res_id,
            "action": self.action,
            "source": self.source,
            "severity": self.severity,
            "summary": self.summary,
            "policy_id": self.policy_id.id if self.policy_id else False,
            "correlation_id": self.correlation_id,
            "changed_field_names": self.changed_field_names,
            "change_digest": self.change_digest,
            "legacy_model": self.legacy_model,
            "legacy_res_id": self.legacy_res_id,
            "legacy_payload_digest": self.legacy_payload_digest,
        })

    @api.model
    def _prepare_vals(self, incoming):
        vals = dict(incoming)

        ref_model = vals.get("ref_model") or vals.get("model") or vals.get("res_model")
        ref_res_id = int(vals.get("ref_res_id") or vals.get("res_id") or 0)
        if not ref_model:
            ref_model = "unknown.model"

        action = self._normalize_action(vals.get("action"))
        company, branch, display = self._resolve_target_scope(ref_model, ref_res_id)

        vals["ref_model"] = ref_model
        vals["ref_res_id"] = ref_res_id
        vals["model"] = ref_model
        vals["res_model"] = ref_model
        vals["res_id"] = ref_res_id
        vals["action"] = action
        vals["company_id"] = vals.get("company_id") or company.id
        vals["branch_id"] = vals.get("branch_id") or (branch.id if branch else False)
        vals["ref_display_name"] = vals.get("ref_display_name") or display or False
        vals["date_event"] = vals.get("date_event") or vals.get("timestamp") or fields.Datetime.now()
        vals["timestamp"] = vals.get("timestamp") or vals["date_event"]
        vals["user_id"] = vals.get("user_id") or self.env.user.id
        vals["source"] = vals.get("source") or self.env["clinic.audit.service"]._source_context()
        vals["severity"] = vals.get("severity") or "medium"
        incoming_name = vals.get("name")
        vals["summary"] = (
            vals.get("summary")
            or vals.get("message")
            or (
                incoming_name
                if incoming_name not in (False, _("New"))
                else False
            )
            or ("%s %s #%s" % (ref_model, action, ref_res_id))
        )
        # `clinic.mixin.audit` sends a descriptive `name`; preserve it as the
        # summary but always allocate the authoritative event sequence here.
        if not self.env.context.get("clinic_audit_preserve_event_name"):
            vals["name"] = _("New")

        if ref_model in self.env:
            model_meta = self.env["ir.model"].sudo()._get(ref_model)
            vals["model_id"] = model_meta.id if model_meta else False

        # The legacy ClinicOne mixin may pass payload_json. Never persist it
        # verbatim because it can contain PHI/secrets; retain only a digest.
        raw_payload = vals.pop("payload_json", None)
        if raw_payload:
            vals["legacy_payload_digest"] = hashlib.sha256(
                str(raw_payload).encode("utf-8")
            ).hexdigest()

        if not vals.get("change_digest"):
            line_commands = vals.get("line_ids") or []
            digest_source = []
            for command in line_commands:
                if isinstance(command, (list, tuple)) and len(command) >= 3 and command[0] == 0:
                    line_vals = command[2] or {}
                    digest_source.append({
                        "field_name": line_vals.get("field_name"),
                        "old_digest": line_vals.get("old_digest"),
                        "new_digest": line_vals.get("new_digest"),
                    })
            vals["change_digest"] = hashlib.sha256(
                self._canonical_json(digest_source).encode("utf-8")
            ).hexdigest()

        return vals

    @api.model_create_multi
    def create(self, vals_list):
        if not (
            self.env.su
            or self.env.context.get("clinic_audit_internal")
            or self.env.context.get("clinic_audit_legacy_import")
        ):
            raise AccessError(
                _("Audit events can only be created by the internal audit service.")
            )

        records = self.browse()
        sequence = self.env["ir.sequence"].sudo()
        for incoming in vals_list:
            vals = self._prepare_vals(incoming)
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = sequence.next_by_code("clinic.audit.event") or _("New")

            company_id = int(vals["company_id"])
            self.env.cr.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                [f"clinic_audit_event_company:{company_id}"],
            )
            previous = self.sudo().search(
                [("company_id", "=", company_id)],
                order="id desc",
                limit=1,
            )
            previous_hash = previous.event_hash if previous else "GENESIS"

            fingerprint = hashlib.sha256(
                self._canonical_json(
                    self._canonical_payload_from_vals(vals)
                ).encode("utf-8")
            ).hexdigest()
            event_hash = hashlib.sha256(
                f"{previous_hash}|{fingerprint}".encode("utf-8")
            ).hexdigest()

            vals["previous_hash"] = previous_hash
            vals["event_fingerprint"] = fingerprint
            vals["event_hash"] = event_hash
            records |= super().create([vals])
        return records

    def write(self, vals):
        if not self.env.context.get("clinic_audit_internal_maintenance"):
            raise AccessError(_("Audit events are immutable and cannot be edited."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Audit events are immutable and cannot be deleted."))

    def copy(self, default=None):
        raise AccessError(_("Audit events cannot be duplicated."))

    def action_open_record(self):
        self.ensure_one()
        if not self.ref_model or not self.ref_res_id or self.ref_model not in self.env:
            raise UserError(_("This audit event does not reference an available record."))
        target = self.env[self.ref_model].browse(self.ref_res_id).exists()
        if not target:
            raise UserError(_("The referenced record no longer exists."))
        target.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": self.ref_display_name or _("Audited Record"),
            "res_model": self.ref_model,
            "res_id": self.ref_res_id,
            "view_mode": "form",
        }

    def action_open_reviews(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Compliance Reviews"),
            "res_model": "clinic.audit.review",
            "view_mode": "list,form",
            "domain": [("event_ids", "in", self.id)],
            "context": {"default_event_ids": [(6, 0, [self.id])]},
        }

    def action_verify_integrity(self):
        self.ensure_one()
        verification = self.env["clinic.audit.verification"].create({
            "company_id": self.company_id.id,
            "branch_id": self.branch_id.id if self.branch_id else False,
            "single_event_id": self.id,
        })
        verification.action_run()
        return {
            "type": "ir.actions.act_window",
            "name": _("Integrity Verification"),
            "res_model": "clinic.audit.verification",
            "res_id": verification.id,
            "view_mode": "form",
        }

    def _verify_fingerprint(self):
        self.ensure_one()
        expected = hashlib.sha256(
            self._canonical_json(
                self._canonical_payload_from_record()
            ).encode("utf-8")
        ).hexdigest()
        return expected == self.event_fingerprint
