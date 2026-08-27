from odoo import api, fields, models, _


SOURCE_SELECTION = [
    ("finance", "Clinic Finance"),
    ("billing", "Clinic Billing"),
    ("ar", "Accounts Receivable"),
    ("ap", "Accounts Payable"),
    ("wallet", "Patient Wallet"),
    ("adjustment", "Accounting Adjustment"),
    ("mixed", "Mixed Clinic Sources"),
    ("other", "Other / Native Odoo"),
]


class AccountMove(models.Model):
    """Accounting source classification over the legal Odoo journal-entry model."""

    _inherit = "account.move"

    clinic_accounting_adjustment_id = fields.Many2one(
        "clinic.accounting.adjustment",
        string="Clinic Accounting Adjustment",
        copy=False,
        index=True,
        ondelete="set null",
    )
    clinic_wallet_transaction_ids = fields.One2many(
        "clinic.wallet.transaction",
        "move_id",
        string="Clinic Wallet Transactions",
    )
    clinic_accounting_source = fields.Selection(
        SOURCE_SELECTION,
        compute="_compute_clinic_accounting_source",
        store=True,
        index=True,
        string="Clinic Accounting Source",
    )
    clinic_accounting_source_detail = fields.Char(
        compute="_compute_clinic_accounting_source",
        store=True,
        string="Clinic Accounting Source Detail",
    )
    clinic_accounting_origin_count = fields.Integer(
        compute="_compute_clinic_accounting_source",
        store=True,
    )

    @api.depends(
        "clinic_accounting_adjustment_id",
        "clinic_finance_transaction_id",
        "clinic_finance_transfer_id",
        "clinic_invoice_id",
        "clinic_ap_ids",
        "ar_invoice_ids",
        "ar_payment_ids",
        "clinic_wallet_transaction_ids",
    )
    def _compute_clinic_accounting_source(self):
        labels = dict(SOURCE_SELECTION)
        for move in self:
            sources = []
            origin_count = 0

            if move.clinic_accounting_adjustment_id:
                sources.append("adjustment")
                origin_count += 1

            finance_count = int(bool(move.clinic_finance_transaction_id)) + int(
                bool(move.clinic_finance_transfer_id)
            )
            if finance_count:
                sources.append("finance")
                origin_count += finance_count

            wallet_count = len(move.clinic_wallet_transaction_ids)
            if wallet_count:
                sources.append("wallet")
                origin_count += wallet_count

            if move.clinic_invoice_id:
                sources.append("billing")
                origin_count += 1

            ap_count = len(move.clinic_ap_ids)
            if ap_count:
                sources.append("ap")
                origin_count += ap_count

            ar_count = len(move.ar_invoice_ids) + len(move.ar_payment_ids)
            if ar_count:
                sources.append("ar")
                origin_count += ar_count

            unique_sources = list(dict.fromkeys(sources))
            if not unique_sources:
                source = "other"
            elif len(unique_sources) == 1:
                source = unique_sources[0]
            else:
                source = "mixed"

            move.clinic_accounting_source = source
            move.clinic_accounting_source_detail = " | ".join(
                labels[item] for item in unique_sources
            ) or labels["other"]
            move.clinic_accounting_origin_count = origin_count

    def action_open_clinic_accounting_origin(self):
        """Open the most specific ClinicOne source when there is a single clear origin."""
        self.ensure_one()

        if self.clinic_accounting_adjustment_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Accounting Adjustment"),
                "res_model": "clinic.accounting.adjustment",
                "view_mode": "form",
                "res_id": self.clinic_accounting_adjustment_id.id,
            }
        if self.clinic_finance_transaction_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Finance Transaction"),
                "res_model": "clinic.finance.transaction",
                "view_mode": "form",
                "res_id": self.clinic_finance_transaction_id.id,
            }
        if self.clinic_finance_transfer_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Finance Transfer"),
                "res_model": "clinic.finance.transfer",
                "view_mode": "form",
                "res_id": self.clinic_finance_transfer_id.id,
            }
        if len(self.clinic_wallet_transaction_ids) == 1:
            wallet_tx = self.clinic_wallet_transaction_ids
            return {
                "type": "ir.actions.act_window",
                "name": _("Wallet Transaction"),
                "res_model": "clinic.wallet.transaction",
                "view_mode": "form",
                "res_id": wallet_tx.id,
            }
        if self.clinic_invoice_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Clinic Billing"),
                "res_model": "clinic.billing.invoice",
                "view_mode": "form",
                "res_id": self.clinic_invoice_id.id,
            }
        if len(self.clinic_ap_ids) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Accounts Payable"),
                "res_model": "clinic.ap",
                "view_mode": "form",
                "res_id": self.clinic_ap_ids.id,
            }
        if len(self.ar_invoice_ids) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Accounts Receivable"),
                "res_model": "clinic.ar.invoice",
                "view_mode": "form",
                "res_id": self.ar_invoice_ids.id,
            }
        if len(self.ar_payment_ids) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("AR Payment"),
                "res_model": "clinic.ar.payment",
                "view_mode": "form",
                "res_id": self.ar_payment_ids.id,
            }

        # For mixed/multiple origins, keep the user on the accounting entry
        # instead of guessing which business document is authoritative.
        return {
            "type": "ir.actions.act_window",
            "name": _("Journal Entry"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.id,
        }


class AccountMoveLine(models.Model):
    """Stored source bridge used by Accounting statements and source analysis."""

    _inherit = "account.move.line"

    clinic_accounting_source = fields.Selection(
        related="move_id.clinic_accounting_source",
        store=True,
        index=True,
        readonly=True,
    )
    clinic_accounting_adjustment_id = fields.Many2one(
        related="move_id.clinic_accounting_adjustment_id",
        store=True,
        index=True,
        readonly=True,
    )
