
"""Deterministic Staff & Clinical Provider dataset for MASTER PROMPT 09."""

from datetime import datetime, time, timedelta

import pytz

from odoo import _
from odoo.exceptions import UserError

from ..base import BaseDemoGenerator
from ...services.constants import RESET_DEACTIVATE, RESET_DELETE_SAFE, RESET_FRESH_DB_ONLY
from ...services.generator_registry import GENERATOR_REGISTRY


ACTORS = (
    {"code": "EXEC", "name": "Adrian Pratama", "title": "Executive Owner", "staff_role": "manager", "grade": "principal", "department": "EXEC", "groups": ("clinic_branch.group_branch_manager", "clinic_dashboard.group_dashboard_manager", "clinic_reports.group_reports_manager", "clinic_analytics.group_analytics_manager")},
    {"code": "MGR", "name": "Maya Lestari", "title": "Clinic Manager", "staff_role": "manager", "grade": "lead", "department": "OPS", "groups": ("clinic_branch.group_branch_manager", "clinic_billing.group_clinic_billing_manager", "clinic_treatment_session.group_treatment_session_manager", "clinic_post_care_followup.group_postcare_manager", "clinic_incident_event.group_incident_manager", "clinic_quality.group_quality_manager")},
    {"code": "FO", "name": "Nadia Kusuma", "title": "Front Office", "staff_role": "admin", "grade": "mid", "department": "FO", "groups": ("clinic_branch.group_branch_user", "clinic_referral.group_referral_user", "clinic_treatment_session.group_treatment_session_user")},
    {"code": "CASH", "name": "Raka Mahendra", "title": "Cashier & Finance", "staff_role": "admin", "grade": "mid", "department": "FIN", "groups": ("clinic_branch.group_branch_user", "clinic_billing.group_clinic_billing_cashier", "clinic_finance.group_clinic_finance_cashier")},
    {"code": "QUAL", "name": "Citra Wulandari", "title": "Quality & Compliance", "staff_role": "other", "grade": "senior", "department": "QUAL", "groups": ("clinic_branch.group_branch_user", "clinic_incident_event.group_incident_investigator", "clinic_quality.group_quality_approver", "clinic_audit.group_audit_user")},
    {"code": "ANL", "name": "Dimas Santoso", "title": "Analytics & Reporting", "staff_role": "other", "grade": "senior", "department": "ANL", "groups": ("clinic_branch.group_branch_user", "clinic_reports.group_reports_analyst", "clinic_dashboard.group_dashboard_analyst", "clinic_analytics.group_analytics_analyst")},
)

CLINICAL = {
    "doctor": (
        ("001", "Dr. Alya Permata", "senior", "Aesthetic Medicine", "AESTH", 9.0, 14.0),
        ("002", "Dr. Bima Adinata", "senior", "Dermatology", "DERM", 10.0, 16.0),
        ("003", "Dr. Kirana Putri", "mid", "Aesthetic Medicine", "AESTH", 12.0, 18.0),
    ),
    "nurse": (
        ("001", "Nurse Sinta Maharani", "senior", "Clinical Nursing"),
        ("002", "Nurse Farah Nirmala", "mid", "Clinical Nursing"),
    ),
    "therapist": (
        ("001", "Therapist Nara Dewi", "senior", "Aesthetic Therapy"),
        ("002", "Therapist Galih Prakoso", "mid", "Aesthetic Therapy"),
    ),
}

PROFILE_COUNTS = {
    "compact": {"doctor": 1, "nurse": 1, "therapist": 1},
    "standard": {"doctor": 2, "nurse": 2, "therapist": 1},
    "full_enterprise": {"doctor": 3, "nurse": 2, "therapist": 2},
}

DEPARTMENTS = (
    ("EXEC", "Executive Management"), ("OPS", "Clinic Operations"),
    ("FO", "Front Office"), ("FIN", "Finance & Cashier"),
    ("QUAL", "Quality & Compliance"), ("ANL", "Analytics & Reporting"),
    ("CLIN", "Clinical Services"),
)

