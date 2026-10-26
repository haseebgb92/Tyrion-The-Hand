"""Media retrieval integration regression checks (no model loaded)."""
import hashlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from tyrion import knowledge_media as media

class MediaIndexTests(unittest.TestCase):
    def test_unapproved_paths_rejected(self):
        with tempfile.NamedTemporaryFile(suffix=".png") as file:
            with self.assertRaises(ValueError):
                media.approved_path(file.name)

    def test_index_is_repeatable_and_project_scoped(self):
        image=Path(__file__).resolve().parent.parent/"plugin/assets/icon.png"
        self.assertTrue(image.is_file())
        with tempfile.TemporaryDirectory() as folder:
            dbfile=Path(folder)/"media.sqlite3"
            vector=[1.0]+[0.0]*255
            with patch.object(media,"DB",dbfile),patch.object(media,"input_embed",return_value=vector) as model:
                first=media.index_media(str(image),"Tyrion – The Hand")
                second=media.index_media(str(image),"Tyrion – The Hand")
                self.assertEqual(first["indexed"],1)
                self.assertTrue(second["cached"])
                result=media.search_media("gold hand icon","Tyrion – The Hand",limit=4)
                self.assertEqual(result["indexed"],1)
                self.assertEqual(result["matches"][0]["kind"],"image")
                self.assertEqual(result["matches"][0]["project"],"Tyrion – The Hand")
                other=media.search_media("gold hand icon","Glissimo",limit=4)
                self.assertEqual(other["indexed"],0)
                self.assertEqual(model.call_count,2)

if __name__=="__main__": unittest.main()
