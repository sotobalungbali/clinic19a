# -*- coding: utf-8 -*-
{
    "name": "ClinicOne - Consent & Legal Forms",
    "summary": "Enterprise consent governance, signatures, legal evidence, and cross-ClinicOne enforcement.",
    "description": """
ClinicOne Consent & Legal Forms for Odoo 19 Community Edition.

Capabilities include:
- Governed consent templates with legal versioning and integrity checksum
- Patient consent lifecycle and signature evidence
- Append-only style signature ledger and attachment confidentiality
- Portal-safe consent viewing
- Treatment, appointment, patient-contact, and invoice consent integration
- Multi-company ORM security and installation-resilient optional UI bridges
    """,
    "version": "19.0.1.1.0",
    "category": "Medical",
    "sequence": 170,
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "contacts",
        "hr",
        "account",
        "product",
        "portal",
        "clinic_base",
        "clinic_patient",
        "clinic_doctor",
        "clinic_booking",
        "clinic_treatment_catalog",
        "clinic_inventory",
        "clinic_room_device",
        "clinic_queue_room",
        "clinic_audit",
    ],
    "data": [
        "security/clinic_consent_legal_rules.xml",
        "security/ir.model.access.csv",
        "data/consent_sequences.xml",
        "views/consent_template_views.xml",
        "views/consent_form_views.xml",
        "views/consent_signature_views.xml",
        "views/consent_attachment_views.xml",
        "views/clinic_consent_legal_menus.xml",
        "views/templates.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
