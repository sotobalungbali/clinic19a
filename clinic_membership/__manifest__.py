

# -*- coding: utf-8 -*-
{
    "name": "ClinicOne - Membership",
    "summary": "Enterprise patient memberships, benefit entitlements, loyalty points, vouchers, holds, and clinical usage traceability.",
    "description": """
ClinicOne Membership
====================
Enterprise membership and loyalty engine for ClinicOne on Odoo 19 Community Edition.

Core capabilities
-----------------
* Membership plan catalog and governed publishing lifecycle
* Patient/member contracts with price snapshots, renewal and hold/freeze workflows
* Immutable contract-benefit entitlement snapshots
* Treatment/product/doctor scoped discounts, quotas, priority and join vouchers
* Auditable benefit usage ledger with Booking/Encounter/Care Plan/Package/eMAR traceability
* Voucher lifecycle and redemption governance
* Loyalty points earn/spend/adjust/expire/reverse ledger
* Patient and contact portfolio integration
* Booking eligibility and pricing preview hooks
* Soft downstream integration events for Billing, AR, Wallet, Portal, Marketing and Analytics
* Multi-company security and enterprise-grade Search/List/Form UI
""",
    "version": "19.0.3.0.5",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Commercial",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "mail",
        "contacts",
        "product",
        "uom",
        "sale",
        "account",
        "stock",
        "portal",
        "website",
        "analytic",
        "clinic_base",
        "clinic_audit",
        "clinic_branch",
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
        "clinic_referral",
        "clinic_treatment_session",
    ],
    "data": [
        "security/clinic_membership_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/cron_data.xml",
        "views/plan_views.xml",
        "views/benefit_views.xml",
        "views/contract_views.xml",
        "views/contract_benefit_views.xml",
        "views/usage_views.xml",
        "views/voucher_views.xml",
        "views/point_tx_views.xml",
        "views/hold_views.xml",
        "views/integration_event_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/contract_renew_wizard_views.xml",
        "wizard/hold_request_wizard_views.xml",
        "wizard/point_adjust_wizard_views.xml",
        "data/optional_view_bridge.xml",
        "views/menu_views.xml",
    ],
    "demo": [],
}

