# -*- coding: utf-8 -*-
# File: clinic_billing/models/billing_membership_wallet.py
# License: LGPL-3

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# ============================================================================
# Membership Usage Log
# ============================================================================
class ClinicBillingMembershipUsage(models.Model):
    """
    Membership Wallet Usage
    -----------------------
    Tracks reservation and consumption of membership wallet amounts against a
    Clinic Billing Invoice. Keeps history even if the wallet module is not installed,
    and finalizes when the accounting invoice is posted.

    States:
    - draft: created but not reserved
    - reserved: amount reserved on wallet (if wallet supports reservation)
    - debited: amount debited from wallet after posting
    - released: reservation released (e.g., invoice cancelled)
    - cancelled: voided usage record
    """
    _name = "clinic.billing.membership.usage"
    _description = "Clinic Billing Membership Usage"
    _order = "id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Usage Number",
        default="/",
        copy=False,
        index=True,
        help="Sequence for this membership usage record."
    )
    invoice_id = fields.Many2one(
        "clinic.billing.invoice",
        string="Clinic Invoice",
        required=True,
        index=True,
        ondelete="cascade"
    )
    patient_id = fields.Many2one(
        related="invoice_id.patient_id",
        string="Patient",
        store=True,
        readonly=True
    )
    company_id = fields.Many2one(
        related="invoice_id.company_id",
        string="Company",
        store=True,
        readonly=True
    )
    currency_id = fields.Many2one(
        related="invoice_id.currency_id",
        string="Currency",
        store=True,
        readonly=True
    )

    # Wallet reference: keep it generic to avoid hard deps
    membership_reference = fields.Char(
        string="Membership Reference",
        help="External membership wallet reference or code."
    )
    wallet_partner_id = fields.Many2one(
        "res.partner",
        string="Wallet Owner",
        help="Partner that owns the membership wallet."
    )

    # Amounts
    amount_planned = fields.Monetary(
        string="Planned Amount",
        currency_field="currency_id",
        help="Planned deduction amount from wallet."
    )
    amount_reserved = fields.Monetary(
        string="Reserved Amount",
        currency_field="currency_id",
        help="Amount reserved on the wallet (if supported)."
    )
    amount_debited = fields.Monetary(
        string="Debited Amount",
        currency_field="currency_id",
        help="Actual amount debited from the wallet on posting."
    )

    # State
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("reserved", "Reserved"),
            ("debited", "Debited"),
            ("released", "Released"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        index=True
    )

    # Technical: store external wallet identifiers if module exists/returns data
    external_wallet_model = fields.Char(string="External Wallet Model", help="Model name of the wallet record (if known).")
    external_wallet_id = fields.Integer(string="External Wallet Record ID", help="ID of the wallet record (if known).")

    note = fields.Char(string="Note")

    # Sequence
    def _next_sequence(self):
        return self.env["ir.sequence"].sudo().next_by_code("clinic.billing.membership.usage") or "/"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") in ("/", False):
                vals["name"] = self._next_sequence()
        recs = super().create(vals_list)
        return recs

    # Transitions
    def action_reserve(self):
        """
        Reserve amount on wallet if the wallet module supports it.
        Otherwise, just move to 'reserved' logically.
        """
        for rec in self:
            if rec.state not in ("draft", "reserved"):
                continue
            if (rec.amount_planned or 0.0) <= 0:
                raise UserError(_("Planned Amount must be greater than zero to reserve."))

            reserved = rec._wallet_reserve(rec.amount_planned)
            if reserved <= 0:
                # If wallet cannot reserve, we mark as logical reservation
                reserved = rec.amount_planned
            rec.write({
                "amount_reserved": reserved,
                "state": "reserved",
            })
        return True

    def action_release(self):
        """Release reservation from wallet (if any) and mark as released."""
        for rec in self:
            if rec.state != "reserved":
                continue
            rec._wallet_release(rec.amount_reserved or 0.0)
            rec.write({
                "state": "released",
                "amount_reserved": 0.0,
            })
        return True

    def action_debit(self, amount=None):
        """
        Debit the wallet at posting time.
        """
        for rec in self:
            if rec.state not in ("reserved", "draft", "released"):
                continue
            amt = amount if amount is not None else (rec.amount_reserved or rec.amount_planned or 0.0)
            amt = max(0.0, amt)
            if amt <= 0:
                continue
            deb = rec._wallet_debit(amt)
            rec.write({
                "amount_debited": deb,
                "state": "debited",
            })
        return True

    def action_cancel(self):
        """Cancel usage; release reservation if present."""
        for rec in self:
            if rec.state == "reserved" and (rec.amount_reserved or 0.0) > 0:
                rec._wallet_release(rec.amount_reserved)
            rec.write({"state": "cancelled"})
        return True

    # ------------------------------
    # Soft Wallet API
    # ------------------------------
    # def _wallet_model(self):
    #     """
    #     Return the wallet model env if exists (soft dependency).
    #     Expected API (illustrative):
    #       - model: clinic.wallet
    #       - fields: partner_id, balance_amount, state, reference (optional)
    #       - methods: reserve(partner, amount, note), release(partner, amount, note), debit(partner, amount, reference, note)
    #     """
    #     return self.env["clinic.wallet"] if "clinic.wallet" in self.env else False

    # def _find_wallet_record(self):
    #     """
    #     Try to find a wallet record by reference/owner.
    #     This is intentionally permissive to fit different implementations.
    #     """
    #     Wallet = self._wallet_model()
    #     if not Wallet:
    #         return False

    #     domain = [("state", "=", "active")]
    #     if self.wallet_partner_id:
    #         domain += [("partner_id", "=", self.wallet_partner_id.id)]
    #     # Try reference field if provided
    #     if self.membership_reference:
    #         # Common naming: 'reference' or 'code'
    #         wallet = Wallet.search([("reference", "=", self.membership_reference)] + domain, limit=1)
    #         if not wallet:
    #             wallet = Wallet.search([("code", "=", self.membership_reference)] + domain, limit=1)
    #     else:
    #         wallet = Wallet.search(domain, limit=1) if self.wallet_partner_id else False

    #     return wallet or False

    def _wallet_model(self):
        """Return the downstream wallet model only when clinic_wallet is installed."""
        return self.env["clinic.wallet"] if "clinic.wallet" in self.env else False

    def _find_wallet_record(self):
        Wallet = self._wallet_model()
        if not Wallet:
            return False
        partner = self.wallet_partner_id or self.invoice_id.patient_id
        domain = [("company_id", "=", self.company_id.id), ("state", "=", "open")]
        if partner:
            domain.append(("partner_id", "=", partner.id))
        if self.membership_reference:
            wallet = Wallet.search(domain + [("name", "=", self.membership_reference)], limit=1)
            if wallet:
                return wallet
        return Wallet.search(domain, limit=1)

    def _wallet_reserve(self, amount):
        """
        Try to reserve on the wallet; return reserved amount (0 if not supported).
        """
        Wallet = self._find_wallet_record()
        if not Wallet:
            return 0.0
        reserved = 0.0
        try:
            # hypothetical API
            if hasattr(Wallet, "reserve_funds"):
                Wallet.reserve_funds(
                    amount,
                    reference=self.invoice_id.name or self.name,
                    billing_model=self.invoice_id._name,
                    billing_id=self.invoice_id.id,
                )
                reserved = amount
            else:
                # If no reservation API, do nothing (logical reserve)
                reserved = 0.0
            # Store technical pointer
            self.write({
                "external_wallet_model": Wallet._name,
                "external_wallet_id": Wallet.id,
            })
        except Exception:
            reserved = 0.0
        return float(reserved or 0.0)

    def _wallet_release(self, amount):
        Wallet = self._find_wallet_record()
        if not Wallet or amount <= 0:
            return False
        try:
            if hasattr(Wallet, "release_reserved"):
                Wallet.release_reserved(
                    reference=self.invoice_id.name or self.name,
                    billing_model=self.invoice_id._name,
                    billing_id=self.invoice_id.id,
                )
            return True
        except Exception:
            return False

    def _wallet_debit(self, amount):
        Wallet = self._find_wallet_record()
        if not Wallet or amount <= 0:
            return 0.0
        deb = 0.0
        try:
            # Example API signature
            if hasattr(Wallet, "validate_reserved_to_posted"):
                Wallet.validate_reserved_to_posted(
                    amount,
                    reference=self.invoice_id.name or self.name,
                    billing_model=self.invoice_id._name,
                    billing_id=self.invoice_id.id,
                )
                deb = amount
            else:
                # Fallback: direct balance field manipulation should be implemented in the wallet module; we do nothing here.
                deb = amount
            # Track pointer if not set yet
            if not self.external_wallet_model:
                self.write({
                    "external_wallet_model": Wallet._name,
                    "external_wallet_id": Wallet.id,
                })
        except Exception:
            deb = 0.0
        return float(deb or 0.0)


