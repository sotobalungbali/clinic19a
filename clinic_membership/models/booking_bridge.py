

# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BookingMembershipBridge(models.Model):
    """Membership eligibility and price-preview contract on ClinicOne Booking."""

    _inherit = "booking.booking"

    membership_contract_id = fields.Many2one(
        "membership.contract",
        string="Membership Contract",
        ondelete="set null",
        domain="[('partner_id', '=', patient_id), ('state', '=', 'active'), ('company_id', '=', company_id)]",
    )
    membership_entitlement_id = fields.Many2one(
        "membership.contract.benefit",
        string="Preview Entitlement",
        compute="_compute_membership_preview",
    )
    membership_discount_preview = fields.Monetary(
        compute="_compute_membership_preview",
        currency_field="currency_id",
        string="Membership Discount Preview",
    )
    membership_price_after_preview = fields.Monetary(
        compute="_compute_membership_preview",
        currency_field="currency_id",
        string="After Membership",
    )
    membership_priority = fields.Selection(
        [
            ("none", "None"),
            ("low", "Low"),
            ("normal", "Normal"),
            ("high", "High"),
            ("vip", "VIP"),
        ],
        compute="_compute_membership_preview",
    )
    membership_usage_count = fields.Integer(compute="_compute_membership_usage_count")

    @api.depends(
        "membership_contract_id",
        "treatment_id",
        "doctor_id",
        "amount_untaxed",
        "start_datetime",
    )
    def _compute_membership_preview(self):
        for rec in self:
            rec.membership_entitlement_id = False
            rec.membership_discount_preview = 0.0
            rec.membership_price_after_preview = rec.amount_untaxed or 0.0
            rec.membership_priority = "none"
            contract = rec.membership_contract_id
            if not contract or contract.state != "active":
                continue
            entitlements = contract.get_applicable_entitlements(
                treatment=rec.treatment_id,
                doctor=rec.doctor_id,
                qty=1.0,
                unit_price=rec.amount_untaxed or 0.0,
                at_datetime=rec.start_datetime,
            )
            entitlement = entitlements[:1]
            if entitlement:
                rec.membership_entitlement_id = entitlement
                discount = entitlement.compute_discount(
                    1.0, rec.amount_untaxed or 0.0
                )
                rec.membership_discount_preview = discount
                rec.membership_price_after_preview = max(
                    (rec.amount_untaxed or 0.0) - discount, 0.0
                )
                rec.membership_priority = (
                    entitlement.booking_priority_delta
                    if entitlement.benefit_type == "priority"
                    else contract.plan_id.priority_level
                )
            else:
                rec.membership_priority = contract.plan_id.priority_level

    def _compute_membership_usage_count(self):
        Usage = self.env["membership.usage"]
        for rec in self:
            rec.membership_usage_count = (
                Usage.search_count([("booking_id", "=", rec.id)]) if rec.id else 0
            )

    @api.onchange("patient_id")
    def _onchange_membership_patient(self):
        for rec in self:
            if rec.patient_id:
                rec.membership_contract_id = self.env[
                    "membership.contract"
                ].find_active_contract(rec.patient_id, rec.company_id)

    @api.constrains("membership_contract_id", "patient_id", "doctor_id", "treatment_id")
    def _check_membership_booking_eligibility(self):
        for rec in self:
            contract = rec.membership_contract_id
            if not contract:
                continue
            if contract.partner_id != rec.patient_id:
                raise UserError(_("The membership contract belongs to another patient."))
            if rec.doctor_id and not contract.plan_id.ensure_doctor_eligibility(rec.doctor_id):
                raise UserError(_("The selected doctor is not eligible for this membership."))
            if rec.treatment_id and not contract.plan_id.ensure_treatment_eligibility(rec.treatment_id):
                raise UserError(_("The selected treatment is not eligible for this membership."))

    def action_create_membership_usage(self):
        self.ensure_one()
        if not self.membership_contract_id:
            raise UserError(_("Select an Active membership contract first."))
        usage = self.env["membership.usage"].create(
            {
                "contract_id": self.membership_contract_id.id,
                "booking_id": self.id,
                "date": self.start_datetime or fields.Datetime.now(),
                "treatment_id": self.treatment_id.id if self.treatment_id else False,
                "doctor_id": self.doctor_id.id if self.doctor_id else False,
                "qty": 1.0,
                "unit_price": self.amount_untaxed or 0.0,
                "source_model": self._name,
                "source_res_id": self.id,
                "source_reference": self.display_name,
            }
        )
        usage.action_apply_best_benefit()
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Usage"),
            "res_model": "membership.usage",
            "view_mode": "form",
            "res_id": usage.id,
        }

    def action_view_membership_usages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Usages"),
            "res_model": "membership.usage",
            "view_mode": "list,form",
            "domain": [("booking_id", "=", self.id)],
            "context": {
                "default_booking_id": self.id,
                "default_contract_id": self.membership_contract_id.id,
            },
        }

