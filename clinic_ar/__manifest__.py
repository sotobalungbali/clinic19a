# -*- coding: utf-8 -*-
{
    "name": "ClinicOne - Accounts Receivable",
    "summary": "Enterprise accounts receivable, collections, aging, allocations, statements, and ClinicOne billing traceability.",
    "description": '''
ClinicOne Accounts Receivable
=============================
Enterprise AR subledger and collection layer for ClinicOne on Odoo 19 Community Edition.

Core capabilities
-----------------
* Billing-to-AR synchronization without duplicate accounting invoices
* Manual AR invoice capability backed by standard Odoo customer invoices
* Customer receipts backed by standard Odoo account.payment
* Partial payment and open-credit allocation
* Credit limits, credit holds and overdue posting guards
* Follow-up / dunning levels and auditable reminder history
* Customer statements and aging buckets
* Traceability to Patient, Booking, Treatment Session, Membership and Billing
* Multi-company security and enterprise-grade Search/List/Form UI
* Integration event outbox for downstream Wallet, AP, Reports and Analytics
''',
    "version": "19.0.3.0.2",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Finance",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "mail",
        "contacts",
        "account",
        "product",
        "uom",
        "sale",
        "hr",
        "clinic_base",
        "clinic_audit",
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
        "clinic_encounter",
        "clinic_emar",
        "clinic_imaging",
        "clinic_care_plan",
        "clinic_package",
        "clinic_membership",
        "clinic_billing",
        "clinic_treatment_session",
    ],
    "data": [
        "security/clinic_ar_security.xml",
        "security/ir.model.access.csv",
        "data/ar_sequences.xml",
        "data/ar_cron.xml",
        "views/ar_invoice_views.xml",
        "views/ar_payment_views.xml",
        "views/ar_allocation_views.xml",
        "views/ar_followup_views.xml",
        "views/ar_statement_views.xml",
        "views/ar_integration_event_views.xml",
        "views/res_partner_views.xml",
        "views/account_move_views.xml",
        "views/billing_bridge_views.xml",
        "data/optional_view_bridge.xml",
        "views/res_config_settings_views.xml",
        "views/menu_views.xml",
    ],
    "demo": [],
}

