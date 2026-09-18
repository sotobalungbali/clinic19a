# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    wallet_ids = fields.One2many("clinic.wallet", "partner_id", string="Wallets")
    wallet_id_current_company = fields.Many2one(
        "clinic.wallet", compute="_compute_current_wallet", string="Wallet (Current Company)"
    )
    wallet_currency_id = fields.Many2one(
        "res.currency", compute="_compute_wallet_summaries", string="Wallet Currency"
    )
    wallet_reserved_amount = fields.Monetary(
        compute="_compute_wallet_summaries", currency_field="wallet_currency_id"
    )
    wallet_total_topup = fields.Monetary(
        compute="_compute_wallet_summaries", currency_field="wallet_currency_id"
    )
    wallet_total_redeem = fields.Monetary(
        compute="_compute_wallet_summaries", currency_field="wallet_currency_id"
    )
    wallet_total_refund = fields.Monetary(
        compute="_compute_wallet_summaries", currency_field="wallet_currency_id"
    )
    wallet_last_transaction_date = fields.Datetime(compute="_compute_wallet_summaries")
    wallet_state = fields.Selection(related="wallet_id_current_company.state", readonly=True)
    wallet_count_total = fields.Integer(compute="_compute_wallet_counts")
    wallet_count_active = fields.Integer(compute="_compute_wallet_counts")

    @api.depends("wallet_ids.company_id", "wallet_ids.state", "wallet_ids.active")
    def _compute_current_wallet(self):
        company = self.env.company
        for partner in self:
            wallets = partner.wallet_ids.filtered(lambda wallet: wallet.company_id == company and wallet.active)
            partner.wallet_id_current_company = (
                wallets.filtered(lambda wallet: wallet.state == "open")[:1]
                or wallets.filtered(lambda wallet: wallet.state == "suspended")[:1]
                or wallets[:1]
            )

    @api.depends(
        "wallet_id_current_company.balance",
        "wallet_id_current_company.reserved_amount",
        "wallet_id_current_company.total_topup",
        "wallet_id_current_company.total_redeem",
        "wallet_id_current_company.total_refund",
        "wallet_id_current_company.last_transaction_date",
        "wallet_id_current_company.currency_id",
    )
    def _compute_wallet_summaries(self):
        for partner in self:
            wallet = partner.wallet_id_current_company
            partner.wallet_currency_id = wallet.currency_id if wallet else self.env.company.currency_id
            partner.wallet_reserved_amount = wallet.reserved_amount if wallet else 0.0
            partner.wallet_total_topup = wallet.total_topup if wallet else 0.0
            partner.wallet_total_redeem = wallet.total_redeem if wallet else 0.0
            partner.wallet_total_refund = wallet.total_refund if wallet else 0.0
            partner.wallet_last_transaction_date = wallet.last_transaction_date if wallet else False

    @api.depends("wallet_ids.state", "wallet_ids.active")
    def _compute_wallet_counts(self):
        for partner in self:
            partner.wallet_count_total = len(partner.wallet_ids)
            partner.wallet_count_active = len(
                partner.wallet_ids.filtered(lambda wallet: wallet.active and wallet.state == "open")
            )

    # clinic_patient owns wallet_balance. Extend its compute contract rather than
    # redeclaring that shared field. The upstream method intentionally had an
    # empty depends list, so Wallet supplies the dependencies it owns.
    @api.depends(
        "wallet_ids.balance",
        "wallet_ids.company_id",
        "wallet_ids.state",
        "wallet_ids.active",
    )
    def _compute_integration_counters(self):
        super()._compute_integration_counters()
        for partner in self:
            wallet = partner.wallet_id_current_company
            partner.wallet_balance = wallet.balance if wallet else 0.0

    def get_or_create_wallet(self, company=None, auto_open=True, ensure_active=False):
        self.ensure_one()
        company = company or self.env.company
        wallet = self.wallet_ids.filtered(lambda item: item.company_id == company)[:1]
        if not wallet:
            wallet = self._create_wallet_for_company(company)
        if ensure_active and wallet.state != "open":
            if not auto_open:
                raise UserError(_("Wallet exists but is not active."))
            if self.env.su or self.env.user.has_group("clinic_wallet.group_wallet_manager"):
                wallet.action_open()
            else:
                raise AccessError(_("A Wallet Manager must activate this wallet."))
        return wallet

    def _create_wallet_for_company(self, company=None):
        self.ensure_one()
        company = company or self.env.company
        existing = self.env["clinic.wallet"].search([
            ("partner_id", "=", self.id),
            ("company_id", "=", company.id),
        ], limit=1)
        if existing:
            return existing
        patient = self.patient_id if "patient_id" in self._fields else False
        return self.env["clinic.wallet"].create({
            "partner_id": self.id,
            "patient_id": patient.id if patient else False,
            "company_id": company.id,
            "currency_id": company.currency_id.id,
        })

    def action_open_wallet(self):
        self.ensure_one()
        wallet = self.wallet_id_current_company or self.get_or_create_wallet(ensure_active=False)
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Wallet"),
            "res_model": "clinic.wallet",
            "view_mode": "form",
            "res_id": wallet.id,
            "target": "current",
        }

    def action_create_wallet(self):
        self.ensure_one()
        if self.wallet_ids.filtered(lambda wallet: wallet.company_id == self.env.company):
            raise UserError(_("This contact already has a wallet for the current company."))
        wallet = self._create_wallet_for_company(self.env.company)
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Wallet"),
            "res_model": "clinic.wallet",
            "view_mode": "form",
            "res_id": wallet.id,
        }

    def action_view_wallet_transactions(self):
        self.ensure_one()
        wallet = self.wallet_id_current_company
        if not wallet:
            raise UserError(_("No wallet exists for this contact in the current company."))
        action = self.env.ref("clinic_wallet.action_wallet_transactions").read()[0]
        action["domain"] = [("wallet_id", "=", wallet.id)]
        action["context"] = {"default_wallet_id": wallet.id}
        return action

    def action_mass_create_wallets(self):
        if not self.env.user.has_group("clinic_wallet.group_wallet_manager"):
            raise AccessError(_("Only Wallet Managers can create wallets in bulk."))
        created = 0
        for partner in self:
            if not partner.wallet_ids.filtered(lambda wallet: wallet.company_id == self.env.company):
                partner._create_wallet_for_company(self.env.company)
                created += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Wallet Creation"),
                "message": _("%s wallet(s) created.") % created,
                "type": "success",
                "sticky": False,
            },
        }

    def wallet_reserve_and_link(self, amount, reference=None, billing_model=None, billing_id=None):
        self.ensure_one()
        return self.get_or_create_wallet(ensure_active=True).reserve_funds(
            amount, reference=reference, billing_model=billing_model, billing_id=billing_id
        )

    def wallet_release_reservation(self, reference=None, billing_model=None, billing_id=None):
        self.ensure_one()
        wallet = self.wallet_id_current_company
        return wallet and wallet.release_reserved(
            reference=reference, billing_model=billing_model, billing_id=billing_id
        ) or True

    def wallet_validate_reservation(self, amount, reference=None, billing_model=None, billing_id=None):
        self.ensure_one()
        return self.get_or_create_wallet(ensure_active=True).validate_reserved_to_posted(
            amount, reference=reference, billing_model=billing_model, billing_id=billing_id
        )

    def _merge_wallets_on_partner_merge(self, sources):
        self.ensure_one()
        for source in sources:
            if source == self:
                continue
            for wallet in source.wallet_ids:
                if self.wallet_ids.filtered(lambda own: own.company_id == wallet.company_id):
                    _logger.warning(
                        "Wallet %s retained on source partner during merge because target already has a company wallet.",
                        wallet.display_name,
                    )
                    continue
                wallet.partner_id = self.id

    def _merge_cleanup(self, sources):
        self._merge_wallets_on_partner_merge(sources)




