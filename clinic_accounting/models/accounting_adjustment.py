from odoo import api, Command, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class ClinicAccountingAdjustment(models.Model):
    """Governed manual adjustment that posts one balanced standard Odoo journal entry."""

    _name = "clinic.accounting.adjustment"
    _description = "Clinic Accounting Adjustment"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.accounting.company.mixin"]
    _order = "adjustment_date desc, id desc"
    _check_company_auto = True

    _company_state_date_idx = models.Index("(company_id, state, adjustment_date)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    adjustment_date = fields.Date(
        default=fields.Date.context_today,
        required=True,
        tracking=True,
        index=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        check_company=True,
        ondelete="restrict",
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]",
        default=lambda self: self.env.company.clinic_accounting_adjustment_journal_id,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    adjustment_type = fields.Selection(
        [
            ("accrual", "Accrual"),
            ("reclassification", "Reclassification"),
            ("correction", "Correction"),
            ("provision", "Provision"),
            ("writeoff", "Write-Off"),
            ("opening", "Opening / Migration"),
            ("other", "Other Adjustment"),
        ],
        default="correction",
        required=True,
        tracking=True,
        index=True,
    )
    reference = fields.Char(tracking=True)
    description = fields.Text(required=True, tracking=True)

    line_ids = fields.One2many(
        "clinic.accounting.adjustment.line",
        "adjustment_id",
        string="Adjustment Lines",
        copy=True,
    )
    total_debit = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    total_credit = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )
    difference = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("posted", "Posted"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    approval_required = fields.Boolean(
        compute="_compute_approval_required",
        store=True,
    )
    submitted_by_id = fields.Many2one("res.users", readonly=True)
    submitted_at = fields.Datetime(readonly=True)
    approved_by_id = fields.Many2one("res.users", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    posted_by_id = fields.Many2one("res.users", readonly=True)
    posted_at = fields.Datetime(readonly=True)

    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        readonly=True,
        copy=False,
        check_company=True,
        ondelete="restrict",
    )
    move_state = fields.Selection(related="move_id.state", readonly=True)

    @api.depends("line_ids.debit", "line_ids.credit")
    def _compute_totals(self):
        for record in self:
            record.total_debit = sum(record.line_ids.mapped("debit"))
            record.total_credit = sum(record.line_ids.mapped("credit"))
            record.difference = record.total_debit - record.total_credit

    @api.depends("total_debit", "company_id.clinic_accounting_adjustment_approval_threshold")
    def _compute_approval_required(self):
        for record in self:
            threshold = record.company_id.clinic_accounting_adjustment_approval_threshold or 0.0
            record.approval_required = bool(threshold and record.total_debit >= threshold)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
            vals.setdefault(
                "journal_id",
                company.clinic_accounting_adjustment_journal_id.id,
            )
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.accounting.adjustment")
                    or "/"
                )
        return super().create(vals_list)

    def write(self, vals):
        editable_fields = {
            "company_id",
            "branch_id",
            "adjustment_date",
            "journal_id",
            "adjustment_type",
            "reference",
            "description",
            "line_ids",
        }
        system_fields = {
            "state",
            "move_id",
            "submitted_by_id",
            "submitted_at",
            "approved_by_id",
            "approved_at",
            "posted_by_id",
            "posted_at",
        }

        if system_fields.intersection(vals) and not self.env.context.get("accounting_transition"):
            raise AccessError(
                _("Adjustment workflow and accounting audit fields can only be changed by Accounting actions.")
            )

        if editable_fields.intersection(vals):
            for record in self:
                if record.state != "draft":
                    raise UserError(_("Adjustment content can only be edited while Draft."))
        return super().write(vals)

    @api.constrains("journal_id", "company_id")
    def _check_journal_scope(self):
        for record in self:
            if record.journal_id.company_id != record.company_id:
                raise ValidationError(_("Adjustment journal and company must match."))
            if record.journal_id.type != "general":
                raise ValidationError(_("Accounting Adjustments require a General journal."))

    def _check_balanced_ready(self):
        self.ensure_one()
        if len(self.line_ids) < 2:
            raise UserError(_("An Accounting Adjustment requires at least two lines."))
        if float_is_zero(self.total_debit, precision_rounding=self.currency_id.rounding):
            raise UserError(_("Adjustment total must be greater than zero."))
        if float_compare(
            self.total_debit,
            self.total_credit,
            precision_rounding=self.currency_id.rounding,
        ):
            raise UserError(_("Debit and credit totals must be exactly balanced."))

    def action_submit(self):
        self._accounting_require_group("clinic_accounting.group_clinic_accounting_accountant")
        now = fields.Datetime.now()
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only Draft adjustments can be submitted."))
            record._check_balanced_ready()
            values = {
                "state": "submitted",
                "submitted_by_id": self.env.user.id,
                "submitted_at": now,
            }
            if not record.approval_required:
                values.update({
                    "state": "approved",
                    "approved_by_id": self.env.user.id,
                    "approved_at": now,
                })
            record.with_context(accounting_transition=True).write(values)
        return True

    def action_approve(self):
        self._accounting_require_group("clinic_accounting.group_clinic_accounting_approver")
        for record in self:
            if record.state != "submitted":
                raise UserError(_("Only Submitted adjustments can be approved."))
            record._check_balanced_ready()
            record.with_context(accounting_transition=True).write({
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })
        return True

    def action_post(self):
        self._accounting_require_group("clinic_accounting.group_clinic_accounting_accountant")
        for record in self:
            if record.state != "approved":
                raise UserError(_("Only Approved adjustments can be posted."))
            record._check_balanced_ready()
            move = self.env["account.move"].create(record._prepare_move_vals())
            move.action_post()
            record.with_context(accounting_transition=True).write({
                "state": "posted",
                "move_id": move.id,
                "posted_by_id": self.env.user.id,
                "posted_at": fields.Datetime.now(),
            })
        return True

    def action_cancel(self):
        self._accounting_require_group("clinic_accounting.group_clinic_accounting_manager")
        for record in self:
            if record.state == "posted":
                raise UserError(
                    _("Posted adjustments cannot be cancelled here. Reverse the standard Odoo Journal Entry.")
                )
            record.with_context(accounting_transition=True).write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        self._accounting_require_group("clinic_accounting.group_clinic_accounting_manager")
        for record in self:
            if record.state == "posted":
                raise UserError(_("Posted adjustments cannot be reset to Draft."))
            record.with_context(accounting_transition=True).write({
                "state": "draft",
                "submitted_by_id": False,
                "submitted_at": False,
                "approved_by_id": False,
                "approved_at": False,
            })
        return True

    def _prepare_move_vals(self):
        self.ensure_one()
        # The legal ledger remains Odoo account.move. Clinic Accounting contributes
        # governance and traceability, never a parallel debit/credit table.
        move_lines = []
        for line in self.line_ids:
            line_vals = {
                "name": line.label or self.description or self.name,
                "account_id": line.account_id.id,
                "partner_id": line.partner_id.id or False,
                "debit": line.debit,
                "credit": line.credit,
            }
            if self.branch_id and "branch_id" in self.env["account.move.line"]._fields:
                line_vals["branch_id"] = self.branch_id.id
            if (
                line.analytic_account_id
                and "analytic_distribution" in self.env["account.move.line"]._fields
            ):
                line_vals["analytic_distribution"] = {
                    str(line.analytic_account_id.id): 100.0,
                }
            move_lines.append(Command.create(line_vals))

        values = {
            "move_type": "entry",
            "date": self.adjustment_date,
            "journal_id": self.journal_id.id,
            "ref": self.reference or self.name,
            "clinic_accounting_adjustment_id": self.id,
            "line_ids": move_lines,
        }
        if self.branch_id and "branch_id" in self.env["account.move"]._fields:
            values["branch_id"] = self.branch_id.id
        return values

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("This Accounting Adjustment has no Journal Entry yet."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Journal Entry"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
        }


