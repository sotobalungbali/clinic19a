import ast
from pathlib import Path
from types import SimpleNamespace as NS
import re
import unittest
ROOT=Path(__file__).resolve().parents[1].parent
SOURCE=ROOT/'clinic_reports/models/report_run.py'
tree=ast.parse(SOURCE.read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
cls.bases=[];cls.decorator_list=[];cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('_add_metric','_metric_code')]
scope={'re':re,'UserError':ValueError,'_':lambda x:x}
exec(compile(ast.Module(body=[cls],type_ignores=[]),'report','exec'),scope)
Owner=scope[cls.name]
class Record:
    def __init__(self,i,v):self.id=i;self.values=v.copy()
    def ensure_one(self):pass
    def write(self,v):self.values.update(v)
class Metric:
    def __init__(self):self.rows=[]
    def sudo(self):return self
    def with_context(self,**kw):return self
    def search(self,d):
        return next((r for r in self.rows if all(r.values[k]==v for k,op,v in d)),False)
    def create(self,v):
        r=Record(len(self.rows)+1,v);self.rows.append(r);return r
class Env(dict):pass
class Refresh(unittest.TestCase):
    def setup_owner(self):
        m=Metric();o=Owner();o.id=7;o.ensure_one=lambda:None;o.env=Env({'clinic.report.metric':m})
        o.env.context={'report_runtime':{'metric_codes':set()}}
        return o,m
    def test_refresh_preserves_referenced_identity_and_updates_value(self):
        o,m=self.setup_owner();r=o._add_metric('REV','Revenue',5);snapshot=NS(metric=r,value=5)
        for v in (12,12,0):
            o.env.context['report_runtime']={'metric_codes':set()}
            updated=o._add_metric('REV','Revenue',v)
            self.assertIs(updated,snapshot.metric);self.assertEqual(updated.values['value'],v)
            self.assertEqual(snapshot.value,5);self.assertEqual(len(m.rows),1)
    def test_new_codes_create_and_other_runs_are_not_modified(self):
        o,m=self.setup_owner();old=m.create(dict(run_id=8,code='REV',value=3))
        o._add_metric('REV','Revenue',10);o._add_metric('COUNT','Count',1)
        self.assertEqual(len(m.rows),3);self.assertEqual(old.values['value'],3)
    def test_duplicate_normalized_codes_fail(self):
        o,m=self.setup_owner();o._add_metric('net rev','Revenue',1)
        with self.assertRaisesRegex(ValueError,'Duplicate'):o._add_metric('NET-REV','Revenue',2)
        self.assertEqual(len(m.rows),1)
    def test_generation_retires_only_unemitted_codes_inside_savepoint(self):
        text=SOURCE.read_text();action=text[text.index('    def action_generate'):text.index('    def action_finalize')]
        self.assertNotIn('run.metric_ids.sudo().with_context(report_generation=True).unlink()',action)
        self.assertIn('metric.code not in runtime["metric_codes"]',action)
        self.assertLess(action.index('with self.env.cr.savepoint()'),action.index('obsolete.sudo()'))
        self.assertLess(action.index('obsolete.sudo()'),action.index('run._refresh_csv()'))
        self.assertIn('run.state == "finalized"',action)
        line=(ROOT/'clinic_dashboard/models/dashboard_snapshot_line.py').read_text()
        self.assertIn('ondelete="restrict"',line[line.index('    metric_id ='):line.index('    value =')])
if __name__=='__main__':unittest.main()
