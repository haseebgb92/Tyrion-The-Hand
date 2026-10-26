import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tyrion import knowledge, bridge

class KnowledgeTests(unittest.TestCase):
    def test_sensitive_content_is_not_indexable(self):
        for value in ("password: 123456", "api_key=privatevalue",
                      "Authorization: Bearer abcdefghi123456",
                      "sk-proj-test_abcdefghijklmnop", "Passwords.kdbx"):
            self.assertEqual(knowledge.scrub(value), "")

    def test_no_vault_or_discontinued_fatir_sources(self):
        refs=knowledge.sources()
        self.assertGreater(len(refs),100)
        self.assertFalse(any(v['name'] in knowledge.EXCLUDED for v in refs.values()))
        self.assertTrue(all('Advertpreneur-Vault' not in v['ref'] for v in refs.values()))

    def test_incremental_index_and_project_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            sources={
                'task:1':dict(ref='task:1',kind='task',name='Alpha update',
                    project='Alpha',snippet='Alpha store subscription testing',
                    hash=hashlib.sha256(b'Alpha store subscription testing').hexdigest()),
                'task:2':dict(ref='task:2',kind='task',name='Beta update',
                    project='Beta',snippet='Beta store checkout integration',
                    hash=hashlib.sha256(b'Beta store checkout integration').hexdigest()),
            }
            def fake_embed(items,query=False):
                if query:return [[1.0,0.0]+[0.0]*254]
                return [[1.0 if 'Alpha' in x else 0.0, 0.0 if 'Alpha' in x else 1.0]+[0.0]*254 for x in items]
            with patch.object(knowledge,'STORE',Path(temp)/'index.sqlite3'),patch.object(knowledge,'sources',return_value=sources),patch.object(knowledge,'embed',side_effect=fake_embed):
                first=knowledge.sync()
                self.assertEqual(first['updated'],2)
                self.assertEqual(knowledge.sync()['updated'],0)
                result=knowledge.search('Alpha store',limit=5,refresh=False,project='Alpha')
                self.assertEqual([x['reference'] for x in result['matches']],['task:1'])
                self.assertTrue((Path(temp)/'index.sqlite3').exists())
                sources.pop('task:1')
                self.assertEqual(knowledge.sync()['removed'],1)
                self.assertEqual(knowledge.status()['indexed'],1)

    def test_mcp_tool_is_retrieval_only(self):
        tools={x['name']:x for x in bridge.TOOLS}
        self.assertIn('tyrion_knowledge_search',tools)
        schema=tools['tyrion_knowledge_search']['inputSchema']
        self.assertNotIn('shell',schema['properties'])
        self.assertNotIn('command',schema['properties'])
        self.assertNotIn('url',schema['properties'])

if __name__=='__main__':unittest.main()
