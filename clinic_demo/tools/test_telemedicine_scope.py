import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
ROOT=Path(__file__).resolve().parents[1]
space={'UserError':ValueError};tree=ast.parse((ROOT/'services/telemedicine_scope.py').read_text());tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))];exec(compile(tree,'scope','exec'),space)
class Refs(list):
    def filtered(self,fn):return Refs(x for x in self if fn(x))
    def __getattr__(self,k):
        assert len(self)==1
        return getattr(self[0],k)
class Model:
    def __init__(self,value):self.value=value
    def with_company(self,*a):return self
    def with_context(self,**k):return self
    def browse(self,*a):return self
    def exists(self):return self.value
class Scope(unittest.TestCase):
    def setup_run(self):
        company=NS(id=1);branch=NS(id=2,company_id=company)
        user=NS(id=14,active=True,company_ids=[company],allowed_branch_ids=[],working_branch_id=1)
        writes=[]
        def write(v):writes.append(v);user.allowed_branch_ids.append(branch)
        user.write=write
        patient=NS(company_id=company,partner_id=NS(branch_id=branch));doctor=NS(user_id=user)
        refs=Refs(NS(demo_key=k,model_name=m,res_id=i,ownership_kind='created') for k,m,i in [('DEMO-USER-DOC-001','res.users',14),('DEMO-PAT-TELE-001','clinic.patient',5),('DEMO-DOC-001','clinic.doctor',7),('DEMO-BRANCH-002','clinic.branch',2)])
        logs=[]
        run=NS(company_id=company,reference_ids=refs,env={'res.users':Model(user),'clinic.patient':Model(patient),'clinic.doctor':Model(doctor)},_check_operator=lambda:None,_log_control_event=lambda *args:logs.append(args))
        return run,user,branch,writes,logs
    def test_only_patient_branch_is_added_and_rerun_is_noop(self):
        run,user,branch,writes,logs=self.setup_run()
        self.assertEqual(space['prepare_telemedicine_scope'](run),branch)
        space['prepare_telemedicine_scope'](run)
        self.assertEqual(writes,[{'allowed_branch_ids':[(4,2)]}]);self.assertEqual(len(logs),1)
        self.assertEqual(user.working_branch_id,1)
    def test_unowned_or_foreign_branch_cannot_grant_access(self):
        for mode in ['unowned','foreign','unowned_user','duplicate']:
            run,user,branch,writes,logs=self.setup_run()
            if mode=='unowned':run.reference_ids[-1].ownership_kind='reused'
            elif mode=='foreign':branch.company_id=NS(id=9)
            elif mode=='duplicate':run.reference_ids.append(run.reference_ids[-1])
            else:run.reference_ids[0].ownership_kind='reused'
            with self.assertRaises(ValueError):space['prepare_telemedicine_scope'](run)
            self.assertFalse(writes)
    def test_both_entry_paths_prepare_scope(self):
        for p in ['services/journey_engine.py','generators/clinical/advanced.py']:
            self.assertIn('prepare_telemedicine_scope(', (ROOT/p).read_text())
if __name__=='__main__':unittest.main()



