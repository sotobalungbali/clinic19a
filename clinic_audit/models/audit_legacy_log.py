# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models, _


class ClinicAuditLegacyLog(models.Model):
    """Compatibility owner for the historical `clinic.audit.log` contract.

    IMPORTANT:
    `clinic_encounter` also defines this same model later in the dependency
    graph. Therefore this class intentionally contains only the common
    historical contract that allows earlier modules to resolve the model.
    Authoritative immutable #38 evidence lives in `clinic.audit.event`.
    """

    _name = "clinic.audit.log"
    _description = "Clinic Audit Legacy Log"
    _order = "date_event desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Log #",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    ref_model = fields.Char(string="Model", required=True, index=True)
    ref_res_id = fields.Integer(string="Record ID", required=True, index=True)
    ref = fields.Reference(
        string="Record",
        selection="_referenceable_models",
        compute="_compute_ref",
        store=False,
    )
    ref_display_name = fields.Char(
        string="Record Display",
        compute="_compute_ref_display",
        store=False,
    )

    category = fields.Selection(
        [
            ("create", "Create"),
            ("update", "Update"),
            ("state", "State Transition"),
            ("stage", "Stage Transition"),
            ("attach", "Attachment"),
            ("comment", "Comment"),
            ("custom", "Custom"),
        ],
        string="Category",
        required=True,
        index=True,
        default="update",
    )
    date_event = fields.Datetime(
        string="When",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Who",
        default=lambda self: self.env.user,
        index=True,
    )
    role = fields.Selection(
        [
            ("system", "System"),
            ("user", "User"),
            ("performer", "Performer"),
            ("supervisor", "Supervisor"),
        ],
        string="Role",
        default="user",
        index=True,
    )

    summary = fields.Char()
    reason_code = fields.Selection(
        [
            ("initial", "Initial"),
            ("edit", "Edit"),
            ("correction", "Correction"),
            ("approval", "Approval"),
            ("rejection", "Rejection"),
            ("auto", "Automated"),
            ("other", "Other"),
        ],
        default="edit",
        index=True,
    )
    note = fields.Text()

    field_name = fields.Char()
    old_value_text = fields.Char()
    new_value_text = fields.Char()
    changes_json = fields.Text(
        help='JSON object: {"field": {"old": "...", "new": "..."}, ...}',
    )
    client_ip = fields.Char()
    user_agent = fields.Char()
    color = fields.Integer()

    @api.model
    def _referenceable_models(self):
        IrModel = self.env["ir.model"].sudo()
        result = [(m.model, m.name) for m in IrModel.search([("model", "like", "clinic.%")])]
        result += [
            ("account.move", "Journal Entry / Invoice"),
            ("stock.picking", "Stock Picking"),
        ]
        seen = set()
        return [item for item in result if not (item[0] in seen or seen.add(item[0]))]

    @api.depends("ref_model", "ref_res_id")
    def _compute_ref(self):
        for rec in self:
            rec.ref = f"{rec.ref_model},{rec.ref_res_id}" if rec.ref_model and rec.ref_res_id else False

    @api.depends("ref_model", "ref_res_id")
    def _compute_ref_display(self):
        for rec in self:
            display = False
            if rec.ref_model and rec.ref_res_id and rec.ref_model in self.env:
                try:
                    target = self.env[rec.ref_model].browse(rec.ref_res_id).exists()
                    display = target.display_name if target else False
                except Exception:
                    display = False
            rec.ref_display_name = display


    def action_open_log(self):
        """Open this historical evidence record in the compliance legacy form.

        This method intentionally lives on the compatibility model itself so
        Odoo can validate ``type="object"`` buttons while clinic_audit data is
        being loaded.  A matching final-registry method is installed later by
        ``clinic.audit.registry.hook`` because clinic_encounter historically
        re-declares the same model name after clinic_audit.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Legacy Audit Log"),
            "res_model": "clinic.audit.log",
            "res_id": self.id,
            "view_mode": "form",
        }

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        normalized = []
        for incoming in vals_list:
            vals = dict(incoming)
            vals.setdefault("company_id", self.env.company.id)
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = sequence.next_by_code("clinic.audit.log") or _("New")
            if isinstance(vals.get("changes_json"), dict):
                vals["changes_json"] = json.dumps(vals["changes_json"], ensure_ascii=False, sort_keys=True)
            normalized.append(vals)
        return super().create(normalized)
