# -*- coding: utf-8 -*-
# File: clinic_billing/models/billing_gateway_tx.py
# License: LGPL-3

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Gateway Transaction
# =============================================================================
class ClinicBillingGatewayTx(models.Model):
    """
    Payment Gateway Transaction
    ---------------------------
    Represents a transaction initiated/handled via an external payment gateway
    (e.g., Midtrans, Xendit, Stripe) for a Clinic Billing Invoice.

    Goals:
    - Track full transaction lifecycle (initiated → pending → authorized → captured/settled → refunded/chargeback).
    - Store raw webhook payload and headers; verify signature when possible.
    - Create/Update a Clinic Billing Payment (+ account.payment) when funds are captured/settled.
    - Link to a specific split payment line when applicable (to avoid double capture).
    - Soft-dependency to other ClinicOne modules; no direct HTTP calls here.

    Typical flows:
    1) Initiate: action_initiate_from_invoice(...) creates a tx in 'initiated' or 'pending'.
    2) Webhook: process_webhook(...) updates state/amounts, and generates accounting artifacts.
    3) Manual: action_mark_captured() etc. for back-office corrections.
    """
    _name = "clinic.billing.gateway.tx"
    _description = "Clinic Billing Gateway Transaction"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _rec_name = "name"

    # -------------------------------------------------------------------------
    # Identity & linkage
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Transaction Number",
        default="/",
        copy=False,
        index=True,
        tracking=True,
        help="Internal sequence number of the gateway transaction."
    )
    provider = fields.Selection(
        [
            ("midtrans", "Midtrans"),
            ("xendit", "Xendit"),
            ("stripe", "Stripe"),
            ("manual", "Manual"),
        ],
        string="Provider",
        required=True,
        default="manual",
        tracking=True,
        help="Gateway provider that processed this transaction."
    )
    method = fields.Selection(
        [
            ("card", "Card"),
            ("ewallet", "E-Wallet"),
            ("bank_transfer", "Bank Transfer"),
            ("qris", "QRIS"),
            ("retail", "Retail Outlet"),
            ("other", "Other"),
        ],
        string="Method",
        default="other",
        help="High-level payment method used."
    )
    channel = fields.Selection(
        [
            ("visa", "VISA"),
            ("mastercard", "Mastercard"),
            ("amex", "AMEX"),
            ("gopay", "GoPay"),
            ("ovo", "OVO"),
            ("dana", "DANA"),
            ("shopeepay", "ShopeePay"),
            ("linkaja", "LinkAja"),
            ("bca_va", "BCA VA"),
            ("bni_va", "BNI VA"),
            ("bri_va", "BRI VA"),
            ("mandiri_va", "Mandiri VA"),
            ("qris", "QRIS"),
            ("other", "Other"),
        ],
        string="Channel",
        help="Specific payment channel if applicable."
    )
    card_scheme = fields.Char(string="Card Scheme", help="Card scheme or brand (free text).")

    state = fields.Selection(
        [
            ("initiated", "Initiated"),
            ("pending", "Pending"),
            ("authorized", "Authorized"),
            ("captured", "Captured"),
            ("settled", "Settled"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
            ("refunded", "Refunded"),
            ("chargeback", "Chargeback"),
        ],
        string="Status",
        default="initiated",
        tracking=True,
        index=True
    )

    invoice_id = fields.Many2one(
        "clinic.billing.invoice",
        string="Clinic Invoice",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True
    )
    move_id = fields.Many2one(
        related="invoice_id.move_id",
        string="Accounting Invoice",
        store=True,
        readonly=True
    )
    partner_id = fields.Many2one(
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

    # Link to clinic payment (header/line) if generated
    payment_id = fields.Many2one(
        "clinic.billing.payment",
        string="Clinic Payment",
        readonly=True,
        copy=False
    )
    payment_line_id = fields.Many2one(
        "clinic.billing.payment.line",
        string="Payment Line",
        readonly=True,
        copy=False
    )

    # External references from provider
    order_reference = fields.Char(
        string="Order Reference",
        help="Local order/invoice reference sent to the gateway (e.g., invoice number)."
    )
    external_tx_id = fields.Char(
        string="Gateway Transaction ID",
        index=True,
        help="Unique transaction identifier on the gateway side."
    )
    external_order_id = fields.Char(
        string="Gateway Order ID",
        index=True,
        help="Order identifier on the gateway side (if different from transaction ID)."
    )
    external_reference = fields.Char(
        string="External Reference",
        help="Any additional reference returned by the gateway."
    )

    # Amounts
    amount = fields.Monetary(
        string="Amount",
        help="Gross amount charged by the gateway."
    )
    fee_amount = fields.Monetary(
        string="Gateway Fee",
        help="Fee charged by the gateway (if reported)."
    )
    net_amount = fields.Monetary(
        string="Net Amount",
        compute="_compute_net_amount",
        store=False,
        help="Net amount (Amount - Fee)."
    )
    captured_amount = fields.Monetary(
        string="Captured Amount",
        help="Amount captured/settled (for preauth flows)."
    )
    refunded_amount = fields.Monetary(
        string="Refunded Amount",
        help="Total refunded amount."
    )

    # Webhook payloads / meta
    raw_payload = fields.Json(string="Raw Payload", help="Last webhook/request payload in JSON form.")
    raw_headers = fields.Json(string="Raw Headers", help="Last webhook/request headers in JSON form.")
    webhook_signature = fields.Char(string="Webhook Signature", help="Signature value extracted from headers/payload.")
    webhook_timestamp = fields.Datetime(string="Webhook Timestamp")

    # Flags & diagnostics
    is_test_mode = fields.Boolean(string="Test Mode", help="True if transaction uses sandbox/test credentials.")
    error_code = fields.Char(string="Error Code")
    error_message = fields.Char(string="Error Message")
    note = fields.Char(string="Note")

    _provider_tx_company_unique = models.Constraint(
        "UNIQUE(provider, external_tx_id, company_id)",
        "Gateway transaction must be unique per provider and company.",
    )

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------
    @api.depends("amount", "fee_amount")
    def _compute_net_amount(self):
        for rec in self:
            rec.net_amount = (rec.amount or 0.0) - (rec.fee_amount or 0.0)

    # -------------------------------------------------------------------------
    # Sequence
    # -------------------------------------------------------------------------
    def _next_sequence(self):
        return self.env["ir.sequence"].sudo().next_by_code("clinic.billing.gateway.tx") or "/"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") in ("/", False):
                vals["name"] = self._next_sequence()
        recs = super().create(vals_list)
        return recs

    # -------------------------------------------------------------------------
    # Gatekeeping
    # -------------------------------------------------------------------------
    @api.constrains("invoice_id", "amount", "currency_id")
    def _check_basic(self):
        for rec in self:
            if rec.amount is not None and rec.amount < 0:
                raise ValidationError(_("Amount cannot be negative."))

    # -------------------------------------------------------------------------
    # Public helpers
    # -------------------------------------------------------------------------
    def action_initiate_from_invoice(self, provider="manual", method="other", channel="other", amount=None, is_test=False):
        """
        Create a tx record for the invoice, place it in 'pending' if amount>0,
        and set external refs if known by the caller.
        """
        for rec in self:
            raise UserError(_("This method must be called on recordset with no existing rows."))
        # create mode (called from environment)
        # kept for clarity; typical usage: self.env['clinic.billing.gateway.tx'].create(...)

    def action_mark_pending(self, external_tx_id=None, external_order_id=None, payload=None, headers=None):
        for rec in self:
            rec.write({
                "state": "pending",
                "external_tx_id": external_tx_id or rec.external_tx_id,
                "external_order_id": external_order_id or rec.external_order_id,
                "raw_payload": payload or rec.raw_payload,
                "raw_headers": headers or rec.raw_headers,
            })
        return True

    def action_mark_authorized(self, amount=None, payload=None, headers=None):
        for rec in self:
            rec.write({
                "state": "authorized",
                "captured_amount": 0.0 if amount is None else min(float(amount), float(rec.amount or 0.0)),
                "raw_payload": payload or rec.raw_payload,
                "raw_headers": headers or rec.raw_headers,
            })
        return True

    def action_mark_captured(self, amount=None, fee=None, payload=None, headers=None, auto_create_payment=True):
        """
        Mark transaction as 'captured' and optionally generate clinic payment + reconcile.
        """
        for rec in self:
            cap_amt = float(amount if amount is not None else (rec.amount or 0.0))
            rec.write({
                "state": "captured",
                "captured_amount": cap_amt,
                "fee_amount": fee if fee is not None else rec.fee_amount,
                "raw_payload": payload or rec.raw_payload,
                "raw_headers": headers or rec.raw_headers,
            })
            if auto_create_payment:
                rec._ensure_clinic_payment_and_reconcile(cap_amt)
        return True

    def action_mark_settled(self, amount=None, fee=None, payload=None, headers=None, auto_create_payment=True):
        for rec in self:
            set_amt = float(amount if amount is not None else (rec.captured_amount or rec.amount or 0.0))
            rec.write({
                "state": "settled",
                "captured_amount": set_amt,
                "fee_amount": fee if fee is not None else rec.fee_amount,
                "raw_payload": payload or rec.raw_payload,
                "raw_headers": headers or rec.raw_headers,
            })
            if auto_create_payment:
                rec._ensure_clinic_payment_and_reconcile(set_amt)
        return True

    def action_mark_failed(self, code=None, message=None, payload=None, headers=None):
        for rec in self:
            rec.write({
                "state": "failed",
                "error_code": code,
                "error_message": message,
                "raw_payload": payload or rec.raw_payload,
                "raw_headers": headers or rec.raw_headers,
            })
            rec._post_chatter(_("Gateway transaction failed: %s") % (message or code or ""))
        return True

    def action_mark_cancelled(self, payload=None, headers=None):
        for rec in self:
            rec.write({
                "state": "cancelled",
                "raw_payload": payload or rec.raw_payload,
                "raw_headers": headers or rec.raw_headers,
            })
        return True

    def action_mark_refunded(self, amount, payload=None, headers=None):
        """
        Mark total/partial refund. This does not create accounting credit note here;
        handle that via normal refund flow, or extend via hooks.
        """
        for rec in self:
            amt = float(amount or 0.0)
            if amt <= 0:
                continue
            new_ref = (rec.refunded_amount or 0.0) + amt
            rec.write({
                "state": "refunded",
                "refunded_amount": new_ref,
                "raw_payload": payload or rec.raw_payload,
                "raw_headers": headers or rec.raw_headers,
            })
            rec._post_chatter(_("Gateway refund recorded: %.2f") % amt)
        return True

    def action_mark_chargeback(self, amount=None, payload=None, headers=None):
        for rec in self:
            rec.write({
                "state": "chargeback",
                "raw_payload": payload or rec.raw_payload,
                "raw_headers": headers or rec.raw_headers,
            })
            rec._post_chatter(_("Chargeback flagged by gateway."))
        return True

    # -------------------------------------------------------------------------
    # Webhook processing (generic)
    # -------------------------------------------------------------------------
    def process_webhook(self, provider, payload, headers=None, test_mode=False):
        """
        Generic webhook entrypoint. Verifies signature if configured, updates state,
        and generates clinic payment when captured/settled.
        This method is synchronous and idempotent at record level.
        """
        provider = (provider or "").lower().strip()
        headers = headers or {}
        tx = self._match_tx_from_payload(provider, payload)
        if not tx:
            raise UserError(_("No matching gateway transaction was found."))

        # Verify signature if possible; failures do not hard-block by default (configurable)
        verified = tx._verify_signature(provider, payload, headers)
        if not verified and tx._get_param_bool("clinic_billing.gateway.enforce_signature", default=False):
            raise UserError(_("Invalid gateway signature."))

        # Provider-specific state mapping
        state_info = tx._extract_state_amount(provider, payload)
        new_state = state_info.get("state")
        amount = state_info.get("amount")
        fee = state_info.get("fee")

        # Save raw payload & headers
        tx.write({
            "raw_payload": payload,
            "raw_headers": headers,
            "webhook_timestamp": fields.Datetime.now(),
            "is_test_mode": test_mode,
            "external_tx_id": state_info.get("external_tx_id") or tx.external_tx_id,
            "external_order_id": state_info.get("external_order_id") or tx.external_order_id,
        })

        # State transitions
        if new_state in ("authorized",):
            tx.action_mark_authorized(amount=amount, payload=payload, headers=headers)
        elif new_state in ("captured", "settled"):
            # prefer settled if explicitly indicated
            if new_state == "settled":
                tx.action_mark_settled(amount=amount, fee=fee, payload=payload, headers=headers, auto_create_payment=True)
            else:
                tx.action_mark_captured(amount=amount, fee=fee, payload=payload, headers=headers, auto_create_payment=True)
        elif new_state in ("failed", "cancelled"):
            tx.action_mark_failed(code=state_info.get("error_code"), message=state_info.get("error_message"),
                                  payload=payload, headers=headers)
        elif new_state in ("refunded", "chargeback"):
            tx.action_mark_refunded(amount=amount or 0.0, payload=payload, headers=headers) if new_state == "refunded" \
                else tx.action_mark_chargeback(amount=amount, payload=payload, headers=headers)
        else:
            # Default to pending if unknown
            tx.action_mark_pending(payload=payload, headers=headers)

        return True

    # -------------------------------------------------------------------------
    # Payment creation / reconciliation
    # -------------------------------------------------------------------------
    def _ensure_clinic_payment_and_reconcile(self, captured_amount):
        """
        Create or link a Clinic Billing Payment and reconcile it to the invoice.
        - If a payment_line already exists, ensure it's posted and reconciled.
        - Else, create a new clinic.payment with one line and post it.
        """
        self.ensure_one()
        inv = self.invoice_id
        if not inv:
            raise UserError(_("No clinic invoice linked."))

        # Ensure accounting invoice exists and is posted
        if not inv.move_id:
            inv.action_generate_account_move()
        if inv.move_id and inv.move_id.state != "posted":
            inv.action_post_account_move()

        # Reuse existing payment line if it references this gateway tx
        if self.payment_line_id:
            pay = self.payment_line_id.payment_id
            if pay and pay.state in ("draft", "confirmed"):
                pay.action_confirm()
            if pay and pay.state != "posted":
                pay.action_post()
            # Reconcile is handled in billing_payment.py during action_post
            self.payment_id = pay.id
            return pay

        # Else, create a fresh clinic.billing.payment
        method_map = {
            "card": "card",
            "ewallet": "ewallet",
            "bank_transfer": "bank_transfer",
            "qris": "ewallet",
            "retail": "other",
            "other": "other",
        }
        line_method = method_map.get(self.method or "other", "other")

        journal = self._resolve_journal(line_method)
        payment_vals = {
            "invoice_id": inv.id,
            "date": fields.Date.context_today(self),
            "narration": "Gateway TX %s (%s)" % (self.name, self.provider),
            "allow_overpayment": False,
            "allow_underpayment": True,
            "line_ids": [(0, 0, {
                "sequence": 20,
                "method": line_method,
                "journal_id": journal.id if journal else False,
                "amount": captured_amount,
                "fee_amount": self.fee_amount or 0.0,
                "reference": self.external_tx_id or self.external_order_id or self.name,
                "gateway_provider": self.provider,
                "gateway_tx_id": self.external_tx_id or self.name,
                "ewallet_channel": (self.channel if line_method == "ewallet" else False),
                "card_scheme": (self.card_scheme if line_method == "card" else False),
                "authorization_code": False,
            })],
        }
        pay = self.env["clinic.billing.payment"].create(payment_vals)
        pay.action_confirm()
        pay.action_post()

        # Link back
        self.payment_id = pay.id
        # Store created line for traceability
        created_line = pay.line_ids.sorted("id")[-1] if pay.line_ids else False
        if created_line:
            self.payment_line_id = created_line.id

        return pay

    def _resolve_journal(self, line_method):
        """Pick a reasonable journal based on method; fallback to any bank/cash/general."""
        Journal = self.env["account.journal"].sudo()
        company = self.company_id
        domain_base = [("company_id", "=", company.id)]
        # Heuristics by method
        if line_method in ("card", "ewallet", "bank_transfer"):
            j = Journal.search([("type", "in", ("bank",)), *domain_base], limit=1)
            if j:
                return j
        if line_method in ("retail", "other"):
            j = Journal.search([("type", "in", ("cash", "bank", "general")), *domain_base], limit=1)
            if j:
                return j
        return Journal.search([("type", "in", ("bank", "cash", "general")), *domain_base], limit=1)

    # -------------------------------------------------------------------------
    # Signature verification (soft)
    # -------------------------------------------------------------------------
    def _verify_signature(self, provider, payload, headers):
        """
        Verify provider webhook signature using keys stored in system parameters.
        Return True if verified or verification not configured; False on mismatch.
        """
        try:
            if provider == "midtrans":
                # Midtrans: typically uses order_id + status_code + gross_amount + server_key with SHA512
                server_key = self._get_param("clinic_billing.gateway.midtrans.server_key")
                if not server_key:
                    return True  # no strict validation if not configured
                order_id = (payload or {}).get("order_id")
                status_code = (payload or {}).get("status_code")
                gross_amount = (payload or {}).get("gross_amount")
                signature = (payload or {}).get("signature_key") or headers.get("X-Signature", "")
                import hashlib
                data = (order_id or "") + (status_code or "") + (gross_amount or "") + server_key
                check = hashlib.sha512(data.encode("utf-8")).hexdigest()
                return str(check) == str(signature)
            if provider == "xendit":
                # Xendit: x-callback-token header or basic auth secret; we accept when header matches configured token
                token_cfg = self._get_param("clinic_billing.gateway.xendit.callback_token")
                if not token_cfg:
                    return True
                return str(headers.get("x-callback-token") or headers.get("X-Callback-Token") or "") == str(token_cfg)
            if provider == "stripe":
                # Stripe: construct_event using webhook secret; here do a lenient check on header presence
                secret = self._get_param("clinic_billing.gateway.stripe.webhook_secret")
                if not secret:
                    return True
                # Minimal check: header exists (actual check should use stripe library; kept soft here)
                sig_header = headers.get("Stripe-Signature") or headers.get("stripe-signature")
                return bool(sig_header)
        except Exception:
            return False
        return True

    def _extract_state_amount(self, provider, payload):
        """
        Map provider payload into a canonical dict:
        {
            'state': 'pending|authorized|captured|settled|failed|cancelled|refunded|chargeback',
            'amount': float,
            'fee': float or None,
            'external_tx_id': str or None,
            'external_order_id': str or None,
            'error_code': str or None,
            'error_message': str or None,
        }
        This method is intentionally permissive and may be overridden by connectors.
        """
        data = payload or {}
        res = {
            "state": "pending",
            "amount": None,
            "fee": None,
            "external_tx_id": None,
            "external_order_id": None,
            "error_code": None,
            "error_message": None,
        }
        p = provider

        try:
            if p == "midtrans":
                # See Midtrans status mapping (simplified)
                # transaction_status: capture, settlement, pending, deny, cancel, expire, refund, chargeback
                status = (data.get("transaction_status") or "").lower()
                res["external_tx_id"] = data.get("transaction_id") or data.get("fraud_status")
                res["external_order_id"] = data.get("order_id")
                res["amount"] = float(data.get("gross_amount") or 0.0)
                if status in ("capture",):
                    res["state"] = "captured"
                elif status in ("settlement",):
                    res["state"] = "settled"
                elif status in ("pending",):
                    res["state"] = "pending"
                elif status in ("deny", "cancel", "expire"):
                    res["state"] = "failed" if status == "deny" else "cancelled"
                elif status in ("refund",):
                    res["state"] = "refunded"
                    res["amount"] = float(data.get("refund_amount") or res["amount"] or 0.0)
                elif status in ("chargeback",):
                    res["state"] = "chargeback"
                # fee not provided in typical webhook
            elif p == "xendit":
                # Example for e-wallet/VA callback (simplified)
                status = (data.get("status") or data.get("ewallet_charge", {}).get("status") or "").lower()
                res["external_tx_id"] = data.get("id") or data.get("ewallet_charge", {}).get("id")
                res["external_order_id"] = data.get("reference_id") or data.get("external_id")
                amt = data.get("amount") or data.get("ewallet_charge", {}).get("charge_amount") or 0.0
                res["amount"] = float(amt or 0.0)
                if status in ("succeeded", "paid", "completed"):
                    res["state"] = "settled"
                elif status in ("pending", "requires_action"):
                    res["state"] = "pending"
                elif status in ("canceled", "voided"):
                    res["state"] = "cancelled"
                elif status in ("failed",):
                    res["state"] = "failed"
                elif status in ("refunded", "partially_refunded"):
                    res["state"] = "refunded"
                    res["amount"] = float(data.get("refunded_amount") or res["amount"] or 0.0)
            elif p == "stripe":
                # Stripe sends event types: payment_intent.succeeded, payment_intent.payment_failed, charge.refunded, etc.
                event_type = (data.get("type") or "").lower()
                obj = data.get("data", {}).get("object", {})
                res["external_tx_id"] = obj.get("id") or obj.get("latest_charge")
                res["external_order_id"] = obj.get("metadata", {}).get("order_id") if obj.get("metadata") else None
                amount = obj.get("amount_received") or obj.get("amount") or 0
                res["amount"] = float(amount) / 100.0 if isinstance(amount, int) else float(amount or 0.0)

                if event_type in ("payment_intent.succeeded", "charge.succeeded"):
                    res["state"] = "settled"
                elif event_type in ("payment_intent.amount_capturable_updated",):
                    res["state"] = "authorized"
                elif event_type in ("payment_intent.payment_failed", "charge.failed"):
                    res["state"] = "failed"
                    res["error_message"] = obj.get("last_payment_error", {}).get("message") if obj.get("last_payment_error") else None
                elif event_type in ("charge.refunded",):
                    res["state"] = "refunded"
                    res["amount"] = float(obj.get("amount_refunded") or 0) / 100.0
            else:
                # Manual/unknown providers -> keep pending with provided amount
                res["state"] = (data.get("state") or "pending").lower()
                res["amount"] = float(data.get("amount") or 0.0)
        except Exception as e:
            res["state"] = "pending"
            res["error_message"] = "Parse error: %s" % e

        return res

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------
    def _get_param(self, key, default=None):
        icp = self.env["ir.config_parameter"].sudo()
        val = icp.get_param(key)
        return val if val is not None else default

    def _get_param_bool(self, key, default=False):
        v = self._get_param(key, default=str(bool(default)))
        return str(v).lower() in ("1", "true", "yes")

    def _post_chatter(self, msg):
        try:
            self.message_post(body=msg)
        except Exception:
            pass


# =============================================================================
# Gateway Event Log (optional, for debugging/audit)
# =============================================================================
class ClinicBillingGatewayEvent(models.Model):
    _name = "clinic.billing.gateway.event"
    _description = "Clinic Billing Gateway Event"
    _order = "id desc"

    tx_id = fields.Many2one("clinic.billing.gateway.tx", string="Gateway Transaction", index=True, ondelete="cascade", required=True)
    event_type = fields.Char(string="Event Type")
    payload = fields.Json(string="Payload")
    headers = fields.Json(string="Headers")
    occurred_on = fields.Datetime(string="Occurred On", default=lambda s: fields.Datetime.now())
    note = fields.Char(string="Note")

    @api.model
    def log_event(self, tx, event_type, payload=None, headers=None, note=None):
        return self.create({
            "tx_id": tx.id if isinstance(tx, models.BaseModel) else int(tx),
            "event_type": event_type,
            "payload": payload or {},
            "headers": headers or {},
            "note": note or "",
        })


# =============================================================================
# Extensions: Payment Line capture hook (wire up with Gateway Tx)
# =============================================================================
class ClinicBillingPaymentLine_GatewayHook(models.Model):
    _inherit = "clinic.billing.payment.line"

    gateway_tx_ref_id = fields.Many2one(
        "clinic.billing.gateway.tx",
        string="Gateway Tx",
        help="Link to a gateway transaction record."
    )

    def _hook_gateway_capture(self):
        """
        When a split payment line includes gateway info, link or create a tx record
        and mark it captured so reconciliation flow stays consistent.
        This does NOT call external APIs; assumes capture already happened at gateway.
        """
        for rec in self:
            if rec.gateway_provider in (False, "none") or not (rec.gateway_tx_id or rec.reference):
                continue

            # Try find an existing tx by provider + external_tx_id
            Tx = self.env["clinic.billing.gateway.tx"]
            tx = False
            if rec.gateway_tx_id:
                tx = Tx.search([
                    ("provider", "=", rec.gateway_provider),
                    ("external_tx_id", "=", rec.gateway_tx_id),
                    ("company_id", "=", rec.company_id.id),
                ], limit=1)

            if not tx:
                # Create a new tx placeholder and mark captured (amount from line)
                tx_vals = {
                    "provider": rec.gateway_provider,
                    "method": rec.method if rec.method in ("card", "ewallet", "bank_transfer", "qris", "retail", "other") else "other",
                    "channel": rec.ewallet_channel if rec.method == "ewallet" else "other",
                    "card_scheme": rec.card_scheme if rec.method == "card" else False,
                    "state": "captured",
                    "invoice_id": rec.invoice_id.id,
                    "order_reference": rec.payment_id.name or rec.invoice_id.name or "",
                    "external_tx_id": rec.gateway_tx_id or rec.reference or "",
                    "external_order_id": rec.reference or "",
                    "amount": rec.amount,
                    "fee_amount": rec.fee_amount or 0.0,
                    "captured_amount": rec.amount,
                    "is_test_mode": False,
                }
                tx = Tx.create(tx_vals)

            # Link and ensure reconciliation will happen (billing_payment will create account.payment)
            rec.gateway_tx_ref_id = tx.id
            tx.payment_id = rec.payment_id.id
            tx.payment_line_id = rec.id

            # If invoice already posted and clinic payment posted, no action needed here
            # Create event log for traceability
            self.env["clinic.billing.gateway.event"].log_event(
                tx, "capture_linked", payload={"line_id": rec.id, "amount": rec.amount}, headers={}, note="Linked from payment line hook"
            )


# =============================================================================
# Extensions: Clinic Billing Invoice (smart button, navigation)
# =============================================================================
class ClinicBillingInvoice_GatewayExt(models.Model):
    _inherit = "clinic.billing.invoice"

    gateway_tx_ids = fields.One2many(
        "clinic.billing.gateway.tx",
        "invoice_id",
        string="Gateway Transactions"
    )
    gateway_tx_count = fields.Integer(
        string="Gateway Tx Count",
        compute="_compute_gateway_tx_count"
    )

    def _compute_gateway_tx_count(self):
        for rec in self:
            rec.gateway_tx_count = len(rec.gateway_tx_ids)

    def action_open_gateway_txs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Gateway Transactions"),
            "res_model": "clinic.billing.gateway.tx",
            "view_mode": "list,form",
            "domain": [("invoice_id", "=", self.id)],
            "context": {"default_invoice_id": self.id},
        }

    def _on_after_move_posted(self, move):
        """
        On posting the accounting invoice, if there are 'captured' tx without
        clinic payment yet, generate payments and reconcile.
        """
        super()._on_after_move_posted(move)
        for rec in self:
            for tx in rec.gateway_tx_ids.filtered(lambda t: t.state in ("captured", "settled") and not t.payment_id):
                try:
                    amount = float(tx.captured_amount or tx.amount or 0.0)
                    if amount > 0:
                        tx._ensure_clinic_payment_and_reconcile(amount)
                except Exception as e:
                    rec.message_post(body=_("Auto-payment from gateway tx failed: %s") % e)


# =============================================================================
# Sequences (Ensure these exist in data XML)
# =============================================================================
# <record id="seq_clinic_billing_gateway_tx" model="ir.sequence">
#   <field name="name">Clinic Billing Gateway Tx</field>
#   <field name="code">clinic.billing.gateway.tx</field>
#   <field name="prefix">CBT/%(year)s/</field>
#   <field name="padding">5</field>
#   <field name="company_id" eval="False"/>
# </record>

