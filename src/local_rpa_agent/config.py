from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentConfig:
    base_url: str
    config_path: Path
    version: str
    device_name: str
    os_type: str

    @staticmethod
    def load(base_url: str | None = None, config_path: str | None = None) -> "AgentConfig":
        path_value = config_path or os.getenv("AGENT_CONFIG_PATH", "~/.local-rpa-agent/config.json")
        device_name = os.getenv("DEVICE_NAME") or platform.node() or "local-agent"
        return AgentConfig(
            base_url=(base_url or os.getenv("SAAS_BASE_URL") or "http://127.0.0.1:8080").rstrip("/"),
            config_path=Path(path_value).expanduser(),
            version=os.getenv("AGENT_VERSION", "0.1.0"),
            device_name=device_name,
            os_type=platform.platform(),
        )