SKILLS = (
    ("MEDCONS", "Clinical Consultation", "medical", False, False, True),
    ("TRIAGE", "Triage & Vital Signs", "nursing", True, False, True),
    ("MEDADMIN", "Medication Administration", "nursing", True, False, True),
    ("AESTHTX", "Aesthetic Treatment Delivery", "therapy", False, True, True),
    ("PATSAFE", "Patient Safety & Escalation", "safety", True, True, True),
)

LICENSE_TYPES = (
    ("DOC", "Medical Practitioner License", False, False, True),
    ("NUR", "Clinical Nursing Registration", True, False, False),
    ("THR", "Aesthetic Therapist Certification", False, True, False),
)

ROLE_GROUPS = {
    "doctor": ("clinic_branch.group_branch_user", "clinic_treatment_session.group_treatment_session_clinician", "clinic_post_care_followup.group_postcare_clinician", "clinic_telemedicine_secure_messaging.group_telemedicine_clinician", "clinic_emar.group_emar_prescriber"),
    "nurse": ("clinic_branch.group_branch_user", "clinic_treatment_session.group_treatment_session_clinician", "clinic_post_care_followup.group_postcare_clinician", "clinic_emar.group_emar_nurse"),
    "therapist": ("clinic_branch.group_branch_user", "clinic_treatment_session.group_treatment_session_clinician", "clinic_post_care_followup.group_postcare_clinician"),
}


