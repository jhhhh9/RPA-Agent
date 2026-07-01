from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from local_rpa_agent.data_pipeline import run_data_pipeline


class DataPipelineTest(unittest.TestCase):
    def test_groups_tasks_and_matches_local_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_csv = root / "tasks.csv"
            label_dir = root / "labels"
            report_dir = root / "reports"
            output_dir = root / "out"
            label_dir.mkdir()
            report_dir.mkdir()
            output_dir.mkdir()

            task_csv.write_text(
                "SPU ID,SKU货号\n"
                "SPU001,AC0194-Golden\n"
                "SPU001,AC0194-Silvery\n"
                "SPU002,AC0292-Golden\n",
                encoding="utf-8",
            )
            (label_dir / "AC0194-label.png").write_text("label", encoding="utf-8")
            (report_dir / "AC0194-Golden test report.pdf").write_text("report", encoding="utf-8")
            (report_dir / "AC0194-Silvery test report.pdf").write_text("report", encoding="utf-8")

            definition = {
                "data_pipeline": [
                    {"step_id": "read_tasks", "type": "read_table", "params": {"path": "{{input.task_excel}}", "output": "task_rows"}},
                    {
                        "step_id": "group_by_spu",
                        "type": "group_rows",
                        "params": {"source": "task_rows", "by": "SPU ID", "collect": {"sku_list": "SKU货号"}, "output": "run_rows"},
                    },
                    {
                        "step_id": "extract_core_sku",
                        "type": "derive_regex_list",
                        "params": {
                            "source": "run_rows",
                            "source_field": "sku_list",
                            "target_field": "core_sku_list",
                            "pattern": "(AB|AC|ER|R)\\d+",
                            "unique": True,
                            "output": "run_rows",
                        },
                    },
                    {"step_id": "list_labels", "type": "list_files", "params": {"root": "{{input.label_dir}}", "recursive": True, "output": "label_files"}},
                    {"step_id": "list_reports", "type": "list_files", "params": {"root": "{{input.report_dir}}", "recursive": False, "output": "report_files"}},
                    {
                        "step_id": "match_labels",
                        "type": "match_files",
                        "params": {
                            "source": "run_rows",
                            "files": "label_files",
                            "values_field": "core_sku_list",
                            "output_field": "label_paths",
                            "mode": "core_stem_equals_any",
                            "output": "run_rows",
                        },
                    },
                    {
                        "step_id": "match_reports",
                        "type": "match_files",
                        "params": {
                            "source": "run_rows",
                            "files": "report_files",
                            "values_field": "sku_list",
                            "output_field": "report_paths",
                            "mode": "exact_token_any",
                            "output": "run_rows",
                        },
                    },
                    {
                        "step_id": "validate_files",
                        "type": "validate_required_fields",
                        "params": {
                            "source": "run_rows",
                            "required_fields": ["report_paths"],
                            "optional_fields": ["label_paths"],
                            "log_path": "{{output.dir}}/miss_resource.txt",
                            "output": "run_rows",
                        },
                    },
                ]
            }
            base_row = {
                "task_excel": str(task_csv),
                "label_dir": str(label_dir),
                "report_dir": str(report_dir),
                "output_dir": str(output_dir),
                "__input": {"task_excel": str(task_csv), "label_dir": str(label_dir), "report_dir": str(report_dir)},
            }

            rows = run_data_pipeline(definition, base_row)

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["SPU ID"], "SPU001")
            self.assertEqual(row["sku_list"], ["AC0194-Golden", "AC0194-Silvery"])
            self.assertEqual(row["core_sku_list"], ["AC0194"])
            self.assertEqual(row["label_paths"], [str((label_dir / "AC0194-label.png").resolve())])
            self.assertEqual(len(row["report_paths"]), 2)
            self.assertIn("SPU002", (output_dir / "miss_resource.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
