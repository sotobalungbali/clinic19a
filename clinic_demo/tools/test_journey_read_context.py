"""Functional-reader regression tests; native database validation is separate."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

ROOT=Path(__file__).resolve().parents[1]
space={'UserError':ValueError}
tree=ast.parse((ROOT/'services/journey_read_context.py').read_text())
tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
exec(compile(tree,'read_context','exec'),space)

class Refs(list):
    def filtered(self,fn):return Refs(x for x in self if fn(x))
    def __getattr__(self,key):
        assert len(self)==1
        return getattr(self[0],key)

class Model:
    def __init__(self,actor=None):self.actor=actor;self.calls=[]
    def browse(self,record_id):self.calls.append(('browse',record_id));return self
    def exists(self):return self.actor
    def with_user(self,user):self.calls.append(('user',user));return self
    def with_company(self,company):self.calls.append(('company',company));return self
    def with_context(self,**kw):self.calls.append(('context',kw));return self

class ReadContracts(unittest.TestCase):
    def test_explicit_actors_across_owner_domains(self):
        cases=[('master.catalog','clinic.emar.medication.profile','DEMO-USER-MGR'),
               ('master.commercial','membership.plan','DEMO-USER-MGR'),
               ('clinical.emar','clinic.emar.administration','DEMO-USER-NUR-001'),
               ('clinical.emar','clinic.emar.order','DEMO-USER-DOC-001'),
               ('clinical.emar','clinic.emar.schedule','DEMO-USER-MGR'),
               ('clinical.care_postcare','clinic.postcare.plan','DEMO-USER-MGR'),
               ('clinical.telemedicine','clinic.telemedicine.message','DEMO-USER-DOC-001'),
               ('commercial.ap','clinic.ap','DEMO-USER-MGR'),
               ('management.reports','clinic.report.run','DEMO-USER-MGR'),
               ('management.reports','stock.move','DEMO-USER-MGR'),
               ('foundation.native','res.company',None)]
        for gen,model,want in cases:
            self.assertEqual(space['actor_key'](NS(generator_key=gen,model_name=model)),want)

    def setup_reader(self,ownership='created',companies=True,count=1):
        company=NS(id=7);actor=NS(active=True,company_ids=[company] if companies else [])
        refs=Refs([NS(demo_key='DEMO-USER-MGR',model_name='res.users',ownership_kind=ownership,res_id=71)]*count)
        target=Model();users=Model(actor)
        run=NS(company_id=company,reference_ids=refs,env={'res.users':users,'clinic.emar.medication.profile':target})
        ref=NS(generator_key='master.catalog',model_name='clinic.emar.medication.profile')
        return run,ref,target,actor

    def test_profile_inspection_selects_manager_and_exact_company(self):
        run,ref,target,actor=self.setup_reader()
        self.assertIs(space['read_model'](run,ref),target)
        self.assertEqual(target.calls[0],('user',actor))
        self.assertEqual(target.calls[-1][1],dict(allowed_company_ids=[7],active_test=False,prefetch_fields=False))

    def test_missing_ambiguous_reused_or_cross_company_actor_blocks_without_fallback(self):
        for kw in ({'count':0},{'count':2},{'ownership':'reused'},{'companies':False}):
            run,ref,target,_=self.setup_reader(**kw)
            with self.assertRaises(ValueError):space['read_model'](run,ref)
            self.assertFalse(target.calls)

    def test_inspection_and_reporting_share_policy_without_privilege_mutations(self):
        for filename in ['journey_engine.py','reporting_sufficiency.py']:
            text=(ROOT/'services'/filename).read_text()
            self.assertIn('read_model(run,ref)',text)
        helper=(ROOT/'services/journey_read_context.py').read_text()
        for forbidden in ['.sudo(','.write(','.create(','.unlink(']:self.assertNotIn(forbidden,helper)

    def test_treatment_session_reader_tracks_declared_booking(self):
        for key,booking in [('DEMO-SESSION-001','002'),('DEMO-SESSION-LINE-001','002'),('DEMO-SESSION-NOSHOW-001','004'),('DEMO-SESSION-CANCEL-001','005')]:
            ref=NS(generator_key='operations.treatment_session',model_name='clinic.treatment.session',demo_key=key)
            self.assertEqual(space['actor_key'](ref),'booking_doctor:DEMO-BOOK-TODAY-'+booking)
        with self.assertRaises(ValueError):
            space['actor_key'](NS(generator_key='operations.treatment_session',model_name='clinic.treatment.session',demo_key='UNKNOWN'))

    def test_encounter_postcare_uses_owner_manager(self):
        self.assertEqual(space['actor_key'](NS(generator_key='operations.encounter',model_name='clinic.postcare.plan')),'DEMO-USER-MGR')

    def test_v53_supported_lineage_survives_v54_upgrade(self):
        ns={};source=(ROOT/'services/build_adoption_service.py').read_text()
        tree=ast.parse(source);tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
        exec(compile(tree,'adoption','exec'),ns)
        self.assertIn('19.0.1.0.53',ns['SUPPORTED_LINEAGE']['f61e5c5a23b01744e5cc3111e5f34dd6c2274014a2de8efd6013743987204a1c'])

if __name__=='__main__':unittest.main()







