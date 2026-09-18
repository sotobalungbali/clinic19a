# -*- coding: utf-8 -*-
{
    "name": "ClinicOne: Inventory & Stock",
    "version": "19.0.1.0.5",
    "summary": "Clinic inventory, clinical stock consumption, adjustments, traceability, and governance",
    "description": """
ClinicOne Inventory & Stock
===========================
Extends Odoo 19 stock/product capabilities with clinic-specific inventory
classification, treatment consumption, patient product traceability,
inventory adjustments, expiry/quality governance, and doctor product rules.

This addon is an existing ClinicOne functional baseline. Changes in this
version are limited to Odoo 19 hardening and enterprise presentation/security
completeness; the business scope is preserved.
    """,
    "author": "PT Dua Empat Tujuh Open Source",
    "website": "https://odoocamp.net",
    "category": "ClinicOne/Inventory",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "contacts",
        "hr",
        "product",
        "product_expiry",
        "uom",
        "stock",
        "portal",
        "clinic_base",
        "clinic_audit",
        "clinic_branch",
        "clinic_staff",
        "clinic_room_device",
        "clinic_treatment_catalog",
        "clinic_patient",
        "clinic_doctor",
        "clinic_queue_room",
    ],
    "data": [
        "security/clinic_inventory_rules.xml",
        "security/ir.model.access.csv",
        "data/clinic_inventory_sequence.xml",
        "views/treatment_product_usage_views.xml",
        "views/inventory_adjustment_views.xml",
        "views/patient_product_history_views.xml",
        "views/doctor_allowed_product_views.xml",
        "views/integration_event_log_views.xml",
        "views/core_inventory_extension_views.xml",
        "views/clinic_inventory_menus.xml",
        "views/templates.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}




