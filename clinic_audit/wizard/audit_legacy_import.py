# -*- coding: utf-8 -*-

import hashlib

from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicAuditLegacyImportWizard(models.TransientModel):
    _name = "clinic.audit.legacy.import.wizard"
    _description = "Clinic Audit Legacy Log Import"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Datetime()
    date_to = fields.Datetime()
    batch_limit = fields.Integer(
        default=1000,
        required=True,
    )
    imported_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)
    last_legacy_id = fields.Integer(
        string="Last Legacy ID",
        readonly=True,
        help=(
            "Pagination cursor for the most recently processed legacy audit "
            "record. The next batch starts strictly after this ID."
        ),
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("done", "Done"),
        ],
        default="draft",
        readonly=True,
    )

    def action_import(self):
        self.ensure_one()
        if not self.env.user.has_group(
            "clinic_audit.group_audit_manager"
        ):
            raise AccessError(
                _(
                    "Only Audit Managers may import "
                    "legacy audit logs."
                )
            )
        if (
            self.batch_limit < 1
            or self.batch_limit > 5000
        ):
            raise ValidationError(
                _(
                    "Batch limit must be between 1 and 5000."
                )
            )
        if "clinic.audit.log" not in self.env:
            raise UserError(
                _("Legacy clinic.audit.log is not available.")
            )

        domain = [
            ("company_id", "=", self.company_id.id),
        ]
        if self.date_from:
            domain.append(
                ("date_event", ">=", self.date_from)
            )
        if self.date_to:
            domain.append(
                ("date_event", "<=", self.date_to)
            )
        if self.last_legacy_id:
            domain.append(
                ("id", ">", self.last_legacy_id)
            )

        Legacy = self.env[
            "clinic.audit.log"
        ].sudo()
        Event = self.env[
            "clinic.audit.event"
        ].sudo().with_context(
            clinic_audit_legacy_import=True,
            clinic_audit_skip=True,
        )

        imported = 0
        skipped = 0
        batch_logs = Legacy.search(
            domain,
            order="id asc",
            limit=self.batch_limit,
        )
        last_processed_id = self.last_legacy_id

        for log in batch_logs:
            last_processed_id = log.id
            exists = Event.search_count([
                (
                    "legacy_model",
                    "=",
                    "clinic.audit.log",
                ),
                ("legacy_res_id", "=", log.id),
            ])
            if exists:
                skipped += 1
                continue

            payload_digest = hashlib.sha256(
                (
                    (getattr(log, "changes_json", False) or "")
                    + "|"
                    + (getattr(log, "note", False) or "")
                ).encode("utf-8")
            ).hexdigest()

            raw_category = (
                getattr(log, "category", False)
                or "custom"
            )
            action = {
                "create": "create",
                "update": "write",
                "state": "state",
                "stage": "state",
                "attach": "custom",
                "comment": "custom",
                "custom": "custom",
            }.get(
                raw_category,
                "custom",
            )

            Event.create({
                "company_id": log.company_id.id,
                "date_event": log.date_event,
                "user_id": (
                    log.user_id.id
                    if log.user_id
                    else self.env.user.id
                ),
                "ref_model": (
                    log.ref_model
                    or "unknown.model"
                ),
                "ref_res_id": (
                    log.ref_res_id or 0
                ),
                "ref_display_name": (
                    getattr(
                        log,
                        "ref_display_name",
                        False,
                    )
                    or False
                ),
                "action": action,
                "source": "legacy",
                "severity": "medium",
                "summary": (
                    log.summary
                    or log.name
                    or _(
                        "Imported legacy audit log"
                    )
                ),
                "legacy_model": (
                    "clinic.audit.log"
                ),
                "legacy_res_id": log.id,
                "legacy_payload_digest": (
                    payload_digest
                ),
            })
            imported += 1

        has_more = False
        if last_processed_id:
            next_domain = [
                item
                for item in domain
                if not (
                    isinstance(item, tuple)
                    and item[0] == "id"
                    and item[1] == ">"
                )
            ]
            next_domain.append(
                ("id", ">", last_processed_id)
            )
            has_more = bool(
                Legacy.search(
                    next_domain,
                    order="id asc",
                    limit=1,
                )
            )

        self.write({
            "imported_count": self.imported_count + imported,
            "skipped_count": self.skipped_count + skipped,
            "last_legacy_id": (
                last_processed_id or self.last_legacy_id
            ),
            "state": "draft" if has_more else "done",
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
