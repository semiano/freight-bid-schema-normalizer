import tempfile
import unittest
from pathlib import Path

from src.function_app.services.artifact_store import LocalArtifactStore


class TestArtifactStore(unittest.TestCase):
    def test_write_and_list_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalArtifactStore(temp_dir)

            text_path = store.write_text("a/test.txt", "hello")
            json_path = store.write_json("b/data.json", {"k": "v"})
            bytes_path = store.write_bytes("c/blob.bin", b"123")

            self.assertTrue(Path(text_path).exists())
            self.assertTrue(Path(json_path).exists())
            self.assertTrue(Path(bytes_path).exists())

            artifacts = store.list_artifacts()
            self.assertEqual(len(artifacts), 3)
            self.assertTrue(any(path.endswith("test.txt") for path in artifacts))


if __name__ == "__main__":
    unittest.main()
