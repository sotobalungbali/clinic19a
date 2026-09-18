# -*- coding: utf-8 -*-
# ClinicOne — clinic_wallet
# File: models/portal.py
# License: LGPL-3.0
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError

_logger = logging.getLogger(__name__)


# =============================================================================
# Approver list (opsional per company) — untuk alur approval portal request
# =============================================================================
class ClinicWalletPortalMgrApprover(models.Model):
    _name = "clinic.wallet.portal.mgr.approver"
    _description = "Clinic Wallet Portal Approver"
    _order = "company_id, sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True, default="Approver")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda s: s.env.company,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Approver User",
        required=True,
        domain=[("share", "=", False)],  # hanya internal users
    )

    _uniq_company_user = models.Constraint(
        "UNIQUE(company_id, user_id)",
        "Approver already exists for this company.",
    )


# =============================================================================
# Portal Request — diajukan dari portal: TOPUP/REFUND (opsional ADJUST by staff)
# =============================================================================
class ClinicWalletPortalRequest(models.Model):
    """
    Permohonan dari Portal:
    - Tipe: topup / refund
    - Dibuat oleh: portal user (res.users.share=True) / staff via backend
    - Lampiran bukti (misal transfer)
    - Approval: draft -> submitted -> approved/rejected -> done/canceled
    - Opsional: generate account.move (topup/refund) bila disetel 'auto_post_move'
    """
    _name = "clinic.wallet.portal.request"
    _description = "Clinic Wallet Portal Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "name"
    _check_company_auto = True

    # Identity
    name = fields.Char(
        string="Request Number",
        copy=False,
        default="/",
        index=True,
        help="Nomor unik permohonan (sequence)."
    )

    # Context
    request_type = fields.Selection(
        [
            ("topup", "Top-Up"),
            ("refund", "Refund"),
        ],
        required=True,
        default="topup",
        tracking=True,
        index=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("done", "Done"),
            ("canceled", "Canceled"),
        ],
        default="draft",
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda s: s.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda s: s.env.company.currency_id.id,
        index=True,
    )

    # Applicant & Wallet
    partner_id = fields.Many2one(
        "res.partner",
        string="Patient/Customer",
        required=True,
        index=True,
        help="Pemohon (portal user atau diwakilkan staff)."
    )
    wallet_id = fields.Many2one(
        "clinic.wallet",
        string="Wallet",
        required=True,
        domain="[('partner_id','=',partner_id),('company_id','=',company_id)]",
        help="Dompet yang akan di-topup/refund."
    )
    requested_by_user_id = fields.Many2one(
        "res.users",
        string="Requested By",
        default=lambda s: s.env.user,
        help="User yang membuat permohonan (portal/staff)."
    )

    # Amount & Proof
    amount = fields.Monetary(
        string="Amount",
        required=True,
        tracking=True,
        help="Nominal yang diminta (selalu positif)."
    )
    note = fields.Text(string="Note")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_wallet_portal_req_attach_rel",
        "request_id",
        "attachment_id",
        string="Attachments (Proof)",
        help="Unggah bukti (transfer, identitas, dsb.)"
    )

    # Accounting (opsional auto posting)
    auto_post_move = fields.Boolean(
        string="Auto Post Accounting",
        help="Jika aktif: saat Approved → otomatis buat & post account.move (topup/refund)."
    )
    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        readonly=True,
        copy=False,
        help="Jurnal yang dibuat untuk request ini (jika auto_post_move aktif).",
    )
    transaction_id = fields.Many2one(
        "clinic.wallet.transaction",
        string="Wallet Transaction",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        help="Override jurnal default wallet (opsional)."
    )

    # Audit/Approval
    submitted_by = fields.Many2one("res.users", string="Submitted By", readonly=True)
    submitted_on = fields.Datetime(string="Submitted On", readonly=True)
    approved_by = fields.Many2one("res.users", string="Approved By", readonly=True)
    approved_on = fields.Datetime(string="Approved On", readonly=True)
    rejected_by = fields.Many2one("res.users", string="Rejected By", readonly=True)
    rejected_on = fields.Datetime(string="Rejected On", readonly=True)
    done_by = fields.Many2one("res.users", string="Done By", readonly=True)
    done_on = fields.Datetime(string="Done On", readonly=True)

    # Snapshot data (UX pada backend)
    wallet_balance_snapshot = fields.Monetary(
        string="Wallet Balance (At Submit)",
        currency_field="currency_id",
        readonly=True
    )

    # -------------------------------------------------------------------------
    # DEFAULTS / CREATE
    # -------------------------------------------------------------------------
    def _is_external_portal_user(self):
        """Return True only for share/portal users, never for internal staff."""
        user = self.env.user
        return bool(user.share and user.has_group("base.group_portal") and not user.has_group("base.group_user"))

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_wallet.seq_clinic_wallet_portal_request", raise_if_not_found=False)
        external_portal = self._is_external_portal_user()
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = seq and self.env["ir.sequence"].next_by_code("clinic.wallet.portal.request") or "/"
            if external_portal:
                partner = self.env.user.partner_id.commercial_partner_id
                company = self.env.company
                vals.update({
                    "partner_id": partner.id,
                    "company_id": company.id,
                    "currency_id": company.currency_id.id,
                    "requested_by_user_id": self.env.user.id,
                    "state": "draft",
                    "auto_post_move": False,
                })
                wallet = self.env["clinic.wallet"].sudo().browse(vals.get("wallet_id")).exists()
                if not wallet or wallet.partner_id != partner or wallet.company_id != company:
                    raise AccessError(_("You can only request operations for your own wallet."))
        return super().create(vals_list)

    def write(self, vals):
        """Protect workflow/audit fields at ORM level, including direct RPC calls."""
        trusted_transition = self.env.su or self.env.context.get("wallet_request_transition") or self.env.context.get("wallet_portal_transition")
        protected = {
            "state", "move_id", "transaction_id", "submitted_by", "submitted_on",
            "approved_by", "approved_on", "rejected_by", "rejected_on",
            "done_by", "done_on", "wallet_balance_snapshot",
        }
        if protected & set(vals) and not trusted_transition:
            raise AccessError(_("Wallet request workflow fields can only be changed through approved action methods."))
        if self._is_external_portal_user() and not trusted_transition:
            allowed = {"request_type", "wallet_id", "amount", "note", "attachment_ids"}
            forbidden = set(vals) - allowed
            if forbidden:
                raise AccessError(_("Portal users cannot modify approval or accounting fields."))
            if any(rec.state != "draft" for rec in self):
                raise AccessError(_("Submitted wallet requests can no longer be edited from the portal."))
        return super().write(vals)

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("amount")
    def _check_amount_positive(self):
        for rec in self:
            if rec.amount is None or rec.amount <= 0:
                raise ValidationError(_("Amount must be greater than zero."))

    @api.constrains("currency_id", "wallet_id")
    def _check_currency_wallet(self):
        for rec in self:
            if rec.wallet_id and rec.currency_id != rec.wallet_id.currency_id:
                raise ValidationError(_("Request currency must match wallet currency."))

    @api.constrains("company_id", "wallet_id")
    def _check_company_wallet(self):
        for rec in self:
            if rec.wallet_id and rec.company_id != rec.wallet_id.company_id:
                raise ValidationError(_("Request company must match wallet company."))

    # -------------------------------------------------------------------------
    # STATE TRANSITIONS
    # -------------------------------------------------------------------------
    def action_submit(self):
        """
        Portal/Staff mengajukan permohonan:
        - Validasi dasar
        - Catat snapshot saldo
        - Buat activity untuk approver
        """
        for rec in self:
            if rec.state not in ("draft",):
                continue
            rec._validate_before_submit()
            rec.with_context(wallet_portal_transition=True).write({
                "submitted_by": self.env.user.id,
                "submitted_on": fields.Datetime.now(),
                "wallet_balance_snapshot": rec.wallet_id.balance,
            })

            # Buat activity untuk para approver perusahaan
            approvers = self.env["clinic.wallet.portal.mgr.approver"].sudo().search([
                ("company_id", "=", rec.company_id.id),
                ("active", "=", True)
            ], order="sequence, id")
            for ap in approvers:
                try:
                    rec.activity_schedule(
                        "mail.mail_activity_data_todo",
                        user_id=ap.user_id.id,
                        summary=_("Wallet Request Approval Needed"),
                        note=_("Please review request %s (%s %s).") % (rec.name, rec.request_type, rec.amount),
                    )
                except Exception as e:
                    _logger.debug("Skip activity for approver %s: %s", ap.user_id.id, e)

            rec.with_context(wallet_portal_transition=True).write({"state": "submitted"})
        return True

    def action_approve(self):
        """
        Disetujui oleh Manager:
        - TOPUP: buat transaksi wallet topup (posted). Jika auto_post_move, buat jurnal.
        - REFUND: cek saldo cukup → buat transaksi refund (posted). Jika auto_post_move, buat jurnal.
        """
        self._check_manager_rights()
        for rec in self:
            if rec.state != "submitted":
                continue

            # Keamanan dasar
            rec.wallet_id.ensure_usable()  # cek state & expiry (saldo dicek di bawah untuk refund)
            if rec.request_type == "refund" and rec.wallet_id.balance < rec.amount:
                raise UserError(_("Insufficient wallet balance for refund."))

            # Buat transaksi wallet
            Tx = rec.env["clinic.wallet.transaction"].sudo()
            vals = {
                "wallet_id": rec.wallet_id.id,
                "transaction_type": "topup" if rec.request_type == "topup" else "refund",
                "amount": rec.amount,
                "state": "draft",
                "is_reserved": False,
                "reference": rec.name,
                "billing_model": self._name,
                "billing_id": rec.id,
                "journal_id": rec.journal_id.id or False,
                "note": rec.note or "",
            }
            tx = Tx.create(vals)
            tx.action_post()
            rec.with_context(wallet_request_transition=True).write({
                "transaction_id": tx.id,
                "move_id": tx.move_id.id or False,
            })

            # Auto post accounting (redundan utk topup/refund karena action_post sudah buat move);
            # tetap disediakan agar alur tetap konsisten jika konfigurasi berubah.
            if rec.auto_post_move and not tx.move_id:
                try:
                    move = tx._create_account_move()
                    tx.with_context(wallet_tx_transition=True).write({"move_id": move.id})
                except Exception as e:
                    _logger.warning("Auto accounting posting skipped: %s", e)

            rec.with_context(wallet_request_transition=True).write({
                "approved_by": self.env.user.id,
                "approved_on": fields.Datetime.now(),
                "state": "approved",
            })
        return True

    def action_reject(self, reason=None):
        self._check_manager_rights()
        for rec in self:
            if rec.state not in ("submitted",):
                continue
            if reason:
                rec.message_post(body=_("Rejected: %s") % reason)
            rec.with_context(wallet_request_transition=True).write({
                "rejected_by": self.env.user.id,
                "rejected_on": fields.Datetime.now(),
                "state": "rejected",
            })
        return True

    def action_set_done(self):
        """Mark reconciliation complete. This is an internal approval transition."""
        self._check_manager_rights()
        for rec in self:
            if rec.state not in ("approved", "rejected"):
                continue
            rec.with_context(wallet_request_transition=True).write({
                "done_by": self.env.user.id,
                "done_on": fields.Datetime.now(),
                "state": "done",
            })
        return True

    def action_cancel(self):
        """
        Batalkan permohonan (oleh pemohon selama masih draft/submitted).
        """
        for rec in self:
            if rec.state in ("approved", "done"):
                raise UserError(_("Approved/Done request cannot be canceled."))
            if rec._is_external_portal_user() and rec.partner_id != self.env.user.partner_id.commercial_partner_id:
                raise AccessError(_("You can only cancel your own wallet request."))
            rec.with_context(wallet_portal_transition=True).write({"state": "canceled"})
        return True

    # -------------------------------------------------------------------------
    # VALIDATIONS & RIGHTS
    # -------------------------------------------------------------------------
    def _validate_before_submit(self):
        self.ensure_one()
        if self.amount <= 0:
            raise ValidationError(_("Amount must be greater than zero."))
        if self.request_type == "refund" and self.wallet_id.balance < self.amount:
            # Kebijakan default: tidak boleh submit refund > saldo
            raise ValidationError(_("Insufficient wallet balance for refund request."))

    def _check_manager_rights(self):
        """
        Hanya Wallet Manager atau Accounting Manager yang boleh approve/reject.
        """
        user = self.env.user
        if not (user.has_group("clinic_wallet.group_wallet_manager") or user.has_group("account.group_account_manager")):
            raise AccessError(_("You need Wallet Manager or Accounting Manager rights."))

    # -------------------------------------------------------------------------
    # SMART BUTTONS
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

    def action_view_transaction(self):
        self.ensure_one()
        if not self.transaction_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Wallet Transaction"),
            "res_model": "clinic.wallet.transaction",
            "view_mode": "form",
            "res_id": self.transaction_id.id,
            "target": "current",
        }

    def action_view_move(self):
        self.ensure_one()
        if not self.move_id:
            # Coba ambil dari tx yang terkait, bila ada
            tx = self.env["clinic.wallet.transaction"].search([
                ("billing_model", "=", self._name),
                ("billing_id", "=", self.id),
                ("move_id", "!=", False),
            ], limit=1, order="id desc")
            if tx:
                self.with_context(wallet_request_transition=True).write({"move_id": tx.move_id.id})
        if not self.move_id:
            return False
        action = self.env.ref("account.action_move_journal_line", raise_if_not_found=False)
        if not action:
            action = self.env.ref("account.action_move_journal", raise_if_not_found=False)
        if not action:
            return False
        res = action.read()[0]
        res.update({"views": [(False, "form")], "res_id": self.move_id.id})
        return res


