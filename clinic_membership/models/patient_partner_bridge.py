


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResPartnerMembership(models.Model):
    """Canonical member hints and portfolio on the commercial partner."""

    _inherit = "res.partner"

    membership_reference = fields.Char(
        string="Membership Reference",
        index=True,
        help="Primary active ClinicOne membership contract reference.",
    )
    membership_level_key = fields.Char(
        string="Membership Level Key",
        index=True,
        help="Primary active membership tier key used by downstream discount engines.",
    )
    membership_contract_ids = fields.One2many(
        "membership.contract",
        "partner_id",
        string="Membership Contracts",
        readonly=True,
    )
    membership_contract_count = fields.Integer(
        compute="_compute_membership_portfolio"
    )
    membership_active_contract_id = fields.Many2one(
        "membership.contract",
        compute="_compute_membership_portfolio",
        string="Active Membership",
    )
    membership_point_balance = fields.Float(
        compute="_compute_membership_portfolio", digits=(16, 2)
    )
    membership_savings_total = fields.Monetary(
        compute="_compute_membership_portfolio",
        currency_field="membership_currency_id",
    )
    membership_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_membership_portfolio",
    )

    def _compute_membership_portfolio(self):
        Contract = self.env["membership.contract"]
        for rec in self:
            contracts = Contract.search(
                [
                    ("partner_id", "=", rec.id),
                    ("company_id", "=", self.env.company.id),
                ],
                order="start_date desc, id desc",
            ) if rec.id else Contract
            active = contracts.filtered(lambda c: c.state == "active")[:1]
            rec.membership_contract_count = len(contracts)
            rec.membership_active_contract_id = active
            rec.membership_point_balance = active.point_balance if active else 0.0
            rec.membership_savings_total = active.savings_total if active else 0.0
            rec.membership_currency_id = (
                active.currency_id if active else self.env.company.currency_id
            )

    def action_view_membership_contracts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Contracts"),
            "res_model": "membership.contract",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {
                "default_partner_id": self.id,
                "default_company_id": self.env.company.id,
            },
        }

    def action_create_membership_contract(self):
        self.ensure_one()
        patient = self.env["clinic.patient"].search(
            [("partner_id", "=", self.id)], limit=1
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("New Membership Contract"),
            "res_model": "membership.contract",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.id,
                "default_patient_id": patient.id if patient else False,
                "default_company_id": self.env.company.id,
            },
        }


class ClinicPatientMembership(models.Model):
    """Clinical patient portfolio backed by the linked commercial partner."""

    _inherit = "clinic.patient"

    membership_contract_ids = fields.One2many(
        "membership.contract",
        "patient_id",
        string="Membership Contracts",
        readonly=True,
    )
    membership_contract_count = fields.Integer(
        compute="_compute_membership_portfolio"
    )
    membership_active_contract_id = fields.Many2one(
        "membership.contract",
        compute="_compute_membership_portfolio",
        string="Active Membership",
    )
    membership_point_balance = fields.Float(
        compute="_compute_membership_portfolio", digits=(16, 2)
    )
    membership_savings_total = fields.Monetary(
        compute="_compute_membership_portfolio",
        currency_field="membership_currency_id",
    )
    membership_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_membership_portfolio",
    )

    def _compute_membership_portfolio(self):
        Contract = self.env["membership.contract"]
        for rec in self:
            contracts = Contract.search(
                [
                    ("patient_id", "=", rec.id),
                    ("company_id", "=", self.env.company.id),
                ],
                order="start_date desc, id desc",
            ) if rec.id else Contract
            active = contracts.filtered(lambda c: c.state == "active")[:1]
            rec.membership_contract_count = len(contracts)
            rec.membership_active_contract_id = active
            rec.membership_point_balance = active.point_balance if active else 0.0
            rec.membership_savings_total = active.savings_total if active else 0.0
            rec.membership_currency_id = (
                active.currency_id if active else self.env.company.currency_id
            )

    def action_view_membership_contracts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Contracts"),
            "res_model": "membership.contract",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {
                "default_patient_id": self.id,
                "default_partner_id": self.partner_id.id if self.partner_id else False,
                "default_company_id": self.env.company.id,
            },
        }

    def action_create_membership_contract(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Membership Contract"),
            "res_model": "membership.contract",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_patient_id": self.id,
                "default_partner_id": self.partner_id.id if self.partner_id else False,
                "default_company_id": self.env.company.id,
            },
        }

