from odoo import api, Command, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicL10nIdTaxProfile(models.Model):
    """ClinicOne governance profile over native Indonesian tax/localization records."""

    _name = "clinic.l10n.id.tax.profile"
    _description = "Clinic Indonesia Tax Profile"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "company_id, id"
    _check_company_auto = True

    _company_unique = models.Constraint(
        "UNIQUE(company_id)",
        "Only one Clinic Indonesia Tax Profile is allowed per company.",
    )
    _company_state_idx = models.Index("(company_id, state)")

    name = fields.Char(
        default=lambda self: _("Indonesia Tax Profile"),
        required=True,
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
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    country_id = fields.Many2one(
        "res.country",
        related="company_id.country_id",
        readonly=True,
    )
    fiscal_country_id = fields.Many2one(
        "res.country",
        related="company_id.account_fiscal_country_id",
        readonly=True,
    )
    company_partner_id = fields.Many2one(
        "res.partner",
        related="company_id.partner_id",
        readonly=True,
    )
    npwp = fields.Char(
        related="company_id.partner_id.vat",
        string="NPWP / Tax ID",
        readonly=True,
    )
    is_pkp = fields.Boolean(
        related="company_id.partner_id.l10n_id_pkp",
        readonly=True,
        string="Company Is PKP",
    )
    tku = fields.Char(
        related="company_id.partner_id.l10n_id_tku",
        readonly=True,
        string="TKU",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("active", "Active"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    # PPN scope stores references to native Odoo taxes; no statutory rate is duplicated here.
    ppn_sale_tax_ids = fields.Many2many(
        "account.tax",
        "clinic_l10n_id_profile_sale_tax_rel",
        "profile_id",
        "tax_id",
        string="PPN Sales Taxes",
        check_company=True,
        domain="[('company_id', '=', company_id), ('type_tax_use', '=', 'sale')]",
        help="Native Indonesian sale tax records to include in ClinicOne PPN output reporting.",
    )
    ppn_purchase_tax_ids = fields.Many2many(
        "account.tax",
        "clinic_l10n_id_profile_purchase_tax_rel",
        "profile_id",
        "tax_id",
        string="PPN Purchase Taxes",
        check_company=True,
        domain="[('company_id', '=', company_id), ('type_tax_use', '=', 'purchase')]",
        help="Native Indonesian purchase tax records to include in ClinicOne PPN input reporting.",
    )
    report_journal_ids = fields.Many2many(
        "account.journal",
        "clinic_l10n_id_profile_journal_rel",
        "profile_id",
        "journal_id",
        string="Report Journals",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Optional journal restriction. Leave empty to include every journal.",
    )

    default_source_scope = fields.Selection(
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
    )

    require_company_npwp = fields.Boolean(default=True)
    require_partner_tax_identity = fields.Boolean(default=True)
    require_product_efaktur_code = fields.Boolean(default=True)
    require_uom_efaktur_code = fields.Boolean(default=False)
    require_numbering_policy = fields.Boolean(default=True)

    readiness_score = fields.Integer(compute="_compute_readiness", store=True)
    readiness_state = fields.Selection(
        [
            ("critical", "Critical"),
            ("attention", "Attention"),
            ("ready", "Ready"),
        ],
        compute="_compute_readiness",
        store=True,
    )
    readiness_note = fields.Char(compute="_compute_readiness", store=True)

    tax_report_count = fields.Integer(compute="_compute_counts")
    compliance_count = fields.Integer(compute="_compute_counts")
    numbering_policy_count = fields.Integer(compute="_compute_counts")
    coretax_document_count = fields.Integer(compute="_compute_counts")
    notes = fields.Text()

    @api.depends(
        "country_id",
        "fiscal_country_id",
        "npwp",
        "ppn_sale_tax_ids",
        "ppn_purchase_tax_ids",
        "require_company_npwp",
    )
    def _compute_readiness(self):
        for record in self:
            score = 0
            problems = []

            if record.country_id.code == "ID":
                score += 20
            else:
                problems.append(_("Company country is not Indonesia."))

            if record.fiscal_country_id.code == "ID":
                score += 20
            else:
                problems.append(_("Fiscal country is not Indonesia."))

            if not record.require_company_npwp or record.npwp:
                score += 20
            else:
                problems.append(_("Company NPWP is missing."))

            if record.ppn_sale_tax_ids:
                score += 20
            else:
                problems.append(_("PPN sales-tax scope is empty."))

            if record.ppn_purchase_tax_ids:
                score += 20
            else:
                problems.append(_("PPN purchase-tax scope is empty."))

            record.readiness_score = score
            record.readiness_state = (
                "ready" if score == 100
                else "attention" if score >= 60
                else "critical"
            )
            record.readiness_note = " ".join(problems) if problems else _("Ready for ClinicOne Indonesia tax reporting.")

    def _compute_counts(self):
        Report = self.env["clinic.l10n.id.tax.report"]
        Compliance = self.env["clinic.l10n.id.compliance.run"]
        Policy = self.env["clinic.l10n.id.numbering.policy"]
        Coretax = self.env["l10n_id_efaktur_coretax.document"]

        for record in self:
            record.tax_report_count = Report.search_count([("profile_id", "=", record.id)])
            record.compliance_count = Compliance.search_count([("profile_id", "=", record.id)])
            record.numbering_policy_count = Policy.search_count([("profile_id", "=", record.id)])
            record.coretax_document_count = Coretax.search_count([("company_id", "=", record.company_id.id)])

    @api.constrains("company_id", "ppn_sale_tax_ids", "ppn_purchase_tax_ids", "report_journal_ids")
    def _check_company_scope(self):
        for record in self:
            if record.ppn_sale_tax_ids.filtered(lambda tax: tax.company_id != record.company_id):
                raise ValidationError(_("All PPN sales taxes must belong to the Profile company."))
            if record.ppn_purchase_tax_ids.filtered(lambda tax: tax.company_id != record.company_id):
                raise ValidationError(_("All PPN purchase taxes must belong to the Profile company."))
            if record.report_journal_ids.filtered(lambda journal: journal.company_id != record.company_id):
                raise ValidationError(_("All report journals must belong to the Profile company."))

    def write(self, vals):
        if "state" in vals and not self.env.context.get("l10n_transition"):
            raise AccessError(_("Use the Tax Profile workflow buttons to change status."))
        if self.filtered(lambda profile: profile.state == "active") and {
            "company_id",
            "ppn_sale_tax_ids",
            "ppn_purchase_tax_ids",
        }.intersection(vals):
            raise UserError(_("Deactivate/archive the active profile before changing core tax scope."))
        return super().write(vals)

    # This helper proposes native Indonesian taxes; managers remain responsible for refining the legal reporting scope.
    def action_load_native_taxes(self):
        self._l10n_manager_required()
        Tax = self.env["account.tax"]
        for record in self:
            sale = Tax.with_company(record.company_id).search([
                ("company_id", "=", record.company_id.id),
                ("country_id.code", "=", "ID"),
                ("type_tax_use", "=", "sale"),
                ("active", "=", True),
            ])
            purchase = Tax.with_company(record.company_id).search([
                ("company_id", "=", record.company_id.id),
                ("country_id.code", "=", "ID"),
                ("type_tax_use", "=", "purchase"),
                ("active", "=", True),
            ])
            record.write({
                "ppn_sale_tax_ids": [Command.set(sale.ids)],
                "ppn_purchase_tax_ids": [Command.set(purchase.ids)],
            })
        return True

    # Validation is deliberately stricter than UI domains so imports/RPC cannot activate an incomplete tax profile.
    def action_validate(self):
        self._l10n_manager_required()
        for record in self:
            if record.country_id.code != "ID":
                raise UserError(_("Company country must be Indonesia."))
            if record.fiscal_country_id.code != "ID":
                raise UserError(_("Accounting fiscal country must be Indonesia."))
            if record.require_company_npwp and not record.npwp:
                raise UserError(_("Company NPWP / Tax ID is required."))
            if not record.ppn_sale_tax_ids:
                raise UserError(_("Configure at least one native PPN sales tax."))
            if not record.ppn_purchase_tax_ids:
                raise UserError(_("Configure at least one native PPN purchase tax."))
            record.with_context(l10n_transition=True).write({"state": "validated"})
        return True

    def action_activate(self):
        self._l10n_manager_required()
        for record in self:
            if record.state != "validated":
                raise UserError(_("Validate the Tax Profile before activation."))
            other = self.search([
                ("id", "!=", record.id),
                ("company_id", "=", record.company_id.id),
                ("state", "=", "active"),
            ])
            if other:
                other.with_context(l10n_transition=True).write({"state": "archived"})
            record.with_context(l10n_transition=True).write({"state": "active"})
            record.company_id.clinic_l10n_id_profile_id = record.id
        return True

    def action_archive(self):
        self._l10n_manager_required()
        for record in self:
            record.with_context(l10n_transition=True).write({"state": "archived"})
            if record.company_id.clinic_l10n_id_profile_id == record:
                record.company_id.clinic_l10n_id_profile_id = False
        return True

    def action_reset_to_draft(self):
        self._l10n_manager_required()
        self.with_context(l10n_transition=True).write({"state": "draft"})
        return True

    def _l10n_manager_required(self):
        if not self.env.user.has_group("clinic_l10n_id.group_clinic_l10n_id_manager"):
            raise AccessError(_("Only an Indonesia Localization Manager can change Tax Profile governance."))

    def action_new_tax_report(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New PPN Tax Report"),
            "res_model": "clinic.l10n.id.tax.report",
            "view_mode": "form",
            "context": {
                "default_profile_id": self.id,
                "default_company_id": self.company_id.id,
                "default_source_scope": self.default_source_scope,
            },
        }

    def action_run_compliance(self):
        self.ensure_one()
        run = self.env["clinic.l10n.id.compliance.run"].create({
            "profile_id": self.id,
            "company_id": self.company_id.id,
        })
        run.action_generate()
        return {
            "type": "ir.actions.act_window",
            "name": _("Indonesia Compliance Run"),
            "res_model": "clinic.l10n.id.compliance.run",
            "view_mode": "form",
            "res_id": run.id,
        }

    def action_view_tax_reports(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("PPN Tax Reports"),
            "res_model": "clinic.l10n.id.tax.report",
            "view_mode": "list,form,pivot,graph",
            "domain": [("profile_id", "=", self.id)],
        }

    def action_view_compliance(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Indonesia Compliance"),
            "res_model": "clinic.l10n.id.compliance.run",
            "view_mode": "list,form",
            "domain": [("profile_id", "=", self.id)],
        }

    def action_view_numbering_policies(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Invoice Numbering Policies"),
            "res_model": "clinic.l10n.id.numbering.policy",
            "view_mode": "list,form",
            "domain": [("profile_id", "=", self.id)],
            "context": {
                "default_profile_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_view_native_taxes(self):
        self.ensure_one()
        tax_ids = (self.ppn_sale_tax_ids | self.ppn_purchase_tax_ids).ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Native Indonesian Taxes"),
            "res_model": "account.tax",
            "view_mode": "list,form",
            "domain": [("id", "in", tax_ids)],
        }

    def action_view_coretax_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Coretax E-Faktur Documents"),
            "res_model": "l10n_id_efaktur_coretax.document",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.company_id.id)],
            "context": {"default_company_id": self.company_id.id},
        }

