from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .scope_mixin import (
    QUALITY_CHECK_GENERATE_TOKEN,
    QUALITY_CHECK_REGENERATE_TOKEN,
)


QUALITY_CONTROL_RESULTS = [
    ("pending", "Pending"),
    ("pass", "Pass"),
    ("fail", "Fail"),
    ("observation", "Observation"),
    ("not_applicable", "Not Applicable"),
]


class ClinicQualityCheckLine(models.Model):
    """Historical control snapshot and quality evidence for one Check."""

    _name = "clinic.quality.check.line"
    _description = "Clinic Quality Check Control Result"
    _inherit = "clinic.quality.security.mixin"
    _order = "sequence, control_code, id"
    _check_company_auto = True

    _check_control_uniq = models.Constraint(
        "UNIQUE(check_id, control_code)",
        "Control Code must be unique within the Quality Check.",
    )
    _weight_positive = models.Constraint(
        "CHECK(weight > 0)",
        "Quality Check Control Weight must be greater than zero.",
    )
    _check_result_idx = models.Index(
        "(check_id, result, critical)"
    )

    check_id = fields.Many2one(
        "clinic.quality.check",
        required=True,
        ondelete="cascade",
        index=True,
    )
    template_line_id = fields.Many2one(
        "clinic.quality.check.template.line",
        ondelete="restrict",
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="check_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    branch_id = fields.Many2one(
        related="check_id.branch_id",
        store=True,
        readonly=True,
        index=True,
    )

    sequence = fields.Integer(default=10, readonly=True)
    control_code = fields.Char(
        required=True,
        readonly=True,
        index=True,
    )
    requirement = fields.Text(
        required=True,
        readonly=True,
    )
    guidance = fields.Text(readonly=True)
    evidence_required = fields.Boolean(readonly=True)
    critical = fields.Boolean(readonly=True, index=True)
    weight = fields.Float(required=True, readonly=True)

    result = fields.Selection(
        QUALITY_CONTROL_RESULTS,
        default="pending",
        required=True,
        index=True,
    )
    evidence_note = fields.Text()
    reviewer_note = fields.Text()
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_quality_check_line_attach_rel",
        "line_id",
        "attachment_id",
        string="Evidence Attachments",
    )

    incident_ids = fields.One2many(
        "clinic.incident",
        "quality_check_line_id",
        string="Incident Cases",
        readonly=True,
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count",
    )

    @api.depends("incident_ids")
    def _compute_incident_count(self):
        for line in self:
            line.incident_count = len(line.incident_ids)

    @api.model_create_multi
    def create(self, vals_list):
        if not (
            self.env.su
            or self.env.context.get("quality_check_generate") is QUALITY_CHECK_GENERATE_TOKEN
        ):
            raise AccessError(
                _(
                    "Quality Check control snapshots are generated "
                    "from the approved Template."
                )
            )

        records = super().create(vals_list)
        records._check_line_scope()
        return records

    def write(self, vals):
        vals = dict(vals)

        immutable_snapshot_fields = {
            "check_id",
            "template_line_id",
            "company_id",
            "branch_id",
            "sequence",
            "control_code",
            "requirement",
            "guidance",
            "evidence_required",
            "critical",
            "weight",
        }
        if immutable_snapshot_fields.intersection(vals):
            raise AccessError(
                _("Quality Control snapshot fields are immutable.")
            )

        inspector_fields = {
            "result",
            "evidence_note",
            "evidence_attachment_ids",
        }
        reviewer_fields = {"reviewer_note"}

        if inspector_fields.intersection(vals):
            self._quality_require_inspector()
            if self.filtered(
                lambda line:
                line.check_id.state != "in_progress"
            ):
                raise AccessError(
                    _(
                        "Control results/evidence can be edited only "
                        "while the Check is In Progress."
                    )
                )

        if reviewer_fields.intersection(vals):
            self._quality_require_approver()
            if self.filtered(
                lambda line:
                line.check_id.state != "review"
            ):
                raise AccessError(
                    _(
                        "Reviewer Note can be edited only while "
                        "the Check is in Review."
                    )
                )

        return super().write(vals)

    def unlink(self):
        if not (
            self.env.su
            or self.env.context.get("quality_check_regenerate") is QUALITY_CHECK_REGENERATE_TOKEN
        ):
            raise AccessError(
                _(
                    "Quality Check control evidence cannot be deleted "
                    "directly."
                )
            )
        return super().unlink()

    @api.constrains(
        "check_id",
        "company_id",
        "branch_id",
        "template_line_id",
        "weight",
    )
    def _check_line_scope(self):
        for line in self:
            if line.company_id != line.check_id.company_id:
                raise ValidationError(
                    _("Quality Control company does not match its Check.")
                )
            if line.branch_id != line.check_id.branch_id:
                raise ValidationError(
                    _("Quality Control Branch does not match its Check.")
                )
            if (
                line.template_line_id
                and line.template_line_id.template_id
                != line.check_id.template_id
            ):
                raise ValidationError(
                    _(
                        "Quality Control source line does not belong "
                        "to the Check Template."
                    )
                )
            if line.weight <= 0:
                raise ValidationError(
                    _("Control Weight must be greater than zero.")
                )

    def _validate_quality_evidence(self):
        for line in self:
            if line.result == "pending":
                raise UserError(
                    _(
                        "Control %(control)s is still Pending."
                    ) % {"control": line.control_code}
                )

            requires_evidence = bool(
                line.evidence_required
                or (
                    line.result == "fail"
                    and line.check_id.template_id.require_evidence_on_failure
                )
            )
            if requires_evidence and not (
                (line.evidence_note or "").strip()
                or line.evidence_attachment_ids
            ):
                raise UserError(
                    _(
                        "Control %(control)s requires evidence "
                        "before submission."
                    ) % {"control": line.control_code}
                )
        return True

    def action_create_incident(self):
        self.ensure_one()
        self._quality_require_approver()

        if self.result != "fail":
            raise UserError(
                _("Only a failed Quality Control can create an Incident.")
            )
        if self.incident_ids:
            return self.action_open_incidents()

        if not self.env.user.has_group(
            "clinic_incident_event.group_incident_reporter"
        ):
            raise AccessError(
                _(
                    "Incident Reporter access is required to escalate "
                    "a Quality failure into an Incident case."
                )
            )

        check = self.check_id
        Incident = self.env["clinic.incident"]
        incident_type = (
            check.template_id.failure_incident_type
            or "operational"
        )
        category = Incident._category_for_type(
            check.company_id,
            incident_type,
        )

        staff_ids = []
        if check.staff_id:
            staff_ids.append(check.staff_id.id)

        incident = Incident.create({
            "company_id": check.company_id.id,
            "branch_id": (
                check.branch_id.id
                if (
                    check.branch_id
                    and check.company_id.policy_branch_scope_incident_event
                )
                else False
            ),
            "category_id": category.id,
            "title": _(
                "Quality Failure %(check)s / %(control)s"
            ) % {
                "check": check.name,
                "control": self.control_code,
            },
            "incident_type": incident_type,
            "classification": "operational",
            "severity": "high" if self.critical else "medium",
            "harm_level": "none",
            "recurrence_risk": "medium",
            "occurred_at": fields.Datetime.now(),
            "doctor_id": (
                check.doctor_id.id
                if check.doctor_id
                else False
            ),
            "involved_staff_ids": (
                [fields.Command.set(staff_ids)]
                if staff_ids
                else False
            ),
            "room_id": (
                check.room_id.id
                if check.room_id
                else False
            ),
            "description": _(
                "<p><strong>Quality Check:</strong> %(check)s</p>"
                "<p><strong>Control:</strong> %(control)s</p>"
                "<p><strong>Requirement:</strong> %(requirement)s</p>"
                "<p><strong>Evidence:</strong> %(evidence)s</p>"
            ) % {
                "check": check.display_name,
                "control": self.control_code,
                "requirement": self.requirement,
                "evidence": self.evidence_note or _("See Quality Check evidence."),
            },
            "quality_check_id": check.id,
            "quality_check_line_id": self.id,
        })

        incident._log_timeline(
            "source",
            _("Created from Quality Check Failure"),
            _("%(check)s / %(control)s") % {
                "check": check.name,
                "control": self.control_code,
            },
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Quality Incident"),
            "res_model": "clinic.incident",
            "view_mode": "form",
            "res_id": incident.id,
        }

    def action_open_incidents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quality Incident Cases"),
            "res_model": "clinic.incident",
            "view_mode": "kanban,list,form",
            "domain": [("quality_check_line_id", "=", self.id)],
        }

    def action_open_check(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quality Check"),
            "res_model": "clinic.quality.check",
            "view_mode": "form",
            "res_id": self.check_id.id,
        }
