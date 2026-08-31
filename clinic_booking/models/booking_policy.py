
# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_policy.py
#
# Purpose:
# - Define booking policies used to govern cancellation/reschedule windows,
#   deposits, no-show penalties, and refund behaviors.
# - Provide generic helper APIs that other modules (booking, channel, portal)
#   can call to check permissions and compute fees/deposits.
#
# Integrations (soft-coupled):
# - booking.booking (policy_id on booking)
# - booking.channel (default policy on channel)
# - account/accounting (fees/deposits will be turned into invoice lines by the caller)
# - mail (chatter tracking)
#
# Notes:
# - Keep dependencies minimal and avoid hard-coding XML IDs.
# - All user-facing strings are in English.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class BookingPolicy(models.Model):
    _name = "booking.policy"
    _description = "Booking Policy"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    # -------------------------------------------------------------------------
    # BASIC / IDENTITY
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Policy Name",
        required=True,
        tracking=True,
        help="Human-friendly name of the policy, e.g., 'Default Online Policy'.",
    )
    code = fields.Char(
        string="Technical Code",
        required=True,
        index=True,
        tracking=True,
        help="Unique, URL-safe technical code. Example: 'online_default', 'walkin_default'.",
    )
    description = fields.Text(
        string="Description",
        help="Optional description or internal notes about this policy.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to stop future usage while preserving historical references.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values appear first in selection lists.",
    )
    color = fields.Integer(
        string="Color Index",
        help="Optional color used in Kanban indicators.",
    )

    # -------------------------------------------------------------------------
    # COMPANY / CURRENCY CONTEXT
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
        help="Company to which this policy belongs.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # EFFECTIVITY WINDOW
    # -------------------------------------------------------------------------
    date_start = fields.Date(
        string="Effective From",
        help="Optional start date when the policy becomes effective.",
    )
    date_end = fields.Date(
        string="Effective Until",
        help="Optional end date after which the policy no longer applies.",
    )

    # -------------------------------------------------------------------------
    # CANCELLATION RULES
    # -------------------------------------------------------------------------
    allow_cancel = fields.Boolean(
        string="Allow Cancellation",
        default=True,
        help="Allow customers/staff to cancel a booking under this policy.",
    )
    cancel_cutoff_unit = fields.Selection(
        selection=[("hours", "Hours"), ("days", "Days")],
        string="Cancellation Cutoff Unit",
        default="hours",
        help="Measure unit for the cancellation cutoff window.",
    )
    cancel_cutoff_value = fields.Float(
        string="Cancellation Cutoff Value",
        default=24.0,
        help=(
            "Minimum time before the booking start when cancellation is still allowed "
            "(e.g., 24 hours). If 0, cancellation is allowed until start time."
        ),
    )
    cancel_fee_type = fields.Selection(
        selection=[("none", "None"), ("fixed", "Fixed Amount"), ("percent", "Percentage")],
        string="Cancellation Fee Type",
        default="none",
        help="Fee type applied when cancelling within allowed window (or per exception rules).",
    )
    cancel_fee_fixed = fields.Monetary(
        string="Cancellation Fee (Fixed)",
        currency_field="currency_id",
        help="Fixed cancellation fee. Used when fee type is 'Fixed Amount'.",
    )
    cancel_fee_percent = fields.Float(
        string="Cancellation Fee (%)",
        help="Percentage of booking total as cancellation fee. Used when fee type is 'Percentage'.",
    )

    # -------------------------------------------------------------------------
    # RESCHEDULE RULES
    # -------------------------------------------------------------------------
    allow_reschedule = fields.Boolean(
        string="Allow Reschedule",
        default=True,
        help="Allow moving a booking to a different date/time under this policy.",
    )
    reschedule_cutoff_unit = fields.Selection(
        selection=[("hours", "Hours"), ("days", "Days")],
        string="Reschedule Cutoff Unit",
        default="hours",
        help="Measure unit for the reschedule cutoff window.",
    )
    reschedule_cutoff_value = fields.Float(
        string="Reschedule Cutoff Value",
        default=12.0,
        help=(
            "Minimum time before the booking start when rescheduling is still allowed. "
            "If 0, rescheduling is allowed until start time."
        ),
    )
    reschedule_limit = fields.Integer(
        string="Max Reschedules",
        default=0,
        help="Maximum number of reschedules allowed (0 = unlimited).",
    )
    reschedule_fee_type = fields.Selection(
        selection=[("none", "None"), ("fixed", "Fixed Amount"), ("percent", "Percentage")],
        string="Reschedule Fee Type",
        default="none",
        help="Fee type applied when rescheduling within allowed window.",
    )
    reschedule_fee_fixed = fields.Monetary(
        string="Reschedule Fee (Fixed)",
        currency_field="currency_id",
        help="Fixed reschedule fee. Used when fee type is 'Fixed Amount'.",
    )
    reschedule_fee_percent = fields.Float(
        string="Reschedule Fee (%)",
        help="Percentage of booking total as reschedule fee. Used when fee type is 'Percentage'.",
    )

    # -------------------------------------------------------------------------
    # NO-SHOW RULES
    # -------------------------------------------------------------------------
    no_show_fee_type = fields.Selection(
        selection=[("none", "None"), ("fixed", "Fixed Amount"), ("percent", "Percentage")],
        string="No-show Fee Type",
        default="fixed",
        help="Fee type applied when the patient does not show up (no check-in).",
    )
    no_show_fee_fixed = fields.Monetary(
        string="No-show Fee (Fixed)",
        currency_field="currency_id",
        default=0.0,
        help="Fixed no-show fee. Used when fee type is 'Fixed Amount'.",
    )
    no_show_fee_percent = fields.Float(
        string="No-show Fee (%)",
        help="Percentage of booking total as no-show fee. Used when fee type is 'Percentage'.",
    )
    no_show_grace_minutes = fields.Integer(
        string="No-show Grace (minutes)",
        default=15,
        help="Minutes after start time before the booking is considered a no-show.",
    )

    # -------------------------------------------------------------------------
    # DEPOSIT RULES
    # -------------------------------------------------------------------------
    allow_prepaid_deposit = fields.Boolean(
        string="Allow Prepaid Deposit",
        help="Enable deposit for bookings under this policy.",
    )
    deposit_is_required = fields.Boolean(
        string="Deposit Required",
        help="If enabled, a deposit must be collected under this policy.",
    )
    deposit_fixed_amount = fields.Monetary(
        string="Deposit Fixed Amount",
        currency_field="currency_id",
        help="Fixed deposit amount to request. Leave 0 if using percentage.",
    )
    deposit_percent = fields.Float(
        string="Deposit Percentage",
        help="Deposit percentage (0 - 100). Leave 0 if using fixed amount.",
    )
    deposit_due_timing = fields.Selection(
        selection=[("on_booking", "On Booking"), ("before_start", "Before Start"), ("on_checkin", "On Check-in")],
        string="Deposit Due Timing",
        default="on_booking",
        help="When the deposit must be collected.",
    )
    deposit_before_start_hours = fields.Float(
        string="Hours Before Start (Deposit)",
        default=0.0,
        help="If 'Before Start' is used, how many hours prior to start deposit must be paid.",
    )
    deposit_refund_policy = fields.Selection(
        selection=[
            ("refundable", "Refundable"),
            ("non_refundable", "Non-refundable"),
            ("conditional", "Conditional"),
        ],
        string="Deposit Refund Policy",
        default="conditional",
        help="Refund policy for collected deposits.",
    )

    # -------------------------------------------------------------------------
    # REFUND RULES
    # -------------------------------------------------------------------------
    refund_method = fields.Selection(
        selection=[("original", "Original Payment"), ("wallet", "Wallet/Credit"), ("manual", "Manual Refund")],
        string="Preferred Refund Method",
        default="original",
        help="Preferred method for refunding fees or deposits. Implemented by the caller.",
    )
    refund_delay_days = fields.Integer(
        string="Refund Delay (days)",
        default=0,
        help="Informational delay before refund is processed.",
    )

    # -------------------------------------------------------------------------
    # LINKS / STATS
    # -------------------------------------------------------------------------
    channel_ids = fields.Many2many(
        "booking.channel",
        "booking_policy_channel_rel",
        "policy_id",
        "channel_id",
        string="Channels",
        help="Default channels associated to this policy.",
    )
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_bookings_count",
        help="Number of active bookings using this policy.",
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Policy Technical Code must be unique per company.',
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Policy Name must be unique per company.',
    )

    @api.constrains("date_start", "date_end")
    def _check_date_range(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Effective Until date cannot be earlier than Effective From date."))

    @api.constrains("cancel_fee_percent", "reschedule_fee_percent", "no_show_fee_percent", "deposit_percent")
    def _check_percentages(self):
        for rec in self:
            for field_name in ("cancel_fee_percent", "reschedule_fee_percent", "no_show_fee_percent", "deposit_percent"):
                val = getattr(rec, field_name)
                if val and (val < 0.0 or val > 100.0):
                    raise ValidationError(_("Percent values must be between 0 and 100."))

    @api.constrains("allow_prepaid_deposit", "deposit_is_required", "deposit_fixed_amount", "deposit_percent")
    def _check_deposit_config(self):
        for rec in self:
            if rec.allow_prepaid_deposit and rec.deposit_is_required:
                if not (rec.deposit_fixed_amount or rec.deposit_percent):
                    raise ValidationError(
                        _("When 'Deposit Required' is enabled, either a Fixed Amount or a Percentage must be set.")
                    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _domain_bookings(self):
        return [("policy_id", "=", self.id), ("active", "=", True)]

    def _compute_bookings_count(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    # -------------------------------------------------------------------------
    # UTILS
    # -------------------------------------------------------------------------
    def _get_now(self):
        """Wrapper to ease testing/mocking."""
        return fields.Datetime.now()

    def _hours_to_start(self, booking, at_dt=None):
        """Return hours from 'at_dt' to booking start (can be negative)."""
        if not booking or not booking.start_datetime:
            return None
        at = fields.Datetime.from_string(at_dt) if at_dt else self._get_now()
        start = fields.Datetime.from_string(booking.start_datetime)
        delta = start - at
        return delta.total_seconds() / 3600.0

    def _unit_to_hours(self, unit, value):
        value = value or 0.0
        if unit == "days":
            return value * 24.0
        return value

    def _compute_fee(self, fee_type, fixed, percent, base_amount):
        """Compute fee value based on fee type/values and a base amount."""
        base = base_amount or 0.0
        if fee_type == "fixed":
            return fixed or 0.0
        if fee_type == "percent":
            return ((percent or 0.0) / 100.0) * base
        return 0.0

    def _is_within_effective_dates(self, at_dt=None):
        at = fields.Datetime.from_string(at_dt) if at_dt else self._get_now()
        at_date = at.date()
        for rec in self:
            if rec.date_start and at_date < rec.date_start:
                return False
            if rec.date_end and at_date > rec.date_end:
                return False
        return True

    # -------------------------------------------------------------------------
    # PUBLIC API — DECISION HELPERS
    # -------------------------------------------------------------------------
    def can_cancel(self, booking, at_dt=None, channel=None):
        """
        Check whether cancellation is allowed and compute the fee.
        Returns a dict:
            {
                'allowed': bool,
                'reason': str,         # human-readable
                'fee': float,          # numeric amount (in company currency)
                'currency_id': id,
                'policy_id': id,
            }
        """
        self.ensure_one()
        if not self.allow_cancel:
            return {
                "allowed": False,
                "reason": _("Cancellation is disabled by this policy."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        if not self._is_within_effective_dates(at_dt=at_dt):
            return {
                "allowed": True,
                "reason": _("Policy date range not applicable; fallback allows cancellation."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }

        # Apply exception rule if any, otherwise use policy-level cutoff/fee
        ex = self._match_exception(action_type="cancel", channel=channel, at_dt=at_dt)
        cutoff_hours = None
        fee_type = None
        fee_fixed = 0.0
        fee_percent = 0.0

        if ex:
            cutoff_hours = self._unit_to_hours(ex.cutoff_unit, ex.cutoff_value)
            fee_type = ex.fee_type or "none"
            fee_fixed = ex.fee_fixed or 0.0
            fee_percent = ex.fee_percent or 0.0
        else:
            cutoff_hours = self._unit_to_hours(self.cancel_cutoff_unit, self.cancel_cutoff_value)
            fee_type = self.cancel_fee_type or "none"
            fee_fixed = self.cancel_fee_fixed or 0.0
            fee_percent = self.cancel_fee_percent or 0.0

        hours_to_start = self._hours_to_start(booking, at_dt=at_dt)
        if hours_to_start is None:
            return {
                "allowed": False,
                "reason": _("Booking has no start time."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }

        if cutoff_hours and hours_to_start < cutoff_hours:
            # Still allowed (policy says allow_cancel=True) but within cutoff → fee applies
            fee = self._compute_fee(fee_type, fee_fixed, fee_percent, booking.amount_total)
            return {
                "allowed": True,
                "reason": _("Cancellation is within cutoff window; a fee may apply."),
                "fee": fee,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        return {
            "allowed": True,
            "reason": _("Cancellation is allowed without fee."),
            "fee": 0.0,
            "currency_id": self.currency_id.id,
            "policy_id": self.id,
        }

    def can_reschedule(self, booking, at_dt=None, channel=None, current_reschedules_count=0):
        """
        Check whether reschedule is allowed and compute the fee.
        Returns a dict like can_cancel().
        """
        self.ensure_one()
        if not self.allow_reschedule:
            return {
                "allowed": False,
                "reason": _("Rescheduling is disabled by this policy."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        if self.reschedule_limit and current_reschedules_count >= self.reschedule_limit:
            return {
                "allowed": False,
                "reason": _("Maximum number of reschedules reached."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        if not self._is_within_effective_dates(at_dt=at_dt):
            return {
                "allowed": True,
                "reason": _("Policy date range not applicable; fallback allows rescheduling."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }

        ex = self._match_exception(action_type="reschedule", channel=channel, at_dt=at_dt)
        cutoff_hours = None
        fee_type = None
        fee_fixed = 0.0
        fee_percent = 0.0

        if ex:
            cutoff_hours = self._unit_to_hours(ex.cutoff_unit, ex.cutoff_value)
            fee_type = ex.fee_type or "none"
            fee_fixed = ex.fee_fixed or 0.0
            fee_percent = ex.fee_percent or 0.0
        else:
            cutoff_hours = self._unit_to_hours(self.reschedule_cutoff_unit, self.reschedule_cutoff_value)
            fee_type = self.reschedule_fee_type or "none"
            fee_fixed = self.reschedule_fee_fixed or 0.0
            fee_percent = self.reschedule_fee_percent or 0.0

        hours_to_start = self._hours_to_start(booking, at_dt=at_dt)
        if hours_to_start is None:
            return {
                "allowed": False,
                "reason": _("Booking has no start time."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }

        if cutoff_hours and hours_to_start < cutoff_hours:
            fee = self._compute_fee(fee_type, fee_fixed, fee_percent, booking.amount_total)
            return {
                "allowed": True,
                "reason": _("Rescheduling is within cutoff window; a fee may apply."),
                "fee": fee,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        return {
            "allowed": True,
            "reason": _("Rescheduling is allowed without fee."),
            "fee": 0.0,
            "currency_id": self.currency_id.id,
            "policy_id": self.id,
        }

    def compute_deposit(self, booking):
        """
        Compute deposit amount for the given booking.
        Returns a dict:
            {'required': bool, 'amount': float, 'currency_id': id, 'policy_id': id, 'refund_policy': 'refundable'|'non_refundable'|'conditional'}
        """
        self.ensure_one()
        if not self.allow_prepaid_deposit:
            return {
                "required": False,
                "amount": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
                "refund_policy": self.deposit_refund_policy,
            }
        if self.deposit_is_required and not (self.deposit_fixed_amount or self.deposit_percent):
            # Guard rail; should be prevented by constrains
            raise UserError(_("Deposit is required but no amount/percentage is configured on the policy."))

        amount = 0.0
        base = getattr(booking, "amount_total", 0.0) or 0.0
        if self.deposit_percent:
            amount = (self.deposit_percent / 100.0) * base
        elif self.deposit_fixed_amount:
            amount = self.deposit_fixed_amount

        return {
            "required": bool(self.deposit_is_required),
            "amount": amount or 0.0,
            "currency_id": self.currency_id.id,
            "policy_id": self.id,
            "refund_policy": self.deposit_refund_policy,
        }

    def can_mark_no_show(self, booking, at_dt=None):
        """
        Determine whether a booking can be marked as 'no-show' according to grace time.
        Returns a dict similar to can_cancel()/can_reschedule().
        """
        self.ensure_one()
        if not booking or not booking.start_datetime:
            return {
                "allowed": False,
                "reason": _("Booking has no start time."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        now = fields.Datetime.from_string(at_dt) if at_dt else self._get_now()
        start = fields.Datetime.from_string(booking.start_datetime)
        grace = timedelta(minutes=self.no_show_grace_minutes or 0)
        if now < (start + grace):
            return {
                "allowed": False,
                "reason": _("No-show cannot be marked before grace time elapses."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }

        fee = self._compute_fee(self.no_show_fee_type, self.no_show_fee_fixed, self.no_show_fee_percent, booking.amount_total)
        return {
            "allowed": True,
            "reason": _("No-show can be marked; a fee may apply."),
            "fee": fee,
            "currency_id": self.currency_id.id,
            "policy_id": self.id,
        }

    # -------------------------------------------------------------------------
    # EXCEPTIONS (PER CHANNEL / DATE RANGE)
    # -------------------------------------------------------------------------
    exception_ids = fields.One2many(
        "booking.policy.exception",
        "policy_id",
        string="Exceptions",
        help="Optional per-channel/date exceptions overriding default cutoff/fees.",
    )

    def _match_exception(self, action_type, channel=None, at_dt=None):
        """
        Return the first matching exception for the given action/channel/date.
        Priority: exact channel match in current date, then generic (no channel) in current date.
        """
        self.ensure_one()
        at = fields.Datetime.from_string(at_dt) if at_dt else self._get_now()
        at_date = at.date()
        candidates = self.exception_ids.filtered(lambda e: e.action_type == action_type and
                                                          (not e.date_start or at_date >= e.date_start) and
                                                          (not e.date_end or at_date <= e.date_end))
        # Prefer exact channel match
        if channel:
            channel_matches = candidates.filtered(lambda e: e.channel_id and e.channel_id.id == channel.id)
            if channel_matches:
                return channel_matches.sorted(lambda e: (e.sequence, e.id))[0]
        # Fallback to generic exception (no channel)
        generic = candidates.filtered(lambda e: not e.channel_id)
        if generic:
            return generic.sorted(lambda e: (e.sequence, e.id))[0]
        return None

    # -------------------------------------------------------------------------
    # ACTIONS / VIEWS
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        """Open bookings filtered by this policy."""
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,pivot,graph,activity",
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_policy_id": self.id},
        }
        try:
            action_def = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
            if action_def:
                action = action_def.read()[0]
                action.update({"domain": [("policy_id", "=", self.id)]})
                ctx = action.get("context", {}) or {}
                ctx.update({"default_policy_id": self.id})
                action["context"] = ctx
        except Exception:
            pass
        return action

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    @api.depends('name', 'company_id')
    def _compute_display_name(self):
        """Odoo 19 display-name bridge preserving the existing ClinicOne label."""
        labels = dict(self.name_get())
        for rec in self:
            rec.display_name = labels.get(rec.id) or rec.name or str(rec.id)

    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{label} - {rec.company_id.name}"
            res.append((rec.id, label))
        return res


class BookingPolicyException(models.Model):
    _name = "booking.policy.exception"
    _description = "Booking Policy Exception"
    _order = "sequence, id"

    # Link back to policy
    policy_id = fields.Many2one(
        "booking.policy",
        string="Policy",
        required=True,
        ondelete="cascade",
        index=True,
        help="Policy to which this exception belongs.",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values are applied first.",
    )

    # Scope
    channel_id = fields.Many2one(
        "booking.channel",
        string="Channel",
        help="Optional channel where this exception applies. Leave empty for generic exception.",
    )
    date_start = fields.Date(
        string="Effective From",
        help="Optional start date for this exception.",
    )
    date_end = fields.Date(
        string="Effective Until",
        help="Optional end date for this exception.",
    )

    # Action-specific settings
    action_type = fields.Selection(
        selection=[("cancel", "Cancel"), ("reschedule", "Reschedule")],
        string="Action",
        required=True,
        help="Which action this exception targets.",
    )
    cutoff_unit = fields.Selection(
        selection=[("hours", "Hours"), ("days", "Days")],
        string="Cutoff Unit",
        default="hours",
        help="Unit for the cutoff window.",
    )
    cutoff_value = fields.Float(
        string="Cutoff Value",
        default=0.0,
        help="Minimum time before the booking start when action is still allowed under this exception.",
    )
    fee_type = fields.Selection(
        selection=[("none", "None"), ("fixed", "Fixed Amount"), ("percent", "Percentage")],
        string="Fee Type",
        default="none",
        help="Fee type applied when action occurs within the cutoff window.",
    )
    fee_fixed = fields.Monetary(
        string="Fee (Fixed)",
        currency_field="currency_id",
        help="Fixed fee applied by this exception.",
    )
    fee_percent = fields.Float(
        string="Fee (%)",
        help="Percentage fee applied by this exception.",
    )

    # Currency / Company context (copied from policy for convenience)
    company_id = fields.Many2one(
        "res.company",
        related="policy_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="policy_id.currency_id",
        store=True,
        readonly=True,
    )

    @api.constrains("fee_percent")
    def _check_percent(self):
        for rec in self:
            if rec.fee_percent and (rec.fee_percent < 0.0 or rec.fee_percent > 100.0):
                raise ValidationError(_("Percent values must be between 0 and 100."))

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Effective Until date cannot be earlier than Effective From date."))


class BookingPolicyMixin(models.AbstractModel):
    """
    Abstract mixin to attach a policy reference and helper calls on other models
    (e.g., booking.booking). This keeps import/coupling low while enabling
    reuse of decision helpers.
    """
    _name = "booking.policy.mixin"
    _description = "Booking Policy Mixin"

    policy_id = fields.Many2one(
        "booking.policy",
        string="Policy",
        index=True,
        help="Policy applied to this record. Controls cancellation, reschedule, and deposit rules.",
    )

    @api.onchange("policy_id")
    def _onchange_policy_id(self):
        # Hook left intentionally light; inheriting models may override
        # to prefill deposit flags/values or to refresh computed fields.
        return


