from __future__ import annotations

import json
import time
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from .client import SaaSClient
from .config import AgentConfig
from .storage import AgentState, load_state, save_state
from .workflow import WorkflowExecutor

app = typer.Typer(help="Local RPA Agent for AI Business SaaS")
console = Console()


@app.command()
def bind(code: str, base_url: str | None = None, config_path: str | None = None) -> None:
    """Bind this device with a one-time code generated in SaaS."""
    cfg = AgentConfig.load(base_url=base_url, config_path=config_path)
    client = SaaSClient(cfg.base_url)
    data = client.bind(code, cfg.device_name, cfg.os_type, cfg.version)
    agent = data["agent"]
    token = data["token"]
    save_state(cfg.config_path, AgentState(agent_id=agent["id"], tenant_id=agent["tenant_id"], user_id=agent["user_id"], token=token))
    console.print(f"[green]Bound local agent:[/] {agent['id']}")
    console.print(f"Config saved to {cfg.config_path}")


@app.command()
def heartbeat(base_url: str | None = None, config_path: str | None = None) -> None:
    cfg, state, client = load_runtime(base_url, config_path)
    data = client.heartbeat(state.token, cfg.version)
    console.print_json(json.dumps(data, ensure_ascii=False))


@app.command()
def once(base_url: str | None = None, config_path: str | None = None) -> None:
    """Poll and execute one pending run."""
    cfg, state, client = load_runtime(base_url, config_path)
    run = client.next_run(state.token)
    if not run:
        console.print("[cyan]No pending run.[/]")
        return
    execute_run(client, state.token, run)


@app.command()
def service(interval: float = 5.0, base_url: str | None = None, config_path: str | None = None) -> None:
    """Run forever and poll SaaS for automation runs."""
    cfg, state, client = load_runtime(base_url, config_path)
    console.print(f"[green]Agent service started.[/] base_url={cfg.base_url}, interval={interval}s")
    while True:
        try:
            client.heartbeat(state.token, cfg.version)
            run = client.next_run(state.token)
            if run:
                execute_run(client, state.token, run)
        except Exception as exc:  # noqa: BLE001 - local service loop must stay alive.
            console.print(f"[red]Agent loop error:[/] {exc}")
        time.sleep(max(1.0, interval))


def load_runtime(base_url: str | None, config_path: str | None) -> tuple[AgentConfig, AgentState, SaaSClient]:
    cfg = AgentConfig.load(base_url=base_url, config_path=config_path)
    state = load_state(cfg.config_path)
    if not state:
        raise typer.BadParameter(f"Agent is not bound. Run: local-rpa-agent bind <code>. Config path: {cfg.config_path}")
    return cfg, state, SaaSClient(cfg.base_url)


def execute_run(client: SaaSClient, token: str, run: dict[str, Any]) -> None:
    run_id = run["id"]
    console.print(f"[blue]Executing run[/] {run_id}")
    client.update_run_status(token, run_id, "running")
    try:
        definition = run.get("workflow_snapshot") or {}
        if isinstance(definition, str):
            definition = json.loads(definition)
        result = WorkflowExecutor().execute(definition, row={}, output_dir=run.get("output_dir") or "")
        print_logs(result.logs)
        if result.failed_rows:
            message = result.logs[-1].message if result.logs else "workflow failed"
            client.update_run_status(token, run_id, "failed", success_rows=result.success_rows, failed_rows=result.failed_rows, error_message=message)
            console.print(f"[red]Run failed:[/] {message}")
            return
        client.update_run_status(token, run_id, "completed", success_rows=result.success_rows, failed_rows=result.failed_rows)
        console.print(f"[green]Run completed:[/] {run_id}")
    except Exception as exc:  # noqa: BLE001 - report failure to SaaS.
        client.update_run_status(token, run_id, "failed", failed_rows=1, error_message=str(exc))
        console.print(f"[red]Run failed:[/] {exc}")


def print_logs(logs: list[Any]) -> None:
    if not logs:
        return
    table = Table(title="Workflow Logs")
    table.add_column("Node")
    table.add_column("Type")
    table.add_column("OK")
    table.add_column("Message")
    for item in logs:
        table.add_row(item.node_id, item.node_type, "yes" if item.ok else "no", item.message)
    console.print(table)


if __name__ == "__main__":
    app()
