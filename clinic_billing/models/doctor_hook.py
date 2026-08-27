# -*- coding: utf-8 -*-
# File: clinic_billing/models/doctor_hook.py
# License: LGPL-3

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# res.partner — Doctor Billing Profile & KPIs
# =============================================================================
class ResPartnerDoctorBilling(models.Model):
    """
    Extend res.partner with doctor billing profile & KPIs.

    Prinsip:
    - Tanpa hard dependency ke clinic_doctor/hr: mapping ke employee/department bersifat optional.
    - Memberikan default komisi dokter (dipakai Commission Engine) dan preferensi akuntansi payout.
    - KPI revenue/komisi diambil dari clinic.billing.line/invoice yang sudah posted.
    """
    _inherit = "res.partner"

    # SUDAH CREATE SAAT Addon clinic_audit 
    # Flag & identity
    # is_doctor = fields.Boolean(
    #     string="Is a Doctor",
    #     help="Enable this if the partner represents a doctor/therapist."
    # )
    doctor_code = fields.Char(
        string="Doctor Code",
        help="Internal code used to identify the doctor."
    )

    # Soft HR mapping (optional)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Linked Employee",
        help="Link to HR Employee if available.",
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        help="Optional department mapping.",
    )

    # Commission defaults (used by Commission Engine when rule not overridden)
    commission_default_percent = fields.Float(
        string="Default Commission (%)",
        help="Default doctor commission percent when no specific rule applies."
    )
    commission_base_type = fields.Selection(
        [("subtotal_excl_tax", "Subtotal (Excl. Tax)"),
         ("total_incl_tax", "Total (Incl. Tax)")],
        string="Commission Base Type",
        default="subtotal_excl_tax",
        help="Base amount used to compute the commission when rules do not override."
    )
    commission_cap_per_invoice = fields.Monetary(
        string="Commission Cap / Invoice",
        currency_field="company_currency_id",
        help="Maximum commission amount per invoice (0 for unlimited)."
    )
    commission_payable_account_id = fields.Many2one(
        "account.account",
        string="Commission Payable Account",
        domain="[('account_type', '=', 'liability_payable')]",
        check_company=True,
        help="Default payable account to credit for commission settlements."
    )
    commission_expense_account_id = fields.Many2one(
        "account.account",
        string="Commission Expense Account",
        domain="[('account_type', '=', 'expense')]",
        check_company=True,
        help="Default expense account to debit for commission settlements."
    )
    commission_settlement_journal_id = fields.Many2one(
        "account.journal",
        string="Commission Settlement Journal",
        domain="[('company_id', '=', company_id)]",
        help="Default journal used to post commission settlement entries."
    )

    # Payout preferences
    vendor_partner_id = fields.Many2one(
        "res.partner",
        string="Vendor Payee",
        help="If commission should be paid to a vendor entity (e.g., doctor company), specify it here."
    )
    bank_account_id = fields.Many2one(
        "res.partner.bank",
        string="Bank Account",
        help="Preferred bank account for commission payout."
    )
    payout_method = fields.Selection(
        [("bill_payment", "Vendor Bill / Payment"),
         ("journal_entry", "Journal Entry")],
        string="Payout Method",
        default="journal_entry",
        help="How the commission settlement will be recorded."
    )

    # Targets & KPIs (company currency)
    target_monthly_revenue = fields.Monetary(
        string="Monthly Revenue Target",
        currency_field="company_currency_id"
    )
    target_monthly_sessions = fields.Integer(
        string="Monthly Sessions Target"
    )
    mtd_revenue = fields.Monetary(
        string="MTD Revenue",
        currency_field="company_currency_id",
        compute="_compute_doctor_kpis",
        help="Month-to-date revenue from posted clinic invoices (line provider = this doctor)."
    )
    mtd_sessions = fields.Integer(
        string="MTD Sessions",
        compute="_compute_doctor_kpis",
        help="Number of billed treatment/service lines this month."
    )
    mtd_commission_due = fields.Monetary(
        string="MTD Commission (Due)",
        currency_field="company_currency_id",
        compute="_compute_doctor_kpis",
        help="Estimated month-to-date commission due based on commission amounts stored on billing lines (if any) or default profile."
    )
    ytd_revenue = fields.Monetary(
        string="YTD Revenue",
        currency_field="company_currency_id",
        compute="_compute_doctor_kpis",
    )
    ytd_commission_due = fields.Monetary(
        string="YTD Commission (Due)",
        currency_field="company_currency_id",
        compute="_compute_doctor_kpis",
    )
    commission_settled_amount = fields.Monetary(
        string="Commission Settled (YTD)",
        currency_field="company_currency_id",
        compute="_compute_doctor_kpis",
        help="Total commission settled for this year (soft; requires commission engine posting)."
    )

    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda s: s.env.company
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        string="Company Currency",
        default=lambda s: s.env.company.currency_id,
        readonly=True
    )

    # Ratings (soft integration with clinic_feedback)
    avg_rating = fields.Float(
        string="Average Rating",
        compute="_compute_doctor_kpis",
        help="Average doctor rating from feedback module if available."
    )

    # ------------------------- Validators -------------------------
    @api.constrains("commission_default_percent")
    def _check_commission_percent(self):
        for rec in self:
            if rec.commission_default_percent and rec.commission_default_percent < 0:
                raise ValidationError(_("Default Commission (%) cannot be negative."))

    # ------------------------- KPI Computes -------------------------
    def _compute_doctor_kpis(self):
        """
        KPI dihitung dari clinic.billing.line yang:
        - provider_partner_id = dokter ini
        - invoice.move_id posted (atau invoice state posted)
        """
        BillingLine = self.env["clinic.billing.line"].sudo() if "clinic.billing.line" in self.env else False
        Feedback = self.env["clinic.feedback"].sudo() if "clinic.feedback" in self.env else False
        today = fields.Date.context_today(self)
        first_day_month = today.replace(day=1) if today else False
        first_day_year = today.replace(month=1, day=1) if today else False

        for rec in self:
            mtd_rev = ytd_rev = 0.0
            mtd_comm = ytd_comm = 0.0
            mtd_sessions = 0
            settled = 0.0
            rating = 0.0

            if BillingLine and rec.id:
                # Posted only: rely on invoice.move_id.state == posted OR invoice state posted (depending on your base model)
                domain_base = [
                    ("provider_partner_id", "=", rec.id),
                    ("invoice_id.company_id", "=", rec.company_id.id if rec.company_id else self.env.company.id),
                    ("invoice_id.state", "in", ["confirmed", "posted", "done", "paid"]),
                    ("invoice_id.move_id.state", "=", "posted"),
                ]
                # MTD
                if first_day_month:
                    mtd_lines = BillingLine.search(domain_base + [
                        ("invoice_id.invoice_date", ">=", first_day_month),
                        ("invoice_id.invoice_date", "<=", today),
                    ])
                    mtd_rev = sum(float(l.subtotal_excl_tax or 0.0) for l in mtd_lines)
                    # Komisi: jika line memiliki komisi tersimpan (mis. kolom commission_amount), gunakan itu;
                    # jika tidak, estimasi pakai default persen dokter
                    if "commission_amount" in BillingLine._fields:
                        mtd_comm = sum(float(l.commission_amount or 0.0) for l in mtd_lines)
                    else:
                        pct = float(rec.commission_default_percent or 0.0) / 100.0
                        base = rec.commission_base_type or "subtotal_excl_tax"
                        calc_base = sum(float(getattr(l, "subtotal_excl_tax" if base == "subtotal_excl_tax" else "total_incl_tax") or 0.0) for l in mtd_lines)
                        mtd_comm = pct * calc_base
                    mtd_sessions = len(mtd_lines)

                # YTD
                if first_day_year:
                    ytd_lines = BillingLine.search(domain_base + [
                        ("invoice_id.invoice_date", ">=", first_day_year),
                        ("invoice_id.invoice_date", "<=", today),
                    ])
                    ytd_rev = sum(float(l.subtotal_excl_tax or 0.0) for l in ytd_lines)
                    if "commission_amount" in BillingLine._fields:
                        ytd_comm = sum(float(l.commission_amount or 0.0) for l in ytd_lines)
                    else:
                        pct = float(rec.commission_default_percent or 0.0) / 100.0
                        base = rec.commission_base_type or "subtotal_excl_tax"
                        calc_base = sum(float(getattr(l, "subtotal_excl_tax" if base == "subtotal_excl_tax" else "total_incl_tax") or 0.0) for l in ytd_lines)
                        ytd_comm = pct * calc_base

                # Settled commission (soft; jika modul komisi menulis settlement ke relasi)
                # Heuristic: cari journal entries/payments yang ditandai untuk dokter (opsional)
                # Jika billing_commission membuat model 'clinic.billing.commission.settlement.line' gunakan itu:
                if "clinic.billing.commission.settlement.line" in self.env:
                    SettleLine = self.env["clinic.billing.commission.settlement.line"].sudo()
                    lines = SettleLine.search([
                        ("doctor_partner_id", "=", rec.id),
                        ("state", "in", ("posted", "paid", "done")),
                        ("date", ">=", first_day_year),
                        ("date", "<=", today),
                    ])
                    settled = sum(float(x.amount or 0.0) for x in lines)

            # Feedback average (soft)
            if Feedback and rec.is_doctor:
                try:
                    # Misal ada model clinic.feedback terkait doctor_partner_id
                    fb = Feedback.search([("doctor_partner_id", "=", rec.id)], limit=1000)
                    cnt = len(fb)
                    rating = (sum(float(x.rating or 0.0) for x in fb) / cnt) if cnt else 0.0
                except Exception:
                    rating = 0.0

            rec.mtd_revenue = mtd_rev
            rec.mtd_commission_due = mtd_comm
            rec.mtd_sessions = mtd_sessions
            rec.ytd_revenue = ytd_rev
            rec.ytd_commission_due = ytd_comm
            rec.commission_settled_amount = settled
            rec.avg_rating = rating

    # ------------------------- Utilities -------------------------
    def get_doctor_commission_profile(self):
        """
        Return a dict used by Commission Engine when evaluating lines for this doctor.
        """
        self.ensure_one()
        return {
            "doctor_id": self.id,
            "default_percent": self.commission_default_percent or 0.0,
            "base_type": self.commission_base_type or "subtotal_excl_tax",
            "cap_per_invoice": self.commission_cap_per_invoice or 0.0,
            "payable_account_id": self.commission_payable_account_id.id or False,
            "expense_account_id": self.commission_expense_account_id.id or False,
            "settlement_journal_id": self.commission_settlement_journal_id.id or False,
            "payout_method": self.payout_method or "journal_entry",
            "vendor_partner_id": self.vendor_partner_id.id or False,
            "bank_account_id": self.bank_account_id.id or False,
        }

    # ------------------------- Actions -------------------------
    def action_open_doctor_billing_lines(self):
        self.ensure_one()
        if "clinic.billing.line" not in self.env:
            raise UserError(_("Clinic Billing Line model is not available."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Doctor Billing Lines"),
            "res_model": "clinic.billing.line",
            "view_mode": "list,form",
            "domain": [("provider_partner_id", "=", self.id)],
            "context": {},
        }

    def action_open_doctor_invoices(self):
        self.ensure_one()
        if "clinic.billing.invoice" not in self.env:
            raise UserError(_("Clinic Billing Invoice model is not available."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Doctor Invoices"),
            "res_model": "clinic.billing.invoice",
            "view_mode": "list,form",
            "domain": ["|", ("doctor_partner_id", "=", self.id), ("line_ids.provider_partner_id", "=", self.id)],
            "context": {},
        }

    def action_open_doctor_schedule(self):
        """
        Open Appointment/Calendar for the doctor (soft).
        """
        self.ensure_one()
        if "booking.booking" in self.env:
            return {
                "type": "ir.actions.act_window",
                "name": _("Appointments"),
                "res_model": "booking.booking",
                "view_mode": "list,form",
                "domain": [("doctor_id", "=", self.id)],
                "context": {"default_doctor_id": self.id},
            }
        if "calendar.event" in self.env:
            return {
                "type": "ir.actions.act_window",
                "name": _("Calendar"),
                "res_model": "calendar.event",
                "view_mode": "calendar,list,form",
                "domain": [("partner_ids", "in", self.ids)],
                "context": {},
            }
        raise UserError(_("No schedule model available."))

    def action_settle_commission(self):
        """
        Trigger commission settlement for this doctor (soft call to Commission Engine).
        """
        self.ensure_one()
        EngineModel = "clinic.billing.commission.engine"
        if EngineModel not in self.env:
            raise UserError(_("Commission Engine is not available."))
        Engine = self.env[EngineModel]
        today = fields.Date.context_today(self)
        first_day_month = today.replace(day=1)
        return Engine.generate_statement_for_doctor(
            doctor=self,
            date_from=first_day_month,
            date_to=today,
            auto_post=True
        )


# =============================================================================
# clinic.billing.line — Provider fields & behaviors
# =============================================================================
class ClinicBillingLine_DoctorBridge(models.Model):
    _inherit = "clinic.billing.line"

    provider_partner_id = fields.Many2one(
        "res.partner",
        string="Provider (Doctor)",
        help="Doctor/Therapist who provided this service."
    )
    provider_employee_id = fields.Many2one(
        "hr.employee",
        string="Provider Employee",
        help="Optional HR link; used if available."
    )
    provider_department_id = fields.Many2one(
        "hr.department",
        string="Provider Department",
        help="Optional department for reporting."
    )
    # Optional: store computed commission for fast settlement (if not already defined elsewhere)
    commission_amount = fields.Monetary(
        string="Commission Amount",
        currency_field="currency_id",
        help="Computed commission amount for this line (if enabled by the commission engine)."
    )
    commission_percent = fields.Float(
        string="Commission (%)",
        help="Percent applied to compute commission for this line (for audit)."
    )

    @api.onchange("provider_partner_id")
    def _onchange_provider_partner_id(self):
        """
        Default provider's HR mapping and offer a hint for commission percent (display only).
        """
        for rec in self:
            if rec.provider_partner_id:
                # Soft HR links
                try:
                    if rec.provider_partner_id.employee_id:
                        rec.provider_employee_id = rec.provider_partner_id.employee_id.id
                    if rec.provider_partner_id.department_id:
                        rec.provider_department_id = rec.provider_partner_id.department_id.id
                except Exception:
                    pass

    def _get_doctor_commission_profile(self):
        """
        Helper used by Commission Engine to fetch doctor defaults.
        """
        self.ensure_one()
        doc = self.provider_partner_id
        if not doc:
            return {}
        return doc.get_doctor_commission_profile() if hasattr(doc, "get_doctor_commission_profile") else {}

    # Convenience to force recompute commission on a line (soft)
    def action_recompute_commission(self):
        EngineModel = "clinic.billing.commission.engine"
        if EngineModel not in self.env:
            raise UserError(_("Commission Engine is not available."))
        Engine = self.env[EngineModel]
        for line in self:
            Engine.compute_commission_for_lines(line.invoice_id, lines=line)
        return True


# =============================================================================
# clinic.billing.invoice — Doctor defaults & aggregation
# =============================================================================
class ClinicBillingInvoice_DoctorBridge(models.Model):
    _inherit = "clinic.billing.invoice"

    doctor_partner_id = fields.Many2one(
        "res.partner",
        string="Responsible Doctor",
        help="Primary doctor in charge of this invoice."
    )
    doctor_ids = fields.Many2many(
        "res.partner",
        "clinic_billing_invoice_doctor_rel",
        "invoice_id", "partner_id",
        string="Contributing Doctors",
        compute="_compute_doctor_ids",
        store=False,
        help="All doctors involved on this invoice (aggregated from lines)."
    )
    doctor_revenue_total = fields.Monetary(
        string="Doctor Revenue (Sum of Lines)",
        currency_field="currency_id",
        compute="_compute_doctor_revenue",
        help="Sum of line subtotals for lines that have a provider."
    )
    doctor_commission_total = fields.Monetary(
        string="Doctor Commission (Sum of Lines)",
        currency_field="currency_id",
        compute="_compute_doctor_revenue",
        help="Sum of commission amounts stored on lines (if any)."
    )

    @api.depends("line_ids.provider_partner_id", "line_ids.subtotal_excl_tax", "line_ids.commission_amount")
    def _compute_doctor_revenue(self):
        for rec in self:
            prov_lines = rec.line_ids.filtered(lambda l: l.provider_partner_id)
            rec.doctor_revenue_total = sum(float(l.subtotal_excl_tax or 0.0) for l in prov_lines)
            if "commission_amount" in self.env["clinic.billing.line"]._fields:
                rec.doctor_commission_total = sum(float(l.commission_amount or 0.0) for l in prov_lines)
            else:
                rec.doctor_commission_total = 0.0

    def _compute_doctor_ids(self):
        for rec in self:
            rec.doctor_ids = [(6, 0, list(set(rec.line_ids.mapped("provider_partner_id").ids)))]

    # -------- Defaults from Booking/Treatment (soft) --------
    @api.onchange("line_ids")
    def _onchange_lines_default_doctor(self):
        """
        Jika doctor_partner_id kosong, isi dari provider line pertama yang ada.
        """
        for rec in self:
            if not rec.doctor_partner_id:
                doc = next((l.provider_partner_id for l in rec.line_ids if l.provider_partner_id), False)
                if doc:
                    rec.doctor_partner_id = doc.id

    # -------- Hooks with Commission Engine (soft) --------
    def _on_after_confirm(self):
        """
        Setelah confirm, minta Commission Engine menghitung komisi (jika ada).
        """
        super()._on_after_confirm()
        EngineModel = "clinic.billing.commission.engine"
        if EngineModel in self.env:
            Engine = self.env[EngineModel]
            for rec in self:
                try:
                    Engine.compute_commission_for_lines(rec)
                except Exception as e:
                    rec.message_post(body=_("Commission compute failed: %s") % e)

    def _on_after_move_posted(self, move):
        """
        Saat invoice akuntansi posted, izinkan Commission Engine memfinalisasi accrual/settlement-ready.
        """
        super()._on_after_move_posted(move)
        EngineModel = "clinic.billing.commission.engine"
        if EngineModel in self.env:
            Engine = self.env[EngineModel]
            for rec in self:
                try:
                    Engine.on_invoice_posted(rec)
                except Exception as e:
                    rec.message_post(body=_("Commission finalize on post failed: %s") % e)

    # -------- Convenience Actions --------
    def action_open_doctor_breakdown(self):
        """
        Pivot/Graph untuk melihat breakdown revenue per dokter pada invoice ini (soft).
        """
        self.ensure_one()
        if "clinic.billing.line" not in self.env:
            raise UserError(_("Clinic Billing Line model is not available."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Doctor Breakdown"),
            "res_model": "clinic.billing.line",
            "view_mode": "pivot,graph,list",
            "domain": [("invoice_id", "=", self.id), ("provider_partner_id", "!=", False)],
            "context": {"group_by": ["provider_partner_id"]},
        }

