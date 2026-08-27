# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)




def _validate_wallet_amount_against_total(record):
    """Preserved cross-model validation helper from the original Wallet API."""
    if not record.use_wallet:
        return True
    record._wallet_validate_preconditions()
    residual = record._wallet_amount_residual()
    amount = float(record.wallet_amount or 0.0)
    if amount - 1e-9 > residual:
        raise ValidationError(_("Wallet Amount cannot exceed the amount due/residual."))
    return True


class ClinicWalletBillingMixin(models.AbstractModel):
    _name = "clinic.wallet.billing.mixin"
    _description = "Clinic Wallet Billing Mixin"

    use_wallet = fields.Boolean(
        string="Use Patient Wallet",
        tracking=True,
        help="Reserve and settle part of this document using the patient's ClinicOne wallet.",
    )
    # Abstract mixins must be registry-safe on their own.  The concrete
    # billing/accounting models below redeclare this field as Monetary
    # because they own the actual document currency_id field.
    wallet_amount = fields.Float(
        string="Wallet Amount",
        tracking=True,
    )
    wallet_info = fields.Char(compute="_compute_wallet_info")
    wallet_tx_ids = fields.Many2many(
        "clinic.wallet.transaction",
        compute="_compute_wallet_transactions",
        string="Wallet Transactions",
    )
    wallet_transaction_count = fields.Integer(compute="_compute_wallet_transactions")
    # Same registry-safety rule as wallet_amount: neutral on the abstract
    # mixin, Monetary on each concrete model that owns currency_id.
    wallet_reserved = fields.Float(
        compute="_compute_wallet_transactions",
        string="Wallet Reserved",
    )

    def _wallet_partner(self):
        self.ensure_one()
        if self._name == "clinic.billing.invoice":
            return self.patient_id
        return self.partner_id

    def _wallet_get(self, create=True, ensure_active=True):
        self.ensure_one()
        partner = self._wallet_partner()
        if not partner:
            return False
        partner_engine = partner.sudo()
        if create:
            return partner_engine.get_or_create_wallet(
                company=self.company_id,
                auto_open=True,
                ensure_active=ensure_active,
            )
        return partner_engine.wallet_ids.filtered(lambda wallet: wallet.company_id == self.company_id)[:1]

    def _wallet_tx_domain(self):
        self.ensure_one()
        if not self.id:
            return [("id", "=", 0)]
        return [
            ("billing_model", "=", self._name),
            ("billing_id", "=", self.id),
            ("company_id", "=", self.company_id.id),
        ]

    @api.depends("use_wallet", "wallet_amount")
    def _compute_wallet_info(self):
        for rec in self:
            wallet = rec._wallet_get(create=False, ensure_active=False)
            rec.wallet_info = (
                _("%(wallet)s · Available %(balance).2f · Reserved %(reserved).2f") % {
                    "wallet": wallet.name,
                    "balance": wallet.balance,
                    "reserved": wallet.reserved_amount,
                }
                if wallet else _("No wallet for this patient in the current company")
            )

    def _compute_wallet_transactions(self):
        Tx = self.env["clinic.wallet.transaction"].sudo()
        for rec in self:
            txs = Tx.search(rec._wallet_tx_domain()) if rec.id else Tx.browse()
            rec.wallet_tx_ids = txs
            rec.wallet_transaction_count = len(txs)
            rec.wallet_reserved = sum(
                tx.amount for tx in txs if tx.is_reserved and tx.state == "reserved"
            )


    def _compute_wallet_reserved(self):
        """Compatibility wrapper retained for the pre-V19 Wallet API."""
        return self._compute_wallet_transactions()

    def _get_default_reference(self):
        """Stable reference used by legacy callers that do not pass one explicitly."""
        self.ensure_one()
        return "%s/%s" % (self._name, self.id or "NEW")

    def _wallet_amount_residual(self):
        self.ensure_one()
        if self._name == "account.move":
            return max(float(self.amount_residual or 0.0), 0.0)
        return max(float(getattr(self, "amount_residual", 0.0) or getattr(self, "amount_total", 0.0) or 0.0), 0.0)

    def _wallet_amount_to_use(self):
        self.ensure_one()
        return min(max(float(self.wallet_amount or 0.0), 0.0), self._wallet_amount_residual())

    def _wallet_validate_preconditions(self):
        self.ensure_one()
        if not self.use_wallet:
            return True
        if not self._wallet_partner():
            raise ValidationError(_("A patient/customer is required before using Wallet."))
        if self.currency_id != self.company_id.currency_id:
            raise ValidationError(_("Wallet settlement currently requires company currency."))
        if self.wallet_amount <= 0:
            raise ValidationError(_("Wallet Amount must be greater than zero."))
        return True

    def _wallet_reserve(self, reference=None):
        self.ensure_one()
        if not self.use_wallet:
            return True
        if not self.id:
            raise UserError(_("Save the document before reserving Wallet funds."))
        self._wallet_validate_preconditions()
        amount = self._wallet_amount_to_use()
        wallet = self._wallet_get(create=True, ensure_active=True)
        current = self.env["clinic.wallet.transaction"].sudo().search(
            self._wallet_tx_domain() + [("is_reserved", "=", True), ("state", "=", "reserved")]
        )
        current_amount = sum(current.mapped("amount"))
        if current and self.currency_id.compare_amounts(current_amount, amount) == 0:
            return True
        if current:
            wallet.release_reserved(billing_model=self._name, billing_id=self.id)
        wallet.reserve_funds(
            amount,
            reference=reference or self.display_name,
            billing_model=self._name,
            billing_id=self.id,
        )
        return True

    def _wallet_release(self):
        self.ensure_one()
        wallet = self._wallet_get(create=False, ensure_active=False)
        if wallet and self.id:
            wallet.release_reserved(billing_model=self._name, billing_id=self.id)
        return True

    def _wallet_finalize(self):
        self.ensure_one()
        if not self.use_wallet or not self.id:
            return True
        amount = self._wallet_amount_to_use()
        if amount <= 0:
            return True
        Tx = self.env["clinic.wallet.transaction"].sudo()
        posted = Tx.search(
            self._wallet_tx_domain() + [("transaction_type", "=", "redeem"), ("state", "=", "posted")]
        )
        if self.currency_id.compare_amounts(sum(posted.mapped("amount")), amount) >= 0:
            return True
        wallet = self._wallet_get(create=True, ensure_active=True)
        wallet.validate_reserved_to_posted(
            amount,
            reference=self.display_name,
            billing_model=self._name,
            billing_id=self.id,
        )
        return True

    @api.onchange("use_wallet")
    def _onchange_use_wallet(self):
        for rec in self:
            if not rec.use_wallet:
                rec.wallet_amount = 0.0
                continue
            wallet = rec._wallet_get(create=False, ensure_active=False)
            if wallet:
                rec.wallet_amount = min(wallet.balance, rec._wallet_amount_residual())

    @api.onchange("wallet_amount")
    def _onchange_wallet_amount(self):
        for rec in self:
            if rec.wallet_amount < 0:
                rec.wallet_amount = 0.0

    def action_open_wallet_transactions(self):
        self.ensure_one()
        action = self.env.ref("clinic_wallet.action_wallet_transactions").read()[0]
        action["domain"] = self._wallet_tx_domain()
        return action


    def action_wallet_reserve_now(self):
        for rec in self:
            rec._wallet_reserve(reference=rec.display_name)
        return True

    def action_wallet_release_now(self):
        for rec in self:
            rec._wallet_release()
        return True


class ClinicBillingInvoiceWallet(models.Model):
    # Odoo 19: multiple _inherit requires an explicit target _name when
    # the intention is to extend an existing model in-place.
    _name = "clinic.billing.invoice"
    _inherit = ["clinic.billing.invoice", "clinic.wallet.billing.mixin"]

    # Concrete financial model: preserve full monetary semantics and use
    # the currency field owned by clinic.billing.invoice.
    wallet_amount = fields.Monetary(
        string="Wallet Amount",
        currency_field="currency_id",
        tracking=True,
    )
    wallet_reserved = fields.Monetary(
        compute="_compute_wallet_transactions",
        currency_field="currency_id",
        string="Wallet Reserved",
    )

    def action_confirm(self):
        result = super().action_confirm()
        for rec in self.filtered("use_wallet"):
            rec._wallet_reserve(reference=rec.name)
        return result

    def action_generate_account_move(self):
        result = super().action_generate_account_move()
        for rec in self.filtered(lambda item: item.move_id):
            rec.move_id.write({
                "use_wallet": rec.use_wallet,
                "wallet_amount": rec.wallet_amount,
            })
        return result

    def action_post_account_move(self):
        for rec in self.filtered("use_wallet"):
            rec._wallet_reserve(reference=rec.name)
        result = super().action_post_account_move()
        for rec in self.filtered("use_wallet"):
            rec._wallet_finalize()
        return result

    def action_cancel(self):
        for rec in self:
            rec._wallet_release()
        return super().action_cancel()

    def action_reset_to_draft(self):
        for rec in self:
            rec._wallet_release()
        return super().action_reset_to_draft()

    @api.constrains("use_wallet", "wallet_amount")
    def _check_wallet_amount(self):
        for rec in self:
            _validate_wallet_amount_against_total(rec)


    def _check_wallet_amount_vs_residual(self):
        """Compatibility alias for integrations created against the earlier Wallet contract."""
        return self._check_wallet_amount()

    def action_post(self):
        """
        Compatibility entry point retained from the earlier Wallet addon.
        Clinic Billing V19 posts through action_post_account_move().
        """
        return self.action_post_account_move()


