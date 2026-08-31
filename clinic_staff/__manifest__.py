

{
    'name': "clinic_staff",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '19.0.1.0.1',

    # any module necessary for this one to work correctly
    "depends": [
        # Odoo core
        "base", "mail", "contacts", "hr", "account", "product",

        # ClinicOne base
        "clinic_base", "clinic_branch", "clinic_audit",

        # Integration set aligned with clinic_patient (23 related modules)
        # "clinic_doctor", "clinic_booking",
        # "clinic_treatment", "clinic_billing", "clinic_ar",
        # "clinic_ap", "clinic_finance",
        # "clinic_accounting", "clinic_inventory",
        # "clinic_ecommerce", "clinic_membership",
        # "clinic_feedback", "clinic_reports",
        # "clinic_dashboard", "clinic_wallet",
        # "clinic_package", "clinic_pricing",
        # "clinic_room_device", "clinic_hr",
        # "clinic_portal", "clinic_marketing",
        # "clinic_l10n_id", "clinic_audit",

        # Additional cross-module clinical integrations for Staff
        # "clinic_patient",
        # "clinic_triage",
        # "clinic_encounter",
        # "clinic_procedure",
        # "clinic_emar",
        # "clinic_postcare",
        # "clinic_incident",
        # "clinic_telemedicine",
        # "clinic_consent",
        # "clinic_imaging",
        # "clinic_careplan",
        # If your Queue is a separate module from room/device, include it:
        # "clinic_queue",
    ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}


