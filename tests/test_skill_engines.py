import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tyrion import skill_engines,skill_router
from tyrion.bridge import TOOLS,call

class SkillEngineTests(unittest.TestCase):
    def test_four_capability_routes(self):
        cases={
            'Scrape public websites and crawl for audit':'scrapling-official',
            'Reverse engineer Android APK':'reverse-engineer-anything',
            'Research the last 30 days on Reddit':'last30days',
            'Code review: reuse existing functions':'ponytail',
        }
        for query,expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(skill_router.route(query)['skills'][0]['name'],expected)
    def test_mcp_has_only_explicit_readonly_engine_ops(self):
        names={t['name'] for t in TOOLS}
        for name in ('tyrion_engine_status','tyrion_recent_research','tyrion_rea_aura_extension'):
            self.assertIn(name,names)
        self.assertEqual(call('tyrion_engine_status',{})['mode'],'on_demand_read_only')
    def test_reject_control_characters(self):
        for value in ('ab', 'hello\nrm -rf /', 'x'*141):
            with self.assertRaises(ValueError):skill_engines.recent_research(value)
    def test_recent_research_disables_cookies_and_paid_web(self):
        captured={}
        def fake_run(cmd,**kwargs):
            captured['cmd']=cmd;captured['env']=kwargs['env'];captured['timeout']=kwargs['timeout']
            return SimpleNamespace(returncode=0,stdout='2026-10-26 research evidence',stderr='')
        with patch.object(skill_engines.subprocess,'run',side_effect=fake_run):
            response=skill_engines.recent_research('WordPress search')
        self.assertFalse(response['browser_cookies'])
        self.assertFalse(response['saved'])
        self.assertIn('--no-browser-cookies',captured['cmd'])
        self.assertIn('--web-backend=none',captured['cmd'])
        self.assertEqual(captured['env']['FROM_BROWSER'],'off')
        self.assertLessEqual(captured['timeout'],50)
    def test_rea_target_cannot_be_supplied_by_caller(self):
        evidence={'evidence_id':'ev_fixture','normalized_result':{'graph':{'nodes':[{'kind':'artifact'}],'edges':[]}},'subject':{'digest':{'sha256':'abc'}}}
        seen={}
        def fake_run(cmd,**kwargs):
            seen['cmd']=cmd
            return SimpleNamespace(returncode=0,stdout=json.dumps(evidence),stderr='')
        with patch.object(skill_engines.subprocess,'run',side_effect=fake_run):
            result=skill_engines.rea_aura_extension()
        self.assertIn(str(skill_engines.AURA),seen['cmd'])
        self.assertFalse(result['executed_target'])
        self.assertEqual(result['graph_nodes'],1)

if __name__=='__main__':unittest.main()
