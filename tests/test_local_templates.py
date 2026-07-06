import tempfile
import unittest
from pathlib import Path

from local_rpa_agent.storage import (
    delete_local_template,
    list_local_templates,
    save_local_template,
)


class LocalTemplateTests(unittest.TestCase):
    def test_saves_lists_and_deletes_templates_by_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"

            save_local_template(
                config_path,
                workflow_id="wf-1",
                name="默认参数",
                input_files={"task_excel": "E:/task.xlsx"},
                runtime_params={"x": "123"},
                output_dir="E:/out",
            )
            save_local_template(
                config_path,
                workflow_id="wf-2",
                name="其他流程",
                input_files={"task_excel": "E:/other.xlsx"},
                runtime_params={},
                output_dir="",
            )

            rows = list_local_templates(config_path, "wf-1")

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "默认参数")
            self.assertEqual(rows[0]["input_files"]["task_excel"], "E:/task.xlsx")
            self.assertEqual(rows[0]["runtime_params"]["x"], "123")
            self.assertEqual(rows[0]["output_dir"], "E:/out")

            delete_local_template(config_path, "wf-1", rows[0]["id"])
            self.assertEqual(list_local_templates(config_path, "wf-1"), [])


if __name__ == "__main__":
    unittest.main()
