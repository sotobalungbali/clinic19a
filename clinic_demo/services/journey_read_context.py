"""Explicit read actors for provenance inspection, matching owner generation APIs.

No role grants, sudo, actor discovery, retries with stronger users, or business
writes. Unknown domains retain the authorized Control Center operator.
"""
from odoo.exceptions import UserError

MANAGER = 'DEMO-USER-MGR'
DOCTOR = 'DEMO-USER-DOC-001'
NURSE = 'DEMO-USER-NUR-001'
MANAGER_JOURNEYS = frozenset({
    'operations.referral', 'operations.future_pipeline',
    'commercial.billing', 'commercial.ar', 'commercial.ap',
    'exception.feedback', 'exception.incident_quality',
    'digital.ecommerce_marketing_portal',
    'management.reports', 'management.dashboard', 'management.analytics',
})
DOCTOR_JOURNEYS = frozenset({
    'clinical.imaging', 'clinical.emar', 'clinical.care_postcare',
    'clinical.telemedicine',
})
COMMERCIAL_MODELS = frozenset({
    'clinic.package.policy', 'clinic.package.pricing', 'clinic.package',
    'clinic.package.line', 'clinic.package.integration.event',
    'membership.plan', 'membership.plan.benefit', 'membership.integration.event',
    'clinic.insurance.plan', 'clinic.insurance.plan.rule', 'clinic.wallet.rule',
})

def actor_key(reference):
    model = reference.model_name
    journey = reference.generator_key
    if model == 'clinic.emar.medication.profile' or (journey == 'operations.encounter' and model.startswith('clinic.postcare.')):
        return MANAGER
    if journey in ('master.commercial', 'master.package') and model in COMMERCIAL_MODELS:
        return MANAGER
    if journey == 'operations.treatment_session':
        bookings = {
            'DEMO-SESSION-001': 'DEMO-BOOK-TODAY-002',
            'DEMO-SESSION-LINE-001': 'DEMO-BOOK-TODAY-002',
            'DEMO-SESSION-NOSHOW-001': 'DEMO-BOOK-TODAY-004',
            'DEMO-SESSION-CANCEL-001': 'DEMO-BOOK-TODAY-005',
        }
        if reference.demo_key not in bookings:
            raise UserError('No declared treatment-session reader for %s' % reference.demo_key)
        return 'booking_doctor:' + bookings[reference.demo_key]
    if journey in DOCTOR_JOURNEYS:
        if model == 'clinic.emar.administration':
            return NURSE
        if model == 'clinic.emar.schedule' or model.startswith('clinic.postcare.'):
            return MANAGER
        return DOCTOR
    if journey in MANAGER_JOURNEYS:
        return MANAGER
    return None


def read_model(run, reference):
    """Select one declared reader, then leave all ORM ACL/rules in force."""
    key = actor_key(reference)
    model = run.env[reference.model_name]
    if key and key.startswith('booking_doctor:'):
        booking_key = key.split(':', 1)[1]
        links = run.reference_ids.filtered(lambda ref: ref.demo_key == booking_key)
        if len(links) != 1 or links.model_name != 'booking.booking' or links.ownership_kind not in ('created', 'updated_demo_owned'):
            raise UserError('Treatment-session reader requires verified booking provenance: %s' % booking_key)
        booking = run.env['booking.booking'].with_company(run.company_id).with_context(allowed_company_ids=[run.company_id.id]).browse(links.res_id).exists()
        if not booking or booking.company_id != run.company_id:
            raise UserError('Treatment-session reader booking is missing or outside run company')
        clinician = booking.doctor_id.user_id
        actors = run.reference_ids.filtered(lambda ref: ref.model_name == 'res.users' and ref.res_id == clinician.id and ref.demo_key.startswith('DEMO-USER-DOC-'))
        if len(actors) != 1:
            raise UserError('Booking clinician must have one run-owned doctor identity')
        key = actors.demo_key
    if key:
        refs = run.reference_ids.filtered(lambda ref: ref.demo_key == key)
        if len(refs) != 1 or refs.model_name != 'res.users' or refs.ownership_kind not in ('created', 'updated_demo_owned'):
            raise UserError('Journey reader %s requires one demo-owned res.users provenance record' % key)
        actor = run.env['res.users'].browse(refs.res_id).exists()
        if not actor or not actor.active or run.company_id not in actor.company_ids:
            raise UserError('Journey reader %s is missing, inactive, or outside the run company' % key)
        model = model.with_user(actor)
    return model.with_company(run.company_id).with_context(
        allowed_company_ids=[run.company_id.id], active_test=False,
        prefetch_fields=False,
    )







