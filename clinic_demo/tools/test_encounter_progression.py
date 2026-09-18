import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from lxml import etree
ROOT=Path(__file__).resolve().parents[1]

class Records(list):
    def filtered(self,fn):return Records(x for x in self if fn(x))
    def __getattr__(self,key):
        assert len(self)==1
        return getattr(self[0],key)

class Progression(unittest.TestCase):
    def setup_case(self):
        tree=ast.parse((ROOT/'generators/operations/encounter.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_treatment_completion_issues')
        ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'completion','exec'),ns)
        partner=NS(_name='res.partner',id=3)
        patient=NS(_name='clinic.patient',id=3,partner_id=partner)
        booking=NS(doctor_id=NS(user_id=7),patient_id=partner)
        enc=NS(patient_id=patient,date_start=10,date_end=20,procedure_line_ids=Records([NS(state='done')]))
        session=NS(state='done',encounter_id=enc,booking_id=booking,company_id=1,patient_id=partner,clinic_patient_id=patient,actual_start_datetime=10,actual_end_datetime=20)
        ref=NS(demo_key='DEMO-SESSION-001',model_name='clinic.treatment.session',generator_key='operations.treatment_session')
        ctx=NS(run=NS(company_id=1,reference_ids=Records([ref])))
        owner=NS(_resolve=lambda ctx,key,model,**kw: booking if model=='booking.booking' else session)
        return lambda:not ns[fn.name](owner,ctx,enc),session,enc,ctx

    def test_completed_downstream_evidence_is_accepted(self):
        validate,*_=self.setup_case();self.assertTrue(validate())

    def test_completion_without_matching_evidence_is_rejected(self):
        for field,value in [('state','in_progress'),('encounter_id',None),('booking_id',None),('company_id',2),('patient_id',4),('clinic_patient_id',4),('actual_end_datetime',9)]:
            validate,session,enc,ctx=self.setup_case();setattr(session,field,value)
            self.assertFalse(validate(),field)
        validate,session,enc,ctx=self.setup_case();ctx.run.reference_ids=Records();self.assertFalse(validate())
        validate,session,enc,ctx=self.setup_case();enc.procedure_line_ids=Records();self.assertFalse(validate())

    def test_patient_comparison_is_typed_even_when_numeric_ids_match(self):
        validate,session,enc,ctx=self.setup_case()
        self.assertEqual(session.patient_id.id,enc.patient_id.id)
        self.assertNotEqual(session.patient_id,enc.patient_id)
        self.assertTrue(validate())
        session.patient_id=enc.patient_id
        self.assertFalse(validate())

    def test_owner_sources_declare_different_patient_comodels(self):
        suite=ROOT.parent
        enc=(suite/'clinic_encounter/models/encounter.py').read_text()
        session=(suite/'clinic_treatment_session/models/treatment_session.py').read_text()
        canonical=(suite/'clinic_treatment_session/models/enterprise_session.py').read_text()
        self.assertRegex(enc,r'patient_id = fields.Many2one\(\s*"clinic.patient"')
        self.assertRegex(session,r'patient_id = fields.Many2one\("res.partner"')
        self.assertRegex(canonical,r'clinic_patient_id = fields.Many2one\(\s*"clinic.patient"')

    def test_progress_navigation_is_at_top_and_retains_existing_tab(self):
        view=etree.parse(str(ROOT/'views/demo_journey_views.xml'))
        self.assertTrue(view.xpath('//xpath[@expr="//header"]//button[@name="action_open_journeys"]'))
        self.assertTrue(view.xpath('//xpath[contains(@expr,"button_box")]//button[@name="action_open_journeys"]'))
        self.assertTrue(view.xpath('//page[@string="Journey Progress"]'))

if __name__=='__main__':unittest.main()






