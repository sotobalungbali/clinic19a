# Odoo 19 Portal / Telemedicine API Audit

Addon 33 reuses the Odoo 19 portal extension pattern:
- subclasses the existing ClinicOne `ClinicPatientPortal`;
- extends `_prepare_home_portal_values(counters)`;
- uses authenticated `auth="user"` routes;
- uses `portal_pager`;
- injects cards into `portal.portal_my_home`;
- uses `portal.portal_docs_entry`;
- uses `portal.portal_layout`.

The existing Clinic Portal profile remains the patient identity/access owner.

Secure communication-specific routes are intentionally `readonly=False`
because they may record:
- patient join evidence;
- patient read evidence;
- new secure Thread;
- new Message;
- new Attachment.

The generic Portal counter hook is read-only-safe and never creates/activates a
Clinic Portal Profile.

Meeting-provider provisioning remains provider-neutral. No external
conferencing API is required by the base addon.

