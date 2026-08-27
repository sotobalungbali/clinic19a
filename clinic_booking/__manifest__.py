# -*- coding: utf-8 -*-
{
    "name": "ClinicONe: Booking Management",
    "summary": "Appointments & resource scheduling for ClinicONe (patients, doctors, rooms, devices).",
    "version": "19.0.1.0.1",
    "category": "Clinic/Booking",
    "author": "ClinicONe Team",
    "website": "https://clinicone.example.com",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "auto_install": False,

    'description': """
Long description of module's purpose
    """,

    # Penting: gunakan technical name Odoo (huruf kecil) untuk modul core.
    "depends": [
        # Odoo core
        "base", "mail", "contacts", 
        "hr", "account", "product", 
        "sale", "stock", "portal", 
        "website", "uom", "analytic",

        # ClinicOne base (only base to avoid circular deps; other modules integrate via hooks)
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
    ],

    # Always loaded. Security is authoritative; UI is loaded afterwards.
    "data": [
        "security/clinic_booking_rules.xml",
        "security/ir.model.access.csv",
        "data/booking_sequence.xml",
        "data/booking_mail_template.xml",
        "views/booking_core_views.xml",
        "views/booking_master_views.xml",
        "views/booking_schedule_views.xml",
        "views/booking_feedback_views.xml",
        "views/booking_menus.xml",
        "views/templates.xml",
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

