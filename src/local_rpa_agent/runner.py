from __future__ import annotations

import json
from typing import Any, Callable

from .auto_cert import append_line, load_auto_cert_rows
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
        base_row = runtime_row(run)
        rows = execution_rows(definition, base_row)
        if not rows:
            rows = [base_row]
        success = 0
        failed = 0
        last_error = ""
        for index, row in enumerate(rows, start=1):
            emit(f"执行第 {index}/{len(rows)} 组：{row.get('SPU ID') or '-'}")
            result = WorkflowExecutor().execute(definition, row=row, output_dir=str(base_row.get("output_dir") or ""))
            for item in result.logs:
                emit(f"[{item.node_id}] {item.node_type}: {'OK' if item.ok else 'FAILED'} - {item.message}")
            success += result.success_rows
            failed += result.failed_rows
            if result.failed_rows:
                last_error = result.logs[-1].message if result.logs else "workflow failed"
            else:
                mark_auto_cert_done(row)
        status = "failed" if failed and not success else "completed"
        client.update_run_status(token, run_id, status, success_rows=success, failed_rows=failed, error_message=last_error)
        emit(f"任务结束：成功 {success}，失败 {failed}")
    except Exception as exc:  # noqa: BLE001 - report failure to SaaS.
        client.update_run_status(token, run_id, "failed", failed_rows=1, error_message=str(exc))
        emit(f"任务失败：{exc}")


def runtime_row(run: dict[str, Any]) -> dict[str, Any]:
    input_files = parse_json_map(run.get("input_files"))
    runtime_params = parse_json_map(run.get("runtime_params"))
    row: dict[str, Any] = {**input_files, **runtime_params}
    row["__input"] = input_files
    row["__runtime"] = runtime_params
    if run.get("output_dir"):
        row["output_dir"] = run["output_dir"]
    return row


def parse_json_map(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def execution_rows(definition: dict[str, Any], base_row: dict[str, Any]) -> list[dict[str, Any]]:
    has_auto_cert = any(node.get("type") == "auto_cert_prepare_spu" for node in definition.get("nodes", []))
    if not has_auto_cert:
        return [base_row]
    prepared = load_auto_cert_rows(base_row)
    rows: list[dict[str, Any]] = []
    for item in prepared:
        row = {**base_row, **item}
        row["__input"] = base_row.get("__input", {})
        row["__runtime"] = base_row.get("__runtime", {})
        rows.append(row)
    return rows


def mark_auto_cert_done(row: dict[str, Any]) -> None:
    done_log = row.get("done_log")
    complete_log = row.get("complete_spu_log")
    sku_list = row.get("sku_list") or []
    if done_log:
        for sku in sku_list:
            append_line(done_log, str(sku))
    if complete_log and row.get("SPU ID"):
        append_line(complete_log, str(row["SPU ID"]))
