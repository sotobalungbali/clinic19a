"""Behavior tests execute the actual validator without a native Odoo server."""
import ast
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import pytz
ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT/'generators/operations/future_pipeline.py').read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
cls.decorator_list=[]; cls.bases=[]
cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in {'_utc','_followup_issues'}]
space=dict(datetime=datetime,time=time,timedelta=timedelta,pytz=pytz)
exec(compile(ast.Module(body=[cls],type_ignores=[]),'future_pipeline','exec'),space)

class FutureLifecycle(unittest.TestCase):
    def setUp(self):
        self.g=space['FuturePipelineGenerator']()
        self.ctx=NS(run=NS(anchor_date=date(2026,8,27),timezone='Europe/Brussels',company_id=1))
    def task(self,offset,state='pending'):
        return NS(state=state,completed_at=False,sent_at=False,contacted_at=False,send_count=0,
            due_datetime=self.g._utc(self.ctx,offset),reference=f'DEMO-FUT-FOLLOWUP-{offset:03d}',
            plan_id=2,assignee_id=3,company_id=1,channel='internal',auto_send=False,escalate_if_overdue=False)
    def issues(self,t,n=1):return self.g._followup_issues(self.ctx,t,n,2,3)
    def test_all_six_offsets_survive_owner_cron_without_mutation(self):
        for n in (1,7,14,30,60,90):
            for state in ('pending','scheduled','due'):
                t=self.task(n,state);before=vars(t).copy()
                self.assertEqual(self.issues(t,n),[])
                self.assertEqual(self.issues(t,n),[])
                self.assertEqual(vars(t),before)
    def test_delivery_and_terminal_states_are_never_adopted(self):
        for state in ('sent','contacted','completed','overdue','escalated','cancelled'):
            self.assertTrue(self.issues(self.task(1,state)))
        for field in ('completed_at','sent_at','contacted_at','send_count'):
            t=self.task(1,'due');setattr(t,field,1)
            self.assertTrue(self.issues(t))
    def test_corrupt_scope_schedule_or_safety_blocks(self):
        for field,value in [('reference','OTHER'),('plan_id',7),('assignee_id',8),('company_id',9),
                ('channel','email'),('auto_send',True),('escalate_if_overdue',True),('due_datetime',False)]:
            t=self.task(1);setattr(t,field,value)
            self.assertTrue(self.issues(t),field)
        self.assertTrue(self.issues(False))
    def test_exact_utc_deadline_across_timezones_and_dst(self):
        for tz in ('Pacific/Kiritimati','America/Los_Angeles','Europe/Brussels'):
            self.ctx.run.timezone=tz
            for n in (1,7,14,30,60,90):
                t=self.task(n)
                self.assertFalse(self.issues(t,n))
                t.due_datetime+=timedelta(hours=1)
                self.assertTrue(self.issues(t,n))
    def test_owner_cron_transition_is_open_due_even_without_auto_send(self):
        text=(ROOT.parent/'clinic_post_care_followup/models/task.py').read_text()
        cron=text[text.index('    def _cron_process_due_tasks'):]
        self.assertIn('"state": "due"',cron)
        self.assertIn('task._schedule_staff_activity()',cron)
        self.assertIn('("escalate_if_overdue", "=", True)',cron)
if __name__=='__main__': unittest.main()


