# -*- coding: utf-8 -*-

import base64
import json

from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicAuditEvidenceExportWizard(models.TransientModel):
    _name = "clinic.audit.evidence.export.wizard"
    _description = "Clinic Audit Evidence Export"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        check_company=True,
    )
    date_from = fields.Datetime()
    date_to = fields.Datetime()
    model_name = fields.Char(string="Model")
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
    )
    include_lines = fields.Boolean(default=True)
    export_file = fields.Binary(readonly=True)
    export_filename = fields.Char(readonly=True)
    record_count = fields.Integer(readonly=True)

    def action_generate(self):
        self.ensure_one()
        if not self.env.user.has_group(
            "clinic_audit.group_audit_user"
        ):
            raise AccessError(
                _("You are not allowed to export audit evidence.")
            )

        domain = [
            ("company_id", "=", self.company_id.id),
        ]
        if self.branch_id:
            domain.append(
                ("branch_id", "=", self.branch_id.id)
            )
        if self.date_from:
            domain.append(
                ("date_event", ">=", self.date_from)
            )
        if self.date_to:
            domain.append(
                ("date_event", "<=", self.date_to)
            )
        if self.model_name:
            domain.append(
                (
                    "ref_model",
                    "=",
                    self.model_name.strip(),
                )
            )
        if self.action:
            domain.append(
                ("action", "=", self.action)
            )

        events = self.env[
            "clinic.audit.event"
        ].search(
            domain,
            order="id asc",
            limit=10000,
        )
        if not events:
            raise UserError(
                _(
                    "No audit events match the selected filters."
                )
            )

        payload = []
        for event in events:
            row = {
                "id": event.id,
                "name": event.name,
                "company_id": event.company_id.id,
                "branch_id": (
                    event.branch_id.id
                    if event.branch_id
                    else False
                ),
                "date_event": str(
                    event.date_event or ""
                ),
                "user_id": event.user_id.id,
                "model": event.ref_model,
                "res_id": event.ref_res_id,
                "resource_snapshot": (
                    event.ref_display_name
                ),
                "action": event.action,
                "severity": event.severity,
                "source": event.source,
                "correlation_id": (
                    event.correlation_id
                ),
                "changed_field_names": (
                    event.changed_field_names
                ),
                "change_digest": (
                    event.change_digest
                ),
                "previous_hash": (
                    event.previous_hash
                ),
                "event_fingerprint": (
                    event.event_fingerprint
                ),
                "event_hash": event.event_hash,
            }
            if self.include_lines:
                row["changes"] = [
                    {
                        "field": line.field_name,
                        "field_type": (
                            line.field_type
                        ),
                        "old": line.old_value,
                        "new": line.new_value,
                        "old_digest": (
                            line.old_digest
                        ),
                        "new_digest": (
                            line.new_digest
                        ),
                        "masked": line.masked,
                    }
                    for line in event.line_ids
                ]
            payload.append(row)

        content = json.dumps(
            {
                "schema": (
                    "ClinicOne Immutable Audit "
                    "Evidence v1"
                ),
                "generated_at": str(
                    fields.Datetime.now()
                ),
                "generated_by": self.env.user.id,
                "company_id": self.company_id.id,
                "record_count": len(payload),
                "events": payload,
            },
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        filename = (
            "clinicone_audit_evidence_"
            f"{fields.Date.today()}.json"
        )
        self.write({
            "export_file": base64.b64encode(
                content
            ),
            "export_filename": filename,
            "record_count": len(payload),
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
