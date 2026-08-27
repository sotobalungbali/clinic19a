# -*- coding: utf-8 -*-
# ClinicOne — clinic_wallet
# File: models/wallet.py
# License: LGPL-3.0
import logging
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError

_logger = logging.getLogger(__name__)


class ClinicWallet(models.Model):
    """
    Dompet prabayar milik pasien (partner) di setiap company.
    Saldo dihitung dari agregat transaksi (topup, redeem, adjustment, refund).

    Integrasi lintas-modul:
    - clinic_patient: patient_id (opsional; fallback ke partner_id)
    - clinic_membership: membership_tier (opsional via related)
    - clinic_billing / clinic_accounting / clinic_ar: method helper reserve/release/validate
    - clinic_portal: summary field + smart action ke transaksi
    - clinic_pricing: disiapkan hook untuk bonus topup by tier/seasonal
    """
    _name = "clinic.wallet"
    _description = "Clinic Wallet"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "partner_id, company_id"
    _rec_name = "display_name"
    _check_company_auto = True

    # --- Identity & Ownership ---
    name = fields.Char(
        string="Wallet Number",
        copy=False,
        index=True,
        default="/",
        help="Nomor unik dompet. Diisi dari sequence saat create."
    )
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True
    )
    active = fields.Boolean(default=True, tracking=True)

    partner_id = fields.Many2one(
        "res.partner",
        string="Patient/Customer",
        required=True,
        index=True,
        tracking=True,
        domain=[("parent_id", "=", False)],
        help="Pemilik dompet (pasien utama)."
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        index=True,
        help="Relasi langsung ke entitas pasien (jika modul clinic_patient terpasang).",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
        help="Mata uang dompet. Default mengikuti company."
    )

    # --- Status & Validity ---
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("open", "Active"),
            ("suspended", "Suspended"),
            ("closed", "Closed"),
        ],
        default="draft",
        tracking=True,
        index=True
    )
    issue_date = fields.Date(
        string="Issue Date",
        default=fields.Date.context_today
    )
    expiry_date = fields.Date(
        string="Expiry Date",
        help="Tanggal kadaluarsa saldo default (bisa override per transaksi)."
    )
    expiry_policy = fields.Selection(
        [
            ("block", "Block usage on expiry"),
            ("warn", "Warn only"),
            ("none", "No expiry control"),
        ],
        default="warn",
        string="Expiry Policy",
        help="Kebijakan saat wallet melewati expiry_date."
    )

    # --- Rules & Transactions ---
    rule_ids = fields.One2many(
        "clinic.wallet.rule", "wallet_id",
        string="Usage Rules"
    )
    transaction_ids = fields.One2many(
        "clinic.wallet.transaction", "wallet_id",
        string="Transactions",
        readonly=True
    )

    # --- Balances (computed) ---
    balance = fields.Monetary(
        string="Available Balance",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True
    )
    reserved_amount = fields.Monetary(
        string="Reserved",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Dana yang sudah dicadangkan untuk billing yang belum diposting."
    )
    total_topup = fields.Monetary(
        string="Total Top-Up",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True
    )
    total_redeem = fields.Monetary(
        string="Total Redeem",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True
    )
    total_refund = fields.Monetary(
        string="Total Refund",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True
    )
    last_transaction_date = fields.Datetime(
        string="Last Transaction",
        compute="_compute_amounts",
        store=True
    )

    # --- Insights / Convenience ---
    membership_tier_id = fields.Many2one(
        "membership.plan",
        string="Membership Plan / Tier",
        compute="_compute_membership_tier",
        store=False,
        help="Active membership plan exposed under the legacy compatibility field name.",
    )
    notes = fields.Text(string="Notes")

    # --- Odoo 19 SQL constraint API ---
    _uniq_partner_company = models.Constraint(
        "UNIQUE(partner_id, company_id)",
        "Each partner can only have a single wallet per company.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends(
        "partner_id",
        "company_id",
        "name",
    )
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "[%s] %s - %s" % (
                (rec.name or "/"),
                rec.partner_id.display_name or _("Unknown"),
                rec.company_id.display_name or _("No Company"),
            )

    @api.depends(
        "transaction_ids.state",
        "transaction_ids.amount",
        "transaction_ids.amount_signed",
        "transaction_ids.is_reserved",
        "transaction_ids.date",
        "transaction_ids.transaction_type",
        "transaction_ids.currency_id",
    )
    def _compute_amounts(self):
        """
        Hitung saldo dompet dari transaksi yang telah disetujui/posted.
        - amount_signed: +topup/adjust_in, -redeem/adjust_out, -refund (kembali ke pasien).
        - reserved: transaksi draft/reserved yang mengikat dana sementara.
        """
        for rec in self:
            posted = [t for t in rec.transaction_ids if t.state == "posted"]
            reserved = [t for t in rec.transaction_ids if t.is_reserved and t.state in ("draft", "reserved")]

            # Agregasi
            total = sum(t.amount_signed for t in posted)
            total_topup = sum(t.amount_signed for t in posted if t.transaction_type == "topup" and t.amount_signed > 0)
            total_redeem = -sum(t.amount_signed for t in posted if t.transaction_type == "redeem" and t.amount_signed < 0)
            total_refund = -sum(t.amount_signed for t in posted if t.transaction_type == "refund" and t.amount_signed < 0)
            reserved_amt = sum(t.amount for t in reserved if t.currency_id == rec.currency_id)

            rec.total_topup = total_topup
            rec.total_redeem = total_redeem
            rec.total_refund = total_refund
            rec.reserved_amount = reserved_amt
            rec.balance = total - reserved_amt
            rec.last_transaction_date = posted and max(t.date for t in posted) or False

    def _compute_membership_tier(self):
        """
        Expose the active membership plan using the historical compatibility
        field name ``membership_tier_id``.

        ClinicOne membership V6 owns tier semantics on ``membership.plan``
        through ``membership.contract.plan_id``. Keeping this field name
        preserves downstream Billing/Wallet rule APIs without reviving the
        removed ``clinic.membership.tier`` model.
        """
        for rec in self:
            contract = False
            if rec.patient_id and "membership_active_contract_id" in rec.patient_id._fields:
                contract = rec.patient_id.membership_active_contract_id
            if not contract and rec.partner_id and "membership_active_contract_id" in rec.partner_id._fields:
                contract = rec.partner_id.membership_active_contract_id
            rec.membership_tier_id = contract.plan_id if contract else False

    # -------------------------------------------------------------------------
    # ONCHANGE / DEFAULTS
    # -------------------------------------------------------------------------
    @api.onchange("partner_id", "company_id")
    def _onchange_partner_company(self):
        """Samakan currency dengan company untuk konsistensi."""
        for rec in self:
            rec.currency_id = rec.company_id.currency_id

    # -------------------------------------------------------------------------
    # CREATE / WRITE / UNLINK
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Create wallets with deterministic sequence and company defaults."""
        for vals in vals_list:
            if not self.env.su and not self.env.user.has_group("clinic_wallet.group_wallet_manager"):
                # Callers may create a wallet, but workflow state is chosen by the
                # company policy below, never by arbitrary RPC payload.
                vals["state"] = "draft"
            company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
            vals.setdefault("company_id", company.id)
            vals.setdefault("currency_id", company.currency_id.id)
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = self.env["ir.sequence"].sudo().next_by_code("clinic.wallet") or self._default_temp_name(vals)
            vals.setdefault("expiry_policy", company.wallet_default_expiry_policy or "warn")
            if not vals.get("expiry_date") and company.wallet_default_expiry_months:
                issue = fields.Date.to_date(vals.get("issue_date") or fields.Date.context_today(self))
                vals["expiry_date"] = issue + relativedelta(months=company.wallet_default_expiry_months)
        recs = super().create(vals_list)
        # Opening on create is a system default, not a manager button action.
        for rec in recs:
            if rec.state == "draft" and rec.company_id.wallet_auto_open_on_create:
                rec.with_context(wallet_state_transition=True).write({"state": "open"})
        return recs

    def write(self, vals):
        # Workflow state is model-protected: hiding buttons is not security.
        if "state" in vals and not self.env.context.get("wallet_state_transition"):
            if not self.env.su and not self.env.user.has_group("clinic_wallet.group_wallet_manager"):
                raise AccessError(_("Only Wallet Managers can change wallet status."))
        # Monetary ownership becomes immutable once the wallet has a ledger.
        identity_fields = {"company_id", "partner_id", "patient_id", "currency_id"} & set(vals)
        if identity_fields:
            for rec in self:
                if rec.transaction_ids:
                    raise ValidationError(_("Wallet owner, company, patient link, and currency cannot change after transactions exist."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.transaction_ids:
                raise UserError(_("Can't delete wallet with transactions. Consider closing it instead."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS (STATE)
    # -------------------------------------------------------------------------
    def action_open(self):
        self._check_access_manager()
        for rec in self:
            if rec.state in ("draft", "suspended"):
                rec.with_context(wallet_state_transition=True).write({"state": "open"})
        return True

    def action_suspend(self):
        self._check_access_manager()
        for rec in self:
            if rec.state == "open":
                rec.with_context(wallet_state_transition=True).write({"state": "suspended"})
        return True

    def action_close(self):
        self._check_access_manager()
        for rec in self:
            if rec.currency_id.compare_amounts(rec.balance, 0.0) != 0:
                raise UserError(_("Wallet balance must be zero before closing."))
            if rec.currency_id.compare_amounts(rec.reserved_amount, 0.0) != 0:
                raise UserError(_("Release all reserved funds before closing the wallet."))
            rec.with_context(wallet_state_transition=True).write({"state": "closed"})
        return True

    # -------------------------------------------------------------------------
    # PUBLIC API (used by Billing / Portal / Wizards)
    # -------------------------------------------------------------------------
    def ensure_usable(self, amount=0.0, date=None):
        """
        Validasi siap pakai:
        - state open
        - belum expired (atau sesuai policy)
        - saldo cukup (jika amount > 0)
        """
        for rec in self:
            if rec.state != "open":
                raise UserError(_("Wallet is not active (state: %s).") % rec.state)
            if rec._is_expired(date=date):
                if rec.expiry_policy == "block":
                    raise UserError(_("Wallet is expired."))
                elif rec.expiry_policy == "warn":
                    # beri activity ke manager, tidak menghalangi
                    rec._notify_expiry_warning()
            if amount and rec.balance < amount:
                raise UserError(_("Insufficient wallet balance."))

    def reserve_funds(self, amount, reference=None, billing_model=None, billing_id=None):
        """
        Cadangkan dana untuk dokumen billing (invoice/receipt/order) sebelum final posting.
        Menghasilkan draft/reserved transaction (is_reserved=True).
        """
        self.ensure_one()
        self._lock_for_update()
        self.ensure_usable(amount=amount)
        if amount <= 0:
            raise ValidationError(_("Reserved amount must be greater than zero."))

        Tx = self.env["clinic.wallet.transaction"].sudo()
        vals = {
            "wallet_id": self.id,
            "transaction_type": "redeem",
            "amount": amount,
            "is_reserved": True,
            "reference": reference or "",
            "billing_model": billing_model or "",
            "billing_id": billing_id or False,
            "state": "reserved",
            "date": fields.Datetime.now(),
        }
        tx = Tx.create(vals)
        _logger.info("Reserved wallet funds: wallet=%s amount=%s ref=%s", self.name, amount, reference)
        # recompute balance via depends
        return tx

    def release_reserved(self, reference=None, billing_model=None, billing_id=None):
        """
        Lepaskan seluruh reservasi yang cocok untuk dokumen tertentu.
        """
        self.ensure_one()
        domain = [
            ("wallet_id", "=", self.id),
            ("is_reserved", "=", True),
            ("state", "in", ("draft", "reserved")),
        ]
        if reference:
            domain.append(("reference", "=", reference))
        if billing_model:
            domain.append(("billing_model", "=", billing_model))
        if billing_id:
            domain.append(("billing_id", "=", billing_id))

        txs = self.env["clinic.wallet.transaction"].sudo().search(domain)
        for tx in txs:
            tx.action_cancel()
        _logger.info("Released reserved wallet funds: wallet=%s count=%s", self.name, len(txs))
        return True

    def validate_reserved_to_posted(self, amount, reference=None, billing_model=None, billing_id=None):
        """
        Konversi reservasi menjadi transaksi posted (redeem final).
        - Jika beberapa reservasi, ambil sesuai reference/billing; jika kurang, error.
        - Akan set is_reserved=False, state=posted pada transaksi terlibat.
        """
        self.ensure_one()
        self._lock_for_update()
        # Reserved funds already reduced available balance when the reservation was made.
        # Re-check state/expiry here, but do not subtract the same reservation twice.
        self.ensure_usable()

        domain = [
            ("wallet_id", "=", self.id),
            ("is_reserved", "=", True),
            ("state", "in", ("draft", "reserved")),
        ]
        if reference:
            domain.append(("reference", "=", reference))
        if billing_model:
            domain.append(("billing_model", "=", billing_model))
        if billing_id:
            domain.append(("billing_id", "=", billing_id))

        txs = self.env["clinic.wallet.transaction"].sudo().search(domain, order="date asc")
        reserved_total = sum(t.amount for t in txs if t.currency_id == self.currency_id)
        if reserved_total + 1e-6 < amount:
            raise UserError(_("Reserved amount (%s) is less than required (%s).") % (reserved_total, amount))

        remaining = amount
        for tx in txs:
            if remaining <= 0:
                break
            take = min(tx.amount, remaining)
            if take < tx.amount:
                # split transaction
                tx.split_reserved(take_amount=take)
                # original tx tetap reserved dengan sisa amount
                conv = self.env["clinic.wallet.transaction"].sudo().search([
                    ("origin_reserved_id", "=", tx.id),
                    ("is_reserved", "=", False),
                    ("state", "=", "draft"),
                ], limit=1, order="id desc")
                if conv:
                    conv.action_post()
            else:
                # Keep the reservation flag through the posting pre-check so the
                # same reserved amount is not counted twice. action_post()
                # performs the trusted transition to posted/unreserved.
                tx.action_post()
            remaining -= take

        _logger.info("Posted reserved redemption: wallet=%s amount=%s", self.name, amount)
        return True

    # -------------------------------------------------------------------------
    # HELPERS / RULES / EXPIRY
    # -------------------------------------------------------------------------
    def _is_expired(self, date=None):
        """Periksa kadaluarsa pada tanggal tertentu (default: today)."""
        self.ensure_one()
        if not self.expiry_date:
            return False
        date = date or fields.Date.context_today(self)
        return fields.Date.from_string(date) > fields.Date.from_string(self.expiry_date)

    def _notify_expiry_warning(self):
        """Buat activity ke manager saat penggunaan pada wallet yang sudah melewati expiry (policy warn)."""
        self.ensure_one()
        try:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Wallet used after expiry"),
                user_id=self.env.user.id,
                note=_("Wallet %s used after expiry policy=warn.") % (self.display_name,),
            )
        except Exception as e:
            _logger.debug("Skipping expiry activity (non-critical): %s", e)

    @api.model
    def _cron_expiry_notify(self):
        """Queue company-scoped expiry reminders without global configuration leakage."""
        today = fields.Date.context_today(self)
        template = self.env.ref("clinic_wallet.mail_tmpl_wallet_expiry", raise_if_not_found=False)
        sent = 0
        companies = self.env["res.company"].sudo().search([])
        for company in companies:
            pre_days = max(company.wallet_expiry_notify_days_before or 0, 0)
            post_days = max(company.wallet_expiry_notify_days_after or 0, 0)
            pre_date = fields.Date.to_date(today) + timedelta(days=pre_days)
            post_date = fields.Date.to_date(today) - timedelta(days=post_days)
            wallets = self.sudo().search([
                ("company_id", "=", company.id),
                ("state", "in", ("open", "suspended")),
                ("expiry_date", "!=", False),
                ("expiry_date", "<=", pre_date),
                ("expiry_date", ">=", post_date),
                ("active", "=", True),
            ])
            if not template:
                continue
            for wallet in wallets.filtered(lambda item: bool(item.partner_id.email)):
                with self.env.cr.savepoint():
                    template.sudo().send_mail(wallet.id, force_send=False, raise_exception=False)
                    sent += 1
        if sent:
            _logger.info("Wallet expiry reminders queued: %s", sent)
        return sent

    # -------------------------------------------------------------------------
    # UI ACTIONS
    # -------------------------------------------------------------------------
    def action_view_transactions(self):
        self.ensure_one()
        action = self.env.ref("clinic_wallet.action_wallet_transactions", raise_if_not_found=False)
        if not action:
            return False
        result = action.read()[0]
        result["domain"] = [("wallet_id", "=", self.id)]
        result["context"] = {"default_wallet_id": self.id}
        return result

    # -------------------------------------------------------------------------
    # ACCESS CONTROL SHORTCUTS
    # -------------------------------------------------------------------------
    def _check_access_manager(self):
        """
        Pastikan hanya Manager yang boleh mengubah state kritikal.
        Group didefinisikan di security/clinic_wallet_groups.xml:
        - clinic_wallet.group_wallet_manager
        """
        user = self.env.user
        if not user.has_group("clinic_wallet.group_wallet_manager"):
            raise AccessError(_("You need Wallet Manager rights to perform this action."))

    # -------------------------------------------------------------------------
    # UTIL & FALLBACK
    # -------------------------------------------------------------------------
    @api.model
    def _default_temp_name(self, vals=None):
        """Fallback name jika sequence belum tersedia saat awal instalasi."""
        partner = None
        company = None
        if vals:
            partner = self.env["res.partner"].browse(vals.get("partner_id")) if vals.get("partner_id") else None
            company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
        return "WALLET/%s/%s" % (
            (partner and partner.id) or "NEW",
            (company and company.id) or "C",
        )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("partner_id", "company_id")
    def _check_unique_per_partner_company(self):
        for rec in self:
            dom = [("id", "!=", rec.id), ("partner_id", "=", rec.partner_id.id), ("company_id", "=", rec.company_id.id)]
            if self.search_count(dom):
                raise ValidationError(_("This partner already has a wallet in this company."))

    @api.constrains("expiry_date", "issue_date")
    def _check_dates(self):
        for rec in self:
            if rec.expiry_date and rec.issue_date and rec.expiry_date < rec.issue_date:
                raise ValidationError(_("Expiry date must be on or after the issue date."))

    # -------------------------------------------------------------------------
    # HOOKS FOR INTEGRATION (OPTIONAL)
    # -------------------------------------------------------------------------
    def get_liability_account(self):
        """Return the configured wallet liability account for this company."""
        self.ensure_one()
        account = self.company_id.account_wallet_liability_id
        if account and account.active:
            return account
        account = self.env["account.account"].with_company(self.company_id).search([
            ("company_ids", "in", [self.company_id.id]),
            ("active", "=", True),
            ("account_type", "in", ("liability_current", "liability_non_current")),
        ], limit=1)
        if not account:
            raise UserError(_("Please configure a Wallet Liability Account in Wallet Settings."))
        return account

    def get_wallet_journal(self):
        """Return the configured wallet journal, with a company-safe fallback."""
        self.ensure_one()
        journal = self.company_id.wallet_journal_id
        if journal and journal.company_id == self.company_id:
            return journal
        journal = self.env["account.journal"].search([
            ("company_id", "=", self.company_id.id),
            ("type", "in", ("bank", "cash", "general")),
        ], limit=1)
        if not journal:
            raise UserError(_("Please configure a Wallet Journal in Wallet Settings."))
        return journal

    def _lock_for_update(self):
        """Serialize monetary decisions per wallet to avoid concurrent overspend."""
        if not self.ids:
            return True
        self.flush_recordset()
        self.env.cr.execute(
            "SELECT id FROM clinic_wallet WHERE id = ANY(%s) FOR UPDATE",
            [self.ids],
        )
        # Values may have changed while waiting on the row lock. Invalidate the
        # monetary cache before the caller performs a balance decision.
        self.invalidate_recordset(["balance", "reserved_amount", "total_topup", "total_redeem", "total_refund"])
        return True

    @api.constrains("currency_id", "company_id")
    def _check_company_currency(self):
        for rec in self:
            if rec.currency_id and rec.company_id and rec.currency_id != rec.company_id.currency_id:
                raise ValidationError(_(
                    "Wallet currency must match the company currency. "
                    "ClinicOne Wallet posts accounting in company currency."
                ))

    # -------------------------------------------------------------------------
    # NAME GET
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            name = "%s · %s" % (rec.name, rec.partner_id.display_name)
            res.append((rec.id, name))
        return res



