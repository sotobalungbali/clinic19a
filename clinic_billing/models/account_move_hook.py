# -*- coding: utf-8 -*-
# File: clinic_billing/models/account_move_hook.py
# License: LGPL-3
#
# Purpose
# -------
# - Soft-bridge between Clinic Billing (clinic.billing.invoice / clinic.billing.line)
#   and Odoo Accounting (account.move / account.move.line).
# - Provide helpers to generate and keep an account move in sync from a clinic invoice.
# - Hook accounting post/draft transitions back to the clinic invoice lifecycle.
#
# Design notes
# ------------
# - No hard dependency on other ClinicOne modules; use soft hooks and try/except.
# - All amounts/taxes rely on Odoo's account.move tax engine once invoice_line_ids are built.
# - Negative lines (e.g., voucher/membership/discount) are handled via negative price/unit.
# - Fixed-amount per-line discounts are folded into effective price_unit (so discount=0 at AML).
#

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# ACCOUNT MOVE <-> CLINIC BILLING: HOOKS ON ACCOUNTING SIDE
# =============================================================================
class AccountMoveClinicBridge(models.Model):
    _inherit = "account.move"

    clinic_invoice_id = fields.Many2one(
        "clinic.billing.invoice",
        string="Clinic Invoice",
        index=True,
        copy=False,
        help="Back-reference to the Clinic Billing Invoice that generated this accounting document."
    )
    is_clinic_billing = fields.Boolean(
        string="Is Clinic Billing Move",
        compute="_compute_is_clinic_billing",
        help="True when this accounting invoice was created from Clinic Billing."
    )

    def _compute_is_clinic_billing(self):
        for rec in self:
            rec.is_clinic_billing = bool(rec.clinic_invoice_id)

    # ----- Lifecycle hooks -----
    def action_post(self):
        """
        After posting, inform Clinic Billing invoice so engines (voucher/membership/gateway/commission)
        can finalize on posting.
        """
        res = super().action_post()
        for move in self:
            inv = move.clinic_invoice_id
            if inv:
                try:
                    # Notify the clinic invoice hook chain (Voucher/Membership/Gateway engines override)
                    inv._on_after_move_posted(move)
                except Exception as e:
                    move.message_post(body=_("Clinic Billing post-hook failed: %s") % e)
        return res

    def button_draft(self):
        """
        When reverting to draft, allow the Clinic Billing invoice to resync if needed.
        """
        res = super().button_draft()
        for move in self:
            inv = move.clinic_invoice_id
            if inv:
                try:
                    # Optional notification; the clinic invoice may want to clean post-only artifacts
                    if hasattr(inv, "_on_after_move_unposted"):
                        inv._on_after_move_unposted(move)
                except Exception as e:
                    move.message_post(body=_("Clinic Billing unpost-hook failed: %s") % e)
        return res

    # Smart action to open the clinic invoice from the move
    def action_open_clinic_invoice(self):
        self.ensure_one()
        if not self.clinic_invoice_id:
            raise UserError(_("No Clinic Billing Invoice linked to this accounting invoice."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Billing Invoice"),
            "res_model": "clinic.billing.invoice",
            "view_mode": "form",
            "res_id": self.clinic_invoice_id.id,
            "target": "current",
        }


class AccountMoveLineClinicBridge(models.Model):
    _inherit = "account.move.line"

    clinic_billing_line_id = fields.Many2one(
        "clinic.billing.line",
        string="Clinic Billing Line",
        index=True,
        copy=False,
        help="Origin clinic billing line for traceability."
    )


# =============================================================================
# ACCOUNTING BUILDER (ABSTRACT) — maps clinic invoice/lines → move/move lines
# =============================================================================
class ClinicBillingAccountBuilder(models.AbstractModel):
    """
    Accounting Builder
    ------------------
    Single place to map Clinic Billing document into a standard account.move.
    """
    _name = "clinic.billing.account.builder"
    _description = "Clinic Billing → Accounting Builder"

    # -------- Public API --------
    def build_or_update_account_move(self, clinic_invoice):
        """
        Create an account.move if missing, or update existing draft move to mirror
        the current clinic invoice lines/values.

        Returns: account.move record.
        """
        clinic_invoice.ensure_one()

        if clinic_invoice.move_id:
            move = clinic_invoice.move_id
            if move.state != "draft":
                raise UserError(_("Cannot sync accounting lines because the accounting invoice is not in draft."))
            # replace invoice_line_ids content with the current mapping
            line_vals_list = self._map_lines_vals(clinic_invoice)
            # wipe existing invoice_line_ids; keep payment terms/metadata
            move.write({"invoice_line_ids": [(5, 0, 0)] + [(0, 0, vals) for vals in line_vals_list]})
            # refresh partner/journal/terms metadata as well
            meta = self._map_move_header_vals(clinic_invoice)
            move.write(meta)
            return move

        # else: create from scratch
        header_vals = self._map_move_header_vals(clinic_invoice)
        line_vals_list = self._map_lines_vals(clinic_invoice)
        header_vals["invoice_line_ids"] = [(0, 0, vals) for vals in line_vals_list]
        move = self.env["account.move"].create(header_vals)
        # link back
        move.clinic_invoice_id = clinic_invoice.id
        # store back-reference on clinic invoice (field must exist on base model)
        try:
            clinic_invoice.move_id = move.id
        except Exception:
            pass
        return move

    # -------- Mapping internals --------
    def _map_move_header_vals(self, clinic_invoice):
        """
        Map clinic invoice header to account.move header fields.
        """
        company = clinic_invoice.company_id
        currency = clinic_invoice.currency_id or company.currency_id
        journal = getattr(clinic_invoice, "journal_id", False) or self._default_sale_journal(company)
        partner = clinic_invoice.patient_id

        vals = {
            "move_type": "out_invoice",  # sales invoice
            "company_id": company.id,
            "currency_id": currency.id,
            "journal_id": journal.id if journal else False,
            "partner_id": partner.id if partner else False,
            "invoice_date": clinic_invoice.invoice_date or fields.Date.context_today(self),
            "invoice_origin": clinic_invoice.name or "",
            "invoice_payment_term_id": getattr(clinic_invoice, "payment_term_id", False) and clinic_invoice.payment_term_id.id or False,
            "invoice_user_id": getattr(clinic_invoice, "user_id", False) and clinic_invoice.user_id.id or False,
            "narration": getattr(clinic_invoice, "note", "") or "",
            # Link back for traceability
            "clinic_invoice_id": clinic_invoice.id,
        }
        # Fiscal position (if present on clinic invoice)
        try:
            if getattr(clinic_invoice, "fiscal_position_id", False):
                vals["fiscal_position_id"] = clinic_invoice.fiscal_position_id.id
        except Exception:
            pass
        return vals

    def _map_lines_vals(self, clinic_invoice):
        """
        Map each clinic.billing.line to account.move.line values.
        """
        aml_vals = []
        for line in clinic_invoice.line_ids:
            aml_vals.append(self._map_single_line(line))
        return aml_vals

    def _map_single_line(self, bl):
        """
        Map a single clinic.billing.line into invoice_line_vals for account.move.
        - Fold fixed discount_amount into effective price_unit.
        - Keep tax_ids from the billing line (or from product fallback).
        - Resolve income account from product/category/journal defaults.
        """
        product = bl.product_id
        # Resolve taxes
        tax_ids = []
        try:
            if bl.tax_ids:
                tax_ids = bl.tax_ids.ids
            elif product and product.taxes_id:
                tax_ids = product.taxes_id.ids
        except Exception:
            tax_ids = []

        # Effective subtotal excl tax (unit*qty - fixed - percent)
        qty = float(bl.quantity or 0.0)
        unit_price = float(bl.unit_price or 0.0)
        line_subtotal = unit_price * qty
        fixed_disc = float(bl.discount_amount or 0.0)
        pct_disc = float(bl.discount_percent or 0.0)
        # apply percent on (unit*qty)
        subtotal_after_pct = line_subtotal * (1.0 - (pct_disc / 100.0))
        effective_subtotal = subtotal_after_pct - fixed_disc
        # If quantity > 0, compute an effective price unit; otherwise push as-is
        eff_unit = (effective_subtotal / qty) if qty else unit_price

        # Income account
        account = self._resolve_income_account(product, bl.invoice_id.company_id)

        vals = {
            "name": bl.name or (product and product.display_name) or _("Service"),
            "product_id": product.id if product else False,
            "quantity": qty or 0.0,
            "price_unit": eff_unit,
            "discount": 0.0,  # fixed/pct already folded into price_unit for stability
            "tax_ids": [(6, 0, tax_ids)],
            "account_id": account.id if account else False,
            # Traceability
            "clinic_billing_line_id": bl.id,
        }

        # Analytic
        try:
            if getattr(bl, "analytic_account_id", False):
                vals["analytic_account_id"] = bl.analytic_account_id.id
            if getattr(bl, "analytic_tag_ids", False):
                vals["analytic_tag_ids"] = [(6, 0, bl.analytic_tag_ids.ids)]
        except Exception:
            pass

        # Section/note support (if your clinic.billing.line implements a type)
        try:
            if getattr(bl, "display_type", False):
                # map to 'line_section'/'line_note' if present
                vals["display_type"] = bl.display_type
                # section/note lines should not carry taxes/accounts
                if bl.display_type in ("line_section", "line_note"):
                    vals["account_id"] = False
                    vals["tax_ids"] = [(6, 0, [])]
                    vals["price_unit"] = 0.0
                    vals["quantity"] = 0.0
        except Exception:
            pass

        return vals

    # -------- Utilities --------
    def _default_sale_journal(self, company):
        Journal = self.env["account.journal"].sudo()
        j = Journal.search([("type", "=", "sale"), ("company_id", "=", company.id)], limit=1)
        if not j:
            # Fallback to any journal
            j = Journal.search([("company_id", "=", company.id)], limit=1)
        return j

    def _resolve_income_account(self, product, company):
        """
        Standard Odoo resolution: product property → category property → any income account.
        """
        Account = self.env["account.account"].sudo().with_company(company)
        if product:
            acc = product.with_company(company).property_account_income_id or product.categ_id.with_company(company).property_account_income_categ_id
            if acc and company in acc.company_ids:
                return acc
        # Fallback: Odoo 19 account.account is multi-company via company_ids.
        acc = Account.search([
            *Account._check_company_domain(company),
            ("account_type", "=", "income"),
        ], limit=1)
        if not acc:
            raise UserError(_("No income account found for company %s. Configure chart of accounts.") % company.display_name)
        return acc


# =============================================================================
# CLINIC BILLING INVOICE — ACCOUNTING HELPERS (SOFT EXTENSION)
# =============================================================================
class ClinicBillingInvoice_AccountingHook(models.Model):
    """
    Add accounting helpers onto Clinic Billing Invoice without relying on other modules.
    These methods are consumed by Voucher/Membership/Gateway engines or other flows.
    """
    _inherit = "clinic.billing.invoice"

    def action_generate_account_move(self):
        """
        Ensure a draft account.move exists mirroring this clinic invoice.
        """
        Builder = self.env["clinic.billing.account.builder"]
        moves = self.env["account.move"]
        for rec in self:
            move = Builder.build_or_update_account_move(rec)
            moves |= move
        return {
            "type": "ir.actions.act_window",
            "name": _("Accounting Invoice"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": moves[:1].id if len(moves) == 1 else False,
            "domain": [("id", "in", moves.ids)],
            "target": "current",
        }

    def action_sync_lines_to_account_move(self):
        """
        If an account.move exists and is draft, sync its invoice_line_ids from clinic lines.
        """
        Builder = self.env["clinic.billing.account.builder"]
        for rec in self:
            if not rec.move_id:
                # create if missing (common in flows where lines are added after draft)
                Builder.build_or_update_account_move(rec)
            else:
                Builder.build_or_update_account_move(rec)
        return True

    def action_post_account_move(self):
        """
        Post the accounting invoice linked to this clinic invoice.
        Will create the account move if missing.
        """
        self.ensure_one()
        if not self.move_id:
            self.action_generate_account_move()
        if self.move_id.state != "posted":
            self.move_id.action_post()
        return True

    # ---- Hooks for Accounting ↔ Clinic Billing lifecycle ----
    def _on_after_move_posted(self, move):
        """
        Called from account.move.action_post via AccountMoveClinicBridge.
        Engines using posting events (voucher/membership/gateway/commission) override this
        in their own _inherit classes (super() is called there).
        """
        # Default behavior: mark clinic invoice state as 'posted' if your base model supports it,
        # and store posted move date/number as mirror fields.
        for rec in self:
            try:
                if "state" in rec._fields and getattr(rec, "state") in ("confirmed", "to_post"):
                    rec.write({"state": "posted"})
            except Exception:
                pass
            try:
                if "posted_move_name" in rec._fields and move.name:
                    rec.posted_move_name = move.name
            except Exception:
                pass

    def _on_after_move_unposted(self, move):
        """
        Optional hook when accounting invoice is reverted to draft.
        """
        for rec in self:
            try:
                if "state" in rec._fields and rec.state == "posted":
                    rec.write({"state": "confirmed"})
            except Exception:
                pass


# =============================================================================
# SAFETY/UTILITIES — RECONCILIATION & PAYMENT REGISTRATION (OPTIONAL)
# =============================================================================
class ClinicBillingInvoice_ReconcileHelper(models.Model):
    _inherit = "clinic.billing.invoice"

    def action_view_accounting(self):
        """
        Open linked account.move (list or form).
        """
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No accounting invoice is linked to this Clinic Billing document yet."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Accounting Invoice"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
            "target": "current",
        }

    def action_register_payment(self):
        """
        Shortcut to Odoo's Register Payment wizard on the linked account.move.
        (Useful when Clinic Billing Payment module is not used.)
        """
        self.ensure_one()
        if not self.move_id or self.move_id.state != "posted":
            raise UserError(_("You can register a payment only after the accounting invoice is posted."))
        return self.move_id.action_register_payment()


# =============================================================================
# OPTIONAL: CREDIT NOTE FLOW (SOFT)
# =============================================================================
class AccountMoveClinicCreditNote(models.Model):
    _inherit = "account.move"

    def action_reverse_from_clinic(self):
        """
        Convenience to create a credit note for a clinic-origin move.
        """
        self.ensure_one()
        if self.move_type != "out_invoice" or self.state != "posted":
            raise UserError(_("Only posted customer invoices can be reversed."))

        action = self._get_reverse_action()  # Odoo's standard reverse action
        # Let standard wizard handle; clinic engines can hook on _on_after_move_posted of the new move
        return action

    def _get_reverse_action(self):
        """
        Standard helper to open reverse wizard (kept separate for clarity).
        """
        return {
            "name": _("Credit Note"),
            "type": "ir.actions.act_window",
            "res_model": "account.move.reversal",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_move_ids": self.ids,
                "default_refund_method": "refund",
            },
        }



