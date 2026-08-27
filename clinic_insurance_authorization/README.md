# ClinicOne Insurance Authorization

Version: **19.0.1.0.1**

Official ClinicOne addon: **25 of 39**

Blueprint responsibility:
> Handles insurance policies, pre-authorization, and claim processing.

The installed Clinic Billing addon already owns the historical
`clinic.insurance.claim` and `clinic.insurance.claim.line` models. This addon
preserves that frozen ownership and extends those models with enterprise Policy,
Authorization and payer-adjudication integration.

Runtime status: **PENDING** until installation and smoke tests on the user's
Odoo 19 CE environment.

