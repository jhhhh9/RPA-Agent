from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .actions import LocalActions

VAR_RE = re.compile(r'\{\{\s*(row|input|runtime|output)\.([^}]+?)\s*\}\}')
StopCheck = Callable[[], bool]


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
    stopped: bool = False
    logs: list[ExecutionLog] = field(default_factory=list)


class WorkflowExecutor:
    def __init__(self, actions: LocalActions | None = None) -> None:
        self.actions = actions or LocalActions()

    def execute(
        self,
        definition: dict[str, Any],
        row: dict[str, Any] | None = None,
        output_dir: str = '',
        should_stop: StopCheck | None = None,
    ) -> ExecutionResult:
        row = row or {}
        nodes = {node['node_id']: node for node in definition.get('nodes', []) if node.get('node_id')}
        edges_by_from = build_edges(definition)
        current = definition.get('entry_node')
        visited: set[str] = set()
        result = ExecutionResult()
        try:
            while current:
                if should_stop and should_stop():
                    result.stopped = True
                    result.logs.append(ExecutionLog(node_id=str(current), node_type='workflow', ok=True, message='任务已收到停止信号'))
                    return result
                if current in visited:
                    raise RuntimeError(f'workflow cycle detected at {current}')
                visited.add(current)
                node = nodes.get(current)
                if not node:
                    raise RuntimeError(f'node not found: {current}')
                log = self._execute_node(node, row, output_dir)
                result.logs.append(log)
                if not log.ok:
                    raise RuntimeError(log.message)
                current = self._next_node(node, row, edges_by_from)
            result.success_rows = 1
        except Exception as exc:  # noqa: BLE001 - top-level workflow failure is returned to SaaS.
            result.failed_rows = 1
            if not result.logs or result.logs[-1].ok:
                result.logs.append(ExecutionLog(node_id=str(current or ''), node_type='workflow', ok=False, message=str(exc)))
        return result

    def _execute_node(self, node: dict[str, Any], row: dict[str, Any], output_dir: str) -> ExecutionLog:
        node_id = str(node.get('node_id', ''))
        node_type = str(node.get('type', ''))
        params = node.get('params') or {}
        if not isinstance(params, dict):
            params = {}
        rendered = {key: render_template(value, row, output_dir) for key, value in params.items()}
        if node_type == 'log':
            message = str(rendered.get('message', ''))
            return ExecutionLog(node_id, node_type, True, message)
        if node_type == 'focus_window':
            action = self.actions.focus_window(rendered)
        elif node_type == 'auto_cert_prepare_spu':
            action = self.actions.auto_cert_prepare_spu(rendered, row)
        elif node_type == 'click_image':
            action = self.actions.click_image(rendered)
        elif node_type == 'click_coordinate':
            action = self.actions.click_coordinate(rendered)
        elif node_type == 'type_text':
            action = self.actions.type_text(rendered, str(rendered.get('text', '')))
        elif node_type == 'select_option':
            action = self.actions.select_option(rendered, str(rendered.get('value', '')))
        elif node_type == 'upload_file':
            action = self.actions.upload_file(rendered, rendered.get('path', ''))
        elif node_type == 'scroll':
            action = self.actions.scroll(float(rendered.get('amount', -220) or -220))
        elif node_type == 'sleep':
            action = self.actions.sleep(float(rendered.get('seconds', 1) or 1))
        elif node_type == 'condition':
            action = self.actions.sleep(0)
        else:
            action = self.actions.sleep(0)
            action.message = f'unsupported node type placeholder: {node_type}'
        return ExecutionLog(node_id, node_type, action.ok, action.message)

    def _next_node(self, node: dict[str, Any], row: dict[str, Any], edges_by_from: dict[str, list[dict[str, Any]]]) -> str:
        outgoing = edges_by_from.get(str(node.get('node_id') or ''), [])
        if outgoing:
            for edge in outgoing:
                condition = str(edge.get('condition') or '').strip()
                if condition and evaluate_condition(condition, row):
                    return str(edge.get('to') or '')
            for edge in outgoing:
                if not str(edge.get('condition') or '').strip():
                    return str(edge.get('to') or '')
            return ''
        if node.get('type') != 'condition':
            return str(node.get('next') or '')
        branches = (node.get('params') or {}).get('branches') or []
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            when = str(branch.get('when') or '')
            if evaluate_condition(when, row):
                return str(branch.get('next') or '')
        return str(node.get('next') or '')


def build_edges(definition: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    raw_edges = definition.get('edges') or []
    if not raw_edges:
        raw_edges = []
        for node in definition.get('nodes', []):
            if node.get('next'):
                raw_edges.append({'from': node.get('node_id'), 'to': node.get('next')})
    out: dict[str, list[dict[str, Any]]] = {}
    for edge in raw_edges:
        if not isinstance(edge, dict):
            continue
        from_id = str(edge.get('from') or '')
        to_id = str(edge.get('to') or '')
        if from_id and to_id:
            out.setdefault(from_id, []).append(edge)
    return out


def render_template(value: Any, row: dict[str, Any], output_dir: str = '') -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    full = VAR_RE.fullmatch(stripped)
    if full:
        return lookup(full.group(1), full.group(2).strip(), row, output_dir)

    def replace(match: re.Match[str]) -> str:
        return str(lookup(match.group(1), match.group(2).strip(), row, output_dir) or '')

    return VAR_RE.sub(replace, value)


def lookup(scope: str, name: str, row: dict[str, Any], output_dir: str) -> Any:
    if scope == 'output':
        return output_dir if name in {'dir', 'output_dir'} else ''
    scoped = row.get(f'__{scope}')
    if isinstance(scoped, dict) and name in scoped:
        return scoped[name]
    return row.get(name, '')


def evaluate_condition(expression: str, row: dict[str, Any]) -> bool:
    expression = expression.strip()
    if not expression:
        return False
    if '==' in expression:
        left, right = [part.strip().strip("'\"") for part in expression.split('==', 1)]
        return str(resolve_condition_value(left, row)) == right
    if '!=' in expression:
        left, right = [part.strip().strip("'\"") for part in expression.split('!=', 1)]
        return str(resolve_condition_value(left, row)) != right
    return bool(resolve_condition_value(expression, row))


def resolve_condition_value(name: str, row: dict[str, Any]) -> Any:
    if name.startswith('row.'):
        return row.get(name[4:], '')
    if name.startswith('input.') and isinstance(row.get('__input'), dict):
        return row['__input'].get(name[6:], '')
    if name.startswith('runtime.') and isinstance(row.get('__runtime'), dict):
        return row['__runtime'].get(name[8:], '')
    return row.get(name, '')
