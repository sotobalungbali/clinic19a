# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from .referral_utils import default_working_branch, normalize_boolean_search, optional_model


class ClinicReferralProgram(models.Model):
    """Referral campaign/program configuration.

    Reward execution remains owned by Wallet/AR/Membership and other downstream
    addons. This model owns only referral eligibility and planned policy.
    """

    _name = "clinic.referral.program"
    _description = "Clinic Referral Program"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_date desc, id desc"

    name = fields.Char(string="Program Name", required=True, tracking=True)
    code = fields.Char(
        string="Program Code", required=True, copy=False, default=lambda self: _("New"),
        tracking=True, index=True,
    )
    active = fields.Boolean(default=True)
    description = fields.Text()
    color = fields.Integer(string="Color Index")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True,
    )
    user_id = fields.Many2one(
        "res.users", string="Program Owner", default=lambda self: self.env.user,
        tracking=True,
    )
    allowed_company_ids = fields.Many2many(
        "res.company", "clinic_referral_program_company_rel", "program_id", "company_id",
        string="Allowed Companies",
        help="If empty, no additional company eligibility restriction is applied.",
    )
    allowed_branch_ids = fields.Many2many(
        "clinic.branch", "clinic_ref_prog_branch_rel", "program_id", "branch_id",
        string="Allowed Branches", domain="[('company_id', '=', company_id)]",
        help="If empty, the program is company-wide.",
    )

    state = fields.Selection(
        [("draft","Draft"),("running","Running"),("paused","Paused"),
         ("closed","Closed"),("archived","Archived")],
        default="draft", required=True, tracking=True, index=True,
    )
    start_date = fields.Date(required=True, tracking=True)
    end_date = fields.Date(tracking=True)
    is_current = fields.Boolean(compute="_compute_period_flags", search="_search_is_current")
    is_future = fields.Boolean(compute="_compute_period_flags", search="_search_is_future")
    is_past = fields.Boolean(compute="_compute_period_flags", search="_search_is_past")

    patient_scope = fields.Selection(
        [("any","Any Patient"),("new_only","New Patients Only"),
         ("existing_only","Existing Patients Only")],
        default="any", required=True,
    )
    min_patient_age = fields.Integer(string="Min Patient Age")
    max_patient_age = fields.Integer(string="Max Patient Age")

    reward_policy = fields.Selection(
        [("none","No Reward"),("wallet_credit","Wallet Credit"),
         ("discount_percent","Discount (%)"),("discount_amount","Discount (Amount)"),
         ("gift","Gift / Free Item"),("points","Loyalty Points"),("other","Other")],
        default="none", required=True, tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id,
    )
    reward_value = fields.Monetary(currency_field="currency_id")
    reward_percent = fields.Float(string="Reward Percent (%)")
    reward_points = fields.Float()
    max_reward_per_referral = fields.Monetary(currency_field="currency_id")
    max_reward_per_referrer = fields.Monetary(currency_field="currency_id")
    min_qualifying_amount = fields.Monetary(currency_field="currency_id")
    auto_convert_on_first_sale = fields.Boolean()
    require_manual_approval = fields.Boolean()

    apply_on_booking = fields.Boolean()
    apply_on_treatment = fields.Boolean()
    apply_on_invoice = fields.Boolean()
    apply_on_wallet = fields.Boolean()
    apply_on_membership = fields.Boolean()
    apply_on_other = fields.Boolean()
    integration_notes = fields.Text()

    referral_ids = fields.One2many("clinic.referral", "program_id", readonly=True)
    referral_count = fields.Integer(compute="_compute_referral_stats", store=True)
    referral_converted_count = fields.Integer(compute="_compute_referral_stats", store=True)
    referral_conversion_rate = fields.Float(compute="_compute_referral_stats", store=True)
    total_reward_value = fields.Monetary(
        currency_field="currency_id", compute="_compute_referral_stats", store=True,
    )
    booking_count = fields.Integer(compute="_compute_external_counts")
    treatment_session_count = fields.Integer(compute="_compute_external_counts")
    membership_count = fields.Integer(compute="_compute_external_counts")

    @api.depends("start_date", "end_date", "state")
    def _compute_period_flags(self):
        today = fields.Date.context_today(self)
        for program in self:
            program.is_current = bool(
                program.state == "running" and program.start_date
                and program.start_date <= today
                and (not program.end_date or program.end_date >= today)
            )
            program.is_future = bool(
                program.start_date and program.start_date > today
                and program.state not in ("closed", "archived")
            )
            program.is_past = bool(
                program.state in ("closed", "archived")
                or (program.end_date and program.end_date < today)
            )

    @api.model
    def _search_is_current(self, operator, value):
        requested = normalize_boolean_search(operator, value)
        if requested is NotImplemented:
            return NotImplemented
        if requested == "all":
            return []
        if requested == "none":
            return [("id", "=", False)]
        today = fields.Date.context_today(self)
        if requested:
            return [
                ("state", "=", "running"), ("start_date", "<=", today),
                "|", ("end_date", "=", False), ("end_date", ">=", today),
            ]
        return [
            "|", ("state", "!=", "running"),
            "|", ("start_date", ">", today),
            "&", ("end_date", "!=", False), ("end_date", "<", today),
        ]

    @api.model
    def _search_is_future(self, operator, value):
        requested = normalize_boolean_search(operator, value)
        if requested is NotImplemented:
            return NotImplemented
        if requested == "all":
            return []
        if requested == "none":
            return [("id", "=", False)]
        today = fields.Date.context_today(self)
        if requested:
            return [("start_date", ">", today), ("state", "not in", ("closed","archived"))]
        return ["|", ("start_date", "<=", today), ("state", "in", ("closed","archived"))]

    @api.model
    def _search_is_past(self, operator, value):
        requested = normalize_boolean_search(operator, value)
        if requested is NotImplemented:
            return NotImplemented
        if requested == "all":
            return []
        if requested == "none":
            return [("id", "=", False)]
        today = fields.Date.context_today(self)
        if requested:
            return [
                "|", ("state", "in", ("closed","archived")),
                "&", ("end_date", "!=", False), ("end_date", "<", today),
            ]
        return [
            ("state", "not in", ("closed","archived")),
            "|", ("end_date", "=", False), ("end_date", ">=", today),
        ]

    @api.depends("referral_ids.state", "referral_ids.reward_value", "referral_ids.reward_state")
    def _compute_referral_stats(self):
        for program in self:
            referrals = program.referral_ids
            converted = referrals.filtered(lambda rec: rec.state == "converted")
            program.referral_count = len(referrals)
            program.referral_converted_count = len(converted)
            program.referral_conversion_rate = (
                len(converted) / len(referrals) * 100.0 if referrals else 0.0
            )
            effective = referrals.filtered(lambda rec: rec.reward_state in ("none","pending","done"))
            program.total_reward_value = sum(effective.mapped("reward_value"))

    @api.depends("referral_ids", "referral_ids.booking_ids")
    def _compute_external_counts(self):
        Membership = optional_model(self.env, "membership.contract")
        SessionLine = optional_model(self.env, "clinic.treatment.session.line")
        for program in self:
            referrals = program.referral_ids
            program.booking_count = sum(referrals.mapped("booking_count"))
            program.membership_count = (
                Membership.search_count([("referral_id", "in", referrals.ids)])
                if Membership and referrals else 0
            )
            if SessionLine and referrals and "referral_id" in SessionLine._fields:
                lines = SessionLine.search([("referral_id", "in", referrals.ids)])
                program.treatment_session_count = len(lines.mapped("session_id"))
            else:
                program.treatment_session_count = 0

    @api.constrains("start_date", "end_date")
    def _check_date_range(self):
        for program in self:
            if program.start_date and program.end_date and program.end_date < program.start_date:
                raise ValidationError(_("End Date cannot be before Start Date."))

    @api.constrains("reward_percent")
    def _check_reward_percent(self):
        for program in self:
            if not 0.0 <= (program.reward_percent or 0.0) <= 100.0:
                raise ValidationError(_("Reward Percent must be between 0 and 100."))

    @api.constrains("min_patient_age", "max_patient_age")
    def _check_patient_age_range(self):
        for program in self:
            if program.min_patient_age < 0 or program.max_patient_age < 0:
                raise ValidationError(_("Patient age limits cannot be negative."))
            if program.min_patient_age and program.max_patient_age and program.max_patient_age < program.min_patient_age:
                raise ValidationError(_("Max Patient Age cannot be smaller than Min Patient Age."))

    @api.constrains("company_id", "allowed_company_ids", "allowed_branch_ids")
    def _check_scope(self):
        for program in self:
            if program.allowed_branch_ids.filtered(lambda branch: branch.company_id != program.company_id):
                raise ValidationError(_("All Allowed Branches must belong to the Program Company."))

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("code", _("New")) == _("New"):
                vals["code"] = sequence.next_by_code("clinic.referral.program") or _("New")
            vals.setdefault("company_id", self.env.company.id)
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals and not self.env.context.get("clinic_referral_workflow"):
            for program in self:
                program._check_state_transition(program.state, vals["state"])
        return super().write(vals)

    def _check_state_transition(self, old_state, new_state):
        allowed = {
            "draft": {"running", "archived"},
            "running": {"paused", "closed", "archived"},
            "paused": {"draft", "running", "closed", "archived"},
            "closed": {"archived"},
            "archived": set(),
        }
        if old_state != new_state and new_state not in allowed.get(old_state, set()):
            raise ValidationError(_("Invalid Referral Program transition: %s → %s.") % (old_state, new_state))

    def _require_manager(self):
        if not self.env.user.has_group("clinic_referral.group_referral_manager"):
            raise AccessError(_("Referral Manager access is required."))

    def action_set_draft(self):
        self._require_manager()
        for program in self:
            if program.state not in ("draft", "paused"):
                raise ValidationError(_("Only Draft or Paused programs can be reset to Draft."))
            program.write({"state": "draft"})
        return True

    def action_start(self):
        self._require_manager()
        today = fields.Date.context_today(self)
        for program in self:
            if not program.start_date:
                raise ValidationError(_("Start Date is required."))
            if program.end_date and program.end_date < today:
                raise ValidationError(_("A program whose End Date is already past cannot be started."))
            program.write({"state": "running"})
        return True

    def action_pause(self):
        self._require_manager()
        for program in self:
            program.write({"state": "paused"})
        return True

    def action_close(self):
        self._require_manager()
        for program in self:
            program.write({"state": "closed"})
        return True

    def action_archive(self):
        self._require_manager()
        for program in self:
            program.write({"state": "archived", "active": False})
        return True

    def is_applicable(self, date=None, company=None, branch=None):
        self.ensure_one()
        date = date or fields.Date.context_today(self)
        company = company or self.env.company
        branch = branch or default_working_branch(self.env)
        # Preserve the historical public contract: company_id is the
        # administrative owner. Eligibility is restricted only when the
        # optional Allowed Companies list is explicitly populated.
        if self.allowed_company_ids and company not in self.allowed_company_ids:
            return False
        if self.allowed_branch_ids and branch not in self.allowed_branch_ids:
            return False
        if self.state != "running":
            return False
        if self.start_date and date < self.start_date:
            return False
        if self.end_date and date > self.end_date:
            return False
        return True

    def get_reward_config(self):
        self.ensure_one()
        return {
            "reward_policy": self.reward_policy,
            "currency_id": self.currency_id.id,
            "reward_value": self.reward_value,
            "reward_percent": self.reward_percent,
            "reward_points": self.reward_points,
            "max_reward_per_referral": self.max_reward_per_referral,
            "min_qualifying_amount": self.min_qualifying_amount,
            "auto_convert_on_first_sale": self.auto_convert_on_first_sale,
            "require_manual_approval": self.require_manual_approval,
        }

    def action_open_referrals(self):
        self.ensure_one()
        return {"type":"ir.actions.act_window","name":_("Program Referrals"),
                "res_model":"clinic.referral","view_mode":"list,kanban,form",
                "domain":[("program_id","=",self.id)],"context":{"default_program_id":self.id}}

    def action_open_bookings(self):
        self.ensure_one()
        return {"type":"ir.actions.act_window","name":_("Program Bookings"),
                "res_model":"booking.booking","view_mode":"list,calendar,form",
                "domain":[("referral_program_id","=",self.id)]}

    def action_open_memberships(self):
        self.ensure_one()
        Membership = optional_model(self.env, "membership.contract")
        if not Membership:
            raise ValidationError(_("Clinic Membership is not installed."))
        return {"type":"ir.actions.act_window","name":_("Program Memberships"),
                "res_model":"membership.contract","view_mode":"list,form",
                "domain":[("referral_id.program_id","=",self.id)]}

    @api.depends("name", "code")
    def _compute_display_name(self):
        for program in self:
            display = program.name or ""
            if program.code and program.code != _("New"):
                display = "[%s] %s" % (program.code, display)
            program.display_name = display

    def name_get(self):
        """Preserve the historical public naming contract."""
        result = []
        for program in self:
            display = program.name or ""
            if program.code and program.code != _("New"):
                display = "[%s] %s" % (program.code, display)
            result.append((program.id, display))
        return result
