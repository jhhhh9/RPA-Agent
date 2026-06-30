from __future__ import annotations

from typing import Any

import httpx


class SaaSClient:
    def __init__(self, base_url: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def bind(self, code: str, device_name: str, os_type: str, version: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/automation/agents/bind",
            json={"code": code, "device_name": device_name, "os_type": os_type, "agent_version": version},
        )

    def heartbeat(self, token: str, version: str) -> dict[str, Any]:
        return self._request("POST", "/api/automation/agents/heartbeat", token=token, json={"agent_version": version})

    def next_run(self, token: str) -> dict[str, Any] | None:
        data = self._request("GET", "/api/automation/agents/runs/next", token=token)
        return data.get("run")

    def update_run_status(
        self,
        token: str,
        run_id: str,
        status: str,
        success_rows: int = 0,
        failed_rows: int = 0,
        error_message: str = "",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/automation/agents/runs/{run_id}/status",
            token=token,
            json={
                "status": status,
                "success_rows": success_rows,
                "failed_rows": failed_rows,
                "error_message": error_message,
            },
        )

    def _request(self, method: str, path: str, token: str | None = None, **kwargs: Any) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
