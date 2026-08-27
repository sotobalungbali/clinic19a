{
    "name": "ClinicOne - eCommerce",
    "summary": "Governed online sale and fulfillment for treatments, packages, memberships, bundles and clinic products.",
    "description": """
ClinicOne eCommerce
===================
Official addon 30 of the ClinicOne 39-addon blueprint.

Enterprise responsibilities:
- curated ClinicOne online catalog on top of Odoo 19 Website/eCommerce;
- safe mapping of Treatment, Treatment Bundle, Package, Membership and Product offerings;
- native Odoo cart, checkout, payment, sales-order and invoice lifecycle;
- branch, patient, consent/terms and scheduling-preference capture;
- deterministic downstream fulfillment into Booking, Package Allocation and Membership Contract owners;
- payment-done fulfillment orchestration without duplicating Odoo payment logic;
- operator exception queue, provenance and reversal-required governance.

Ownership boundaries:
- Odoo website_sale owns cart/checkout/sale/payment/invoicing;
- source ClinicOne addons own Treatment, Booking, Package and Membership workflows;
- clinic_ecommerce owns only catalog governance, eCommerce metadata and fulfillment orchestration.
""",
    "version": "19.0.1.0.0",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/eCommerce",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "base_setup",
        "mail",
        "web",
        "website",
        "website_sale",
        "payment",
        "clinic_base",
        "clinic_branch",
        "clinic_patient",
        "clinic_treatment_catalog",
        "clinic_booking",
        "clinic_package",
        "clinic_membership"
    ],
    "data": [
        "security/clinic_ecommerce_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "views/catalog_item_views.xml",
        "views/fulfillment_views.xml",
        "views/sale_order_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/catalog_discovery_wizard_views.xml",
        "views/website_templates.xml",
        "views/menu_views.xml"
    ],
    "assets": {
        "web.assets_frontend": [
            "clinic_ecommerce/static/src/scss/clinic_shop.scss"
        ]
    },
    "demo": []
}
