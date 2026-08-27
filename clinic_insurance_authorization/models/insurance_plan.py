from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicInsurancePlan(models.Model):
    """Payer plan master; actual patient enrollment lives in Insurance Policy."""

    _name = "clinic.insurance.plan"
    _description = "Clinic Insurance Plan"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.insurance.company.mixin"]
    _order = "insurer_partner_id, code, id"
    _check_company_auto = True

    _plan_unique = models.Constraint(
        "UNIQUE(company_id, insurer_partner_id, code)",
        "Insurance Plan code must be unique per company and insurer.",
    )
    _coverage_range = models.Constraint(
        "CHECK(default_coverage_percent >= 0 AND default_coverage_percent <= 100)",
        "Default coverage percentage must be between 0 and 100.",
    )
    _copay_range = models.Constraint(
        "CHECK(default_copay_percent >= 0 AND default_copay_percent <= 100)",
        "Default co-pay percentage must be between 0 and 100.",
    )
    _amounts_nonnegative = models.Constraint(
        "CHECK(default_deductible_amount >= 0 AND annual_limit >= 0)",
        "Insurance deductible and annual limit cannot be negative.",
    )
    _company_state_idx = models.Index("(company_id, state, insurer_partner_id)")

    name = fields.Char(required=True, tracking=True, index=True)
    code = fields.Char(required=True, tracking=True, index=True)
    insurer_partner_id = fields.Many2one(
        "res.partner",
        string="Insurer / Payer",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('is_insurer', '=', True)]",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    authorization_required_default = fields.Boolean(
        string="Pre-Authorization Required by Default",
        default=True,
        tracking=True,
    )
    default_coverage_percent = fields.Float(
        string="Default Coverage (%)",
        default=0.0,
        tracking=True,
    )
    default_copay_percent = fields.Float(
        string="Default Co-pay (%)",
        default=0.0,
        tracking=True,
    )
    default_deductible_amount = fields.Monetary(
        string="Default Deductible",
        currency_field="currency_id",
        default=0.0,
        tracking=True,
    )
    annual_limit = fields.Monetary(
        string="Annual Benefit Limit",
        currency_field="currency_id",
        default=0.0,
        tracking=True,
        help="Zero means no ClinicOne-enforced annual monetary limit.",
    )
    eligibility_valid_days = fields.Integer(
        string="Eligibility Evidence Validity (Days)",
        default=30,
    )
    authorization_valid_days = fields.Integer(
        string="Authorization Validity (Days)",
        default=30,
    )
    settlement_journal_id = fields.Many2one(
        "account.journal",
        string="Preferred Settlement Journal",
        check_company=True,
        domain="[('company_id', '=', company_id), ('type', 'in', ('bank','cash','general'))]",
    )

    rule_ids = fields.One2many(
        "clinic.insurance.plan.rule",
        "plan_id",
        string="Benefit / Coverage Rules",
        copy=True,
    )
    policy_count = fields.Integer(compute="_compute_counts")
    authorization_count = fields.Integer(compute="_compute_counts")
    claim_count = fields.Integer(compute="_compute_counts")
    notes = fields.Text()

    @api.onchange("code")
    def _onchange_code_upper(self):
        for record in self:
            if record.code:
                record.code = record.code.strip().upper()

    @api.constrains(
        "company_id",
        "insurer_partner_id",
        "settlement_journal_id",
        "eligibility_valid_days",
        "authorization_valid_days",
    )
    def _check_plan_company_and_validity(self):
        for record in self:
            if record.settlement_journal_id and record.settlement_journal_id.company_id != record.company_id:
                raise ValidationError(_("Settlement Journal must belong to the Insurance Plan company."))
            if record.eligibility_valid_days < 0 or record.authorization_valid_days < 0:
                raise ValidationError(_("Insurance validity-day settings cannot be negative."))

    def _compute_counts(self):
        Policy = self.env["clinic.insurance.policy"]
        Authorization = self.env["clinic.insurance.authorization"]
        Claim = self.env["clinic.insurance.claim"]
        for record in self:
            record.policy_count = Policy.search_count([("plan_id", "=", record.id)])
            record.authorization_count = Authorization.search_count([("plan_id", "=", record.id)])
            record.claim_count = Claim.search_count([("plan_id", "=", record.id)])

    def write(self, vals):
        if "state" in vals and not self.env.context.get("insurance_transition"):
            raise AccessError(_("Use Insurance Plan workflow actions to change status."))
        if self.filtered(lambda plan: plan.state == "active") and {
            "company_id",
            "insurer_partner_id",
            "code",
        }.intersection(vals):
            raise UserError(_("Archive the active Insurance Plan before changing its core identity."))
        return super().write(vals)

    def action_activate(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_manager",
            _("Only an Insurance Manager can activate plans."),
        )
        for record in self:
            if not record.insurer_partner_id.is_insurer:
                raise UserError(_("The selected payer must be marked as an Insurer / Payer."))
            record.with_context(insurance_transition=True).write({"state": "active"})
        return True

    def action_archive(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_manager",
            _("Only an Insurance Manager can archive plans."),
        )
        self.with_context(insurance_transition=True).write({"state": "archived"})
        return True

    def action_reset_to_draft(self):
        self._insurance_require_group(
            "clinic_insurance_authorization.group_clinic_insurance_manager",
            _("Only an Insurance Manager can reset plans."),
        )
        for record in self:
            if record.state == "active":
                raise UserError(_("Archive an active plan before resetting it."))
            record.with_context(insurance_transition=True).write({"state": "draft"})
        return True

    def _rule_domain_for_service(self, treatment_catalog=None, procedure_catalog=None, product=None):
        self.ensure_one()
        domain = [("plan_id", "=", self.id), ("active", "=", True)]
        candidates = []
        if treatment_catalog:
            candidates.append(("treatment_catalog_id", "=", treatment_catalog.id))
        if procedure_catalog:
            candidates.append(("procedure_catalog_id", "=", procedure_catalog.id))
        if product:
            candidates.append(("product_id", "=", product.id))

        if not candidates:
            return domain + [
                ("treatment_catalog_id", "=", False),
                ("procedure_catalog_id", "=", False),
                ("product_id", "=", False),
            ]

        # Find exact service rules first. If none exist, caller can fall back to
        # the plan's generic rule (all three service selectors empty).
        return domain + ["|"] * (len(candidates) - 1) + candidates

    # Benefit resolution is deterministic: exact service rule first, generic Plan fallback second.
    def get_rule_for_service(self, treatment_catalog=None, procedure_catalog=None, product=None):
        """Return the first specific rule, otherwise a generic plan rule."""
        self.ensure_one()
        Rule = self.env["clinic.insurance.plan.rule"]
        rule = Rule.search(
            self._rule_domain_for_service(treatment_catalog, procedure_catalog, product),
            order="sequence, id",
            limit=1,
        )
        if rule:
            return rule
        return Rule.search([
            ("plan_id", "=", self.id),
            ("active", "=", True),
            ("treatment_catalog_id", "=", False),
            ("procedure_catalog_id", "=", False),
            ("product_id", "=", False),
        ], order="sequence, id", limit=1)

    def action_view_policies(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Policies"),
            "res_model": "clinic.insurance.policy",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
            "context": {
                "default_plan_id": self.id,
                "default_company_id": self.company_id.id,
                "default_insurer_partner_id": self.insurer_partner_id.id,
            },
        }

    def action_view_authorizations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pre-Authorizations"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
        }

    # Claim navigation uses the Billing-owned claim model; no claim master is duplicated here.
    def action_view_claims(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Claims"),
            "res_model": "clinic.insurance.claim",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
        }


