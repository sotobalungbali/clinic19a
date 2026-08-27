import ast
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicL10nIdComplianceRun(models.Model):
    """Generated Indonesia localization readiness/compliance evidence."""

    _name = "clinic.l10n.id.compliance.run"
    _description = "Clinic Indonesia Compliance Run"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_to desc, id desc"
    _check_company_auto = True

    _date_range_check = models.Constraint(
        "CHECK(date_from <= date_to)",
        "Compliance start date must be before or equal to end date.",
    )
    _company_state_idx = models.Index("(company_id, state, date_to)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    profile_id = fields.Many2one(
        "clinic.l10n.id.tax.profile",
        required=True,
        check_company=True,
        ondelete="restrict",
        domain="[('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    date_from = fields.Date(
        default=lambda self: fields.Date.context_today(self) - timedelta(days=30),
        required=True,
    )
    date_to = fields.Date(default=fields.Date.context_today, required=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("generated", "Generated"),
            ("reviewed", "Reviewed"),
            ("locked", "Locked"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    line_ids = fields.One2many(
        "clinic.l10n.id.compliance.line",
        "run_id",
        string="Compliance Checks",
        copy=False,
    )
    blocking_count = fields.Integer(compute="_compute_counts", store=True)
    warning_count = fields.Integer(compute="_compute_counts", store=True)
    clear_count = fields.Integer(compute="_compute_counts", store=True)
    readiness_score = fields.Integer(compute="_compute_counts", store=True)

    generated_at = fields.Datetime(readonly=True)
    generated_by_id = fields.Many2one("res.users", readonly=True)
    reviewed_at = fields.Datetime(readonly=True)
    reviewed_by_id = fields.Many2one("res.users", readonly=True)
    note = fields.Text()

    @api.depends("line_ids.status", "line_ids.severity")
    def _compute_counts(self):
        for record in self:
            open_blocking = record.line_ids.filtered(
                lambda line: line.status == "open" and line.severity == "blocking"
            )
            open_warning = record.line_ids.filtered(
                lambda line: line.status == "open" and line.severity == "warning"
            )
            clear = record.line_ids.filtered(lambda line: line.status == "clear")

            record.blocking_count = len(open_blocking)
            record.warning_count = len(open_warning)
            record.clear_count = len(clear)

            total = len(record.line_ids)
            penalty = (len(open_blocking) * 20) + (len(open_warning) * 5)
            record.readiness_score = max(0, min(100, 100 - penalty)) if total else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            profile = self.env["clinic.l10n.id.tax.profile"].browse(vals.get("profile_id"))
            if profile.exists():
                vals.setdefault("company_id", profile.company_id.id)
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.l10n.id.compliance.run")
                    or "/"
                )
        return super().create(vals_list)

    @api.constrains("profile_id", "company_id")
    def _check_profile_company(self):
        for record in self:
            if record.profile_id.company_id != record.company_id:
                raise ValidationError(_("Compliance Run and Tax Profile company must match."))

    def write(self, vals):
        filter_fields = {"profile_id", "company_id", "date_from", "date_to"}
        system_fields = {
            "state",
            "generated_at",
            "generated_by_id",
            "reviewed_at",
            "reviewed_by_id",
        }
        if system_fields.intersection(vals) and not self.env.context.get("l10n_transition"):
            raise AccessError(_("Compliance workflow and audit fields are controlled by Compliance actions."))
        if filter_fields.intersection(vals):
            for record in self:
                if record.state != "draft":
                    raise UserError(_("Compliance scope can only be edited while Draft."))
        return super().write(vals)

    def action_generate(self):
        self._require_user()
        Line = self.env["clinic.l10n.id.compliance.line"].sudo()

        for record in self:
            if record.state == "locked":
                raise UserError(_("Locked Compliance evidence cannot be regenerated."))
            record.line_ids.sudo().unlink()
            values = record._prepare_checks()
            if values:
                Line.create(values)
            record.with_context(l10n_transition=True).write({
                "state": "generated",
                "generated_at": fields.Datetime.now(),
                "generated_by_id": self.env.user.id,
            })
        return True

    def _require_user(self):
        if not (
            self.env.su
            or self.env.user.has_group("clinic_l10n_id.group_clinic_l10n_id_user")
        ):
            raise AccessError(_("You do not have permission to run Indonesia compliance checks."))

    # Compliance checks produce evidence and drill-down domains; they do not alter tax, invoice, partner, product, or Coretax records.
    def _prepare_checks(self):
        self.ensure_one()
        profile = self.profile_id
        values = []

        def direct(code, title, severity, is_clear, note):
            values.append({
                "run_id": self.id,
                "code": code,
                "title": title,
                "severity": severity,
                "status": "clear" if is_clear else "open",
                "record_count": 0,
                "note": note,
            })

        def query(code, title, severity, model_name, domain, note):
            count = self.env[model_name].sudo().search_count(domain)
            values.append({
                "run_id": self.id,
                "code": code,
                "title": title,
                "severity": severity,
                "status": "clear" if not count else "open",
                "record_count": count,
                "model_name": model_name,
                "domain_text": repr(domain),
                "note": note,
            })

        # Company localization readiness.
        direct(
            "company_country",
            _("Company Country = Indonesia"),
            "blocking",
            self.company_id.country_id.code == "ID",
            _("Set the company country to Indonesia."),
        )
        direct(
            "fiscal_country",
            _("Accounting Fiscal Country = Indonesia"),
            "blocking",
            self.company_id.account_fiscal_country_id.code == "ID",
            _("The accounting fiscal country must be Indonesia for Indonesian tax reporting."),
        )
        direct(
            "company_npwp",
            _("Company NPWP / Tax ID"),
            "blocking" if profile.require_company_npwp else "warning",
            bool(self.company_id.partner_id.vat) or not profile.require_company_npwp,
            _("Populate the company's NPWP / Tax ID on the company contact."),
        )
        direct(
            "ppn_sale_scope",
            _("PPN Sales Tax Scope"),
            "blocking",
            bool(profile.ppn_sale_tax_ids),
            _("Configure native Indonesian sales taxes on the ClinicOne Tax Profile."),
        )
        direct(
            "ppn_purchase_scope",
            _("PPN Purchase Tax Scope"),
            "warning",
            bool(profile.ppn_purchase_tax_ids),
            _("Configure native Indonesian purchase taxes for input PPN reporting."),
        )

        sale_tax_ids = profile.ppn_sale_tax_ids.ids
        period_domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "posted"),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
            ("move_type", "in", ("out_invoice", "out_refund")),
        ]

        if sale_tax_ids:
            # Native Coretax requires transaction metadata; ClinicOne only surfaces missing readiness data.
            # Native Coretax requires a transaction code on generated e-Faktur.
            query(
                "coretax_transaction_code",
                _("Taxable Customer Invoices Missing Coretax Transaction Code"),
                "blocking",
                "account.move",
                period_domain + [
                    ("invoice_line_ids.tax_ids", "in", sale_tax_ids),
                    ("l10n_id_kode_transaksi", "=", False),
                ],
                _("Set the Indonesian transaction code before Coretax XML generation."),
            )

            identity_domain = period_domain + [
                ("invoice_line_ids.tax_ids", "in", sale_tax_ids),
                ("commercial_partner_id.vat", "=", False),
                ("commercial_partner_id.l10n_id_nik", "=", False),
                ("commercial_partner_id.l10n_id_buyer_document_number", "=", False),
            ]
            query(
                "buyer_tax_identity",
                _("Taxable Customer Invoices with Missing Buyer Tax Identity"),
                "blocking" if profile.require_partner_tax_identity else "warning",
                "account.move",
                identity_domain,
                _("Provide NPWP, NIK, or the native Indonesian buyer-document information."),
            )

            product_domain = [
                ("company_id", "=", self.company_id.id),
                ("move_id.state", "=", "posted"),
                ("move_id.invoice_date", ">=", self.date_from),
                ("move_id.invoice_date", "<=", self.date_to),
                ("move_id.move_type", "in", ("out_invoice", "out_refund")),
                ("tax_ids", "in", sale_tax_ids),
                ("product_id", "!=", False),
                ("product_id.l10n_id_product_code", "=", False),
            ]
            query(
                "efaktur_product_code",
                _("Taxable Invoice Lines Missing E-Faktur Product Code"),
                "blocking" if profile.require_product_efaktur_code else "warning",
                "account.move.line",
                product_domain,
                _("Assign the native Coretax E-Faktur product code to taxable products."),
            )

            uom_domain = [
                ("company_id", "=", self.company_id.id),
                ("move_id.state", "=", "posted"),
                ("move_id.invoice_date", ">=", self.date_from),
                ("move_id.invoice_date", "<=", self.date_to),
                ("move_id.move_type", "in", ("out_invoice", "out_refund")),
                ("tax_ids", "in", sale_tax_ids),
                ("product_uom_id", "!=", False),
                ("product_uom_id.l10n_id_uom_code", "=", False),
            ]
            query(
                "efaktur_uom_code",
                _("Taxable Invoice Lines Missing E-Faktur UoM Code"),
                "blocking" if profile.require_uom_efaktur_code else "warning",
                "account.move.line",
                uom_domain,
                _("Assign native Coretax UoM codes where operationally required."),
            )

            # Coretax batching is an operational workflow, so unbatched eligible invoices remain warnings rather than ledger blockers.
            # Unbatched documents are a workflow warning, not an accounting blocker.
            query(
                "coretax_not_batched",
                _("Taxable PKP Customer Invoices Not Yet Assigned to Coretax Document"),
                "warning",
                "account.move",
                period_domain + [
                    ("invoice_line_ids.tax_ids", "in", sale_tax_ids),
                    ("commercial_partner_id.l10n_id_pkp", "=", True),
                    ("l10n_id_coretax_document", "=", False),
                ],
                _("Review and add eligible invoices to the native Coretax E-Faktur document workflow."),
            )

        # Journal numbering governance.
        if profile.require_numbering_policy:
            sale_journals = self.env["account.journal"].sudo().search([
                ("company_id", "=", self.company_id.id),
                ("type", "=", "sale"),
                ("active", "=", True),
            ])
            for journal in sale_journals:
                policy = self.env["clinic.l10n.id.numbering.policy"].sudo().search([
                    ("journal_id", "=", journal.id),
                    ("state", "=", "applied"),
                ], limit=1)
                direct(
                    f"numbering_{journal.id}",
                    _("Applied Numbering Policy: %s") % journal.display_name,
                    "warning",
                    bool(policy and policy.compliant),
                    _("Create/apply a numbering policy or review the native journal sequence configuration."),
                )

        return values

    def action_mark_reviewed(self):
        if not self.env.user.has_group("clinic_l10n_id.group_clinic_l10n_id_approver"):
            raise AccessError(_("Only an Indonesia Localization Approver can review compliance evidence."))
        for record in self:
            if record.state != "generated":
                raise UserError(_("Generate the Compliance Run before review."))
            record.with_context(l10n_transition=True).write({
                "state": "reviewed",
                "reviewed_at": fields.Datetime.now(),
                "reviewed_by_id": self.env.user.id,
            })
        return True

    def action_lock(self):
        if not self.env.user.has_group("clinic_l10n_id.group_clinic_l10n_id_manager"):
            raise AccessError(_("Only an Indonesia Localization Manager can lock compliance evidence."))
        for record in self:
            if record.state != "reviewed":
                raise UserError(_("Review the Compliance Run before locking it."))
            record.with_context(l10n_transition=True).write({"state": "locked"})
        return True

    def action_reset_to_draft(self):
        if not self.env.user.has_group("clinic_l10n_id.group_clinic_l10n_id_accountant"):
            raise AccessError(_("Only Indonesia tax/accounting staff can reset compliance runs."))
        for record in self:
            if record.state == "locked":
                raise UserError(_("Locked Compliance evidence cannot be reset."))
            record.line_ids.sudo().unlink()
            record.with_context(l10n_transition=True).write({
                "state": "draft",
                "generated_at": False,
                "generated_by_id": False,
                "reviewed_at": False,
                "reviewed_by_id": False,
            })
        return True

    def action_view_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Compliance Check Lines"),
            "res_model": "clinic.l10n.id.compliance.line",
            "view_mode": "list,form",
            "domain": [("run_id", "=", self.id)],
        }

    def action_print_compliance(self):
        self.ensure_one()
        if self.state == "draft":
            raise UserError(_("Generate the Compliance Run before printing."))
        return self.env.ref("clinic_l10n_id.action_report_compliance").report_action(self)


