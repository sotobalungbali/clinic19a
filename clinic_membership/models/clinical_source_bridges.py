


# -*- coding: utf-8 -*-
from odoo import fields, models, _


class ClinicTreatmentMembership(models.Model):
    """Treatment-side discovery API for membership benefit rules."""

    _inherit = "clinic.treatment"

    membership_benefit_count = fields.Integer(
        compute="_compute_membership_benefit_count"
    )

    def _compute_membership_benefit_count(self):
        Benefit = self.env["membership.plan.benefit"]
        for rec in self:
            rec.membership_benefit_count = (
                Benefit.search_count(
                    [
                        ("treatment_id", "=", rec.id),
                        ("active", "=", True),
                    ]
                )
                if rec.id
                else 0
            )

    def action_view_membership_benefits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Benefits"),
            "res_model": "membership.plan.benefit",
            "view_mode": "list,form",
            "domain": [("treatment_id", "=", self.id)],
            "context": {"default_treatment_id": self.id},
        }

    def membership_estimate_discount(
        self, contract, *, doctor=None, unit_price=0.0, qty=1.0, at_datetime=None
    ):
        self.ensure_one()
        contract.ensure_one()
        entitlements = contract.get_applicable_entitlements(
            treatment=self,
            doctor=doctor,
            unit_price=unit_price,
            qty=qty,
            at_datetime=at_datetime,
        )
        entitlement = entitlements[:1]
        return {
            "entitlement_id": entitlement.id if entitlement else False,
            "discount_amount": (
                entitlement.compute_discount(qty, unit_price)
                if entitlement
                else 0.0
            ),
        }


class ClinicEncounterMembership(models.Model):
    _inherit = "clinic.encounter"

    membership_usage_count = fields.Integer(compute="_compute_membership_usage_count")

    def _compute_membership_usage_count(self):
        Usage = self.env["membership.usage"]
        for rec in self:
            rec.membership_usage_count = (
                Usage.search_count([("encounter_id", "=", rec.id)]) if rec.id else 0
            )

    def action_view_membership_usages(self):
        self.ensure_one()
        return _membership_source_action(self, "encounter_id")


class ClinicTreatmentSessionMembership(models.Model):
    _inherit = "clinic.treatment.session"

    membership_usage_count = fields.Integer(compute="_compute_membership_usage_count")

    def _compute_membership_usage_count(self):
        Usage = self.env["membership.usage"]
        for rec in self:
            rec.membership_usage_count = (
                Usage.search_count([("treatment_session_id", "=", rec.id)])
                if rec.id
                else 0
            )

    def action_view_membership_usages(self):
        self.ensure_one()
        return _membership_source_action(self, "treatment_session_id")


class ClinicCarePlanMembership(models.Model):
    _inherit = "clinic.care.plan"

    membership_usage_count = fields.Integer(compute="_compute_membership_usage_count")

    def _compute_membership_usage_count(self):
        Usage = self.env["membership.usage"]
        for rec in self:
            rec.membership_usage_count = (
                Usage.search_count([("care_plan_id", "=", rec.id)]) if rec.id else 0
            )

    def action_view_membership_usages(self):
        self.ensure_one()
        return _membership_source_action(self, "care_plan_id")


class ClinicPackageAllocationMembership(models.Model):
    _inherit = "clinic.package.allocation"

    membership_usage_count = fields.Integer(compute="_compute_membership_usage_count")

    def _compute_membership_usage_count(self):
        Usage = self.env["membership.usage"]
        for rec in self:
            rec.membership_usage_count = (
                Usage.search_count([("package_allocation_id", "=", rec.id)])
                if rec.id
                else 0
            )

    def action_view_membership_usages(self):
        self.ensure_one()
        return _membership_source_action(self, "package_allocation_id")


class ClinicPackageUsageMembership(models.Model):
    _inherit = "clinic.package.usage"

    membership_usage_count = fields.Integer(compute="_compute_membership_usage_count")

    def _compute_membership_usage_count(self):
        Usage = self.env["membership.usage"]
        for rec in self:
            rec.membership_usage_count = (
                Usage.search_count([("package_usage_id", "=", rec.id)]) if rec.id else 0
            )

    def action_view_membership_usages(self):
        self.ensure_one()
        return _membership_source_action(self, "package_usage_id")


class ClinicEmarAdministrationMembership(models.Model):
    _inherit = "clinic.emar.administration"

    membership_usage_count = fields.Integer(compute="_compute_membership_usage_count")

    def _compute_membership_usage_count(self):
        Usage = self.env["membership.usage"]
        for rec in self:
            rec.membership_usage_count = (
                Usage.search_count([("emar_administration_id", "=", rec.id)])
                if rec.id
                else 0
            )

    def action_view_membership_usages(self):
        self.ensure_one()
        return _membership_source_action(self, "emar_administration_id")


def _membership_source_action(record, field_name):
    return {
        "type": "ir.actions.act_window",
        "name": _("Membership Usages"),
        "res_model": "membership.usage",
        "view_mode": "list,form",
        "domain": [(field_name, "=", record.id)],
        "context": {f"default_{field_name}": record.id},
    }


