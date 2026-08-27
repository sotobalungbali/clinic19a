from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicAccountingLedger(models.Model):
    """Named reporting/control scope over the standard Odoo accounting ledger."""

    _name = "clinic.accounting.ledger"
    _description = "Clinic Accounting Ledger"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "company_id, sequence, code, name"
    _check_company_auto = True

    _code_company_unique = models.Constraint(
        "UNIQUE(company_id, code)",
        "Accounting Ledger code must be unique per company.",
    )
    _company_active_idx = models.Index("(company_id, active)")

    # A Ledger can intentionally span several clinic branches, so it owns only
    # a company plus the explicit branch_ids reporting scope; there is no
    # misleading single "primary branch" field.
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)

    ledger_type = fields.Selection(
        [
            ("general", "General Ledger"),
            ("treasury", "Treasury Ledger"),
            ("revenue", "Revenue Ledger"),
            ("expense", "Expense Ledger"),
            ("clinic_operations", "Clinic Operations Ledger"),
            ("custom", "Custom Ledger"),
        ],
        default="general",
        required=True,
        tracking=True,
        index=True,
    )
    source_scope = fields.Selection(
        [
            ("all", "All Accounting Entries"),
            ("clinic_only", "ClinicOne-Sourced Entries"),
            ("finance", "Clinic Finance"),
            ("billing", "Clinic Billing"),
            ("ar", "Accounts Receivable"),
            ("ap", "Accounts Payable"),
            ("wallet", "Patient Wallet"),
            ("adjustment", "Accounting Adjustments"),
            ("mixed", "Mixed Clinic Sources"),
            ("other", "Other / Native Odoo"),
        ],
        default="all",
        required=True,
        tracking=True,
    )
    journal_ids = fields.Many2many(
        "account.journal",
        "clinic_accounting_ledger_journal_rel",
        "ledger_id",
        "journal_id",
        string="Journals",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Leave empty to include every journal allowed by the other Ledger filters.",
    )
    account_ids = fields.Many2many(
        "account.account",
        "clinic_accounting_ledger_account_rel",
        "ledger_id",
        "account_id",
        string="Accounts",
        help="Leave empty to include all accounts available to the company.",
    )
    branch_ids = fields.Many2many(
        "clinic.branch",
        "clinic_accounting_ledger_branch_rel",
        "ledger_id",
        "branch_id",
        string="Branches",
        domain="[('company_id', '=', company_id)]",
        help="Leave empty to include every branch in the company.",
    )
    posted_only = fields.Boolean(
        default=True,
        help="Recommended. Draft moves remain outside the official ledger scope.",
    )
    default_statement_type = fields.Selection(
        [
            ("trial_balance", "Trial Balance"),
            ("general_ledger", "General Ledger"),
            ("profit_loss", "Profit & Loss"),
            ("balance_sheet", "Balance Sheet"),
            ("journal_audit", "Journal Audit"),
            ("source_summary", "Clinic Source Summary"),
        ],
        default="trial_balance",
        required=True,
    )
    notes = fields.Text()

    entry_count = fields.Integer(compute="_compute_counts")
    statement_count = fields.Integer(compute="_compute_counts")

    @api.constrains("company_id", "journal_ids", "account_ids", "branch_ids")
    def _check_ledger_company_scope(self):
        # Odoo 19 account.account can belong to multiple companies through
        # company_ids; membership, not a scalar company_id, is the right check.
        for record in self:
            if record.journal_ids.filtered(lambda journal: journal.company_id != record.company_id):
                raise ValidationError(_("Every selected journal must belong to the Ledger company."))
            if record.account_ids.filtered(lambda account: record.company_id not in account.company_ids):
                raise ValidationError(_("Every selected account must be available to the Ledger company."))
            if record.branch_ids.filtered(lambda branch: branch.company_id != record.company_id):
                raise ValidationError(_("Every selected branch must belong to the Ledger company."))

    def _entry_domain(self):
        self.ensure_one()
        domain = [("company_id", "=", self.company_id.id)]
        if self.posted_only:
            domain.append(("state", "=", "posted"))
        if self.journal_ids:
            domain.append(("journal_id", "in", self.journal_ids.ids))
        if self.branch_ids and "branch_id" in self.env["account.move"]._fields:
            domain.append(("branch_id", "in", self.branch_ids.ids))
        if self.source_scope == "clinic_only":
            domain.append(("clinic_accounting_source", "!=", "other"))
        elif self.source_scope != "all":
            domain.append(("clinic_accounting_source", "=", self.source_scope))
        return domain

    def _move_line_domain(self):
        self.ensure_one()
        domain = [("company_id", "=", self.company_id.id)]
        if self.posted_only:
            domain.append(("move_id.state", "=", "posted"))
        if self.journal_ids:
            domain.append(("move_id.journal_id", "in", self.journal_ids.ids))
        if self.account_ids:
            domain.append(("account_id", "in", self.account_ids.ids))
        if self.branch_ids and "branch_id" in self.env["account.move.line"]._fields:
            domain.append(("branch_id", "in", self.branch_ids.ids))
        if self.source_scope == "clinic_only":
            domain.append(("clinic_accounting_source", "!=", "other"))
        elif self.source_scope != "all":
            domain.append(("clinic_accounting_source", "=", self.source_scope))
        return domain

    def _compute_counts(self):
        Move = self.env["account.move"]
        Statement = self.env["clinic.accounting.statement"]
        for record in self:
            record.entry_count = Move.search_count(record._entry_domain())
            record.statement_count = Statement.search_count([("ledger_id", "=", record.id)])

    def action_view_entries(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Ledger Journal Entries"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": self._entry_domain(),
            "search_view_id": self.env.ref(
                "clinic_accounting.view_account_move_clinic_accounting_search"
            ).id,
        }

    def action_view_statements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Accounting Statements"),
            "res_model": "clinic.accounting.statement",
            "view_mode": "list,form,pivot,graph",
            "domain": [("ledger_id", "=", self.id)],
            "context": {"default_ledger_id": self.id, "default_company_id": self.company_id.id},
        }

    def action_new_statement(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Accounting Statement"),
            "res_model": "clinic.accounting.statement",
            "view_mode": "form",
            "context": {
                "default_ledger_id": self.id,
                "default_company_id": self.company_id.id,
                "default_statement_type": self.default_statement_type,
            },
        }