class ClinicAccountingAdjustmentLine(models.Model):
    """Human-readable debit/credit line used by a governed Accounting Adjustment."""

    _name = "clinic.accounting.adjustment.line"
    _description = "Clinic Accounting Adjustment Line"
    _order = "sequence, id"

    _debit_nonnegative = models.Constraint(
        "CHECK(debit >= 0)",
        "Adjustment line debit cannot be negative.",
    )
    _credit_nonnegative = models.Constraint(
        "CHECK(credit >= 0)",
        "Adjustment line credit cannot be negative.",
    )
    _single_side_only = models.Constraint(
        "CHECK(NOT (debit > 0 AND credit > 0))",
        "An Adjustment line cannot contain both debit and credit.",
    )

    adjustment_id = fields.Many2one(
        "clinic.accounting.adjustment",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        related="adjustment_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    branch_id = fields.Many2one(
        related="adjustment_id.branch_id",
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="adjustment_id.currency_id",
        store=True,
        readonly=True,
    )
    account_id = fields.Many2one(
        "account.account",
        required=True,
        ondelete="restrict",
        index=True,
    )
    partner_id = fields.Many2one("res.partner")
    analytic_account_id = fields.Many2one("account.analytic.account", ondelete="restrict")
    label = fields.Char(required=True)
    debit = fields.Monetary(currency_field="currency_id", default=0.0)
    credit = fields.Monetary(currency_field="currency_id", default=0.0)
    balance = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_balance",
        store=True,
    )

    @api.depends("debit", "credit")
    def _compute_balance(self):
        for record in self:
            record.balance = record.debit - record.credit

    @api.constrains("debit", "credit")
    def _check_debit_credit_exclusive(self):
        for record in self:
            has_debit = not float_is_zero(
                record.debit,
                precision_rounding=record.currency_id.rounding,
            )
            has_credit = not float_is_zero(
                record.credit,
                precision_rounding=record.currency_id.rounding,
            )
            if has_debit == has_credit:
                raise ValidationError(
                    _("Each adjustment line must contain either a debit or a credit, but not both.")
                )

    @api.constrains("account_id", "company_id")
    def _check_account_company(self):
        for record in self:
            if record.account_id and record.company_id not in record.account_id.company_ids:
                raise ValidationError(
                    _("The selected account must be available to the Adjustment company.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        adjustments = self.env["clinic.accounting.adjustment"].browse(
            [vals.get("adjustment_id") for vals in vals_list if vals.get("adjustment_id")]
        )
        if adjustments.filtered(lambda adjustment: adjustment.state != "draft"):
            raise AccessError(_("Adjustment lines can only be created while the Adjustment is Draft."))
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered(lambda line: line.adjustment_id.state != "draft"):
            raise AccessError(_("Adjustment lines are immutable outside Draft."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda line: line.adjustment_id.state != "draft"):
            raise AccessError(_("Adjustment lines cannot be deleted outside Draft."))
        return super().unlink()

    def action_open_adjustment(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Accounting Adjustment"),
            "res_model": "clinic.accounting.adjustment",
            "view_mode": "form",
            "res_id": self.adjustment_id.id,
        }
