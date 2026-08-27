# -*- coding: utf-8 -*-
{
    "name": "ClinicOne - Predictive Analytics",
    "summary": "Governed KPI snapshots, forecasting, retention cohorts, and actionable analytics insights.",
    "description": '''
ClinicOne Predictive Analytics
==============================
Official addon 39 of 39 for ClinicOne on Odoo 19 Community Edition.

Responsibilities
----------------
* governed KPI catalog and scoped analytical snapshots;
* deterministic revenue, demand, retention and risk forecasting;
* patient retention cohorts without copying patient PII into analytics tables;
* actionable insight workflow;
* scheduled analytics execution;
* integration with Clinic Reports, Clinic Dashboard, Integration API and Audit;
* fixed source adapters rather than arbitrary model/domain execution;
* multi-company and branch-aware analytics segregation;
* Enterprise Development Guardrail HARD GATE 0-15.

Forecast methods are intentionally transparent baseline methods:
Naive, Moving Average and Linear Trend. The addon does not claim opaque AI/ML
accuracy and does not introduce an external ML dependency.
''',
    "version": "19.0.1.0.0",
    "category": "ClinicOne/Analytics",
    "author": "IG @odoocamp",
    "website": "https://www.247opensource.com",
    "license": "AGPL-3",
    "depends": [
        "base",
        "base_setup",
        "mail",
        "web",
        "contacts",
        "clinic_base",
        "clinic_branch",
        "clinic_patient",
        "clinic_booking",
        "clinic_billing",
        "clinic_membership",
        "clinic_wallet",
        "clinic_feedback",
        "clinic_reports",
        "clinic_dashboard",
        "clinic_marketing",
        "clinic_incident_event",
        "clinic_quality",
        "clinic_integration_api",
        "clinic_audit"
    ],
    "data": [
        "security/clinic_analytics_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/kpi_data.xml",
        "data/integration_event_type_data.xml",
        "data/cron_data.xml",
        "views/kpi_views.xml",
        "views/snapshot_views.xml",
        "views/snapshot_line_views.xml",
        "views/forecast_views.xml",
        "views/forecast_point_views.xml",
        "views/cohort_views.xml",
        "views/insight_views.xml",
        "views/schedule_views.xml",
        "views/integration_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu_views.xml"
    ],
    "installable": True,
    "application": True,
    "auto_install": False
}