class ClinicInsurancePlanRule(models.Model):
    """Service-level coverage/authorization rule under an Insurance Plan."""

    _name = "clinic.insurance.plan.rule"
    _description = "Clinic Insurance Plan Benefit Rule"
    _order = "plan_id, sequence, id"
    _check_company_auto = True

    _coverage_range = models.Constraint(
        "CHECK(coverage_percent >= 0 AND coverage_percent <= 100)",
        "Coverage percentage must be between 0 and 100.",
    )
    _copay_range = models.Constraint(
        "CHECK(copay_percent >= 0 AND copay_percent <= 100)",
        "Co-pay percentage must be between 0 and 100.",
    )
    _rule_amounts_nonnegative = models.Constraint(
        "CHECK(deductible_amount >= 0 AND maximum_amount >= 0 AND maximum_quantity >= 0)",
        "Benefit-rule monetary and quantity limits cannot be negative.",
    )
    _plan_sequence_idx = models.Index("(plan_id, active, sequence)")

    plan_id = fields.Many2one(
        "clinic.insurance.plan",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="plan_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="plan_id.currency_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    treatment_catalog_id = fields.Many2one(
        "clinic.treatment.catalog",
        string="Treatment Catalog",
        ondelete="restrict",
    )
    procedure_catalog_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure Catalog",
        ondelete="restrict",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product / Service",
        ondelete="restrict",
    )

    authorization_required = fields.Boolean(default=True)
    coverage_percent = fields.Float(default=0.0)
    copay_percent = fields.Float(default=0.0)
    deductible_amount = fields.Monetary(currency_field="currency_id", default=0.0)
    maximum_amount = fields.Monetary(
        string="Maximum Insurer Amount per Authorization",
        currency_field="currency_id",
        default=0.0,
        help="Zero means no rule-level maximum.",
    )
    maximum_quantity = fields.Float(
        string="Maximum Quantity per Authorization",
        default=0.0,
        help="Zero means no rule-level quantity maximum.",
    )
    note = fields.Char()

    @api.constrains(
        "plan_id",
        "treatment_catalog_id",
        "procedure_catalog_id",
        "product_id",
    )
    def _check_rule_company(self):
        for record in self:
            for service in (
                record.treatment_catalog_id,
                record.procedure_catalog_id,
            ):
                if service and "company_id" in service._fields and service.company_id and service.company_id != record.company_id:
                    raise ValidationError(_("Benefit Rule service must belong to the Insurance Plan company."))

    def action_open_plan(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Plan"),
            "res_model": "clinic.insurance.plan",
            "view_mode": "form",
            "res_id": self.plan_id.id,
        }

