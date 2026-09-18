


# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MembershipContract(models.Model):
    """Patient/member enrollment and entitlement owner."""

    _name = "membership.contract"
    _description = "Membership Contract"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "membership.workflow.mixin",
        "membership.event.mixin",
    ]
    _order = "state, start_date desc, id desc"

    name = fields.Char(
        string="Contract Reference",
        required=True,
        copy=False,
        index=True,
        default=lambda self: self._next_name(),
        tracking=True,
    )
    plan_id = fields.Many2one(
        "membership.plan",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Member",
        required=True,
        index=True,
        tracking=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        ondelete="restrict",
        index=True,
    )
    referral_id = fields.Many2one(
        "clinic.referral",
        string="Referral / Acquisition Source",
        ondelete="set null",
    )
    user_id = fields.Many2one(
        "res.users", string="Salesperson", default=lambda self: self.env.user
    )
    responsible_id = fields.Many2one(
        "res.users", string="Account Manager", default=lambda self: self.env.user
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("awaiting_payment", "Awaiting Payment"),
            ("active", "Active"),
            ("on_hold", "On Hold"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
            ("renewed", "Renewed"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    start_date = fields.Date(tracking=True)
    end_date = fields.Date(tracking=True)
    next_renewal_date = fields.Date(index=True)
    remaining_days = fields.Integer(compute="_compute_runtime_status")
    is_expired = fields.Boolean(
        compute="_compute_runtime_status",
        search="_search_is_expired",
    )
    duration_human = fields.Char(compute="_compute_duration_human")

    hold_from = fields.Date()
    hold_to = fields.Date()
    total_hold_days = fields.Integer(default=0)
    auto_renew = fields.Boolean(default=False)
    renewal_policy = fields.Selection(
        [("same_plan", "Renew Same Plan"), ("custom_plan", "Renew Custom Plan")],
        default="same_plan",
    )
    renewal_plan_id = fields.Many2one(
        "membership.plan",
        string="Renewal Plan",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    renewed_from_id = fields.Many2one(
        "membership.contract",
        string="Renewed From",
        ondelete="set null",
        readonly=True,
    )
    renewed_to_id = fields.Many2one(
        "membership.contract",
        string="Renewed To",
        ondelete="set null",
        readonly=True,
    )

    list_price = fields.Monetary(currency_field="currency_id", tracking=True)
    join_fee = fields.Monetary(currency_field="currency_id")
    renewal_fee = fields.Monetary(currency_field="currency_id")
    contract_value = fields.Monetary(
        compute="_compute_contract_value",
        store=True,
        currency_field="currency_id",
    )

    invoice_id = fields.Many2one(
        "account.move",
        string="Membership Invoice",
        ondelete="restrict",
        copy=False,
        domain="[('move_type', '=', 'out_invoice'), ('company_id', '=', company_id)]",
    )
    payment_state = fields.Selection(
        related="invoice_id.payment_state", readonly=True
    )

    plan_benefit_ids = fields.One2many(
        related="plan_id.benefit_ids",
        string="Current Plan Benefits",
        readonly=True,
    )
    benefit_snapshot_ids = fields.One2many(
        "membership.contract.benefit",
        "contract_id",
        string="Contract Entitlements",
        readonly=True,
    )
    usage_ids = fields.One2many(
        "membership.usage", "contract_id", string="Usage History", readonly=True
    )
    voucher_ids = fields.One2many(
        "membership.voucher", "contract_id", string="Vouchers", readonly=True
    )
    point_tx_ids = fields.One2many(
        "membership.point.tx", "contract_id", string="Point Ledger", readonly=True
    )
    hold_ids = fields.One2many(
        "membership.hold", "contract_id", string="Hold / Freeze History", readonly=True
    )

    usage_count = fields.Integer(compute="_compute_kpis")
    voucher_count = fields.Integer(compute="_compute_kpis")
    point_tx_count = fields.Integer(compute="_compute_kpis")
    hold_count = fields.Integer(compute="_compute_kpis")
    benefit_count = fields.Integer(compute="_compute_kpis")
    point_balance = fields.Float(compute="_compute_kpis", digits=(16, 2))
    savings_total = fields.Monetary(
        compute="_compute_kpis", currency_field="currency_id"
    )
    active_voucher_count = fields.Integer(compute="_compute_kpis")

    portal_access_token = fields.Char(copy=False)
    notes = fields.Text()

    _reference_company_uniq = models.Constraint(
        "UNIQUE(company_id, name)",
        "Membership contract reference must be unique per company.",
    )
    _commercial_non_negative = models.Constraint(
        "CHECK(list_price >= 0 AND join_fee >= 0 AND renewal_fee >= 0)",
        "Membership contract prices and fees cannot be negative.",
    )
    _hold_days_non_negative = models.Constraint(
        "CHECK(total_hold_days >= 0)",
        "Total hold days cannot be negative.",
    )

    @api.model
    def _next_name(self):
        return self.env["ir.sequence"].next_by_code("membership.contract") or "/"

    @api.depends("list_price", "join_fee", "renewal_fee")
    def _compute_contract_value(self):
        for rec in self:
            rec.contract_value = (
                (rec.list_price or 0.0)
                + (rec.join_fee or 0.0)
                + (rec.renewal_fee or 0.0)
            )

    @api.depends("plan_id.duration_value", "plan_id.duration_unit")
    def _compute_duration_human(self):
        labels = dict(self.env["membership.plan"]._fields["duration_unit"].selection)
        for rec in self:
            rec.duration_human = (
                f"{rec.plan_id.duration_value} {labels.get(rec.plan_id.duration_unit, '')}"
                if rec.plan_id
                else ""
            )

    @api.depends("end_date", "state")
    def _compute_runtime_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_expired = bool(rec.end_date and rec.end_date < today)
            rec.remaining_days = (
                max((rec.end_date - today).days, 0)
                if rec.end_date and rec.state in ("active", "on_hold")
                else 0
            )

    @api.model
    def _search_is_expired(self, operator, value):
        if operator not in ("=", "!="):
            return NotImplemented
        today = fields.Date.context_today(self)
        expired_domain = [("end_date", "<", today)]
        wanted = bool(value)
        if operator == "!=":
            wanted = not wanted
        return expired_domain if wanted else ["|", ("end_date", "=", False), ("end_date", ">=", today)]

    @api.depends(
        "usage_ids.state",
        "usage_ids.discount_amount",
        "voucher_ids.state",
        "point_tx_ids.state",
        "point_tx_ids.points",
        "hold_ids.state",
        "benefit_snapshot_ids.active",
    )
    def _compute_kpis(self):
        for rec in self:
            rec.usage_count = len(rec.usage_ids)
            rec.voucher_count = len(rec.voucher_ids)
            rec.point_tx_count = len(rec.point_tx_ids)
            rec.hold_count = len(rec.hold_ids)
            rec.benefit_count = len(rec.benefit_snapshot_ids)
            rec.point_balance = sum(
                rec.point_tx_ids.filtered(lambda tx: tx.state == "validated").mapped("points")
            )
            rec.savings_total = sum(
                rec.usage_ids.filtered(lambda usage: usage.state == "validated").mapped(
                    "discount_amount"
                )
            )
            rec.active_voucher_count = len(
                rec.voucher_ids.filtered(lambda voucher: voucher.state in ("issued", "reserved"))
            )

    @api.model
    def _compute_end_date_from_plan(self, start_date, plan):
        start_date = fields.Date.to_date(start_date)
        if not start_date or not plan:
            return False
        if plan.duration_unit == "day":
            return start_date + relativedelta(days=plan.duration_value - 1)
        if plan.duration_unit == "month":
            return start_date + relativedelta(months=plan.duration_value, days=-1)
        return start_date + relativedelta(years=plan.duration_value, days=-1)

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        if self.patient_id and self.patient_id.partner_id:
            self.partner_id = self.patient_id.partner_id

    @api.onchange("plan_id")
    def _onchange_plan_id(self):
        if self.plan_id:
            self.currency_id = self.plan_id.currency_id
            self.list_price = self.plan_id.list_price
            self.join_fee = self.plan_id.join_fee
            self.renewal_fee = 0.0
            if not self.start_date:
                self.start_date = fields.Date.context_today(self)
            self.end_date = self._compute_end_date_from_plan(
                self.start_date, self.plan_id
            )

    @api.onchange("start_date", "plan_id")
    def _onchange_start_date(self):
        if self.start_date and self.plan_id:
            self.end_date = self._compute_end_date_from_plan(
                self.start_date, self.plan_id
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "/":
                vals["name"] = self._next_name()
            vals.setdefault("company_id", self.env.company.id)
            plan = self.env["membership.plan"].browse(vals.get("plan_id")).exists()
            if plan:
                vals.setdefault("currency_id", plan.currency_id.id)
                vals.setdefault("list_price", plan.list_price)
                vals.setdefault("join_fee", plan.join_fee)
                vals.setdefault("renewal_fee", 0.0)
                vals.setdefault("start_date", fields.Date.context_today(self))
                if vals.get("start_date") and not vals.get("end_date"):
                    vals["end_date"] = self._compute_end_date_from_plan(
                        vals["start_date"], plan
                    )
            patient = self.env["clinic.patient"].browse(vals.get("patient_id")).exists()
            if patient and patient.partner_id:
                vals.setdefault("partner_id", patient.partner_id.id)
        records = super().create(vals_list)
        return records

    def write(self, vals):
        self._membership_guard_direct_state_write(vals)
        immutable_when_live = {
            "plan_id", "partner_id", "patient_id", "company_id", "currency_id",
            "list_price", "join_fee", "renewal_fee", "start_date",
        }
        if immutable_when_live.intersection(vals) and any(
            rec.state in ("active", "on_hold", "expired", "renewed", "cancelled")
            for rec in self
        ):
            raise UserError(
                _("Commercial identity of a live or historical membership contract is immutable.")
            )
        return super().write(vals)

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(_("End Date cannot be earlier than Start Date."))

    @api.constrains("plan_id", "partner_id", "state")
    def _check_single_active_per_plan(self):
        for rec in self:
            if rec.state not in ("active", "on_hold") or not rec.partner_id:
                continue
            duplicate = self.search_count(
                [
                    ("id", "!=", rec.id),
                    ("company_id", "=", rec.company_id.id),
                    ("partner_id", "=", rec.partner_id.id),
                    ("plan_id", "=", rec.plan_id.id),
                    ("state", "in", ("active", "on_hold")),
                ]
            )
            if duplicate:
                raise ValidationError(
                    _("A member cannot have two simultaneous active/on-hold contracts for the same plan.")
                )

    def _accounting_income_account(self):
        self.ensure_one()
        account = self.plan_id.income_account_id
        if account:
            return account
        product = self.plan_id.product_id
        if product:
            account = (
                product.property_account_income_id
                or product.categ_id.property_account_income_categ_id
            )
        if account:
            return account
        Account = self.env["account.account"].with_company(self.company_id)
        return Account.search(
            [
                *Account._check_company_domain(self.company_id),
                ("account_type", "=", "income"),
            ],
            limit=1,
        )

    def _prepare_invoice_line(self, label, amount):
        self.ensure_one()
        product = self.plan_id.product_id
        account = self._accounting_income_account()
        if not account:
            raise UserError(
                _("Configure an income account on the Membership Plan or its service product.")
            )
        vals = {
            "name": label,
            "quantity": 1.0,
            "price_unit": amount,
            "account_id": account.id,
        }
        if product:
            vals["product_id"] = product.id
            vals["tax_ids"] = [(6, 0, product.taxes_id.ids)]
        if self.plan_id.analytic_account_id:
            vals["analytic_distribution"] = {
                str(self.plan_id.analytic_account_id.id): 100.0
            }
        return vals

    def _prepare_invoice_vals(self):
        self.ensure_one()
        lines = []
        if self.list_price:
            lines.append(
                (0, 0, self._prepare_invoice_line(
                    _("%s - Membership Plan") % self.plan_id.display_name,
                    self.list_price,
                ))
            )
        if self.join_fee:
            lines.append(
                (0, 0, self._prepare_invoice_line(
                    _("%s - Join Fee") % self.plan_id.display_name,
                    self.join_fee,
                ))
            )
        if self.renewal_fee:
            lines.append(
                (0, 0, self._prepare_invoice_line(
                    _("%s - Renewal Fee") % self.plan_id.display_name,
                    self.renewal_fee,
                ))
            )
        if not lines:
            raise UserError(_("This contract has no amount to invoice."))
        return {
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": fields.Date.context_today(self),
            "invoice_origin": self.name,
            "ref": self.name,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "invoice_line_ids": lines,
        }

    def action_create_invoice(self):
        for rec in self:
            if rec.invoice_id:
                raise UserError(_("A membership invoice is already linked."))
            if not rec.partner_id:
                raise UserError(_("Select a Member before creating an invoice."))
            invoice = self.env["account.move"].create(rec._prepare_invoice_vals())
            rec.invoice_id = invoice
            if rec.state == "draft":
                rec._membership_write_state({"state": "awaiting_payment"})
            rec._membership_publish_event(
                "contract.invoice_created",
                {"contract_id": rec.id, "account_move_id": invoice.id},
            )
        return True

    def action_confirm(self):
        for rec in self:
            if rec.state != "draft":
                continue
            if rec.plan_id.state != "active":
                raise UserError(_("Only an Active membership plan can be sold."))
            if rec.contract_value > 0 and not rec.invoice_id:
                rec.action_create_invoice()
            else:
                rec._membership_write_state({"state": "awaiting_payment"})
            rec._membership_publish_event("contract.confirmed", {"contract_id": rec.id})
        return True

    def _build_benefit_snapshot(self):
        Snapshot = self.env["membership.contract.benefit"]
        for rec in self:
            if rec.benefit_snapshot_ids:
                continue
            benefits = rec.plan_id.benefit_ids.filtered("active")
            values = [
                Snapshot.snapshot_values_from_plan_benefit(benefit, rec)
                for benefit in benefits
            ]
            if values:
                Snapshot.sudo().with_context(
                    clinic_membership_snapshot_build=True
                ).create(values)

    def _issue_join_vouchers(self):
        Voucher = self.env["membership.voucher"]
        for rec in self:
            for entitlement in rec.benefit_snapshot_ids.filtered(
                lambda benefit: benefit.benefit_type == "voucher_on_join"
                and benefit.voucher_on_join_qty > 0
            ):
                Voucher.issue_from_entitlement(entitlement)

    def _sync_partner_membership_hints(self):
        """Soft bridge for already-installed downstream billing/wallet modules."""
        for rec in self:
            values = {}
            if "membership_reference" in rec.partner_id._fields:
                values["membership_reference"] = rec.name
            if "membership_level_key" in rec.partner_id._fields:
                values["membership_level_key"] = rec.plan_id.tier or rec.plan_id.code
            if values:
                rec.partner_id.write(values)

    def action_activate(self):
        Config = self.env["membership.config.service"]
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state not in ("draft", "awaiting_payment"):
                raise UserError(_("Only Draft or Awaiting Payment contracts can be activated."))
            if rec.plan_id.state != "active":
                raise UserError(_("The membership plan must be Active."))
            require_paid = Config.get_value(
                "require_paid_before_activation", rec.company_id
            )
            if require_paid and rec.contract_value > 0:
                if not rec.invoice_id:
                    raise UserError(_("Create and pay the membership invoice before activation."))
                if rec.invoice_id.payment_state != "paid":
                    raise UserError(_("The membership invoice must be fully paid before activation."))
            if not rec.start_date:
                rec.start_date = today
            if not rec.end_date:
                rec.end_date = rec._compute_end_date_from_plan(rec.start_date, rec.plan_id)
            rec._build_benefit_snapshot()
            rec._issue_join_vouchers()
            rec._membership_write_state(
                {
                    "state": "active",
                    "next_renewal_date": rec.end_date,
                }
            )
            rec._sync_partner_membership_hints()
            rec._membership_publish_event(
                "contract.activated",
                {
                    "contract_id": rec.id,
                    "plan_id": rec.plan_id.id,
                    "partner_id": rec.partner_id.id,
                    "patient_id": rec.patient_id.id if rec.patient_id else False,
                },
            )
        return True

    def action_set_on_hold(self, date_from=None, date_to=None):
        for rec in self:
            if rec.state != "active":
                raise UserError(_("Only Active contracts can be put on hold."))
            if not rec.plan_id.allow_hold:
                raise UserError(_("This plan does not allow Hold/Freeze."))
            date_from = fields.Date.to_date(date_from or fields.Date.context_today(rec))
            date_to = fields.Date.to_date(date_to or date_from)
            if date_to < date_from:
                raise ValidationError(_("Hold To cannot be earlier than Hold From."))
            days = (date_to - date_from).days + 1
            if (
                rec.plan_id.max_hold_days_per_term
                and rec.total_hold_days + days > rec.plan_id.max_hold_days_per_term
            ):
                raise UserError(_("The plan's maximum hold days would be exceeded."))
            values = {
                "state": "on_hold",
                "hold_from": date_from,
                "hold_to": date_to,
                "total_hold_days": rec.total_hold_days + days,
            }
            if rec.end_date:
                values["end_date"] = rec.end_date + relativedelta(days=days)
            rec._membership_write_state(values)
            rec._membership_publish_event(
                "contract.on_hold",
                {"contract_id": rec.id, "days": days},
            )
        return True

    def action_resume(self):
        for rec in self:
            if rec.state != "on_hold":
                raise UserError(_("Only On Hold contracts can be resumed."))
            rec._membership_write_state(
                {"state": "active", "hold_from": False, "hold_to": False}
            )
            rec._membership_publish_event("contract.resumed", {"contract_id": rec.id})
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state in ("cancelled", "renewed"):
                continue
            rec._membership_write_state({"state": "cancelled"})
            rec._membership_publish_event("contract.cancelled", {"contract_id": rec.id})
        return True

    def action_expire(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if (
                rec.state in ("active", "on_hold")
                and rec.end_date
                and rec.end_date < today
            ):
                rec._membership_write_state({"state": "expired"})
                rec._membership_publish_event(
                    "contract.expired", {"contract_id": rec.id}
                )
        return True

    def action_open_renew_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Renew Membership"),
            "res_model": "membership.contract.renew.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_id": self.id},
        }

    def get_applicable_entitlements(
        self, treatment=None, product=None, doctor=None, qty=1.0, unit_price=0.0, at_datetime=None
    ):
        self.ensure_one()
        if self.state != "active" or self.is_expired:
            return self.env["membership.contract.benefit"]
        return self.benefit_snapshot_ids.filtered(
            lambda entitlement: entitlement.is_scope_applicable(
                treatment=treatment,
                product=product,
                doctor=doctor,
                qty=qty,
                unit_price=unit_price,
                at_datetime=at_datetime,
            )
        ).sorted(key=lambda benefit: (benefit.sequence, -benefit.priority_order, benefit.id))

    @api.model
    def find_active_contract(self, partner, company=None, at_date=None):
        if not partner:
            return self.browse()
        company = company or self.env.company
        at_date = fields.Date.to_date(at_date or fields.Date.context_today(self))
        return self.search(
            [
                ("partner_id", "=", partner.id),
                ("company_id", "=", company.id),
                ("state", "=", "active"),
                "|",
                ("start_date", "=", False),
                ("start_date", "<=", at_date),
                "|",
                ("end_date", "=", False),
                ("end_date", ">=", at_date),
            ],
            order="plan_id, start_date desc, id desc",
            limit=1,
        )

    @api.model
    def cron_expire_contracts(self):
        companies = self.env["res.company"].search([])
        Config = self.env["membership.config.service"]
        for company in companies:
            if not Config.get_value("auto_expire_contracts", company):
                continue
            contracts = self.with_company(company).search(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", ("active", "on_hold")),
                    ("end_date", "<", fields.Date.context_today(self)),
                ]
            )
            contracts.action_expire()
        return True

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No accounting invoice is linked to this contract."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Invoice"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
        }

    def _action_related(self, model, domain, name, context=None):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "list,form",
            "domain": domain,
            "context": context or {},
        }

    def action_open_entitlements(self):
        return self._action_related(
            "membership.contract.benefit",
            [("contract_id", "=", self.id)],
            _("Membership Entitlements"),
        )

    def action_open_usages(self):
        return self._action_related(
            "membership.usage",
            [("contract_id", "=", self.id)],
            _("Membership Usage"),
            {"default_contract_id": self.id},
        )

    def action_open_vouchers(self):
        return self._action_related(
            "membership.voucher",
            [("contract_id", "=", self.id)],
            _("Membership Vouchers"),
            {"default_contract_id": self.id},
        )

    def action_open_points(self):
        return self._action_related(
            "membership.point.tx",
            [("contract_id", "=", self.id)],
            _("Membership Point Ledger"),
            {"default_contract_id": self.id},
        )

    def action_open_holds(self):
        return self._action_related(
            "membership.hold",
            [("contract_id", "=", self.id)],
            _("Membership Hold History"),
            {"default_contract_id": self.id},
        )

    def action_open_hold_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Request Hold / Freeze"),
            "res_model": "membership.hold.request.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_id": self.id},
        }

    def action_open_point_adjust_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Adjust Loyalty Points"),
            "res_model": "membership.point.adjust.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_id": self.id},
        }


