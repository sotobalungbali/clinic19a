"""Execute actor reconciliation without relying on an administrator actor."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/'generators/management/source_journeys.py').read_text())
GROUPS=next(ast.literal_eval(n.value) for n in TREE.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GROUPS' for t in n.targets))
CLS=next(n for n in TREE.body if isinstance(n,ast.ClassDef))
FN=next(n for n in CLS.body if isinstance(n,ast.FunctionDef) and n.name=='_prepare_actor')
ns={'GROUPS':GROUPS,'UserError':ValueError}
exec(compile(ast.Module(body=[FN],type_ignores=[]),'<actor>','exec'),ns)

class SourceActorContracts(unittest.TestCase):
    def actor(self,missing=None):
        groups={xmlid:NS(id=i+1) for i,xmlid in enumerate(GROUPS)}
        manager=NS(group_ids=[]);writes=[]
        def write(values):
            writes.append(values)
            for op,gid in values['group_ids']:
                self.assertEqual(op,4)
                manager.group_ids.append(next(g for g in groups.values() if g.id==gid))
        manager.write=write
        env=NS(ref=lambda key,raise_if_not_found=False:False if key==missing else groups[key])
        return NS(ctx=NS(env=env),manager=manager),groups,writes

    def test_functional_entitlement_is_idempotent(self):
        actor,groups,writes=self.actor()
        ns['_prepare_actor'](actor)
        self.assertIn(groups['product.group_product_manager'],actor.manager.group_ids)
        self.assertNotIn('base.group_system',GROUPS)
        self.assertEqual(len(writes),1)
        ns['_prepare_actor'](actor);self.assertEqual(len(writes),1)

    def test_missing_group_blocks_before_partial_assignment(self):
        actor,_,writes=self.actor('product.group_product_manager')
        with self.assertRaisesRegex(ValueError,'product.group_product_manager'):ns['_prepare_actor'](actor)
        self.assertFalse(writes)

    def test_delegated_product_model_and_preflight_order(self):
        contracts=next(ast.literal_eval(n.value) for n in TREE.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CONTRACTS' for t in n.targets))
        self.assertTrue({'product.product','product.template','product.category'}<=set(contracts))
        self.assertIn('product_tmpl_id',contracts['product.product'].split())
        fn=next(n for n in CLS.body if isinstance(n,ast.FunctionDef) and n.name=='preflight')
        body=ast.unparse(fn)
        self.assertLess(body.index('self._prepare_actor()'),body.index('for name, fields in CONTRACTS.items()'))
        self.assertIn("('product.product', 'product_tmpl_id'): 'product.template'",body)

if __name__=='__main__':unittest.main()










