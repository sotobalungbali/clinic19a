{
    "name": "ClinicOne - Enterprise KPI Dashboard",
    "summary": "Interactive KPI dashboards for revenue, performance, patient experience, and room utilization.",
    "description": """
ClinicOne Enterprise KPI Dashboard
==================================
Official addon 29 of the ClinicOne 39-addon blueprint.

Blueprint responsibility:
- interactive dashboards for KPIs;
- revenue dashboards;
- performance dashboards;
- room-utilization dashboards.

Architecture:
- consumes the governed normalized reporting layer owned by clinic_reports;
- never re-owns Billing, AR, AP, Finance, Accounting, Booking, Queue,
  Room, Encounter, Post-Care, Feedback or other upstream transactions;
- creates company-scoped dashboard boards, widget configuration,
  immutable dashboard snapshots and snapshot lines;
- supports controlled refresh and optional generation of missing Report Runs;
- supports executive, financial, operational, clinical, room-utilization,
  and patient-experience workspaces;
- includes an Odoo 19 Owl client action plus full backend fallback views.

Enterprise controls:
- company/branch/date scope;
- statusbar workflows;
- smart buttons;
- body actions;
- One2many row actions;
- KPI trend and threshold signaling;
- scheduled refresh;
- multi-company security;
- bounded Codex implementation rules;
- 15-hard-gate Enterprise Development Guardrail.
""",
    "version": "19.0.1.0.1",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Dashboard",
    "application": True,
    "installable": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
    "depends": [
        "base",
        "base_setup",
        "mail",
        "web",
        "contacts",
        "clinic_base",
        "clinic_branch",
        "clinic_reports"
    ],
    "data": [
        "security/clinic_dashboard_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/cron_data.xml",
        "views/dashboard_board_views.xml",
        "views/dashboard_widget_views.xml",
        "views/dashboard_snapshot_views.xml",
        "views/dashboard_snapshot_line_views.xml",
        "views/res_config_settings_views.xml",
        "views/dashboard_client_action.xml",
        "views/menu_views.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "clinic_dashboard/static/src/js/dashboard_client.js",
            "clinic_dashboard/static/src/xml/dashboard_client.xml",
            "clinic_dashboard/static/src/scss/dashboard.scss"
        ]
    },
    "demo": []
}
