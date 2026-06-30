from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class ActionResult:
    ok: bool
    message: str


class LocalActions:
    """Local desktop/browser action adapter.

    当前先做安全占位：只记录将要执行的动作，不真正控制鼠标键盘。
    后续接入 pyautogui/OpenCV 时，只需要替换这里，不影响 SaaS 协议和 workflow 解释器。
    """

    def focus_window(self, params: dict[str, Any]) -> ActionResult:
        title = params.get("window_title_contains") or params.get("title") or ""
        return ActionResult(True, f"focus_window placeholder: {title}")

    def click_image(self, params: dict[str, Any]) -> ActionResult:
        return ActionResult(True, f"click_image placeholder: {params.get('asset_id') or params.get('image') or '-'}")

    def type_text(self, params: dict[str, Any], text: str) -> ActionResult:
        return ActionResult(True, f"type_text placeholder: {text}")

    def select_option(self, params: dict[str, Any], value: str) -> ActionResult:
        return ActionResult(True, f"select_option placeholder: {value}")

    def upload_file(self, params: dict[str, Any], path: str) -> ActionResult:
        return ActionResult(True, f"upload_file placeholder: {path}")

    def sleep(self, seconds: float) -> ActionResult:
        seconds = max(0.0, min(seconds, 60.0))
        time.sleep(seconds)
        return ActionResult(True, f"sleep {seconds}s")
