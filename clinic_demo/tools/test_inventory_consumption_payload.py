"""Execute owner payload methods as one template→variant→usage-line chain."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
ROOT=Path(__file__).resolve().parents[1].parent

def method(filename,name):
    tree=ast.parse((ROOT/'clinic_inventory/models'/filename).read_text())
    node=next(n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body
              if isinstance(n,ast.FunctionDef) and n.name==name)
    node.decorator_list=[]
    scope={'_':lambda s:s,'UserError':ValueError}
    exec(compile(ast.Module(body=[node],type_ignores=[]),filename,'exec'),scope)
    return scope[name]
class Base:
    def ensure_one(self):pass
class Template(Base):
    _clinic_hook_prepare_consumption_vals=method('product_template.py','_clinic_hook_prepare_consumption_vals')
    clinic_prepare_consumption_move_vals=method('product_template.py','clinic_prepare_consumption_move_vals')
class Product(Base):
    clinic_prepare_consumption_move_vals=method('product_product.py','clinic_prepare_consumption_move_vals')
    def _clinic_hook_finalize_consumption_vals(self,vals,**kw):return vals
class Line(Base):
    _prepare_consumption_move_vals=method('treatment_product_usage.py','_prepare_consumption_move_vals')
class Payload(unittest.TestCase):
    def setup_chain(self):
        t=Template();p=Product();line=Line();uom=NS(id=6)
        p.id=8;p.uom_id=uom;p.display_name='Demo gauze';p.product_tmpl_id=t
        t.product_variant_id=p;t.display_name='Demo gauze'
        line.product_id=p;line.product_uom=uom;line.product_uom_qty=1
        line.usage_id=NS(id=30)
        usage=NS(treatment_ref=False,patient_id=NS(id=4),doctor_id=False)
        return t,p,line,usage
    def test_full_owner_chain_has_origin_and_no_legacy_name(self):
        t,p,line,usage=self.setup_chain()
        for count in range(2):
            vals=line._prepare_consumption_move_vals(usage,NS(id=11),NS(id=12))
            self.assertEqual(vals,dict(product_id=8,product_uom_qty=1,product_uom=6,
                origin='Clinical consumption of Demo gauze',location_id=11,location_dest_id=12))
    def test_both_apis_reject_missing_quantity(self):
        t,p,line,usage=self.setup_chain()
        original=t._clinic_hook_prepare_consumption_vals
        def bad(**kw):
            vals=original(**kw);vals.pop('product_uom_qty');return vals
        t._clinic_hook_prepare_consumption_vals=bad
        for obj in (t,p):
            with self.assertRaisesRegex(ValueError,'product_uom_qty'):
                obj.clinic_prepare_consumption_move_vals(qty=1)
    def test_variant_finalizer_cannot_remove_required_uom(self):
        t,p,line,usage=self.setup_chain()
        def bad(vals,**kw):vals.pop('product_uom');return vals
        p._clinic_hook_finalize_consumption_vals=bad
        with self.assertRaisesRegex(ValueError,'product_uom'):
            p.clinic_prepare_consumption_move_vals(qty=1)
    def test_variant_identity_and_hook_extension_survive(self):
        t,p,line,usage=self.setup_chain()
        t.product_variant_id=NS(id=99,uom_id=p.uom_id)
        def enrich(vals,**kw):vals['clinic_usage_id']=30;return vals
        p._clinic_hook_finalize_consumption_vals=enrich
        vals=p.clinic_prepare_consumption_move_vals(qty=2)
        self.assertEqual(vals['product_id'],8);self.assertEqual(vals['product_uom_qty'],2)
        self.assertEqual(vals['clinic_usage_id'],30);self.assertNotIn('name',vals)
if __name__=='__main__':unittest.main()

