# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    ar_writeoff_account_id = fields.Many2one(
        "account.account",
        string="AR Write-off Account",
        check_company=True,
        domain="[('deprecated', '=', False)]",
        help="Expense or income account used for approved small AR residual write-offs.",
    )
    ar_writeoff_threshold = fields.Monetary(
        string="AR Write-off Threshold",
        currency_field="currency_id",
        default=0.0,
    )
    ar_default_general_journal_id = fields.Many2one(
        "account.journal",
        string="Default General Journal (AR Ops)",
        check_company=True,
        domain="[('type', '=', 'general')]",
    )

    @api.constrains("ar_writeoff_threshold")
    def _check_ar_writeoff_threshold(self):
        for company in self:
            if company.ar_writeoff_threshold < 0:
                raise ValidationError(_("AR write-off threshold cannot be negative."))

    @api.constrains("ar_writeoff_account_id")
    def _check_ar_writeoff_account_company(self):
        for company in self:
            if company.ar_writeoff_account_id and company not in company.ar_writeoff_account_id.sudo().company_ids:
                raise ValidationError(_("AR write-off account is not available to this company."))


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    ar_is_receivable = fields.Boolean(compute="_compute_ar_is_receivable")

    @api.depends("account_id.account_type")
    def _compute_ar_is_receivable(self):
        for line in self:
            line.ar_is_receivable = line.account_id.account_type == "asset_receivable"


class AccountMove(models.Model):
    _inherit = "account.move"

    ar_invoice_ids = fields.One2many("clinic.ar.invoice", "move_id", string="Clinic AR Invoices")
    ar_payment_ids = fields.One2many("clinic.ar.payment", "move_id", string="Clinic AR Receipts")
    ar_invoice_count = fields.Integer(compute="_compute_ar_counts")
    ar_payment_count = fields.Integer(compute="_compute_ar_counts")
    ar_is_ar_invoice_move = fields.Boolean(compute="_compute_ar_counts")
    ar_is_ar_payment_move = fields.Boolean(compute="_compute_ar_counts")
    ar_receivable_line_ids = fields.Many2many(
        "account.move.line", compute="_compute_ar_receivable_lines", string="Receivable Lines"
    )

    @api.depends("ar_invoice_ids", "ar_payment_ids", "move_type")
    def _compute_ar_counts(self):
        for move in self:
            move.ar_invoice_count = len(move.ar_invoice_ids)
            move.ar_payment_count = len(move.ar_payment_ids)
            move.ar_is_ar_invoice_move = move.move_type == "out_invoice" and bool(move.ar_invoice_ids)
            move.ar_is_ar_payment_move = bool(move.ar_payment_ids)

    @api.depends("line_ids.account_id.account_type", "line_ids.partner_id", "partner_id")
    def _compute_ar_receivable_lines(self):
        for move in self:
            partner = move.partner_id.commercial_partner_id if move.partner_id else False
            lines = move.line_ids.filtered(lambda line: line.account_id.account_type == "asset_receivable")
            if partner:
                lines = lines.filtered(lambda line: line.partner_id.commercial_partner_id == partner)
            move.ar_receivable_line_ids = lines

    def action_open_related_ar_invoice(self):
        self.ensure_one()
        if not self.ar_invoice_ids:
            raise UserError(_("No Clinic AR Invoice is linked to this Accounting Move."))
        return self.ar_invoice_ids._get_records_action(name=_("Clinic AR Invoices"))

    def action_open_related_ar_payment(self):
        self.ensure_one()
        if not self.ar_payment_ids:
            raise UserError(_("No Clinic AR Receipt is linked to this Accounting Move."))
        return self.ar_payment_ids._get_records_action(name=_("Clinic AR Receipts"))

    def action_open_receivable_items(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda line: line.ar_is_receivable)
        return lines._get_records_action(name=_("Receivable Items"))

    def ar_get_open_receivable_lines(self, only_credit=False, only_debit=False):
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable" and not line.reconciled
        )
        if self.partner_id:
            partner = self.partner_id.commercial_partner_id
            lines = lines.filtered(lambda line: line.partner_id.commercial_partner_id == partner)
        if only_credit:
            lines = lines.filtered(lambda line: line.amount_residual < 0)
        if only_debit:
            lines = lines.filtered(lambda line: line.amount_residual > 0)
        return lines

    def ar_force_reconcile_all(self):
        for move in self:
            lines = move.ar_get_open_receivable_lines()
            debit = lines.filtered(lambda line: line.amount_residual > 0)
            credit = lines.filtered(lambda line: line.amount_residual < 0)
            if debit and credit:
                (debit + credit).reconcile()
        return True

    def _get_ar_writeoff_journal(self):
        self.ensure_one()
        journal = self.company_id.ar_default_general_journal_id
        if journal:
            return journal
        journal = self.env["account.journal"].search([
            ("company_id", "=", self.company_id.id),
            ("type", "=", "general"),
        ], limit=1)
        if not journal:
            raise UserError(_("Configure a General journal for AR write-off operations."))
        return journal

    def action_ar_writeoff_small_residual(self):
        """Clear an approved small residual through a posted journal entry + reconciliation.

        The original baseline attempted foreign-currency write-offs by writing debit/credit
        directly. V1 deliberately refuses that unsafe case until a dedicated currency-rate
        policy exists; incorrect accounting is worse than a clear operational block.
        """
        for move in self:
            if move.move_type != "out_invoice" or move.state != "posted":
                raise UserError(_("Small residual write-off is only available on posted Customer Invoices."))
            if move.currency_id != move.company_id.currency_id:
                raise UserError(_("Foreign-currency AR write-off requires a dedicated exchange-rate policy and is intentionally blocked."))
            threshold = move.company_id.ar_writeoff_threshold
            account = move.company_id.ar_writeoff_account_id
            if threshold <= 0 or not account:
                raise UserError(_("Configure AR Write-off Threshold and AR Write-off Account first."))
            receivable = move.ar_get_open_receivable_lines(only_debit=True)
            residual = move.company_id.currency_id.round(sum(receivable.mapped("amount_residual")))
            if residual <= 0:
                raise UserError(_("This invoice has no positive receivable residual to write off."))
            if residual > threshold:
                raise UserError(_("Residual exceeds the configured AR write-off threshold."))
            partner = move.partner_id.commercial_partner_id
            recv_account = receivable[:1].account_id
            if not recv_account:
                raise UserError(_("No open receivable account line was found."))
            writeoff = self.env["account.move"].with_company(move.company_id).create({
                "move_type": "entry",
                "date": fields.Date.context_today(move),
                "ref": _("AR small residual write-off for %s") % move.name,
                "journal_id": move._get_ar_writeoff_journal().id,
                "company_id": move.company_id.id,
                "line_ids": [
                    (0, 0, {"name": _("AR Write-off"), "account_id": account.id, "debit": residual, "credit": 0.0, "partner_id": partner.id}),
                    (0, 0, {"name": _("AR Write-off Receivable"), "account_id": recv_account.id, "debit": 0.0, "credit": residual, "partner_id": partner.id}),
                ],
            })
            writeoff.action_post()
            credit = writeoff.line_ids.filtered(
                lambda line: line.account_id == recv_account and line.partner_id.commercial_partner_id == partner and line.amount_residual < 0
            )
            if not credit:
                raise UserError(_("Write-off entry posted without an open receivable credit; transaction rolled back."))
            (receivable + credit).reconcile()
            if move.amount_residual:
                raise UserError(_("Write-off reconciliation did not clear the expected residual; transaction rolled back."))
            move.message_post(body=_("Small AR residual written off through %s.") % writeoff.display_name)
        return True

    def action_ar_rebuild_links(self):
        """Reverse links are relational and computed from child move_id values; refresh caches."""
        self.invalidate_recordset(["ar_invoice_ids", "ar_payment_ids", "ar_invoice_count", "ar_payment_count"])
        return True

