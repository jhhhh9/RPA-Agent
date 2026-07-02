import unittest

from local_rpa_agent.capabilities import LOCAL_CAPABILITIES, capability_label, missing_capabilities


class CapabilityTest(unittest.TestCase):
    def test_missing_capabilities_keeps_required_order(self):
        missing = missing_capabilities(["upload_file@1", "future@9"], ["upload_file@1"])
        self.assertEqual(missing, ["future@9"])

    def test_known_labels_are_readable(self):
        self.assertIn("upload_file@1", LOCAL_CAPABILITIES)
        self.assertEqual(capability_label("upload_file@1"), "上传文件")


if __name__ == "__main__":
    unittest.main()
