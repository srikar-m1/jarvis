import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jarvis.storage import SQLiteStore


class SQLiteStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database = Path(self.temp_dir.name) / "jarvis.db"

    def test_notes_are_normalized_and_persisted(self):
        store = SQLiteStore(self.database)
        store.set_note(" Project ", "Ship the API")

        reopened = SQLiteStore(self.database)

        self.assertEqual(reopened.get_note("project"), "Ship the API")
        self.assertEqual(reopened.list_notes(), [("project", "Ship the API")])

    def test_due_reminders_can_be_completed(self):
        store = SQLiteStore(self.database)
        now = datetime.now(UTC)
        due_id = store.add_reminder("Send application", now - timedelta(minutes=1))
        store.add_reminder("Prepare interview notes", now + timedelta(hours=1))

        due = store.list_reminders(due_before=now)

        self.assertEqual([item.id for item in due], [due_id])
        self.assertTrue(store.complete_reminder(due_id))
        self.assertEqual(store.list_reminders(due_before=now), [])
        self.assertFalse(store.complete_reminder(due_id))

    def test_empty_note_is_rejected(self):
        store = SQLiteStore(self.database)

        with self.assertRaisesRegex(ValueError, "requires both"):
            store.set_note("", "value")
