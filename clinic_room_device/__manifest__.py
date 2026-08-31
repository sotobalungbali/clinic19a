
# -*- coding: utf-8 -*-
{
    "name": "ClinicOne - Clinical Room & Device Management",
    "summary": "Manage clinic rooms, medical devices, assignments, availability, sessions, and movement history.",
    "description": """
ClinicOne - Clinical Room & Device Management
=============================================
Enterprise room and device management for ClinicOne, preserving the existing
functional baseline while hardening it for Odoo 19 Community Edition.
    """,
    "version": "19.0.1.0.1",
    "author": "ClinicOne Project",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "Healthcare/Clinic",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "web",
        "mail",
        "contacts",
        "hr",
        "product",
        "stock",
        "maintenance",
        "uom",
        "clinic_base",
    ],
    "data": [
        "security/clinic_room_device_rules.xml",
        "security/ir.model.access.csv",
        "data/clinic_room_device_sequence.xml",
        "views/room_views.xml",
        "views/device_views.xml",
        "views/assignment_views.xml",
        "views/availability_views.xml",
        "views/movement_views.xml",
        "views/room_session_views.xml",
        "views/clinic_room_device_menus.xml",
        "views/views.xml",
        "views/templates.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
}
