import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from jarvis.app import main


class LocalCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database = str(Path(self.temp_dir.name) / "jarvis.db")

    def run_main(self, *arguments):
        output = io.StringIO()
        with patch.dict("os.environ", {"JARVIS_DB_PATH": self.database}), redirect_stdout(output):
            result = main(list(arguments))
        return result, output.getvalue()

    def test_remember_and_recall_do_not_require_ollama(self):
        remembered, _ = self.run_main("--remember", "role", "Python developer")
        recalled, output = self.run_main("--recall", "role")

        self.assertEqual(remembered, 0)
        self.assertEqual(recalled, 0)
        self.assertIn("Python developer", output)

    def test_system_status_is_json(self):
        result, output = self.run_main("--system-status")

        self.assertEqual(result, 0)
        self.assertIn('"disk_free_gb"', output)
