from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .capabilities import LOCAL_CAPABILITIES, capability_labels, missing_capabilities
from .data_pipeline import run_data_pipeline_with_trace
from .workflow import WorkflowExecutor

if TYPE_CHECKING:
    from .client import SaaSClient

LogFn = Callable[[str], None]
StopFn = Callable[[], bool]


def execute_run(client: "SaaSClient", token: str, run: dict[str, Any], log: LogFn | None = None, should_stop: StopFn | None = None) -> None:
    def emit(message: str) -> None:
        if log:
            log(message)

    run_id = run['id']
    stop_requested = make_stop_checker(client, token, run_id, should_stop)
    emit(f'开始执行任务：{run_id}')
    client.update_run_status(token, run_id, 'running')
    success = 0
    failed = 0
    last_error = ''
    try:
        definition = run.get('workflow_snapshot') or {}
        if isinstance(definition, str):
            definition = json.loads(definition)
        missing = missing_capabilities(definition.get('required_capabilities') or [], LOCAL_CAPABILITIES)
        if missing:
            message = '本地 Agent 缺少工作流能力：' + '、'.join(capability_labels(missing))
            client.update_run_status(token, run_id, 'failed', failed_rows=max(1, failed), error_message=message)
            emit(message)
            return
        base_row = runtime_row(run)
        rows, pipeline_trace = execution_rows_with_trace(definition, base_row)
        if pipeline_trace:
            trace_path = write_pipeline_trace(base_row, pipeline_trace)
            if trace_path:
                emit(f"数据管道明细已写入：{trace_path}")
        if not rows:
            rows = [base_row]
        for index, row in enumerate(rows, start=1):
            if stop_requested():
                client.update_run_status(token, run_id, 'stopped', success_rows=success, failed_rows=failed, error_message=last_error)
                emit('任务已停止')
                return
            emit(f"执行第 {index}/{len(rows)} 组：{row.get('SPU ID') or '-'}")
            result = WorkflowExecutor().execute(definition, row=row, output_dir=str(base_row.get('output_dir') or ''), should_stop=stop_requested)
            for item in result.logs:
                emit(f"[{item.node_id}] {item.node_type}: {'OK' if item.ok else 'FAILED'} - {item.message}")
            if result.stopped:
                client.update_run_status(token, run_id, 'stopped', success_rows=success, failed_rows=failed, error_message=last_error)
                emit('任务已停止')
                return
            success += result.success_rows
            failed += result.failed_rows
            if result.failed_rows:
                last_error = result.logs[-1].message if result.logs else 'workflow failed'
        status = 'failed' if failed and not success else 'completed'
        client.update_run_status(token, run_id, status, success_rows=success, failed_rows=failed, error_message=last_error)
        emit(f'任务结束：成功 {success}，失败 {failed}')
    except Exception as exc:  # noqa: BLE001 - report failure to SaaS.
        if stop_requested():
            client.update_run_status(token, run_id, 'stopped', success_rows=success, failed_rows=failed, error_message=last_error)
            emit('任务已停止')
            return
        client.update_run_status(token, run_id, 'failed', failed_rows=max(1, failed), error_message=str(exc))
        emit(f'任务失败：{exc}')


def make_stop_checker(client: "SaaSClient", token: str, run_id: str, local_stop: StopFn | None = None) -> StopFn:
    last_check = 0.0
    server_stopping = False

    def check() -> bool:
        nonlocal last_check, server_stopping
        if local_stop and local_stop():
            return True
        now = time.monotonic()
        if server_stopping or now - last_check < 2.0:
            return server_stopping
        last_check = now
        try:
            current = client.run(token, run_id)
            server_stopping = str(current.get('status') or '') == 'stopping'
        except Exception:
            server_stopping = False
        return server_stopping

    return check


def runtime_row(run: dict[str, Any]) -> dict[str, Any]:
    input_files = parse_json_map(run.get('input_files'))
    runtime_params = parse_json_map(run.get('runtime_params'))
    row: dict[str, Any] = {**input_files, **runtime_params}
    row['__input'] = input_files
    row['__runtime'] = runtime_params
    if run.get('output_dir'):
        row['output_dir'] = run['output_dir']
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
    rows, _trace = execution_rows_with_trace(definition, base_row)
    return rows


def execution_rows_with_trace(definition: dict[str, Any], base_row: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    prepared, trace = run_data_pipeline_with_trace(definition, base_row)
    rows: list[dict[str, Any]] = []
    for item in prepared:
        row = {**base_row, **item}
        row['__input'] = base_row.get('__input', {})
        row['__runtime'] = base_row.get('__runtime', {})
        rows.append(row)
    return rows, trace


def write_pipeline_trace(base_row: dict[str, Any], trace: list[dict[str, Any]]) -> str:
    output_dir = str(base_row.get('output_dir') or '').strip()
    if not output_dir:
        return ''
    path = Path(output_dir).expanduser() / 'pipeline_trace.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(path)


def preview_data_pipeline(definition: dict[str, Any], base_row: dict[str, Any], sample_limit: int = 5) -> dict[str, Any]:
    """Run the local data pipeline only, without creating a SaaS run or touching UI automation."""
    missing = missing_capabilities(definition.get('required_capabilities') or [], LOCAL_CAPABILITIES)
    if missing:
        return {"ok": False, "error": "本地 Agent 缺少工作流能力：" + "、".join(capability_labels(missing)), "total": 0, "sample": []}
    rows, trace = execution_rows_with_trace(definition, base_row)
    return {"ok": True, "total": len(rows), "sample": rows[:max(0, sample_limit)], "trace": trace}
