import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from tyrion import core,extension_bridge,server


class SteeringHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_data,self.old_db=core.DATA,core.DB
        core.DATA=Path(self.tmp.name)
        core.DB=core.DATA/"isolated.sqlite3"
        self.key=extension_bridge.get_pairing_key()
        self.chat="https://chatgpt.com/c/12345678-aaaa-aaaa-aaaa-123456789012"
        self.http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=3)
        core.DATA,self.tmp_data=self.old_data,None
        core.DB=self.old_db
        self.tmp.cleanup()

    def request(self,path,payload=None,paired=True):
        headers={"Host":"127.0.0.1:17877"}
        if paired:headers["X-Tyrion-Extension"]=self.key
        if payload is not None:headers["Content-Type"]="application/json"
        body=json.dumps(payload).encode() if payload is not None else None
        req=urllib.request.Request(f"http://127.0.0.1:{self.http.server_port}"+path,
            data=body,headers=headers,method="POST" if body is not None else "GET")
        with urllib.request.urlopen(req,timeout=6) as r:
            return json.load(r)

    def test_paired_endpoints_and_auth(self):
        chat=self.chat
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.request("/api/extension/steering?chat="+urllib.parse.quote(chat),paired=False)
        self.assertEqual(err.exception.code,403)
        added=self.request("/api/extension/steering/add",
             {"chat":chat,"instruction":"Preserve existing product prices"})
        self.assertTrue(added["ok"])
        iid=added["result"]["id"]
        queue=self.request("/api/extension/steering?chat="+urllib.parse.quote(chat))
        self.assertEqual(queue["pending"][0]["instruction"],"Preserve existing product prices")
        removed=self.request("/api/extension/steering/remove",{"chat":chat,"id":iid})
        self.assertTrue(removed["result"]["removed"])
        self.assertEqual(self.request("/api/extension/steering?chat="+urllib.parse.quote(chat))["pending"],[])

if __name__=="__main__":
    unittest.main()
