
# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18/19 CE)
# File: models/clinic_queue_channel.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicQueueChannel(models.Model):
    _name = "clinic.queue.channel"
    _description = "Clinic Queue Channel"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"
    _rec_name = "display_name"

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Channel Name",
        required=True,
        tracking=True,
        index=True,
        help="Human-readable name for this queue channel (e.g., Walk-in, Booking, Kiosk).",
    )
    code = fields.Char(
        string="Code",
        required=True,
        tracking=True,
        index=True,
        help="Unique short code (e.g., WALKIN, BOOK, KIOSK). Used for integrations and mapping.",
    )
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Html(string="Description/Notes")

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda s: s.env.company,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Policy/Flags
    # -------------------------------------------------------------------------
    is_default = fields.Boolean(
        string="Default Channel",
        help="If enabled, this channel will be used by default when creating queues.",
        tracking=True,
    )
    allow_walkin = fields.Boolean(
        string="Allow Walk-in",
        default=True,
        help="Whether this channel is used for walk-in patients."
    )
    allow_booking = fields.Boolean(
        string="Allow Booking",
        default=True,
        help="Whether this channel is used for scheduled bookings/appointments."
    )
    allow_portal = fields.Boolean(
        string="Allow Portal",
        default=False,
        help="Whether this channel can be used from website/portal."
    )
    allow_kiosk = fields.Boolean(
        string="Allow Kiosk",
        default=False,
        help="Whether this channel can be used from self-service kiosk."
    )
    allow_phone = fields.Boolean(
        string="Allow Phone",
        default=False,
        help="Whether this channel can be used for phone-based check-in."
    )

    avg_service_time_min = fields.Integer(
        string="Avg. Service Time (min)",
        default=10,
        help="Average handling time per case on this channel. Used for ETA estimation."
    )
    service_calendar_id = fields.Many2one(
        "resource.calendar",
        string="Service Calendar",
        help="Optional working calendar specific for this channel.",
    )

    # Optional charge when using this channel (use safe domain: type or product_tmpl_id.type)
    surcharge_product_id = fields.Many2one(
        "product.product",
        string="Channel Surcharge Product",
        domain=["|", ("type", "=", "service"), ("product_tmpl_id.type", "=", "service")],
        help="Optional service product to charge when this channel is used.",
    )

    # Allowed queue stages specific to this channel (optional)
    allowed_stage_ids = fields.Many2many(
        "clinic.queue.stage",
        "clinic_queue_channel_stage_rel",
        "channel_id",
        "stage_id",
        string="Allowed Stages",
        help="Limit stages available on queues of this channel (leave empty for all).",
    )

    # Backlinks & Stats
    queue_ids = fields.One2many("clinic.queue", "channel_id", string="Queues")
    queue_waiting_count = fields.Integer(
        string="Waiting",
        compute="_compute_queue_stats",
        help="Number of queues in Waiting on this channel."
    )
    queue_in_progress_count = fields.Integer(
        string="In Progress",
        compute="_compute_queue_stats",
        help="Number of queues In Progress on this channel."
    )

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------
    _code_company_uniq = models.Constraint(
        "unique(company_id, code)",
        "Channel Code must be unique per company.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "[%s] %s" % ((rec.code or "").upper(), rec.name or "")

    @api.depends("queue_ids.state")
    def _compute_queue_stats(self):
        for rec in self:
            qs = rec.queue_ids
            rec.queue_waiting_count = len(qs.filtered(lambda q: q.state == "waiting"))
            rec.queue_in_progress_count = len(qs.filtered(lambda q: q.state == "in_progress"))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = (vals["code"] or "").strip().upper()
        recs = super().create(vals_list)
        recs._enforce_single_default_per_company()
        return recs

    def write(self, vals):
        if "code" in vals and vals["code"]:
            vals["code"] = (vals["code"] or "").strip().upper()
        res = super().write(vals)
        if "is_default" in vals:
            self._enforce_single_default_per_company()
        return res

    def _enforce_single_default_per_company(self):
        """
        Ensure only one default channel per company.
        If multiple become default, keep the latest and unset others.
        """
        for company in self.mapped("company_id"):
            defaults = self.search([("company_id", "=", company.id), ("is_default", "=", True)])
            if len(defaults) > 1:
                # keep last written/created (highest id), unset the rest
                to_unset = defaults.sorted(key=lambda r: r.id)[:-1]
                to_unset.write({"is_default": False})

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @api.model
    def get_default_channel(self, company=None):
        company = company or self.env.company
        chan = self.search([("company_id", "=", company.id), ("is_default", "=", True)], limit=1, order="id desc")
        if chan:
            return chan
        # fallback: first active
        return self.search([("company_id", "=", company.id), ("active", "=", True)], limit=1, order="sequence, id")

    @api.model
    def map_from_string(self, txt, company=None):
        """
        Map free-text (e.g., 'walkin', 'booking') to a channel by code or name.
        """
        if not txt:
            return False
        s = (txt or "").strip().upper()
        company = company or self.env.company
        dom = [("company_id", "=", company.id), ("active", "=", True)]
        return self.search([("code", "=", s)] + dom, limit=1) or \
               self.search([("name", "=ilike", txt)] + dom, limit=1)

    # -------------------------------------------------------------------------
    # UI Actions
    # -------------------------------------------------------------------------
    def action_view_queues(self):
        self.ensure_one()
        return {
            "name": _("Queues"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.queue",
            "view_mode": "list,form,kanban",
            "domain": [("channel_id", "=", self.id)],
            "context": {"search_default_active_states": 1},
        }

    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------
    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name or rec.name or "") for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = domain or []
        criteria = []
        if name:
            criteria = ["|", ("code", "=", (name or "").strip().upper()), ("name", operator, name)]
        recs = self.search(domain + criteria, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]
