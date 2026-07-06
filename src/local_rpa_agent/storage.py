from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AgentState:
    agent_id: str
    tenant_id: str
    user_id: str
    token: str


def load_state(path: Path) -> AgentState | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return AgentState(**data)


def save_state(path: Path, state: AgentState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        # Windows may not support POSIX chmod semantics; the token is still stored in the user profile path.
        pass


def clear_state(path: Path) -> None:
    if path.exists():
        path.unlink()


def template_store_path(config_path: Path) -> Path:
    return config_path.with_name(config_path.stem + ".templates.json")


def _load_template_store(config_path: Path) -> dict[str, Any]:
    path = template_store_path(config_path)
    if not path.exists():
        return {"templates": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"templates": []}
    templates = data.get("templates")
    if not isinstance(templates, list):
        data["templates"] = []
    return data


def _save_template_store(config_path: Path, data: dict[str, Any]) -> None:
    path = template_store_path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_local_templates(config_path: Path, workflow_id: str) -> list[dict[str, Any]]:
    data = _load_template_store(config_path)
    rows = [
        item for item in data.get("templates", [])
        if isinstance(item, dict) and str(item.get("workflow_id") or "") == workflow_id
    ]
    return sorted(rows, key=lambda item: str(item.get("updated_at") or ""), reverse=True)


def save_local_template(
    config_path: Path,
    workflow_id: str,
    name: str,
    input_files: dict[str, Any],
    runtime_params: dict[str, Any],
    output_dir: str,
    template_id: str | None = None,
) -> dict[str, Any]:
    data = _load_template_store(config_path)
    now = datetime.now(timezone.utc).isoformat()
    templates = [item for item in data.get("templates", []) if isinstance(item, dict)]
    existing = next((item for item in templates if str(item.get("id") or "") == str(template_id or "")), None)
    if existing is None and not template_id:
        existing = next(
            (
                item for item in templates
                if str(item.get("workflow_id") or "") == workflow_id and str(item.get("name") or "") == name
            ),
            None,
        )
    row = {
        "id": str(existing.get("id") if existing else template_id or uuid.uuid4()),
        "workflow_id": workflow_id,
        "name": name,
        "input_files": input_files,
        "runtime_params": runtime_params,
        "output_dir": output_dir,
        "created_at": str(existing.get("created_at") if existing else now),
        "updated_at": now,
    }
    templates = [item for item in templates if str(item.get("id") or "") != row["id"]]
    templates.append(row)
    data["templates"] = templates
    _save_template_store(config_path, data)
    return row


def delete_local_template(config_path: Path, workflow_id: str, template_id: str) -> None:
    data = _load_template_store(config_path)
    data["templates"] = [
        item for item in data.get("templates", [])
        if not (
            isinstance(item, dict)
            and str(item.get("workflow_id") or "") == workflow_id
            and str(item.get("id") or "") == template_id
        )
    ]
    _save_template_store(config_path, data)
