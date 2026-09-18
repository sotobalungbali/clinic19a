"""Execute owner overrides with strict native signature doubles and hook checks."""
import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
OWNER=ROOT.parent/'clinic_inventory/models/stock_move.py'
tree=ast.parse(OWNER.read_text())
node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='StockMove')
methods=[n for n in node.body if isinstance(n,ast.FunctionDef) and n.name in ('_action_confirm','_action_assign','_action_done')]
class NativeMove:
    def __init__(self,empty=False):self.events=[];self.empty=empty
    def __iter__(self):return iter([] if self.empty else [self])
    def _clinic_pre_confirm_checks(self):self.events.append('pre_confirm')
    def _clinic_hook_post_confirm(self):self.events.append('post_confirm')
    def _clinic_validate_expiration_on_reserved_lots(self):self.events.append('expiration')
    def _clinic_pre_done_checks(self):self.events.append('pre_done')
    def _clinic_hook_post_done(self):self.events.append('post_done')
    def _action_confirm(self,merge=True,merge_into=False,create_proc=True):
        self.events.append(('confirm',merge,merge_into,create_proc));return self
    def _action_assign(self,force_qty=False):self.events.append(('assign',force_qty));return self
    def _action_done(self,cancel_backorder=False):
        # Native stock invokes confirmation even for an empty backorder set.
        self._action_confirm(merge=False,create_proc=False)
        self.events.append(('done',cancel_backorder));return self
ns={'NativeMove':NativeMove}
cls=ast.ClassDef(name='StockMove',bases=[ast.Name(id='NativeMove',ctx=ast.Load())],keywords=[],body=methods,decorator_list=[])
exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),'<owner>','exec'),ns)
StockMove=ns['StockMove']
class StockOwnerContracts(unittest.TestCase):
    def test_confirm_forwards_all_keywords_and_preserves_hooks(self):
        m=StockMove();self.assertIs(m._action_confirm(False,'target',False),m)
        self.assertEqual(m.events,['pre_confirm',('confirm',False,'target',False),'post_confirm'])
    def test_native_empty_backorder_call_and_defaults(self):
        m=StockMove(True);self.assertIs(m._action_done(),m)
        self.assertEqual(m.events,[('confirm',False,False,False),('done',False)])
        m=StockMove();m._action_confirm();self.assertIn(('confirm',True,False,True),m.events)
    def test_reservation_force_qty_and_expiration_checks(self):
        m=StockMove();self.assertIs(m._action_assign(force_qty=3),m)
        self.assertEqual(m.events,[('assign',3),'expiration'])
    def test_done_hooks_and_cancel_flag_preserved(self):
        m=StockMove();m._action_done(cancel_backorder=True)
        self.assertEqual(m.events[0],'pre_done');self.assertEqual(m.events[-1],'post_done')
        self.assertIn(('done',True),m.events)

if __name__=='__main__':unittest.main()









