from odoo import fields, models, _


class ClinicReportEngineFinancial(models.AbstractModel):
    """Financial report family using existing Billing/AR/AP/Finance/Accounting sources."""

    _name = "clinic.report.engine.financial"
    _description = "Clinic Reports Financial Engine"

    # Billing revenue uses posted/paid Clinic Billing invoices, not accounting guesses or dashboard caches.
    def _generate_fin_revenue(self):
        self.ensure_one()
        Invoice = self.env["clinic.billing.invoice"]
        invoices = Invoice.sudo().search(
            self._report_domain(
                "clinic.billing.invoice",
                "invoice_date",
                self.date_from,
                self.date_to,
                extra=[("state", "in", ("posted", "paid"))],
                branch_path="move_id.branch_id",
            ),
            order="invoice_date, id",
        )

        gross = sum(invoices.mapped("amount_total"))
        untaxed = sum(invoices.mapped("amount_untaxed"))
        tax = sum(invoices.mapped("amount_tax"))
        residual = sum(invoices.mapped("amount_residual"))
        collected = gross - residual
        paid_count = len(invoices.filtered("is_paid"))

        self._add_metric("INVOICE_COUNT", _("Posted/Paid Invoices"), len(invoices), "count", 10)
        self._add_metric("GROSS_REVENUE", _("Gross Revenue"), gross, "amount", 20)
        self._add_metric("UNTAXED_REVENUE", _("Untaxed Revenue"), untaxed, "amount", 30)
        self._add_metric("TAX_AMOUNT", _("Tax Amount"), tax, "amount", 40)
        self._add_metric("COLLECTED_AMOUNT", _("Collected Amount"), collected, "amount", 50)
        self._add_metric("OUTSTANDING_AMOUNT", _("Outstanding Amount"), residual, "amount", 60)
        self._add_metric(
            "COLLECTION_RATE",
            _("Collection Rate"),
            self._percentage(collected, gross),
            "percentage",
            70,
        )
        self._add_metric("PAID_INVOICE_COUNT", _("Paid Invoices"), paid_count, "count", 80)

        for invoice in invoices:
            self._add_detail(
                invoice,
                _("Billing Invoice"),
                event_date=invoice.invoice_date,
                reference=invoice.name,
                state_label=invoice.state,
                partner=invoice.patient_id,
                patient=invoice.clinic_patient_id,
                doctor=invoice.clinic_doctor_id,
                amount=invoice.amount_total,
                note=_("Residual: %.2f") % (invoice.amount_residual or 0.0),
            )

    # AR aging consumes the upstream stored overdue/aging contract so one aging definition remains authoritative.
    def _generate_fin_receivables(self):
        self.ensure_one()
        Invoice = self.env["clinic.ar.invoice"]
        invoices = Invoice.sudo().search(
            self._report_domain(
                "clinic.ar.invoice",
                "invoice_date",
                self.date_from,
                self.date_to,
                extra=[("state", "=", "posted")],
                branch_path="move_id.branch_id",
            ),
            order="invoice_date, id",
        )

        total = sum(invoices.mapped("amount_total"))
        paid = sum(invoices.mapped("amount_paid"))
        residual = sum(invoices.mapped("amount_residual"))
        overdue = invoices.filtered("is_overdue")
        overdue_amount = sum(overdue.mapped("amount_residual"))
        avg_days = (
            sum(overdue.mapped("days_overdue")) / len(overdue)
            if overdue
            else 0.0
        )

        self._add_metric("AR_INVOICE_COUNT", _("Posted AR Invoices"), len(invoices), "count", 10)
        self._add_metric("AR_TOTAL", _("Receivable Total"), total, "amount", 20)
        self._add_metric("AR_PAID", _("Amount Paid"), paid, "amount", 30)
        self._add_metric("AR_RESIDUAL", _("Outstanding Receivable"), residual, "amount", 40)
        self._add_metric("AR_OVERDUE_COUNT", _("Overdue Invoices"), len(overdue), "count", 50)
        self._add_metric("AR_OVERDUE_AMOUNT", _("Overdue Amount"), overdue_amount, "amount", 60)
        self._add_metric("AR_AVG_DAYS_OVERDUE", _("Average Days Overdue"), avg_days, "number", 70)

        bucket_totals = {}
        for invoice in invoices:
            bucket = invoice.aging_bucket or "not_due"
            bucket_totals[bucket] = bucket_totals.get(bucket, 0.0) + invoice.amount_residual
        for index, bucket in enumerate(sorted(bucket_totals)):
            self._add_metric(
                f"AGING_{bucket}",
                _("Aging %s") % bucket.replace("_", " ").title(),
                bucket_totals[bucket],
                "amount",
                100 + index,
            )

        for invoice in invoices:
            self._add_detail(
                invoice,
                _("Accounts Receivable"),
                event_date=invoice.invoice_date,
                reference=invoice.name,
                state_label=invoice.payment_state or invoice.state,
                partner=invoice.partner_id,
                patient=invoice.patient_id,
                doctor=invoice.doctor_id,
                treatment=invoice.treatment_id,
                amount=invoice.amount_residual,
                note=_("Due %s | Aging %s")
                % (invoice.due_date or "-", invoice.aging_bucket or "-"),
            )

    def _generate_fin_payables(self):
        self.ensure_one()
        Payable = self.env["clinic.ap"]
        payables = Payable.sudo().search(
            self._report_domain(
                "clinic.ap",
                "invoice_date",
                self.date_from,
                self.date_to,
                extra=[
                    ("state", "in", ("approved", "posted", "partial", "paid")),
                ],
                branch_path="move_id.branch_id",
            ),
            order="invoice_date, id",
        )

        total = sum(payables.mapped("amount_total"))
        residual = sum(payables.mapped("amount_residual"))
        paid = sum(payables.mapped("amount_paid"))
        open_docs = payables.filtered(lambda rec: rec.state in ("approved", "posted", "partial"))

        self._add_metric("AP_DOCUMENT_COUNT", _("AP Documents"), len(payables), "count", 10)
        self._add_metric("AP_TOTAL", _("Payable Total"), total, "amount", 20)
        self._add_metric("AP_PAID", _("Paid Amount"), paid, "amount", 30)
        self._add_metric("AP_RESIDUAL", _("Outstanding Payable"), residual, "amount", 40)
        self._add_metric("AP_OPEN_COUNT", _("Open Payables"), len(open_docs), "count", 50)

        self._state_breakdown_metrics(payables, "AP_STATE", 100)

        for payable in payables:
            self._add_detail(
                payable,
                _("Accounts Payable"),
                event_date=payable.invoice_date,
                reference=payable.name,
                state_label=payable.state,
                partner=payable.vendor_id,
                amount=payable.amount_residual,
                note=_("Total %.2f | Due %s")
                % (payable.amount_total or 0.0, payable.invoice_date_due or "-"),
            )

    def _generate_fin_cashflow(self):
        self.ensure_one()
        Transaction = self.env["clinic.finance.transaction"]
        transactions = Transaction.sudo().search(
            self._report_domain(
                "clinic.finance.transaction",
                "transaction_date",
                self.date_from,
                self.date_to,
                extra=[("state", "=", "posted")],
            ),
            order="transaction_date, id",
        )

        inflow = sum(
            rec.amount for rec in transactions if rec.direction == "in"
        )
        outflow = sum(
            rec.amount for rec in transactions if rec.direction == "out"
        )
        net = inflow - outflow

        self._add_metric("CASH_TX_COUNT", _("Posted Finance Transactions"), len(transactions), "count", 10)
        self._add_metric("CASH_INFLOW", _("Cash Inflow"), inflow, "amount", 20)
        self._add_metric("CASH_OUTFLOW", _("Cash Outflow"), outflow, "amount", 30)
        self._add_metric("NET_CASHFLOW", _("Net Cash Flow"), net, "amount", 40)
        self._add_metric(
            "INFLOW_SHARE",
            _("Inflow Share"),
            self._percentage(inflow, inflow + outflow),
            "percentage",
            50,
        )

        for transaction in transactions:
            signed = transaction.amount if transaction.direction == "in" else -transaction.amount
            self._add_detail(
                transaction,
                _("Finance Transaction"),
                event_date=transaction.transaction_date,
                reference=transaction.name,
                state_label=transaction.direction,
                partner=transaction.partner_id,
                amount=signed,
                note=transaction.category_id.display_name if transaction.category_id else "",
            )

    # Accounting Activity reads posted journal items only; Reports never creates or adjusts accounting entries.
    def _generate_fin_accounting(self):
        self.ensure_one()
        MoveLine = self.env["account.move.line"]
        extra = [("parent_state", "=", "posted")]
        lines = MoveLine.sudo().search(
            self._report_domain(
                "account.move.line",
                "date",
                self.date_from,
                self.date_to,
                extra=extra,
            ),
            order="date, move_id, id",
        )

        debit = sum(lines.mapped("debit"))
        credit = sum(lines.mapped("credit"))
        balance = sum(lines.mapped("balance"))
        moves = lines.mapped("move_id")

        self._add_metric("JOURNAL_ITEM_COUNT", _("Posted Journal Items"), len(lines), "count", 10)
        self._add_metric("JOURNAL_MOVE_COUNT", _("Posted Journal Entries"), len(moves), "count", 20)
        self._add_metric("TOTAL_DEBIT", _("Total Debit"), debit, "amount", 30)
        self._add_metric("TOTAL_CREDIT", _("Total Credit"), credit, "amount", 40)
        self._add_metric("NET_BALANCE", _("Net Balance"), balance, "amount", 50)

        for line in lines:
            self._add_detail(
                line,
                _("Accounting Journal Item"),
                event_date=line.date,
                reference=line.move_id.name,
                state_label=line.parent_state,
                partner=line.partner_id,
                amount=line.balance,
                note="%s | D %.2f | C %.2f"
                % (
                    line.account_id.display_name,
                    line.debit or 0.0,
                    line.credit or 0.0,
                ),
            )

    # Indonesia Tax reporting reuses generated/locked owner-module tax reports instead of recomputing tax law here.
    def _generate_fin_tax(self):
        self.ensure_one()
        TaxReport = self.env["clinic.l10n.id.tax.report"]
        domain = [
            ("company_id", "=", self.company_id.id),
            ("date_from", "<=", self.date_to),
            ("date_to", ">=", self.date_from),
            ("state", "in", ("generated", "locked")),
        ]
        if self.branch_id and "branch_ids" in TaxReport._fields:
            domain.append(("branch_ids", "in", self.branch_id.id))

        reports = TaxReport.sudo().search(domain, order="date_to, id")

        output_tax = sum(reports.mapped("output_tax"))
        input_tax = sum(reports.mapped("input_tax"))
        net_ppn = sum(reports.mapped("net_ppn"))

        self._add_metric("TAX_REPORT_COUNT", _("Generated/Locked Tax Reports"), len(reports), "count", 10)
        self._add_metric("OUTPUT_TAX", _("Output Tax"), output_tax, "amount", 20)
        self._add_metric("INPUT_TAX", _("Input Tax"), input_tax, "amount", 30)
        self._add_metric("NET_PPN", _("Net PPN"), net_ppn, "amount", 40)

        for report in reports:
            self._add_detail(
                report,
                _("Indonesia Tax Report"),
                event_date=report.date_to,
                reference=report.name,
                state_label=report.state,
                amount=report.net_ppn,
                note=_("Output %.2f | Input %.2f")
                % (report.output_tax or 0.0, report.input_tax or 0.0),
            )

    # Insurance combines authorization and claim facts while preserving both upstream workflows unchanged.
    def _generate_fin_insurance(self):
        self.ensure_one()
        Authorization = self.env["clinic.insurance.authorization"]
        Claim = self.env["clinic.insurance.claim"]

        authorizations = Authorization.sudo().search(
            self._report_domain(
                "clinic.insurance.authorization",
                "request_date",
                self.date_from,
                self.date_to,
            ),
            order="request_date, id",
        )
        claim_domain = self._report_domain(
            "clinic.insurance.claim",
            "claim_date",
            self.date_from,
            self.date_to,
            # Claim.invoice_id is required in the current ClinicOne contract.
            # Its posted Billing move carries the authoritative Clinic Branch.
            branch_path=(
                "invoice_id.move_id.branch_id"
                if self.branch_id
                else None
            ),
        )
        claims = Claim.sudo().search(claim_domain, order="claim_date, id")

        requested = sum(authorizations.mapped("requested_amount"))
        approved = sum(authorizations.mapped("approved_amount"))
        payer = sum(authorizations.mapped("insurer_payable_amount"))
        patient_resp = sum(authorizations.mapped("patient_responsibility_amount"))
        approval_count = len(
            authorizations.filtered(lambda rec: rec.state in ("approved", "partial"))
        )
        rejected_count = len(
            authorizations.filtered(lambda rec: rec.state == "rejected")
        )

        claim_requested = sum(claims.mapped("requested_amount"))
        claim_approved = sum(claims.mapped("approved_amount"))

        self._add_metric("AUTH_COUNT", _("Authorization Requests"), len(authorizations), "count", 10)
        self._add_metric("AUTH_REQUESTED", _("Authorization Requested"), requested, "amount", 20)
        self._add_metric("AUTH_APPROVED", _("Authorization Approved"), approved, "amount", 30)
        self._add_metric("AUTH_PAYER", _("Insurer Payable"), payer, "amount", 40)
        self._add_metric("AUTH_PATIENT_RESP", _("Patient Responsibility"), patient_resp, "amount", 50)
        self._add_metric("AUTH_APPROVED_COUNT", _("Approved / Partial"), approval_count, "count", 60)
        self._add_metric("AUTH_REJECTED_COUNT", _("Rejected"), rejected_count, "count", 70)
        self._add_metric(
            "AUTH_APPROVAL_RATE",
            _("Authorization Approval Rate"),
            self._percentage(approval_count, len(authorizations)),
            "percentage",
            80,
        )
        self._add_metric("CLAIM_COUNT", _("Insurance Claims"), len(claims), "count", 90)
        self._add_metric("CLAIM_REQUESTED", _("Claim Requested"), claim_requested, "amount", 100)
        self._add_metric("CLAIM_APPROVED", _("Claim Approved"), claim_approved, "amount", 110)

        for authorization in authorizations:
            self._add_detail(
                authorization,
                _("Insurance Authorization"),
                event_date=authorization.request_date,
                reference=authorization.name,
                state_label=authorization.state,
                partner=authorization.partner_id,
                patient=authorization.patient_id,
                treatment=authorization.treatment_id,
                amount=authorization.approved_amount,
                note=_("Requested %.2f") % (authorization.requested_amount or 0.0),
            )

        for claim in claims:
            self._add_detail(
                claim,
                _("Insurance Claim"),
                event_date=claim.claim_date,
                reference=claim.name,
                state_label=claim.state,
                # clinic.insurance.claim.patient_id is res.partner, while the
                # canonical clinic.patient card lives on the required Billing invoice.
                partner=claim.patient_id,
                patient=(
                    claim.invoice_id.clinic_patient_id
                    if claim.invoice_id
                    else False
                ),
                amount=claim.approved_amount,
                note=_("Requested %.2f") % (claim.requested_amount or 0.0),
            )
