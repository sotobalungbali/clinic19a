def post_init_hook(env):
    """Seed Portal Profiles for existing patient portal users only.

    The hook never grants portal access. Native Odoo `portal.wizard` remains the
    owner of invitation, access grant, revocation, and signup email behavior.
    """
    Profile = env["clinic.portal.profile"].sudo()
    users = env["res.users"].sudo().search([
        ("active", "=", True),
        ("share", "=", True),
    ])
    for user in users:
        patient = user.patient_id or user.partner_id.patient_id
        if user._is_portal() and patient and patient.company_id:
            # Installation prepares staff-reviewable Draft governance records.
            # It never auto-enables clinical history merely because a generic
            # Odoo Portal account already exists.
            Profile._seed_draft_for_user(user, patient.company_id)
