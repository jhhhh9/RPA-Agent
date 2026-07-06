import unittest
import tempfile
from pathlib import Path

from local_rpa_agent.workflow_metadata import asset_requirements, validate_asset_directories


class GuiHelperTests(unittest.TestCase):
    def test_extracts_button_asset_requirements_from_click_image_nodes(self):
        definition = {
            "nodes": [
                {"node_id": "search", "type": "click_image", "params": {"asset_id": "search_btn.png", "asset_dir": "{{input.button_asset_dir}}"}},
                {"node_id": "upload", "type": "click_image", "params": {"asset_id": "upload_btn.png", "asset_dir": "{{input.button_asset_dir}}"}},
                {"node_id": "duplicate", "type": "click_image", "params": {"asset_id": "upload_btn.png", "asset_dir": "{{input.button_asset_dir}}"}},
                {"node_id": "coordinate", "type": "click_coordinate", "params": {"x": 1, "y": 2}},
            ]
        }

        self.assertEqual(
            asset_requirements(definition),
            ["search_btn.png", "upload_btn.png"],
        )

    def test_validates_required_button_assets_in_runtime_directory(self):
        definition = {
            "assets": [{"key": "button_asset_dir", "label": "按钮截图目录", "type": "image_directory", "required": True}],
            "nodes": [
                {"node_id": "search", "type": "click_image", "params": {"asset_id": "search_btn.png", "asset_dir": "{{input.button_asset_dir}}"}},
                {"node_id": "upload", "type": "click_image", "params": {"asset_id": "upload_btn.png", "asset_dir": "{{input.button_asset_dir}}"}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "search_btn.png").write_text("placeholder", encoding="utf-8")

            errors = validate_asset_directories(definition, {"button_asset_dir": tmp})

        self.assertEqual(errors, ["按钮截图目录缺少按钮截图文件：upload_btn.png"])


if __name__ == "__main__":
    unittest.main()
