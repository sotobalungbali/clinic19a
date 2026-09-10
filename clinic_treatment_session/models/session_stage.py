
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicTreatmentSessionStage(models.Model):
    """Configurable Kanban stage mapped to a technical Treatment Session state."""

    _name = "clinic.treatment.session.stage"
    _description = "Treatment Session Stage"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)
    color = fields.Integer()
    fold = fields.Boolean()
    company_id = fields.Many2one("res.company", index=True, ondelete="cascade")
    technical_state = fields.Selection([
        ("draft", "Draft"), ("confirmed", "Confirmed"),
        ("in_progress", "In Progress"), ("done", "Done"),
        ("no_show", "No-show"), ("cancelled", "Cancelled"),
    ], required=True, default="draft", index=True)
    is_default = fields.Boolean(default=False)
    is_final = fields.Boolean(default=False)
    legend_normal = fields.Char(default="In Progress")
    legend_done = fields.Char(default="Done")
    legend_blocked = fields.Char(default="Blocked")
    session_ids = fields.One2many("clinic.treatment.session", "stage_id")
    sessions_count = fields.Integer(compute="_compute_sessions_count")

    _stage_name_company_unique = models.Constraint(
        "UNIQUE (name, company_id)",
        "Treatment Session Stage name must be unique per company.",
    )

    def _compute_sessions_count(self):
        Session = self.env["clinic.treatment.session"]
        for rec in self:
            rec.sessions_count = Session.search_count([("stage_id", "=", rec.id)])

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list); records._ensure_single_default_per_state(); return records

    def write(self, vals):
        res = super().write(vals)
        if set(vals) & {"is_default", "technical_state", "company_id"}:
            self._ensure_single_default_per_state()
        return res

    def unlink(self):
        for rec in self:
            if rec.session_ids:
                raise ValidationError(_("A Stage used by Treatment Sessions cannot be deleted."))
        return super().unlink()

    def _ensure_single_default_per_state(self):
        for rec in self.filtered("is_default"):
            self.search([
                ("id", "!=", rec.id), ("technical_state", "=", rec.technical_state),
                ("is_default", "=", True),
                ("company_id", "=", rec.company_id.id if rec.company_id else False),
            ]).write({"is_default": False})
        return True

    @api.model
    def get_default_stage(self, technical_state, company_id=False):
        company_id = company_id or self.env.company.id
        domain = [
            ("technical_state", "=", technical_state or "draft"),
            "|", ("company_id", "=", False), ("company_id", "=", company_id),
        ]
        return self.search(domain + [("is_default", "=", True)], limit=1) or self.search(domain, order="sequence, id", limit=1)

    def action_view_sessions(self):
        self.ensure_one()
        action = self.env.ref("clinic_treatment_session.action_clinic_treatment_session").read()[0]
        action["domain"] = [("stage_id", "=", self.id)]
        action["context"] = {"default_stage_id": self.id}
        return action

    def name_get(self):
        labels = dict(self._fields["technical_state"].selection)
        return [(rec.id, "%s [%s: %s]" % (rec.name, _("Status"), labels.get(rec.technical_state))) for rec in self]

    @api.constrains("technical_state", "is_final")
    def _check_final_flag(self):
        return True
