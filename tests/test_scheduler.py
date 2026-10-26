import datetime as dt
import pathlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from tyrion import core,workflow_scheduler as ws,bridge


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_db,self.old_data=core.DB,core.DATA
        core.DATA=pathlib.Path(self.tmp.name)
        core.DB=core.DATA/'test.sqlite3'
        ws.setup()

    def tearDown(self):
        core.DB,core.DATA=self.old_db,self.old_data
        self.tmp.cleanup()

    def add(self,**args):
        fields={'title':'Sample controlled blog','project':'CooCoo Babys','kind':'blog_draft',
          'instructions':'Create an educational parenting article with originality and review requirements',
          'cadence':'daily','time_local':'20:00','timezone':'Asia/Karachi'}
        fields.update(args)
        return ws.create_schedule(**fields)

    def test_more_than_five_independent_schedules(self):
        for n in range(8):self.add(title=f"Tyrion workflow {n}")
        self.assertEqual(len(ws.list_schedules()),8)
        self.assertEqual(len([s for s in ws.list_schedules() if s['enabled']]),8)

    def test_time_timezone_and_recurrence(self):
        now=dt.datetime(2026,10,24,12,0,tzinfo=dt.timezone.utc)
        n=ws.next_occurrence('daily','20:00','Asia/Karachi',after=now)
        self.assertEqual(n,'2026-10-24T15:00:00+00:00')
        tomorrow=ws.next_occurrence('daily','20:00','Asia/Karachi',after=dt.datetime(2026,10,24,15,1,tzinfo=dt.timezone.utc))
        self.assertEqual(tomorrow,'2026-10-25T15:00:00+00:00')
        monday=ws.next_occurrence('weekly','20:00','Asia/Karachi',[0],after=now)
        self.assertEqual(monday,'2026-10-26T15:00:00+00:00')

    def test_due_queue_once_and_dedup(self):
        x=self.add()
        now=ws.parse_utc(x['next_run_utc'])+dt.timedelta(seconds=2)
        jobs=ws.enqueue_due(now_override=now)
        self.assertEqual(len(jobs),1)
        self.assertEqual(ws.enqueue_due(now_override=now),[])
        self.assertEqual(ws.run_detail(jobs[0])['status'],'awaiting_chatgpt')
        self.assertEqual(len(ws.pending_chatgpt()),1)
        self.assertGreater(ws.parse_utc(ws.get_schedule(x['id'])['next_run_utc']),now)

    def test_handoff_submission_saves_local_markdown(self):
        x=self.add()
        r=ws.run_now(x['id'])
        result=ws.submit_chatgpt_result(r['id'],'Original New Baby Routine',
               '## Introducing a simple routine\n\n'+('Practical, clearly explained and fact-checked guidance. '*14))
        self.assertEqual(result['status'],'draft_ready')
        self.assertTrue(pathlib.Path(result['output_path']).read_text().startswith('# Original New Baby Routine'))
        self.assertTrue(str(pathlib.Path(result['output_path']).resolve()).startswith(str(core.DATA.resolve())))
        with self.assertRaises(ValueError):ws.submit_chatgpt_result(r['id'],'Duplicate submission','Long '*90)

    def test_one_time_run_and_weekday_validation(self):
        with self.assertRaises(ValueError):self.add(cadence='weekly',weekdays=[9])
        with self.assertRaises(ValueError):self.add(cadence='once',once_date='2020-01-01')
        with self.assertRaises(ValueError):self.add(time_local='99:00')

    def test_pending_queue_prevents_runaway(self):
        x=self.add()
        for i in range(3):
            ws.run_now(x['id'])
        with self.assertRaises(ValueError):ws.run_now(x['id'])

    def test_local_engine_requires_explicit_local_model(self):
        with self.assertRaises(ValueError):self.add(engine='ollama_local',model='gemma4:cloud')
        x=self.add(engine='ollama_local',model='qwen3.5:4b')
        r=ws.run_now(x['id'])
        self.assertEqual(r['status'],'generating')
        self.assertEqual(r['engine'],'ollama_local')

    def test_local_draft_then_chatgpt_review_cycle(self):
        job=self.add(engine='ollama_local',model='qwen3.5:0.8b')
        run=ws.run_now(job['id'])
        model_result='# Practical Parenting Checklist\n\n'+('Practical content that needs an editor to check facts and overlap. '*35)
        def fake_urlopen(req,timeout=0):
            if req.full_url.endswith('/api/tags'):
                return io.BytesIO(json.dumps({'models':[{'name':'qwen3.5:0.8b'}]}).encode())
            self.assertIn('/api/generate',req.full_url)
            payload=json.loads(req.data)
            self.assertEqual(payload.get('think'),False)
            return io.BytesIO(json.dumps({'response':model_result}).encode())
        with patch('tyrion.workflow_scheduler.urllib.request.urlopen',side_effect=fake_urlopen):
            ws._generate_model_draft(run['id'])
        status=ws.run_detail(run['id'])
        self.assertEqual(status['status'],'draft_ready')
        self.assertEqual(len(bridge.call('tyrion_review_queue',{})),1)
        original=bridge.call('tyrion_read_run_draft',{'run_id':run['id']})
        self.assertIn('Checklist',original['markdown'])
        old_path=pathlib.Path(status['output_path'])
        updated=bridge.call('tyrion_revise_run_draft',{'run_id':run['id'],
             'title':'Reviewed Checklist for New Families',
             'markdown':'## Reviewed guidance\n\n'+('Edited paragraphs with notes for future source review. '*24)})
        self.assertEqual(updated['status'],'draft_ready')
        self.assertTrue(old_path.exists())
        self.assertNotEqual(str(old_path),updated['output_path'])

    def test_seed_no_duplication(self):
        ws.seed_coocoobabys()
        ws.seed_coocoobabys()
        self.assertEqual(len(ws.list_schedules()),1)
        self.assertEqual(ws.list_schedules()[0]['time_local'],'20:00')

    def test_edit_and_archive_preserves_history(self):
        sched=self.add()
        old=ws.run_now(sched['id'])
        revised=ws.update_schedule(sched['id'],{"title":"Revised daily content task","time_local":"19:15"})
        self.assertEqual(revised["time_local"],"19:15")
        self.assertEqual(ws.run_detail(old["id"])["status"],"awaiting_chatgpt")
        archived=ws.archive_schedule(sched['id'])
        self.assertTrue(archived['archived'])
        self.assertEqual(len(ws.list_schedules()),0)
        self.assertEqual(ws.run_detail(old['id'])['status'],'cancelled')
        with self.assertRaises(ValueError):ws.run_now(sched['id'])

    def test_bridge_tools_exist(self):
        names={x['name'] for x in bridge.TOOLS}
        self.assertIn('tyrion_due_chatgpt_work',names)
        self.assertIn('tyrion_submit_blog_draft',names)
        self.assertIn('tyrion_create_schedule',names)


if __name__=='__main__':unittest.main()
