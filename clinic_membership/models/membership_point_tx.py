


# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MembershipPointTransaction(models.Model):
    """Immutable loyalty-points ledger."""

    _name = "membership.point.tx"
    _description = "Membership Point Transaction"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "membership.workflow.mixin",
        "membership.event.mixin",
    ]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Transaction Reference",
        required=True,
        copy=False,
        index=True,
        default=lambda self: self._next_name(),
        tracking=True,
    )
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

    tx_type = fields.Selection(
        [
            ("earn", "Earn"),
            ("spend", "Spend"),
            ("adjust", "Adjust"),
            ("expire", "Expire"),
            ("reverse", "Reverse"),
        ],
        default="earn",
        required=True,
        index=True,
        tracking=True,
    )
    date = fields.Datetime(
        default=fields.Datetime.now, required=True, index=True, tracking=True
    )
    points = fields.Float(required=True, digits=(16, 2), tracking=True)
    running_balance = fields.Float(
        compute="_compute_running_balance", digits=(16, 2)
    )
    money_value = fields.Monetary(currency_field="currency_id")
    expiry_date = fields.Date(index=True)
    expired_source_id = fields.Many2one(
        "membership.point.tx",
        string="Expired Earn Transaction",
        ondelete="restrict",
    )
    reversed_of_id = fields.Many2one(
        "membership.point.tx",
        string="Reversed Transaction",
        ondelete="restrict",
    )

    state = fields.Selection(
        [("draft", "Draft"), ("validated", "Validated"), ("cancelled", "Cancelled")],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    created_by = fields.Many2one(
        "res.users", default=lambda self: self.env.user, readonly=True
    )
    validated_by = fields.Many2one("res.users", readonly=True)
    validated_on = fields.Datetime(readonly=True)

    usage_id = fields.Many2one("membership.usage", ondelete="set null")
    booking_id = fields.Many2one("booking.booking", ondelete="set null")
    encounter_id = fields.Many2one("clinic.encounter", ondelete="set null")
    treatment_session_id = fields.Many2one(
        "clinic.treatment.session", ondelete="set null"
    )
    package_usage_id = fields.Many2one("clinic.package.usage", ondelete="set null")
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration", ondelete="set null"
    )
    sale_order_id = fields.Many2one("sale.order", ondelete="set null")
    sale_line_id = fields.Many2one("sale.order.line", ondelete="set null")
    move_id = fields.Many2one("account.move", ondelete="set null")
    move_line_id = fields.Many2one("account.move.line", ondelete="set null")
    source_model = fields.Char(index=True)
    source_res_id = fields.Integer(index=True)
    external_reference = fields.Char(index=True)
    note = fields.Text()

    _reference_company_uniq = models.Constraint(
        "UNIQUE(company_id, name)",
        "Membership point transaction reference must be unique per company.",
    )
    _single_reversal = models.Constraint(
        "UNIQUE(reversed_of_id)",
        "A membership point transaction can only be reversed once.",
    )

    @api.model
    def _next_name(self):
        return self.env["ir.sequence"].next_by_code("membership.point.tx") or "/"

    @api.depends("contract_id", "date", "points", "state")
    def _compute_running_balance(self):
        for rec in self:
            if not rec.contract_id:
                rec.running_balance = 0.0
                continue
            rows = self.search(
                [
                    ("contract_id", "=", rec.contract_id.id),
                    ("state", "=", "validated"),
                ],
                order="date asc, id asc",
            )
            balance = 0.0
            snapshot = 0.0
            for row in rows:
                balance += row.points
                if row.id == rec.id:
                    snapshot = balance
                    break
            rec.running_balance = snapshot if rec.state == "validated" else balance

    @api.constrains("points", "tx_type")
    def _check_points_sign(self):
        for rec in self:
            if rec.tx_type == "earn" and rec.points <= 0:
                raise ValidationError(_("Earn transactions require positive points."))
            if rec.tx_type in ("spend", "expire") and rec.points >= 0:
                raise ValidationError(_("Spend and Expire transactions require negative points."))
            if not rec.points:
                raise ValidationError(_("Point transaction amount cannot be zero."))

    @api.constrains("expired_source_id", "tx_type")
    def _check_expired_source(self):
        for rec in self:
            if rec.expired_source_id and rec.expired_source_id.tx_type != "earn":
                raise ValidationError(_("Expired Source must be an Earn transaction."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("name", self._next_name())
        return super().create(vals_list)

    def write(self, vals):
        self._membership_guard_direct_state_write(vals)
        protected = {
            "contract_id", "tx_type", "date", "points", "money_value",
            "expiry_date", "expired_source_id", "reversed_of_id", "usage_id",
            "booking_id", "encounter_id", "treatment_session_id",
            "package_usage_id", "emar_administration_id", "sale_order_id",
            "sale_line_id", "move_id", "move_line_id", "source_model",
            "source_res_id", "external_reference",
        }
        if protected.intersection(vals) and any(rec.state == "validated" for rec in self):
            raise UserError(
                _("Validated point transactions are immutable. Reverse the transaction instead.")
            )
        return super().write(vals)

    def unlink(self):
        if any(rec.state == "validated" for rec in self):
            raise UserError(_("Validated point transactions cannot be deleted."))
        return super().unlink()

    @api.model
    def get_balance(self, contract_id):
        return sum(
            self.search(
                [
                    ("contract_id", "=", contract_id),
                    ("state", "=", "validated"),
                ]
            ).mapped("points")
        )

    @api.model
    def get_spendable_balance(self, contract_id):
        return max(self.get_balance(contract_id), 0.0)

    def action_validate(self):
        Config = self.env["membership.config.service"]
        for rec in self:
            if rec.state != "draft":
                continue
            if rec.contract_id.state not in ("active", "on_hold"):
                raise UserError(_("Points can only be posted to an Active/On Hold contract."))
            if rec.tx_type == "spend":
                available = self.get_spendable_balance(rec.contract_id.id)
                allow_negative = Config.get_value(
                    "allow_negative_points", rec.company_id
                )
                if not allow_negative and available + rec.points < -1e-9:
                    raise UserError(
                        _("Insufficient loyalty points. Available: %.2f") % available
                    )
            rec._membership_write_state(
                {
                    "state": "validated",
                    "validated_by": rec.env.user.id,
                    "validated_on": fields.Datetime.now(),
                }
            )
            rec._membership_publish_event(
                "points.validated",
                {
                    "point_tx_id": rec.id,
                    "contract_id": rec.contract_id.id,
                    "tx_type": rec.tx_type,
                    "points": rec.points,
                },
            )
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "validated":
                raise UserError(_("Validated point transactions must be reversed, not cancelled."))
            rec._membership_write_state({"state": "cancelled"})
        return True

    def action_reverse(self):
        created = self.browse()
        for rec in self:
            if rec.state != "validated":
                raise UserError(_("Only Validated point transactions can be reversed."))
            if self.search_count([("reversed_of_id", "=", rec.id)]):
                raise UserError(_("This point transaction has already been reversed."))
            reverse_sudo = self.sudo().create(
                {
                    "contract_id": rec.contract_id.id,
                    "tx_type": "reverse",
                    "points": -rec.points,
                    "money_value": -(rec.money_value or 0.0),
                    "reversed_of_id": rec.id,
                    "external_reference": rec.name,
                    "note": _("Reversal of %s") % rec.name,
                }
            )
            reverse = self.browse(reverse_sudo.id)
            reverse.action_validate()
            created |= reverse
        if len(created) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Point Reversal"),
                "res_model": "membership.point.tx",
                "view_mode": "form",
                "res_id": created.id,
            }
        return True

    @api.model
    def earn_points(
        self,
        contract,
        points,
        *,
        note=None,
        expiry_days=None,
        source_model=None,
        source_res_id=None,
        external_reference=None,
    ):
        contract.ensure_one()
        if points <= 0:
            raise ValidationError(_("Earned points must be greater than zero."))
        if expiry_days is None:
            expiry_days = self.env["membership.config.service"].get_value(
                "default_points_expiry_days", contract.company_id
            )
        expiry_date = (
            fields.Date.context_today(self) + timedelta(days=int(expiry_days))
            if expiry_days
            else False
        )
        tx_sudo = self.sudo().create(
            {
                "contract_id": contract.id,
                "tx_type": "earn",
                "points": points,
                "expiry_date": expiry_date,
                "note": note,
                "source_model": source_model,
                "source_res_id": source_res_id,
                "external_reference": external_reference,
            }
        )
        tx = self.browse(tx_sudo.id)
        tx = self.browse(tx_sudo.id)
        tx = self.browse(tx_sudo.id)
        tx.action_validate()
        return tx

    @api.model
    def spend_points(
        self,
        contract,
        points,
        *,
        note=None,
        source_model=None,
        source_res_id=None,
        external_reference=None,
    ):
        contract.ensure_one()
        points = abs(float(points or 0.0))
        if not points:
            raise ValidationError(_("Points to spend must be greater than zero."))
        tx_sudo = self.sudo().create(
            {
                "contract_id": contract.id,
                "tx_type": "spend",
                "points": -points,
                "note": note,
                "source_model": source_model,
                "source_res_id": source_res_id,
                "external_reference": external_reference,
            }
        )
        tx.action_validate()
        return tx

    @api.model
    def adjust_points(self, contract, points, *, note=None):
        contract.ensure_one()
        if not points:
            raise ValidationError(_("Adjustment points cannot be zero."))
        tx_sudo = self.sudo().create(
            {
                "contract_id": contract.id,
                "tx_type": "adjust",
                "points": points,
                "note": note,
            }
        )
        tx.action_validate()
        return tx

    @api.model
    def cron_expire_earned_points(self):
        today = fields.Date.context_today(self)
        earned = self.search(
            [
                ("tx_type", "=", "earn"),
                ("state", "=", "validated"),
                ("expiry_date", "!=", False),
                ("expiry_date", "<", today),
            ],
            order="expiry_date asc, date asc, id asc",
        )
        for earn in earned:
            if self.search_count(
                [
                    ("expired_source_id", "=", earn.id),
                    ("state", "=", "validated"),
                ]
            ):
                continue
            balance = self.get_spendable_balance(earn.contract_id.id)
            amount = min(max(balance, 0.0), max(earn.points, 0.0))
            if amount <= 0:
                continue
            tx = self.create(
                {
                    "contract_id": earn.contract_id.id,
                    "tx_type": "expire",
                    "points": -amount,
                    "expired_source_id": earn.id,
                    "note": _("Automatic expiry of points from %s") % earn.name,
                }
            )
            tx.action_validate()
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

