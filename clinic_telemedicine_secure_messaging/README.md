# ClinicOne Telemedicine & Secure Messaging

Version: **19.0.1.0.1**

Official ClinicOne addon: **33 of 39**

Official blueprint:

> Teleconsultation and secure doctor-patient chat system with file sharing.

The addon deliberately separates:
- teleconsultation lifecycle (`clinic.telemedicine.session`);
- secure chat scope (`clinic.telemedicine.thread`);
- immutable messages (`clinic.telemedicine.message`);
- secure file evidence (`clinic.telemedicine.attachment`).

Patient access is through authenticated ClinicOne Portal exact-patient routes.
The base addon does not pretend to provide an external video service or
end-to-end encryption. Manual HTTPS meeting URLs work immediately. Future
`clinic_integration_api` may override a provider-neutral meeting provisioning
hook.

Runtime status is **PENDING** until the target Odoo 19 CE instance successfully
installs the addon and passes patient-isolation, messaging, file-sharing, and
teleconsultation smoke tests.

