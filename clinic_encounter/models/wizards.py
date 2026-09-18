# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/wizards.py
#
# Small operational wizards that complete contracts already referenced by the
# finished baseline. They are intentionally kept in the owner addon so runtime
# buttons do not point to missing XML-IDs.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ClinicEncounterBillWizard(models.TransientModel):
    _name = "clinic.encounter.bill.wizard"
    _description = "Generate Encounter Invoice"

    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Invoice Customer",
        related="encounter_id.partner_id",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="encounter_id.company_id",
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="encounter_id.currency_id",
        readonly=True,
    )
    invoice_date = fields.Date(
        string="Invoice Date",
        default=fields.Date.context_today,
        required=True,
    )
    eligible_plan_count = fields.Integer(
        string="Eligible Procedure Plans",
        compute="_compute_summary",
    )
    estimated_amount = fields.Monetary(
        string="Estimated Amount",
        compute="_compute_summary",
        currency_field="currency_id",
    )
    note = fields.Text(
        string="Billing Note",
        help="Optional internal note copied to the invoice narration.",
    )

    @api.depends(
        "encounter_id.procedure_line_ids.billing_policy",
        "encounter_id.procedure_line_ids.price_total",
        "encounter_id.procedure_line_ids.state",
    )
    def _compute_summary(self):
        for wizard in self:
            plans = wizard.encounter_id.procedure_line_ids.filtered(
                lambda line: line.billing_policy != "no_bill"
                and line.state != "cancelled"
            )
            wizard.eligible_plan_count = len(plans)
            wizard.estimated_amount = sum(plans.mapped("price_total"))

    def action_generate_invoice(self):
        self.ensure_one()
        encounter = self.encounter_id
        if not encounter.partner_id:
            raise UserError(_("The encounter patient does not have an invoicing contact."))

        plans = encounter.procedure_line_ids.filtered(
            lambda line: line.billing_policy != "no_bill"
            and line.state != "cancelled"
        )
        if not plans:
            raise UserError(_("There are no billable procedure plans on this encounter."))

        line_commands = []
        line_plan_map = []
        for plan in plans:
            prepared = plan.action_prepare_invoice_line_vals()
            for vals in prepared:
                # account.move owns currency; a currency_id on invoice lines is
                # not necessary and can interfere with Odoo's own precompute.
                vals = dict(vals)
                vals.pop("currency_id", None)
                line_commands.append((0, 0, vals))
                line_plan_map.append(plan)

        if not line_commands:
            raise UserError(_(
                "No invoice lines are currently eligible. "
                "Per-session billing requires completed procedure sessions."
            ))

        invoice_vals = {
            "move_type": "out_invoice",
            "partner_id": encounter.partner_id.id,
            "invoice_date": self.invoice_date,
            "invoice_origin": encounter.name,
            "company_id": encounter.company_id.id,
            "invoice_line_ids": line_commands,
        }
        if self.note:
            invoice_vals["narration"] = self.note

        invoice = self.env["account.move"].create(invoice_vals)

        # Preserve the plan -> invoice-line traceability expected by the baseline.
        created_lines = invoice.invoice_line_ids.filtered(
            lambda line: not line.display_type
        ).sorted("id")
        for plan, invoice_line in zip(line_plan_map, created_lines):
            plan.invoice_line_ids = [(4, invoice_line.id)]

        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_move_out_invoice_type"
        )
        action.update({
            "res_id": invoice.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "domain": [("id", "=", invoice.id)],
        })
        return action


class ClinicDiagnosisPlanProcedureWizard(models.TransientModel):
    _name = "clinic.diagnosis.plan.procedure.wizard"
    _description = "Generate Procedure Plans from Diagnosis"

    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
    )
    diagnosis_id = fields.Many2one(
        "clinic.diagnosis",
        string="Diagnosis",
        required=True,
        ondelete="cascade",
    )
    procedure_ids = fields.Many2many(
        "clinic.procedure.catalog",
        relation="clinic_diag_plan_proc_wiz_rel",
        column1="wizard_id",
        column2="procedure_id",
        string="Procedures",
        required=True,
        help="Procedures selected for plan generation from this diagnosis.",
    )
    skip_existing = fields.Boolean(
        string="Skip Existing Procedure Plans",
        default=True,
        help="Avoid creating another active plan for the same encounter, diagnosis and procedure.",
    )

    @api.onchange("diagnosis_id")
    def _onchange_diagnosis_id(self):
        if self.diagnosis_id:
            self.encounter_id = self.diagnosis_id.encounter_id
            if self.diagnosis_id.suggested_procedure_ids:
                self.procedure_ids = [(6, 0, self.diagnosis_id.suggested_procedure_ids.ids)]

    def action_generate_plans(self):
        self.ensure_one()
        if not self.procedure_ids:
            raise UserError(_("Select at least one procedure."))

        Plan = self.env["clinic.encounter.procedure"]
        created = Plan
        for procedure in self.procedure_ids:
            if self.skip_existing:
                existing = Plan.search([
                    ("encounter_id", "=", self.encounter_id.id),
                    ("diagnosis_id", "=", self.diagnosis_id.id),
                    ("procedure_id", "=", procedure.id),
                    ("state", "!=", "cancelled"),
                ], limit=1)
                if existing:
                    created |= existing
                    continue

            vals = {
                "encounter_id": self.encounter_id.id,
                "diagnosis_id": self.diagnosis_id.id,
                "procedure_id": procedure.id,
                "product_id": procedure.product_id.id if procedure.product_id else False,
                "uom_id": procedure.uom_id.id if procedure.uom_id else (
                    procedure.product_id.uom_id.id if procedure.product_id else False
                ),
                "quantity": 1.0,
                "planned_sessions": procedure.default_sessions or 1,
                "planned_duration": procedure.default_duration_min or 0.0,
                "price_unit": procedure.list_price or 0.0,
                "tax_ids": [(6, 0, procedure.tax_ids.ids)] if procedure.tax_ids else [],
                "billing_policy": procedure.billing_policy or "per_plan",
            }
            created |= Plan.create(vals)

        action = self.env.ref(
            "clinic_encounter.action_clinic_encounter_procedure"
        ).read()[0]
        action["domain"] = [("id", "in", created.ids)]
        action["context"] = {
            "default_encounter_id": self.encounter_id.id,
            "default_diagnosis_id": self.diagnosis_id.id,
        }
        return action

