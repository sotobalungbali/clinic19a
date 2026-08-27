
# -*- coding: utf-8 -*-
"""Patient package allocations (contracts) and immutable benefit snapshots."""

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class ClinicPackageAllocation(models.Model):
    _name = "clinic.package.allocation"
    _description = "Clinic Package Allocation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Allocation Number", required=True, readonly=True, copy=False, default="/", index=True
    )
    code = fields.Char(string="External Reference", index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )

    package_id = fields.Many2one(
        "clinic.package", required=True, ondelete="restrict", index=True, tracking=True, check_company=True
    )
    patient_id = fields.Many2one(
        "clinic.patient", required=True, ondelete="restrict", index=True, tracking=True, check_company=True
    )
    partner_id = fields.Many2one(
        "res.partner", string="Customer / Contact", ondelete="restrict", index=True, tracking=True
    )
    doctor_id = fields.Many2one(
        "clinic.doctor", string="Responsible Doctor", ondelete="set null", tracking=True, check_company=True
    )
    branch_id = fields.Many2one(
        "clinic.branch", string="Branch / Outlet", ondelete="restrict", tracking=True, check_company=True
    )
    care_plan_id = fields.Many2one(
        "clinic.care.plan", string="Care Plan", ondelete="set null", tracking=True, check_company=True
    )
    sold_by_user_id = fields.Many2one(
        "res.users", default=lambda self: self.env.user, tracking=True, string="Sold By"
    )

    sale_order_id = fields.Many2one("sale.order", string="Sales Order", ondelete="set null", check_company=True)
    invoice_id = fields.Many2one("account.move", string="Invoice / Receipt", ondelete="set null", check_company=True)
    booking_id = fields.Many2one("booking.booking", string="Initial Booking", ondelete="set null", check_company=True)
    source_voucher_id = fields.Many2one("clinic.package.voucher", ondelete="set null")

    qty = fields.Float(default=1.0, required=True)
    start_date = fields.Date(tracking=True)
    valid_from = fields.Date(tracking=True)
    valid_to = fields.Date(string="Original Expiry", tracking=True)
    valid_to_effective = fields.Date(compute="_compute_effective_expiry", store=True)

    pause_days_accum = fields.Integer(default=0, readonly=True)
    paused_since = fields.Date(readonly=True)
    last_resumed_on = fields.Date(readonly=True)
    pause_count = fields.Integer(default=0, readonly=True)
    transfer_count = fields.Integer(default=0, readonly=True)
    last_transfer_on = fields.Datetime(readonly=True)
    transfer_fee_due = fields.Monetary(readonly=True)

    list_price_unit = fields.Monetary(readonly=True)
    price_total = fields.Monetary(readonly=True, tracking=True)
    discount_amount = fields.Monetary(readonly=True)
    discount_pct = fields.Float(readonly=True)

    line_ids = fields.One2many(
        "clinic.package.allocation.line", "allocation_id", string="Benefit Snapshot", copy=False
    )
    usage_ids = fields.One2many(
        "clinic.package.usage", "allocation_id", string="Redemption History", readonly=True, copy=False
    )
    usage_count = fields.Integer(compute="_compute_usage_count")
    remaining_percent = fields.Float(compute="_compute_remaining", string="Remaining %")
    remaining_value = fields.Monetary(compute="_compute_remaining")
    remaining_summary = fields.Char(compute="_compute_remaining")
    is_expired = fields.Boolean(compute="_compute_is_expired", search="_search_is_expired")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("paused", "Paused"),
            ("expired", "Expired"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
            ("refunded", "Refunded"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    note = fields.Text()
    internal_note = fields.Text()

    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "Allocation number must be unique per company.",
    )
    _qty_positive = models.Constraint(
        "CHECK(qty > 0)",
        "Allocation quantity must be greater than zero.",
    )
    _pause_counters_nonnegative = models.Constraint(
        "CHECK(pause_days_accum >= 0 AND pause_count >= 0 AND transfer_count >= 0 AND transfer_fee_due >= 0)",
        "Allocation counters and transfer fee cannot be negative.",
    )

    @api.depends("valid_to", "pause_days_accum", "package_id.policy_id.max_pause_days")
    def _compute_effective_expiry(self):
        for record in self:
            if not record.valid_to:
                record.valid_to_effective = False
                continue
            cap = record.package_id.policy_id.max_pause_days if record.package_id.policy_id else 0
            extra_days = min(record.pause_days_accum, cap) if cap else record.pause_days_accum
            record.valid_to_effective = record.valid_to + timedelta(days=extra_days)

    def _compute_usage_count(self):
        Usage = self.env["clinic.package.usage"]
        for record in self:
            record.usage_count = Usage.search_count([("allocation_id", "=", record.id)])

    def _compute_remaining(self):
        for record in self:
            ratios = []
            value = 0.0
            summary = []
            for line in record.line_ids:
                total = line.credit_amount_total if line.line_type == "credit" else line.qty_total
                remaining = line.remaining_credit if line.line_type == "credit" else line.remaining_qty
                if line.line_type in ("treatment", "product", "credit") and total:
                    ratios.append(max(min(remaining / total, 1.0), 0.0))
                if line.line_type == "credit":
                    value += line.remaining_credit
                elif line.line_type in ("treatment", "product"):
                    value += line.remaining_qty * line.list_price
                if line.line_type == "credit":
                    summary.append(_("%(name)s: %(amount).2f credit", name=line.name, amount=line.remaining_credit))
                elif line.line_type in ("treatment", "product"):
                    summary.append(_("%(name)s: %(qty).2f left", name=line.name, qty=line.remaining_qty))
            record.remaining_percent = (sum(ratios) / len(ratios) * 100.0) if ratios else 0.0
            record.remaining_value = value
            record.remaining_summary = "; ".join(summary) if summary else _("No consumable benefits")

    @api.depends("valid_to_effective", "state")
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_expired = bool(
                record.valid_to_effective
                and record.valid_to_effective < today
                and record.state in ("active", "paused", "expired")
            )

    def _search_is_expired(self, operator, value):
        today = fields.Date.context_today(self)
        if (operator in ("=", "==") and value) or (operator == "!=" and not value):
            return [("valid_to_effective", "<", today), ("state", "in", ["active", "paused", "expired"])]
        return ["|", ("valid_to_effective", ">=", today), ("valid_to_effective", "=", False)]

    @api.constrains("start_date", "valid_from", "valid_to")
    def _check_dates(self):
        for record in self:
            if record.valid_from and record.start_date and record.valid_from < record.start_date:
                raise ValidationError(_("Valid From cannot be before Start Date."))
            if record.valid_to and record.start_date and record.valid_to < record.start_date:
                raise ValidationError(_("Original Expiry cannot be before Start Date."))

    @api.constrains("patient_id", "partner_id")
    def _check_patient_partner(self):
        for record in self:
            if record.patient_id.partner_id and record.partner_id and record.patient_id.partner_id != record.partner_id:
                raise ValidationError(_("Customer / Contact must match the selected patient's linked contact."))

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        for record in self:
            if record.patient_id and record.patient_id.partner_id:
                record.partner_id = record.patient_id.partner_id

    @api.onchange("package_id", "qty")
    def _onchange_package_pricing(self):
        for record in self:
            if not record.package_id:
                continue
            record.list_price_unit = record.package_id.list_price
            profile = record.package_id.pricing_id
            if profile:
                result = profile.compute_package_price(
                    record.package_id, record.partner_id, record.qty, fields.Date.context_today(record), "frontdesk"
                )
                record.price_total = result["final_total"]
                record.discount_amount = result["discount_amount"]
                record.discount_pct = result["discount_pct"]
            else:
                record.price_total = record.package_id.list_price * record.qty
                record.discount_amount = 0.0
                record.discount_pct = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("state", "draft") != "draft" and not self.env.context.get("clinic_package_state_change"):
                raise UserError(_("Allocations must be created in Draft and activated through the approved action."))
            vals.setdefault("company_id", self.env.company.id)
            if vals.get("name") in (False, "/", None):
                vals["name"] = sequence.next_by_code("clinic.package.allocation") or "/"
            patient = self.env["clinic.patient"].browse(vals.get("patient_id")) if vals.get("patient_id") else False
            if patient and patient.partner_id and not vals.get("partner_id"):
                vals["partner_id"] = patient.partner_id.id
        records = super().create(vals_list)
        records._refresh_price_snapshot()
        return records

    def write(self, vals):
        if "state" in vals and not self.env.context.get("clinic_package_state_change"):
            raise UserError(_("Allocation status can only be changed through workflow actions."))
        immutable_fields = {"package_id", "patient_id", "qty", "company_id"}
        protected_changes = immutable_fields.intersection(vals)
        if protected_changes and any(record.state != "draft" for record in self):
            transfer_only = (
                protected_changes == {"patient_id"}
                and self.env.context.get("clinic_package_authorized_transfer")
            )
            if not transfer_only:
                raise UserError(_("Package, patient, quantity, and company are locked after activation."))
        result = super().write(vals)
        if {"package_id", "partner_id", "qty"}.intersection(vals) and all(record.state == "draft" for record in self):
            self._refresh_price_snapshot()
        return result

    def unlink(self):
        if any(record.state not in ("draft", "cancelled") for record in self):
            raise UserError(_("Only Draft or Cancelled allocations can be deleted."))
        return super().unlink()

    def _refresh_price_snapshot(self):
        for record in self.filtered("package_id"):
            profile = record.package_id.pricing_id
            if profile:
                result = profile.compute_package_price(
                    record.package_id,
                    record.partner_id,
                    record.qty,
                    fields.Date.context_today(record),
                    "frontdesk",
                )
            else:
                base_total = record.package_id.list_price * record.qty
                result = {
                    "base_unit_price": record.package_id.list_price,
                    "final_total": base_total,
                    "discount_amount": 0.0,
                    "discount_pct": 0.0,
                }
            super(ClinicPackageAllocation, record).write(
                {
                    "list_price_unit": result["base_unit_price"],
                    "price_total": result["final_total"],
                    "discount_amount": result["discount_amount"],
                    "discount_pct": result["discount_pct"],
                }
            )

    def _prepare_snapshot_lines(self):
        self.ensure_one()
        return [
            (0, 0, line._prepare_allocation_line_vals(self))
            for line in self.package_id.line_ids.filtered("active")
        ]

    def _ensure_ready_to_activate(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only Draft allocations can be activated."))
        if self.package_id.state != "active":
            raise UserError(_("Only an Active package can be allocated."))
        if not self.patient_id:
            raise UserError(_("A patient is required before activation."))
        if not self.partner_id and self.patient_id.partner_id:
            self.partner_id = self.patient_id.partner_id
        if not self.package_id.line_ids.filtered("active"):
            raise UserError(_("The package has no active component lines."))

    def action_activate(self):
        for record in self:
            record._ensure_ready_to_activate()
            start = record.start_date or fields.Date.context_today(record)
            values = {
                "start_date": start,
                "valid_from": record.valid_from or start,
                "valid_to": record.valid_to or record.package_id._get_expiry_date(start),
                "state": "active",
            }
            if not record.line_ids:
                values["line_ids"] = record._prepare_snapshot_lines()
            record.with_context(clinic_package_state_change=True, clinic_package_snapshot_build=True).write(values)
            record._refresh_price_snapshot()
            record._enqueue_integration_event("allocation.activated")
        return True

    def action_pause(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state != "active":
                raise UserError(_("Only Active allocations can be paused."))
            if record.package_id.policy_id:
                record.package_id.policy_id.validate_pause(record)
            record.with_context(clinic_package_state_change=True).write({"state": "paused", "paused_since": today, "pause_count": record.pause_count + 1})
            record._enqueue_integration_event("allocation.paused")
        return True

    def action_resume(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state != "paused":
                raise UserError(_("Only Paused allocations can be resumed."))
            days = max((today - record.paused_since).days, 0) if record.paused_since else 0
            record.with_context(clinic_package_state_change=True).write(
                {
                    "state": "active",
                    "pause_days_accum": record.pause_days_accum + days,
                    "paused_since": False,
                    "last_resumed_on": today,
                }
            )
            record._enqueue_integration_event("allocation.resumed", {"pause_days": days})
        return True

    def action_close(self):
        for record in self:
            if record.state not in ("active", "paused", "expired"):
                raise UserError(_("Only Active, Paused, or Expired allocations can be closed."))
            record.with_context(clinic_package_state_change=True).write({"state": "closed"})
            record._enqueue_integration_event("allocation.closed")
        return True

    def action_cancel(self):
        for record in self:
            if record.state not in ("draft", "active", "paused"):
                raise UserError(_("This allocation cannot be cancelled from its current status."))
            if record.usage_ids.filtered(lambda usage: usage.state == "confirmed"):
                raise UserError(_("Cancel confirmed redemptions before cancelling this allocation."))
            record.with_context(clinic_package_state_change=True).write({"state": "cancelled"})
            record._enqueue_integration_event("allocation.cancelled")
        return True

    def action_mark_refunded(self):
        for record in self:
            if record.state not in ("active", "paused", "expired", "closed"):
                raise UserError(_("This allocation cannot be marked refunded from its current status."))
            if not record.package_id.policy_id or not record.package_id.policy_id.allow_refund:
                raise UserError(_("The package policy does not allow refunds."))
            record.with_context(clinic_package_state_change=True).write({"state": "refunded"})
            record._enqueue_integration_event("allocation.refunded", {"remaining_value": record.remaining_value})
        return True

    def action_reset_to_draft(self):
        for record in self:
            if record.state != "cancelled":
                raise UserError(_("Only Cancelled allocations can be reset to Draft."))
            if record.usage_ids:
                raise UserError(_("Allocations with redemption history cannot be reset to Draft."))
            record.with_context(clinic_package_state_change=True).write({"state": "draft", "line_ids": [(5, 0, 0)]})
        return True

    def action_open_redeem_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Redeem Package Benefit"),
            "res_model": "clinic.package.redeem.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_allocation_id": self.id},
        }

    def action_open_transfer_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Transfer Package"),
            "res_model": "clinic.package.transfer.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_allocation_id": self.id},
        }

    def action_create_care_plan(self):
        self.ensure_one()
        if self.care_plan_id:
            return self.action_view_care_plan()
        care_plan = self.env["clinic.care.plan"].create(
            {
                "display_name": _("%(package)s — %(patient)s", package=self.package_id.name, patient=self.patient_id.display_name),
                "patient_id": self.patient_id.id,
                "doctor_id": self.doctor_id.id,
                "start_date": self.start_date or fields.Date.context_today(self),
                "company_id": self.company_id.id,
                "package_allocation_id": self.id,
            }
        )
        self.care_plan_id = care_plan
        return self.action_view_care_plan()

    def action_view_care_plan(self):
        self.ensure_one()
        if not self.care_plan_id:
            raise UserError(_("No care plan is linked to this allocation."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Care Plan"),
            "res_model": "clinic.care.plan",
            "view_mode": "form",
            "res_id": self.care_plan_id.id,
        }

    def action_view_usages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Redemption History"),
            "res_model": "clinic.package.usage",
            "view_mode": "list,form",
            "domain": [("allocation_id", "=", self.id)],
            "context": {"default_allocation_id": self.id},
        }

    def _transfer_to_patient(self, target_patient, note=False):
        self.ensure_one()
        if self.state not in ("active", "paused"):
            raise UserError(_("Only Active or Paused allocations can be transferred."))
        policy = self.package_id.policy_id
        if not policy:
            raise UserError(_("A package policy is required for transfer."))
        policy.validate_transfer(self, target_patient)
        previous_patient = self.patient_id
        fee = policy.compute_transfer_fee(self)
        self.with_context(clinic_package_authorized_transfer=True).write(
            {
                "patient_id": target_patient.id,
                "partner_id": target_patient.partner_id.id or False,
                "transfer_count": self.transfer_count + 1,
                "last_transfer_on": fields.Datetime.now(),
                "transfer_fee_due": fee,
                "internal_note": (self.internal_note or "") + ("\n" + note if note else ""),
            }
        )
        self._enqueue_integration_event(
            "allocation.transferred",
            {
                "from_patient_id": previous_patient.id,
                "to_patient_id": target_patient.id,
                "transfer_fee_due": fee,
            },
        )
        return True

    @api.model
    def _cron_expire_allocations(self):
        today = fields.Date.context_today(self)
        companies = self.env["res.company"].sudo().search([]).filtered(
            lambda company: company.clinic_pkg_auto_expire_allocations
        )
        records = self.sudo().search(
            [
                ("company_id", "in", companies.ids),
                ("state", "in", ["active", "paused"]),
                ("valid_to_effective", "<", today),
            ]
        )
        if records:
            records.with_context(clinic_package_state_change=True).write({"state": "expired"})
            for record in records:
                record._enqueue_integration_event("allocation.expired")
        return True

    def _enqueue_integration_event(self, event_code, payload=None):
        self.ensure_one()
        return self.env["clinic.package.integration.event"].enqueue(event_code, self, payload=payload)


