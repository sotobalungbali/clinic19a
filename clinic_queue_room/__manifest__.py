
# -*- coding: utf-8 -*-
{
    "name": "ClinicOne: Queue & Room Operations",
    "summary": "Clinical queue, token, visit, ticket, room assignment, SLA and doctor queue operations",
    "description": """
ClinicOne Queue & Room Operations
=================================
Operational queue and room-routing layer for ClinicOne. This addon preserves
the existing functional baseline while hardening it for Odoo 19 Community
Edition and completing the enterprise presentation/security layer.
    """,
    "version": "19.0.1.0.1",
    "category": "ClinicOne/Operations",
    "author": "PT Dua Empat Tujuh Open Source",
    "website": "https://odoocamp.net",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "contacts",
        "hr",
        "account",
        "product",
        "sale",
        "clinic_base",
        "clinic_room_device",
        "clinic_doctor",
        "clinic_treatment_catalog",
        "clinic_audit",
        "clinic_branch",
        "clinic_staff",
        "clinic_patient",
    ],
    "data": [
        "security/clinic_queue_room_rules.xml",
        "security/ir.model.access.csv",
        "data/clinic_queue_room_sequence.xml",
        "views/queue_stage_channel_views.xml",
        "views/queue_token_views.xml",
        "views/queue_views.xml",
        "views/room_assignment_views.xml",
        "views/queue_event_views.xml",
        "views/queue_visit_ticket_views.xml",
        "views/hr_doctor_queue_views.xml",
        "views/clinic_queue_room_menus.xml",
        "views/templates.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "application": True,
    "installable": True,
}
