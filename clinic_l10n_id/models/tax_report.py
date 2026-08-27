from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


SOURCE_SELECTION = [
    ("finance", "Clinic Finance"),
    ("billing", "Clinic Billing"),
    ("ar", "Accounts Receivable"),
    ("ap", "Accounts Payable"),
    ("wallet", "Patient Wallet"),
    ("adjustment", "Accounting Adjustment"),
    ("mixed", "Mixed Clinic Sources"),
    ("other", "Other / Native Odoo"),
]


class ClinicL10nIdTaxReport(models.Model):
    """Persistent PPN input/output report snapshot from posted native tax lines."""

    _name = "clinic.l10n.id.tax.report"
    _description = "Clinic Indonesia PPN Tax Report"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_to desc, id desc"
    _check_company_auto = True

    _date_range_check = models.Constraint(
        "CHECK(date_from <= date_to)",
        "PPN report start date must be before or equal to end date.",
    )
    _company_period_idx = models.Index("(company_id, date_to, state)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    profile_id = fields.Many2one(
        "clinic.l10n.id.tax.profile",
        required=True,
        check_company=True,
        ondelete="restrict",
        domain="[('company_id', '=', company_id), ('state', 'in', ('validated', 'active'))]",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    date_from = fields.Date(required=True, tracking=True)
    date_to = fields.Date(required=True, tracking=True)

    source_scope = fields.Selection(
        [
            ("all", "All Accounting Entries"),
            ("clinic_only", "ClinicOne-Sourced Entries"),
            ("finance", "Clinic Finance"),
            ("billing", "Clinic Billing"),
            ("ar", "Accounts Receivable"),
            ("ap", "Accounts Payable"),
            ("wallet", "Patient Wallet"),
            ("adjustment", "Accounting Adjustment"),
            ("mixed", "Mixed Clinic Sources"),
            ("other", "Other / Native Odoo"),
        ],
        default="clinic_only",
        required=True,
        tracking=True,
    )
    branch_ids = fields.Many2many(
        "clinic.branch",
        "clinic_l10n_id_tax_report_branch_rel",
        "report_id",
        "branch_id",
        string="Branches",
        domain="[('company_id', '=', company_id)]",
    )
    journal_ids = fields.Many2many(
        "account.journal",
        "clinic_l10n_id_tax_report_journal_rel",
        "report_id",
        "journal_id",
        string="Journals",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("generated", "Generated"),
            ("locked", "Locked"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    line_ids = fields.One2many(
        "clinic.l10n.id.tax.report.line",
        "report_id",
        string="PPN Report Lines",
        copy=False,
    )

    output_base = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    output_tax = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    input_base = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    input_tax = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    net_ppn = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        help="PPN Output minus PPN Input for the selected reporting scope.",
    )
    line_count = fields.Integer(compute="_compute_totals", store=True)

    generated_at = fields.Datetime(readonly=True)
    generated_by_id = fields.Many2one("res.users", readonly=True)
    auto_generated = fields.Boolean(default=False, readonly=True, copy=False)
    note = fields.Text()

    @api.depends(
        "line_ids.direction",
        "line_ids.base_amount",
        "line_ids.tax_amount",
    )
    def _compute_totals(self):
        for record in self:
            output_lines = record.line_ids.filtered(lambda line: line.direction == "output")
            input_lines = record.line_ids.filtered(lambda line: line.direction == "input")
            record.output_base = sum(output_lines.mapped("base_amount"))
            record.output_tax = sum(output_lines.mapped("tax_amount"))
            record.input_base = sum(input_lines.mapped("base_amount"))
            record.input_tax = sum(input_lines.mapped("tax_amount"))
            record.net_ppn = record.output_tax - record.input_tax
            record.line_count = len(record.line_ids)

    @api.onchange("profile_id")
    def _onchange_profile(self):
        for record in self:
            if not record.profile_id:
                continue
            profile = record.profile_id
            record.company_id = profile.company_id
            record.source_scope = profile.default_source_scope
            record.journal_ids = profile.report_journal_ids

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            profile = self.env["clinic.l10n.id.tax.profile"].browse(vals.get("profile_id"))
            if profile.exists():
                vals.setdefault("company_id", profile.company_id.id)
                vals.setdefault("source_scope", profile.default_source_scope)
                if "journal_ids" not in vals and profile.report_journal_ids:
                    vals["journal_ids"] = [(6, 0, profile.report_journal_ids.ids)]

            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.l10n.id.tax.report")
                    or "/"
                )
        return super().create(vals_list)

    def write(self, vals):
        filter_fields = {
            "profile_id",
            "company_id",
            "date_from",
            "date_to",
            "source_scope",
            "branch_ids",
            "journal_ids",
        }
        system_fields = {"state", "generated_at", "generated_by_id", "auto_generated"}

        if system_fields.intersection(vals) and not self.env.context.get("l10n_transition"):
            raise AccessError(_("PPN report workflow and generation audit fields are controlled by report actions."))

        if filter_fields.intersection(vals):
            for record in self:
                if record.state != "draft":
                    raise UserError(_("PPN report filters can only be changed while Draft."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda report: report.state == "locked"):
            raise UserError(_("Locked PPN report snapshots cannot be deleted."))
        return super().unlink()

    @api.constrains("profile_id", "company_id", "branch_ids", "journal_ids")
    def _check_scope(self):
        for record in self:
            if record.profile_id.company_id != record.company_id:
                raise ValidationError(_("Tax Profile and PPN Report company must match."))
            if record.branch_ids.filtered(lambda branch: branch.company_id != record.company_id):
                raise ValidationError(_("Every selected branch must belong to the PPN Report company."))
            if record.journal_ids.filtered(lambda journal: journal.company_id != record.company_id):
                raise ValidationError(_("Every selected journal must belong to the PPN Report company."))

    # Reporting reads posted native tax journal items; ClinicOne never recalculates legal tax from hard-coded rates.
    def _tax_line_domain(self):
        self.ensure_one()
        tax_ids = (
            self.profile_id.ppn_sale_tax_ids
            | self.profile_id.ppn_purchase_tax_ids
        ).ids
        if not tax_ids:
            raise UserError(_("The Tax Profile has no PPN taxes configured."))

        domain = [
            ("company_id", "=", self.company_id.id),
            ("move_id.state", "=", "posted"),
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
            ("tax_line_id", "in", tax_ids),
        ]

        journal_ids = self.journal_ids.ids or self.profile_id.report_journal_ids.ids
        if journal_ids:
            domain.append(("move_id.journal_id", "in", journal_ids))

        if self.branch_ids and "branch_id" in self.env["account.move.line"]._fields:
            domain.append(("branch_id", "in", self.branch_ids.ids))

        if self.source_scope == "clinic_only":
            domain.append(("clinic_accounting_source", "!=", "other"))
        elif self.source_scope != "all":
            domain.append(("clinic_accounting_source", "=", self.source_scope))

        return domain

    def action_generate(self):
        self._l10n_report_role()
        Line = self.env["clinic.l10n.id.tax.report.line"].sudo()

        for record in self:
            if record.state == "locked":
                raise UserError(_("Locked PPN Reports cannot be regenerated."))

            record.line_ids.sudo().unlink()
            values = record._prepare_report_lines()
            if values:
                Line.create(values)

            record.with_context(l10n_transition=True).write({
                "state": "generated",
                "generated_at": fields.Datetime.now(),
                "generated_by_id": self.env.user.id,
            })
        return True

    def _l10n_report_role(self):
        if not (
            self.env.su
            or self.env.user.has_group("clinic_l10n_id.group_clinic_l10n_id_user")
        ):
            raise AccessError(_("You do not have permission to generate PPN reports."))

    # Refund signs are normalized at reporting time while the underlying accounting entry remains untouched.
    def _prepare_report_lines(self):
        self.ensure_one()
        tax_lines = self.env["account.move.line"].sudo().search(
            self._tax_line_domain(),
            order="date, move_id, tax_line_id, id",
        )

        values = []
        for line in tax_lines:
            move = line.move_id

            if move.move_type in ("out_invoice", "out_refund", "out_receipt"):
                direction = "output"
            elif move.move_type in ("in_invoice", "in_refund", "in_receipt"):
                direction = "input"
            else:
                # Miscellaneous tax adjustments are classified by the tax's
                # intended usage; they remain visible rather than being discarded.
                direction = (
                    "output"
                    if line.tax_line_id.type_tax_use == "sale"
                    else "input"
                )

            is_refund = move.move_type in ("out_refund", "in_refund")

            # account.move.line.balance and tax_base_amount are company-currency
            # accounting values. Normal invoices are normalized to positive PPN,
            # refunds reduce the period totals, while miscellaneous tax
            # adjustments preserve their debit/credit correction sign.
            if move.move_type in (
                "out_invoice", "out_refund", "out_receipt",
                "in_invoice", "in_refund", "in_receipt",
            ):
                refund_sign = -1.0 if is_refund else 1.0
                base_amount = abs(line.tax_base_amount or 0.0) * refund_sign
                tax_amount = abs(line.balance or 0.0) * refund_sign
            else:
                if line.tax_line_id.type_tax_use == "sale":
                    direction = "output"
                    tax_amount = -(line.balance or 0.0)
                elif line.tax_line_id.type_tax_use == "purchase":
                    direction = "input"
                    tax_amount = line.balance or 0.0
                else:
                    direction = "output" if (line.balance or 0.0) < 0 else "input"
                    tax_amount = abs(line.balance or 0.0)

                adjustment_sign = -1.0 if tax_amount < 0 else 1.0
                base_amount = abs(line.tax_base_amount or 0.0) * adjustment_sign

            partner = move.commercial_partner_id
            values.append({
                "report_id": self.id,
                "company_id": self.company_id.id,
                "branch_id": line.branch_id.id if "branch_id" in line._fields else False,
                "date": line.date,
                "direction": direction,
                "is_refund": is_refund,
                "move_id": move.id,
                "move_line_id": line.id,
                "journal_id": move.journal_id.id,
                "partner_id": partner.id or False,
                "partner_npwp": partner.vat or False,
                "partner_nik": partner.l10n_id_nik or False,
                "clinic_source": line.clinic_accounting_source or "other",
                "tax_id": line.tax_line_id.id,
                "tax_group_id": line.tax_line_id.tax_group_id.id,
                "base_amount": base_amount,
                "tax_amount": tax_amount,
                "coretax_document_id": move.l10n_id_coretax_document.id or False,
                "transaction_code": move.l10n_id_kode_transaksi or False,
                "invoice_number": move.name,
            })
        return values

    def action_lock(self):
        if not self.env.user.has_group("clinic_l10n_id.group_clinic_l10n_id_manager"):
            raise AccessError(_("Only an Indonesia Localization Manager can lock PPN reports."))
        for record in self:
            if record.state != "generated":
                raise UserError(_("Generate the PPN Report before locking it."))
            record.with_context(l10n_transition=True).write({"state": "locked"})
        return True

    def action_reset_to_draft(self):
        if not self.env.user.has_group("clinic_l10n_id.group_clinic_l10n_id_accountant"):
            raise AccessError(_("Only Indonesia tax/accounting staff can reset generated reports."))
        for record in self:
            if record.state == "locked":
                raise UserError(_("Locked PPN Reports are historical snapshots."))
            record.line_ids.sudo().unlink()
            record.with_context(l10n_transition=True).write({
                "state": "draft",
                "generated_at": False,
                "generated_by_id": False,
            })
        return True

    def action_view_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("PPN Report Lines"),
            "res_model": "clinic.l10n.id.tax.report.line",
            "view_mode": "list,form",
            "domain": [("report_id", "=", self.id)],
        }

    def action_view_source_tax_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Source Tax Journal Items"),
            "res_model": "account.move.line",
            "view_mode": "list",
            "domain": self._tax_line_domain(),
        }

    def action_print_report(self):
        self.ensure_one()
        if self.state == "draft":
            raise UserError(_("Generate the PPN Report before printing."))
        return self.env.ref("clinic_l10n_id.action_report_ppn_tax").report_action(self)

    @api.model
    # Scheduled snapshots are idempotent per company/profile/period so retries do not duplicate monthly evidence.
    def _cron_monthly_ppn_report(self):
        today = fields.Date.context_today(self)
        if today.day != 1:
            return

        previous_end = today.replace(day=1) - timedelta(days=1)
        previous_start = previous_end.replace(day=1)

        companies = self.env["res.company"].sudo().search([
            ("clinic_l10n_id_auto_monthly_tax_report", "=", True),
            ("clinic_l10n_id_profile_id", "!=", False),
        ])

        for company in companies:
            profile = company.clinic_l10n_id_profile_id
            if profile.state != "active":
                continue

            existing = self.sudo().search([
                ("company_id", "=", company.id),
                ("profile_id", "=", profile.id),
                ("date_from", "=", previous_start),
                ("date_to", "=", previous_end),
                ("auto_generated", "=", True),
            ], limit=1)
            if existing:
                continue

            report = self.sudo().create({
                "company_id": company.id,
                "profile_id": profile.id,
                "date_from": previous_start,
                "date_to": previous_end,
                "source_scope": profile.default_source_scope,
                "journal_ids": [(6, 0, profile.report_journal_ids.ids)],
                "auto_generated": True,
            })
            report.sudo().action_generate()


