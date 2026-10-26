"""Tyrion Android companion: pairing, private-device ACL, revocation, PC relay."""
import http.client
import json
import pathlib
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from tyrion import core,companion_pairing as pairing,companion_server

class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.previous=(core.DATA,core.DB,pairing._SETUP)
        core.DATA=pathlib.Path(self.tmp.name)
        core.DB=core.DATA/'mobile.sqlite3'
        pairing._SETUP=False
        pairing.FAILED.clear()
        pairing.setup()
    def tearDown(self):
        core.DATA,core.DB,pairing._SETUP=self.previous
        pairing.FAILED.clear()
        self.tmp.cleanup()
    def test_one_time_code_and_no_plaintext_storage(self):
        payload=pairing.pairing_code()
        self.assertRegex(payload['code'],r'^[0-9]{8}$')
        self.assertTrue(payload['qr_data_url'].startswith('data:image/png;base64,'))
        with core.connection() as db:
            row=db.execute('SELECT code_hash FROM companion_codes').fetchone()
            self.assertNotEqual(row['code_hash'],payload['code'])
        result=pairing.claim(payload['code'],'Redmi Note 14 Pro')
        self.assertEqual(pairing.validate(result['token'])['label'],'Redmi Note 14 Pro')
        self.assertNotIn(result['token'],str(pairing.devices()))
        with self.assertRaises(ValueError):pairing.claim(payload['code'],'Duplicate')
        self.assertTrue(pairing.revoke(result['device_id'])['revoked'])
        self.assertIsNone(pairing.validate(result['token']))
    def test_expiry_wrong_codes_and_rate_limit(self):
        code=pairing.pairing_code()
        with self.assertRaises(ValueError):pairing.claim('99999x99','Invalid')
        with self.assertRaises(ValueError):pairing.claim('12345678' if code['code']!='12345678' else '87654321','Invalid')
        with core.connection() as db:
            db.execute('UPDATE companion_codes SET expires_at=?',(int(time.time())-1,))
            db.commit()
        with self.assertRaises(ValueError):pairing.claim(code['code'],'Expired')
    def test_remote_http_authentication_relay_and_revocation(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),companion_server.Handler)
        server.daemon_threads=True
        runner=threading.Thread(target=server.serve_forever,daemon=True)
        runner.start()
        try:
            def request(method,path,body=None,token=None,extra=None):
                conn=http.client.HTTPConnection('127.0.0.1',server.server_address[1],timeout=5)
                headers={'Host':'127.0.0.1:17878'}
                if body is not None:headers['Content-Type']='application/json'
                if token:headers['X-Tyrion-Session']=token
                if extra:headers.update(extra)
                conn.request(method,path,json.dumps(body).encode() if body is not None else None,headers)
                response=conn.getresponse()
                raw=response.read();status=response.status
                conn.close()
                return status,json.loads(raw) if response.getheader('Content-Type','').startswith('application/json') else raw
            self.assertEqual(request('GET','/api/tasks')[0],401)
            code=pairing.pairing_code()
            self.assertEqual(request('POST','/api/mobile/pair',{'code':code['code'],'name':'Acceptance Phone'},extra={'Origin':'https://attacker.test'})[0],403)
            status,device=request('POST','/api/mobile/pair',{'code':code['code'],'name':'Acceptance Phone'})
            self.assertEqual(status,200)
            token=device['token']
            self.assertEqual(request('GET','/api/mobile/session',token=token)[0],200)
            def fake_local(path,method='GET',body=None):
                if path=='/':return 200,b'<html><head><meta name="tyrion-session" content="__TYRION_SESSION__"></head></html>','text/html'
                return 200,b'[{"name":"Shared PC Task"}]','application/json'
            with patch.object(companion_server,'local_request',side_effect=fake_local):
                status,result=request('GET','/api/tasks',token=token)
                self.assertEqual((status,result[0]['name']),(200,'Shared PC Task'))
                status,result=request('GET','/',token=token)
                self.assertEqual(status,200)
                self.assertIn(b'companion.css',result)
            self.assertTrue(pairing.revoke(device['device_id'])['revoked'])
            self.assertEqual(request('GET','/api/tasks',token=token)[0],401)
            self.assertEqual(request('GET','/api/extension/key',token=token)[0],401)
        finally:server.shutdown();server.server_close();runner.join(timeout=3)

if __name__=='__main__':unittest.main()
