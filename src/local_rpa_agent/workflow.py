from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .actions import LocalActions

ROW_VAR_RE = re.compile(r"\{\{\s*row\.([^}]+?)\s*\}\}")


@dataclass
class ExecutionLog:
    node_id: str
    node_type: str
    ok: bool
    message: str


@dataclass
class ExecutionResult:
    success_rows: int = 0
    failed_rows: int = 0
    logs: list[ExecutionLog] = field(default_factory=list)


class WorkflowExecutor:
    def __init__(self, actions: LocalActions | None = None) -> None:
        self.actions = actions or LocalActions()

    def execute(self, definition: dict[str, Any], row: dict[str, Any] | None = None, output_dir: str = "") -> ExecutionResult:
        row = row or {}
        nodes = {node["node_id"]: node for node in definition.get("nodes", []) if node.get("node_id")}
        current = definition.get("entry_node")
        visited: set[str] = set()
        result = ExecutionResult()
        try:
            while current:
                if current in visited:
                    raise RuntimeError(f"workflow cycle detected at {current}")
                visited.add(current)
                node = nodes.get(current)
                if not node:
                    raise RuntimeError(f"node not found: {current}")
                log = self._execute_node(node, row, output_dir)
                result.logs.append(log)
                if not log.ok:
                    raise RuntimeError(log.message)
                current = self._next_node(node, row)
            result.success_rows = 1
        except Exception as exc:  # noqa: BLE001 - top-level workflow failure is returned to SaaS.
            result.failed_rows = 1
            if not result.logs or result.logs[-1].ok:
                result.logs.append(ExecutionLog(node_id=str(current or ""), node_type="workflow", ok=False, message=str(exc)))
        return result

    def _execute_node(self, node: dict[str, Any], row: dict[str, Any], output_dir: str) -> ExecutionLog:
        node_id = str(node.get("node_id", ""))
        node_type = str(node.get("type", ""))
        params = node.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        rendered = {key: render_template(value, row, output_dir) for key, value in params.items()}
        if node_type == "log":
            message = str(rendered.get("message", ""))
            return ExecutionLog(node_id, node_type, True, message)
        if node_type == "focus_window":
            action = self.actions.focus_window(rendered)
        elif node_type == "click_image":
            action = self.actions.click_image(rendered)
        elif node_type == "type_text":
            action = self.actions.type_text(rendered, str(rendered.get("text", "")))
        elif node_type == "select_option":
            action = self.actions.select_option(rendered, str(rendered.get("value", "")))
        elif node_type == "upload_file":
            action = self.actions.upload_file(rendered, str(rendered.get("path", "")))
        elif node_type == "sleep":
            action = self.actions.sleep(float(rendered.get("seconds", 1) or 1))
        elif node_type == "condition":
            action = self.actions.sleep(0)
        else:
            action = self.actions.sleep(0)
            action.message = f"unsupported node type placeholder: {node_type}"
        return ExecutionLog(node_id, node_type, action.ok, action.message)

    def _next_node(self, node: dict[str, Any], row: dict[str, Any]) -> str:
        if node.get("type") != "condition":
            return str(node.get("next") or "")
        branches = (node.get("params") or {}).get("branches") or []
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            when = str(branch.get("when") or "")
            if evaluate_condition(when, row):
                return str(branch.get("next") or "")
        return str(node.get("next") or "")


def render_template(value: Any, row: dict[str, Any], output_dir: str = "") -> Any:
    if not isinstance(value, str):
        return value
    def replace(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        if name == "output_dir":
            return output_dir
        return str(row.get(name, ""))
    return ROW_VAR_RE.sub(replace, value)


def evaluate_condition(expression: str, row: dict[str, Any]) -> bool:
    expression = expression.strip()
    if not expression:
        return False
    if "==" in expression:
        left, right = [part.strip().strip("\'\"") for part in expression.split("==", 1)]
        if left.startswith("row."):
            return str(row.get(left[4:], "")) == right
    if expression.startswith("row."):
        return bool(row.get(expression[4:]))
    return False