@GENERATOR_REGISTRY.register
class WorkforceStaffProviderGenerator(BaseDemoGenerator):
    key = "workforce.staff"
    phase = "09_workforce"
    sequence = 210
    depends_on = ("workforce.preflight",)
    scenario_keys = ("SCN-WORKFORCE-01",)
    owned_models = (
        "res.users", "res.partner", "hr.employee", "hr.department", "clinic.staff",
        "clinic.practitioner", "clinic.skill", "clinic.staff.skill", "clinic.license.type",
        "clinic.staff.license", "clinic.staff.availability", "clinic.specialty",
        "clinic.doctor", "clinic.schedule.rule",
    )
    required_groups = ("base.group_system", "clinic_branch.group_branch_manager")

    def _counters(self):
        return {"created": 0, "reused": 0, "updated": 0, "skipped": 0, "warning": 0, "error": 0}

    @staticmethod
    def _bump(counters, status):
        if status in counters:
            counters[status] += 1
        elif status == "created":
            counters["created"] += 1

    def _ensure(
        self,
        ctx,
        counters,
        key,
        model,
        values,
        policy,
        reset_sequence,
        update=True,
        prepare_update=None,
    ):
        Model = ctx.env[model]

        def create():
            return Model.create(dict(values))

        def update_record(record):
            write_values = dict(values)
            if prepare_update:
                write_values = prepare_update(record, write_values)
            if write_values:
                record.write(write_values)

        record, _ref, status = ctx.reference_service.ensure_record(
            run=ctx.run,
            demo_key=key,
            model_name=model,
            generator_key=self.key,
            scenario_key=ctx.scenario.key,
            create_callback=create,
            update_callback=update_record if update else None,
            reset_policy=policy,
            reset_sequence=reset_sequence,
        )
        self._bump(counters, status)
        return record

    def _prepare_user_update(self, ctx, branch):
        """Avoid rewriting protected branch fields when a rerun already matches them.

        clinic_branch correctly guards branch changes on existing users. Prompt 09
        remains idempotent without sudo by omitting those protected fields when the
        deterministic branch assignment is already correct. A real mismatch is
        surfaced instead of bypassed.
        """
        def prepare(record, values):
            desired_branch_ids = {branch.id}
            current_branch_ids = set(record.allowed_branch_ids.ids)
            branch_matches = (
                current_branch_ids == desired_branch_ids
                and record.working_branch_id == branch
            )
            if branch_matches:
                values.pop("allowed_branch_ids", None)
                values.pop("working_branch_id", None)
                return values

            can_change_branch = (
                ctx.env.su
                or ctx.env.user.has_group("clinic_branch.group_branch_manager")
            )
            if not can_change_branch:
                raise UserError(_(
                    "Existing demo user %(user)s has branch assignments that differ "
                    "from deterministic Prompt 09 values. Re-run as a Branch Manager "
                    "or correct the demo-owned user through the supported branch workflow."
                ) % {"user": record.display_name})
            return values

        return prepare

    def _branch(self, ctx, number):
        max_branch = {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile]
        number = min(number, max_branch)
        return ctx.reference_service.resolve(ctx.run, f"DEMO-BRANCH-{number:03d}", "clinic.branch")

    def _group_ids(self, ctx, xmlids):
        result = [ctx.env.ref("base.group_user").id]
        for xmlid in xmlids:
            group = ctx.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                raise UserError(_("Required presentation group is missing: %s") % xmlid)
            result.append(group.id)
        return sorted(set(result))

    def _utc(self, ctx, date_value, hour):
        tz = pytz.timezone(ctx.run.timezone or "UTC")
        local = tz.localize(datetime.combine(date_value, time(hour=hour)))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    def _ensure_department(self, ctx, counters, code, name):
        return self._ensure(ctx, counters, f"DEMO-DEPT-{code}", "hr.department", {
            "name": f"ClinicOne Demo — {name}", "company_id": ctx.run.company_id.id,
        }, RESET_DEACTIVATE, 400)

    def _ensure_user_identity(self, ctx, counters, code, name, title, department, groups, branch):
        partner = self._ensure(ctx, counters, f"DEMO-PARTNER-{code}", "res.partner", {
            "name": name, "email": f"{code.lower()}@clinicone-demo.invalid",
            "phone": f"+62-811-247-{1000 + sum(ord(c) for c in code):04d}",
            "company_type": "person", "company_id": ctx.run.company_id.id,
        }, RESET_DEACTIVATE, 900)
        user = self._ensure(
            ctx,
            counters,
            f"DEMO-USER-{code}",
            "res.users",
            {
                "name": name,
                "login": f"demo.{code.lower()}@clinicone.invalid",
                "email": f"{code.lower()}@clinicone-demo.invalid",
                "partner_id": partner.id,
                "company_id": ctx.run.company_id.id,
                "company_ids": [(6, 0, [ctx.run.company_id.id])],
                "group_ids": [(6, 0, self._group_ids(ctx, groups))],
                "allowed_branch_ids": [(6, 0, [branch.id])],
                "working_branch_id": branch.id,
                "active": True,
            },
            RESET_DEACTIVATE,
            850,
            prepare_update=self._prepare_user_update(ctx, branch),
        )
        employee = self._ensure(ctx, counters, f"DEMO-EMP-{code}", "hr.employee", {
            "name": name, "company_id": ctx.run.company_id.id, "department_id": department.id,
            "user_id": user.id, "branch_id": branch.id, "work_email": user.email,
        }, RESET_DEACTIVATE, 800)
        return partner, user, employee

    def _ensure_staff(self, ctx, counters, code, partner, user, employee, role, grade, branch):
        return self._ensure(ctx, counters, f"DEMO-STAFF-{code}", "clinic.staff", {
            "partner_id": partner.id, "user_id": user.id, "employee_id": employee.id,
            "role": role, "grade": grade, "employment_status": "active", "is_active": True,
            "hire_date": ctx.run.anchor_date - timedelta(days=730),
            "company_id": ctx.run.company_id.id, "branch_id": branch.id,
        }, RESET_DEACTIVATE, 750)

    def _masters(self, ctx, counters):
        departments = {code: self._ensure_department(ctx, counters, code, name) for code, name in DEPARTMENTS}
        skills = {}
        for code, name, category, nurse, therapist, doctor in SKILLS:
            skills[code] = self._ensure(ctx, counters, f"DEMO-SKILL-{code}", "clinic.skill", {
                "name": f"ClinicOne Demo — {name}", "category": category,
                "applicable_to_nurse": nurse, "applicable_to_therapist": therapist,
                "applicable_to_doctor": doctor, "requires_license": code != "PATSAFE",
                "minimum_grade": "junior", "is_active": True, "company_id": ctx.run.company_id.id,
            }, RESET_DEACTIVATE, 500)
        license_types = {}
        for code, name, nurse, therapist, doctor in LICENSE_TYPES:
            license_types[code] = self._ensure(ctx, counters, f"DEMO-LTYPE-{code}", "clinic.license.type", {
                "name": f"ClinicOne Demo — {name}", "applicable_to_nurse": nurse,
                "applicable_to_therapist": therapist, "applicable_to_doctor": doctor,
                "validity_months": 60, "renewal_notice_days": 90, "requires_number": True,
                "requires_issuer": True, "requires_country": True, "requires_attachment": False,
                "is_active": True, "company_id": ctx.run.company_id.id,
            }, RESET_DEACTIVATE, 500)
        specialties = {}
        for code, name in (("AESTH", "Aesthetic Medicine"), ("DERM", "Dermatology")):
            specialties[code] = self._ensure(ctx, counters, f"DEMO-SPEC-{code}", "clinic.specialty", {
                "name": f"ClinicOne Demo — {name}", "code": f"DEMO-{code}",
                "company_id": ctx.run.company_id.id, "active": True,
            }, RESET_DEACTIVATE, 500)
        return departments, skills, license_types, specialties

    def _license_and_skills(self, ctx, counters, staff, role, code, license_type, skills):
        indonesia = ctx.env["res.country"].search([("code", "=", "ID")], limit=1)
        license_record = self._ensure(ctx, counters, f"DEMO-LIC-{code}", "clinic.staff.license", {
            "staff_id": staff.id, "license_type_id": license_type.id,
            "number": f"SYN-{role.upper()}-{code}-247", "issuer": "Synthetic Professional Board",
            "country_id": indonesia.id, "issue_date": ctx.run.anchor_date - timedelta(days=365),
            "expiry_date": ctx.run.anchor_date + timedelta(days=1095), "active": True,
        }, RESET_DEACTIVATE, 700)
        if license_record.state not in ("active", "expiring"):
            license_record.action_activate()
        if not license_record.verified:
            license_record.action_mark_verified()

        wanted = {
            "doctor": ("MEDCONS", "AESTHTX", "PATSAFE"),
            "nurse": ("TRIAGE", "MEDADMIN", "PATSAFE"),
            "therapist": ("AESTHTX", "PATSAFE"),
        }[role]
        linked = []
        for skill_code in wanted:
            skill = skills[skill_code]
            rec = self._ensure(ctx, counters, f"DEMO-STAFFSKILL-{code}-{skill_code}", "clinic.staff.skill", {
                "staff_id": staff.id, "skill_id": skill.id, "level": "4" if staff.grade in ("senior", "lead", "principal") else "3",
                "last_assessed_date": ctx.run.anchor_date - timedelta(days=30), "assessor_id": ctx.env.user.id,
                "valid_from": ctx.run.anchor_date - timedelta(days=180), "valid_to": ctx.run.anchor_date + timedelta(days=365),
            }, RESET_DELETE_SAFE, 720)
            linked.append(skill)
        return linked

    def _availability(self, ctx, counters, staff, code, offset_hours=0):
        day = ctx.run.anchor_date + timedelta(days=1)
        start_hour = 8 + offset_hours
        return self._ensure(ctx, counters, f"DEMO-AVAIL-{code}", "clinic.staff.availability", {
            "name": "Demo recurring clinical availability", "staff_id": staff.id,
            "start": self._utc(ctx, day, start_hour),
            "stop": self._utc(ctx, day, min(start_hour + 8, 23)), "availability_type": "available",
            "recurrency": True, "rrule_type": "weekly", "interval": 1,
            "w_mon": True, "w_tue": True, "w_wed": True, "w_thu": True, "w_fri": True,
            "recur_end_type": "until", "recur_until": ctx.run.anchor_date + timedelta(days=90), "active": True,
        }, RESET_DEACTIVATE, 730)

    def _practitioner(self, ctx, counters, staff, code, specialty, skills):
        return self._ensure(ctx, counters, f"DEMO-PRAC-{code}", "clinic.practitioner", {
            "staff_id": staff.id, "company_id": ctx.run.company_id.id, "branch_id": staff.branch_id.id,
            "specialty": specialty, "grade": staff.grade, "language_skills": "Indonesian, English",
            "experience_years": 8 if staff.grade == "senior" else 4,
            "skill_ids": [(6, 0, [s.id for s in skills])], "active": True,
        }, RESET_DEACTIVATE, 740)

    def _doctor(self, ctx, counters, code, staff, specialty, specialty_master, start_time, end_time):
        calendar = ctx.run.company_id.resource_calendar_id if "resource_calendar_id" in ctx.run.company_id._fields else False
        doctor = self._ensure(ctx, counters, f"DEMO-DOC-{code}", "clinic.doctor", {
            "partner_id": staff.partner_id.id, "user_id": staff.user_id.id, "company_id": ctx.run.company_id.id,
            "staff_id": staff.id, "license_no": f"SYN-DOC-{code}-247", "license_authority": "Synthetic Medical Council",
            "specialty_ids": [(6, 0, [specialty_master.id])], "seniority_level": "senior" if staff.grade == "senior" else "junior",
            "allow_portal_booking": True, "telemedicine_enabled": True, "rating_enabled": True,
            "calendar_id": calendar.id if calendar else False, "capacity_per_slot": 1 if code != "003" else 2,
            "min_lead_time_hours": 2, "max_lead_time_days": 90, "active": True,
        }, RESET_DEACTIVATE, 760)
        weekdays = ("0", "2") if code != "003" else ("1", "4")
        for index, weekday in enumerate(weekdays, 1):
            self._ensure(ctx, counters, f"DEMO-DOCSCHED-{code}-{index}", "clinic.schedule.rule", {
                "name": f"{doctor.name} — Demo Schedule {index}", "company_id": ctx.run.company_id.id,
                "doctor_id": doctor.id, "specialty_id": specialty_master.id, "weekday": weekday,
                "interval_weeks": 1, "date_start": ctx.run.anchor_date,
                "date_end": ctx.run.anchor_date + timedelta(days=90), "start_time": start_time,
                "end_time": end_time, "slot_duration_min": 30, "capacity_per_slot": doctor.capacity_per_slot,
                "conflict_policy": "skip", "rule_tz": ctx.run.timezone, "active": True,
            }, RESET_DEACTIVATE, 770)
        return doctor

    def generate(self, ctx, scenario):
        counters = self._counters()
        departments, skills, license_types, specialties = self._masters(ctx, counters)

        # Explicitly register the executing System Administrator as a presentation actor; never clone it.
        ctx.reference_service.bind_reused(
            run=ctx.run, demo_key="DEMO-USER-TECH-ADMIN", record=ctx.env.user,
            generator_key=self.key, scenario_key=scenario.key,
            reset_policy=RESET_FRESH_DB_ONLY, reset_sequence=1000,
        )
        counters["reused"] += 1

        for idx, spec in enumerate(ACTORS, 1):
            branch = self._branch(ctx, 1 if spec["code"] in {"EXEC", "MGR", "FO", "CASH"} else min(idx, 3))
            partner, user, employee = self._ensure_user_identity(
                ctx, counters, spec["code"], spec["name"], spec["title"], departments[spec["department"]], spec["groups"], branch,
            )
            self._ensure_staff(ctx, counters, spec["code"], partner, user, employee, spec["staff_role"], spec["grade"], branch)

        counts = PROFILE_COUNTS[ctx.profile]
        clinical_index = 0
        for role in ("doctor", "nurse", "therapist"):
            for data in CLINICAL[role][:counts[role]]:
                clinical_index += 1
                code = data[0]
                actor_code = f"{role[:3].upper()}-{code}"
                branch = self._branch(ctx, ((clinical_index - 1) % {"compact": 1, "standard": 2, "full_enterprise": 3}[ctx.profile]) + 1)
                partner, user, employee = self._ensure_user_identity(
                    ctx, counters, actor_code, data[1], role.title(), departments["CLIN"], ROLE_GROUPS[role], branch,
                )
                staff = self._ensure_staff(ctx, counters, actor_code, partner, user, employee, role, data[2], branch)
                license_type = license_types[{"doctor": "DOC", "nurse": "NUR", "therapist": "THR"}[role]]
                linked_skills = self._license_and_skills(ctx, counters, staff, role, actor_code, license_type, skills)
                self._availability(ctx, counters, staff, actor_code, clinical_index % 2)
                specialty_label = data[3]
                self._practitioner(ctx, counters, staff, actor_code, specialty_label, linked_skills)
                if role == "doctor":
                    self._doctor(ctx, counters, code, staff, specialty_label, specialties[data[4]], data[5], data[6])

        return counters

    def validate(self, ctx, scenario):
        failures = []
        tech_admin = ctx.reference_service.resolve(ctx.run, "DEMO-USER-TECH-ADMIN", "res.users")
        if tech_admin != ctx.env.user or not tech_admin.has_group("base.group_system"):
            failures.append("Technical Administrator reference is not the executing System Administrator.")

        expected_clinical = []
        counts = PROFILE_COUNTS[ctx.profile]
        for role in ("doctor", "nurse", "therapist"):
            for data in CLINICAL[role][:counts[role]]:
                actor_code = f"{role[:3].upper()}-{data[0]}"
                expected_clinical.append((role, actor_code, data[0]))

        for role, actor_code, doc_code in expected_clinical:
            staff = ctx.reference_service.resolve(ctx.run, f"DEMO-STAFF-{actor_code}", "clinic.staff")
            user = ctx.reference_service.resolve(ctx.run, f"DEMO-USER-{actor_code}", "res.users")
            employee = ctx.reference_service.resolve(ctx.run, f"DEMO-EMP-{actor_code}", "hr.employee")
            practitioner = ctx.reference_service.resolve(ctx.run, f"DEMO-PRAC-{actor_code}", "clinic.practitioner")
            if not (staff.user_id == user and staff.employee_id == employee and staff.partner_id == user.partner_id):
                failures.append(f"{actor_code}: orphan/mismatched user-employee-staff identity.")
            if not (staff.branch_id == employee.branch_id == practitioner.branch_id == user.working_branch_id):
                failures.append(f"{actor_code}: branch assignment is inconsistent across actor identity.")
            if not staff.license_ids.filtered(lambda item: item.state in ("active", "expiring")):
                failures.append(f"{actor_code}: no active professional license.")
            if not staff.skill_ids.filtered(lambda item: item.state == "valid" and item.is_compliant):
                failures.append(f"{actor_code}: no valid compliant capability/skill.")
            if not staff.can_be_scheduled:
                failures.append(f"{actor_code}: staff is not schedule-eligible.")
            if role == "doctor":
                doctor = ctx.reference_service.resolve(ctx.run, f"DEMO-DOC-{doc_code}", "clinic.doctor")
                if doctor.staff_id != staff or doctor.user_id != user or doctor.branch_id != staff.branch_id:
                    failures.append(f"DOC-{doc_code}: doctor/staff/provider identity bridge is inconsistent.")
                if not doctor.specialty_ids or len(doctor.schedule_rule_ids.filtered("active")) < 2:
                    failures.append(f"DOC-{doc_code}: specialty/schedule capability is incomplete.")

        # Role-based source access validation without sudo. Menus are suite-level Prompt-23 scope.
        access_matrix = (("EXEC", "clinic.doctor"), ("MGR", "clinic.staff"), ("FO", "clinic.doctor"),
                         ("CASH", "clinic.staff"), ("QUAL", "clinic.staff"), ("ANL", "clinic.doctor"))
        for code, model_name in access_matrix:
            user = ctx.reference_service.resolve(ctx.run, f"DEMO-USER-{code}", "res.users")
            try:
                ctx.env[model_name].with_user(user).browse().check_access("read")
            except Exception as exc:
                failures.append(f"{code}: read access to {model_name} failed: {exc}")

        if failures:
            raise UserError(_("MASTER PROMPT 09 validation failed:\n%s") % "\n".join(f"- {item}" for item in failures))
        return []

    def repair_missing(self, ctx, scenario):
        return self.generate(ctx, scenario)

    def reset(self, ctx, scenario):
        return True


