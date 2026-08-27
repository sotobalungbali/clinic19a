
# -*- coding: utf-8 -*-
{
    "name": "Clinic Base",
    "summary": "Foundation module for clinic domain objects and features",
    "description": """
Core building blocks for clinic apps (models, security, mail subtypes, etc.)

Read full description in static/description/index.html.
""",
    "version": "19.0.1.0.0",
    "category": "ClinicOne",
    'author': "IG @odoocamp",
    'website': "https://www.247opensource.com",
    "application": True,
    "installable": True,

    # Minimal dependencies. Tambah jika model Anda membutuhkan modul lain.
    "depends": [
        "base",
        "mail",
    ],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}


