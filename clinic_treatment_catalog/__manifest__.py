{
    'name': "ClinicOne - Treatment Catalog",

    'summary': "Enterprise treatment catalog, bundles, pricing rules, and consent integration",

    'description': """
ClinicOne treatment master data, treatment bundles, attributes, pricing rules,
and consent integration for the clinical service catalog.
    """,

    'author': "ClinicOne",

    'category': 'Services/Healthcare',
    'version': '19.0.1.0.2',

    # Hard dependencies required by the active Odoo 19 runtime contract.
    # Dormant bridges/engines remain soft-coupled and are not activated here.
    "depends": [
        "base",
        "mail",
        "product",
        "uom",
        "contacts",
        "account",
        "clinic_base",
        "clinic_audit",
        "clinic_branch",
        "clinic_staff",
        "clinic_room_device",
        # Active consent integration already reads clinic.patient.
        # Make the existing runtime contract explicit instead of relying on install order.
        "clinic_patient",
    ],

    # Always loaded
    'data': [
        'security/clinic_treatment_catalog_security.xml',
        'security/ir.model.access.csv',
        'data/treatment_sequences.xml',
        'views/treatment_views.xml',
        'views/treatment_master_views.xml',
        'views/treatment_attribute_views.xml',
        'views/treatment_bundle_views.xml',
        'views/treatment_pricelist_views.xml',
        'views/consent_views.xml',
        'views/treatment_catalog_menus.xml',
        'views/templates.xml',
    ],
    'post_init_hook': '_post_init_hook',

    # Loaded only in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

