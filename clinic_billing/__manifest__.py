# -*- coding: utf-8 -*-
{
    "name": "ClinicOne - Billing",
    "summary": "Enterprise clinical billing, invoicing, payment orchestration, insurance, vouchers, commissions, and ClinicOne traceability.",
    "description": """
ClinicOne Billing
=================
Enterprise billing layer for ClinicOne on Odoo 19 Community Edition.

Key capabilities
----------------
* Clinical billing invoices and detailed service/product lines
* Accounting invoice generation and synchronization
* Split payment orchestration using Odoo 19 account.payment
* Discount and voucher engines
* Insurance claim lifecycle
* Doctor/provider commission calculation and settlement
* Gateway transaction traceability
* Membership/wallet soft integration without forward dependency
* Traceability to patient, doctor, booking, encounter, care plan, package, eMAR,
  treatment catalog, room/device and inventory consumption
* Multi-company security and enterprise-grade UI
""",
    "version": "19.0.3.0.2",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Finance",
    "application": True,
    "auto_install": False,
    "installable": True,
    "depends": [
        "base",
        "mail",
        "contacts",
        "account",
        "product",
        "stock",
        "uom",
        "hr",
        "clinic_base",
        "clinic_staff",
        "clinic_room_device",
        "clinic_treatment_catalog",
        "clinic_patient",
        "clinic_doctor",
        "clinic_inventory",
        "clinic_booking",
        "clinic_encounter",
        "clinic_emar",
        "clinic_care_plan",
        "clinic_package",
    ],
    "data": [
        "security/clinic_billing_security.xml",
        "security/ir.model.access.csv",
        "data/billing_sequences.xml",
        "data/billing_cron.xml",
        "views/billing_invoice_views.xml",
        "views/billing_payment_views.xml",
        "views/billing_discount_views.xml",
        "views/billing_voucher_views.xml",
        "views/billing_insurance_views.xml",
        "views/billing_commission_views.xml",
        "views/billing_gateway_views.xml",
        "views/billing_membership_views.xml",
        "views/billing_traceability_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu_views.xml",
    ],
    "demo": [],
}
