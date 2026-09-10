# -*- coding: utf-8 -*-
# File: clinic_billing/models/billing_invoice.py
# License: LGPL-3 (following Odoo CE add-ons convention)

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicBillingInvoice(models.Model):
    """
    ClinicOne Billing Invoice
    -------------------------
    Core clinic billing document that wraps Accounting (account.move out_invoice) with
    clinical context and soft-coupled integrations to other ClinicOne modules.

    Design goals:
    - No circular dependency with clinic_patient et al.
    - Safe to install as the first model in clinic_billing.
    - Ready for incremental enrichment by other modules (membership, insurance, etc.).
    """
    _name = "clinic.billing.invoice"
    _description = "Clinic Billing Invoice"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _rec_name = "name"

    # -------------------------------------------------------------------------
    # Identity & Lifecycle
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Invoice Number",
        default="/",
        copy=False,
        index=True,
        tracking=True,
        help="Clinic billing number (sequence)."
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("posted", "Posted"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        help="Lifecycle status of this clinic billing record."
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        help="Owning company."
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        help="Currency for amounts on this invoice."
    )

    line_ids = fields.One2many(
        "clinic.billing.line",
        "invoice_id",
        string="Billing Lines",
        copy=True,
        help="Clinical services, products, discounts and benefit lines included in this billing document.",
    )

    # -------------------------------------------------------------------------
    # Parties & Clinical Context (soft-coupled)
    # -------------------------------------------------------------------------
    clinic_patient_id = fields.Many2one(
        "clinic.patient",
        string="Clinic Patient",
        index=True,
        tracking=True,
        check_company=True,
        help="Canonical ClinicOne patient record. The accounting patient/contact is synchronized from this record.",
    )
    clinic_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Clinic Doctor",
        index=True,
        tracking=True,
        check_company=True,
        help="Canonical ClinicOne doctor responsible for the billing context.",
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        required=True,
        tracking=True,
        domain=[("type", "!=", "private")],
        help="Patient being billed (a customer partner)."
    )
    # Doctor can be represented as a partner and/or user for flexibility
    doctor_partner_id = fields.Many2one(
        "res.partner",
        string="Doctor (Partner)",
        help="Doctor in charge, represented as a partner contact with Doctor tag."
    )
    doctor_user_id = fields.Many2one(
        "res.users",
        string="Doctor (User)",
        help="Doctor in charge, represented as an internal user (optional)."
    )
    clinic_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Clinic Branch",
        help="Clinic branch/location where the service took place."
    )

    # Optional clinical references (Booking, Treatment, Encounter, Package, etc.)
    # Keep selection strings aligned with the rest of ClinicOne naming.
    clinical_ref = fields.Reference(
        selection="_selection_clinical_ref",
        string="Clinical Reference",
        help="Optional source record that originated this billing document.",
    )
    booking_id = fields.Many2one(
        "booking.booking", string="Booking", index=True, check_company=True
    )
    encounter_id = fields.Many2one(
        "clinic.encounter", string="Encounter", index=True, check_company=True
    )
    care_plan_id = fields.Many2one(
        "clinic.care.plan", string="Care Plan", index=True, check_company=True
    )
    package_allocation_id = fields.Many2one(
        "clinic.package.allocation", string="Package Allocation", index=True, check_company=True
    )
    external_origin = fields.Char(
        string="External Origin",
        help="External source code/number (e.g., Booking code, Treatment code)."
    )

    # Commercial / fiscal context
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Pricelist",
        help="Pricelist used for price computation (if applicable)."
    )
    payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Payment Terms",
        help="Payment terms passed to the accounting invoice."
    )
    fiscal_position_id = fields.Many2one(
        "account.fiscal.position",
        string="Fiscal Position",
        help="Tax/account mapping for the accounting invoice."
    )

    # -------------------------------------------------------------------------
    # Accounting Binding (account.move)
    # -------------------------------------------------------------------------
    move_id = fields.Many2one(
        "account.move",
        string="Accounting Invoice",
        readonly=True,
        copy=False,
        index=True,
        help="Linked account.move (Customer Invoice)."
    )
    move_state = fields.Selection(
        related="move_id.state",
        string="Journal State",
        readonly=True
    )
    move_type = fields.Selection(
        related="move_id.move_type",
        string="Move Type",
        readonly=True
    )
    payment_state = fields.Selection(
        related="move_id.payment_state",
        string="Payment State",
        readonly=True
    )

    invoice_date = fields.Date(
        string="Invoice Date",
        help="Requested accounting invoice date (defaults to today on generation)."
    )
    invoice_date_due = fields.Date(
        string="Due Date",
        help="Requested due date for the accounting invoice."
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Sales Journal",
        domain=[("type", "in", ("sale", "general"))],
        help="Journal used when generating the accounting invoice."
    )

    # Direct view into move lines for convenience in form/tree (read-only mirror)
    move_line_ids = fields.One2many(
        comodel_name="account.move.line",
        related="move_id.line_ids",
        string="Accounting Lines",
        readonly=True,
        help="Lines of the linked accounting invoice (read-only mirror).",
    )

    # -------------------------------------------------------------------------
    # Amount Mirrors (from account.move)
    # -------------------------------------------------------------------------
    amount_untaxed = fields.Monetary(
        string="Untaxed Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        help="Mirror of untaxed amount from the accounting invoice."
    )
    amount_tax = fields.Monetary(
        string="Tax",
        currency_field="currency_id",
        compute="_compute_amounts",
        help="Mirror of tax amount from the accounting invoice."
    )
    amount_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        compute="_compute_amounts",
        help="Mirror of total amount from the accounting invoice."
    )
    amount_residual = fields.Monetary(
        string="Amount Due",
        currency_field="currency_id",
        compute="_compute_amounts",
        help="Mirror of residual amount from the accounting invoice."
    )
    is_paid = fields.Boolean(
        string="Is Paid?",
        compute="_compute_is_paid",
        search="_search_is_paid",
        help="True if the accounting invoice is fully paid."
    )
    is_overdue = fields.Boolean(
        string="Is Overdue?",
        compute="_compute_is_overdue",
        search="_search_is_overdue",
        help="True if the invoice is overdue (due date passed and still unpaid)."
    )
    days_overdue = fields.Integer(
        string="Days Overdue",
        compute="_compute_is_overdue",
        help="Number of days past due date when still unpaid."
    )

    # -------------------------------------------------------------------------
    # Discounts / Insurance / Membership / Voucher / Commission (hooks)
    # -------------------------------------------------------------------------
    discount_note = fields.Char(
        string="Discount Note",
        help="Reason for discount or voucher code reference."
    )
    voucher_code = fields.Char(
        string="Voucher Code",
        help="Applied voucher/coupon code (if any)."
    )

    insurer_partner_id = fields.Many2one(
        "res.partner",
        string="Insurer",
        help="Insurance company responsible for the covered amount.",
    )
    insurance_copay_percent = fields.Float(
        string="Insurance Co-pay (%)",
        digits=(16, 2),
        help="Patient co-pay percentage for the insurance context.",
    )
    membership_level_key = fields.Char(
        string="Membership Level Key",
        help="Soft membership tier key used by billing benefit rules.",
    )

    insurance_policy_number = fields.Char(
        string="Insurance Policy",
        help="Insurance policy number used for this invoice (if any)."
    )
    insurance_coverage_percent = fields.Float(
        string="Insurance Coverage (%)",
        digits=(16, 2),
        help="Coverage percentage (informational, split accounting occurs on move)."
    )
    insurance_claim_state = fields.Selection(
        [
            ("none", "None"),
            ("prepared", "Prepared"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("settled", "Settled"),
        ],
        string="Insurance Claim State",
        default="none",
        tracking=True,
        help="High-level state of claim process; detailed records live in insurance module."
    )

    membership_reference = fields.Char(
        string="Membership Reference",
        help="Membership wallet or ID used for partial/full coverage."
    )
    membership_amount_used = fields.Monetary(
        string="Membership Amount Used",
        currency_field="currency_id",
        help="Amount covered by membership wallet (informational)."
    )

    commission_policy = fields.Selection(
        [
            ("none", "None"),
            ("fixed_percent", "Fixed Percent"),
            ("tiered", "Tiered"),
            ("per_treatment", "Per Treatment"),
        ],
        string="Doctor Commission Policy",
        default="none",
        help="Commission policy hint; detailed computation lives in commission module."
    )
    commission_amount = fields.Monetary(
        string="Commission Amount",
        currency_field="currency_id",
        help="Computed commission amount (may be set by commission engine)."
    )

    # Misc
    note = fields.Text(
        string="Internal Notes",
        help="Internal-only notes for staff."
    )

    # Smart buttons counters (computed lazily)
    payments_count = fields.Integer(
        string="Payments",
        compute="_compute_payments_count",
        help="Number of payments reconciled with the accounting invoice."
    )
    # insurance_docs_count = fields.Integer(
    #     string="Insurance Docs",
    #     compute="_compute_insurance_docs_count",
    #     help="Number of linked insurance documents (if insurance module is installed)."
    # )
    vouchers_count = fields.Integer(
        string="Vouchers",
        compute="_compute_vouchers_count",
        help="Number of linked vouchers (if voucher module is installed)."
    )
    commissions_count = fields.Integer(
        string="Commissions",
        compute="_compute_commissions_count",
        help="Number of commission lines/records (if commission module is installed)."
    )

    @api.model
    def _selection_clinical_ref(self):
        """Only expose source models that are part of the authoritative ClinicOne baseline."""
        candidates = [
            ("booking.booking", _("Booking")),
            ("clinic.encounter", _("Encounter")),
            ("clinic.care.plan", _("Care Plan")),
            ("clinic.package.allocation", _("Package Allocation")),
            ("clinic.package.usage", _("Package Redemption")),
            ("clinic.emar.order", _("eMAR Order")),
            ("clinic.emar.administration", _("eMAR Administration")),
            ("clinic.treatment", _("Treatment")),
        ]
        return [(model, label) for model, label in candidates if model in self.env]

    @api.onchange("clinic_patient_id")
    def _onchange_clinic_patient_id(self):
        for rec in self:
            if rec.clinic_patient_id and rec.clinic_patient_id.partner_id:
                rec.patient_id = rec.clinic_patient_id.partner_id

    @api.onchange("clinic_doctor_id")
    def _onchange_clinic_doctor_id(self):
        for rec in self:
            doctor = rec.clinic_doctor_id
            if doctor:
                rec.doctor_partner_id = doctor.partner_id
                rec.doctor_user_id = doctor.user_id

    # -------------------------------------------------------------------------
    # HELPERS (Registry checks)
    # -------------------------------------------------------------------------
    @api.model
    def _model(self, model_name):
        """Return model env if exists, else False (safe soft dependency)."""
        return self.env[model_name] if model_name in self.env else False

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends(
        "move_id.amount_untaxed",
        "move_id.amount_tax",
        "move_id.amount_total",
        "move_id.amount_residual",
        "line_ids.subtotal_excl_tax",
        "line_ids.tax_amount",
        "line_ids.total_incl_tax",
    )
    def _compute_amounts(self):
        for rec in self:
            if rec.move_id:
                rec.amount_untaxed = rec.move_id.amount_untaxed
                rec.amount_tax = rec.move_id.amount_tax
                rec.amount_total = rec.move_id.amount_total
                rec.amount_residual = rec.move_id.amount_residual
                continue

            billable_lines = rec.line_ids.filtered(lambda line: not line.display_type)
            rec.amount_untaxed = sum(billable_lines.mapped("subtotal_excl_tax"))
            rec.amount_tax = sum(billable_lines.mapped("tax_amount"))
            rec.amount_total = sum(billable_lines.mapped("total_incl_tax"))
            rec.amount_residual = rec.amount_total

    @api.depends("payment_state")
    def _compute_is_paid(self):
        for rec in self:
            rec.is_paid = bool(rec.payment_state == "paid")

    @api.depends("invoice_date_due", "amount_residual")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.invoice_date_due and rec.amount_residual and rec.amount_residual > 0:
                rec.is_overdue = rec.invoice_date_due < today
                rec.days_overdue = (today - rec.invoice_date_due).days if rec.is_overdue else 0
            else:
                rec.is_overdue = False
                rec.days_overdue = 0

    @api.model
    def _search_is_paid(self, operator, value):
        """Translate boolean searches to the persisted billing lifecycle state."""
        if operator not in ("=", "!="):
            raise ValueError("Unsupported operator for Is Paid search: %s" % operator)
        expected = bool(value)
        positive = expected if operator == "=" else not expected
        return [("state", "=", "paid")] if positive else [("state", "!=", "paid")]

    @api.model
    def _search_is_overdue(self, operator, value):
        """Search overdue documents without relying on a non-stored computed field."""
        if operator not in ("=", "!="):
            raise ValueError("Unsupported operator for Is Overdue search: %s" % operator)
        expected = bool(value)
        positive = expected if operator == "=" else not expected
        today = fields.Date.context_today(self)
        overdue_domain = [
            ("invoice_date_due", "<", today),
            ("state", "not in", ("paid", "cancelled")),
        ]
        if positive:
            return overdue_domain
        # NOT(A and B) == (not A) or (not B)
        return [
            "|",
            "|",
            ("invoice_date_due", "=", False),
            ("invoice_date_due", ">=", today),
            ("state", "in", ("paid", "cancelled")),
        ]

    def _compute_payments_count(self):
        Payment = self._model("account.payment")
        for rec in self:
            if not (rec.move_id and Payment):
                rec.payments_count = 0
                continue
            rec.payments_count = Payment.search_count([("reconciled_invoice_ids", "in", rec.move_id.ids)])

    # def _compute_insurance_docs_count(self):
    #     Claim = self._model("clinic.insurance.claim")
    #     for rec in self:
    #         if not (Claim and rec.id):
    #             rec.insurance_docs_count = 0
    #             continue
    #         rec.insurance_docs_count = Claim.search_count([("billing_invoice_id", "=", rec.id)])

    def _compute_vouchers_count(self):
        Voucher = self._model("clinic.billing.voucher")
        for rec in self:
            if not (Voucher and rec.id):
                rec.vouchers_count = 0
                continue
            rec.vouchers_count = Voucher.search_count([("reserved_invoice_id", "=", rec.id)])

    def _compute_commissions_count(self):
        Commission = self._model("clinic.billing.commission.line")
        for rec in self:
            if not (Commission and rec.id):
                rec.commissions_count = 0
                continue
            rec.commissions_count = Commission.search_count([("invoice_id", "=", rec.id)])

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        """Derive fiscal context from patient."""
        if self.patient_id:
            self.payment_term_id = self.patient_id.property_payment_term_id.id
            fp = self.env["account.fiscal.position"].get_fiscal_position(self.patient_id)
            self.fiscal_position_id = fp.id if fp else False

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("patient_id")
    def _check_patient(self):
        for rec in self:
            if not rec.patient_id:
                raise ValidationError(_("Patient is required."))

    _name_company_unique = models.Constraint(
        "UNIQUE(name, company_id)",
        "Invoice Number must be unique per company.",
    )

    # -------------------------------------------------------------------------
    # SEQUENCE
    # -------------------------------------------------------------------------
    def _next_sequence(self):
        """Return next sequence for clinic billing invoice."""
        return self.env["ir.sequence"].sudo().next_by_code("clinic.billing.invoice") or "/"

    # -------------------------------------------------------------------------
    # LIFECYCLE ACTIONS
    # -------------------------------------------------------------------------
    def action_confirm(self):
        """Move from Draft to Confirmed: validate basic requirements, assign number."""
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.patient_id:
                raise UserError(_("Please set the Patient before confirming."))
            if rec.name in (False, "/", ""):
                rec.name = rec._next_sequence()
            rec._on_after_confirm()
            rec.with_context(clinic_billing_skip_state_sync=True).write({"state": "confirmed"})
        return True

    def _on_after_confirm(self):
        """Hook for other modules: pricing locks, package consumption, etc."""
        # Example soft calls (will run only if models exist):
        # - clinic.package: reserve quotas
        # - clinic.pricing: freeze computed prices
        pass

    def action_reset_to_draft(self):
        """Allowed only if no posted accounting move is linked."""
        for rec in self:
            if rec.move_id and rec.move_id.state == "posted":
                raise UserError(_("Cannot reset to Draft because the accounting invoice is posted."))
            if rec.state in ("cancelled", "confirmed"):
                rec.state = "draft"
        return True

    def action_cancel(self):
        """Cancel only if no posted accounting move."""
        for rec in self:
            if rec.move_id and rec.move_id.state == "posted":
                raise UserError(_("You cannot cancel because the accounting invoice is already posted. Consider a credit note/refund."))
            rec._on_before_cancel()
            rec.state = "cancelled"
            rec._on_after_cancel()
        return True

    def _on_before_cancel(self):
        """Hook for other modules: rollback reservations, reverse package usage, etc."""
        pass

    def _on_after_cancel(self):
        """Hook for other modules: audit trails, notify stakeholders, etc."""
        pass

    def _sync_state_from_move(self):
        """Sync clinic state with accounting state/payment_state."""
        for rec in self:
            if not rec.move_id:
                continue
            if rec.move_id.state == "draft":
                # keep as confirmed to indicate already prepared
                if rec.state not in ("paid", "cancelled"):
                    rec.with_context(clinic_billing_skip_state_sync=True).write({"state": "confirmed"})
            elif rec.move_id.state == "posted":
                rec.with_context(clinic_billing_skip_state_sync=True).write({"state": "paid" if rec.move_id.payment_state == "paid" else "posted"})

    # -------------------------------------------------------------------------
    # ACCOUNTING GENERATION (safe minimal draft)
    # -------------------------------------------------------------------------
    def _ensure_placeholder_service_product(self):
        """Ensure there is a generic service product to build a minimal invoice."""
        Product = self.env["product.product"].sudo()
        product = Product.search([
            ("default_code", "=", "CLINIC-SERVICE-PLACEHOLDER"),
            ("company_id", "in", [False, self.env.company.id])], limit=1)
        if product:
            return product
        tmpl_vals = {
            "name": "Clinic Service (Placeholder)",
            "type": "service",
            "default_code": "CLINIC-SERVICE-PLACEHOLDER",
            "lst_price": 0.0,
            "company_id": self.env.company.id,
        }
        return Product.create(tmpl_vals)

    def _resolve_income_account(self, product):
        """Resolve income account for a product; fallback to a generic income account."""
        income = product.property_account_income_id or product.categ_id.property_account_income_categ_id
        if income:
            return income
        company = self.env.company
        Account = self.env["account.account"].sudo().with_company(company)
        acc = Account.search([
            *Account._check_company_domain(company),
            ("account_type", "=", "income"),
        ], limit=1)
        if not acc:
            raise UserError(_("No income account found for company %s. Configure chart of accounts.")
                            % self.env.company.display_name)
        return acc

    # ------- Enrichment hooks for other modules (pricing/lines/insurance/membership) -------
    def _collect_planned_lines(self):
        """Map the real Clinic Billing lines into standard invoice lines.

        Accounting must reflect the commercial document.  A zero-value
        placeholder would create a fake ledger and disconnect AR totals from
        their source billing document.
        """
        self.ensure_one()
        planned = []
        for line in self.line_ids.sorted("sequence"):
            if line.display_type:
                planned.append({
                    "display_type": line.display_type,
                    "name": line.name or "",
                })
                continue
            if not line.product_id:
                raise UserError(_("Every monetary Billing line requires a Product/Service."))
            if line.quantity <= 0:
                raise UserError(_("Every monetary Billing line requires a positive quantity."))
            planned.append({
                "name": line.name or line.product_id.display_name,
                "product_id": line.product_id.id,
                "product_uom_id": line.product_uom_id.id or line.product_id.uom_id.id,
                "quantity": line.quantity,
                "price_unit": line.get_effective_unit_price(),
                "tax_ids": [(6, 0, line.tax_ids.ids)],
                "account_id": self._resolve_income_account(line.product_id).id,
            })
        if not any(not values.get("display_type") for values in planned):
            raise UserError(_("At least one monetary Billing line is required."))
        return planned

    def _apply_pricing_rules(self, line_vals_list):
        """
        Hook: Apply pricelist, discounts, vouchers, membership/insurance hints to line values.
        This is intentionally a placeholder; detailed math should live in pricing/voucher modules.
        """
        # Example: If voucher_code present, tag on line name
        if self.voucher_code:
            for lv in line_vals_list:
                lv["name"] = (lv.get("name") or "") + _(" (Voucher: %s)") % self.voucher_code
        return line_vals_list

    def action_generate_account_move(self):
        """
        Create a minimal draft customer invoice (account.move) for this clinic billing.
        Detailed line construction is delegated to hook methods for extensibility.
        """
        for rec in self:
            if rec.move_id:
                raise UserError(_("An accounting invoice is already linked."))
            if rec.state not in ("confirmed", "draft"):
                raise UserError(_("Only Draft/Confirmed documents can generate an accounting invoice."))

            partner = rec.patient_id
            if not partner:
                raise UserError(_("Patient is required to generate the accounting invoice."))

            journal = rec.journal_id or self.env["account.journal"].sudo().search([
                ("type", "=", "sale"),
                ("company_id", "=", rec.company_id.id)
            ], limit=1)
            if not journal:
                raise UserError(_("No Sales Journal found for company %s.") % rec.company_id.display_name)

            # Collect initial planned lines then let pricing/discount modules modify them
            planned_lines = rec._collect_planned_lines()
            planned_lines = rec._apply_pricing_rules(planned_lines)

            line_commands = [(0, 0, lv) for lv in planned_lines]

            move_vals = {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": rec.invoice_date or fields.Date.context_today(self),
                "invoice_date_due": rec.invoice_date_due or False,
                "currency_id": rec.currency_id.id,
                "invoice_origin": rec.external_origin or rec.name or "",
                "invoice_line_ids": line_commands,
                "journal_id": journal.id,
                "invoice_payment_term_id": rec.payment_term_id.id if rec.payment_term_id else False,
                "fiscal_position_id": rec.fiscal_position_id.id if rec.fiscal_position_id else False,
                "company_id": rec.company_id.id,
            }

            move = self.env["account.move"].sudo().create(move_vals)
            rec.move_id = move.id
            # Back sync critical dates
            rec.invoice_date = move.invoice_date
            rec.invoice_date_due = move.invoice_date_due

            # Hook: allow other modules to attach metadata (insurance claim draft, membership locks)
            rec._on_after_move_created(move)
            # Sync clinic state
            rec._sync_state_from_move()
        return True

    def _on_after_move_created(self, move):
        """Hook: after account.move was created (e.g., prepare insurance claim draft)."""
        # Example integrations:
        # - clinic_insurance: create draft claim record linked to this billing.
        # - clinic_membership: record a reserved membership deduction.
        pass

    def action_post_account_move(self):
        """Post the accounting invoice and sync clinical state."""
        for rec in self:
            if not rec.move_id:
                raise UserError(_("No accounting invoice to post. Please generate it first."))
            if rec.move_id.state != "posted":
                rec.move_id.sudo().action_post()
            # Commission engine or audit hook on posting
            rec._on_after_move_posted(rec.move_id)
            rec._sync_state_from_move()
        return True

    def _on_after_move_posted(self, move):
        """
        Hook after posting:
        - Trigger commission computation
        - Trigger audit log
        - Trigger insurance submit (if auto-submit policy enabled)
        """
        # Example soft calls (only if models exist):
        # Commission = self._model("clinic.billing.commission.engine")
        # if Commission:
        #     Commission.compute_for_billing(self.id)
        pass

    # -------------------------------------------------------------------------
    # UI Actions (Smart Buttons)
    # -------------------------------------------------------------------------
    def action_view_account_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No accounting invoice linked yet."))
        action = self.env.ref("account.action_move_out_invoice_type").read()[0]
        action.update({
            "views": [(self.env.ref("account.view_move_form").id, "form")],
            "res_id": self.move_id.id,
            "domain": [("id", "=", self.move_id.id)],
        })
        return action

    def action_view_payments(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No accounting invoice linked yet."))
        action = self.env.ref("account.action_account_payments").read()[0]
        action.update({
            "domain": [("reconciled_invoice_ids", "in", self.move_id.ids)],
            "context": {"default_partner_id": self.patient_id.id},
        })
        return action

    # def action_open_insurance_documents(self):
    #     self.ensure_one()
    #     Claim = self._model("clinic.insurance.claim")
    #     if not Claim:
    #         raise UserError(_("Insurance module is not installed."))
    #     action = {
    #         "type": "ir.actions.act_window",
    #         "name": _("Insurance Claims"),
    #         "res_model": "clinic.insurance.claim",
    #         "view_mode": "list,form",
    #         "domain": [("invoice_id", "=", self.id)],
    #         "context": {"default_invoice_id": self.id},
    #     }
    #     return action

    def action_open_commissions(self):
        self.ensure_one()
        CommissionLine = self._model("clinic.billing.commission.line")
        if not CommissionLine:
            raise UserError(_("Commission module is not installed."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Commissions"),
            "res_model": "clinic.billing.commission.line",
            "view_mode": "list,form",
            "domain": [("invoice_id", "=", self.id)],
            "context": {"default_invoice_id": self.id},
        }

    def action_open_vouchers(self):
        self.ensure_one()
        Voucher = self._model("clinic.billing.voucher")
        if not Voucher:
            raise UserError(_("Voucher module is not installed."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Vouchers"),
            "res_model": "clinic.billing.voucher",
            "view_mode": "list,form",
            "domain": [("reserved_invoice_id", "=", self.id)],
            "context": {"default_reserved_invoice_id": self.id},
        }

    # -------------------------------------------------------------------------
    # CREATE/WRITE OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        patient_model = self.env["clinic.patient"]
        doctor_model = self.env["clinic.doctor"]
        for vals in vals_list:
            patient_id = vals.get("clinic_patient_id")
            if patient_id and not vals.get("patient_id"):
                patient = patient_model.browse(patient_id).exists()
                if patient and patient.partner_id:
                    vals["patient_id"] = patient.partner_id.id
            doctor_id = vals.get("clinic_doctor_id")
            if doctor_id:
                doctor = doctor_model.browse(doctor_id).exists()
                if doctor:
                    vals.setdefault("doctor_partner_id", doctor.partner_id.id if doctor.partner_id else False)
                    vals.setdefault("doctor_user_id", doctor.user_id.id if doctor.user_id else False)
            if not vals.get("name") or vals.get("name") in ("/", False):
                vals["name"] = (
                    self.env.context.get("clinic_demo_billing_name")
                    or self.env["ir.sequence"].sudo().next_by_code("clinic.billing.invoice")
                    or "/"
                )
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("currency_id"):
                vals["currency_id"] = self.env.company.currency_id.id
        records = super().create(vals_list)
        # Post-create hook (audit, initial activities)
        for rec in records:
            rec._on_after_create()
        return records

    def _on_after_create(self):
        """Hook: schedule activities, log audit entries, notify stakeholders."""
        # Example:
        # if self._model("clinic.audit.log"):
        #     self.env["clinic.audit.log"].sudo().create({...})
        pass

    def write(self, vals):
        vals = dict(vals)
        protected = {
            "patient_id", "clinic_patient_id", "clinic_doctor_id", "company_id", "currency_id",
            "line_ids", "pricelist_id", "payment_term_id", "fiscal_position_id",
            "invoice_date", "invoice_date_due", "journal_id",
        }
        if protected.intersection(vals):
            locked = self.filtered(lambda rec: rec.move_id and rec.move_id.state == "posted")
            if locked:
                raise UserError(_("Posted billing documents are financially locked. Create a credit note/correction instead."))
        if "clinic_patient_id" in vals and "patient_id" not in vals:
            patient = self.env["clinic.patient"].browse(vals["clinic_patient_id"]).exists()
            vals["patient_id"] = patient.partner_id.id if patient and patient.partner_id else False
        if "clinic_doctor_id" in vals:
            doctor = self.env["clinic.doctor"].browse(vals["clinic_doctor_id"]).exists()
            if doctor:
                vals.setdefault("doctor_partner_id", doctor.partner_id.id if doctor.partner_id else False)
                vals.setdefault("doctor_user_id", doctor.user_id.id if doctor.user_id else False)
        res = super().write(vals)
        # Do not recurse while the synchronization itself is writing state.
        if not self.env.context.get("clinic_billing_skip_state_sync"):
            self.with_context(clinic_billing_skip_state_sync=True)._sync_state_from_move()
        return res

    def unlink(self):
        locked = self.filtered(lambda rec: rec.state not in ("draft", "cancelled") or (rec.move_id and rec.move_id.state == "posted"))
        if locked:
            raise UserError(_("Only Draft or Cancelled billing documents without a posted accounting invoice can be deleted."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # PAYMENT HELPERS
    # -------------------------------------------------------------------------
    def action_register_payment(self):
        """
        Open Register Payment wizard for linked account.move (standard Odoo flow).
        """
        self.ensure_one()
        if not self.move_id or self.move_id.state != "posted":
            raise UserError(_("Please post the accounting invoice first."))
        return self.move_id.action_register_payment()

    # -------------------------------------------------------------------------
    # EXPORT/ACCOUNTING HELPERS
    # -------------------------------------------------------------------------
    def _export_for_finance(self):
        """
        Hook: Provide summarized data for finance/reporting export pipelines.
        Other modules can extend this via inheritance.
        """
        self.ensure_one()
        return {
            "clinic_invoice": self.name,
            "patient": self.patient_id.display_name if self.patient_id else "",
            "doctor": self.doctor_partner_id.display_name if self.doctor_partner_id else "",
            "company": self.company_id.display_name,
            "currency": self.currency_id.name,
            "state": self.state,
            "amount_total": self.amount_total or 0.0,
            "amount_residual": self.amount_residual or 0.0,
            "invoice_date": self.invoice_date or False,
            "invoice_date_due": self.invoice_date_due or False,
            "payment_state": self.payment_state or "",
            "insurance_state": self.insurance_claim_state or "none",
            "membership_used": self.membership_amount_used or 0.0,
            "voucher_code": self.voucher_code or "",
        }

