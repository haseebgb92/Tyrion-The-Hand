import pathlib
import tempfile
import unittest
from unittest.mock import patch
from tyrion import core, project_hub, integration_extra

class ProjectDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_data,self.old_db=core.DATA,core.DB
        core.DATA=pathlib.Path(self.tmp.name)
        core.DB=core.DATA/'p.sqlite3'
        project_hub.initialize()
    def tearDown(self):
        core.DATA,core.DB=self.old_data,self.old_db
        self.tmp.cleanup()
    def test_known_directory_with_safe_resources(self):
        items=project_hub.mapped_projects()
        self.assertGreaterEqual(len(items),20)
        coo=next(x for x in items if x['name']=='CooCoo Babys')
        self.assertTrue(any(x['locator']=='https://coocoobabys.com' for x in coo['resources']))
        self.assertTrue(all('password' not in str(x).lower() for x in items))
    def test_project_creation_and_resource(self):
        x=project_hub.create_project('Temporary Client','WordPress / client')
        self.assertEqual(x['name'],'Temporary Client')
        r=project_hub.add_resource('Temporary Client','Site','website','https://example.com')
        self.assertEqual(r['kind'],'website')
        self.assertTrue(any(x['name']=='Temporary Client' for x in project_hub.mapped_projects()))
    def test_credentials_and_file_paths_not_allowed(self):
        with self.assertRaises(ValueError):
            project_hub.add_resource('CooCoo Babys','Bad link','website','https://user:pass@example.com')
        with self.assertRaises(ValueError):
            project_hub.add_resource('CooCoo Babys','Bad folder','local_folder','/etc')
        with self.assertRaises(ValueError):
            project_hub.add_resource('CooCoo Babys','Fake protocol','repository','http://github.com/example/repo')
    def test_cloud_relay_sanitized(self):
        out=core.record_connector_relay('supabase','relay_connected','Read-only project verified',{'project':'advertpreneur-connect','active_projects':1})
        self.assertEqual(out['status'],'relay_connected')
        with self.assertRaises(ValueError):
            core.record_connector_relay('supabase','relay_connected','No',{'secret_key':'must not store'})
        with self.assertRaises(ValueError):
            core.record_connector_relay('nonexistent','relay_connected','Unknown')
    def test_local_inventory_has_no_live_claim(self):
        result=integration_extra.security_fleet_summary()
        self.assertEqual(result['status'],'inventory_only')
        self.assertEqual(result['capabilities'],['inventory.read'])
        self.assertTrue(all('password' not in str(x).lower() for x in result.get('sites',[])))

if __name__=='__main__':unittest.main()
