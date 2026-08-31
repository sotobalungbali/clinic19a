
#!/usr/bin/env python3
"""Standalone MASTER PROMPT 09 source-contract regression tests."""
from pathlib import Path
import ast, unittest
ROOT = Path(__file__).resolve().parents[1]

def class_meta(path, name):
    tree=ast.parse(path.read_text(encoding="utf-8")); cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name==name); vals={}
    for s in cls.body:
        if isinstance(s,ast.Assign):
            for t in s.targets:
                if isinstance(t,ast.Name):
                    try: vals[t.id]=ast.literal_eval(s.value)
                    except Exception: pass
    return cls, vals

class TestPrompt09(unittest.TestCase):
    def test_version_and_owner_versions(self):
        m=ast.literal_eval(ast.parse((ROOT/'__manifest__.py').read_text()).body[0].value)
        self.assertEqual(m['version'],'19.0.1.0.19')
        c=(ROOT/'services/constants.py').read_text()
        self.assertIn('"clinic_staff": "19.0.1.0.1"',c); self.assertIn('"clinic_doctor": "19.0.1.0.2"',c); self.assertIn('"clinic_patient": "19.0.1.0.1"',c)
        self.assertIn('1b91d4402f242a91bbbb7a483403187936eab960cc1b9858b059bc7987af2c7e',c)
    def test_workforce_generators(self):
        _,p=class_meta(ROOT/'generators/workforce/preflight.py','WorkforcePreflightGenerator')
        _,w=class_meta(ROOT/'generators/workforce/staff_provider.py','WorkforceStaffProviderGenerator')
        self.assertEqual(p['key'],'workforce.preflight'); self.assertEqual(w['key'],'workforce.staff')
        self.assertEqual(p['depends_on'],('foundation.organization',)); self.assertEqual(w['depends_on'],('workforce.preflight',))
        self.assertEqual(w['phase'],'09_workforce'); self.assertIn('base.group_system',w['required_groups'])
    def test_acl_sequence_preflight_contract(self):
        text=(ROOT/'generators/workforce/preflight.py').read_text()
        self.assertEqual(text.count('clinic_staff.access_'),20); self.assertEqual(text.count('clinic_doctor.access_'),6)
        self.assertIn('clinic_staff.seq_clinic_staff',text); self.assertIn('clinic_doctor.seq_clinic_appointment',text)
        self.assertIn('clinic.staff.license',text); self.assertIn('clinic.practitioner',text)
    def test_actor_and_provider_budgets(self):
        text=(ROOT/'generators/workforce/staff_provider.py').read_text(); tree=ast.parse(text)
        values={}
        for n in tree.body:
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
                try: values[n.targets[0].id]=ast.literal_eval(n.value)
                except Exception: pass
        self.assertEqual(len(values['ACTORS']),6)
        self.assertEqual(values['PROFILE_COUNTS']['full_enterprise'],{'doctor':3,'nurse':2,'therapist':2})
        for token in ('DEMO-USER-TECH-ADMIN','DEMO-DOC-','DEMO-PRAC-','DEMO-STAFF-','DEMO-DOCSCHED-'):
            self.assertIn(token,text)
    def test_no_sudo_or_direct_sql_in_workforce(self):
        runtime='\n'.join(p.read_text() for p in (ROOT/'generators/workforce').glob('*.py'))
        self.assertNotIn('.sudo(',runtime); self.assertNotIn('.execute(',runtime); self.assertNotIn('.cr.commit(',runtime)
    def test_compat_adoption_is_repair_bounded(self):
        text=(ROOT/'models/demo_run.py').read_text()
        self.assertIn('foundation_generators = {"foundation.native", "foundation.organization"}',text)
        self.assertIn('workforce_generators = {"workforce.preflight", "workforce.staff"}',text)
        self.assertIn('prompt09_staff_failed',text)
        self.assertIn('runtime_repair_adoption',text)
        self.assertIn('no_workforce_references',text)
    def test_system_administrator_can_execute_without_duplicate_functional_roles(self):
        text=(ROOT/'services/execution_engine.py').read_text()
        self.assertIn('if self.env.user.has_group("base.group_system"):', text)
        self.assertIn('return True', text)

    def test_reset_supports_is_active(self):
        self.assertIn('"is_active" if "is_active" in record._fields', (ROOT/'services/reset_service.py').read_text())
        rp=(ROOT/'services/reset_policy_registry.py').read_text(); self.assertIn('"clinic.staff"',rp); self.assertIn('"clinic.doctor"',rp)

    def test_odoo19_user_group_and_access_api(self):
        text=(ROOT/'generators/workforce/staff_provider.py').read_text()
        preflight=(ROOT/'generators/workforce/preflight.py').read_text()
        self.assertIn('"group_ids": [(6, 0, self._group_ids(ctx, groups))]', text)
        self.assertNotIn('"groups_id":', text)
        self.assertIn('.browse().check_access("read")', text)
        self.assertNotIn('check_access_rights(', text)
        self.assertIn('"group_ids"', preflight)

    def test_fail_fast_notification_surfaces_generator(self):
        text=(ROOT/'services/execution_engine.py').read_text()
        self.assertIn('First failure: %(generator)s', text)
        self.assertIn('first.error_summary', text)

    def test_user_rerun_preserves_branch_security(self):
        text=(ROOT/'generators/workforce/staff_provider.py').read_text()
        self.assertIn('def _prepare_user_update(self, ctx, branch):', text)
        self.assertIn('values.pop("allowed_branch_ids", None)', text)
        self.assertIn('values.pop("working_branch_id", None)', text)
        self.assertIn('clinic_branch.group_branch_manager', text)
        self.assertNotIn('.sudo(', text)

    def test_is_doctor_runtime_contract(self):
        doctor = (ROOT.parent / "clinic_doctor" / "models" / "res_partner_inherit.py").read_text(encoding="utf-8")
        preflight = (ROOT / "generators" / "workforce" / "preflight.py").read_text(encoding="utf-8")
        self.assertIn("is_doctor = fields.Boolean(", doctor)
        self.assertIn('"res.partner": {"is_doctor"}', preflight)

    def test_clinic_patient_odoo19_group_field_repair(self):
        patient = (ROOT.parent / "clinic_patient" / "models" / "res_users_inherit.py").read_text(encoding="utf-8")
        active = "\n".join(line for line in patient.splitlines() if not line.lstrip().startswith("#"))
        self.assertIn('portal_group in self.group_ids', active)
        self.assertIn('"group_ids" in vals', active)
        self.assertNotIn('self.groups_id', active)
        self.assertNotIn('"groups_id" in vals', active)

if __name__=='__main__': unittest.main(verbosity=2)


