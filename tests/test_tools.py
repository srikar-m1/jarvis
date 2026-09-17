import unittest

from jarvis.tools import ToolRegistry, default_registry


class ToolRegistryTests(unittest.TestCase):
    def test_only_registered_tools_can_run(self):
        registry = ToolRegistry()
        registry.register("double", lambda value: value * 2)

        self.assertEqual(registry.run("double", 4), 8)
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            registry.run("shell")

    def test_system_status_returns_expected_fields(self):
        result = default_registry().run("system_status")

        self.assertIn("platform", result)
        self.assertIn("python", result)
        self.assertIn("disk_free_gb", result)
