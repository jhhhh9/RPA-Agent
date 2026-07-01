from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


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
