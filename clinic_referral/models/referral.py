# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .referral_utils import (
    default_working_branch,
    normalize_boolean_search,
    optional_model,
)


class ClinicReferral(models.Model):
    """Referral acquisition and conversion transaction.

    The model remains a neutral hub: downstream sales/service modules may
    point to a Referral, while Referral itself never hard-depends back on
    Treatment Session or Membership.
    """

    _name = "clinic.referral"
    _description = "Clinic Referral"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_referral desc, id desc"

    # ------------------------------------------------------------------
    # Identity and scope
    # ------------------------------------------------------------------
    name = fields.Char(
        string="Referral Number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("converted", "Converted"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        string="Branch",
        check_company=True,
        index=True,
        default=lambda self: default_working_branch(self.env),
        domain="[('company_id', '=', company_id)]",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Patient / clinical context
    # ------------------------------------------------------------------
    patient_id = fields.Many2one(
        "clinic.patient",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    patient_partner_id = fields.Many2one(
        related="patient_id.partner_id",
        store=True,
        readonly=True,
        index=True,
    )
    target_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Target Doctor",
        ondelete="restrict",
        tracking=True,
    )
    clinical_reason = fields.Char(tracking=True)
    clinical_notes = fields.Text()

    # ------------------------------------------------------------------
    # Referrer
    # ------------------------------------------------------------------
    referrer_type = fields.Selection(
        [
            ("internal_doctor", "Internal Doctor"),
            ("external_doctor", "External Doctor / Clinic"),
            ("agent", "Marketing Agent"),
            ("patient", "Existing Patient"),
            ("corporate", "Corporate / Company"),
            ("other", "Other"),
        ],
        default="internal_doctor",
        required=True,
        tracking=True,
    )
    internal_referrer_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Internal Referrer Doctor",
        ondelete="restrict",
    )
    external_referrer_partner_id = fields.Many2one(
        "res.partner",
        string="External Referrer",
        ondelete="restrict",
    )
    referrer_patient_id = fields.Many2one(
        "clinic.patient",
        string="Referrer Patient",
        ondelete="restrict",
    )
    referrer_free_text = fields.Char(string="Other Referrer")

    # ------------------------------------------------------------------
    # Program / acquisition attribution
    # ------------------------------------------------------------------
    program_id = fields.Many2one(
        "clinic.referral.program",
        ondelete="restrict",
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    source_id = fields.Many2one(
        "clinic.referral.source",
        ondelete="restrict",
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    lead_id = fields.Many2one(
        "crm.lead",
        string="CRM Lead / Opportunity",
        ondelete="set null",
        index=True,
    )
    utm_campaign_id = fields.Many2one("utm.campaign", ondelete="set null")
    utm_source_id = fields.Many2one("utm.source", ondelete="set null")
    utm_medium_id = fields.Many2one("utm.medium", ondelete="set null")

    # ------------------------------------------------------------------
    # Dates / expiry
    # ------------------------------------------------------------------
    date_referral = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        index=True,
    )
    date_received = fields.Datetime(tracking=True)
    valid_until = fields.Date(index=True)
    date_converted = fields.Datetime(index=True)
    date_cancelled = fields.Datetime()
    is_expired = fields.Boolean(
        compute="_compute_is_expired",
        search="_search_is_expired",
    )

    # ------------------------------------------------------------------
    # Reward planning / status. Real wallet/accounting settlement remains
    # owned by the downstream financial module.
    # ------------------------------------------------------------------
    reward_policy = fields.Selection(
        [
            ("none", "No Reward"),
            ("wallet_credit", "Wallet Credit"),
            ("discount_percent", "Discount (%)"),
            ("discount_amount", "Discount (Amount)"),
            ("gift", "Gift / Free Item"),
            ("points", "Loyalty Points"),
            ("other", "Other"),
        ],
        default="none",
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    reward_value = fields.Monetary(currency_field="currency_id")
    reward_percent = fields.Float()
    reward_points = fields.Float()
    reward_state = fields.Selection(
        [
            ("none", "No Reward"),
            ("pending", "Pending"),
            ("done", "Done"),
            ("rejected", "Rejected"),
        ],
        default="none",
        tracking=True,
        index=True,
    )
    reward_reference = fields.Char()
    reward_notes = fields.Text()

    # ------------------------------------------------------------------
    # Generic source / conversion lineage
    # ------------------------------------------------------------------
    origin_model_id = fields.Many2one("ir.model")
    origin_res_id = fields.Integer()
    origin_display_name = fields.Char(compute="_compute_origin_display_name")
    conversion_model_id = fields.Many2one(
        "ir.model",
        string="Conversion Document Model",
    )
    conversion_res_id = fields.Integer(string="Conversion Record ID")
    conversion_display_name = fields.Char(
        compute="_compute_conversion_display_name"
    )
    conversion_value = fields.Monetary(
        currency_field="currency_id",
        help="Optional business value attributed to this referral conversion.",
    )

    # ------------------------------------------------------------------
    # Operational links / counters
    # ------------------------------------------------------------------
    booking_ids = fields.One2many(
        "booking.booking",
        "referral_id",
        string="Bookings",
        readonly=True,
    )
    booking_count = fields.Integer(compute="_compute_related_counts")
    treatment_session_count = fields.Integer(compute="_compute_related_counts")
    membership_count = fields.Integer(compute="_compute_related_counts")
    audit_event_count = fields.Integer(compute="_compute_related_counts")
    notes = fields.Text(string="Internal Notes")

    @api.depends("valid_until", "state")
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for referral in self:
            referral.is_expired = bool(
                referral.valid_until
                and referral.valid_until < today
                and referral.state not in ("converted", "cancelled")
            )

    @api.model
    def _search_is_expired(self, operator, value):
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
                ("valid_until", "!=", False),
                ("valid_until", "<", today),
                ("state", "not in", ("converted", "cancelled")),
            ]
        return [
            "|",
            ("valid_until", "=", False),
            "|",
            ("valid_until", ">=", today),
            ("state", "in", ("converted", "cancelled")),
        ]

    @api.depends("origin_model_id", "origin_res_id")
    def _compute_origin_display_name(self):
        self._compute_generic_reference_display(
            "origin_model_id",
            "origin_res_id",
            "origin_display_name",
        )

    @api.depends("conversion_model_id", "conversion_res_id")
    def _compute_conversion_display_name(self):
        self._compute_generic_reference_display(
            "conversion_model_id",
            "conversion_res_id",
            "conversion_display_name",
        )

    def _compute_generic_reference_display(
        self,
        model_field,
        res_id_field,
        display_field,
    ):
        for referral in self:
            label = False
            model_rec = referral[model_field]
            res_id = referral[res_id_field]
            if model_rec and res_id:
                Model = optional_model(self.env, model_rec.model)
                if Model:
                    try:
                        record = Model.browse(res_id).exists()
                        label = record.display_name if record else False
                    except (AccessError, UserError):
                        label = False
            referral[display_field] = label

    @api.depends("booking_ids")
    def _compute_related_counts(self):
        Membership = optional_model(self.env, "membership.contract")
        SessionLine = optional_model(
            self.env,
            "clinic.treatment.session.line",
        )
        AuditEvent = optional_model(self.env, "clinic.audit.event")

        for referral in self:
            referral.booking_count = len(referral.booking_ids)
            referral.membership_count = (
                Membership.search_count([("referral_id", "=", referral.id)])
                if Membership and "referral_id" in Membership._fields
                else 0
            )
            if SessionLine and "referral_id" in SessionLine._fields:
                lines = SessionLine.search([("referral_id", "=", referral.id)])
                referral.treatment_session_count = len(lines.mapped("session_id"))
            else:
                referral.treatment_session_count = 0
            referral.audit_event_count = (
                AuditEvent.search_count(
                    [
                        ("ref_model", "=", referral._name),
                        ("ref_res_id", "=", referral.id),
                    ]
                )
                if AuditEvent
                else 0
            )

    @api.onchange("source_id")
    def _onchange_source_id(self):
        for referral in self:
            if not referral.source_id:
                continue
            source = referral.source_id
            referral.referrer_type = source.referrer_type
            if not referral.program_id and source.default_program_id:
                referral.program_id = source.default_program_id
            if source.internal_doctor_id:
                referral.internal_referrer_doctor_id = source.internal_doctor_id
            if source.partner_id:
                referral.external_referrer_partner_id = source.partner_id
            referral._apply_reward_config_to_record()

    @api.onchange("program_id")
    def _onchange_program_id(self):
        self._apply_reward_config_to_record()

    def _effective_reward_config(self):
        self.ensure_one()
        if self.source_id:
            return self.source_id.get_effective_reward_config()
        if self.program_id:
            return self.program_id.get_reward_config()
        return {}

    def _apply_reward_config_to_record(self):
        for referral in self:
            config = referral._effective_reward_config()
            if not config:
                continue
            referral.reward_policy = config.get("reward_policy") or "none"
            referral.currency_id = (
                config.get("currency_id")
                or referral.company_id.currency_id.id
            )
            referral.reward_value = config.get("reward_value") or 0.0
            referral.reward_percent = config.get("reward_percent") or 0.0
            referral.reward_points = config.get("reward_points") or 0.0

    # ------------------------------------------------------------------
    # Data integrity
    # ------------------------------------------------------------------
    @api.constrains("valid_until", "date_referral")
    def _check_valid_until(self):
        for referral in self:
            if (
                referral.valid_until
                and referral.date_referral
                and referral.valid_until < referral.date_referral.date()
            ):
                raise ValidationError(
                    _("Valid Until cannot be earlier than Referral Date.")
                )

    @api.constrains("reward_percent")
    def _check_reward_percent(self):
        for referral in self:
            if not 0.0 <= (referral.reward_percent or 0.0) <= 100.0:
                raise ValidationError(
                    _("Reward Percent must be between 0 and 100.")
                )

    @api.constrains(
        "company_id",
        "branch_id",
        "patient_id",
        "target_doctor_id",
        "internal_referrer_doctor_id",
        "referrer_patient_id",
        "program_id",
        "source_id",
    )
    def _check_company_scope(self):
        for referral in self:
            if referral.branch_id and referral.branch_id.company_id != referral.company_id:
                raise ValidationError(
                    _("Referral Branch belongs to another Company.")
                )
            if referral.patient_id and referral.patient_id.company_id != referral.company_id:
                raise ValidationError(
                    _("Referral Patient belongs to another Company.")
                )
            for doctor in (
                referral.target_doctor_id,
                referral.internal_referrer_doctor_id,
            ):
                if doctor and doctor.company_id != referral.company_id:
                    raise ValidationError(
                        _("Referral Doctor belongs to another Company.")
                    )
            if (
                referral.referrer_patient_id
                and referral.referrer_patient_id.company_id != referral.company_id
            ):
                raise ValidationError(
                    _("Referrer Patient belongs to another Company.")
                )
            if referral.program_id:
                if referral.program_id.company_id != referral.company_id:
                    raise ValidationError(
                        _("Referral Program belongs to another Company.")
                    )
                if (
                    referral.branch_id
                    and referral.program_id.allowed_branch_ids
                    and referral.branch_id not in referral.program_id.allowed_branch_ids
                ):
                    raise ValidationError(
                        _("Referral Program is not applicable to the selected Branch.")
                    )
            if referral.source_id:
                if referral.source_id.company_id != referral.company_id:
                    raise ValidationError(
                        _("Referral Source belongs to another Company.")
                    )
                if (
                    referral.source_id.branch_id
                    and referral.branch_id
                    and referral.source_id.branch_id != referral.branch_id
                ):
                    raise ValidationError(
                        _(
                            "Branch-specific Referral Source does not match "
                            "the Referral Branch."
                        )
                    )

    # ------------------------------------------------------------------
    # CRUD / workflow
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    sequence.next_by_code("clinic.referral")
                    or _("New")
                )
            vals.setdefault("company_id", self.env.company.id)

            patient = (
                self.env["clinic.patient"].browse(vals["patient_id"])
                if vals.get("patient_id")
                else self.env["clinic.patient"].browse()
            )
            if not vals.get("branch_id") and patient and patient.partner_id:
                partner_branch = patient.partner_id.branch_id
                if partner_branch:
                    vals["branch_id"] = partner_branch.id
            if not vals.get("branch_id"):
                branch = default_working_branch(self.env)
                if branch:
                    vals["branch_id"] = branch.id

            if not vals.get("valid_until"):
                company = self.env["res.company"].browse(vals["company_id"])
                days = company.clinic_referral_default_valid_days
                referral_dt = (
                    fields.Datetime.to_datetime(vals.get("date_referral"))
                    or fields.Datetime.now()
                )
                if days:
                    vals["valid_until"] = referral_dt.date() + timedelta(days=days)

            source = (
                self.env["clinic.referral.source"].browse(vals["source_id"])
                if vals.get("source_id")
                else self.env["clinic.referral.source"].browse()
            )
            program = (
                self.env["clinic.referral.program"].browse(vals["program_id"])
                if vals.get("program_id")
                else self.env["clinic.referral.program"].browse()
            )

            if source and not program and source.default_program_id:
                program = source.default_program_id
                vals["program_id"] = program.id
            if source:
                vals.setdefault("referrer_type", source.referrer_type)
                if source.internal_doctor_id:
                    vals.setdefault(
                        "internal_referrer_doctor_id",
                        source.internal_doctor_id.id,
                    )
                if source.partner_id:
                    vals.setdefault(
                        "external_referrer_partner_id",
                        source.partner_id.id,
                    )

            if not any(
                key in vals
                for key in (
                    "reward_policy",
                    "reward_value",
                    "reward_percent",
                    "reward_points",
                )
            ):
                config = (
                    source.get_effective_reward_config()
                    if source
                    else program.get_reward_config()
                    if program
                    else {}
                )
                if config:
                    company = self.env["res.company"].browse(vals["company_id"])
                    vals.update(
                        {
                            "reward_policy": config.get("reward_policy") or "none",
                            "currency_id": (
                                config.get("currency_id")
                                or company.currency_id.id
                            ),
                            "reward_value": config.get("reward_value") or 0.0,
                            "reward_percent": config.get("reward_percent") or 0.0,
                            "reward_points": config.get("reward_points") or 0.0,
                        }
                    )

        records = super().create(vals_list)
        records._ensure_user_scope()
        return records

    def write(self, vals):
        if "state" in vals and not self.env.context.get("clinic_referral_workflow"):
            for referral in self:
                referral._check_state_transition(referral.state, vals["state"])
        result = super().write(vals)
        if {"company_id", "branch_id"}.intersection(vals):
            self._ensure_user_scope()
        return result

    def unlink(self):
        self._require_manager()
        protected = self.filtered(
            lambda referral: referral.state not in ("draft", "cancelled")
        )
        if protected:
            raise AccessError(
                _("Only Draft or Cancelled referrals can be deleted.")
            )
        return super().unlink()

    def _check_state_transition(self, old_state, new_state):
        allowed = {
            "draft": {"confirmed", "converted", "cancelled", "expired"},
            "confirmed": {"converted", "cancelled", "expired"},
            "converted": set(),
            "cancelled": {"draft"},
            "expired": {"draft"},
        }
        if old_state == new_state:
            return
        if new_state not in allowed.get(old_state, set()):
            raise ValidationError(
                _("Invalid Referral transition: %s → %s.")
                % (old_state, new_state)
            )

    def _require_manager(self):
        if not self.env.user.has_group(
            "clinic_referral.group_referral_manager"
        ):
            raise AccessError(_("Referral Manager access is required."))

    def _ensure_user_scope(self):
        """Fail closed when a normal Referral User crosses branch scope."""
        if self.env.su or self.env.user.has_group(
            "clinic_referral.group_referral_manager"
        ):
            return True
        allowed_branches = self.env.user.allowed_branch_ids
        for referral in self:
            if referral.company_id not in self.env.user.company_ids:
                raise AccessError(
                    _("You are not allowed to manage referrals for this company.")
                )
            if referral.branch_id and referral.branch_id not in allowed_branches:
                raise AccessError(
                    _("The selected Branch is outside your allowed branch scope.")
                )
        return True

    def _validate_confirmation_requirements(self):
        for referral in self:
            company = referral.company_id
            if company.clinic_referral_require_source and not referral.source_id:
                raise ValidationError(
                    _("A Referral Source is required before confirmation.")
                )
            if (
                company.clinic_referral_require_program_for_reward
                and referral.reward_policy != "none"
                and not referral.program_id
            ):
                raise ValidationError(
                    _("A Referral Program is required for rewarded referrals.")
                )
            if referral.is_expired:
                raise ValidationError(_("Expired referrals cannot be confirmed."))

    def action_set_draft(self):
        self._require_manager()
        for referral in self:
            if referral.state not in ("draft", "cancelled", "expired"):
                raise ValidationError(
                    _(
                        "Only Draft, Cancelled or Expired referrals can return "
                        "to Draft."
                    )
                )
            referral.write(
                {
                    "state": "draft",
                    "date_cancelled": False,
                }
            )
        return True

    @staticmethod
    def _effective_datetime(value=None):
        """Normalize an optional business-effective datetime for deterministic history.

        Existing callers remain unchanged: omitting ``value`` preserves the historical
        runtime behavior and uses the current Odoo datetime.
        """
        return fields.Datetime.to_datetime(value) if value else fields.Datetime.now()

    def action_confirm(self, effective_datetime=None):
        self._validate_confirmation_requirements()
        effective = self._effective_datetime(effective_datetime)
        for referral in self:
            if referral.state != "draft":
                continue
            values = {"state": "confirmed"}
            if not referral.date_received:
                values["date_received"] = effective
            referral.write(values)
        return True

    def action_convert(self, effective_datetime=None):
        effective = self._effective_datetime(effective_datetime)
        for referral in self:
            if referral.state not in ("draft", "confirmed"):
                raise ValidationError(
                    _("Only Draft or Confirmed referrals can be converted.")
                )
            if referral.is_expired:
                raise ValidationError(_("Expired referrals cannot be converted."))

            values = {
                "state": "converted",
                "date_converted": effective,
            }
            if not referral.date_received:
                values["date_received"] = effective
            if referral.reward_policy != "none" and referral.reward_state == "none":
                values["reward_state"] = "pending"
            referral.write(values)
        return True

    def mark_converted(self, source_record=None, conversion_value=0.0, effective_datetime=None):
        """Public downstream API for a real conversion event.

        ``effective_datetime`` is optional and exists for legitimate historical
        business events such as deterministic demo/import generation. Omitting it
        preserves the original current-time conversion behavior.
        """
        IrModel = self.env["ir.model"]
        for referral in self:
            values = {}
            if source_record:
                source_record.ensure_one()
                model_rec = IrModel._get(source_record._name)
                values.update(
                    {
                        "conversion_model_id": model_rec.id,
                        "conversion_res_id": source_record.id,
                    }
                )
            if conversion_value:
                values["conversion_value"] = conversion_value
            if values:
                referral.write(values)
            referral.action_convert(effective_datetime=effective_datetime)
        return True

    def action_cancel(self, effective_datetime=None):
        effective = self._effective_datetime(effective_datetime)
        for referral in self:
            if referral.state not in ("draft", "confirmed"):
                raise ValidationError(
                    _("Only Draft or Confirmed referrals can be cancelled.")
                )
            referral.write(
                {
                    "state": "cancelled",
                    "date_cancelled": effective,
                }
            )
        return True

    def action_mark_expired(self, as_of_date=None):
        effective_date = (
            fields.Date.to_date(as_of_date)
            if as_of_date
            else fields.Date.context_today(self)
        )
        for referral in self:
            if referral.state not in ("draft", "confirmed"):
                continue
            if not referral.valid_until or referral.valid_until >= effective_date:
                raise ValidationError(
                    _("Referral can only be marked Expired after Valid Until.")
                )
            referral.write({"state": "expired"})
        return True

    @api.model
    def _cron_expire_due_referrals(self):
        """Expire at most 500 due records per cron pass."""
        today = fields.Date.context_today(self)
        due = self.search(
            [
                ("state", "in", ("draft", "confirmed")),
                ("valid_until", "!=", False),
                ("valid_until", "<", today),
            ],
            limit=500,
        )
        if due:
            due.with_context(clinic_referral_workflow=True).write(
                {"state": "expired"}
            )
        return True

    # ------------------------------------------------------------------
    # Reward workflow
    # ------------------------------------------------------------------
    def action_apply_reward_policy(self):
        self._apply_reward_config_to_record()
        return True

    def action_set_reward_pending(self):
        for referral in self:
            if referral.state != "converted":
                raise ValidationError(
                    _("Reward can become Pending only after conversion.")
                )
            if referral.reward_policy == "none":
                raise ValidationError(_("This referral has no reward policy."))
            referral.reward_state = "pending"
        return True

    def action_mark_reward_done(self):
        self._require_manager()
        for referral in self:
            if referral.state != "converted":
                raise ValidationError(
                    _("Reward can be completed only after conversion.")
                )
            if referral.reward_policy == "none":
                raise ValidationError(_("This referral has no reward policy."))
            referral.reward_state = "done"
        return True

    def action_reject_reward(self):
        self._require_manager()
        for referral in self:
            if referral.reward_policy == "none":
                raise ValidationError(_("This referral has no reward policy."))
            referral.reward_state = "rejected"
        return True

    def action_reset_reward(self):
        self._require_manager()
        self.write(
            {
                "reward_state": "none",
                "reward_reference": False,
            }
        )
        return True

