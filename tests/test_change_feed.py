import pathlib
import tempfile
import unittest
from tyrion import core,project_hub,workflow_scheduler as ws,change_feed

class SharedSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_data,self.old_db=core.DATA,core.DB
        core.DATA=pathlib.Path(self.tmp.name)
        core.DB=core.DATA/"changefeed.sqlite"
        ws.setup()
        project_hub.initialize()
        change_feed.setup()

    def tearDown(self):
        core.DATA,core.DB=self.old_data,self.old_db
        self.tmp.cleanup()

    def test_dashboard_or_mcp_task_single_entry(self):
        task=core.create_task("Review homepage visual regression","Glissimo",source="dashboard")
        first=change_feed.inbox()
        self.assertEqual(len(first["changes"]["events"]),1)
        self.assertEqual(first["changes"]["events"][0]["kind"],"task.created")
        self.assertEqual(first["changes"]["events"][0]["entity_id"],task["id"])
        marker=first["changes"]["max_event_id"]
        self.assertEqual(change_feed.ack(marker)["pending_changes"],0)
        self.assertEqual(change_feed.inbox()["changes"]["events"],[])
        core.set_task_status(task["id"],"awaiting_approval")
        second=change_feed.inbox()
        self.assertEqual([e["kind"] for e in second["changes"]["events"]],["task.updated"])
        self.assertGreater(second["changes"]["max_event_id"],marker)

    def test_project_schedule_and_run_all_recorded(self):
        project=project_hub.create_project("New Tyrion Project","WordPress / client")
        s=ws.create_schedule("Review New Project",project["name"],"general_task",
           "Review this project's outstanding tasks without changing the live site",
           "daily","20:00")
        r=ws.run_now(s["id"])
        events=change_feed.feed()["events"]
        self.assertEqual([e["kind"] for e in events],
                         ["project.created","schedule.created","run.queued"])
        self.assertEqual(change_feed.inbox()["scheduled_work"][0]["id"],r["id"])

    def test_ack_cannot_skip_future_or_rewind(self):
        core.create_task("A testable operation","Advertpreneur")
        data=change_feed.feed()
        with self.assertRaises(ValueError):change_feed.ack(data["max_event_id"]+1)
        change_feed.ack(data["max_event_id"])
        with self.assertRaises(ValueError):change_feed.ack(-1)
        self.assertEqual(change_feed.status()["pending_changes"],0)

    def test_chatgpt_writes_into_original_task(self):
        from tyrion import bridge
        task=core.create_task("Check Glissimo product media","Glissimo",source="dashboard")
        note=bridge.call("tyrion_add_task_update",{"task_id":task["id"],
            "note":"Reviewed available product media references; no live changes made."})
        self.assertEqual(note["source"],"chatgpt")
        self.assertEqual(len(core.tasks()),1)
        history=bridge.call("tyrion_task_updates",{"task_id":task["id"]})
        self.assertEqual(len(history),1)
        self.assertEqual(history[0]["note"],note["note"])
        self.assertEqual(core.tasks()[0]["status"],"open")

    def test_notes_reject_unrelated_target(self):
        with self.assertRaises(ValueError):core.add_task_update(9999,"Unknown task")
        with self.assertRaises(ValueError):core.add_task_update(9999,"Hello","unauthorized")

    def test_project_update_and_resources_emit_events(self):
        p=project_hub.create_project("Design Regression Project","Internal / development")
        project_hub.update_project(p["name"],"Internal / quality assurance","Compare screenshot changes")
        project_hub.add_resource(p["name"],"Project reference","website","https://example.org")
        events=change_feed.feed()["events"]
        self.assertEqual([e["kind"] for e in events],
                         ["project.created","project.updated","project.updated"])

    def test_bridge_reads_but_does_not_execute(self):
        from tyrion import bridge
        core.create_task("Prepare a design outline","Advertpreneur",source="dashboard")
        data=bridge.call("tyrion_sync_inbox",{})
        self.assertEqual(data["changes"]["total_unread"],1)
        self.assertEqual(core.tasks()[0]["status"],"open")
        acknowledged=bridge.call("tyrion_acknowledge_events",
                                 {"last_event_id":data["changes"]["max_event_id"]})
        self.assertEqual(acknowledged["pending_changes"],0)
        self.assertEqual(core.tasks()[0]["status"],"open")

if __name__=="__main__":
    unittest.main()
