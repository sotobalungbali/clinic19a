
# -*- coding: utf-8 -*-
"""Redemption ledger for package benefits."""

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicPackageUsage(models.Model):
    _name = "clinic.package.usage"
    _description = "Clinic Package Redemption"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "redeem_datetime desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True, copy=False, default="/", index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )

    allocation_id = fields.Many2one(
        "clinic.package.allocation", required=True, ondelete="restrict", index=True, tracking=True, check_company=True
    )
    allocation_line_id = fields.Many2one(
        "clinic.package.allocation.line", required=True, ondelete="restrict", index=True, tracking=True, check_company=True
    )
    package_id = fields.Many2one(
        "clinic.package", related="allocation_id.package_id", store=True, readonly=True, index=True
    )
    package_line_id = fields.Many2one(
        "clinic.package.line", related="allocation_line_id.package_line_id", store=True, readonly=True, index=True
    )
    patient_id = fields.Many2one(
        "clinic.patient", related="allocation_id.patient_id", store=True, readonly=True, index=True
    )
    partner_id = fields.Many2one(
        "res.partner", related="allocation_id.partner_id", store=True, readonly=True, index=True
    )
    doctor_id = fields.Many2one("clinic.doctor", ondelete="set null", check_company=True, tracking=True)
    booking_id = fields.Many2one("booking.booking", ondelete="set null", check_company=True, tracking=True)
    care_plan_line_id = fields.Many2one("clinic.care.plan.line", ondelete="set null", check_company=True)
    care_plan_id = fields.Many2one(
        "clinic.care.plan", related="care_plan_line_id.plan_id", store=True, readonly=True, index=True
    )
    visit_id = fields.Many2one("clinic.queue.visit", ondelete="set null", check_company=True)
    room_id = fields.Many2one("clinic.room", ondelete="set null", check_company=True)
    device_id = fields.Many2one("clinic.device", ondelete="set null", check_company=True)
    sale_order_id = fields.Many2one("sale.order", ondelete="set null", check_company=True)
    invoice_id = fields.Many2one("account.move", ondelete="set null", check_company=True)

    line_type = fields.Selection(related="allocation_line_id.line_type", store=True, readonly=True)
    redeem_datetime = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True, index=True)
    redeem_date = fields.Date(compute="_compute_redeem_date", store=True, index=True)
    qty_used = fields.Float(default=0.0, tracking=True)
    credit_used = fields.Monetary(default=0.0, tracking=True)
    uom_id = fields.Many2one("uom.uom", related="allocation_line_id.uom_id", store=True, readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("cancelled", "Cancelled")],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    note = fields.Text()
    internal_note = fields.Text()

    _usage_values_nonnegative = models.Constraint(
        "CHECK(qty_used >= 0 AND credit_used >= 0)",
        "Redemption quantity and credit cannot be negative.",
    )

    @api.depends("redeem_datetime")
    def _compute_redeem_date(self):
        for record in self:
            record.redeem_date = fields.Date.to_date(record.redeem_datetime) if record.redeem_datetime else False

    @api.constrains("allocation_id", "allocation_line_id")
    def _check_line_belongs_to_allocation(self):
        for record in self:
            if record.allocation_line_id.allocation_id != record.allocation_id:
                raise ValidationError(_("The selected benefit line does not belong to the allocation."))

    @api.onchange("allocation_id")
    def _onchange_allocation_id(self):
        for record in self:
            if record.allocation_id:
                record.doctor_id = record.allocation_id.doctor_id
                if record.allocation_line_id.allocation_id != record.allocation_id:
                    record.allocation_line_id = False

    @api.onchange("allocation_line_id")
    def _onchange_allocation_line_id(self):
        for record in self:
            line = record.allocation_line_id
            if not line:
                continue
            if line.line_type == "credit":
                record.credit_used = min(line.remaining_credit, line.credit_amount_total)
                record.qty_used = 0.0
            elif line.line_type in ("treatment", "product"):
                default_qty = line.consume_per_use or 1.0
                record.qty_used = min(default_qty, line.remaining_qty)
                record.credit_used = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("state", "draft") != "draft" and not self.env.context.get("clinic_package_state_change"):
                raise UserError(_("Redemptions must be created in Draft and confirmed through the approved action."))
            vals.setdefault("company_id", self.env.company.id)
            if vals.get("name") in (False, "/", None):
                vals["name"] = sequence.next_by_code("clinic.package.usage") or "/"
            if vals.get("allocation_id"):
                allocation = self.env["clinic.package.allocation"].browse(vals["allocation_id"])
                vals.setdefault("company_id", allocation.company_id.id)
                vals.setdefault("doctor_id", allocation.doctor_id.id)
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals and not self.env.context.get("clinic_package_state_change"):
            raise UserError(_("Redemption status can only be changed through workflow actions."))
        protected = {
            "allocation_id",
            "allocation_line_id",
            "qty_used",
            "credit_used",
            "redeem_datetime",
            "doctor_id",
            "booking_id",
            "visit_id",
            "room_id",
            "device_id",
            "emar_order_id",
            "emar_schedule_id",
            "emar_administration_id",
        }
        if protected.intersection(vals) and any(record.state != "draft" for record in self):
            raise UserError(_("Confirmed or Cancelled redemptions are immutable. Cancel and create a correction instead."))
        return super().write(vals)

    def unlink(self):
        if any(record.state != "draft" for record in self):
            raise UserError(_("Only Draft redemptions can be deleted."))
        return super().unlink()

    def _validate_daily_limits(self):
        self.ensure_one()
        line = self.allocation_line_id
        if not self.redeem_date:
            return True
        confirmed_domain = [
            ("id", "!=", self.id),
            ("allocation_line_id", "=", line.id),
            ("state", "=", "confirmed"),
            ("redeem_date", "=", self.redeem_date),
        ]
        if line.limit_per_day:
            existing = sum(self.search(confirmed_domain).mapped("qty_used"))
            if existing + self.qty_used > line.limit_per_day:
                raise UserError(_("This redemption would exceed the configured per-day limit."))
        if line.cooldown_days:
            previous = self.search(
                [
                    ("id", "!=", self.id),
                    ("allocation_line_id", "=", line.id),
                    ("state", "=", "confirmed"),
                    ("redeem_datetime", "<", self.redeem_datetime),
                ],
                order="redeem_datetime desc",
                limit=1,
            )
            if previous and previous.redeem_date:
                next_allowed = previous.redeem_date + timedelta(days=line.cooldown_days)
                if self.redeem_date < next_allowed:
                    raise UserError(
                        _("Cooldown policy blocks redemption until %(date)s.", date=fields.Date.to_string(next_allowed))
                    )
        return True

    def _validate_operational_context(self):
        self.ensure_one()
        line = self.allocation_line_id
        line.check_redeem_constraints(
            qty_used=self.qty_used,
            credit_used=self.credit_used,
            doctor=self.doctor_id,
            room=self.room_id,
            device=self.device_id,
        )
        self._validate_daily_limits()
        if self.booking_id and self.booking_id.patient_id and self.partner_id and self.booking_id.patient_id != self.partner_id:
            raise UserError(_("The booking patient does not match the package allocation contact."))
        if self.booking_id and line.treatment_id and self.booking_id.treatment_id and self.booking_id.treatment_id != line.treatment_id:
            raise UserError(_("The booking treatment does not match the selected package benefit."))
        return True

    def action_confirm(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only Draft redemptions can be confirmed."))
            record._validate_operational_context()
            record.with_context(clinic_package_state_change=True).write({"state": "confirmed"})
            if record.booking_id and not record.booking_id.package_usage_id:
                record.booking_id.package_usage_id = record
            record._enqueue_integration_event(
                "usage.confirmed",
                {
                    "qty_used": record.qty_used,
                    "credit_used": record.credit_used,
                    "emar_order_id": record.emar_order_id.id,
                    "emar_schedule_id": record.emar_schedule_id.id,
                    "emar_administration_id": record.emar_administration_id.id,
                },
            )
        return True

    def action_cancel(self):
        for record in self:
            if record.state != "confirmed":
                raise UserError(_("Only Confirmed redemptions can be cancelled."))
            record.with_context(clinic_package_state_change=True).write({"state": "cancelled"})
            if record.booking_id and record.booking_id.package_usage_id == record:
                record.booking_id.package_usage_id = False
            record._enqueue_integration_event(
                "usage.cancelled",
                {
                    "qty_used": record.qty_used,
                    "credit_used": record.credit_used,
                    "emar_order_id": record.emar_order_id.id,
                    "emar_schedule_id": record.emar_schedule_id.id,
                    "emar_administration_id": record.emar_administration_id.id,
                },
            )
        return True

    def action_reset_to_draft(self):
        for record in self:
            if record.state != "cancelled":
                raise UserError(_("Only Cancelled redemptions can be reset to Draft."))
            record.with_context(clinic_package_state_change=True).write({"state": "draft"})
        return True

    def action_view_booking(self):
        self.ensure_one()
        if not self.booking_id:
            raise UserError(_("No booking is linked to this redemption."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Booking"),
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.booking_id.id,
        }

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice is linked to this redemption."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Invoice / Receipt"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
        }

    def _enqueue_integration_event(self, event_code, payload=None):
        self.ensure_one()
        return self.env["clinic.package.integration.event"].enqueue(event_code, self, payload=payload)
