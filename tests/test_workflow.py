from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from local_rpa_agent.workflow import WorkflowExecutor, render_template


class WorkflowExecutorTest(unittest.TestCase):
    def test_render_template_row_value(self):
        self.assertEqual(render_template("hello {{row.name}}", {"name": "Temu"}), "hello Temu")

    def test_executor_runs_linear_workflow(self):
        definition = {
            "entry_node": "n1",
            "nodes": [
                {"node_id": "n1", "type": "log", "params": {"message": "start {{row.id}}"}, "next": "n2"},
                {"node_id": "n2", "type": "sleep", "params": {"seconds": 0}},
            ],
        }
        result = WorkflowExecutor().execute(definition, row={"id": "AC001"})
        self.assertEqual(result.success_rows, 1)
        self.assertEqual(result.failed_rows, 0)
        self.assertEqual(result.logs[0].message, "start AC001")

    def test_executor_appends_log_lines(self):
        with TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "done.txt"
            definition = {
                "entry_node": "n1",
                "nodes": [
                    {"node_id": "n1", "type": "append_log", "params": {"path": str(log_path), "content": "{{row.sku_list}}"}},
                ],
            }

            result = WorkflowExecutor().execute(definition, row={"sku_list": ["AC001-Golden", "AC001-Silver"]})

            self.assertEqual(result.success_rows, 1)
            self.assertEqual(result.failed_rows, 0)
            self.assertEqual(log_path.read_text(encoding="utf-8").splitlines(), ["AC001-Golden", "AC001-Silver"])


if __name__ == "__main__":
    unittest.main()
