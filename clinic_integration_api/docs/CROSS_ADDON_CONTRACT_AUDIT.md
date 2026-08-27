# CROSS-ADDON CONTRACT AUDIT — HARD GATES 2–4

The latest ClinicOne baseline was audited before implementation.

## Preserved extension seams

`clinic_marketing` owns WhatsApp message workflow and intentionally exposes:

- `clinic.marketing.message._dispatch_via_gateway()`

`clinic_telemedicine_secure_messaging` owns secure session lifecycle and intentionally exposes:

- `clinic.telemedicine.session._provision_meeting_via_provider()`

`clinic_billing` owns payment state/accounting and its `process_webhook()` calls:

- `_match_tx_from_payload(provider, payload)`

The Billing matcher was absent from the upstream Billing owner and is supplied here as a provider-specific additive bridge. This addon does **not** own invoice posting, payment creation, reconciliation, marketing campaign intent, or telemedicine session workflow.

## Canonical ID normalization

`booking.booking.patient_id` is historically a `res.partner`, while the public patient identity is `clinic.patient`. The API accepts/returns canonical Clinic Patient IDs and translates them to the Booking partner link internally.

## Resource ownership

The API uses fixed adapters for upstream owner models. It creates no shadow models such as `clinic.api.patient`, `clinic.api.booking`, or `clinic.api.invoice`.