class AccountMoveWallet(models.Model):
    # Keep account.move as the real technical model; do not create an
    # accidental account.move.wallet shadow model.
    _name = "account.move"
    _inherit = ["account.move", "clinic.wallet.billing.mixin"]

    # account.move owns its document currency_id; keep the Wallet fields
    # Monetary here without imposing that field on the abstract mixin.
    wallet_amount = fields.Monetary(
        string="Wallet Amount",
        currency_field="currency_id",
        tracking=True,
    )
    wallet_reserved = fields.Monetary(
        compute="_compute_wallet_transactions",
        currency_field="currency_id",
        string="Wallet Reserved",
    )

    def _eligible_wallet_invoice(self):
        self.ensure_one()
        return self.move_type in ("out_invoice", "out_refund")

    def action_post(self):
        for rec in self.filtered(lambda item: item.use_wallet and item._eligible_wallet_invoice()):
            # Direct accounting invoices may not have an upstream clinic.billing reservation.
            txs = self.env["clinic.wallet.transaction"].sudo().search(
                rec._wallet_tx_domain() + [("is_reserved", "=", True), ("state", "=", "reserved")]
            )
            if not txs:
                rec._wallet_reserve(reference=rec.name or rec.ref)
        result = super().action_post()
        for rec in self.filtered(lambda item: item.use_wallet and item._eligible_wallet_invoice()):
            rec._wallet_finalize()
        return result

    def button_draft(self):
        for rec in self:
            posted_wallet = self.env["clinic.wallet.transaction"].sudo().search_count(
                rec._wallet_tx_domain() + [("state", "=", "posted")]
            )
            if posted_wallet:
                raise UserError(_(
                    "This invoice has posted Wallet transactions. Reverse the Wallet settlement "
                    "before resetting the invoice to draft."
                ))
            rec._wallet_release()
        return super().button_draft()

    def action_wallet_reserve_now(self):
        for rec in self:
            if not rec._eligible_wallet_invoice():
                raise UserError(_("Wallet reserve is only available on customer invoices/refunds."))
            rec._wallet_reserve()
        return True

    def action_wallet_release_now(self):
        for rec in self:
            rec._wallet_release()
        return True

    def button_cancel(self):
        """
        Preserve the historical Wallet cancel hook while respecting Odoo 19's
        native account.move.button_cancel workflow.
        """
        for rec in self:
            posted_wallet = self.env["clinic.wallet.transaction"].sudo().search_count(
                rec._wallet_tx_domain() + [("state", "=", "posted")]
            )
            if posted_wallet:
                raise UserError(_(
                    "This invoice has posted Wallet transactions. Reverse the Wallet settlement "
                    "before cancelling the invoice."
                ))
            rec._wallet_release()
        return super().button_cancel()

    @api.onchange("use_wallet")
    def _onchange_use_wallet_invoice(self):
        """Compatibility onchange name retained for earlier inherited views/custom code."""
        return self._onchange_use_wallet()

    @api.onchange("wallet_amount")
    def _onchange_wallet_amount_invoice(self):
        """Compatibility onchange name retained for earlier inherited views/custom code."""
        return self._onchange_wallet_amount()

    @api.constrains("use_wallet", "wallet_amount")
    def _check_wallet_amount(self):
        for rec in self.filtered(lambda item: not item.use_wallet or item._eligible_wallet_invoice()):
            _validate_wallet_amount_against_total(rec)

    def _check_wallet_amount_vs_residual(self):
        """Compatibility alias for the pre-V19 Wallet constraint method."""
        return self._check_wallet_amount()


class ClinicBillingPaymentLineWallet(models.Model):
    _inherit = "clinic.billing.payment.line"

    def _hook_membership_debit(self):
        """Settle Wallet for split-payment membership lines not already engine-backed."""
        result = super()._hook_membership_debit()
        for line in self.filtered(lambda item: item.method == "membership" and item.amount > 0):
            invoice = line.invoice_id
            if invoice.line_ids.filtered(lambda bill_line: getattr(bill_line, "is_membership_line", False)):
                continue
            wallet = line.partner_id.get_or_create_wallet(
                company=line.company_id,
                ensure_active=True,
            )
            wallet.reserve_funds(
                line.amount,
                reference=line.payment_id.name,
                billing_model=line.payment_id._name,
                billing_id=line.payment_id.id,
            )
            wallet.validate_reserved_to_posted(
                line.amount,
                reference=line.payment_id.name,
                billing_model=line.payment_id._name,
                billing_id=line.payment_id.id,
            )
        return result



