# -*- coding: utf-8 -*-
# ClinicOne — clinic_wallet
# File: models/wallet_transaction.py
# License: LGPL-3.0
import logging
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError

_logger = logging.getLogger(__name__)


class ClinicWalletTransaction(models.Model):
    """
    Transaksi dompet prabayar.

    Tipe transaksi:
    - topup      : +saldo (kas/bank → liabilitas wallet)
    - redeem     : -saldo (pakai untuk bayar billing). Default: tanpa jurnal di sini.
                   Akuntansi biasanya dibuat oleh modul Billing/Accounting pada saat posting dokumen.
                   Dapat dipaksa buat jurnal di sini via setting 'clinic_wallet.redeem_post_accounting'.
    - refund     : -saldo (kembalikan ke pasien) → (liabilitas wallet → kas/bank)
    - adjust_in  : +saldo (koreksi internal)     → (akun penyeimbang → liabilitas wallet)
    - adjust_out : -saldo (koreksi internal)     → (liabilitas wallet → akun penyeimbang)

    Status:
    - draft     : baru dibuat
    - reserved  : menahan saldo sementara (digunakan oleh billing sebelum final)
    - posted    : final; mempengaruhi saldo & (opsional) jurnal sudah dibuat
    - canceled  : dibatalkan (tidak pengaruhi saldo)
    """
    _name = "clinic.wallet.transaction"
    _description = "Clinic Wallet Transaction"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _rec_name = "name"
    _check_company_auto = True

    # Identity
    name = fields.Char(
        string="Transaction Number",
        copy=False,
        index=True,
        default="/",
        help="Nomor unik transaksi. Diisi sequence saat create."
    )

    wallet_id = fields.Many2one(
        "clinic.wallet",
        string="Wallet",
        required=True,
        ondelete="cascade",
        index=True
    )
    company_id = fields.Many2one(
        related="wallet_id.company_id",
        store=True,
        index=True,
        readonly=True
    )
    currency_id = fields.Many2one(
        related="wallet_id.currency_id",
        store=True,
        index=True,
        readonly=True
    )
    partner_id = fields.Many2one(
        related="wallet_id.partner_id",
        store=True,
        index=True,
        readonly=True
    )

    # Core fields
    transaction_type = fields.Selection(
        [
            ("topup", "Top-Up"),
            ("redeem", "Redeem"),
            ("refund", "Refund"),
            ("adjust_in", "Adjustment In (+)"),
            ("adjust_out", "Adjustment Out (-)"),
        ],
        required=True,
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("reserved", "Reserved"),
            ("posted", "Posted"),
            ("canceled", "Canceled"),
        ],
        default="draft",
        index=True,
        tracking=True,
    )
    is_reserved = fields.Boolean(
        string="Is Reserved",
        default=False,
        help="Menandai transaksi penahanan saldo sementara (belum final).",
    )
    date = fields.Datetime(
        string="Transaction Date",
        default=lambda self: fields.Datetime.now(),
        index=True,
        tracking=True,
    )

    # Amounts
    amount = fields.Monetary(
        string="Amount",
        required=True,
        tracking=True,
        help="Nilai nominal transaksi (selalu positif)."
    )
    amount_signed = fields.Monetary(
        string="Signed Amount",
        compute="_compute_amount_signed",
        store=True,
        help="Nilai bernilai + atau - sesuai tipe transaksi, hanya dihitung saat posted.",
    )
    note = fields.Text(string="Notes / Memo")

    # Accounting linkage
    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        readonly=True,
        copy=False,
        help="Jurnal yang dibuat untuk transaksi ini (jika ada).",
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        help="Override jurnal default wallet (opsional)."
    )

    # Billing linkage (optional soft-coupling)
    billing_model = fields.Char(
        string="Billing Model",
        help="Nama model dokumen billing (misal: clinic.billing, account.move, sale.order)."
    )
    billing_id = fields.Integer(
        string="Billing ID",
        help="ID record dokumen billing yang terkait."
    )
    reference = fields.Char(
        string="External Reference",
        help="Referensi eksternal (nomor invoice/order/tiket/portal)."
    )
    origin_reserved_id = fields.Many2one(
        "clinic.wallet.transaction",
        string="Origin Reserved",
        readonly=True,
        copy=False,
        help="Diisi jika transaksi ini hasil split dari reservasi."
    )

    # Rule tags (opsional; memudahkan validasi penggunaan)
    category_id = fields.Many2one(
        "product.category",
        string="Usage Category",
        help="Kategori produk/treatment (opsional) untuk evaluasi rule."
    )
    product_id = fields.Many2one(
        "product.product",
        string="Related Product/Treatment",
        help="Produk/treatment spesifik untuk evaluasi rule."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("transaction_type", "amount", "state")
    def _compute_amount_signed(self):
        """
        amount_signed menghitung dampak ke saldo saat state = posted.
        Untuk draft/reserved/canceled -> amount_signed = 0 (tidak mengubah saldo).
        """
        for rec in self:
            if rec.state != "posted":
                rec.amount_signed = 0.0
                continue

            amt = (rec.amount or 0.0)
            if rec.transaction_type in ("topup", "adjust_in"):
                rec.amount_signed = amt
            elif rec.transaction_type in ("redeem", "refund", "adjust_out"):
                rec.amount_signed = -amt
            else:
                rec.amount_signed = 0.0

    # -------------------------------------------------------------------------
    # DEFAULTS / CREATE / WRITE / DELETE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_wallet.seq_clinic_wallet_tx", raise_if_not_found=False)
        trusted_transition = self.env.su or self.env.context.get("wallet_tx_transition")
        for vals in vals_list:
            if not trusted_transition and (
                vals.get("state") in ("posted", "canceled", "reserved")
                or vals.get("is_reserved")
            ):
                raise AccessError(_("Wallet transaction workflow must be changed through its action methods."))
            # Default journal dari wallet settings
            if not vals.get("journal_id"):
                # jurnal boleh kosong, nanti diambil dari wallet.get_wallet_journal() saat post
                pass
            if not vals.get("name") or vals.get("name") == "/":
                if seq:
                    vals["name"] = self.env["ir.sequence"].next_by_code("clinic.wallet.transaction") or "/"
                else:
                    vals["name"] = self._temp_name(vals)
            # safety: amount harus positif
            if vals.get("amount") is not None and vals["amount"] <= 0:
                raise ValidationError(_("Amount must be greater than zero."))
        recs = super().create(vals_list)

        # Jika is_reserved=True → state mengikuti reserved
        for rec in recs:
            if rec.is_reserved and rec.state == "draft":
                rec.state = "reserved"
        return recs

    def write(self, vals):
        sensitive = {"state", "is_reserved", "move_id"} & set(vals)
        if sensitive and not (self.env.su or self.env.context.get("wallet_tx_transition")):
            raise AccessError(_("Wallet transaction workflow fields are protected; use the action buttons/API."))
        # Proteksi perubahan kritikal setelah posted
        if any(k in vals for k in ("amount", "transaction_type", "wallet_id", "currency_id", "company_id")):
            for rec in self:
                if rec.state == "posted":
                    raise UserError(_("You cannot modify a posted wallet transaction."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            rec.wallet_id._lock_for_update()
            if rec.state == "posted":
                raise UserError(_("You cannot delete a posted wallet transaction."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # STATE ACTIONS
    # -------------------------------------------------------------------------
    def action_set_reserved(self):
        """Menandai transaksi sebagai reserved (digunakan oleh billing)."""
        for rec in self:
            if rec.state not in ("draft", "reserved"):
                raise UserError(_("Only draft transactions can be reserved."))
            if rec.amount <= 0:
                raise ValidationError(_("Reserved amount must be greater than zero."))
            rec.with_context(wallet_tx_transition=True).write({
                "is_reserved": True,
                "state": "reserved",
            })
        return True

    def action_post(self, accounting_name=None, accounting_date=None, liability_account_id=None):
        """
        Finalisasi transaksi:
        - Validasi rule & ketersediaan saldo (untuk transaksi pengurang: redeem/refund/adjust_out).
        - Buat jurnal (topup/refund/adjust_in/adjust_out).
        - Untuk redeem: default tanpa jurnal di sini, kecuali setting mengharuskan.
        """
        if accounting_name is not None or accounting_date is not None or liability_account_id is not None:
            self.ensure_one()
            self.wallet_id._check_access_manager()
            if not accounting_name or not accounting_date or not liability_account_id:
                raise UserError(_("Explicit posting requires name, date and liability account together."))
        for rec in self:
            rec.wallet_id._lock_for_update()
            if rec.state == "posted":
                continue
            if rec.state not in ("draft", "reserved"):
                raise UserError(_("Only draft/reserved transactions can be posted."))
            # Adjustments are privileged accounting corrections. The check lives
            # in the model method so RPC/API callers cannot bypass the UI group.
            if rec.transaction_type in ("adjust_in", "adjust_out"):
                rec._ensure_adjustment_rights()

            # Validasi kebijakan/aturan & saldo
            rec._check_rules()
            rec._check_balance_policy_before_post()

            # Buat jurnal bila diperlukan
            if rec._should_post_accounting_now():
                move = rec._create_account_move(accounting_name, accounting_date, liability_account_id)
                rec.with_context(wallet_tx_transition=True).write({"move_id": move.id})

            # Tandai posted & lepaskan flag reserved
            rec.with_context(wallet_tx_transition=True).write({
                "is_reserved": False,
                "state": "posted",
            })
        return True

    def action_cancel(self):
        """
        Batalkan transaksi (hanya draft/reserved). Jika sudah posted → tidak bisa cancel.
        """
        for rec in self:
            if rec.state == "posted":
                raise UserError(_("You cannot cancel a posted transaction."))
            rec.with_context(wallet_tx_transition=True).write({
                "state": "canceled",
                "is_reserved": False,
            })
        return True

    # -------------------------------------------------------------------------
    # SPLIT LOGIC (untuk validasi_reserved_to_posted di wallet)
    # -------------------------------------------------------------------------
    def split_reserved(self, take_amount):
        """
        Membelah transaksi reserved menjadi:
        - 1 baris posted (jumlah = take_amount) → (is_reserved=False, state=draft → akan di-post oleh caller)
        - Sisanya tetap reserved (amount berkurang).
        Returns: record baru hasil split (yang siap diposting).
        """
        self.ensure_one()
        if self.state not in ("draft", "reserved") or not self.is_reserved:
            raise UserError(_("Only reserved transactions can be split."))
        if take_amount <= 0 or take_amount > self.amount:
            raise ValidationError(_("Split amount must be within (0, amount]."))

        remain = self.amount - take_amount
        # Update transaksi asal (sisa tetap reserved)
        self.amount = remain

        # Buat transaksi baru (turunan) untuk jumlah yang diambil
        new_vals = {
            "name": "/",  # akan diisi sequence
            "wallet_id": self.wallet_id.id,
            "transaction_type": self.transaction_type,
            "amount": take_amount,
            "is_reserved": False,
            "state": "draft",
            "date": fields.Datetime.now(),
            "reference": self.reference,
            "billing_model": self.billing_model,
            "billing_id": self.billing_id,
            "origin_reserved_id": self.id,
            "category_id": self.category_id.id or False,
            "product_id": self.product_id.id or False,
            "journal_id": self.journal_id.id or False,
            "note": (self.note or "") + " [split]",
        }
        new_rec = self.with_context(wallet_tx_transition=True).create([new_vals])
        return new_rec and new_rec[0] or self.browse()

    # -------------------------------------------------------------------------
    # VALIDATIONS & RULES
    # -------------------------------------------------------------------------
    def _check_rules(self):
        """
        Placeholder validasi kebijakan usage (clinic.wallet.rule).
        Implementasi detail berada di model rule (domain per kategori, treatment, limit per transaksi/per hari, dll).
        """
        Rule = self.env["clinic.wallet.rule"]
        for rec in self:
            # Only balance-reducing transactions are governed by usage rules.
            if rec.transaction_type not in ("redeem", "adjust_out", "refund"):
                continue
            # Apply both wallet-specific rules and company templates whose
            # wallet_id is empty. This makes the documented global scope real.
            rules = Rule.search([
                ("company_id", "=", rec.company_id.id),
                ("active", "=", True),
                "|",
                ("wallet_id", "=", False),
                ("wallet_id", "=", rec.wallet_id.id),
            ], order="sequence, id")
            for rule in rules:
                rule._check_transaction(rec)

    def _check_balance_policy_before_post(self):
        """
        Cek ketersediaan saldo dan status wallet sebelum transaksi yang mengurangi saldo diposting.
        """
        for rec in self:
            if rec.transaction_type in ("redeem", "refund", "adjust_out"):
                # A reservation has already reduced wallet.balance, so do not
                # count its own amount twice during final posting.
                if rec.is_reserved and rec.state == "reserved":
                    rec.wallet_id.ensure_usable()
                else:
                    rec.wallet_id.ensure_usable(amount=rec.amount)
            else:
                rec.wallet_id.ensure_usable()

    # -------------------------------------------------------------------------
    # ACCOUNTING
    # -------------------------------------------------------------------------
    def _should_post_accounting_now(self):
        """
        Menentukan apakah transaksi ini harus membuat jurnal di sini.
        Default:
        - topup/refund/adjust_in/adjust_out → YES (harus ada jurnal)
        - redeem → NO (umumnya diakui saat billing). Bisa diaktifkan via setting.
        """
        self.ensure_one()
        if self.transaction_type in ("topup", "refund", "adjust_in", "adjust_out"):
            return True
        if self.transaction_type == "redeem":
            return bool(self.wallet_id.company_id.wallet_redeem_post_accounting)
        return False

    def _create_account_move(self, accounting_name=None, accounting_date=None, liability_account_id=None):
        """
        Buat account.move untuk transaksi ini.
        Mapping akun:
        - Liability wallet: wallet.get_liability_account()
        - Journal:
          - pakai journal_id jika diset di transaksi
          - else pakai wallet.get_wallet_journal()
        - Counterpart:
          - topup/refund: default_account dari journal (kas/bank)
          - adjust_in / adjust_out: akun penyeimbang dari parameter sistem
            (clinic_wallet.account_adjust_in_id / clinic_wallet.account_adjust_out_id) per company.
            Jika tidak ada → fallback ke journal.default_account_id.
        """
        self.ensure_one()
        if self.move_id:
            return self.move_id

        wallet = self.wallet_id
        journal = self.journal_id or wallet.get_wallet_journal()
        if not journal:
            raise UserError(_("Wallet journal is not configured."))

        liability_acc = self.env["account.account"].browse(liability_account_id).exists() if liability_account_id else wallet.get_liability_account()
        if liability_account_id:
            liability_acc.check_access("read")
            if (not liability_acc or wallet.company_id not in liability_acc.company_ids
                    or not liability_acc.active or liability_acc.account_type not in ("liability_current", "liability_non_current")):
                raise UserError(_("Explicit Wallet liability account must be active and belong to the Wallet company."))
        if not liability_acc:
            raise UserError(_("Wallet liability account is not configured."))

        counterpart_acc = self._get_counterpart_account(journal)

        # Tanggal & ref
        move_vals = {
            "ref": self._build_move_ref(),
            "date": fields.Date.to_date(accounting_date) if accounting_date else fields.Date.context_today(self),
            "journal_id": journal.id,
            "company_id": wallet.company_id.id,
            "line_ids": [],
        }

        if accounting_name:
            move_vals["name"] = accounting_name

        amt = self.amount
        def _add_line(account, debit=0.0, credit=0.0, name=None):
            line_vals = {
                "name": name or self.name,
                "account_id": account.id,
                "debit": debit,
                "credit": credit,
                "partner_id": wallet.partner_id.id,
            }
            # Wallet currently enforces company currency, but keep the journal
            # helper correct if multi-currency support is introduced later.
            if self.currency_id != wallet.company_id.currency_id:
                line_vals.update({
                    "currency_id": self.currency_id.id,
                    "amount_currency": amt if debit else -amt,
                })
            move_vals["line_ids"].append((0, 0, line_vals))

        # Skema jurnal
        # a) TOPUP: Debit Cash/Bank (counterpart), Credit Liability (wallet)
        # b) REFUND: Debit Liability (wallet), Credit Cash/Bank (counterpart)
        # c) ADJUST_IN: Debit Adjustment In Account (counterpart), Credit Liability
        # d) ADJUST_OUT: Debit Liability, Credit Adjustment Out Account (counterpart)
        if self.transaction_type == "topup":
            _add_line(counterpart_acc, debit=amt, name=_("Wallet Top-Up"))
            _add_line(liability_acc, credit=amt, name=_("Wallet Liability (+)"))

        elif self.transaction_type == "refund":
            _add_line(liability_acc, debit=amt, name=_("Wallet Liability (-)"))
            _add_line(counterpart_acc, credit=amt, name=_("Wallet Refund"))

        elif self.transaction_type == "adjust_in":
            _add_line(counterpart_acc, debit=amt, name=_("Wallet Adjustment In"))
            _add_line(liability_acc, credit=amt, name=_("Wallet Liability (+) [Adjust]"))

        elif self.transaction_type == "adjust_out":
            _add_line(liability_acc, debit=amt, name=_("Wallet Liability (-) [Adjust]"))
            _add_line(counterpart_acc, credit=amt, name=_("Wallet Adjustment Out"))

        elif self.transaction_type == "redeem":
            # Hanya jika diaktifkan lewat setting; mapping default:
            # Debit Liability, Credit Counterpart (mis. clearing)
            _add_line(liability_acc, debit=amt, name=_("Wallet Liability (-) [Redeem]"))
            _add_line(counterpart_acc, credit=amt, name=_("Wallet Redeem (Clearing)"))

        else:
            raise UserError(_("Unsupported transaction type for accounting."))

        move = self.env["account.move"].create(move_vals)
        move.action_post()
        _logger.info("Wallet TX Journal created: tx=%s move=%s", self.name, move.name)
        return move

    def _get_counterpart_account(self, journal):
        """Resolve transaction counterpart from company-owned Wallet Settings."""
        self.ensure_one()
        company = self.wallet_id.company_id
        if self.transaction_type in ("topup", "refund"):
            account = journal.default_account_id
        elif self.transaction_type == "adjust_in":
            account = company.account_wallet_adjust_in_id or journal.default_account_id
        elif self.transaction_type == "adjust_out":
            account = company.account_wallet_adjust_out_id or journal.default_account_id
        elif self.transaction_type == "redeem":
            account = company.account_wallet_redeem_clearing_id or journal.default_account_id
        else:
            account = journal.default_account_id
        return account or self._fallback_general_account(company)

    def _fallback_general_account(self, company):
        acc = self.env["account.account"].with_company(company).search([
            ("company_ids", "in", [company.id]),
            ("active", "=", True),
            ("account_type", "in", ("asset_cash", "asset_current")),
        ], limit=1)
        if not acc:
            raise UserError(_("No suitable counterpart account found; please configure Accounts in Settings."))
        return acc

    def _build_move_ref(self):
        parts = [
            self.name or "",
            self.reference or "",
            self.transaction_type or "",
            self.wallet_id and self.wallet_id.name or "",
        ]
        return " / ".join([p for p in parts if p])

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _temp_name(self, vals=None):
        wallet_id = None
        if vals and vals.get("wallet_id"):
            wallet_id = vals["wallet_id"]
        return "WALTX/%s/%s" % (wallet_id or "NEW", datetime.now().strftime("%Y%m%d%H%M%S"))

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("amount")
    def _check_amount_positive(self):
        for rec in self:
            if rec.amount is None or rec.amount <= 0:
                raise ValidationError(_("Amount must be greater than zero."))

    @api.constrains("currency_id")
    def _check_currency_wallet(self):
        for rec in self:
            if rec.currency_id != rec.wallet_id.currency_id:
                raise ValidationError(_("Transaction currency must match wallet currency."))

    @api.constrains("company_id")
    def _check_company_wallet(self):
        for rec in self:
            if rec.company_id != rec.wallet_id.company_id:
                raise ValidationError(_("Transaction company must match wallet company."))

    # -------------------------------------------------------------------------
    # ACCESS SHORTCUTS
    # -------------------------------------------------------------------------
    def _ensure_adjustment_rights(self):
        """Hanya Manager yang boleh melakukan adjustment in/out."""
        user = self.env.user
        if not self.env.su and not user.has_group("clinic_wallet.group_wallet_manager"):
            raise AccessError(_("You need Wallet Manager rights to perform adjustments."))

    # -------------------------------------------------------------------------
    # PUBLIC SHORTCUTS (untuk wizard / portal / api)
    # -------------------------------------------------------------------------
    def do_topup(self):
        for rec in self:
            if rec.transaction_type != "topup":
                raise UserError(_("Transaction type mismatch: expected TOPUP."))
            rec.action_post()
        return True

    def do_refund(self):
        for rec in self:
            if rec.transaction_type != "refund":
                raise UserError(_("Transaction type mismatch: expected REFUND."))
            rec.action_post()
        return True

    def do_adjust_in(self):
        self._ensure_adjustment_rights()
        for rec in self:
            if rec.transaction_type != "adjust_in":
                raise UserError(_("Transaction type mismatch: expected ADJUST IN."))
            rec.action_post()
        return True

    def do_adjust_out(self):
        self._ensure_adjustment_rights()
        for rec in self:
            if rec.transaction_type != "adjust_out":
                raise UserError(_("Transaction type mismatch: expected ADJUST OUT."))
            rec.action_post()
        return True

    # -------------------------------------------------------------------------
    # SMART BUTTON / ACTIONS
    # -------------------------------------------------------------------------
    def action_view_wallet(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Wallet"),
            "res_model": "clinic.wallet",
            "view_mode": "form",
            "res_id": self.wallet_id.id,
            "target": "current",
        }

    def action_view_move(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Wallet Journal Entry"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
            "target": "current",
        }

    def action_open_self(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Wallet Transaction"),
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }




