


# -*- coding: utf-8 -*-
from datetime import timedelta
import secrets
import string

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MembershipVoucher(models.Model):
    """Membership-owned voucher with an auditable reservation/redemption lifecycle."""

    _name = "membership.voucher"
    _description = "Membership Voucher"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "membership.workflow.mixin",
        "membership.event.mixin",
    ]
    _order = "state, expiry_date, id desc"

    name = fields.Char(
        string="Voucher Code",
        required=True,
        copy=False,
        index=True,
        default=lambda self: self._generate_code(),
        tracking=True,
    )
    description = fields.Char()
    contract_id = fields.Many2one(
        "membership.contract",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    plan_id = fields.Many2one(
        related="contract_id.plan_id", store=True, readonly=True, index=True
    )
    partner_id = fields.Many2one(
        related="contract_id.partner_id", store=True, readonly=True, index=True
    )
    patient_id = fields.Many2one(
        related="contract_id.patient_id", store=True, readonly=True, index=True
    )
    company_id = fields.Many2one(
        related="contract_id.company_id", store=True, readonly=True, index=True
    )
    currency_id = fields.Many2one(
        related="contract_id.currency_id", store=True, readonly=True
    )
    source_entitlement_id = fields.Many2one(
        "membership.contract.benefit",
        string="Source Entitlement",
        ondelete="set null",
        readonly=True,
    )
    source_benefit_id = fields.Many2one(
        related="source_entitlement_id.source_benefit_id",
        store=True,
        readonly=True,
    )

    voucher_type = fields.Selection(
        [("amount", "Amount"), ("percent", "Percent"), ("free_item", "Free Item")],
        default="amount",
        required=True,
        tracking=True,
    )
    value = fields.Float(digits=(16, 2), required=True)
    max_amount = fields.Monetary(currency_field="currency_id")
    min_base_amount = fields.Monetary(currency_field="currency_id")
    product_id = fields.Many2one(
        "product.product",
        string="Scoped / Free Product",
        ondelete="restrict",
    )
    product_category_id = fields.Many2one("product.category", ondelete="restrict")
    treatment_id = fields.Many2one("clinic.treatment", ondelete="restrict")
    doctor_id = fields.Many2one("clinic.doctor", ondelete="restrict")

    issue_date = fields.Datetime(default=fields.Datetime.now, index=True)
    expiry_date = fields.Date(index=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("issued", "Issued"),
            ("reserved", "Reserved"),
            ("redeemed", "Redeemed"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    is_expired = fields.Boolean(
        compute="_compute_is_expired", search="_search_is_expired"
    )
    pretty_value = fields.Char(compute="_compute_pretty_value")

    reserved_on = fields.Datetime(readonly=True)
    reserved_by = fields.Many2one("res.users", readonly=True)
    redeemed_on = fields.Datetime(readonly=True)
    redeemed_by = fields.Many2one("res.users", readonly=True)
    usage_id = fields.Many2one("membership.usage", ondelete="set null", readonly=True)

    booking_id = fields.Many2one("booking.booking", ondelete="set null")
    encounter_id = fields.Many2one("clinic.encounter", ondelete="set null")
    treatment_session_id = fields.Many2one(
        "clinic.treatment.session", ondelete="set null"
    )
    package_usage_id = fields.Many2one("clinic.package.usage", ondelete="set null")
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration", ondelete="set null"
    )
    move_id = fields.Many2one("account.move", ondelete="set null")
    source_model = fields.Char(index=True)
    source_res_id = fields.Integer(index=True)
    external_reference = fields.Char(index=True)
    notes = fields.Text()

    _code_company_uniq = models.Constraint(
        "UNIQUE(company_id, name)",
        "Membership voucher code must be unique per company.",
    )
    _non_negative_values = models.Constraint(
        "CHECK(value >= 0 AND max_amount >= 0 AND min_base_amount >= 0)",
        "Voucher value and monetary limits cannot be negative.",
    )

    @api.model
    def _generate_code(self):
        alphabet = string.ascii_uppercase + string.digits
        for _attempt in range(20):
            code = "MEM-" + "".join(secrets.choice(alphabet) for _ in range(10))
            if not self.search_count([("name", "=", code)]):
                return code
        return self.env["ir.sequence"].next_by_code("membership.voucher") or "/"

    @api.depends("expiry_date", "state")
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_expired = bool(
                rec.state not in ("redeemed", "cancelled", "expired")
                and rec.expiry_date
                and rec.expiry_date < today
            )

    @api.model
    def _search_is_expired(self, operator, value):
        if operator not in ("=", "!="):
            return NotImplemented
        today = fields.Date.context_today(self)
        domain = [
            ("state", "not in", ("redeemed", "cancelled", "expired")),
            ("expiry_date", "<", today),
        ]
        wanted = bool(value)
        if operator == "!=":
            wanted = not wanted
        return domain if wanted else [
            "|", ("expiry_date", "=", False), ("expiry_date", ">=", today)
        ]

    @api.depends("voucher_type", "value", "currency_id")
    def _compute_pretty_value(self):
        for rec in self:
            if rec.voucher_type == "percent":
                rec.pretty_value = _("%.2f%%") % (rec.value or 0.0)
            elif rec.voucher_type == "free_item":
                rec.pretty_value = _("Free Item")
            else:
                rec.pretty_value = f"{(rec.value or 0.0):,.2f} {rec.currency_id.name or ''}"

    @api.constrains("voucher_type", "value")
    def _check_value(self):
        for rec in self:
            if rec.voucher_type == "percent" and not 0 < rec.value <= 100:
                raise ValidationError(_("Percentage voucher value must be between 0 and 100."))
            if rec.voucher_type == "amount" and rec.value <= 0:
                raise ValidationError(_("Amount voucher value must be greater than zero."))
            if rec.voucher_type == "free_item" and not rec.product_id:
                raise ValidationError(_("Free Item vouchers require a Product."))

    @api.constrains("issue_date", "expiry_date")
    def _check_dates(self):
        for rec in self:
            if rec.issue_date and rec.expiry_date:
                if rec.expiry_date < fields.Datetime.to_datetime(rec.issue_date).date():
                    raise ValidationError(_("Voucher Expiry Date cannot be before Issue Date."))

    def write(self, vals):
        self._membership_guard_direct_state_write(vals)
        protected = {
            "contract_id", "voucher_type", "value", "max_amount", "min_base_amount",
            "product_id", "product_category_id", "treatment_id", "doctor_id",
            "issue_date", "expiry_date", "source_entitlement_id",
        }
        if protected.intersection(vals) and any(
            rec.state in ("redeemed", "expired", "cancelled") for rec in self
        ):
            raise UserError(_("Historical vouchers are immutable."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state != "draft" for rec in self):
            raise UserError(_("Only Draft vouchers can be deleted."))
        return super().unlink()

    @api.model
    def issue_from_entitlement(self, entitlement):
        entitlement.ensure_one()
        contract = entitlement.contract_id
        created = self.browse()
        qty = entitlement.voucher_on_join_qty or 0
        for _index in range(qty):
            expiry_date = False
            if entitlement.voucher_expiry_days:
                expiry_date = (
                    fields.Date.context_today(self)
                    + timedelta(days=entitlement.voucher_expiry_days)
                )
            voucher_sudo = self.sudo().create(
                {
                    "contract_id": contract.id,
                    "source_entitlement_id": entitlement.id,
                    "voucher_type": entitlement.voucher_on_join_type,
                    "value": entitlement.voucher_value,
                    "product_id": (
                        entitlement.free_product_id.id
                        if entitlement.voucher_on_join_type == "free_item"
                        else False
                    ),
                    "treatment_id": entitlement.treatment_id.id,
                    "doctor_id": entitlement.doctor_id.id,
                    "expiry_date": expiry_date,
                }
            )
            voucher = self.browse(voucher_sudo.id)
            voucher.action_issue()
            created |= voucher
        return created

    def action_issue(self):
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.expiry_date and rec.source_entitlement_id.voucher_expiry_days:
                rec.expiry_date = (
                    fields.Date.context_today(rec)
                    + timedelta(days=rec.source_entitlement_id.voucher_expiry_days)
                )
            rec._membership_write_state({"state": "issued"})
            rec._membership_publish_event(
                "voucher.issued",
                {"voucher_id": rec.id, "contract_id": rec.contract_id.id},
            )
        return True

    def _check_redeemability(
        self, *, base_amount=0.0, product=None, treatment=None, doctor=None
    ):
        self.ensure_one()
        if self.state not in ("issued", "reserved"):
            raise UserError(_("Only Issued/Reserved vouchers can be redeemed."))
        if self.is_expired:
            raise UserError(_("This membership voucher has expired."))
        if self.contract_id.state != "active":
            raise UserError(_("The related membership contract is not Active."))
        if self.min_base_amount and base_amount < self.min_base_amount:
            raise UserError(
                _("Minimum base amount for this voucher is %s.")
                % f"{self.min_base_amount:,.2f} {self.currency_id.name or ''}"
            )
        if self.product_id and product != self.product_id:
            raise UserError(_("This voucher is not valid for the selected product."))
        if self.product_category_id and (
            not product or product.categ_id != self.product_category_id
        ):
            raise UserError(_("This voucher is not valid for the selected product category."))
        if self.treatment_id and treatment != self.treatment_id:
            raise UserError(_("This voucher is not valid for the selected treatment."))
        if self.doctor_id and doctor != self.doctor_id:
            raise UserError(_("This voucher is not valid for the selected doctor."))
        return True

    def prepare_discount(
        self, *, base_amount=0.0, product=None, treatment=None, doctor=None
    ):
        self.ensure_one()
        self._check_redeemability(
            base_amount=base_amount,
            product=product,
            treatment=treatment,
            doctor=doctor,
        )
        if self.voucher_type == "amount":
            amount = min(self.value, base_amount)
        elif self.voucher_type == "percent":
            amount = base_amount * self.value / 100.0
            if self.max_amount:
                amount = min(amount, self.max_amount)
        else:
            amount = 0.0
        return max(min(amount, base_amount), 0.0)

    def action_reserve(self):
        for rec in self:
            rec._check_redeemability()
            if rec.state == "issued":
                rec._membership_write_state(
                    {
                        "state": "reserved",
                        "reserved_on": fields.Datetime.now(),
                        "reserved_by": rec.env.user.id,
                    }
                )
        return True

    def action_release(self):
        for rec in self:
            if rec.state != "reserved":
                raise UserError(_("Only Reserved vouchers can be released."))
            rec._membership_write_state(
                {
                    "state": "issued",
                    "reserved_on": False,
                    "reserved_by": False,
                }
            )
        return True

    def action_redeem(self):
        for rec in self:
            rec._check_redeemability()
            if rec.usage_id and rec.usage_id.state != "validated":
                raise UserError(_("Linked membership usage must be Validated before voucher redemption."))
            rec._membership_write_state(
                {
                    "state": "redeemed",
                    "redeemed_on": fields.Datetime.now(),
                    "redeemed_by": rec.env.user.id,
                }
            )
            rec._membership_publish_event(
                "voucher.redeemed",
                {
                    "voucher_id": rec.id,
                    "contract_id": rec.contract_id.id,
                    "usage_id": rec.usage_id.id if rec.usage_id else False,
                },
            )
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "redeemed":
                raise UserError(_("Redeemed vouchers cannot be cancelled; create a compensating voucher if required."))
            rec._membership_write_state({"state": "cancelled"})
            rec._membership_publish_event(
                "voucher.cancelled",
                {"voucher_id": rec.id, "contract_id": rec.contract_id.id},
            )
        return True

    def action_expire(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if (
                rec.state in ("issued", "reserved")
                and rec.expiry_date
                and rec.expiry_date < today
            ):
                rec._membership_write_state({"state": "expired"})
                rec._membership_publish_event(
                    "voucher.expired",
                    {"voucher_id": rec.id, "contract_id": rec.contract_id.id},
                )
        return True

    @api.model
    def cron_expire_vouchers(self):
        Config = self.env["membership.config.service"]
        for company in self.env["res.company"].search([]):
            if not Config.get_value("auto_expire_vouchers", company):
                continue
            records = self.with_company(company).search(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", ("issued", "reserved")),
                    ("expiry_date", "<", fields.Date.context_today(self)),
                ]
            )
            records.action_expire()
        return True

    def action_view_contract(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Contract"),
            "res_model": "membership.contract",
            "view_mode": "form",
            "res_id": self.contract_id.id,
        }


