"""End-to-end local HTTP tests, isolated from the live Tyrion SQLite database."""
import json
import pathlib
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from tyrion import core,server,workflow_scheduler as ws

class LocalSchedulerHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_db,cls.old_data,cls.old_port,cls.old_token=core.DB,core.DATA,server.PORT,server.TOKEN
        cls.temp=tempfile.TemporaryDirectory()
        core.DATA=pathlib.Path(cls.temp.name)
        core.DB=core.DATA/'http_test.sqlite3'
        ws.setup()
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        server.PORT=cls.http.server_address[1]
        server.TOKEN='test-only-session'
        cls.worker=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.worker.start()
        cls.origin=f'http://127.0.0.1:{server.PORT}'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.worker.join(timeout=3)
        core.DB,core.DATA=cls.old_db,cls.old_data
        server.PORT,server.TOKEN=cls.old_port,cls.old_token
        cls.temp.cleanup()

    def get(self,path):
        with urllib.request.urlopen(self.origin+path,timeout=5) as response:
            return response.status,json.loads(response.read())

    def post(self,path,data,authenticated=True):
        headers={'Content-Type':'application/json'}
        if authenticated:headers['X-Tyrion-Session']='test-only-session'
        req=urllib.request.Request(self.origin+path,json.dumps(data).encode(),headers,method='POST')
        with urllib.request.urlopen(req,timeout=6) as response:
            return json.loads(response.read())

    def test_browser_extension_pairing_is_required(self):
        from tyrion import extension_bridge
        key=extension_bridge.get_pairing_key()
        import urllib.error
        with self.assertRaises(urllib.error.HTTPError) as failure:
            self.get('/api/extension/state')
        self.assertEqual(failure.exception.code,403)
        req=urllib.request.Request(self.origin+'/api/extension/state',headers={'X-Tyrion-Extension':key})
        with urllib.request.urlopen(req,timeout=4) as reply:
            data=json.load(reply)
        self.assertIn('open_tasks',data['counts'])
        req=urllib.request.Request(self.origin+'/api/extension/key')
        with self.assertRaises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(req,timeout=4)
        self.assertEqual(denied.exception.code,403)
        req=urllib.request.Request(self.origin+'/api/extension/key',headers={'X-Tyrion-Session':'test-only-session'})
        with urllib.request.urlopen(req,timeout=4) as reply:
            self.assertEqual(json.load(reply)['key'],key)
        # Only user-entered notes are mutable through the extension; no task auto-completion.
        item=core.create_task('Extension HTTP status test','Advertpreneur')
        payload={'task_id':item['id'],'note':'Manual note confirmed; no client action performed.'}
        req=urllib.request.Request(self.origin+'/api/extension/note',
           json.dumps(payload).encode(),{'Content-Type':'application/json','Origin':'chrome-extension://'+'a'*32,
                                      'X-Tyrion-Extension':key},method='POST')
        with urllib.request.urlopen(req,timeout=4) as reply:
            self.assertEqual(json.load(reply)['result']['source'],'operator')
        self.assertEqual(core.one('SELECT status FROM tasks WHERE id=?',(item['id'],))['status'],'open')

    def test_authenticated_schedule_full_lifecycle(self):
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.post('/api/workflows/schedules',{'title':'Unauthorized'},authenticated=False)
        self.assertEqual(err.exception.code,403)
        status,initial=self.get('/api/workflows')
        self.assertEqual(status,200)
        self.assertEqual(initial['counts']['schedules'],0)
        payload={'title':'HTTP Test Draft','project':'CooCoo Babys','kind':'blog_draft',
          'instructions':'Draft original, factual, educational baby content with an editorial checkpoint.',
          'cadence':'daily','time_local':'17:55','timezone':'Asia/Karachi',
          'engine':'chatgpt_handoff'}
        schedule=self.post('/api/workflows/schedules',payload)['result']
        self.assertEqual(schedule['time_local'],'17:55')
        sid=schedule['id']
        updated=self.post(f'/api/workflows/schedules/{sid}/edit',{'time_local':'18:40'})['result']
        self.assertEqual(updated['time_local'],'18:40')
        run=self.post(f'/api/workflows/schedules/{sid}/run-now',{})['result']
        self.assertEqual(run['status'],'awaiting_chatgpt')
        body='## An accessible review checklist\n\n'+('Careful original content with source checks. '*18)
        saved=ws.submit_chatgpt_result(run['id'],'Practical Baby Checklist',body)
        self.assertEqual(saved['status'],'draft_ready')
        _,view=self.get(f'/api/workflows/runs/{run["id"]}/output')
        self.assertIn('Practical Baby Checklist',view['markdown'])
        completed=self.post(f'/api/workflows/runs/{run["id"]}/complete',{})['result']
        self.assertEqual(completed['status'],'completed')
        archived=self.post(f'/api/workflows/schedules/{sid}/archive',{})['result']
        self.assertTrue(archived['archived'])
        _,final=self.get('/api/workflows')
        self.assertEqual(final['counts']['schedules'],0)
        self.assertEqual(final['runs'][0]['status'],'completed')

if __name__=='__main__':unittest.main()
