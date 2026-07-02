from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from local_rpa_agent.data_pipeline import run_data_pipeline, run_data_pipeline_with_trace


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

    def test_dash_sku_core_is_normalized_before_label_matching_and_both_files_required(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            label_dir = root / "labels"
            report_dir = root / "reports"
            output_dir = root / "out"
            label_dir.mkdir()
            report_dir.mkdir()
            output_dir.mkdir()
            (label_dir / "R0059-G.jpg").write_text("label", encoding="utf-8")
            (label_dir / "R0059-S.jpg").write_text("label", encoding="utf-8")
            (report_dir / "铅镉镍R-0059-G SL-0015.pdf").write_text("report", encoding="utf-8")
            (report_dir / "铅镉镍R-0059-S SL-0007.pdf").write_text("report", encoding="utf-8")

            definition = {
                "data_pipeline": [
                    {
                        "step_id": "extract_core_sku",
                        "type": "derive_regex_list",
                        "params": {
                            "source": "run_rows",
                            "source_field": "sku_list",
                            "target_field": "core_sku_list",
                            "pattern": "(AB|AC|ER|R)-?\\d+",
                            "normalize_before_match": True,
                            "normalize_core": True,
                            "output": "run_rows",
                        },
                    },
                    {"step_id": "list_labels", "type": "list_files", "params": {"root": str(label_dir), "recursive": True, "output": "label_files"}},
                    {"step_id": "list_reports", "type": "list_files", "params": {"root": str(report_dir), "recursive": False, "output": "report_files"}},
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
                            "mode": "regex_any",
                            "pattern": "(^|[^A-Za-z0-9]){{value}}([^A-Za-z0-9]|$)",
                            "target": "name",
                            "output": "run_rows",
                        },
                    },
                    {
                        "step_id": "validate_files",
                        "type": "validate_required_fields",
                        "params": {
                            "source": "run_rows",
                            "required_fields": ["label_paths", "report_paths"],
                            "log_path": str(output_dir / "miss_resource.txt"),
                            "output": "run_rows",
                        },
                    },
                ]
            }
            base_row = {
                "run_rows": [
                    {"SPU ID": "SPU001", "sku_list": ["R-0059-G", "R-0059-S"]},
                    {"SPU ID": "SPU002", "sku_list": ["R-9999-G"]},
                ]
            }

            rows = run_data_pipeline(definition, base_row)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["core_sku_list"], ["R0059"])
            self.assertEqual(len(rows[0]["label_paths"]), 2)
            self.assertEqual(len(rows[0]["report_paths"]), 2)
            miss = (output_dir / "miss_resource.txt").read_text(encoding="utf-8")
            self.assertIn("SPU:SPU002", miss)
            self.assertIn("缺失必填:label_paths,report_paths", miss)

    def test_trace_records_each_pipeline_step_count_and_sample(self):
        definition = {
            "data_pipeline": [
                {"step_id": "set_name", "type": "set_field", "params": {"source": "rows", "field": "name", "value": "demo", "output": "rows"}},
                {"step_id": "validate", "type": "validate_required_fields", "params": {"source": "rows", "required_fields": ["name"], "output": "rows"}},
            ]
        }

        rows, trace = run_data_pipeline_with_trace(definition, {"rows": [{"id": 1}]})

        self.assertEqual(rows[0]["name"], "demo")
        self.assertEqual([item["step_id"] for item in trace], ["set_name", "validate"])
        self.assertEqual(trace[0]["input_count"], 1)
        self.assertEqual(trace[0]["output_count"], 1)
        self.assertEqual(trace[0]["sample"][0]["name"], "demo")

    def test_regex_file_match_respects_sku_boundaries(self):
        definition = {
            "data_pipeline": [
                {
                    "step_id": "match_reports",
                    "type": "match_files",
                    "params": {
                        "source": "rows",
                        "files": "files",
                        "values_field": "sku_list",
                        "output_field": "report_paths",
                        "mode": "regex_any",
                        "pattern": "(^|[^A-Za-z0-9]){{value}}([^A-Za-z0-9]|$)",
                        "target": "name",
                        "output": "rows",
                    },
                },
            ]
        }
        base_row = {
            "rows": [{"SPU ID": "SPU001", "sku_list": ["R0262"]}],
            "files": [
                {"name": "ER0262 report.pdf", "path": "/tmp/wrong.pdf"},
                {"name": "R0262 report.pdf", "path": "/tmp/right.pdf"},
            ],
        }

        rows = run_data_pipeline(definition, base_row)

        self.assertEqual(rows[0]["report_paths"], ["/tmp/right.pdf"])

    def test_sku_candidates_match_dash_and_compact_report_names(self):
        definition = {
            "data_pipeline": [
                {
                    "step_id": "report_candidates",
                    "type": "derive_sku_candidates",
                    "params": {
                        "source": "rows",
                        "source_field": "sku_list",
                        "target_field": "report_sku_candidates",
                        "candidate_templates": [
                            "{prefix}{number}-{suffix}",
                            "{prefix}-{number}-{suffix}",
                            "{prefix}{number}",
                            "{prefix}-{number}",
                        ],
                        "output": "rows",
                    },
                },
                {
                    "step_id": "match_reports",
                    "type": "match_files",
                    "params": {
                        "source": "rows",
                        "files": "files",
                        "values_field": "report_sku_candidates",
                        "output_field": "report_paths",
                        "mode": "regex_any",
                        "pattern": "(^|[^A-Za-z0-9]){{value}}([^A-Za-z0-9]|$)",
                        "target": "name",
                        "output": "rows",
                    },
                },
            ]
        }
        base_row = {
            "rows": [{"SPU ID": "SPU001", "sku_list": ["R0052-G", "R0052-S"]}],
            "files": [
                {"name": "铅镉镍R-0052-G SL-0015.pdf", "path": "/tmp/gold.pdf"},
                {"name": "铅镉镍R-0052-S SL-0007.pdf", "path": "/tmp/silver.pdf"},
            ],
        }

        rows = run_data_pipeline(definition, base_row)

        self.assertIn("R-0052-G", rows[0]["report_sku_candidates"])
        self.assertIn("R0052-G", rows[0]["report_sku_candidates"])
        self.assertIn("R-0052", rows[0]["report_sku_candidates"])
        self.assertEqual(rows[0]["report_paths"], ["/tmp/gold.pdf", "/tmp/silver.pdf"])

    def test_validate_required_fields_overwrites_log_and_uses_format_template(self):
        with TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "miss_resource.txt"
            log_path.write_text("old log\n", encoding="utf-8")
            definition = {
                "data_pipeline": [
                    {
                        "step_id": "validate",
                        "type": "validate_required_fields",
                        "params": {
                            "source": "rows",
                            "required_fields": ["label_paths", "report_paths"],
                            "log_path": str(log_path),
                            "write_mode": "overwrite",
                            "format": "SPU:{SPU ID} | SKU:{sku_list} | 缺失:{missing_required_labels}",
                            "field_labels": {"label_paths": "标签图", "report_paths": "测试报告"},
                            "output": "rows",
                        },
                    },
                ],
            }

            rows = run_data_pipeline(definition, {
                "rows": [
                    {"SPU ID": "SPU001", "sku_list": ["R0052-G"], "label_paths": [], "report_paths": []},
                    {"SPU ID": "SPU002", "sku_list": ["R0053-G"], "label_paths": ["/tmp/a.jpg"], "report_paths": ["/tmp/a.pdf"]},
                ],
            })

            self.assertEqual(len(rows), 1)
            content = log_path.read_text(encoding="utf-8")
            self.assertNotIn("old log", content)
            self.assertIn("SPU:SPU001 | SKU:R0052-G | 缺失:标签图,测试报告", content)

    def test_find_file_discovers_optional_package_image_from_label_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            label_dir = root / "labels"
            label_dir.mkdir()
            (label_dir / "AC0194-label.png").write_text("label", encoding="utf-8")
            package = label_dir / "label_update.jpg"
            package.write_text("package", encoding="utf-8")

            definition = {
                "data_pipeline": [
                    {
                        "step_id": "list_labels",
                        "type": "list_files",
                        "params": {"root": str(label_dir), "recursive": True, "output": "label_files"},
                    },
                    {
                        "step_id": "find_package",
                        "type": "find_file",
                        "params": {
                            "files": "label_files",
                            "mode": "name_contains",
                            "keyword": "label_update",
                            "output_field": "package_img_path",
                        },
                    },
                ],
            }

            rows, trace = run_data_pipeline_with_trace(definition, {})

            self.assertEqual(rows, [{"package_img_path": str(package.resolve())}])
            self.assertEqual(trace[-1]["output"], "package_img_path")
            self.assertEqual(trace[-1]["output_count"], 1)


if __name__ == "__main__":
    unittest.main()