class ClinicL10nIdComplianceLine(models.Model):
    """Generated compliance result with safe source-domain drill-down."""

    _name = "clinic.l10n.id.compliance.line"
    _description = "Clinic Indonesia Compliance Line"
    _order = "severity, code, id"

    _record_count_nonnegative = models.Constraint(
        "CHECK(record_count >= 0)",
        "Compliance record count cannot be negative.",
    )

    run_id = fields.Many2one(
        "clinic.l10n.id.compliance.run",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="run_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    code = fields.Char(required=True, index=True)
    title = fields.Char(required=True)
    severity = fields.Selection(
        [
            ("blocking", "Blocking"),
            ("warning", "Warning"),
            ("info", "Information"),
        ],
        required=True,
        index=True,
    )
    status = fields.Selection(
        [("clear", "Clear"), ("open", "Open")],
        required=True,
        index=True,
    )
    record_count = fields.Integer(default=0)
    model_name = fields.Char()
    domain_text = fields.Text()
    note = fields.Text()

    def action_open_records(self):
        self.ensure_one()
        if not self.model_name or not self.record_count:
            raise UserError(_("There are no source records to open."))
        try:
            domain = ast.literal_eval(self.domain_text or "[]")
        except (ValueError, SyntaxError):
            domain = []
        if not isinstance(domain, list):
            domain = []
        return {
            "type": "ir.actions.act_window",
            "name": self.title,
            "res_model": self.model_name,
            "view_mode": "list,form",
            "domain": domain,
        }

    def action_open_run(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Indonesia Compliance Run"),
            "res_model": "clinic.l10n.id.compliance.run",
            "view_mode": "form",
            "res_id": self.run_id.id,
        }

