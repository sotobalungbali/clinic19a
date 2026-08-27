from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    """ClinicOne Indonesia readiness metadata over native invoices/journal entries."""

    _inherit = "account.move"

    clinic_l10n_id_ppn_candidate = fields.Boolean(
        compute="_compute_clinic_l10n_id_readiness",
        store=True,
        index=True,
        string="Clinic PPN Candidate",
    )
    clinic_l10n_id_readiness = fields.Selection(
        [
            ("not_applicable", "Not Applicable"),
            ("attention", "Attention"),
            ("ready", "Ready"),
        ],
        compute="_compute_clinic_l10n_id_readiness",
        store=True,
        index=True,
        string="Indonesia Tax Readiness",
    )
    clinic_l10n_id_readiness_note = fields.Char(
        compute="_compute_clinic_l10n_id_readiness",
        store=True,
        string="Indonesia Tax Readiness Note",
    )

    # Stored readiness fields are searchable for operational review while native Coretax fields remain authoritative.
    @api.depends(
        "company_id.clinic_l10n_id_profile_id",
        "company_id.clinic_l10n_id_profile_id.ppn_sale_tax_ids",
        "company_id.clinic_l10n_id_profile_id.require_partner_tax_identity",
        "invoice_line_ids.tax_ids",
        "partner_id.vat",
        "partner_id.l10n_id_nik",
        "partner_id.l10n_id_buyer_document_number",
        "l10n_id_kode_transaksi",
        "l10n_id_coretax_document",
        "state",
        "move_type",
    )
    def _compute_clinic_l10n_id_readiness(self):
        for move in self:
            profile = move.company_id.clinic_l10n_id_profile_id
            if (
                not profile
                or move.move_type not in ("out_invoice", "out_refund")
                or move.company_id.account_fiscal_country_id.code != "ID"
            ):
                move.clinic_l10n_id_ppn_candidate = False
                move.clinic_l10n_id_readiness = "not_applicable"
                move.clinic_l10n_id_readiness_note = _("Not in ClinicOne Indonesian customer-tax scope.")
                continue

            sale_tax_ids = profile.ppn_sale_tax_ids
            invoice_taxes = move.invoice_line_ids.tax_ids
            candidate = bool(sale_tax_ids & invoice_taxes)
            move.clinic_l10n_id_ppn_candidate = candidate

            if not candidate:
                move.clinic_l10n_id_readiness = "not_applicable"
                move.clinic_l10n_id_readiness_note = _("No configured PPN sales tax is used.")
                continue

            problems = []
            partner = move.commercial_partner_id

            if profile.require_partner_tax_identity and not (
                partner.vat
                or partner.l10n_id_nik
                or partner.l10n_id_buyer_document_number
            ):
                problems.append(_("buyer tax identity"))

            if not move.l10n_id_kode_transaksi:
                problems.append(_("Coretax transaction code"))

            if problems:
                move.clinic_l10n_id_readiness = "attention"
                move.clinic_l10n_id_readiness_note = _("Missing: %s") % ", ".join(problems)
            else:
                move.clinic_l10n_id_readiness = "ready"
                move.clinic_l10n_id_readiness_note = _("Ready for ClinicOne Indonesian tax governance.")

    def action_open_clinic_l10n_id_profile(self):
        self.ensure_one()
        profile = self.company_id.clinic_l10n_id_profile_id
        if not profile:
            raise UserError(_("This company has no Clinic Indonesia Tax Profile."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Indonesia Tax Profile"),
            "res_model": "clinic.l10n.id.tax.profile",
            "view_mode": "form",
            "res_id": profile.id,
        }

    # Navigation delegates to the native Coretax document; no XML generation is implemented in ClinicOne.
    def action_open_native_coretax_document(self):
        self.ensure_one()
        if not self.l10n_id_coretax_document:
            raise UserError(_("This invoice has not been assigned to a native Coretax document."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Coretax E-Faktur Document"),
            "res_model": "l10n_id_efaktur_coretax.document",
            "view_mode": "form",
            "res_id": self.l10n_id_coretax_document.id,
        }


class AccountJournal(models.Model):
    """Reverse traceability from native journal to ClinicOne numbering governance."""

    _inherit = "account.journal"

    clinic_l10n_id_numbering_policy_ids = fields.One2many(
        "clinic.l10n.id.numbering.policy",
        "journal_id",
        string="Clinic Indonesia Numbering Policies",
    )
    clinic_l10n_id_numbering_policy_count = fields.Integer(
        compute="_compute_clinic_l10n_id_numbering_policy_count"
    )

    def _compute_clinic_l10n_id_numbering_policy_count(self):
        for journal in self:
            journal.clinic_l10n_id_numbering_policy_count = len(
                journal.clinic_l10n_id_numbering_policy_ids
            )

    def action_open_clinic_l10n_id_numbering_policies(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Indonesia Numbering Policies"),
            "res_model": "clinic.l10n.id.numbering.policy",
            "view_mode": "list,form",
            "domain": [("journal_id", "=", self.id)],
            "context": {
                "default_journal_id": self.id,
                "default_company_id": self.company_id.id,
                "default_expected_code": self.code,
            },
        }