class ClinicPackageAllocationLine(models.Model):
    _name = "clinic.package.allocation.line"
    _description = "Clinic Package Allocation Benefit Snapshot"
    _order = "allocation_id, sequence, id"
    _check_company_auto = True

    allocation_id = fields.Many2one(
        "clinic.package.allocation", required=True, ondelete="cascade", index=True, check_company=True
    )
    package_id = fields.Many2one(
        "clinic.package", related="allocation_id.package_id", store=True, readonly=True, index=True
    )
    package_line_id = fields.Many2one("clinic.package.line", ondelete="set null", index=True)
    benefit_id = fields.Many2one("clinic.package.benefit", ondelete="set null")
    company_id = fields.Many2one(
        "res.company", related="allocation_id.company_id", store=True, readonly=True, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="allocation_id.currency_id", store=True, readonly=True
    )
    patient_id = fields.Many2one(
        "clinic.patient", related="allocation_id.patient_id", store=True, readonly=True, index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    line_type = fields.Selection(
        [
            ("treatment", "Treatment Sessions"),
            ("product", "Product Quantity"),
            ("credit", "Monetary Credit"),
            ("discount", "Discount Benefit"),
        ],
        required=True,
        index=True,
    )
    treatment_id = fields.Many2one("clinic.treatment", ondelete="restrict", check_company=True)
    treatment_categ_id = fields.Many2one("clinic.treatment.category", ondelete="restrict")
    product_id = fields.Many2one("product.product", ondelete="restrict", check_company=True)
    product_categ_id = fields.Many2one("product.category", ondelete="restrict")
    apply_to_all_treatments = fields.Boolean(default=False)
    apply_to_all_products = fields.Boolean(default=False)
    qty_total = fields.Float(default=0.0)
    qty_redeemed = fields.Float(compute="_compute_consumption", store=True, readonly=True)
    remaining_qty = fields.Float(compute="_compute_consumption", store=True, readonly=True)
    uom_id = fields.Many2one("uom.uom")
    consume_per_use = fields.Float(default=1.0)
    credit_amount_total = fields.Monetary(default=0.0)
    credit_redeemed = fields.Monetary(compute="_compute_consumption", store=True, readonly=True)
    remaining_credit = fields.Monetary(compute="_compute_consumption", store=True, readonly=True)
    discount_type = fields.Selection([("percent", "Percentage"), ("fixed", "Fixed Amount")])
    discount_value = fields.Float(default=0.0)
    discount_max_amount = fields.Monetary(default=0.0)
    allowed_doctor_ids = fields.Many2many(
        "clinic.doctor",
        "clinic_package_alloc_line_doctor_rel",
        "allocation_line_id",
        "doctor_id",
        check_company=True,
    )
    allowed_room_ids = fields.Many2many(
        "clinic.room",
        "clinic_package_alloc_line_room_rel",
        "allocation_line_id",
        "room_id",
        check_company=True,
    )
    allowed_device_ids = fields.Many2many(
        "clinic.device",
        "clinic_package_alloc_line_device_rel",
        "allocation_line_id",
        "device_id",
        check_company=True,
    )
    limit_per_visit = fields.Float(default=0.0)
    limit_per_day = fields.Float(default=0.0)
    cooldown_days = fields.Integer(default=0)
    list_price = fields.Monetary(default=0.0)
    cost_price = fields.Monetary(default=0.0)

    # Redemption history is the authoritative source for consumption balances.
    # Keeping these aggregates stored makes them safe for Odoo domains/searches
    # while @api.depends below guarantees automatic recomputation whenever a
    # redemption is confirmed, cancelled, reset, or its amount changes in Draft.
    usage_ids = fields.One2many(
        "clinic.package.usage",
        "allocation_line_id",
        string="Redemption History",
        readonly=True,
        copy=False,
    )
    is_depleted = fields.Boolean(compute="_compute_consumption", store=True, readonly=True, index=True)
    usage_count = fields.Integer(compute="_compute_consumption", store=True, readonly=True)
    note = fields.Text()

    _nonnegative_snapshot_values = models.Constraint(
        "CHECK(qty_total >= 0 AND consume_per_use >= 0 AND credit_amount_total >= 0 "
        "AND discount_value >= 0 AND discount_max_amount >= 0 AND limit_per_visit >= 0 "
        "AND limit_per_day >= 0 AND cooldown_days >= 0 AND list_price >= 0 AND cost_price >= 0)",
        "Allocation snapshot quantities, limits, discounts, and prices must be zero or positive.",
    )

    @api.depends(
        "line_type",
        "qty_total",
        "credit_amount_total",
        "currency_id.rounding",
        "usage_ids.state",
        "usage_ids.qty_used",
        "usage_ids.credit_used",
    )
    def _compute_consumption(self):
        for record in self:
            usages = record.usage_ids.filtered(lambda usage: usage.state == "confirmed")
            qty = sum(usages.mapped("qty_used"))
            credit = sum(usages.mapped("credit_used"))
            record.qty_redeemed = qty
            record.credit_redeemed = credit
            record.remaining_qty = max(record.qty_total - qty, 0.0)
            record.remaining_credit = max(record.credit_amount_total - credit, 0.0)
            record.usage_count = len(usages)
            if record.line_type == "credit":
                record.is_depleted = bool(record.credit_amount_total) and float_compare(
                    record.remaining_credit, 0.0, precision_rounding=record.currency_id.rounding
                ) <= 0
            elif record.line_type in ("treatment", "product"):
                record.is_depleted = bool(record.qty_total) and float_compare(
                    record.remaining_qty, 0.0, precision_digits=4
                ) <= 0
            else:
                record.is_depleted = False

    def check_redeem_constraints(self, qty_used=0.0, credit_used=0.0, doctor=False, room=False, device=False):
        self.ensure_one()
        allocation = self.allocation_id
        allowed_states = ["active"] + (["paused"] if allocation.package_id.allow_usage_when_paused else [])
        if allocation.state not in allowed_states:
            raise UserError(_("This package allocation is not currently redeemable."))
        if allocation.is_expired:
            raise UserError(_("This package allocation has expired."))
        if self.is_depleted:
            raise UserError(_("This benefit is fully consumed."))
        if self.allowed_doctor_ids and not doctor:
            raise UserError(_("Select a doctor because this benefit restricts eligible doctors."))
        if self.allowed_doctor_ids and doctor not in self.allowed_doctor_ids:
            raise UserError(_("The selected doctor is not allowed for this benefit."))
        if self.allowed_room_ids and not room:
            raise UserError(_("Select a room because this benefit restricts eligible rooms."))
        if self.allowed_room_ids and room not in self.allowed_room_ids:
            raise UserError(_("The selected room is not allowed for this benefit."))
        if self.allowed_device_ids and not device:
            raise UserError(_("Select a device because this benefit restricts eligible devices."))
        if self.allowed_device_ids and device not in self.allowed_device_ids:
            raise UserError(_("The selected device is not allowed for this benefit."))
        if self.line_type == "credit":
            if credit_used <= 0:
                raise UserError(_("Credit redemption must be greater than zero."))
            if float_compare(credit_used, self.remaining_credit, precision_rounding=self.currency_id.rounding) > 0:
                raise UserError(_("Credit redemption exceeds the remaining package credit."))
        elif self.line_type in ("treatment", "product"):
            if qty_used <= 0:
                raise UserError(_("Redemption quantity must be greater than zero."))
            if float_compare(qty_used, self.remaining_qty, precision_digits=4) > 0:
                raise UserError(_("Redemption quantity exceeds the remaining package benefit."))
            if self.limit_per_visit and qty_used > self.limit_per_visit:
                raise UserError(_("Redemption quantity exceeds the per-visit limit."))
        else:
            raise UserError(_("Discount-only lines are applied commercially and cannot be redeemed directly."))
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("clinic_package_snapshot_build"):
            raise UserError(_("Allocation benefit snapshots are generated only by package activation."))
        return super().create(vals_list)

    def write(self, vals):
        if any(line.allocation_id.state != "draft" for line in self):
            raise UserError(_("Activated package benefit snapshots are immutable."))
        return super().write(vals)

    def unlink(self):
        if any(line.allocation_id.state not in ("draft", "cancelled") for line in self):
            raise UserError(_("Only Draft or Cancelled allocation benefit snapshots can be deleted."))
        return super().unlink()

    def action_redeem(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Redeem Benefit"),
            "res_model": "clinic.package.redeem.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_allocation_id": self.allocation_id.id,
                "default_allocation_line_id": self.id,
            },
        }

    def action_create_booking(self):
        self.ensure_one()
        if self.line_type != "treatment" or not self.treatment_id:
            raise UserError(_("Only a specific treatment benefit can prefill a booking."))
        partner = self.allocation_id.partner_id or self.allocation_id.patient_id.partner_id
        if not partner:
            raise UserError(_("The patient needs a linked contact before creating a booking."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Schedule Package Treatment"),
            "res_model": "booking.booking",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_patient_id": partner.id,
                "default_doctor_id": self.allocation_id.doctor_id.id,
                "default_treatment_id": self.treatment_id.id,
                "default_package_allocation_id": self.allocation_id.id,
                "default_package_allocation_line_id": self.id,
            },
        }