# =============================================================================
# M I X I N   untuk bantuan data portal (dipakai controller/portal template)
# =============================================================================
class ClinicWalletPortalMixin(models.AbstractModel):
    _name = "clinic.wallet.portal.mixin"
    _description = "Clinic Wallet Portal Mixin"

    @api.model
    def portal_get_wallet_summary(self, partner_id=None, company_id=None):
        """
        Ringkasan saldo untuk kartu portal:
        - nama wallet, saldo, reserved, last_tx_date
        - 10 transaksi terakhir
        """
        partner = self._portal_get_partner(partner_id)
        company = self._portal_get_company(company_id)
        wallet = partner.wallet_ids.filtered(lambda w: w.company_id == company)[:1]
        if not wallet:
            wallet = partner.get_or_create_wallet(company=company, auto_open=True, ensure_active=True)

        Tx = self.env["clinic.wallet.transaction"].sudo()
        last_txs = Tx.search([
            ("wallet_id", "=", wallet.id),
            ("state", "=", "posted"),
        ], limit=10, order="date desc, id desc")
        return {
            "wallet_name": wallet.name,
            "currency": wallet.currency_id.display_name,
            "balance": wallet.balance,
            "reserved": wallet.reserved_amount,
            "last_transaction_date": wallet.last_transaction_date,
            "last_transactions": [{
                "name": t.name,
                "type": t.transaction_type,
                "amount": t.amount,
                "date": t.date,
                "reference": t.reference,
            } for t in last_txs],
        }

    @api.model
    def portal_submit_request(self, request_type, amount, partner_id=None, company_id=None, note=None, attachment_ids=None, auto_post_move=False):
        """
        Backward-compatible portal service API.

        External portal callers are always forced to their own commercial
        partner/current company and may only use an already-issued wallet.
        Internal staff may explicitly address another patient/company.
        """
        if request_type not in ("topup", "refund"):
            raise ValidationError(_("Unsupported request type."))

        external = self._portal_is_external_user()
        partner = self._portal_get_partner(partner_id)
        company = self._portal_get_company(company_id)

        if external:
            wallet = self.env["clinic.wallet"].search([
                ("partner_id", "=", partner.id),
                ("company_id", "=", company.id),
                ("active", "=", True),
            ], limit=1)
            if not wallet:
                raise UserError(_("No active wallet is available for your patient account."))
            safe_attachment_ids = self._portal_filter_attachment_ids(attachment_ids or [])
            Request = self.env["clinic.wallet.portal.request"]
            auto_post_move = False
        else:
            wallet = partner.sudo().get_or_create_wallet(
                company=company,
                auto_open=True,
                ensure_active=True,
            )
            safe_attachment_ids = attachment_ids or []
            Request = self.env["clinic.wallet.portal.request"].sudo()

        req = Request.create({
            "request_type": request_type,
            "company_id": company.id,
            "currency_id": wallet.currency_id.id,
            "partner_id": partner.id,
            "wallet_id": wallet.id,
            "amount": amount,
            "note": note or "",
            "auto_post_move": bool(auto_post_move),
            "attachment_ids": [(6, 0, safe_attachment_ids)],
        })
        req.action_submit()
        return {"ok": True, "request_id": req.id, "request_name": req.name}

    # ---------------------------------------------------------------------
    # INTERNAL HELPERS
    # ---------------------------------------------------------------------
    def _portal_is_external_user(self):
        user = self.env.user
        return bool(
            user.share
            and user.has_group("base.group_portal")
            and not user.has_group("base.group_user")
        )

    def _portal_get_partner(self, partner_id=None):
        user_partner = self.env.user.partner_id.commercial_partner_id
        if self._portal_is_external_user():
            if partner_id and int(partner_id) != user_partner.id:
                raise AccessError(_("Portal users can only access their own wallet."))
            return user_partner

        if partner_id:
            partner = self.env["res.partner"].browse(int(partner_id)).exists()
            if partner:
                return partner.commercial_partner_id
        if user_partner:
            return user_partner
        raise UserError(_("No partner found for current user."))

    def _portal_get_company(self, company_id=None):
        if self._portal_is_external_user():
            if company_id and int(company_id) != self.env.company.id:
                raise AccessError(_("Portal users can only access the current company wallet."))
            return self.env.company
        if company_id:
            company = self.env["res.company"].browse(int(company_id)).exists()
            if company:
                if company not in self.env.user.company_ids:
                    raise AccessError(_("You are not allowed to operate in the selected company."))
                return company
        return self.env.company

    def _portal_filter_attachment_ids(self, attachment_ids):
        """Prevent portal callers from linking arbitrary attachments by ID."""
        if not attachment_ids:
            return []
        attachments = self.env["ir.attachment"].browse(
            [int(item) for item in attachment_ids]
        ).exists()
        safe = attachments.filtered(
            lambda attachment: attachment.create_uid == self.env.user
            and (
                not attachment.res_model
                or attachment.res_model == "clinic.wallet.portal.request"
            )
        )
        if len(safe) != len(attachments):
            raise AccessError(_("One or more attachments are not owned by the current portal user."))
        return safe.ids




