
"""MASTER PROMPT 09 fail-fast checks for owner-addon ACL and sequence contracts."""

from odoo import _
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.generator_registry import GENERATOR_REGISTRY


STAFF_ACL_XMLIDS = (
    "clinic_staff.access_clinic_staff_internal",
    "clinic_staff.access_clinic_skill_internal",
    "clinic_staff.access_clinic_staff_skill_internal",
    "clinic_staff.access_clinic_license_type_internal",
    "clinic_staff.access_clinic_staff_license_internal",
    "clinic_staff.access_clinic_staff_availability_internal",
    "clinic_staff.access_clinic_staff_availability_occurrence_internal",
    "clinic_staff.access_clinic_shift_template_internal",
    "clinic_staff.access_clinic_staff_roster_internal",
    "clinic_staff.access_clinic_staff_assignment_internal",
    "clinic_staff.access_clinic_workload_policy_internal",
    "clinic_staff.access_clinic_staff_workload_internal",
    "clinic_staff.access_clinic_staff_workload_line_internal",
    "clinic_staff.access_clinic_staff_presence_internal",
    "clinic_staff.access_clinic_staff_presence_session_internal",
    "clinic_staff.access_clinic_staff_presence_break_internal",
    "clinic_staff.access_clinic_kpi_definition_internal",
    "clinic_staff.access_clinic_staff_kpi_internal",
    "clinic_staff.access_clinic_staff_kpi_line_internal",
    "clinic_staff.access_clinic_practitioner_internal",
)

DOCTOR_ACL_XMLIDS = (
    "clinic_doctor.access_clinic_doctor_internal",
    "clinic_doctor.access_clinic_specialty_internal",
    "clinic_doctor.access_clinic_schedule_rule_internal",
    "clinic_doctor.access_clinic_availability_slot_internal",
    "clinic_doctor.access_clinic_doctor_leave_internal",
    "clinic_doctor.access_clinic_appointment_internal",
)

SEQUENCE_CONTRACT = (
    ("clinic_staff.seq_clinic_staff", "clinic.staff"),
    ("clinic_staff.seq_clinic_skill", "clinic.skill"),
    ("clinic_staff.seq_clinic_license_type", "clinic.license.type"),
    ("clinic_staff.seq_clinic_staff_license", "clinic.staff.license"),
    ("clinic_staff.seq_clinic_shift_template", "clinic.shift.template"),
    ("clinic_staff.seq_clinic_staff_assignment", "clinic.staff.assignment"),
    ("clinic_staff.seq_clinic_workload_policy", "clinic.workload.policy"),
    ("clinic_staff.seq_clinic_staff_presence_session", "clinic.staff.presence.session"),
    ("clinic_staff.seq_clinic_kpi_definition", "clinic.kpi.definition"),
    ("clinic_staff.seq_clinic_practitioner", "clinic.practitioner"),
    ("clinic_doctor.seq_clinic_appointment", "clinic.appointment"),
)

REQUIRED_FIELDS = {
    "res.partner": {"is_doctor"},
    "clinic.staff": {"partner_id", "user_id", "employee_id", "branch_id", "can_be_scheduled"},
    "clinic.practitioner": {"staff_id", "employee_id", "partner_id", "branch_id", "skill_ids"},
    "clinic.doctor": {"partner_id", "user_id", "staff_id", "branch_id", "specialty_ids", "schedule_rule_ids"},
    "hr.employee": {"user_id", "branch_id"},
    "res.users": {"allowed_branch_ids", "working_branch_id", "group_ids"},
}


@GENERATOR_REGISTRY.register
class WorkforcePreflightGenerator(BaseDemoGenerator):
    key = "workforce.preflight"
    phase = "09_workforce"
    sequence = 200
    depends_on = ("foundation.organization",)
    scenario_keys = ("SCN-WORKFORCE-01",)
    owned_models = ()
    required_groups = ("base.group_system", "clinic_branch.group_branch_manager")

    def _failures(self, ctx):
        failures = []
        for model_name, fields in REQUIRED_FIELDS.items():
            try:
                model = ctx.env[model_name]
            except KeyError:
                failures.append(f"missing model {model_name}")
                continue
            missing = sorted(fields - set(model._fields))
            if missing:
                failures.append(f"{model_name} missing fields: {', '.join(missing)}")

        for xmlid in STAFF_ACL_XMLIDS + DOCTOR_ACL_XMLIDS:
            access = ctx.env.ref(xmlid, raise_if_not_found=False)
            if not access:
                failures.append(f"missing ACL {xmlid}")
                continue
            if not all((access.perm_read, access.perm_write, access.perm_create, access.perm_unlink)):
                failures.append(f"incomplete CRUD ACL {xmlid}")

        for xmlid, expected_code in SEQUENCE_CONTRACT:
            sequence = ctx.env.ref(xmlid, raise_if_not_found=False)
            if not sequence:
                failures.append(f"missing sequence {xmlid}")
            elif sequence.code != expected_code:
                failures.append(f"sequence {xmlid} code={sequence.code!r}, expected {expected_code!r}")
        return failures

    def generate(self, ctx, scenario):
        failures = self._failures(ctx)
        if failures:
            raise UserError(_(
                "MASTER PROMPT 09 owner-addon preflight failed. Upgrade clinic_staff, then "
                "clinic_doctor, then clinic_demo, run Refresh Compatibility, and retry.\n\n%s"
            ) % "\n".join(f"- {item}" for item in failures))
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    def validate(self, ctx, scenario):
        return self._failures(ctx)

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return True


