"""Explicit cross-branch demo consultation entitlement, through owner user API."""
from odoo.exceptions import UserError


def prepare_telemedicine_scope(run, optional=False):
    run._check_operator()
    def owned(key, model):
        refs = run.reference_ids.filtered(lambda ref: ref.demo_key == key)
        if not refs and optional:
            return False
        if len(refs) != 1 or refs.model_name != model or refs.ownership_kind not in ('created', 'updated_demo_owned'):
            raise UserError('Telemedicine scope requires unique demo-owned provenance: %s' % key)
        return run.env[model].with_company(run.company_id).with_context(allowed_company_ids=[run.company_id.id],prefetch_fields=False).browse(refs.res_id).exists()
    user = owned('DEMO-USER-DOC-001', 'res.users')
    patient = owned('DEMO-PAT-TELE-001', 'clinic.patient')
    doctor = owned('DEMO-DOC-001', 'clinic.doctor')
    if not user or not patient or not doctor:
        if optional:return False
        raise UserError('Telemedicine actor/patient/doctor prerequisite is missing')
    if doctor.user_id != user or patient.company_id != run.company_id or run.company_id not in user.company_ids or not user.active:
        raise UserError('Telemedicine actor/patient company or doctor-user relationship differs')
    branch = patient.partner_id.branch_id
    if not branch:
        return False
    if branch.company_id != run.company_id:
        raise UserError('Telemedicine patient branch is outside the run company')
    refs = run.reference_ids.filtered(lambda ref: ref.model_name == 'clinic.branch' and ref.res_id == branch.id and ref.demo_key.startswith('DEMO-') and ref.ownership_kind in ('created','updated_demo_owned'))
    if len(refs) != 1:
        raise UserError('Telemedicine patient branch requires unique demo-owned provenance')
    for key, model in [('DEMO-TELE-SESSION-001','clinic.telemedicine.session'),
                       ('DEMO-TELE-THREAD-001','clinic.telemedicine.thread')]:
        if run.reference_ids.filtered(lambda ref: ref.demo_key == key):
            record = owned(key, model)
            if record and (record.company_id != run.company_id or record.patient_id != patient or (record.branch_id and record.branch_id != branch)):
                raise UserError('Existing Telemedicine company/patient/branch differs: %s' % key)
    # Only this consultation's branch; preserve the doctor's home/working branch.
    if branch not in user.allowed_branch_ids:
        user.write({'allowed_branch_ids': [(4, branch.id)]})
        run._log_control_event('info','telemedicine_actor_scope',
            'DEMO-USER-DOC-001 granted consultation branch %s for DEMO-PAT-TELE-001; working branch unchanged' % refs.demo_key)
    return branch



