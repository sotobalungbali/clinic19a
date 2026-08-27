# -*- coding: utf-8 -*-

import hashlib

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicAuditVerification(models.Model):
    _name = "clinic.audit.verification"
    _description = "Clinic Audit Integrity Verification"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(
        required=True,
        default=lambda self: _("New"),
        copy=False,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        check_company=True,
        index=True,
    )
    date_from = fields.Datetime()
    date_to = fields.Datetime()
    single_event_id = fields.Many2one(
        "clinic.audit.event",
        ondelete="set null",
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("running", "Running"),
            ("passed", "Passed"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
        index=True,
    )
    checked_count = fields.Integer(readonly=True)
    failure_count = fields.Integer(readonly=True)
    first_failure_event_id = fields.Many2one(
        "clinic.audit.event",
        readonly=True,
    )
    result_summary = fields.Text(readonly=True)
    run_by_id = fields.Many2one("res.users", readonly=True)
    run_at = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = (
                    sequence.next_by_code("clinic.audit.verification")
                    or _("New")
                )
        return super().create(vals_list)

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(
                    _("From date must be before To date.")
                )

    def action_run(self):
        if not self.env.user.has_group(
            "clinic_audit.group_audit_manager"
        ):
            raise AccessError(
                _("Only Audit Managers may run integrity verification.")
            )

        Event = self.env["clinic.audit.event"]
        for verification in self:
            verification.write({"state": "running"})
            domain = [
                ("company_id", "=", verification.company_id.id),
            ]
            if verification.single_event_id:
                domain.append(
                    ("id", "=", verification.single_event_id.id)
                )
            else:
                if verification.branch_id:
                    domain.append(
                        ("branch_id", "=", verification.branch_id.id)
                    )
                if verification.date_from:
                    domain.append(
                        ("date_event", ">=", verification.date_from)
                    )
                if verification.date_to:
                    domain.append(
                        ("date_event", "<=", verification.date_to)
                    )

            events = Event.search(domain, order="id asc")
            failures = []
            for event in events:
                if not event._verify_fingerprint():
                    failures.append(event)
                    continue

                previous = Event.search(
                    [
                        ("company_id", "=", event.company_id.id),
                        ("id", "<", event.id),
                    ],
                    order="id desc",
                    limit=1,
                )
                expected_previous = (
                    previous.event_hash if previous else "GENESIS"
                )
                expected_hash = hashlib.sha256(
                    (
                        f"{expected_previous}|"
                        f"{event.event_fingerprint}"
                    ).encode("utf-8")
                ).hexdigest()

                if (
                    event.previous_hash != expected_previous
                    or event.event_hash != expected_hash
                ):
                    failures.append(event)

            verification.write({
                "state": "failed" if failures else "passed",
                "checked_count": len(events),
                "failure_count": len(failures),
                "first_failure_event_id": (
                    failures[0].id if failures else False
                ),
                "result_summary": (
                    _(
                        "Integrity failures detected. "
                        "First failed event: %s"
                    )
                    % failures[0].display_name
                    if failures
                    else _(
                        "All selected audit events passed "
                        "fingerprint and chain verification."
                    )
                ),
                "run_by_id": self.env.user.id,
                "run_at": fields.Datetime.now(),
            })
        return True

    def action_open_failure(self):
        self.ensure_one()
        if not self.first_failure_event_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Failed Audit Event"),
            "res_model": "clinic.audit.event",
            "res_id": self.first_failure_event_id.id,
            "view_mode": "form",
        }
