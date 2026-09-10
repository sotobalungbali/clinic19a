# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicARPayment(models.Model):
    _name = "clinic.ar.payment"
    _description = "Accounts Receivable Receipt"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "payment_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Receipt Number",
        default="/",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        domain="[('active', '=', True)]",
    )

    invoice_id = fields.Many2one(
        "clinic.ar.invoice",
        string="AR Invoice",
        index=True,
        check_company=True,
        ondelete="restrict",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        index=True,
        check_company=True,
        tracking=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Clinic Patient",
        index=True,
        check_company=True,
    )
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        index=True,
        check_company=True,
    )
    treatment_session_id = fields.Many2one(
        "clinic.treatment.session",
        string="Treatment Session",
        index=True,
        check_company=True,
    )
    membership_id = fields.Many2one(
        "membership.contract",
        string="Membership Contract",
        index=True,
        check_company=True,
    )
    billing_payment_id = fields.Many2one(
        "clinic.billing.payment",
        string="Billing Payment",
        index=True,
        check_company=True,
        ondelete="restrict",
    )
    origin_ref = fields.Reference(
        selection=[
            ("clinic.ar.invoice", "AR Invoice"),
            ("clinic.billing.payment", "Billing Payment"),
            ("booking.booking", "Booking"),
            ("membership.contract", "Membership Contract"),
            ("sale.order", "Sales Order"),
        ],
        string="Source Document",
    )

    payment_date = fields.Date(
        string="Payment Date",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    amount = fields.Monetary(
        required=True,
        currency_field="currency_id",
        tracking=True,
    )
    method = fields.Selection(
        [
            ("cash", "Cash"),
            ("bank", "Bank"),
            ("card", "Card"),
            ("transfer", "Transfer"),
            ("wallet", "Wallet"),
            ("insurance", "Insurance"),
            ("other", "Other"),
        ],
        default="cash",
        required=True,
        tracking=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Receipt Journal",
        check_company=True,
        domain="[('type', 'in', ('bank', 'cash'))]",
        tracking=True,
    )
    communication = fields.Char(string="Payment Reference")

    invoice_residual_snapshot = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
        copy=False,
    )
    applied_amount = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
        copy=False,
    )
    overpay_amount = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
        copy=False,
    )
    is_overpay = fields.Boolean(readonly=True, copy=False)

    account_payment_id = fields.Many2one(
        "account.payment",
        string="Accounting Payment",
        readonly=True,
        copy=False,
        check_company=True,
        index=True,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        related="account_payment_id.move_id",
        store=True,
        readonly=True,
    )
    account_payment_state = fields.Selection(
        related="account_payment_id.state",
        string="Accounting State",
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("posted", "Posted"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    note = fields.Text(string="Internal Notes")

    _name_company_unique = models.Constraint(
        "UNIQUE (name, company_id)",
        "AR Receipt Number must be unique per company.",
    )
    _account_payment_unique = models.Constraint(
        "UNIQUE (account_payment_id)",
        "An Accounting Payment can only be linked to one AR Receipt.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "/") in (False, "/", "New"):
                vals["name"] = sequence.next_by_code("clinic.ar.payment") or "/"
            if vals.get("invoice_id"):
                invoice = self.env["clinic.ar.invoice"].browse(vals["invoice_id"])
                vals.setdefault("partner_id", invoice.partner_id.id)
                vals.setdefault("patient_id", invoice.patient_id.id if invoice.patient_id else False)
                vals.setdefault("company_id", invoice.company_id.id)
                vals.setdefault("currency_id", invoice.currency_id.id)
            company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
            vals.setdefault("company_id", company.id)
            vals.setdefault("currency_id", company.currency_id.id)
        return super().create(vals_list)

    @api.onchange("invoice_id")
    def _onchange_invoice_id(self):
        for rec in self:
            if not rec.invoice_id:
                continue
            inv = rec.invoice_id
            rec.partner_id = inv.partner_id
            rec.patient_id = inv.patient_id
            rec.company_id = inv.company_id
            rec.currency_id = inv.currency_id
            rec.booking_id = inv.booking_id
            rec.treatment_session_id = inv.treatment_session_id
            rec.membership_id = inv.membership_id
            rec.amount = inv.amount_residual

    @api.onchange("method", "company_id")
    def _onchange_method(self):
        for rec in self:
            if rec.journal_id or not rec.company_id:
                continue
            preferred = "cash" if rec.method in {"cash", "card"} else "bank"
            rec.journal_id = self.env["account.journal"].search([
                ("company_id", "=", rec.company_id.id),
                ("type", "=", preferred),
            ], limit=1)

    @api.constrains("amount")
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Receipt Amount must be greater than zero."))

    @api.constrains("invoice_id", "partner_id", "company_id", "currency_id")
    def _check_scope(self):
        for rec in self:
            if not rec.invoice_id:
                continue
            if rec.invoice_id.partner_id.commercial_partner_id != rec.partner_id.commercial_partner_id:
                raise ValidationError(_("Receipt Customer must match the AR Invoice Customer."))
            if rec.invoice_id.company_id != rec.company_id:
                raise ValidationError(_("Receipt and AR Invoice must belong to the same company."))
            if rec.invoice_id.currency_id != rec.currency_id:
                raise ValidationError(_("Receipt and AR Invoice must use the same currency."))

    def write(self, vals):
        protected = {
            "company_id", "currency_id", "invoice_id", "partner_id", "amount",
            "payment_date", "journal_id", "method",
        }
        if protected.intersection(vals) and any(rec.state != "draft" for rec in self):
            raise UserError(_("Posted or cancelled AR Receipts are immutable."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state != "draft" for rec in self):
            raise UserError(_("Only draft AR Receipts can be deleted."))
        return super().unlink()

    def _get_journal(self):
        self.ensure_one()
        if self.journal_id:
            return self.journal_id
        preferred = "cash" if self.method in {"cash", "card"} else "bank"
        journal = self.env["account.journal"].search([
            ("company_id", "=", self.company_id.id),
            ("type", "=", preferred),
        ], limit=1)
        if not journal:
            journal = self.env["account.journal"].search([
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
            ], limit=1)
        if not journal:
            raise UserError(_("Configure a Cash or Bank journal for this company."))
        return journal

    def _prepare_account_payment_vals(self):
        self.ensure_one()
        journal = self._get_journal()
        method_line = journal.inbound_payment_method_line_ids[:1]
        values = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner_id.commercial_partner_id.id,
            "amount": self.amount,
            "date": self.payment_date,
            "journal_id": journal.id,
            "currency_id": self.currency_id.id,
            "memo": self.communication or self.name,
            "payment_reference": self.communication or self.name,
        }
        if method_line:
            values["payment_method_line_id"] = method_line.id
        return values

    def _reconcile_account_payment(self, payment):
        self.ensure_one()
        if not self.invoice_id or not self.invoice_id.move_id:
            raise UserError(_("A posted Accounting Invoice is required for reconciliation."))

        invoice_move = self.invoice_id.move_id
        partner = self.partner_id.commercial_partner_id
        invoice_lines = invoice_move.line_ids.filtered(
            lambda line: (
                line.account_id.account_type == "asset_receivable"
                and line.partner_id.commercial_partner_id == partner
                and not line.reconciled
            )
        )
        payment_lines = payment.move_id.line_ids.filtered(
            lambda line: (
                line.account_id.account_type == "asset_receivable"
                and line.partner_id.commercial_partner_id == partner
                and not line.reconciled
            )
        )
        if not invoice_lines or not payment_lines:
            raise UserError(
                _("Unable to locate compatible open receivable lines for strict AR reconciliation.")
            )
        (invoice_lines + payment_lines).reconcile()
        return True

    def action_post(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft AR Receipts can be posted."))
            if not rec.invoice_id or rec.invoice_id.state != "posted":
                raise UserError(_("A posted AR Invoice is required."))
            residual = rec.invoice_id.amount_residual
            rec.invoice_residual_snapshot = residual

            payment = self.env["account.payment"].with_company(rec.company_id).with_context(
                force_payment_move=True
            ).create(rec._prepare_account_payment_vals())
            payment.action_post()
            if not payment.move_id or payment.move_id.state != "posted":
                raise UserError(_("Odoo Accounting did not create a posted payment journal entry."))

            rec._reconcile_account_payment(payment)
            rec.account_payment_id = payment
            applied = min(rec.amount, residual)
            rec.applied_amount = rec.currency_id.round(applied)
            rec.overpay_amount = rec.currency_id.round(max(rec.amount - applied, 0.0))
            rec.is_overpay = rec.overpay_amount > 0
            rec.state = "posted"
            rec.invoice_id._sync_from_accounting()
            rec.invoice_id._emit_event("payment.posted")
            rec.message_post(
                body=_(
                    "AR Receipt posted. Applied: %(applied).2f; Open Credit: %(credit).2f",
                    applied=rec.applied_amount,
                    credit=rec.overpay_amount,
                )
            )
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "cancelled":
                continue
            if rec.account_payment_id:
                open_lines = rec.account_payment_id.move_id.line_ids.filtered(
                    lambda line: line.matched_debit_ids or line.matched_credit_ids
                )
                if open_lines:
                    open_lines.remove_move_reconcile()
                rec.account_payment_id.action_cancel()
            rec.state = "cancelled"
            if rec.invoice_id:
                rec.invoice_id._sync_from_accounting()
                rec.invoice_id._emit_event("payment.cancelled")
            rec.message_post(body=_("AR Receipt cancelled."))
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state != "cancelled":
                raise UserError(_("Only cancelled AR Receipts can be reset to draft."))
            if rec.account_payment_id:
                rec.account_payment_id.action_draft()
                rec.account_payment_id.unlink()
            rec.write({
                "state": "draft",
                "account_payment_id": False,
                "invoice_residual_snapshot": 0.0,
                "applied_amount": 0.0,
                "overpay_amount": 0.0,
                "is_overpay": False,
            })
        return True

    def action_open_account_payment(self):
        self.ensure_one()
        if not self.account_payment_id:
            raise UserError(_("No Accounting Payment is linked."))
        return self.account_payment_id._get_records_action(name=_("Accounting Payment"))

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No Journal Entry is linked."))
        return self.move_id._get_records_action(name=_("Payment Journal Entry"))

    def action_create_allocation(self):
        self.ensure_one()
        if self.state != "posted" or self.overpay_amount <= 0:
            raise UserError(_("Only posted receipts with open credit can create allocations."))
        allocation = self.env["clinic.ar.allocation"].create({
            "partner_id": self.partner_id.id,
            "payment_id": self.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
        })
        return allocation._get_records_action(name=_("AR Allocation"))



