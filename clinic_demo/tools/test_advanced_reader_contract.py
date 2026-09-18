"""Execute actual resolver and validators against actor-enforcing record doubles."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
ROOT=Path(__file__).resolve().parents[1]

def functions(path,cls):
    tree=ast.parse(path.read_text());node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
    return [n for n in node.body if isinstance(n,ast.FunctionDef)]

class Record:
    def __init__(self,reader,expected,**values):self.reader=reader;self.expected=expected;self.values=values
    def __getattr__(self,key):
        if self.reader!=self.expected:raise PermissionError('wrong reader for '+key)
        return self.values[key]
    def with_company(self,company):return self
    def with_context(self,**kw):return self

class AdvancedReaders(unittest.TestCase):
    def setup_owner(self,explicit=None):
        policy={};tree=ast.parse((ROOT/'services/journey_read_context.py').read_text());tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))];policy['UserError']=ValueError;exec(compile(tree,'policy','exec'),policy)
        refs={
            'DEMO-EMAR-ORDER-001':NS(generator_key='clinical.emar',model_name='clinic.emar.order'),
            'DEMO-EMAR-ADMIN-001':NS(generator_key='clinical.emar',model_name='clinic.emar.administration'),
            'DEMO-MED-PROFILE-PARA-500':NS(generator_key='master.catalog',model_name='clinic.emar.medication.profile'),
        }
        calls=[]
        def resolve(run,key,model,missing_ok=False,record_user=None):
            calls.append(record_user)
            if key not in refs:return False
            expected=policy['actor_key'](refs[key]);return Record(record_user,expected,state='active' if model=='clinic.emar.order' else 'done',line_ids=[1])
        ctx=NS(run=NS(company_id=NS(id=4)),reference_service=NS(_reference=lambda run,key:refs.get(key),resolve=resolve))
        ns={'actor_key':policy['actor_key'],'read_model':lambda run,ref:NS(env=NS(user=policy['actor_key'](ref)))}
        fn=next(n for n in functions(ROOT/'generators/clinical/advanced.py','AdvancedClinicalBase') if n.name=='_resolve')
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'resolver','exec'),ns)
        owner=NS(_as_actor=lambda record,user:record)
        owner._resolve=lambda *args,**kwargs:ns['_resolve'](owner,*args,**kwargs)
        return owner,ctx,calls

    def test_actual_emar_validator_reads_order_and_administration_as_different_actors(self):
        owner,ctx,calls=self.setup_owner();fn=next(n for n in functions(ROOT/'generators/clinical/advanced.py','AdvancedEmarGenerator') if n.name=='validate')
        ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'validator','exec'),ns)
        self.assertEqual(ns['validate'](owner,ctx,None),[])
        self.assertEqual(calls,['DEMO-USER-DOC-001','DEMO-USER-NUR-001'])

    def test_prerequisite_profile_uses_catalog_manager(self):
        owner,ctx,calls=self.setup_owner()
        rec=owner._resolve(ctx,'DEMO-MED-PROFILE-PARA-500','clinic.emar.medication.profile')
        self.assertEqual(rec.state,'done');self.assertEqual(calls,['DEMO-USER-MGR'])

    def test_explicit_actor_and_missing_identity_semantics_are_preserved(self):
        owner,ctx,calls=self.setup_owner()
        owner._resolve(ctx,'DEMO-EMAR-ORDER-001','clinic.emar.order',record_user='explicit')
        self.assertEqual(calls,['explicit'])
        self.assertFalse(owner._resolve(ctx,'MISSING','clinic.emar.order',missing_ok=True))

if __name__=='__main__':unittest.main()




