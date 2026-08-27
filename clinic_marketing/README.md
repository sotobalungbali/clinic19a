# ClinicOne Marketing

Version: **19.0.1.0.1**

Official ClinicOne addon: **32 of 39**

Official blueprint:

> Manages campaigns, promotions, and communication with patients via email/WhatsApp.

Primary enterprise objects:

- `clinic.marketing.preference`
- `clinic.marketing.segment`
- `clinic.marketing.promotion`
- `clinic.marketing.campaign`
- `clinic.marketing.recipient`
- `clinic.marketing.message`

Email is delegated to Odoo 19 Email Marketing. WhatsApp is queued as governed
patient outreach with a provider-neutral transport hook and a safe manual
WhatsApp deep-link fallback. Future `clinic_integration_api` can override the
transport hook without changing campaign ownership.

Runtime status remains **PENDING** until activation and sending/security smoke
tests succeed on the target Odoo 19 CE database.

