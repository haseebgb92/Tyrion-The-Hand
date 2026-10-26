import pathlib
import tempfile
import threading
import unittest
from unittest.mock import patch

from tyrion import core, project_history, knowledge, server

class ProjectHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.saved_data,self.saved_db=core.DATA,core.DB
        core.DATA=pathlib.Path(self.temp.name)
        core.DB=core.DATA/'test.sqlite3'
        core.setup()
        with core.LOCK,core.connection() as db:
            db.execute('INSERT OR IGNORE INTO projects(name,category,updated_at) VALUES(?,?,?)',
                       ('Taiyo Munch','Ecommerce / subscriptions',core.now()))
            db.commit()
        self.saved_store=knowledge.STORE
        knowledge.STORE=core.DATA/'knowledge.sqlite3'
    def tearDown(self):
        core.DATA,core.DB=self.saved_data,self.saved_db
        knowledge.STORE=self.saved_store
        self.temp.cleanup()
    def test_attribution_idempotency_and_no_fabricated_completion(self):
        args=('Taiyo Munch','2026-10-24','request','Publisher logos homepage',
              'Requested logo color toggle and original article links in existing Core.',
              'prior_conversation','historical_report','source:logos:20261024')
        first=project_history.add(*args)
        second=project_history.add(*args)
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(project_history.coverage()['history_entries'],1)
        self.assertIn('historical_report',knowledge.sources()['history:'+str(first['id'])]['snippet'])
        self.assertNotIn('verified_at_date',knowledge.sources()['history:'+str(first['id'])]['snippet'])
        with self.assertRaises(ValueError):
            project_history.add(*('Advertpreneur Vault',)+args[1:])
    def test_new_updates_become_indexable_without_new_tasks(self):
        with core.LOCK,core.connection() as db:
            db.execute("""INSERT INTO tasks(title,project,created_at,updated_at)
                 VALUES('Test existing task','Taiyo Munch',?,?)""",(core.now(),core.now()))
            tid=db.execute('SELECT last_insert_rowid()').fetchone()[0]
            db.execute('INSERT INTO task_updates(task_id,source,note,created_at) VALUES(?,?,?,?)',
                       (tid,'chatgpt','Review completed for draft only; publish not authorized.',core.now()))
            db.commit()
        refs=knowledge.sources()
        self.assertIn('task:'+str(tid),refs)
        self.assertEqual(len([key for key in refs if key.startswith('update:')]),1)
    def test_autowatcher_records_sync_status(self):
        fake={'updated':1,'removed':0,'indexed':9}
        class Stop:
            def __init__(self):self.count=0
            def is_set(self):return False
            def wait(self,seconds):
                self.count+=1
                return self.count>1
        with patch.object(knowledge,'sync',return_value=fake):
            server.knowledge_watcher(Stop())
        from json import loads
        record=core.one("SELECT value FROM meta WHERE key='knowledge_auto_status'")
        data=loads(record['value'])
        self.assertTrue(data['ok'])
        self.assertEqual(data['updated'],1)
if __name__=='__main__':unittest.main()