class ClinicL10nIdTaxReportLine(models.Model):
    """Generated PPN report line with tax, invoice, ClinicOne source and Coretax traceability."""

    _name = "clinic.l10n.id.tax.report.line"
    _description = "Clinic Indonesia PPN Tax Report Line"
    _order = "date, move_id, tax_id, id"
    _check_company_auto = True

    _base_reasonable = models.Constraint(
        "CHECK(base_amount IS NOT NULL)",
        "PPN report base amount must be present.",
    )

    report_id = fields.Many2one(
        "clinic.l10n.id.tax.report",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="report_id.currency_id",
        store=True,
        readonly=True,
    )
    branch_id = fields.Many2one("clinic.branch", ondelete="set null", index=True)
    date = fields.Date(required=True, index=True)
    direction = fields.Selection(
        [("output", "PPN Output"), ("input", "PPN Input")],
        required=True,
        index=True,
    )
    is_refund = fields.Boolean(index=True)

    move_id = fields.Many2one("account.move", required=True, ondelete="restrict", index=True)
    move_line_id = fields.Many2one("account.move.line", required=True, ondelete="restrict", index=True)
    journal_id = fields.Many2one("account.journal", required=True, ondelete="restrict")
    partner_id = fields.Many2one("res.partner", ondelete="set null")
    partner_npwp = fields.Char(string="Partner NPWP")
    partner_nik = fields.Char(string="Partner NIK")

    clinic_source = fields.Selection(SOURCE_SELECTION, index=True)
    tax_id = fields.Many2one("account.tax", required=True, ondelete="restrict", index=True)
    tax_group_id = fields.Many2one("account.tax.group", ondelete="restrict")
    base_amount = fields.Monetary(currency_field="currency_id")
    tax_amount = fields.Monetary(currency_field="currency_id")

    coretax_document_id = fields.Many2one(
        "l10n_id_efaktur_coretax.document",
        ondelete="set null",
        string="Coretax Document",
    )
    transaction_code = fields.Char(string="Coretax Transaction Code")
    invoice_number = fields.Char(index=True)

    def action_open_move(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Journal Entry / Invoice"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
        }

    def action_open_coretax_document(self):
        self.ensure_one()
        if not self.coretax_document_id:
            raise UserError(_("This tax line is not linked to a Coretax document."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Coretax E-Faktur Document"),
            "res_model": "l10n_id_efaktur_coretax.document",
            "view_mode": "form",
            "res_id": self.coretax_document_id.id,
        }

    def action_open_report(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("PPN Tax Report"),
            "res_model": "clinic.l10n.id.tax.report",
            "view_mode": "form",
            "res_id": self.report_id.id,
        }

