# ClinicOne Enterprise KPI Dashboard

Version: **19.0.1.0.0**

Official ClinicOne addon: **29 of 39**

Blueprint responsibility:

> Interactive dashboards for KPIs, revenue, performance, and room utilization.

`clinic_dashboard` is intentionally a **consumer** of the normalized
`clinic_reports` layer:

- `clinic.report.definition`
- `clinic.report.run`
- `clinic.report.metric`
- `clinic.report.detail`

It does not recompute or own transactional accounting/clinical logic.

Built-in company dashboards:

1. Executive Overview
2. Financial Performance
3. Operations Performance
4. Clinical Performance
5. Room Utilization
6. Patient Experience

Runtime status remains **PENDING** until activation and smoke tests succeed on
the target Odoo 19 CE database.


