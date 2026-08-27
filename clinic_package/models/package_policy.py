
# -*- coding: utf-8 -*-
"""Reusable package policy profiles."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicPackagePolicy(models.Model):
    _name = "clinic.package.policy"
    _description = "Clinic Package Policy"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )

    allow_pause = fields.Boolean(default=True)
    max_pause_days = fields.Integer(default=30)
    pause_min_days_each = fields.Integer(default=1)
    pause_max_times = fields.Integer(
        default=0, help="0 means unlimited pause cycles within the total pause-day cap."
    )
    pause_require_manager = fields.Boolean(default=False)

    allow_transfer = fields.Boolean(default=True)
    transfer_scope = fields.Selection(
        [("same_patient", "Same Patient"), ("family", "Family"), ("any", "Any Patient")],
        default="family",
        required=True,
    )
    transfer_max_times = fields.Integer(default=1)
    transfer_min_remaining_pct = fields.Float(default=10.0)
    transfer_fee_type = fields.Selection(
        [("none", "No Fee"), ("percent", "Percent"), ("fixed", "Fixed Amount")],
        default="none",
        required=True,
    )
    transfer_fee_value = fields.Monetary()
    transfer_require_manager = fields.Boolean(default=False)

    allow_refund = fields.Boolean(default=False)
    refund_mode = fields.Selection(
        [("none", "No Refund"), ("remaining_value", "Remaining Value"), ("flat", "Flat Amount")],
        default="none",
        required=True,
    )
    refund_flat_amount = fields.Monetary()
    refund_window_days = fields.Integer(default=30)
    refund_min_remaining_pct = fields.Float(default=20.0)
    refund_fee_type = fields.Selection(
        [("none", "No Fee"), ("percent", "Percent"), ("fixed", "Fixed Amount")],
        default="none",
        required=True,
    )
    refund_fee_value = fields.Monetary()
    refund_require_manager = fields.Boolean(default=True)

    allow_upgrade = fields.Boolean(default=True)
    allow_downgrade = fields.Boolean(default=False)
    upgrade_min_remaining_pct = fields.Float(default=5.0)
    note = fields.Text()

    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "A package policy with the same name already exists in this company.",
    )
    _nonnegative_policy_values = models.Constraint(
        "CHECK(max_pause_days >= 0 AND pause_min_days_each >= 0 AND pause_max_times >= 0 "
        "AND transfer_max_times >= 0 AND transfer_fee_value >= 0 AND refund_flat_amount >= 0 "
        "AND refund_window_days >= 0 AND refund_fee_value >= 0)",
        "Package policy limits and fees must be zero or positive.",
    )

    @api.constrains(
        "transfer_min_remaining_pct",
        "refund_min_remaining_pct",
        "upgrade_min_remaining_pct",
    )
    def _check_percentages(self):
        for record in self:
            values = [
                record.transfer_min_remaining_pct,
                record.refund_min_remaining_pct,
                record.upgrade_min_remaining_pct,
            ]
            if any(value < 0.0 or value > 100.0 for value in values):
                raise ValidationError(_("Policy percentages must be between 0 and 100."))

    def validate_pause(self, allocation):
        self.ensure_one()
        if not self.allow_pause:
            raise UserError(_("This package policy does not allow pausing."))
        if self.pause_max_times and allocation.pause_count >= self.pause_max_times:
            raise UserError(_("The maximum number of pause cycles has been reached."))
        if self.max_pause_days and allocation.pause_days_accum >= self.max_pause_days:
            raise UserError(_("The maximum accumulated pause duration has been reached."))
        return True

    def validate_transfer(self, allocation, target_patient):
        self.ensure_one()
        if not self.allow_transfer:
            raise UserError(_("This package policy does not allow transfers."))
        if self.transfer_max_times and allocation.transfer_count >= self.transfer_max_times:
            raise UserError(_("The maximum number of package transfers has been reached."))
        remaining_pct = allocation.remaining_percent
        if remaining_pct < self.transfer_min_remaining_pct:
            raise UserError(
                _("At least %(pct)s%% of the package must remain before transfer.", pct=self.transfer_min_remaining_pct)
            )
        if self.transfer_scope == "same_patient" and target_patient != allocation.patient_id:
            raise UserError(_("This policy only permits reassignment to the same patient."))
        if self.transfer_scope == "family" and target_patient != allocation.patient_id:
            source_partner = allocation.patient_id.partner_id
            target_partner = target_patient.partner_id
            if not source_partner or not target_partner:
                raise UserError(_("Both patients need linked contacts for family-transfer validation."))
            same_family = (
                source_partner.parent_id
                and target_partner.parent_id
                and source_partner.parent_id == target_partner.parent_id
            ) or source_partner.parent_id == target_partner or target_partner.parent_id == source_partner
            if not same_family:
                raise UserError(_("The target patient is not in the same contact family hierarchy."))
        return True

    def compute_transfer_fee(self, allocation):
        self.ensure_one()
        if self.transfer_fee_type == "percent":
            return allocation.price_total * self.transfer_fee_value / 100.0
        if self.transfer_fee_type == "fixed":
            return self.transfer_fee_value
        return 0.0
