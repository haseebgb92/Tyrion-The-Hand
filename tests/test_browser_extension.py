import pathlib
import tempfile
import unittest
from tyrion import core,workflow_scheduler,extension_bridge

class ExtensionBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_data,self.old_db=core.DATA,core.DB
        core.DATA=pathlib.Path(self.tmp.name);core.DB=core.DATA/'browser.sqlite3'
        workflow_scheduler.setup()
    def tearDown(self):
        core.DATA,core.DB=self.old_data,self.old_db
        self.tmp.cleanup()
    def test_private_pairing_and_unauthorized_rejection(self):
        token=extension_bridge.get_pairing_key()
        self.assertTrue(extension_bridge.validate(token))
        self.assertFalse(extension_bridge.validate('bad'))
        self.assertFalse(extension_bridge.validate(token+'suffix'))
        self.assertEqual(token,extension_bridge.get_pairing_key())
        mode=oct(extension_bridge.setup().stat().st_mode & 0o777)
        self.assertEqual(mode,'0o600')
    def test_task_handoff_uses_original_id_and_notes(self):
        task=core.create_task('Review product media','Glissimo',instructions='Review photo references, report only verified issues.')
        core.add_task_update(task['id'],'The initial screenshots were reviewed.','chatgpt')
        p=extension_bridge.handoff('task',task['id'])
        self.assertEqual(p['id'],task['id'])
        self.assertIn('TASK #'+str(task['id']),p['text'])
        self.assertIn('The initial screenshots were reviewed',p['text'])
        self.assertEqual(len(core.tasks()),1)
        self.assertEqual(core.tasks()[0]['status'],'open')
    def test_scheduled_handoff_and_live_state(self):
        job=workflow_scheduler.create_schedule('Weekly Review','Glissimo','general_task',
           'Review Glissimo search diagnostics and prepare a short report.', 'daily','20:00')
        run=workflow_scheduler.run_now(job['id'])
        state=extension_bridge.state()
        self.assertEqual(state['counts']['due_handoffs'],1)
        p=extension_bridge.handoff('run',run['id'])
        self.assertIn('scheduled RUN #'+str(run['id']),p['text'])
    def test_notes_do_not_mark_as_done(self):
        task=core.create_task('Evaluate SEO audit','Advertpreneur')
        note=extension_bridge.manual_note(task['id'],'Auditing blocked pending login verification.')
        self.assertEqual(note['source'],'operator')
        self.assertEqual(core.tasks()[0]['status'],'open')
        with self.assertRaises(ValueError):extension_bridge.manual_note(task['id'],'ok')
        with self.assertRaises(ValueError):extension_bridge.handoff('invalid',1)

if __name__=='__main__':unittest.main()
