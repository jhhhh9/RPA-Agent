from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any


def asset_requirements(definition: dict[str, Any], asset_key: str | None = None) -> list[str]:
    seen: OrderedDict[str, None] = OrderedDict()
    for node in definition.get("nodes") or []:
        if not isinstance(node, dict) or node.get("type") != "click_image":
            continue
        params = node.get("params") if isinstance(node.get("params"), dict) else {}
        if asset_key and f"input.{asset_key}" not in str(params.get("asset_dir") or ""):
            continue
        asset_id = str(params.get("asset_id") or "").strip()
        if not asset_id or "{{" in asset_id:
            continue
        seen[asset_id] = None
    return list(seen.keys())


def field_help(spec: dict[str, Any], extra: str = "") -> str:
    parts = []
    for key in ("help", "description", "placeholder"):
        text = str(spec.get(key) or "").strip()
        if text and text not in parts:
            parts.append(text)
    if extra:
        parts.append(extra)
    return "\n".join(parts)


def validate_asset_directories(definition: dict[str, Any], input_files: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for spec in definition.get("assets") or []:
        if not isinstance(spec, dict):
            continue
        key = str(spec.get("key") or "").strip()
        if not key:
            continue
        raw_path = str(input_files.get(key) or "").strip()
        label = str(spec.get("label") or key)
        if spec.get("required") and not raw_path:
            errors.append(f"请选择：{label}")
            continue
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.exists() or not path.is_dir():
            errors.append(f"{label}不存在或不是目录：{raw_path}")
            continue
        missing = [name for name in asset_requirements(definition, key) if not (path / name).exists()]
        if missing:
            errors.append(f"{label}缺少按钮截图文件：{', '.join(missing)}")
    return errors


def usage_blocks(definition: dict[str, Any]) -> list[dict[str, Any]]:
    guide = definition.get("usage_guide") if isinstance(definition.get("usage_guide"), dict) else {}
    blocks: list[dict[str, Any]] = []
    summary = str(guide.get("summary") or "").strip()
    if summary:
        blocks.append({"title": "工作流简介", "kind": "summary", "items": [summary]})
    block_specs = [
        ("输入文件要求", "input_requirements", "input"),
        ("文件命名规则", "file_naming_rules", "naming"),
        ("运行注意事项", "run_notes", "notes"),
    ]
    for title, key, kind in block_specs:
        values = [str(item).strip() for item in guide.get(key) or [] if str(item).strip()]
        if values:
            blocks.append({"title": title, "kind": kind, "items": values})
    assets = []
    for spec in definition.get("assets") or []:
        if not isinstance(spec, dict):
            continue
        names = asset_requirements(definition, str(spec.get("key") or ""))
        if names:
            assets.append(f"{spec.get('label') or spec.get('key')}需包含：" + "、".join(names))
    if assets:
        blocks.append({"title": "按钮截图要求", "kind": "asset", "items": assets})
    return blocks