# ============================================================================
# Membership Engine
# ============================================================================
class ClinicBillingMembershipEngine(models.AbstractModel):
    """
    Membership Engine
    -----------------
    Applies membership wallet coverage to a Clinic Billing Invoice by creating
    a negative clinic billing line ("Membership Wallet Deduction"). Optionally
    reserves the amount at confirm, then debits on posting.
    """
    _name = "clinic.billing.membership.engine"
    _description = "Clinic Billing Membership Engine"

    PARAM_AUTO_APPLY_ON_CONFIRM = "clinic_billing.membership.auto_apply_on_confirm"  # default False
    PARAM_RESERVE_ON_CONFIRM = "clinic_billing.membership.reserve_on_confirm"        # default True
    PARAM_PRODUCT_CODE = "clinic_billing.membership.product_code"                    # default CLINIC-MEMBERSHIP-DEDUCT

    # ------ Public API ------
    # def apply_to_invoice(self, invoice, amount=None, reference=None):
    #     """
    #     Apply membership deduction as a negative line on the clinic invoice.
    #     - amount: optional; if omitted, try to compute from wallet balance (soft).
    #     - reference: optional external wallet reference code.
    #     """
    #     invoice.ensure_one()

    #     if invoice.move_id and invoice.move_id.state == "posted":
    #         raise UserError(_("Cannot apply membership: accounting invoice has been posted."))

    #     # Determine amount to apply
    #     amt = self._determine_amount(invoice, amount, reference)
    #     if amt <= 0:
    #         return {"applied": False, "amount": 0.0}

    #     # Create usage record
    #     usage = self.env["clinic.billing.membership.usage"].create({
    #         "invoice_id": invoice.id,
    #         "membership_reference": reference or invoice.membership_reference or "",
    #         "wallet_partner_id": invoice.patient_id.id if invoice.patient_id else False,
    #         "amount_planned": amt,
    #         "note": "Auto-applied on confirm" if self._get_param_bool(self.PARAM_AUTO_APPLY_ON_CONFIRM, False) else "",
    #     })

    #     # Create negative invoice line
    #     product = self._ensure_membership_product(invoice.company_id)
    #     income_account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
    #     if not income_account:
    #         income_account = self._fallback_income_account(invoice.company_id)

    #     self.env["clinic.billing.line"].create({
    #         "invoice_id": invoice.id,
    #         "sequence": 8300,
    #         "name": "%s - %s" % (_("Membership Wallet"), usage.name),
    #         "product_id": product.id,
    #         "product_uom_id": product.uom_id.id if product.uom_id else False,
    #         "line_type": "service",
    #         "quantity": 1.0,
    #         "unit_price": -amt,  # negative line
    #         "discount_percent": 0.0,
    #         "discount_amount": 0.0,
    #         "tax_ids": [(6, 0, [])],
    #         "analytic_account_id": False,
    #         "analytic_tag_ids": [(6, 0, [])],
    #         "is_membership_line": True,
    #         "membership_usage_id": usage.id,
    #     })

    #     # Update invoice summary
    #     try:
    #         invoice.write({
    #             "membership_reference": reference or invoice.membership_reference or "",
    #             "membership_amount_used": (invoice.membership_amount_used or 0.0) + amt,
    #         })
    #     except Exception:
    #         pass

    #     # Reserve if configured
    #     if self._get_param_bool(self.PARAM_RESERVE_ON_CONFIRM, True):
    #         try:
    #             usage.action_reserve()
    #         except Exception:
    #             invoice.message_post(body=_("Membership reservation failed for usage %s.") % usage.name)

    #     # Resync to accounting draft move if exists
    #     if invoice.move_id and invoice.move_id.state != "posted":
    #         invoice.action_sync_lines_to_account_move()

    #     return {"applied": True, "amount": amt, "usage_id": usage.id}

    def remove_membership_lines(self, invoice):
        """
        Remove engine-generated membership lines from an invoice (if not posted),
        and release reservations.
        """
        invoice.ensure_one()
        if invoice.move_id and invoice.move_id.state == "posted":
            raise UserError(_("Cannot remove membership lines: accounting invoice is posted."))
        lines = invoice.line_ids.filtered(lambda l: l.is_membership_line)
        usage_ids = lines.mapped("membership_usage_id")
        # Delete lines first
        lines.unlink()
        # Release reservations and cancel usage
        for u in usage_ids:
            if u.state == "reserved":
                u.action_release()
            u.action_cancel()
        # Resync to accounting move if exists
        if invoice.move_id and invoice.move_id.state != "posted":
            invoice.action_sync_lines_to_account_move()
        return True

    def finalize_on_post(self, invoice):
        """
        After posting the accounting invoice, debit wallet for all membership usages
        attached to engine-generated membership lines.
        """
        invoice.ensure_one()
        for usage in invoice.membership_usage_ids:
            if usage.state in ("debited", "cancelled"):
                continue
            # Try to debit planned or reserved
            try:
                usage.action_debit()
            except Exception as e:
                invoice.message_post(body=_("Membership debit failed for %s: %s.") % (usage.name, e))

    # ------ Internals ------
    # def _determine_amount(self, invoice, amount, reference):
    #     """
    #     Compute the applicable amount based on:
    #     - explicit amount argument
    #     - wallet balance (soft)
    #     - invoice residual
    #     """
    #     residual = float(invoice.amount_residual or invoice.amount_total or 0.0)
    #     if amount is not None:
    #         return max(0.0, min(amount, residual))

    #     # Soft query wallet balance if module available
    #     balance = self._wallet_balance(invoice.patient_id, reference or invoice.membership_reference)
    #     if balance is None:
    #         # Unknown wallet → require explicit amount or use 0
    #         return 0.0
    #     return max(0.0, min(balance, residual))

    # def _wallet_balance(self, partner, reference=None):
    #     """
    #     Soft check: query wallet balance from clinic.wallet if any.
    #     Returns float or None if not available.
    #     """
    #     if "clinic.wallet" not in self.env:
    #         return None
    #     Wallet = self.env["clinic.wallet"]
    #     domain = [("state", "=", "active")]
    #     if partner:
    #         domain += [("partner_id", "=", partner.id)]
    #     wallet = False
    #     if reference:
    #         wallet = Wallet.search([("reference", "=", reference)] + domain, limit=1) \
    #                  or Wallet.search([("code", "=", reference)] + domain, limit=1)
    #     if not wallet:
    #         wallet = Wallet.search(domain, limit=1) if partner else False
    #     if not wallet:
    #         return None
    #     # Prefer a standard 'balance_amount' field if present
    #     try:
    #         return float(wallet.balance_amount or 0.0)
    #     except Exception:
    #         return None

    def _ensure_membership_product(self, company):
        code = self._get_param("clinic_billing.membership.product_code", default="CLINIC-MEMBERSHIP-DEDUCT")
        Product = self.env["product.product"].sudo()
        product = Product.search([
            ("default_code", "=", code),
            ("company_id", "in", [False, company.id])
        ], limit=1)
        if product:
            return product
        tmpl_vals = {
            "name": "Membership Wallet Deduction (Auto)",
            "type": "service",
            "default_code": code,
            "lst_price": 0.0,
            "company_id": company.id,
        }
        return Product.create(tmpl_vals)

    def _fallback_income_account(self, company):
        Account = self.env["account.account"].sudo().with_company(company)
        acc = Account.search([
            *Account._check_company_domain(company),
            ("account_type", "=", "income"),
        ], limit=1)
        if not acc:
            raise UserError(_("No income account found for company %s. Configure chart of accounts.") % company.display_name)
        return acc

    def _get_param(self, key, default=None):
        icp = self.env["ir.config_parameter"].sudo()
        val = icp.get_param(key)
        return val if val is not None else default

    def _get_param_bool(self, key, default=False):
        v = self._get_param(key, default=str(bool(default)))
        return str(v).lower() in ("1", "true", "yes")


