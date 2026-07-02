from __future__ import annotations

import json
import time
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from .capabilities import LOCAL_CAPABILITIES, capability_labels
from .client import SaaSClient
from .config import AgentConfig
from .storage import AgentState, load_state, save_state
from .runner import execute_run as execute_agent_run

app = typer.Typer(help="Local RPA Agent for AI Business SaaS")
console = Console()


@app.command()
def bind(code: str, base_url: str | None = None, config_path: str | None = None) -> None:
    """Bind this device with a one-time code generated in SaaS."""
    cfg = AgentConfig.load(base_url=base_url, config_path=config_path)
    client = SaaSClient(cfg.base_url)
    data = client.bind(code, cfg.device_name, cfg.os_type, cfg.version, cfg.device_fingerprint, LOCAL_CAPABILITIES)
    agent = data["agent"]
    token = data["token"]
    save_state(cfg.config_path, AgentState(agent_id=agent["id"], tenant_id=agent["tenant_id"], user_id=agent["user_id"], token=token))
    console.print(f"[green]Bound local agent:[/] {agent['id']}")
    console.print(f"Config saved to {cfg.config_path}")


@app.command()
def heartbeat(base_url: str | None = None, config_path: str | None = None) -> None:
    cfg, state, client = load_runtime(base_url, config_path)
    data = client.heartbeat(state.token, cfg.version, LOCAL_CAPABILITIES)
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
            client.heartbeat(state.token, cfg.version, LOCAL_CAPABILITIES)
            run = client.next_run(state.token)
            if run:
                execute_run(client, state.token, run)
        except Exception as exc:  # noqa: BLE001 - local service loop must stay alive.
            console.print(f"[red]Agent loop error:[/] {exc}")
        time.sleep(max(1.0, interval))


@app.command()
def capabilities() -> None:
    """Print local Agent capabilities reported to SaaS."""
    table = Table(title="Local Agent Capabilities")
    table.add_column("Capability")
    table.add_column("Name")
    for value, label in zip(LOCAL_CAPABILITIES, capability_labels(LOCAL_CAPABILITIES), strict=False):
        table.add_row(value, label)
    console.print(table)


def load_runtime(base_url: str | None, config_path: str | None) -> tuple[AgentConfig, AgentState, SaaSClient]:
    cfg = AgentConfig.load(base_url=base_url, config_path=config_path)
    state = load_state(cfg.config_path)
    if not state:
        raise typer.BadParameter(f"Agent is not bound. Run: local-rpa-agent bind <code>. Config path: {cfg.config_path}")
    return cfg, state, SaaSClient(cfg.base_url)


def execute_run(client: SaaSClient, token: str, run: dict[str, Any]) -> None:
    execute_agent_run(client, token, run, log=lambda message: console.print(message))


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
