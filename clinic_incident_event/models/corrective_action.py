from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


ACTION_TYPES = [
    ("containment", "Containment / Immediate Control"),
    ("corrective", "Corrective Action"),
    ("preventive", "Preventive Action"),
    ("training", "Training / Competency"),
    ("process", "Process / Protocol Change"),
    ("device", "Device / Equipment Action"),
    ("other", "Other"),
]

ACTION_STATES = [
    ("planned", "Planned"),
    ("in_progress", "In Progress"),
    ("done", "Done"),
    ("verified", "Verified"),
    ("cancelled", "Cancelled"),
]


class ClinicIncidentAction(models.Model):
    """Governed Incident CAPA with explicit effectiveness verification."""

    _name = "clinic.incident.action"
    _description = "Clinic Incident Corrective / Preventive Action"
    _inherit = ["mail.activity.mixin"]
    _order = "due_at, priority desc, id"
    _check_company_auto = True

    _incident_state_due_idx = models.Index(
        "(incident_id, state, due_at, owner_user_id)"
    )

    name = fields.Char(required=True, index=True)
    incident_id = fields.Many2one(
        "clinic.incident",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="incident_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    branch_id = fields.Many2one(
        related="incident_id.branch_id",
        store=True,
        readonly=True,
        index=True,
    )

    action_type = fields.Selection(
        ACTION_TYPES,
        default="corrective",
        required=True,
        index=True,
    )
    priority = fields.Selection(
        [
            ("0", "Normal"),
            ("1", "High"),
            ("2", "Very High"),
            ("3", "Critical"),
        ],
        default="0",
        required=True,
        index=True,
    )
    state = fields.Selection(
        ACTION_STATES,
        default="planned",
        required=True,
        readonly=True,
        index=True,
    )

    owner_user_id = fields.Many2one(
        "res.users",
        string="Action Owner",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    owner_staff_id = fields.Many2one(
        "clinic.staff",
        string="Responsible Staff",
        ondelete="set null",
        index=True,
    )
    due_at = fields.Datetime(required=True, index=True)
    started_at = fields.Datetime(readonly=True)
    done_at = fields.Datetime(readonly=True)
    verified_at = fields.Datetime(readonly=True)
    verified_by_id = fields.Many2one("res.users", readonly=True)

    description = fields.Text(required=True)
    completion_note = fields.Text()
    effectiveness_result = fields.Selection(
        [
            ("effective", "Effective"),
            ("partially_effective", "Partially Effective"),
            ("ineffective", "Ineffective"),
        ],
        readonly=True,
        index=True,
    )
    effectiveness_note = fields.Text()
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_incident_action_attach_rel",
        "action_id",
        "attachment_id",
        string="Evidence Attachments",
    )
    is_overdue = fields.Boolean(compute="_compute_is_overdue")

    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for action in self:
            action.is_overdue = bool(
                action.state
                not in ("done", "verified", "cancelled")
                and action.due_at
                and action.due_at < now
            )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            incident = self.env["clinic.incident"].browse(
                vals.get("incident_id")
            ).exists()
            if not incident:
                raise ValidationError(_("A valid Incident is required."))

            incident._require_investigator()
            if incident.state in ("closed", "cancelled"):
                raise UserError(
                    _("Closed/Cancelled Incidents cannot receive a new CAPA.")
                )

            if not vals.get("due_at"):
                vals["due_at"] = (
                    fields.Datetime.now()
                    + timedelta(
                        days=(
                            incident.company_id
                            .clinic_incident_default_capa_days
                        )
                    )
                )

            prepared.append(vals)

        records = super().create(prepared)
        records._check_scope()
        for record in records:
            record.incident_id._log_timeline(
                "action",
                _("CAPA Created"),
                record.name,
            )
        return records

    def write(self, vals):
        if (
            "state" in vals
            and not self.env.context.get("incident_action_transition")
        ):
            raise AccessError(
                _("Use CAPA workflow actions to change status.")
            )

        if self.filtered(
            lambda action:
            action.state in ("verified", "cancelled")
        ) and not self.env.context.get("incident_action_transition"):
            raise AccessError(
                _("Verified/Cancelled CAPA records are read-only.")
            )

        verification_fields = {
            "effectiveness_result",
            "verified_at",
            "verified_by_id",
        }
        if verification_fields.intersection(vals) and not self.env.context.get(
            "incident_action_verification"
        ):
            raise AccessError(
                _(
                    "CAPA effectiveness result/timestamps are "
                    "verification-managed."
                )
            )

        if (
            "effectiveness_note" in vals
            and not self.env.context.get("incident_action_verification")
        ):
            self.incident_id._require_manager()
            if self.filtered(
                lambda action:
                action.state != "done"
            ):
                raise AccessError(
                    _(
                        "Effectiveness Note can only be prepared "
                        "on a Done CAPA."
                    )
                )

        result = super().write(vals)
        self._check_scope()
        return result

    def unlink(self):
        if not self.env.su:
            self.incident_id._require_manager()
            if self.filtered(
                lambda action: action.state != "planned"
            ):
                raise UserError(
                    _("Only Planned CAPA records may be deleted.")
                )
        return super().unlink()

    @api.constrains(
        "incident_id",
        "company_id",
        "owner_user_id",
        "owner_staff_id",
    )
    def _check_scope(self):
        for action in self:
            if action.company_id != action.incident_id.company_id:
                raise ValidationError(
                    _("CAPA company does not match its Incident.")
                )

            if (
                action.owner_user_id
                and action.company_id
                not in action.owner_user_id.company_ids
            ):
                raise ValidationError(
                    _(
                        "CAPA Action Owner does not have access "
                        "to this company."
                    )
                )

            if (
                action.owner_staff_id
                and action.owner_staff_id.company_id
                and action.owner_staff_id.company_id != action.company_id
            ):
                raise ValidationError(
                    _("Responsible Staff belongs to another company.")
                )

    def action_start(self):
        for action in self:
            action.incident_id._require_investigator()
            if action.state != "planned":
                raise UserError(_("Only Planned CAPA can be started."))

            action.with_context(
                incident_action_transition=True
            ).write({
                "state": "in_progress",
                "started_at": fields.Datetime.now(),
            })
            action.incident_id._log_timeline(
                "action",
                _("CAPA Started"),
                action.name,
            )
        return True

    def action_mark_done(self):
        for action in self:
            action.incident_id._require_investigator()
            if action.state not in ("planned", "in_progress"):
                raise UserError(
                    _(
                        "Only Planned/In-Progress CAPA can be "
                        "marked Done."
                    )
                )
            if not (action.completion_note or "").strip():
                raise UserError(
                    _(
                        "Completion Note is required before "
                        "marking CAPA Done."
                    )
                )

            action.with_context(
                incident_action_transition=True
            ).write({
                "state": "done",
                "started_at": (
                    action.started_at
                    or fields.Datetime.now()
                ),
                "done_at": fields.Datetime.now(),
            })
            action.incident_id._log_timeline(
                "action",
                _("CAPA Completed"),
                action.name,
            )
        return True

    def _verify(self, result):
        label = dict(
            self._fields["effectiveness_result"].selection
        ).get(result, result)

        for action in self:
            action.incident_id._require_manager()
            if action.state != "done":
                raise UserError(
                    _("Only a Done CAPA can be verified.")
                )
            if not (action.effectiveness_note or "").strip():
                raise UserError(
                    _(
                        "Effectiveness Note is required before "
                        "verifying CAPA."
                    )
                )

            action.with_context(
                incident_action_transition=True,
                incident_action_verification=True,
            ).write({
                "state": "verified",
                "effectiveness_result": result,
                "verified_at": fields.Datetime.now(),
                "verified_by_id": self.env.user.id,
            })
            action.incident_id._log_timeline(
                "action",
                _("CAPA Verified: %(result)s") % {
                    "result": label,
                },
                action.name,
            )
        return True

    def action_verify_effective(self):
        return self._verify("effective")

    def action_verify_partial(self):
        return self._verify("partially_effective")

    def action_verify_ineffective(self):
        return self._verify("ineffective")

    def action_cancel(self):
        for action in self:
            action.incident_id._require_manager()
            if action.state == "verified":
                raise UserError(
                    _("A Verified CAPA cannot be cancelled.")
                )

            action.with_context(
                incident_action_transition=True
            ).write({"state": "cancelled"})
            action.incident_id._log_timeline(
                "action",
                _("CAPA Cancelled"),
                action.name,
            )
        return True

    def action_open_incident(self):
        self.ensure_one()
        return self.incident_id._incident_form_action()