# ============================================================================
# Extensions: Clinic Billing Line & Invoice
# ============================================================================
class ClinicBillingLine_MembershipExt(models.Model):
    _inherit = "clinic.billing.line"

    is_membership_line = fields.Boolean(
        string="Is Membership Line (Engine)",
        default=False,
        help="True if this line is an engine-generated membership deduction."
    )
    membership_usage_id = fields.Many2one(
        "clinic.billing.membership.usage",
        string="Membership Usage",
        help="Usage record linked to this membership line."
    )


class ClinicBillingInvoice_MembershipExt(models.Model):
    _inherit = "clinic.billing.invoice"

    membership_usage_ids = fields.One2many(
        "clinic.billing.membership.usage",
        "invoice_id",
        string="Membership Usages"
    )

    # def action_apply_membership(self, amount=None, reference=None):
    #     """
    #     Manually apply membership wallet deduction to this invoice.
    #     """
    #     Engine = self.env["clinic.billing.membership.engine"]
    #     for rec in self:
    #         Engine.apply_to_invoice(rec, amount=amount, reference=reference)
    #     return True

    def action_remove_membership_lines(self):
        """
        Remove engine-generated membership lines and release any reservation.
        """
        Engine = self.env["clinic.billing.membership.engine"]
        for rec in self:
            Engine.remove_membership_lines(rec)
        return True

    def _on_after_confirm(self):
        """
        Optionally auto-apply membership on confirm.
        """
        super()._on_after_confirm()
        Engine = self.env["clinic.billing.membership.engine"]
        auto_apply = self.env["ir.config_parameter"].sudo().get_param(
            Engine.PARAM_AUTO_APPLY_ON_CONFIRM, default="False"
        )
        if (auto_apply or "").lower() in ("1", "true", "yes"):
            for rec in self:
                try:
                    Engine.apply_to_invoice(rec, amount=None, reference=rec.membership_reference or "")
                except Exception as e:
                    rec.message_post(body=_("Membership auto-apply failed: %s") % e)

    def _on_after_move_posted(self, move):
        """
        Finalize membership wallet debit after the accounting invoice is posted.
        """
        super()._on_after_move_posted(move)
        Engine = self.env["clinic.billing.membership.engine"]
        for rec in self:
            try:
                Engine.finalize_on_post(rec)
            except Exception as e:
                rec.message_post(body=_("Membership finalize failed: %s") % e)


