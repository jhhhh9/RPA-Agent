from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from local_rpa_agent.workflow import WorkflowExecutor, evaluate_condition, render_template


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

    def test_condition_supports_not_empty_and_boolean_operators_for_list_fields(self):
        row = {"label_paths": ["label.jpg"], "report_paths": ["report.pdf"], "package_img_path": ""}

        self.assertTrue(evaluate_condition("not_empty(row.label_paths) && not_empty(row.report_paths)", row))
        self.assertTrue(evaluate_condition("is_empty(row.package_img_path) || not_empty(row.label_paths)", row))
        self.assertFalse(evaluate_condition("not_empty(row.package_img_path)", row))

    def test_executor_routes_by_not_empty_condition(self):
        definition = {
            "entry_node": "entry",
            "nodes": [
                {"node_id": "entry", "type": "log", "params": {"message": "entry"}},
                {"node_id": "upload", "type": "log", "params": {"message": "upload"}},
                {"node_id": "skip", "type": "log", "params": {"message": "skip"}},
            ],
            "edges": [
                {"from": "entry", "to": "upload", "condition": "not_empty(row.label_paths) && not_empty(row.report_paths)"},
                {"from": "entry", "to": "skip"},
            ],
        }

        result = WorkflowExecutor().execute(definition, row={"label_paths": ["label.jpg"], "report_paths": ["report.pdf"]})

        self.assertEqual(result.success_rows, 1)
        self.assertEqual([item.node_id for item in result.logs], ["entry", "upload"])

    def test_executor_supports_optional_click_node(self):
        class FakeActions:
            def optional_click(self, params):
                self.params = params
                from local_rpa_agent.actions import ActionResult

                return ActionResult(True, "optional click ok")

        actions = FakeActions()
        definition = {
            "entry_node": "security_confirm",
            "nodes": [
                {
                    "node_id": "security_confirm",
                    "type": "optional_click",
                    "params": {"strategy": "coordinate_click_twice", "x": "{{runtime.x}}", "y": "{{runtime.y}}"},
                },
            ],
        }

        result = WorkflowExecutor(actions=actions).execute(definition, row={"__runtime": {"x": 1057, "y": 610}})

        self.assertEqual(result.success_rows, 1)
        self.assertEqual(actions.params["x"], 1057)
        self.assertEqual(actions.params["y"], 610)


if __name__ == "__main__":
    unittest.main()
