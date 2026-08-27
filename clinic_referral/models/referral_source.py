# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from .referral_utils import optional_model


class ClinicReferralSource(models.Model):
    """Master acquisition/referral source used across ClinicOne."""

    _name = "clinic.referral.source"
    _description = "Clinic Referral Source"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"

    name = fields.Char(string="Source Name", required=True, tracking=True)
    code = fields.Char(string="Source Code", copy=False, default=lambda self: _("New"), tracking=True, index=True)
    active = fields.Boolean(default=True)
    description = fields.Text()
    sequence = fields.Integer(default=10)
    color = fields.Integer(string="Color Index")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one(
        "clinic.branch", string="Owning Branch", check_company=True, index=True,
        domain="[('company_id', '=', company_id)]", help="Leave empty for a company-wide source.",
    )

    category = fields.Selection(
        [("internal_doctor","Internal Doctor Network"),("external_doctor","External Doctor / Clinic"),
         ("agent","Agent / Sales"),("corporate","Corporate / Company"),("patient","Existing Patient Referral"),
         ("social_media","Social Media"),("online_ads","Online Ads / Digital Marketing"),
         ("offline_event","Offline Event / Booth"),("other","Other")],
        required=True, default="internal_doctor", tracking=True,
    )
    referrer_type = fields.Selection(
        [("internal_doctor","Internal Doctor"),("external_doctor","External Doctor / Clinic"),
         ("agent","Marketing Agent"),("patient","Existing Patient"),("corporate","Corporate / Company"),
         ("other","Other")], string="Default Referrer Type", required=True, default="internal_doctor",
    )
    internal_doctor_id = fields.Many2one("clinic.doctor", string="Internal Doctor", ondelete="restrict")
    partner_id = fields.Many2one("res.partner", string="Related Partner", ondelete="restrict")
    contact_name = fields.Char(string="Contact Person")
    phone = fields.Char()
    email = fields.Char()
    address = fields.Char()

    channel_tags = fields.Char()
    campaign_name = fields.Char(string="Default Campaign Name")
    tracking_code = fields.Char(index=True)
    landing_page_url = fields.Char()

    apply_on_booking = fields.Boolean(string="Used in Bookings")
    apply_on_treatment = fields.Boolean(string="Used in Treatment Sessions")
    apply_on_invoice = fields.Boolean(string="Used in Invoices (AR)")
    apply_on_wallet = fields.Boolean(string="Used in Wallet / Finance Rewards")
    apply_on_membership = fields.Boolean(string="Used in Membership Programs")
    apply_on_marketing = fields.Boolean(string="Used in Marketing / Campaigns")
    apply_on_other = fields.Boolean(string="Used in Other Modules")
    integration_notes = fields.Text()

    default_program_id = fields.Many2one(
        "clinic.referral.program", ondelete="restrict", domain="[('company_id', '=', company_id)]",
    )
    default_reward_policy = fields.Selection(
        [("inherit","Inherit from Program"),("none","No Reward"),("wallet_credit","Wallet Credit"),
         ("discount_percent","Discount (%)"),("discount_amount","Discount (Amount)"),
         ("gift","Gift / Free Item"),("points","Loyalty Points"),("other","Other")],
        default="inherit",
    )
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.company.currency_id)
    default_reward_value = fields.Monetary(currency_field="currency_id")
    default_reward_percent = fields.Float()
    default_reward_points = fields.Float()

    referral_ids = fields.One2many("clinic.referral", "source_id", readonly=True)
    referral_count = fields.Integer(compute="_compute_stats", store=True)
    referral_converted_count = fields.Integer(compute="_compute_stats", store=True)
    referral_conversion_rate = fields.Float(compute="_compute_stats", store=True)
    patient_count = fields.Integer(compute="_compute_stats", store=True)
    booking_count = fields.Integer(compute="_compute_external_counts")
    treatment_session_count = fields.Integer(compute="_compute_external_counts")
    membership_count = fields.Integer(compute="_compute_external_counts")

    _code_company_unique = models.Constraint(
        "UNIQUE(code, company_id)", "The Source Code must be unique per company."
    )

    @api.depends("referral_ids.state", "referral_ids.patient_id")
    def _compute_stats(self):
        for source in self:
            referrals = source.referral_ids
            converted = referrals.filtered(lambda rec: rec.state == "converted")
            source.referral_count = len(referrals)
            source.referral_converted_count = len(converted)
            source.referral_conversion_rate = len(converted) / len(referrals) * 100.0 if referrals else 0.0
            source.patient_count = len(referrals.mapped("patient_id"))

    @api.depends("referral_ids", "referral_ids.booking_ids")
    def _compute_external_counts(self):
        Membership = optional_model(self.env, "membership.contract")
        SessionLine = optional_model(self.env, "clinic.treatment.session.line")
        for source in self:
            referrals = source.referral_ids
            source.booking_count = sum(referrals.mapped("booking_count"))
            source.membership_count = (
                Membership.search_count([("referral_id","in",referrals.ids)]) if Membership and referrals else 0
            )
            if SessionLine and referrals and "referral_id" in SessionLine._fields:
                lines = SessionLine.search([("referral_id","in",referrals.ids)])
                source.treatment_session_count = len(lines.mapped("session_id"))
            else:
                source.treatment_session_count = 0

    @api.constrains("default_reward_percent")
    def _check_default_reward_percent(self):
        for source in self:
            if not 0.0 <= (source.default_reward_percent or 0.0) <= 100.0:
                raise ValidationError(_("Default Reward Percent must be between 0 and 100."))

    @api.constrains("company_id", "branch_id", "default_program_id", "internal_doctor_id")
    def _check_company_consistency(self):
        for source in self:
            if source.branch_id and source.branch_id.company_id != source.company_id:
                raise ValidationError(_("Owning Branch must belong to the Source Company."))
            if source.default_program_id and source.default_program_id.company_id != source.company_id:
                raise ValidationError(_("Default Program must belong to the Source Company."))
            if source.internal_doctor_id and source.internal_doctor_id.company_id != source.company_id:
                raise ValidationError(_("Internal Doctor must belong to the Source Company."))

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("code", _("New")) == _("New"):
                vals["code"] = sequence.next_by_code("clinic.referral.source") or _("New")
            vals.setdefault("company_id", self.env.company.id)
        return super().create(vals_list)

    def write(self, vals):
        """Preserve the historical public write surface explicitly."""
        return super().write(vals)

    def get_effective_reward_config(self):
        self.ensure_one()
        if self.default_reward_policy == "inherit" and self.default_program_id:
            config = self.default_program_id.get_reward_config()
            config.update({"from":"program","program_id":self.default_program_id.id,"source_id":self.id})
            return config
        return {
            "from":"source", "source_id":self.id,
            "program_id":self.default_program_id.id if self.default_program_id else False,
            "reward_policy": self.default_reward_policy if self.default_reward_policy != "inherit" else "none",
            "currency_id":self.currency_id.id, "reward_value":self.default_reward_value,
            "reward_percent":self.default_reward_percent, "reward_points":self.default_reward_points,
            "max_reward_per_referral":False, "min_qualifying_amount":False,
            "auto_convert_on_first_sale":False, "require_manual_approval":False,
        }

    def action_open_referrals(self):
        self.ensure_one()
        return {"type":"ir.actions.act_window","name":_("Source Referrals"),"res_model":"clinic.referral",
                "view_mode":"list,kanban,form","domain":[("source_id","=",self.id)],
                "context":{"default_source_id":self.id}}

    def action_open_patients(self):
        self.ensure_one()
        patient_ids = self.referral_ids.mapped("patient_id").ids
        return {"type":"ir.actions.act_window","name":_("Referred Patients"),"res_model":"clinic.patient",
                "view_mode":"list,form","domain":[("id","in",patient_ids)]}

    def action_open_bookings(self):
        self.ensure_one()
        return {"type":"ir.actions.act_window","name":_("Source Bookings"),"res_model":"booking.booking",
                "view_mode":"list,calendar,form","domain":[("referral_source_id","=",self.id)]}

    def action_open_memberships(self):
        self.ensure_one()
        Membership = optional_model(self.env, "membership.contract")
        if not Membership:
            raise ValidationError(_("Clinic Membership is not installed."))
        return {"type":"ir.actions.act_window","name":_("Source Memberships"),"res_model":"membership.contract",
                "view_mode":"list,form","domain":[("referral_id.source_id","=",self.id)]}

    @api.depends("name", "code", "category")
    def _compute_display_name(self):
        selections = dict(self._fields["category"].selection)
        for source in self:
            label = source.name or ""
            if source.code and source.code != _("New"):
                label = "[%s] %s" % (source.code, label)
            if source.category:
                label = "%s (%s)" % (label, selections.get(source.category, source.category))
            source.display_name = label

    def name_get(self):
        """Preserve the historical public naming contract."""
        selections = dict(self._fields["category"].selection)
        result = []
        for source in self:
            label = source.name or ""
            if source.code and source.code != _("New"):
                label = "[%s] %s" % (source.code, label)
            if source.category:
                label = "%s (%s)" % (
                    label,
                    selections.get(source.category, source.category),
                )
            result.append((source.id, label))
        return result