# ============================================================================
# Extension: Payment Line hook to debit wallet (for split payment flow)
# ============================================================================
# class ClinicBillingPaymentLine_MembershipHook(models.Model):
#     _inherit = "clinic.billing.payment.line"

#     def _hook_membership_debit(self):
#         """
#         When a split payment line uses method 'membership', attempt to debit the wallet.
#         Avoid double-debit if engine-generated membership lines are present on the invoice
#         (those are finalized on invoice posting already).
#         """
#         for rec in self:
#             if rec.method != "membership":
#                 continue
#             inv = rec.invoice_id
#             if not inv:
#                 continue

#             # If engine membership lines exist, skip here (engine will handle debit)
#             if inv.line_ids.filtered(lambda l: l.is_membership_line):
#                 continue

#             # Soft call to wallet
#             WalletModel = "clinic.wallet"
#             if WalletModel not in self.env:
#                 # Wallet module not installed; nothing to do
#                 continue

#             # Try find wallet by invoice reference or patient
#             wallet = False
#             Wallet = self.env[WalletModel]
#             if inv.membership_reference:
#                 wallet = Wallet.search([("reference", "=", inv.membership_reference), ("state", "=", "active")], limit=1) \
#                       or Wallet.search([("code", "=", inv.membership_reference), ("state", "=", "active")], limit=1)
#             if not wallet and inv.patient_id:
#                 wallet = Wallet.search([("partner_id", "=", inv.patient_id.id), ("state", "=", "active")], limit=1)

#             if not wallet:
#                 # Log but do not raise to avoid blocking payment flow
#                 rec.payment_id.message_post(body=_("Membership wallet not found for patient. Debit skipped."))
#                 continue

#             # Perform debit (soft)
#             try:
#                 if hasattr(wallet, "debit"):
#                     wallet.debit(inv.patient_id, rec.amount, reference=inv.name or rec.payment_id.name, note="Billing Payment")
#                 # Update invoice mirror
#                 try:
#                     inv.write({"membership_amount_used": (inv.membership_amount_used or 0.0) + rec.amount})
#                 except Exception:
#                     pass
#             except Exception as e:
#                 rec.payment_id.message_post(body=_("Membership debit failed: %s") % e)
#         return


# ============================================================================
# Sequences (Ensure sequence code exists via data XML)
# ============================================================================
# Expected in data/billing_sequences.xml:
# <record id="seq_clinic_billing_membership_usage" model="ir.sequence">
#   <field name="name">Clinic Membership Usage</field>
#   <field name="code">clinic.billing.membership.usage</field>
#   <field name="prefix">CMU/%(year)s/</field>
#   <field name="padding">4</field>
#   <field name="company_id" eval="False"/>
# </record>



