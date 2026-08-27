# -*- coding: utf-8 -*-
{
    "name": "ClinicOne - Clinical Encounter",
    "summary": (
        "Encounter, SOAP, diagnosis, procedure planning/execution, clinical results, "
        "encounter consent, anesthesia, adverse events and checklists"
    ),
    "description": """
ClinicOne Clinical Encounter — Odoo 19 CE
=========================================
Enterprise clinical encounter backbone for ClinicOne.

Preserved functional domains:
- Encounter lifecycle and stage policies
- SOAP documentation and diagnoses
- Procedure catalog, steps, encounter plans and execution sessions
- Execution logs and clinical result documents
- Encounter-specific consent evidence
- Anesthesia workflow from pre-op through recovery
- Adverse-event / near-miss reporting with CAPA
- Checklist templates, instances and scoring
- Audit/evidence records and operational billing/inventory bridges

This Odoo 19 hardening preserves the finished functional baseline while adding
machine-checkable enterprise guardrails, complete UI/security surfaces and
bounded integration resilience.
""",
    "version": "19.0.1.0.0",
    "category": "Healthcare",
    "license": "LGPL-3",
    "author": "ClinicOne",
    "maintainers": ["ClinicOne Team"],
    "website": "https://example.com/clinicone",
    "depends": [
        "base",
        "mail",
        "portal",
        "product",
        "uom",
        "account",
        "web",
        # Direct dependency: active encounter session code creates/opens
        # stock.picking and stock.move records.
        "stock",
        "clinic_base",
        "clinic_branch",
        "clinic_staff",
        "clinic_room_device",
        "clinic_treatment_catalog",
        "clinic_patient",
        "clinic_doctor",
        "clinic_queue_room",
        "clinic_inventory",
        "clinic_booking",
        "clinic_triage_vitals",
        "clinic_consent_legal",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/clinic_encounter_rules.xml",
        "data/clinic_encounter_sequences.xml",
        "data/clinic_encounter_mail_templates.xml",
        "views/encounter_list_search_views.xml",
        "views/encounter_support_forms.xml",
        "views/encounter_primary_forms.xml",
        "views/encounter_actions.xml",
        "views/encounter_wizard_views.xml",
        "report/encounter_report_templates.xml",
        "report/encounter_reports.xml",
        "views/clinic_encounter_menus.xml",
    ],
    "post_init_hook": "_post_init_hook",
    "installable": True,
    "application": True,
}
