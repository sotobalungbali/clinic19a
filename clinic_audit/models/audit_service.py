# -*- coding: utf-8 -*-

import hashlib
import json
import logging
import re
import uuid

from odoo import api, models
from odoo.http import request

_logger = logging.getLogger(__name__)


class ClinicAuditService(models.AbstractModel):
    """Single bounded capture service used by registry-level coverage."""

    _name = "clinic.audit.service"
    _description = "Clinic Audit Capture Service"

    _technical_fields = {
        "id",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "__last_update",
        "display_name",
        "message_ids",
        "message_follower_ids",
        "activity_ids",
    }

    _sensitive_name_re = re.compile(
        r"(password|passwd|token|secret|api[_-]?key|authorization|"
        r"credential|signature|private[_-]?key|cvv|pin)",
        re.IGNORECASE,
    )
    _privacy_name_re = re.compile(
        r"(diagnos|soap|symptom|allerg|medical|clinical|assessment|"
        r"history|note|comment|description|image|photo|attachment|"
        r"document|file|binary|raw[_-]?payload)",
        re.IGNORECASE,
    )

    @api.model
    def _enabled(self):
        if (
            self.env.context.get("clinic_audit_skip")
            or self.env.context.get("audit_skip")
            or self.env.context.get("no_audit")
        ):
            return False

        value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("clinic.audit.enabled", "true")
        )
        return str(value).strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    @api.model
    def _fail_closed(self):
        value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("clinic.audit.fail_closed", "true")
        )
        return str(value).strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    @api.model
    def _emit_guarded(self, callable_):
        if not self._enabled():
            return
        try:
            callable_()
        except Exception:
            if self._fail_closed():
                raise
            _logger.exception(
                "Clinic Audit emission failed while fail-closed "
                "mode is disabled."
            )

    @api.model
    def _source_context(self):
        context = self.env.context
        if context.get("clinic_api_request"):
            return "api"
        if context.get("clinic_webhook_request"):
            return "webhook"
        if context.get("import_file"):
            return "import"
        if context.get("cron_id") or context.get("clinic_audit_cron"):
            return "cron"

        try:
            if request and request.httprequest:
                path = request.httprequest.path or ""
                if "/api/clinic/" in path:
                    return "api"
                return "ui"
        except Exception:
            pass

        return "system"

    @api.model
    def _correlation_id(self):
        existing = self.env.context.get("clinic_correlation_id")
        if existing:
            return str(existing)[:128]

        try:
            if request and request.httprequest:
                value = request.httprequest.headers.get("X-Request-ID")
                if value:
                    return value[:128]
        except Exception:
            pass

        return uuid.uuid4().hex

    @api.model
    def _resolve_scope(self, record):
        """Resolve company/branch from code-owned field paths only."""

        company = False
        branch = False

        if "company_id" in record._fields:
            try:
                company = record.company_id
            except Exception:
                company = False

        if "branch_id" in record._fields:
            try:
                branch = record.branch_id
            except Exception:
                branch = False

        # Shallow relation paths cover the historical ClinicOne contracts
        # without accepting relation names from external input.
        if not branch:
            for relation_name in (
                "partner_id",
                "patient_id",
                "booking_id",
                "encounter_id",
                "invoice_id",
                "session_id",
                "contract_id",
            ):
                if relation_name not in record._fields:
                    continue

                try:
                    related = record[relation_name]
                except Exception:
                    continue

                if not related:
                    continue

                if "branch_id" in related._fields:
                    try:
                        branch = related.branch_id
                    except Exception:
                        branch = False

                if not branch and "partner_id" in related._fields:
                    try:
                        partner = related.partner_id
                        if partner and "branch_id" in partner._fields:
                            branch = partner.branch_id
                    except Exception:
                        branch = False

                if branch:
                    break

        if branch and not company:
            company = branch.company_id

        if not company:
            company = self.env.company

        return company, branch

    @api.model
    def _policy_for(
        self,
        model_name,
        company,
        branch,
        operation,
    ):
        Policy = self.env["clinic.audit.policy"].sudo()
        policies = Policy.search(
            [
                ("active", "=", True),
                ("state", "=", "active"),
                ("model_name", "=", model_name),
            ],
            order="sequence, id",
        ).filtered(
            lambda rec: (
                rec.company_id == company
                or (
                    not rec.company_id
                    and (not rec.company_ids or company in rec.company_ids)
                )
            )
        )

        policy = False
        if branch:
            policy = policies.filtered(
                lambda rec: rec.branch_id == branch
            )[:1]
        if not policy:
            policy = policies.filtered(
                lambda rec: not rec.branch_id
            )[:1]

        if not policy:
            return True, False

        field_name = {
            "create": "audit_create",
            "write": "audit_write",
            "unlink": "audit_unlink",
        }[operation]
        return bool(policy[field_name]), policy

    @api.model
    def _eligible_field_names(
        self,
        record,
        requested_names,
        policy=False,
        for_unlink=False,
    ):
        include = (
            set(policy.include_field_ids.mapped("name"))
            if policy
            else set()
        )
        exclude = (
            set(policy.exclude_field_ids.mapped("name"))
            if policy
            else set()
        )

        names = []
        source_names = list(requested_names or [])
        if for_unlink and not source_names:
            source_names = list(record._fields.keys())

        for name in source_names:
            if (
                name in self._technical_fields
                or name in exclude
                or name not in record._fields
            ):
                continue
            if include and name not in include:
                continue

            field = record._fields[name]
            if field.type in {"one2many", "many2many"}:
                continue
            if field.compute and not field.inverse:
                continue
            names.append(name)

        if not for_unlink:
            for name in (
                "name",
                "code",
                "state",
                "status",
                "company_id",
                "branch_id",
                "patient_id",
                "partner_id",
            ):
                if (
                    name not in record._fields
                    or name in names
                    or name in exclude
                    or (include and name not in include)
                ):
                    continue
                field = record._fields[name]
                if (
                    field.type not in {"one2many", "many2many"}
                    and not (field.compute and not field.inverse)
                ):
                    names.append(name)

        return names[:80]

    @api.model
    def _serialize_value(
        self,
        record,
        field_name,
        policy=False,
    ):
        field = record._fields[field_name]
        value = record[field_name]

        policy_masks = (
            set(policy.mask_field_ids.mapped("name"))
            if policy
            else set()
        )
        sensitive = (
            field_name in policy_masks
            or bool(self._sensitive_name_re.search(field_name))
            or bool(self._privacy_name_re.search(field_name))
            or field.type in {"binary", "html"}
        )

        if field.type == "many2one":
            raw = (
                {
                    "id": value.id,
                    "model": field.comodel_name,
                }
                if value
                else False
            )
        elif field.type in {"date", "datetime"}:
            raw = str(value) if value else False
        else:
            raw = value

        canonical = json.dumps(
            raw,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        digest = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

        if sensitive:
            display = json.dumps(
                {
                    "redacted": True,
                    "sha256": digest,
                    "length": len(canonical),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            return display, digest, True

        limit = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "clinic.audit.value_char_limit",
                "2048",
            )
            or 2048
        )
        if len(canonical) > limit:
            display = json.dumps(
                {
                    "truncated": True,
                    "sha256": digest,
                    "length": len(canonical),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            return display, digest, True

        return canonical, digest, False

    @api.model
    def _snapshot(
        self,
        record,
        names,
        policy=False,
    ):
        snapshot = {}
        for name in names:
            try:
                snapshot[name] = self._serialize_value(
                    record,
                    name,
                    policy,
                )
            except Exception:
                unavailable = hashlib.sha256(
                    b"<unavailable>"
                ).hexdigest()
                snapshot[name] = (
                    "<unavailable>",
                    unavailable,
                    True,
                )
        return snapshot

    @api.model
    def _before_write(
        self,
        records,
        vals,
    ):
        if not self._enabled() or not records:
            return {}

        result = {}
        for record in records:
            company, branch = self._resolve_scope(record)
            enabled, policy = self._policy_for(
                record._name,
                company,
                branch,
                "write",
            )
            if not enabled:
                continue

            names = (
                []
                if policy
                and policy.capture_mode == "metadata"
                else self._eligible_field_names(
                    record,
                    vals.keys(),
                    policy,
                )
            )
            result[record.id] = {
                "company_id": company.id,
                "branch_id": branch.id if branch else False,
                "policy_id": policy.id if policy else False,
                "severity": (
                    policy.severity
                    if policy
                    else "medium"
                ),
                "capture_mode": (
                    policy.capture_mode
                    if policy
                    else "changed"
                ),
                "names": names,
                "before": self._snapshot(
                    record,
                    names,
                    policy,
                ),
            }
        return result

    @api.model
    def _after_write(
        self,
        records,
        vals,
        before_map,
    ):
        if not before_map:
            return

        def emit():
            for record in records:
                data = before_map.get(record.id)
                if not data:
                    continue

                policy = (
                    self.env["clinic.audit.policy"]
                    .sudo()
                    .browse(data["policy_id"])
                    if data["policy_id"]
                    else False
                )
                after = self._snapshot(
                    record,
                    data["names"],
                    policy,
                )
                changes = {}
                for name in data["names"]:
                    old = data["before"].get(name)
                    new = after.get(name)
                    if old != new:
                        changes[name] = {
                            "old": old,
                            "new": new,
                        }

                if (
                    changes
                    or data["capture_mode"] == "metadata"
                ):
                    self._create_event_from_changes(
                        record._name,
                        record.id,
                        record.display_name,
                        "write",
                        data["company_id"],
                        data["branch_id"],
                        data["policy_id"],
                        data["severity"],
                        changes,
                    )

        self._emit_guarded(emit)

    @api.model
    def _after_create(
        self,
        records,
        vals_list,
    ):
        if not self._enabled() or not records:
            return

        def emit():
            for record, vals in zip(records, vals_list):
                company, branch = self._resolve_scope(record)
                enabled, policy = self._policy_for(
                    record._name,
                    company,
                    branch,
                    "create",
                )
                if not enabled:
                    continue

                names = (
                    []
                    if policy
                    and policy.capture_mode == "metadata"
                    else self._eligible_field_names(
                        record,
                        vals.keys(),
                        policy,
                    )
                )
                after = self._snapshot(
                    record,
                    names,
                    policy,
                )
                changes = {
                    name: {
                        "old": False,
                        "new": value,
                    }
                    for name, value in after.items()
                }

                self._create_event_from_changes(
                    record._name,
                    record.id,
                    record.display_name,
                    "create",
                    company.id,
                    branch.id if branch else False,
                    policy.id if policy else False,
                    policy.severity if policy else "medium",
                    changes,
                )

        self._emit_guarded(emit)

    @api.model
    def _before_unlink(self, records):
        if not self._enabled() or not records:
            return []

        snapshots = []
        for record in records:
            company, branch = self._resolve_scope(record)
            enabled, policy = self._policy_for(
                record._name,
                company,
                branch,
                "unlink",
            )
            if not enabled:
                continue

            names = (
                []
                if policy
                and policy.capture_mode == "metadata"
                else self._eligible_field_names(
                    record,
                    [],
                    policy,
                    for_unlink=True,
                )
            )
            snapshots.append({
                "model": record._name,
                "res_id": record.id,
                "display_name": record.display_name,
                "company_id": company.id,
                "branch_id": (
                    branch.id if branch else False
                ),
                "policy_id": (
                    policy.id if policy else False
                ),
                "severity": (
                    policy.severity
                    if policy
                    else "high"
                ),
                "auto_review": bool(
                    policy
                    and policy.auto_review_unlink
                ),
                "before": self._snapshot(
                    record,
                    names,
                    policy,
                ),
            })

        return snapshots

    @api.model
    def _after_unlink(self, snapshots):
        if not snapshots:
            return

        def emit():
            for data in snapshots:
                changes = {
                    name: {
                        "old": value,
                        "new": False,
                    }
                    for name, value
                    in data["before"].items()
                }
                event = self._create_event_from_changes(
                    data["model"],
                    data["res_id"],
                    data["display_name"],
                    "unlink",
                    data["company_id"],
                    data["branch_id"],
                    data["policy_id"],
                    data["severity"],
                    changes,
                )
                if data["auto_review"]:
                    self._create_review_for_delete(event)

        self._emit_guarded(emit)

    @api.model
    def _create_review_for_delete(self, event):
        self.env["clinic.audit.review"].sudo().with_context(
            clinic_audit_skip=True
        ).create({
            "company_id": event.company_id.id,
            "branch_id": (
                event.branch_id.id
                if event.branch_id
                else False
            ),
            "severity": event.severity,
            "priority": (
                "3"
                if event.severity == "critical"
                else "1"
            ),
            "event_ids": [(6, 0, [event.id])],
            "finding": (
                "Automatic compliance review opened "
                "for an audited delete operation."
            ),
        })

    @api.model
    def _create_event_from_changes(
        self,
        model_name,
        res_id,
        display_name,
        action,
        company_id,
        branch_id,
        policy_id,
        severity,
        changes,
    ):
        lines = []
        compact = {}

        for field_name, change in changes.items():
            old_tuple = (
                change["old"]
                if change["old"]
                else (False, False, False)
            )
            new_tuple = (
                change["new"]
                if change["new"]
                else (False, False, False)
            )
            (
                old_value,
                old_digest,
                old_masked,
            ) = old_tuple
            (
                new_value,
                new_digest,
                new_masked,
            ) = new_tuple

            field = (
                self.env[model_name]._fields.get(field_name)
                if model_name in self.env
                else False
            )
            compact[field_name] = {
                "old_digest": old_digest,
                "new_digest": new_digest,
                "masked": bool(
                    old_masked or new_masked
                ),
            }
            lines.append((
                0,
                0,
                {
                    "field_name": field_name,
                    "field_label": (
                        field.string if field else field_name
                    ),
                    "field_type": (
                        field.type if field else False
                    ),
                    "old_value": old_value or False,
                    "new_value": new_value or False,
                    "old_digest": old_digest or False,
                    "new_digest": new_digest or False,
                    "masked": bool(
                        old_masked or new_masked
                    ),
                },
            ))

        change_digest = hashlib.sha256(
            json.dumps(
                compact,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        return (
            self.env["clinic.audit.event"]
            .sudo()
            .with_context(
                clinic_audit_internal=True,
                clinic_audit_skip=True,
            )
            .create({
                "company_id": company_id,
                "branch_id": branch_id or False,
                "ref_model": model_name,
                "ref_res_id": res_id,
                "ref_display_name": (
                    display_name or model_name
                ),
                "action": action,
                "summary": (
                    f"{display_name or model_name}: "
                    f"{action}"
                ),
                "severity": severity,
                "policy_id": policy_id or False,
                "source": self._source_context(),
                "correlation_id": (
                    self._correlation_id()
                ),
                "changed_field_names": ", ".join(
                    sorted(changes)
                ),
                "change_digest": change_digest,
                "line_ids": lines,
            })
        )
