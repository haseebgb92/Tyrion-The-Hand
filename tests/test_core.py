import pathlib
import tempfile
import unittest
from tyrion import core,bridge,integrations
from unittest.mock import patch

class TyrionCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_db=core.DB
        self.old_data=core.DATA
        core.DATA=pathlib.Path(self.tmp.name)
        core.DB=core.DATA/"tyrion.sqlite3"
        core.setup()

    def tearDown(self):
        core.DB=self.old_db
        core.DATA=self.old_data
        self.tmp.cleanup()

    def test_project_seed_is_unverified(self):
        data=core.overview()
        self.assertGreater(len(data["projects"]),5)
        self.assertTrue(all(p["status"]=="needs_sync" for p in data["projects"]))

    def test_task_lifecycle(self):
        task=bridge.call("tyrion_create_task",{"title":"Test local bridge","project":"Glissimo","priority":"high"})
        self.assertEqual(task["status"],"open")
        self.assertEqual(task["source"],"mcp")
        new=bridge.call("tyrion_update_task",{"id":task["id"],"status":"awaiting_approval"})
        self.assertEqual(new["status"],"awaiting_approval")
        self.assertEqual(len(core.tasks()),1)
        self.assertGreater(len(core.activity()),0)

    def test_unknown_project_refused(self):
        with self.assertRaises(ValueError):
            core.create_task("An important task","Fake client")

    def test_identity_can_update_but_not_rewrite_permissions(self):
        current=core.identity()
        core.update_identity({"voice":"Clear, direct, work-focused."})
        self.assertEqual(core.identity()["voice"],"Clear, direct, work-focused.")
        with self.assertRaises(ValueError):
            core.update_identity({"secret_api_key":"abc"})
        self.assertIn("boundaries",current)

    def test_skills_from_real_catalog(self):
        data=core.catalog()
        self.assertGreater(len(data["skills"]),100)
        self.assertTrue(any(s["name"]=="advertpreneur-design-toolkit" for s in data["skills"]))
        self.assertIn("name:",core.skill_text("advertpreneur-design-toolkit")["content"])

    def test_relay_keeps_remote_credentials_out(self):
        report=core.record_advert_connect_relay([{"url":"https://example.org","ok":True,"version":"0.6"}])
        self.assertEqual(report["services"][0]["status"],"relay_connected")
        self.assertNotIn("token",str(report))
        self.assertEqual(core.relay_snapshot(),report)

    def test_mcp_write_allowlist_denies_publishing(self):
        with self.assertRaises(ValueError):integrations.meta_call("publish_post",{},approved_write=True)
        with self.assertRaises(ValueError):integrations.meta_call("run_command",{})

    def test_approvals_are_not_executed_without_operator(self):
        item=core.create_meta_draft_proposal("account_abc","Client draft","facebook","Draft preview")
        self.assertEqual(item["status"],"pending")
        with patch.object(integrations,"meta_call",side_effect=AssertionError("should not dispatch")):
            self.assertEqual(core.approval_requests()[0]["status"],"pending")
            core.decide_approval(item["id"],"reject")
        self.assertEqual(core.approval_requests()[0]["status"],"rejected")
        with self.assertRaises(ValueError):core.decide_approval(item["id"],"approve")

    def test_approved_draft_goes_only_to_allowed_meta_tool(self):
        item=core.create_meta_draft_proposal("account_abc","Client draft","instagram","Caption")
        with patch.object(integrations,"meta_accounts",return_value=[{"id":"account_abc","name":"Approved workspace","status":"connected"}]),patch.object(integrations,"meta_call",return_value={"id":"draft_test"}) as call:
            result=core.decide_approval(item["id"],"approve")
        self.assertEqual(result["status"],"executed")
        self.assertEqual(call.call_args.args[0],"create_post")
        self.assertTrue(call.call_args.kwargs["approved_write"])
        self.assertNotIn("scheduled_for",call.call_args.args[1])

    def test_skill_route_is_deterministic(self):
        from tyrion import skill_router
        v=skill_router.route("Audit SEO and WordPress content on Coocoo Babys")
        self.assertTrue(v["skills"])
        self.assertIn("advertpreneur-search-growth",[s["name"] for s in v["skills"]])

    def test_job_toggle(self):
        job=core.set_job_enabled("catalog_refresh",False)
        self.assertEqual(job["enabled"],0)
        with self.assertRaises(ValueError):
            core.set_job_enabled("missing",True)

if __name__=="__main__":unittest.main()
