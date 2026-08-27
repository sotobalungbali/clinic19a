from lxml import etree

from odoo.tests.common import TransactionCase


PERSISTENT_MODELS = (
    "clinic.l10n.id.tax.profile",
    "clinic.l10n.id.tax.report",
    "clinic.l10n.id.tax.report.line",
    "clinic.l10n.id.numbering.policy",
    "clinic.l10n.id.compliance.run",
    "clinic.l10n.id.compliance.line",
)


class TestClinicL10nIdEnterprise(TransactionCase):

    def test_01_owned_models_exist(self):
        for model in PERSISTENT_MODELS:
            self.assertIn(model, self.env.registry)

    def test_02_company_mixin_exists(self):
        self.assertIn("clinic.l10n.id.company.mixin", self.env.registry)

    def test_03_native_indonesia_localization_module_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "l10n_id")], limit=1)
        self.assertEqual(module.state, "installed")

    def test_04_native_coretax_module_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "l10n_id_efaktur_coretax")], limit=1)
        self.assertEqual(module.state, "installed")

    def test_05_clinic_accounting_dependency_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "clinic_accounting")], limit=1)
        self.assertEqual(module.state, "installed")

    def test_06_coretax_document_model_exists(self):
        self.assertIn("l10n_id_efaktur_coretax.document", self.env.registry)

    def test_07_coretax_product_code_model_exists(self):
        self.assertIn("l10n_id_efaktur_coretax.product.code", self.env.registry)

    def test_08_coretax_uom_code_model_exists(self):
        self.assertIn("l10n_id_efaktur_coretax.uom.code", self.env.registry)

    def test_09_partner_indonesia_fields_exist(self):
        partner = self.env["res.partner"]
        for field in (
            "l10n_id_tku",
            "l10n_id_buyer_document_type",
            "l10n_id_buyer_document_number",
            "l10n_id_nik",
            "l10n_id_pkp",
            "l10n_id_kode_transaksi",
        ):
            self.assertIn(field, partner._fields)

    def test_10_move_coretax_fields_exist(self):
        move = self.env["account.move"]
        for field in (
            "l10n_id_kode_transaksi",
            "l10n_id_coretax_document",
            "l10n_id_coretax_efaktur_available",
        ):
            self.assertIn(field, move._fields)

    def test_11_product_coretax_code_exists(self):
        self.assertIn("l10n_id_product_code", self.env["product.template"]._fields)

    def test_12_uom_coretax_code_exists(self):
        self.assertIn("l10n_id_uom_code", self.env["uom.uom"]._fields)

    def test_13_native_journal_sequence_prefix_exists(self):
        self.assertIn("code", self.env["account.journal"]._fields)

    def test_14_native_credit_note_sequence_exists(self):
        self.assertIn("refund_sequence", self.env["account.journal"]._fields)

    def test_15_native_secure_entry_setting_exists(self):
        self.assertIn("restrict_mode_hash_table", self.env["account.journal"]._fields)

    def test_16_native_sequence_override_regex_exists(self):
        self.assertIn("sequence_override_regex", self.env["account.journal"]._fields)

    def test_17_native_tax_line_fields_exist(self):
        line = self.env["account.move.line"]
        for field in ("tax_line_id", "tax_base_amount", "balance", "tax_ids"):
            self.assertIn(field, line._fields)

    def test_18_native_tax_country_field_exists(self):
        self.assertIn("country_id", self.env["account.tax"]._fields)

    def test_19_native_tax_use_field_exists(self):
        self.assertIn("type_tax_use", self.env["account.tax"]._fields)

    def test_20_accounting_source_bridge_exists_on_move(self):
        self.assertIn("clinic_accounting_source", self.env["account.move"]._fields)

    def test_21_accounting_source_bridge_exists_on_move_line(self):
        self.assertIn("clinic_accounting_source", self.env["account.move.line"]._fields)

    def test_22_branch_bridge_exists_on_move(self):
        self.assertIn("branch_id", self.env["account.move"]._fields)

    def test_23_branch_bridge_exists_on_move_line(self):
        self.assertIn("branch_id", self.env["account.move.line"]._fields)

    def test_24_tax_profile_company_contract(self):
        self.assertEqual(
            self.env["clinic.l10n.id.tax.profile"]._fields["company_id"].comodel_name,
            "res.company",
        )

    def test_25_tax_profile_sale_tax_contract(self):
        self.assertEqual(
            self.env["clinic.l10n.id.tax.profile"]._fields["ppn_sale_tax_ids"].comodel_name,
            "account.tax",
        )

    def test_26_tax_profile_purchase_tax_contract(self):
        self.assertEqual(
            self.env["clinic.l10n.id.tax.profile"]._fields["ppn_purchase_tax_ids"].comodel_name,
            "account.tax",
        )

    def test_27_tax_profile_workflow(self):
        states = dict(self.env["clinic.l10n.id.tax.profile"]._fields["state"].selection)
        for state in ("draft", "validated", "active", "archived"):
            self.assertIn(state, states)

    def test_28_ppn_report_workflow(self):
        states = dict(self.env["clinic.l10n.id.tax.report"]._fields["state"].selection)
        for state in ("draft", "generated", "locked"):
            self.assertIn(state, states)

    def test_29_ppn_report_line_links_native_move(self):
        self.assertEqual(
            self.env["clinic.l10n.id.tax.report.line"]._fields["move_id"].comodel_name,
            "account.move",
        )

    def test_30_ppn_report_line_links_native_tax(self):
        self.assertEqual(
            self.env["clinic.l10n.id.tax.report.line"]._fields["tax_id"].comodel_name,
            "account.tax",
        )

    def test_31_ppn_report_line_links_coretax_document(self):
        self.assertEqual(
            self.env["clinic.l10n.id.tax.report.line"]._fields["coretax_document_id"].comodel_name,
            "l10n_id_efaktur_coretax.document",
        )

    def test_32_ppn_report_source_scope_includes_clinic_sources(self):
        selection = dict(self.env["clinic.l10n.id.tax.report"]._fields["source_scope"].selection)
        for value in ("clinic_only", "finance", "billing", "ar", "ap", "wallet", "adjustment", "mixed", "other"):
            self.assertIn(value, selection)

    def test_33_numbering_policy_links_native_journal(self):
        self.assertEqual(
            self.env["clinic.l10n.id.numbering.policy"]._fields["journal_id"].comodel_name,
            "account.journal",
        )

    def test_34_numbering_policy_workflow(self):
        states = dict(self.env["clinic.l10n.id.numbering.policy"]._fields["state"].selection)
        for state in ("draft", "validated", "applied", "archived"):
            self.assertIn(state, states)

    def test_35_compliance_workflow(self):
        states = dict(self.env["clinic.l10n.id.compliance.run"]._fields["state"].selection)
        for state in ("draft", "generated", "reviewed", "locked"):
            self.assertIn(state, states)

    def test_36_compliance_severity_levels(self):
        selection = dict(self.env["clinic.l10n.id.compliance.line"]._fields["severity"].selection)
        for value in ("blocking", "warning", "info"):
            self.assertIn(value, selection)

    def test_37_company_settings_exist(self):
        company = self.env["res.company"]
        self.assertIn("clinic_l10n_id_profile_id", company._fields)
        self.assertIn("clinic_l10n_id_auto_monthly_tax_report", company._fields)

    def test_38_move_readiness_fields_exist(self):
        move = self.env["account.move"]
        for field in (
            "clinic_l10n_id_ppn_candidate",
            "clinic_l10n_id_readiness",
            "clinic_l10n_id_readiness_note",
        ):
            self.assertIn(field, move._fields)

    def test_39_move_readiness_is_searchable_stored(self):
        move = self.env["account.move"]
        self.assertTrue(move._fields["clinic_l10n_id_ppn_candidate"].store)
        self.assertTrue(move._fields["clinic_l10n_id_readiness"].store)

    def test_40_journal_numbering_reverse_link_exists(self):
        journal = self.env["account.journal"]
        self.assertIn("clinic_l10n_id_numbering_policy_ids", journal._fields)
        self.assertIn("clinic_l10n_id_numbering_policy_count", journal._fields)

    def test_41_security_groups_exist(self):
        for xmlid in (
            "clinic_l10n_id.group_clinic_l10n_id_user",
            "clinic_l10n_id.group_clinic_l10n_id_accountant",
            "clinic_l10n_id.group_clinic_l10n_id_approver",
            "clinic_l10n_id.group_clinic_l10n_id_manager",
        ):
            self.assertTrue(self.env.ref(xmlid))

    def test_42_accountant_implies_clinic_accounting_accountant(self):
        group = self.env.ref("clinic_l10n_id.group_clinic_l10n_id_accountant")
        self.assertIn(
            self.env.ref("clinic_accounting.group_clinic_accounting_accountant"),
            group.implied_ids,
        )

    def test_43_approver_implies_clinic_accounting_approver(self):
        group = self.env.ref("clinic_l10n_id.group_clinic_l10n_id_approver")
        self.assertIn(
            self.env.ref("clinic_accounting.group_clinic_accounting_approver"),
            group.implied_ids,
        )

    def test_44_manager_implies_clinic_accounting_manager(self):
        group = self.env.ref("clinic_l10n_id.group_clinic_l10n_id_manager")
        self.assertIn(
            self.env.ref("clinic_accounting.group_clinic_accounting_manager"),
            group.implied_ids,
        )

    def test_45_search_views_follow_clinicone_odoo19_contract(self):
        xmlids = (
            "clinic_l10n_id.view_l10n_id_tax_profile_search",
            "clinic_l10n_id.view_l10n_id_tax_report_search",
            "clinic_l10n_id.view_l10n_id_tax_report_line_search",
            "clinic_l10n_id.view_l10n_id_numbering_search",
            "clinic_l10n_id.view_l10n_id_compliance_search",
            "clinic_l10n_id.view_l10n_id_compliance_line_search",
        )
        for xmlid in xmlids:
            view = self.env.ref(xmlid)
            arch = view.arch_db
            if hasattr(arch, "get"):
                arch = arch.get(self.env.lang) or next(iter(arch.values()), "")
            root = etree.fromstring((arch or "").encode())
            self.assertEqual(root.tag, "search")
            self.assertFalse(root.attrib)
            for group in root.xpath("./group"):
                self.assertFalse(group.attrib)

    def test_46_every_owned_model_has_search_view(self):
        for model in PERSISTENT_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "search")], limit=1),
                model,
            )

    def test_47_every_owned_model_has_list_view(self):
        for model in PERSISTENT_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "list")], limit=1),
                model,
            )

    def test_48_every_owned_model_has_form_view(self):
        for model in PERSISTENT_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "form")], limit=1),
                model,
            )

    def test_49_ppn_analysis_views_exist(self):
        self.assertTrue(self.env.ref("clinic_l10n_id.view_l10n_id_tax_report_pivot"))
        self.assertTrue(self.env.ref("clinic_l10n_id.view_l10n_id_tax_report_graph"))

    def test_50_ppn_pdf_report_exists(self):
        self.assertTrue(self.env.ref("clinic_l10n_id.action_report_ppn_tax"))

    def test_51_compliance_pdf_report_exists(self):
        self.assertTrue(self.env.ref("clinic_l10n_id.action_report_compliance"))

    def test_52_monthly_ppn_cron_exists(self):
        self.assertTrue(self.env.ref("clinic_l10n_id.cron_clinic_l10n_id_monthly_ppn"))

    def test_53_settings_action_is_local(self):
        action = self.env.ref("clinic_l10n_id.action_clinic_l10n_id_settings")
        self.assertEqual(action.res_model, "res.config.settings")
        self.assertIn("clinic_l10n_id", action.context or "")

    def test_54_native_coretax_action_exists(self):
        action = self.env.ref("clinic_l10n_id.action_l10n_id_native_coretax_documents")
        self.assertEqual(action.res_model, "l10n_id_efaktur_coretax.document")

    def test_55_native_tax_action_exists(self):
        action = self.env.ref("clinic_l10n_id.action_l10n_id_native_taxes")
        self.assertEqual(action.res_model, "account.tax")

    def test_56_ppn_line_model_is_generated_child(self):
        report = self.env["clinic.l10n.id.tax.report"]
        line = self.env["clinic.l10n.id.tax.report.line"]
        self.assertEqual(report._fields["line_ids"].comodel_name, line._name)
        self.assertEqual(line._fields["report_id"].comodel_name, report._name)

    def test_57_compliance_line_model_is_generated_child(self):
        run = self.env["clinic.l10n.id.compliance.run"]
        line = self.env["clinic.l10n.id.compliance.line"]
        self.assertEqual(run._fields["line_ids"].comodel_name, line._name)
        self.assertEqual(line._fields["run_id"].comodel_name, run._name)

    def test_58_native_coretax_document_owns_xml_generation(self):
        model = self.env["l10n_id_efaktur_coretax.document"]
        self.assertTrue(hasattr(model, "action_download"))
        self.assertTrue(hasattr(model, "_generate_xml"))

    def test_59_tax_report_generation_uses_native_tax_lines(self):
        model = self.env["clinic.l10n.id.tax.report"]
        self.assertTrue(hasattr(model, "_tax_line_domain"))
        self.assertTrue(hasattr(model, "_prepare_report_lines"))

    def test_60_clinic_localization_does_not_replace_native_tax_engine(self):
        self.assertNotIn("clinic.l10n.id.tax", self.env.registry)
        self.assertNotIn("clinic.l10n.id.efaktur.document", self.env.registry)

    def test_61_numbering_compliant_is_searchable_stored(self):
        field = self.env["clinic.l10n.id.numbering.policy"]._fields["compliant"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

