# -*- coding: utf-8 -*-
# ClinicOne — clinic_wallet
# File: models/wallet_rule.py
# License: LGPL-3.0
import logging
from datetime import datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError

_logger = logging.getLogger(__name__)


class ClinicWalletRule(models.Model):
    """
    Aturan penggunaan dompet (wallet) untuk mengendalikan konsumsi saldo:
    - Scope: global / product category / product
    - Filter: membership tier (opsional), partner tag (opsional)
    - Window: tanggal mulai/akhir, hari dalam minggu, jam (opsional)
    - Limit: min/max per transaksi, kuota harian & bulanan (amount & count)
    - Kebijakan expiry: auto-nonaktif ketika lewat date_end (cron)
    
    Catatan Integrasi:
    - clinic_wallet.transaction akan memanggil rule._check_transaction(tx)
      hanya untuk transaksi yang MENGURANGI saldo: redeem/refund/adjust_out.
    - Untuk membership tier/partner tags: field ini opsional (tidak wajib modul lain).
    """
    _name = "clinic.wallet.rule"
    _description = "Clinic Wallet Usage Rule"
    _order = "sequence, id"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & linkage
    # -------------------------------------------------------------------------
    name = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, index=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    wallet_id = fields.Many2one(
        "clinic.wallet",
        string="Wallet",
        ondelete="cascade",
        index=True,
        help="Kosongkan bila rule ini bersifat template (global). Jika diisi, hanya berlaku utk wallet tsb.",
    )

    # -------------------------------------------------------------------------
    # Scope & Filters
    # -------------------------------------------------------------------------
    scope = fields.Selection(
        [
            ("global", "Global"),
            ("category", "Product Category"),
            ("product", "Specific Product"),
        ],
        default="global",
        required=True,
        index=True,
        help="Menentukan cakupan item yang diawasi oleh rule."
    )
    product_category_ids = fields.Many2many(
        "product.category",
        "clinic_wallet_rule_product_category_rel",
        "rule_id",
        "categ_id",
        string="Allowed Categories",
        help="Jika scope=category, transaksi harus memiliki category yang termasuk daftar ini."
    )
    product_ids = fields.Many2many(
        "product.product",
        "clinic_wallet_rule_product_rel",
        "rule_id",
        "product_id",
        string="Allowed Products",
        help="Jika scope=product, transaksi harus memiliki produk yang termasuk daftar ini."
    )

    # Membership V6 owns tier semantics on membership.plan.
    membership_tier_ids = fields.Many2many(
        "membership.plan",
        "clinic_wallet_rule_membership_tier_rel",
        "rule_id",
        "tier_id",
        string="Allowed Membership Plans / Tiers",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
        help="If set, the wallet owner's active membership plan must match.",
    )
    # Partner tags (res.partner.category) untuk whitelist/blacklist ringan
    partner_category_ids = fields.Many2many(
        "res.partner.category",
        "clinic_wallet_rule_partner_category_rel",
        "rule_id",
        "category_id",
        string="Required Partner Tags",
        help="Jika diisi, partner harus memiliki setidaknya salah satu tag ini."
    )
    blacklist_partner_ids = fields.Many2many(
        "res.partner",
        "clinic_wallet_rule_blacklist_partner_rel",
        "rule_id",
        "partner_id",
        string="Blacklist Partners",
        help="Transaksi dari partner dalam daftar ini akan ditolak."
    )

    # -------------------------------------------------------------------------
    # Time window (date range, weekday, hour-of-day)
    # -------------------------------------------------------------------------
    date_start = fields.Date(string="Start Date")
    date_end = fields.Date(string="End Date")
    weekdays = fields.Selection(
        [
            ("mon", "Mon"), ("tue", "Tue"), ("wed", "Wed"),
            ("thu", "Thu"), ("fri", "Fri"), ("sat", "Sat"), ("sun", "Sun")
        ],
        string="Allowed Weekday",
        help="Opsional: jika diisi, hanya berlaku pada hari ini saja."
    )
    time_start = fields.Float(
        string="Start Time (HH:MM)",
        help="Opsional: Jam mulai (dalam jam desimal, misal 8.5=08:30)."
    )
    time_end = fields.Float(
        string="End Time (HH:MM)",
        help="Opsional: Jam akhir (dalam jam desimal, misal 17.0=17:00)."
    )

    # -------------------------------------------------------------------------
    # Limits
    # -------------------------------------------------------------------------
    # Per-transaction
    min_amount = fields.Monetary(currency_field="currency_id", string="Min Amount / Tx")
    max_amount = fields.Monetary(currency_field="currency_id", string="Max Amount / Tx")

    # Daily caps
    daily_amount_limit = fields.Monetary(currency_field="currency_id", string="Daily Amount Limit")
    daily_tx_limit = fields.Integer(string="Daily Tx Count Limit")

    # Monthly caps
    monthly_amount_limit = fields.Monetary(currency_field="currency_id", string="Monthly Amount Limit")
    monthly_tx_limit = fields.Integer(string="Monthly Tx Count Limit")

    # % terhadap nilai dokumen (opsional; dipakai jika billing meneruskan nilai dokumen)
    max_ratio_per_invoice = fields.Float(
        string="Max Ratio per Billing (%)",
        help="Batasi redeem max sekian % dari nilai dokumen terkait (jika reference billing tersedia)."
    )

    # Currency
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
        required=True,
    )

    # -------------------------------------------------------------------------
    # State & Insights
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("upcoming", "Upcoming"),
            ("active", "Active"),
            ("expired", "Expired"),
        ],
        compute="_compute_state",
        store=True,
    )
    last_violation_note = fields.Text(readonly=True)
    color = fields.Integer(
        help="UI helper (kanban/color)."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("active", "date_start", "date_end")
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.active:
                rec.state = "expired" if rec.date_end and rec.date_end < today else "upcoming"
                continue
            if rec.date_start and today < rec.date_start:
                rec.state = "upcoming"
            elif rec.date_end and today > rec.date_end:
                rec.state = "expired"
            else:
                rec.state = "active"

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("min_amount", "max_amount")
    def _check_min_max(self):
        for rec in self:
            if rec.min_amount and rec.max_amount and rec.min_amount > rec.max_amount:
                raise ValidationError(_("Min amount cannot be greater than Max amount."))

    @api.constrains("time_start", "time_end")
    def _check_time_window(self):
        for rec in self:
            if rec.time_start and (rec.time_start < 0.0 or rec.time_start >= 24.0):
                raise ValidationError(_("Start time must be within [0, 24)."))
            if rec.time_end and (rec.time_end <= 0.0 or rec.time_end > 24.0):
                raise ValidationError(_("End time must be within (0, 24]."))
            if rec.time_start and rec.time_end and rec.time_start >= rec.time_end:
                raise ValidationError(_("Start time must be earlier than End time."))

    # -------------------------------------------------------------------------
    # PUBLIC API (dipanggil dari wallet_transaction._check_rules)
    # -------------------------------------------------------------------------
    def _check_transaction(self, tx):
        """
        Validasi transaksi 'tx' terhadap rule ini.
        Hanya dipanggil untuk transaksi pengurang saldo (redeem/refund/adjust_out).
        Harus raise UserError jika tidak lolos.
        """
        self.ensure_one()
        # 0) Filter awal: rule aktif & company cocok
        if not self.active:
            return True
        if tx.company_id != self.company_id:
            return True  # ignore, beda company

        # 1) Jika rule terikat ke wallet tertentu
        if self.wallet_id and self.wallet_id.id != tx.wallet_id.id:
            return True  # ignore rule lain

        # 2) Blacklist partner
        if tx.partner_id and self.blacklist_partner_ids and tx.partner_id.id in self.blacklist_partner_ids.ids:
            self._raise(tx, _("Partner is blacklisted by rule: %s") % self.name)

        # 3) Membership tier (opsional)
        if self.membership_tier_ids:
            tier = tx.wallet_id.membership_tier_id
            if not tier or tier.id not in self.membership_tier_ids.ids:
                self._raise(tx, _("This wallet does not match required membership tiers."))

        # 4) Partner tags (opsional, minimal salah satu)
        if self.partner_category_ids and tx.partner_id:
            if not tx.partner_id.category_id or not (set(tx.partner_id.category_id.ids) & set(self.partner_category_ids.ids)):
                self._raise(tx, _("Patient/Partner is missing required tags."))

        # 5) Scope matching (global/category/product)
        if not self._match_scope(tx):
            self._raise(tx, _("Transaction does not match rule scope."))

        # 6) Waktu: tanggal, hari, jam
        self._check_date_time_window(tx)

        # 7) Limit per transaksi
        self._check_per_transaction_limits(tx)

        # 8) Kuota: harian & bulanan (amount & count)
        self._check_quota_limits(tx)

        # 9) Rasio terhadap dokumen billing (opsional)
        self._check_max_ratio_per_invoice(tx)

        return True

    # -------------------------------------------------------------------------
    # MATCH HELPERS
    # -------------------------------------------------------------------------
    def _match_scope(self, tx):
        """Cek kecocokan dengan scope rule."""
        if self.scope == "global":
            return True
        if self.scope == "category":
            if not tx.category_id:
                return False
            return tx.category_id.id in self.product_category_ids.ids if self.product_category_ids else True
        if self.scope == "product":
            if not tx.product_id:
                return False
            return tx.product_id.id in self.product_ids.ids if self.product_ids else True
        return True

    def _check_date_time_window(self, tx):
        """
        Cek rentang tanggal, hari dalam minggu, dan jam (opsional).
        Date dan time window dievaluasi dalam timezone user/context Odoo.
        """
        today = fields.Date.context_today(self)
        local_now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        if self.date_start and today < self.date_start:
            self._raise(tx, _("Rule not yet active (start on %s).") % self.date_start)
        if self.date_end and today > self.date_end:
            self._raise(tx, _("Rule expired on %s.") % self.date_end)

        # weekday check
        if self.weekdays:
            dow = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][local_now.weekday()]
            if dow != self.weekdays:
                self._raise(tx, _("Rule not allowed on this weekday."))

        # time window check
        def _float_to_time(f):
            h = int(f)
            m = int(round((f - h) * 60))
            return time(hour=h, minute=m)

        if self.time_start or self.time_end:
            now_t = local_now.time()
            if self.time_start:
                if now_t < _float_to_time(self.time_start):
                    self._raise(tx, _("Usage not allowed before start time."))
            if self.time_end:
                if now_t > _float_to_time(self.time_end):
                    self._raise(tx, _("Usage not allowed after end time."))

    def _check_per_transaction_limits(self, tx):
        """Cek min/max per transaksi terhadap tx.amount."""
        amt = tx.amount or 0.0
        if self.min_amount and amt + 1e-9 < self.min_amount:
            self._raise(tx, _("Amount is below rule minimum per transaction."))
        if self.max_amount and amt - 1e-9 > self.max_amount:
            self._raise(tx, _("Amount exceeds rule maximum per transaction."))

    def _check_quota_limits(self, tx):
        """
        Cek kuota harian & bulanan:
        - Total AMOUNT posted + current tx.amount tidak boleh melebihi limit
        - COUNT transaksi posted + current tx (1) tidak boleh melebihi limit
        Hanya menghitung transaksi yang:
        - wallet sama, state='posted', transaction_type dalam (redeem/refund/adjust_out)
        - opsional: match scope (category/product) agar adil
        """
        Tx = self.env["clinic.wallet.transaction"].sudo()

        # domain dasar
        dom_base = [
            ("wallet_id", "=", tx.wallet_id.id),
            ("state", "=", "posted"),
            ("transaction_type", "in", ("redeem", "refund", "adjust_out")),
        ]
        # batasi sesuai scope rule agar konsisten
        if self.scope == "category" and self.product_category_ids:
            dom_base += [("category_id", "in", self.product_category_ids.ids)]
        if self.scope == "product" and self.product_ids:
            dom_base += [("product_id", "in", self.product_ids.ids)]

        # HARIAN
        if self.daily_amount_limit or self.daily_tx_limit:
            start_day = fields.Datetime.to_string(datetime.combine(fields.Date.context_today(self), time.min))
            end_day = fields.Datetime.to_string(datetime.combine(fields.Date.context_today(self), time.max))
            dom_day = dom_base + [("date", ">=", start_day), ("date", "<=", end_day)]
            day_recs = Tx.search(dom_day)
            day_amount = sum(r.amount for r in day_recs if r.currency_id == tx.currency_id)
            day_count = len(day_recs)
            # include current tx
            if self.daily_amount_limit and (day_amount + tx.amount - 1e-9) > self.daily_amount_limit:
                self._raise(tx, _("Daily amount limit exceeded by this transaction."))
            if self.daily_tx_limit and (day_count + 1) > self.daily_tx_limit:
                self._raise(tx, _("Daily transaction count limit exceeded."))

        # BULANAN
        if self.monthly_amount_limit or self.monthly_tx_limit:
            today = fields.Date.context_today(self)
            month_start = today.replace(day=1)
            # cari awal bulan berikutnya lalu minus satu micro detik
            if month_start.month == 12:
                next_start = month_start.replace(year=month_start.year + 1, month=1)
            else:
                next_start = month_start.replace(month=month_start.month + 1)
            start_month = fields.Datetime.to_string(datetime.combine(month_start, time.min))
            end_month = fields.Datetime.to_string(datetime.combine(next_start - timedelta(seconds=1), time.max))
            dom_mon = dom_base + [("date", ">=", start_month), ("date", "<=", end_month)]
            mon_recs = Tx.search(dom_mon)
            mon_amount = sum(r.amount for r in mon_recs if r.currency_id == tx.currency_id)
            mon_count = len(mon_recs)
            # include current tx
            if self.monthly_amount_limit and (mon_amount + tx.amount - 1e-9) > self.monthly_amount_limit:
                self._raise(tx, _("Monthly amount limit exceeded by this transaction."))
            if self.monthly_tx_limit and (mon_count + 1) > self.monthly_tx_limit:
                self._raise(tx, _("Monthly transaction count limit exceeded."))

    def _check_max_ratio_per_invoice(self, tx):
        """
        Batasi porsi redeem terhadap nilai dokumen billing (jika diketahui).
        Asumsikan modul billing, bila ada, akan mengisi 'billing_model', 'billing_id',
        dan menyediakan method ringan untuk membaca 'amount_total' (soft-coupling).
        """
        if not self.max_ratio_per_invoice:
            return True
        if not tx.billing_model or not tx.billing_id:
            return True  # tidak ada referensi billing, abaikan

        # Soft-coupling: read a billing total if the referenced model exposes
        # one. Only lookup/read failures are soft; a real ratio violation must
        # never be swallowed by this compatibility boundary.
        try:
            rec = self.env[tx.billing_model].sudo().browse(int(tx.billing_id)).exists()
            total = 0.0
            for field_name in ("amount_total", "amount_residual", "amount_untaxed"):
                if rec and field_name in rec._fields:
                    total = float(rec[field_name] or 0.0)
                    if total:
                        break
        except (KeyError, TypeError, ValueError, AccessError) as exc:
            _logger.debug("Ratio check skipped (billing lookup/read error): %s", exc)
            return True

        if total <= 0:
            return True
        ratio = (tx.amount / total) * 100.0
        if ratio - 1e-9 > self.max_ratio_per_invoice:
            self._raise(tx, _("Redeem exceeds allowed ratio against billing total."))
        return True

    # -------------------------------------------------------------------------
    # CRON
    # -------------------------------------------------------------------------
    @api.model
    def _cron_auto_expire_rules(self):
        """
        Cron harian: nonaktifkan rule yang sudah kadaluarsa (date_end < today).
        Mengembalikan jumlah rule yang dinonaktifkan.
        """
        today = fields.Date.context_today(self)
        rules = self.search([("active", "=", True), ("date_end", "!=", False), ("date_end", "<", today)])
        count = 0
        for r in rules:
            with self.env.cr.savepoint():
                r.active = False
                count += 1
        if count:
            _logger.info("Wallet rules auto-deactivated: %s", count)
        return count

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    def _raise(self, tx, message):
        """Catat pelanggaran pada rule & raise UserError yang ramah pengguna."""
        self.last_violation_note = "[%s] %s" % (tx.name or tx.id, message)
        raise UserError("%s\n\n[%s] %s" % (_("Wallet Rule Violation"), self.name, message))


    def action_activate(self):
        self.write({"active": True})
        return True

    def action_deactivate(self):
        self.write({"active": False})
        return True

    def action_open_self(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Wallet Usage Rule"),
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }



