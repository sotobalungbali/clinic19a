# -*- coding: utf-8 -*-

import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ClinicAnalyticsIntegrationService(models.AbstractModel):
    """Bridge analytics workflow evidence to Audit and Integration API."""

    _name = "clinic.analytics.integration.service"
    _description = "Clinic Analytics Integration Service"

    @api.model
    def emit_audit(
        self,
        record,
        action,
        summary,
        severity="low",
    ):
        if "clinic.audit.event" not in self.env:
            return False

        try:
            return (
                self.env["clinic.audit.event"]
                .sudo()
                .with_context(
                    clinic_audit_internal=True,
                    clinic_audit_skip=True,
                )
                .create({
                    "company_id": record.company_id.id,
                    "branch_id": record.branch_id.id if record.branch_id else False,
                    "ref_model": record._name,
                    "ref_res_id": record.id,
                    "action": action,
                    "source": "system",
                    "severity": severity,
                    "summary": summary,
                })
            )
        except Exception:
            _logger.exception(
                "Unable to emit Clinic Audit evidence for %s,%s",
                record._name,
                record.id,
            )
            return False

    @api.model
    def publish_event(
        self,
        record,
        event_code,
        payload,
    ):
        """Optionally publish non-PII analytics metadata to Integration API."""
        enabled = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "clinic.analytics.publish_integration_events",
                "false",
            )
        )
        if str(enabled).strip().lower() not in {
            "1", "true", "yes", "on"
        }:
            return False

        if (
            "clinic.api.event" not in self.env
            or "clinic.api.event.type" not in self.env
        ):
            return False

        EventType = self.env["clinic.api.event.type"].sudo()
        event_type = EventType.search(
            [("code", "=", event_code), ("active", "=", True)],
            limit=1,
        )
        if not event_type:
            return False

        clean_payload = dict(payload or {})
        clean_payload.update({
            "model": record._name,
            "res_id": record.id,
            "company_id": record.company_id.id,
            "branch_id": record.branch_id.id if record.branch_id else False,
        })

        event = self.env["clinic.api.event"].sudo().create({
            "company_id": record.company_id.id,
            "branch_id": record.branch_id.id if record.branch_id else False,
            "event_type_id": event_type.id,
            "model_name": record._name,
            "res_id": record.id,
            "payload_json": json.dumps(
                clean_payload,
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ),
            "state": "draft",
        })
        event._create_deliveries()
        event.sudo().write({"state": "queued"})
        return event
