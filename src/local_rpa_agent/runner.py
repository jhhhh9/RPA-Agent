from __future__ import annotations

import json
from typing import Any, Callable

from .client import SaaSClient
from .workflow import WorkflowExecutor

LogFn = Callable[[str], None]


def execute_run(client: SaaSClient, token: str, run: dict[str, Any], log: LogFn | None = None) -> None:
    def emit(message: str) -> None:
        if log:
            log(message)

    run_id = run["id"]
    emit(f"开始执行任务：{run_id}")
    client.update_run_status(token, run_id, "running")
    try:
        definition = run.get("workflow_snapshot") or {}
        if isinstance(definition, str):
            definition = json.loads(definition)
        row = runtime_row(run)
        result = WorkflowExecutor().execute(definition, row=row, output_dir=run.get("output_dir") or "")
        for item in result.logs:
            emit(f"[{item.node_id}] {item.node_type}: {'OK' if item.ok else 'FAILED'} - {item.message}")
        if result.failed_rows:
            message = result.logs[-1].message if result.logs else "workflow failed"
            client.update_run_status(token, run_id, "failed", success_rows=result.success_rows, failed_rows=result.failed_rows, error_message=message)
            emit(f"任务失败：{message}")
            return
        client.update_run_status(token, run_id, "completed", success_rows=result.success_rows, failed_rows=result.failed_rows)
        emit(f"任务完成：{run_id}")
    except Exception as exc:  # noqa: BLE001 - report failure to SaaS.
        client.update_run_status(token, run_id, "failed", failed_rows=1, error_message=str(exc))
        emit(f"任务失败：{exc}")


def runtime_row(run: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key in ("input_files", "runtime_params"):
        value = run.get(key) or {}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = {}
        if isinstance(value, dict):
            row.update(value)
    if run.get("output_dir"):
        row["output_dir"] = run["output_dir"]
    return row
