"""Authenticated MCP Events behavior, delivered via mocked HTTPS transport only."""
import base64
import datetime as dt
import json
import pathlib
import tempfile
import time
import unittest
from unittest.mock import patch
from tyrion import core,project_hub,workflow_scheduler as w,change_feed,mcp_events

class EventTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.old_data,self.old_db=core.DATA,core.DB
        core.DATA=pathlib.Path(self.folder.name)
        core.DB=core.DATA/'events.sqlite3'
        w.setup();project_hub.initialize();change_feed.setup();mcp_events.setup()
        self.secret='whsec_'+base64.b64encode(bytes(range(32))).decode()

    def tearDown(self):
        core.DATA,core.DB=self.old_data,self.old_db
        self.folder.cleanup()

    def subscribe(self,event='task.created',args=None):
        def mock_verify(url,secret,subid,message,eventid):
            self.assertEqual(message.get('type'),'verification')
            self.assertTrue(eventid.startswith('msg_verify_'))
            return 200,json.dumps({'challenge':message['challenge']}).encode()
        with patch.object(mcp_events,'_public_addresses',return_value=['8.8.8.8']),patch.object(mcp_events,'_post_signed',side_effect=mock_verify):
            return mcp_events.subscribe({'name':event,'arguments':args or {},
                'delivery':{'mode':'webhook','url':'https://callback.example.org/event','secret':self.secret}})

    def test_catalog_and_auth(self):
        names=[v['name'] for v in mcp_events.event_catalog()['events']]
        self.assertIn('run.queued',names)
        with self.assertRaises(ValueError):mcp_events.subscribe({'name':'task.created','delivery':{'mode':'webhook',
             'url':'http://localhost/unsafe','secret':self.secret}})
        for url in ['https://localhost/a','https://127.0.0.1/test','http://www.example.com','https://user:pw@evil.com/a']:
            with self.assertRaises(ValueError):mcp_events._callback_host(url)
        with self.assertRaises(ValueError):mcp_events._secret_bytes('badsecret')

    def test_verified_subscription_queues_only_new_matching_events(self):
        core.create_task('Old work not delivered','Advertpreneur')
        sub=self.subscribe(args={'project':'Glissimo'})
        self.assertEqual(sub['cursor'],None)
        self.assertEqual(mcp_events.status()['subscriptions_active'],1)
        core.create_task('Unrelated new work','Advertpreneur')
        wanted=core.create_task('Glissimo media regression','Glissimo')
        self.assertEqual(mcp_events.queue_events(),1)
        self.assertEqual(mcp_events.queue_events(),0)
        posts=[]
        def sink(url,secret,subid,message,eventid):
            posts.append(message)
            self.assertEqual(eventid,message['eventId'])
            return 202,b''
        with patch.object(mcp_events,'_post_signed',side_effect=sink):
            result=mcp_events.deliver_one()
        self.assertEqual(result['status'],'delivered')
        self.assertEqual(posts[0]['data']['entity_id'],wanted['id'])
        self.assertEqual(posts[0]['name'],'task.created')
        self.assertIsNone(mcp_events.deliver_one())

    def test_schedule_and_project_resource_events(self):
        self.subscribe('run.queued')
        one=w.create_schedule('Review resources','Glissimo','general_task',
          'Review the staging tasks without changing production','daily','20:00')
        w.run_now(one['id'])
        self.assertEqual(mcp_events.queue_events(),1)
        self.subscribe('project.updated')
        project_hub.add_resource('Glissimo','Official product page','website','https://glissimo.example.org')
        self.assertEqual(mcp_events.queue_events(),1)

    def test_filtered_due_run_inherits_project(self):
        self.subscribe('run.queued',{'project':'Glissimo'})
        wflow=w.create_schedule('Glissimo daily review','Glissimo','general_task',
            'Check product listings and prepare an accurate status report','daily','20:00')
        run=w.run_now(wflow['id'])
        self.assertEqual(mcp_events.queue_events(),1)
        with patch.object(mcp_events,'_post_signed',return_value=(200,b'')) as send:
            result=mcp_events.deliver_one()
        self.assertEqual(result['status'],'delivered')
        self.assertEqual(send.call_args.args[3]['data']['project'],'Glissimo')

    def test_unsubscribe_stops_delivery(self):
        sub=self.subscribe()
        mcp_events.unsubscribe({'name':'task.created','arguments':{},
             'delivery':{'url':'https://callback.example.org/event','mode':'webhook'}})
        core.create_task('No subscribed delivery now','Advertpreneur')
        self.assertEqual(mcp_events.queue_events(),0)
        self.assertEqual(mcp_events.status()['subscriptions_active'],0)

    def test_signature_stability(self):
        signature=mcp_events.sign(self.secret,'evt1',123,b'{}')
        self.assertTrue(signature.startswith('v1,'))
        self.assertEqual(signature,mcp_events.sign(self.secret,'evt1',123,b'{}'))
        self.assertNotEqual(signature,mcp_events.sign(self.secret,'evt1',124,b'{}'))

if __name__=='__main__':unittest.main()
