import tempfile
import unittest
from pathlib import Path

from tyrion import core,steering


class SteeringQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_data,self.old_db=core.DATA,core.DB
        core.DATA=Path(self.temp.name)
        core.DB=core.DATA/"isolated.sqlite3"
        self.chat="https://chatgpt.com/c/12345678-aaaa-aaaa-aaaa-123456789012"

    def tearDown(self):
        core.DATA=self.old_data
        core.DB=self.old_db
        self.temp.cleanup()

    def test_per_conversation_fifo_and_delete(self):
        a=steering.add(self.chat,"Don't update prices")
        b=steering.add(self.chat,"Check alt text")
        self.assertEqual([v["id"] for v in steering.pending(self.chat)],[a["id"],b["id"]])
        other="https://chatgpt.com/c/98765432-bbbb-bbbb-bbbb-123456789012"
        self.assertEqual(steering.pending(other),[])
        self.assertEqual(steering.remove(other,a["id"]),{"removed":False})
        self.assertEqual(steering.remove(self.chat,a["id"]),{"removed":True})
        self.assertEqual(steering.pending(self.chat)[0]["instruction"],"Check alt text")
        self.assertEqual(steering.clear(self.chat),{"removed":1})

    def test_validation(self):
        for bad in ["https://evil.example/c/123456789","https://chatgpt.com.evil.example/c/123456789",
                    "http://chatgpt.com/c/123456789","https://chatgpt.com/"]:
            with self.assertRaises(ValueError):steering.add(bad,"Hello")
        with self.assertRaises(ValueError):steering.add(self.chat,"X"*1501)
        with self.assertRaises(ValueError):steering.remove(self.chat,"1")

    def test_mcp_bridge_reads_and_acknowledges_exact_chat(self):
        from tyrion import bridge
        first=steering.add(self.chat,"Also check the reviews")
        second=steering.add(self.chat,"Keep the current layout")
        overview=bridge.call("tyrion_steering_queue",{})
        self.assertEqual(overview["conversations"][0]["pending_count"],2)
        got=bridge.call("tyrion_steering_queue",{"chat_url":self.chat})
        self.assertEqual(len(got["pending"]),2)
        result=bridge.call("tyrion_steering_ack",{"chat_url":self.chat,"ids":[first["id"]]})
        self.assertEqual(result,{"acknowledged":1})
        self.assertEqual([v["id"] for v in steering.pending(self.chat)],[second["id"]])
        with self.assertRaises(ValueError):
            bridge.call("tyrion_steering_ack",{"chat_url":self.chat,"ids":[first["id"]]})

    def test_queue_limit(self):
        for n in range(50):steering.add(self.chat,f"Update {n}")
        with self.assertRaises(ValueError):steering.add(self.chat,"Too many")
        self.assertEqual(len(steering.pending(self.chat)),50)

if __name__=="__main__":
    unittest.main()