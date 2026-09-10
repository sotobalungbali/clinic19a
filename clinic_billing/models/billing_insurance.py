# -*- coding: utf-8 -*-
# File: clinic_billing/models/billing_insurance.py
# License: LGPL-3

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# ============================================================================
# Insurance Claim (Header)
# ============================================================================
class ClinicInsuranceClaim(models.Model):
    """
    Clinic Insurance Claim
    ----------------------
    Insurance claim document linked to a Clinic Billing Invoice.
    Provides a detailed line-level coverage computation and an action
    to settle approved amounts by creating a Clinic Billing Payment
    (method: insurance), which will then generate/account for an
    account.payment and reconcile with the accounting invoice.

    Design goals:
    - Holistic but safe (no hard dependency to other ClinicOne modules).
    - Coverage math at line-level: deductible, copay, covered%.
    - Flexible states and hooks for external connectors (EDI/API).
    """
    _name = "clinic.insurance.claim"
    _description = "Clinic Insurance Claim"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _rec_name = "name"

    # -------------------------------------------------------------------------
    # Identity & Linkage
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Claim Number",
        default="/",
        copy=False,
        index=True,
        tracking=True,
        help="Sequence number of this insurance claim."
    )
    invoice_id = fields.Many2one(
        "clinic.billing.invoice",
        string="Clinic Invoice",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
        help="Clinic billing invoice for which this insurance claim is submitted."
    )
    move_id = fields.Many2one(
        related="invoice_id.move_id",
        string="Accounting Invoice",
        store=True,
        readonly=True
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

    insurer_partner_id = fields.Many2one(
        "res.partner",
        string="Insurer",
        help="Insurance company/partner responsible for coverage."
    )
    policy_number = fields.Char(
        string="Policy Number",
        help="Insurance policy number applicable to this claim."
    )
    coverage_percent = fields.Float(
        string="Coverage (%)",
        digits=(16, 2),
        help="Default coverage percentage applied to lines (can be overridden per line)."
    )
    deductible_amount = fields.Monetary(
        string="Deductible",
        help="Total deductible amount applied at the claim level (distributed across lines)."
    )
    copay_percent = fields.Float(
        string="Co-pay (%)",
        digits=(16, 2),
        help="Default co-pay percentage the patient must pay (can be overridden per line)."
    )

    claim_date = fields.Date(
        string="Claim Date",
        default=lambda self: fields.Date.context_today(self),
        tracking=True
    )

    # State & timestamps
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("prepared", "Prepared"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("settled", "Settled"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True
    )
    submitted_on = fields.Datetime(string="Submitted On", tracking=True)
    approved_on = fields.Datetime(string="Approved On", tracking=True)
    rejected_on = fields.Datetime(string="Rejected On", tracking=True)
    settled_on = fields.Datetime(string="Settled On", tracking=True)

    # Lines & docs
    claim_line_ids = fields.One2many(
        "clinic.insurance.claim.line",
        "claim_id",
        string="Claim Lines",
        copy=True
    )
    document_ids = fields.Many2many(
        "ir.attachment",
        "clinic_insurance_claim_attachment_rel",
        "claim_id",
        "attachment_id",
        string="Attachments",
        help="Supporting documents (ID, authorization, medical notes, invoices, etc.)"
    )

    # Totals (computed)
    requested_amount = fields.Monetary(
        string="Requested Amount",
        compute="_compute_totals",
        store=False,
        help="Sum of requested amounts across lines (usually pre-tax)."
    )
    approved_amount = fields.Monetary(
        string="Approved Amount",
        compute="_compute_totals",
        store=False,
        help="Sum of line-level approved amounts (editable per line on approval)."
    )
    insurer_payable_amount = fields.Monetary(
        string="Insurer Payable",
        compute="_compute_totals",
        store=False,
        help="Sum of insurer payable across lines after deductible/copay/coverage."
    )
    patient_responsibility_amount = fields.Monetary(
        string="Patient Responsibility",
        compute="_compute_totals",
        store=False,
        help="Sum of patient portion across lines."
    )

    # Settlement
    settlement_journal_id = fields.Many2one(
        "account.journal",
        string="Settlement Journal",
        domain="[('company_id', '=', company_id)]",
        help="Journal to use when creating a payment for insurer settlement."
    )
    settlement_payment_id = fields.Many2one(
        "clinic.billing.payment",
        string="Settlement Payment",
        readonly=True,
        copy=False,
        help="Clinic payment document created for insurer settlement."
    )

    # Notes
    reason_rejected = fields.Char(string="Rejection Reason")
    note = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # Soft dependency helper
    # -------------------------------------------------------------------------
    @api.model
    def _model(self, model_name):
        return self.env[model_name] if model_name in self.env else False

    # -------------------------------------------------------------------------
    # Sequences
    # -------------------------------------------------------------------------
    def _next_sequence(self):
        return self.env["ir.sequence"].sudo().next_by_code("clinic.insurance.claim") or "/"

    # -------------------------------------------------------------------------
    # Compute totals from lines
    # -------------------------------------------------------------------------
    @api.depends("claim_line_ids.requested_amount",
                 "claim_line_ids.approved_amount",
                 "claim_line_ids.insurer_payable",
                 "claim_line_ids.patient_responsibility")
    def _compute_totals(self):
        for rec in self:
            req = sum(l.requested_amount for l in rec.claim_line_ids)
            appr = sum(l.approved_amount for l in rec.claim_line_ids)
            ins = sum(l.insurer_payable for l in rec.claim_line_ids)
            pat = sum(l.patient_responsibility for l in rec.claim_line_ids)
            rec.requested_amount = req
            rec.approved_amount = appr
            rec.insurer_payable_amount = ins
            rec.patient_responsibility_amount = pat

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains("invoice_id")
    def _check_invoice_required(self):
        for rec in self:
            if not rec.invoice_id:
                raise ValidationError(_("Clinic Invoice is required."))

    # -------------------------------------------------------------------------
    # Lifecycle actions
    # -------------------------------------------------------------------------
    def action_prepare(self):
        """
        Build claim lines based on clinic billing lines (if empty),
        applying default coverage rules. Switch to Prepared.
        """
        for rec in self:
            if rec.state not in ("draft", "prepared"):
                continue
            if rec.name in ("/", False, ""):
                rec.name = rec._next_sequence()

            if not rec.claim_line_ids:
                rec._build_lines_from_billing()

            # Optionally distribute deductible at header level across lines
            if rec.deductible_amount:
                rec._allocate_header_deductible()

            # Copy hint defaults from invoice if empty
            rec._apply_defaults_from_invoice()

            rec.state = "prepared"
            rec._sync_invoice_claim_state()

        return True

    def _apply_defaults_from_invoice(self):
        """If header coverage/copay not set, borrow defaults from invoice."""
        for rec in self:
            inv = rec.invoice_id
            if inv:
                if not rec.coverage_percent and inv.insurance_coverage_percent:
                    rec.coverage_percent = inv.insurance_coverage_percent
                if not rec.policy_number and inv.insurance_policy_number:
                    rec.policy_number = inv.insurance_policy_number

    def _build_lines_from_billing(self):
        """Create claim lines from clinic.billing.line or (fallback) from account.move lines."""
        for rec in self:
            line_model = rec._model("clinic.billing.line")
            if line_model:
                source_lines = rec.invoice_id.line_ids
                for s in source_lines:
                    s_vals = s._snapshot_for_claim(rec)
                    self.env["clinic.insurance.claim.line"].create(s_vals)
            else:
                # Fallback: from account.move lines (pre-tax amount per line)
                if not rec.move_id:
                    # Generate accounting invoice first if needed
                    rec.invoice_id.action_generate_account_move()
                for aml in rec.move_id.invoice_line_ids.filtered(lambda l: not l.display_type):
                    s_vals = {
                        "claim_id": rec.id,
                        "billing_line_id": False,
                        "product_id": aml.product_id.id,
                        "name": aml.name,
                        "quantity": aml.quantity,
                        "unit_price": aml.price_unit,
                        "subtotal_excl_tax": aml.price_subtotal,  # subtotal without taxes
                        "covered_percent": rec.coverage_percent or 0.0,
                        "deductible_amount": 0.0,
                        "copay_percent": rec.copay_percent or 0.0,
                    }
                    self.env["clinic.insurance.claim.line"].create(s_vals)

    def _allocate_header_deductible(self):
        """
        Distribute header deductible_amount across claim lines proportionally
        to their requested_amount.
        """
        for rec in self:
            if not rec.claim_line_ids:
                continue
            total_req = sum(l.requested_amount for l in rec.claim_line_ids) or 0.0
            if total_req <= 0:
                continue
            remaining = rec.deductible_amount or 0.0
            for line in rec.claim_line_ids:
                if remaining <= 0:
                    line.deductible_amount = 0.0
                    continue
                share = (line.requested_amount / total_req) * (rec.deductible_amount or 0.0)
                line.deductible_amount = round(share, 2)
                remaining -= line.deductible_amount

    def action_submit(self):
        """Move to Submitted and (optionally) call external connector hook."""
        for rec in self:
            if rec.state not in ("prepared", "draft"):
                continue
            rec.action_prepare()
            rec.submitted_on = fields.Datetime.now()
            rec.state = "submitted"
            # Hook to send data to insurer API
            rec._hook_send_to_insurer()
            rec._sync_invoice_claim_state()
        return True

    def action_approve(self):
        """
        Approve claim. Ensure line.approved_amount is set.
        If not provided, default approved = insurer_payable (pre-computed).
        """
        for rec in self:
            if rec.state not in ("submitted", "prepared"):
                continue
            for line in rec.claim_line_ids:
                if not line.approved_amount:
                    # If approved_amount not explicitly set, take insurer_payable as approved baseline
                    line.approved_amount = line.insurer_payable
            rec.approved_on = fields.Datetime.now()
            rec.state = "approved"
            rec._hook_after_approve()
            rec._sync_invoice_claim_state()
        return True

    def action_reject(self):
        """Reject claim (requires reason)."""
        for rec in self:
            if rec.state not in ("submitted", "prepared"):
                continue
            if not rec.reason_rejected:
                raise UserError(_("Please provide a Rejection Reason."))
            rec.rejected_on = fields.Datetime.now()
            rec.state = "rejected"
            rec._hook_after_reject()
            rec._sync_invoice_claim_state()
        return True

    def action_settle(self):
        """
        Create a clinic.billing.payment with method 'insurance' for the approved amount,
        confirm+post it, and reconcile with the accounting invoice.
        """
        for rec in self:
            if rec.state not in ("approved", "submitted"):
                raise UserError(_("Only Approved/Submitted claims can be settled."))
            if not rec.invoice_id or not rec.invoice_id.move_id:
                # Ensure accounting invoice exists and is posted
                rec.invoice_id.action_generate_account_move()
                if rec.invoice_id.move_id.state != "posted":
                    rec.invoice_id.action_post_account_move()

            settle_amount = rec.insurer_payable_amount
            if settle_amount <= 0:
                raise UserError(_("Insurer payable amount is zero; nothing to settle."))

            # Create Clinic Billing Payment
            payment_vals = {
                "invoice_id": rec.invoice_id.id,
                "date": fields.Date.context_today(self),
                "narration": "Insurance settlement for claim %s" % (rec.name,),
                "allow_overpayment": False,
                "allow_underpayment": True,
                "line_ids": [(0, 0, {
                    "sequence": 10,
                    "method": "insurance",
                    "journal_id": rec._resolve_settlement_journal().id if rec._resolve_settlement_journal() else False,
                    "amount": settle_amount,
                    "fee_amount": 0.0,
                    "reference": rec.policy_number or rec.name,
                    "gateway_provider": "manual",
                    "gateway_tx_id": rec.name,
                    "insurance_policy_number": rec.policy_number or "",
                })],
            }
            pay = self.env["clinic.billing.payment"].create(payment_vals)
            pay.action_confirm()
            pay.action_post()

            rec.settlement_payment_id = pay.id
            rec.settled_on = fields.Datetime.now()
            rec.state = "settled"
            rec._hook_after_settle()
            rec._sync_invoice_claim_state()
        return True

    def action_cancel(self):
        """Cancel claim (only when not settled)."""
        for rec in self:
            if rec.state == "settled":
                raise UserError(_("Cannot cancel a settled claim. Please create a corrective claim instead."))
            rec.state = "cancelled"
            rec._hook_audit("cancel_claim", {"claim_id": rec.id})
            rec._sync_invoice_claim_state()
        return True

    # -------------------------------------------------------------------------
    # Journal resolution
    # -------------------------------------------------------------------------
    def _resolve_settlement_journal(self):
        """Prefer claim.settlement_journal_id; fallback to any bank/general journal."""
        for rec in self:
            if rec.settlement_journal_id:
                return rec.settlement_journal_id
        Journal = self.env["account.journal"].sudo()
        return Journal.search([
            ("type", "in", ("bank", "cash", "general")),
            ("company_id", "=", self.company_id.id)
        ], limit=1)

    # -------------------------------------------------------------------------
    # Hooks & Audit
    # -------------------------------------------------------------------------
    def _hook_send_to_insurer(self):
        """
        Push claim data to external insurer connector (if any).
        Implement via an inheriting module (e.g., clinic_insurance_connector_*).
        """
        # Example:
        # Connector = self._model("clinic.insurance.connector")
        # if Connector:
        #     Connector.sudo().submit_claim(self)
        return

    def _hook_after_approve(self):
        """Hook after claim approval (notify, audit)."""
        self._hook_audit("approve_claim", {"claim_id": self.id})

    def _hook_after_reject(self):
        """Hook after claim rejection (notify, audit)."""
        self._hook_audit("reject_claim", {"claim_id": self.id, "reason": self.reason_rejected})

    def _hook_after_settle(self):
        """Hook after claim settlement (notify, audit)."""
        self._hook_audit("settle_claim", {"claim_id": self.id, "payment_id": self.settlement_payment_id.id})

    def _hook_audit(self, event, payload=None):
        """Send audit log to clinic_audit if installed."""
        Audit = self._model("clinic.audit.log")
        if Audit:
            Audit.sudo().create({
                "event": event,
                "payload": payload or {},
                "res_model": self._name,
                "res_id": self.id,
            })

    # -------------------------------------------------------------------------
    # Invoice state sync
    # -------------------------------------------------------------------------
    def _sync_invoice_claim_state(self):
        """Mirror a simplified claim state on the invoice."""
        for rec in self:
            if not rec.invoice_id:
                continue
            # Determine a coarse state based on the newest non-cancelled claim
            state_priority = {
                "settled": 5,
                "approved": 4,
                "submitted": 3,
                "prepared": 2,
                "draft": 1,
                "rejected": 0,
                "cancelled": -1,
            }
            claims = self.search([("invoice_id", "=", rec.invoice_id.id), ("state", "!=", "cancelled")])
            if not claims:
                rec.invoice_id.insurance_claim_state = "none"
                continue
            # pick max priority state
            best = max(claims, key=lambda c: state_priority.get(c.state, -1))
            mapping = {
                "draft": "prepared",
                "prepared": "prepared",
                "submitted": "submitted",
                "approved": "approved",
                "rejected": "rejected",
                "settled": "settled",
            }
            rec.invoice_id.insurance_claim_state = mapping.get(best.state, "prepared")


# ============================================================================
# Insurance Claim Line (Detail)
# ============================================================================
class ClinicInsuranceClaimLine(models.Model):
    """
    Line-level detail for insurance claim coverage.
    Captures product, quantity, price, taxes-free subtotal snapshot,
    and computes insurer payable vs patient responsibility.
    """
    _name = "clinic.insurance.claim.line"
    _description = "Clinic Insurance Claim Line"
    _order = "claim_id, sequence, id"

    claim_id = fields.Many2one(
        "clinic.insurance.claim",
        string="Insurance Claim",
        required=True,
        index=True,
        ondelete="cascade"
    )

    sequence = fields.Integer(string="Sequence", default=10)

    # Link back to billing line if present (soft)
    billing_line_id = fields.Many2one(
        "clinic.billing.line",
        string="Billing Line",
        help="Linked clinic billing line (if claim built from clinic lines)."
    )

    product_id = fields.Many2one("product.product", string="Product")
    name = fields.Char(string="Description")
    quantity = fields.Float(string="Quantity", default=1.0)
    unit_price = fields.Monetary(string="Unit Price", currency_field="currency_id")
    currency_id = fields.Many2one(
        related="claim_id.currency_id", store=True, readonly=True
    )

    # Snapshot subtotal without taxes (frozen at prepare time)
    subtotal_excl_tax = fields.Monetary(
        string="Subtotal (Excl. Tax)",
        currency_field="currency_id",
        help="Snapshot of line subtotal before taxes at the time of claim preparation."
    )

    # Coverage parameters (header defaults can be overridden per line)
    covered_percent = fields.Float(
        string="Coverage (%)",
        digits=(16, 2),
        help="Coverage percentage applied to this line."
    )
    deductible_amount = fields.Monetary(
        string="Deductible",
        currency_field="currency_id",
        help="Deductible applied on this line (portion of header deductible or specific)."
    )
    copay_percent = fields.Float(
        string="Co-pay (%)",
        digits=(16, 2),
        help="Co-pay percentage applied to this line."
    )

    # Amounts
    requested_amount = fields.Monetary(
        string="Requested Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=False,
        help="Requested amount (typically equals subtotal before tax)."
    )
    approved_amount = fields.Monetary(
        string="Approved Amount",
        currency_field="currency_id",
        help="Approved amount from insurer. If empty at approval, defaults to insurer payable."
    )
    insurer_payable = fields.Monetary(
        string="Insurer Payable",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=False,
        help="Insurer pays this portion after deductible & co-pay."
    )
    patient_responsibility = fields.Monetary(
        string="Patient Responsibility",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=False,
        help="Patient portion after coverage calculations."
    )

    # Mirrors (for convenience)
    state = fields.Selection(
        related="claim_id.state", string="Claim State", store=True, readonly=True
    )
    company_id = fields.Many2one(
        related="claim_id.company_id", store=True, readonly=True
    )

    # -------------------------------------------------------------------------
    # Compute coverage math
    # -------------------------------------------------------------------------
    @api.depends("subtotal_excl_tax",
                 "covered_percent", "deductible_amount", "copay_percent",
                 "approved_amount", "quantity", "unit_price")
    def _compute_amounts(self):
        for line in self:
            base = line.subtotal_excl_tax
            # Fallback: compute from qty * unit_price if subtotal snapshot missing
            if not base and line.quantity and line.unit_price:
                base = (line.quantity or 0.0) * (line.unit_price or 0.0)

            base = max(base, 0.0)

            # Requested amount is base
            req = base

            # Apply deductible (cannot exceed base)
            after_deduct = max(base - (line.deductible_amount or 0.0), 0.0)

            # Apply coverage %
            cov = (line.covered_percent or 0.0) / 100.0
            covered_part = after_deduct * cov

            # Apply copay on the covered portion (patient share)
            cop = (line.copay_percent or 0.0) / 100.0
            patient_copay = covered_part * cop

            insurer_payable = max(covered_part - patient_copay, 0.0)

            # If approved_amount is lower than insurer_payable (payer allowance), cap it
            if line.approved_amount:
                insurer_payable = min(insurer_payable, line.approved_amount)

            patient_resp = max(base - insurer_payable, 0.0)

            line.requested_amount = req
            line.insurer_payable = insurer_payable
            line.patient_responsibility = patient_resp

    # -------------------------------------------------------------------------
    # Snapshot helper when building from billing line
    # -------------------------------------------------------------------------
    def _prepare_from_billing_line(self, claim):
        """Return vals dict to create a claim line from a clinic.billing.line."""
        self.ensure_one()


# ============================================================================
# Extension on Clinic Billing Line: snapshot helper
# ============================================================================
class ClinicBillingLine_InsuranceExt(models.Model):
    _inherit = "clinic.billing.line"

    def _snapshot_for_claim(self, claim):
        """
        Build a snapshot dict for creating clinic.insurance.claim.line from this billing line.
        Uses clinic billing line’s subtotal before tax as the requested amount baseline.
        """
        self.ensure_one()
        # Ensure computed amounts are available (call compute if needed by reading fields)
        _ = (self.subtotal_excl_tax, self.total_incl_tax, self.price_effective)

        return {
            "claim_id": claim.id,
            "billing_line_id": self.id,
            "product_id": self.product_id.id,
            "name": self.name or (self.product_id.display_name if self.product_id else ""),
            "quantity": self.quantity or 1.0,
            "unit_price": self.price_effective or self.unit_price or 0.0,
            "subtotal_excl_tax": self.subtotal_excl_tax or 0.0,
            "covered_percent": claim.coverage_percent or 0.0,
            "deductible_amount": 0.0,  # distributed later from header if needed
            "copay_percent": claim.copay_percent or 0.0,
        }


# ============================================================================
# Extension on Clinic Billing Invoice: O2M & Smart Actions
# ============================================================================
class ClinicBillingInvoice_InsuranceExt(models.Model):
    _inherit = "clinic.billing.invoice"

    insurance_claim_ids = fields.One2many(
        "clinic.insurance.claim",
        "invoice_id",
        string="Insurance Claims"
    )

    def action_open_insurance_claims(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Claims"),
            "res_model": "clinic.insurance.claim",
            "view_mode": "list,form",
            "domain": [("invoice_id", "=", self.id)],
            "context": {
                "default_invoice_id": self.id,
                "default_policy_number": self.insurance_policy_number or "",
                "default_coverage_percent": self.insurance_coverage_percent or 0.0,
            },
        }

    def action_new_insurance_claim(self):
        """Shortcut: open new claim form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Insurance Claim"),
            "res_model": "clinic.insurance.claim",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_invoice_id": self.id,
                "default_policy_number": self.insurance_policy_number or "",
                "default_coverage_percent": self.insurance_coverage_percent or 0.0,
            },
        }



