from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


INVESTIGATION_STATES = [
    ("draft", "Draft"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]

METHODOLOGIES = [
    ("five_whys", "5 Whys"),
    ("fishbone", "Fishbone / Ishikawa"),
    ("rca", "Root Cause Analysis"),
    ("timeline", "Timeline Analysis"),
    ("process_review", "Process / Protocol Review"),
    ("other", "Other"),
]


class ClinicIncidentInvestigation(models.Model):
    """Structured root-cause investigation owned by the Incident case."""

    _name = "clinic.incident.investigation"
    _description = "Clinic Incident Investigation"
    _inherit = ["mail.activity.mixin"]
    _order = "started_at desc, id desc"
    _check_company_auto = True

    _incident_state_idx = models.Index(
        "(incident_id, state, lead_user_id)"
    )

    name = fields.Char(
        string="Investigation Reference",
        required=True,
        default="/",
        readonly=True,
        copy=False,
        index=True,
    )
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
    patient_id = fields.Many2one(
        related="incident_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )

    methodology = fields.Selection(
        METHODOLOGIES,
        default="five_whys",
        required=True,
        index=True,
    )
    state = fields.Selection(
        INVESTIGATION_STATES,
        default="draft",
        required=True,
        readonly=True,
        index=True,
    )
    lead_user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    participant_user_ids = fields.Many2many(
        "res.users",
        "clinic_incident_invest_user_rel",
        "investigation_id",
        "user_id",
        string="Participants",
    )

    started_at = fields.Datetime(readonly=True, index=True)
    completed_at = fields.Datetime(readonly=True, index=True)

    scope = fields.Text(
        help="What is included/excluded from this investigation."
    )
    evidence_summary = fields.Text()
    chronology = fields.Text()
    five_whys = fields.Text(string="5 Whys Analysis")
    contributing_factors = fields.Text()
    root_cause = fields.Text()
    lessons_learned = fields.Text()
    recommendation = fields.Text()

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
                    _(
                        "A closed/cancelled Incident cannot receive "
                        "a new Investigation."
                    )
                )

            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(incident.company_id)
                    .next_by_code("clinic.incident.investigation")
                    or "/"
                )
            prepared.append(vals)

        records = super().create(prepared)
        records._check_company()
        for record in records:
            record.incident_id._log_timeline(
                "investigation",
                _("Investigation Created"),
                record.name,
            )
        return records

    def write(self, vals):
        if (
            "state" in vals
            and not self.env.context.get("incident_investigation_transition")
        ):
            raise AccessError(
                _("Use Investigation workflow actions to change status.")
            )

        if self.filtered(
            lambda investigation:
            investigation.state in ("completed", "cancelled")
        ) and not self.env.context.get("incident_investigation_transition"):
            raise AccessError(
                _("Completed/Cancelled Investigations are read-only.")
            )

        result = super().write(vals)
        self._check_company()
        return result

    def unlink(self):
        if not self.env.su:
            self.incident_id._require_manager()
            if self.filtered(
                lambda investigation:
                investigation.state != "draft"
            ):
                raise UserError(
                    _("Only Draft Investigations may be deleted.")
                )
        return super().unlink()

    @api.constrains(
        "incident_id",
        "company_id",
        "lead_user_id",
        "participant_user_ids",
    )
    def _check_company(self):
        for record in self:
            if record.company_id != record.incident_id.company_id:
                raise ValidationError(
                    _("Investigation company does not match its Incident.")
                )

            users = record.lead_user_id | record.participant_user_ids
            invalid = users.filtered(
                lambda user:
                record.company_id not in user.company_ids
            )
            if invalid:
                raise ValidationError(
                    _(
                        "Investigation Lead/Participants must have access "
                        "to the Incident company."
                    )
                )

    def action_start(self):
        for record in self:
            record.incident_id._require_investigator()
            if record.state != "draft":
                raise UserError(
                    _("Only a Draft Investigation can be started.")
                )

            record.with_context(
                incident_investigation_transition=True
            ).write({
                "state": "in_progress",
                "started_at": fields.Datetime.now(),
            })
            record.incident_id._log_timeline(
                "investigation",
                _("Investigation Started"),
                record.name,
            )
        return True

    def action_complete(self):
        for record in self:
            record.incident_id._require_investigator()
            if record.state not in ("draft", "in_progress"):
                raise UserError(
                    _(
                        "Only Draft/In-Progress Investigations can "
                        "be completed."
                    )
                )
            if not (record.root_cause or "").strip():
                raise UserError(
                    _("Root Cause is required before completing Investigation.")
                )
            if not (record.evidence_summary or "").strip():
                raise UserError(
                    _(
                        "Evidence Summary is required before completing "
                        "Investigation."
                    )
                )

            record.with_context(
                incident_investigation_transition=True
            ).write({
                "state": "completed",
                "started_at": (
                    record.started_at
                    or fields.Datetime.now()
                ),
                "completed_at": fields.Datetime.now(),
            })

            if not record.incident_id.root_cause_summary:
                record.incident_id.with_context(
                    incident_transition=True
                ).write({
                    "root_cause_summary": record.root_cause,
                })

            record.incident_id._log_timeline(
                "investigation",
                _("Investigation Completed"),
                record.name,
            )
        return True

    def action_cancel(self):
        for record in self:
            record.incident_id._require_manager()
            if record.state == "completed":
                raise UserError(
                    _("A completed Investigation cannot be cancelled.")
                )

            record.with_context(
                incident_investigation_transition=True
            ).write({"state": "cancelled"})
            record.incident_id._log_timeline(
                "investigation",
                _("Investigation Cancelled"),
                record.name,
            )
        return True

    def action_open_incident(self):
        self.ensure_one()
        return self.incident_id._incident_form_action()
