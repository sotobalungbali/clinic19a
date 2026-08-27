{
    "name": "ClinicOne - Marketing",
    "summary": "Enterprise patient campaigns, promotions, audience segmentation, email marketing, and governed WhatsApp outreach.",
    "description": """
ClinicOne Marketing
===================
Official addon 32 of the ClinicOne 39-addon blueprint.

Official blueprint responsibility:
- manages marketing campaigns;
- manages promotions;
- communicates with patients through email and WhatsApp.

Architecture:
- Odoo 19 Email Marketing (`mass_mailing`) remains the owner of email delivery,
  exclusion lists, bounce/open/click/reply tracking, and mailing statistics;
- ClinicOne owns patient segmentation, clinic-specific communication consent,
  campaign orchestration, promotion presentation, recipient snapshots, and
  governed WhatsApp handoff;
- pricing, vouchers, packages, memberships, storefront, booking, billing,
  feedback, patient identity, and branch policies remain owned by their
  existing ClinicOne addons;
- future `clinic_integration_api` may override the WhatsApp transport hook but
  is not a dependency;
- future `clinic_audit` and `clinic_analytics` remain downstream concerns.

Enterprise controls:
- structured patient segments;
- explicit email / WhatsApp marketing preferences;
- branch-aware campaign governance;
- reusable promotional offers linked to owner pricing/voucher/eCommerce models;
- immutable audience snapshots after campaign readiness;
- native Odoo Email Marketing campaign generation and queueing;
- WhatsApp queue with safe phone normalization and manual/provider-neutral handoff;
- campaign delivery synchronization and management KPIs;
- 16 hard gates including Database Identifier & ORM Naming Safety.
""",
    "version": "19.0.1.0.1",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Marketing",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "base_setup",
        "mail",
        "web",
        "contacts",
        "mass_mailing",
        "website",
        "clinic_base",
        "clinic_branch",
        "clinic_patient",
        "clinic_treatment_catalog",
        "clinic_booking",
        "clinic_package",
        "clinic_membership",
        "clinic_billing",
        "clinic_feedback",
        "clinic_ecommerce",
        "clinic_portal"
    ],
    "data": [
        "security/clinic_marketing_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/cron_data.xml",
        "views/marketing_preference_views.xml",
        "views/marketing_segment_views.xml",
        "views/marketing_promotion_views.xml",
        "views/marketing_recipient_views.xml",
        "views/marketing_message_views.xml",
        "views/marketing_campaign_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu_views.xml"
    ],
    "demo": []
}

