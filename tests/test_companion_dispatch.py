"""Durable Tyrion Chat handoff queue with exactly-one claim and explicit recovery."""
import pathlib,tempfile,threading,unittest
from tyrion import core,companion_dispatch as dispatch,workflow_scheduler as workflows
class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=(core.DATA,core.DB)
        core.DATA=pathlib.Path(self.tmp.name)
        core.DB=core.DATA/'dispatch.sqlite3'
        workflows.setup()
        dispatch.setup()
    def tearDown(self):
        core.DATA,core.DB=self.old
        self.tmp.cleanup()
    def test_new_phone_task_stays_queued_and_claimed_once(self):
        task=core.create_task('Phone queue test',source='dashboard',instructions='Only verify shared state.')
        initial=dispatch.list_queue()
        self.assertEqual(len(initial),1)
        self.assertEqual(initial[0]['status'],'queued')
        self.assertEqual(initial[0]['entity_id'],task['id'])
        result=dispatch.claim()
        self.assertEqual(result['entity_id'],task['id'])
        self.assertIsNone(dispatch.claim())
        self.assertEqual(dispatch.report(result['id'],'opened',tab_id=123)['status'],'opened')
        self.assertEqual(dispatch.report(result['id'],'submitted',tab_id=123)['status'],'submitted')
        core.add_task_update(task['id'],'Verified phone-to-PC delivery through Tyrion.','chatgpt')
        self.assertEqual(dispatch.list_queue()[0]['status'],'progressing')
        core.set_task_status(task['id'],'done')
        self.assertEqual(dispatch.list_queue()[0]['status'],'completed')
        self.assertIsNone(dispatch.claim())
        self.assertEqual(len(dispatch.list_queue()),1)
    def test_no_age_filter_and_operator_retry_only(self):
        task=core.create_task('Old persistent task',source='dashboard')
        with core.connection() as db:
            db.execute("UPDATE tasks SET created_at='2020-01-01T00:00:00+00:00' WHERE id=?",(task['id'],))
            db.commit()
        claim=dispatch.claim()
        self.assertEqual(claim['entity_id'],task['id'])
        self.assertIsNone(dispatch.claim())
        dispatch.report(claim['id'],'needs_attention',error='Chrome offline')
        self.assertIsNone(dispatch.claim())
        dispatch.manual('task',task['id'],'retry')
        second=dispatch.claim()
        self.assertEqual(second['id'],claim['id'])
        self.assertEqual(dispatch.list_queue()[0]['attempt'],2)
    def test_cannot_requeue_completed_and_prevent_mcp_loop(self):
        task=core.create_task('Internal MCP followup',source='mcp')
        self.assertFalse(dispatch.list_queue())
        dispatch.manual('task',task['id'],'queue')
        self.assertEqual(len(dispatch.list_queue()),1)
        core.set_task_status(task['id'],'done')
        with self.assertRaises(ValueError):dispatch.manual('task',task['id'],'retry')
        with self.assertRaises(ValueError):dispatch.enqueue('task',task['id'],requested=True)
    def test_claim_is_exclusive_concurrently(self):
        task=core.create_task('Atomic dispatch claim',source='dashboard')
        responses=[]
        def worker():responses.append(dispatch.claim())
        a=threading.Thread(target=worker);b=threading.Thread(target=worker)
        a.start();b.start();a.join();b.join()
        self.assertEqual(sum(bool(v) for v in responses),1)
    def test_invalid_transition_rejected(self):
        task=core.create_task('Transition validation',source='dashboard')
        item=dispatch.list_queue()[0]
        with self.assertRaises(ValueError):dispatch.report(item['id'],'submitted')
        with self.assertRaises(ValueError):dispatch.report(item['id'],'completed')
if __name__=='__main__':unittest.main()
