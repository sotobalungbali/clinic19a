{
    "name": "ClinicOne - Indonesia Localization",
    "summary": "Enterprise Indonesia tax governance, PPN reporting, Coretax readiness, and invoice numbering controls.",
    "description": """
ClinicOne Indonesia Localization
================================
Indonesia localization governance layer for ClinicOne on Odoo 19 Community Edition.

This addon extends, but does not replace, Odoo's official Indonesian localization.
It consumes the native `l10n_id` fiscal package and the Odoo 19 Coretax e-Faktur
module, then adds ClinicOne-specific governance and auditability.

Enterprise scope:
- company Indonesian tax profile and PKP/NPWP readiness;
- explicit ClinicOne PPN sale/purchase tax scope using native account.tax records;
- persistent PPN input/output tax report snapshots generated from posted
  account.move.line tax lines;
- ClinicOne financial-source traceability from clinic_accounting;
- Coretax readiness/compliance checks using native Indonesian fields and
  native `l10n_id_efaktur_coretax.document`;
- controlled invoice-numbering policy over native account.journal sequence
  prefix, credit-note sequencing, and secure-posted-entry controls;
- multi-company and multi-branch reporting;
- scheduled prior-month PPN snapshots;
- PDF PPN report and Indonesia compliance evidence.

Ownership boundary:
- `l10n_id` owns the Indonesian chart/tax localization;
- `l10n_id_efaktur_coretax` owns Coretax XML/e-Faktur generation;
- `account.move` / `account.move.line` remain the legal accounting ledger;
- `clinic_accounting` remains the accounting governance/reporting owner;
- this addon adds ClinicOne Indonesia-specific tax governance only.
""",
    "version": "19.0.1.0.1",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Localization",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "base_setup",
        "mail",
        "web",
        "account",
        "l10n_id",
        "l10n_id_efaktur_coretax",
        "clinic_base",
        "clinic_audit",
        "clinic_branch",
        "clinic_treatment_catalog",
        "clinic_billing",
        "clinic_ar",
        "clinic_ap",
        "clinic_wallet",
        "clinic_finance",
        "clinic_accounting"
    ],
    "data": [
        "security/clinic_l10n_id_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/cron_data.xml",
        "views/tax_profile_views.xml",
        "views/tax_report_views.xml",
        "views/numbering_policy_views.xml",
        "views/compliance_views.xml",
        "views/integration_views.xml",
        "views/res_config_settings_views.xml",
        "report/tax_report_templates.xml",
        "report/tax_report_report.xml",
        "report/compliance_templates.xml",
        "report/compliance_report.xml",
        "views/menu_views.xml"
    ],
    "demo": [],
}

