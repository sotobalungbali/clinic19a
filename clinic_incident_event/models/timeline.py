from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


TIMELINE_TYPES = [
    ("created", "Created"),
    ("state", "State Change"),
    ("investigation", "Investigation"),
    ("action", "Corrective / Preventive Action"),
    ("regulatory", "Regulatory"),
    ("source", "Source Link"),
    ("note", "Case Note"),
    ("system", "System"),
]


class ClinicIncidentTimeline(models.Model):
    """Immutable Incident-case timeline evidence.

    This is case-specific evidence, not a replacement for the future generic
    ClinicOne Audit owner.
    """

    _name = "clinic.incident.timeline"
    _description = "Clinic Incident Timeline"
    _order = "event_at desc, id desc"
    _check_company_auto = True

    _incident_event_idx = models.Index(
        "(incident_id, event_at, event_type)"
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
    event_at = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        readonly=True,
        index=True,
    )
    event_type = fields.Selection(
        TIMELINE_TYPES,
        required=True,
        default="system",
        readonly=True,
        index=True,
    )
    title = fields.Char(required=True, readonly=True)
    note = fields.Text(readonly=True)
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    from_state = fields.Char(readonly=True, index=True)
    to_state = fields.Char(readonly=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not (
            self.env.su
            or self.env.context.get("incident_timeline_system")
        ):
            raise AccessError(
                _(
                    "Incident Timeline entries require a controlled "
                    "Incident action."
                )
            )

        records = super().create(vals_list)
        records._check_scope()
        return records

    def write(self, vals):
        raise AccessError(
            _("Incident Timeline evidence is immutable.")
        )

    def unlink(self):
        if not self.env.su:
            raise AccessError(
                _("Incident Timeline evidence cannot be deleted.")
            )
        return super().unlink()

    @api.constrains("incident_id", "company_id", "branch_id")
    def _check_scope(self):
        for record in self:
            if record.company_id != record.incident_id.company_id:
                raise ValidationError(
                    _("Timeline company does not match its Incident.")
                )
            if record.branch_id != record.incident_id.branch_id:
                raise ValidationError(
                    _("Timeline Branch does not match its Incident.")
                )

    def action_open_incident(self):
        self.ensure_one()
        return self.incident_id._incident_form_action()
