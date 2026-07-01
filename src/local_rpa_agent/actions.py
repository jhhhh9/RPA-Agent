from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # Optional until the Windows package installs GUI automation dependencies.
    import pyautogui
except Exception:  # noqa: BLE001
    pyautogui = None  # type: ignore[assignment]

try:
    import pyperclip
except Exception:  # noqa: BLE001
    pyperclip = None  # type: ignore[assignment]


@dataclass
class ActionResult:
    ok: bool
    message: str


class LocalActions:
    """Local desktop/browser action adapter.

    SaaS 只下发结构化 workflow；真正读取本地路径、截图匹配、键盘鼠标操作都在这里。
    """

    def focus_window(self, params: dict[str, Any]) -> ActionResult:
        title = params.get("window_title_contains") or params.get("title") or ""
        if not pyautogui:
            return ActionResult(True, f"focus_window placeholder: {title}")
        # pyautogui 本身没有稳定跨平台聚焦窗口 API；Windows 后续可接 pygetwindow。
        return ActionResult(True, f"focus_window requested: {title}")

    def auto_cert_prepare_spu(self, params: dict[str, Any], row: dict[str, Any]) -> ActionResult:
        spu = row.get("SPU ID") or "-"
        return ActionResult(True, f"auto_cert prepared SPU {spu}")

    def click_image(self, params: dict[str, Any]) -> ActionResult:
        path = resolve_asset_path(params)
        threshold = float(params.get("threshold") or params.get("confidence") or 0.85)
        if not path:
            return ActionResult(False, "click_image missing asset_id")
        if not pyautogui:
            return ActionResult(True, f"click_image placeholder: {path}")
        if not Path(path).exists():
            return ActionResult(False, f"按钮截图不存在: {path}")
        retry = int(params.get("retry") or 7)
        for _ in range(max(1, retry)):
            try:
                pos = pyautogui.locateCenterOnScreen(path, confidence=threshold)
                if pos:
                    pyautogui.click(pos, duration=0.12)
                    time.sleep(float(params.get("after_sleep") or 0.8))
                    return ActionResult(True, f"clicked image {path} at {pos.x},{pos.y}")
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                time.sleep(0.5)
                continue
            time.sleep(0.5)
        return ActionResult(False, f"图片匹配失败: {path}; threshold={threshold}; {locals().get('last_error', '')}")

    def click_coordinate(self, params: dict[str, Any]) -> ActionResult:
        x = int(float(params.get("x") or 0))
        y = int(float(params.get("y") or 0))
        if not x or not y:
            return ActionResult(False, "click_coordinate requires x and y")
        if not pyautogui:
            return ActionResult(True, f"click_coordinate placeholder: {x},{y}")
        pyautogui.click(x, y, duration=0.12)
        time.sleep(float(params.get("after_sleep") or 0.8))
        return ActionResult(True, f"clicked coordinate {x},{y}")

    def type_text(self, params: dict[str, Any], text: str) -> ActionResult:
        if not pyautogui:
            return ActionResult(True, f"type_text placeholder: {text}")
        paste_text(text)
        return ActionResult(True, f"typed text: {text}")

    def select_option(self, params: dict[str, Any], value: str) -> ActionResult:
        if not pyautogui:
            return ActionResult(True, f"select_option placeholder: {value}")
        paste_text(value)
        pyautogui.press("enter")
        return ActionResult(True, f"selected option: {value}")

    def upload_file(self, params: dict[str, Any], path: Any) -> ActionResult:
        paths = normalize_paths(path)
        if not paths:
            if params.get("optional"):
                return ActionResult(True, "upload_file skipped optional empty path")
            return ActionResult(False, "upload_file missing path")
        missing = [item for item in paths if not Path(item).exists()]
        if missing and not params.get("allow_missing"):
            return ActionResult(False, "文件不存在: " + ", ".join(missing[:3]))
        if not pyautogui:
            return ActionResult(True, f"upload_file placeholder: {paths}")
        multi = " ".join([f'"{item}"' for item in paths])
        paste_text(multi)
        pyautogui.press("enter")
        time.sleep(float(params.get("after_sleep") or 1.8))
        self.secure_confirm(params)
        return ActionResult(True, f"uploaded {len(paths)} file(s)")

    def scroll(self, amount: float) -> ActionResult:
        if not pyautogui:
            return ActionResult(True, f"scroll placeholder: {amount}")
        pyautogui.scroll(int(amount))
        time.sleep(0.6)
        return ActionResult(True, f"scroll {amount}")

    def sleep(self, seconds: float) -> ActionResult:
        seconds = max(0.0, min(seconds, 120.0))
        time.sleep(seconds)
        return ActionResult(True, f"sleep {seconds}s")

    def secure_confirm(self, params: dict[str, Any]) -> None:
        if not pyautogui:
            return
        x = int(float(params.get("secure_confirm_x") or 0))
        y = int(float(params.get("secure_confirm_y") or 0))
        if x and y:
            time.sleep(0.4)
            pyautogui.click(x, y, duration=0.12)
            time.sleep(0.4)
            pyautogui.click(x, y, duration=0.12)


def resolve_asset_path(params: dict[str, Any]) -> str:
    asset_id = str(params.get("asset_id") or params.get("image") or "").strip()
    if not asset_id:
        return ""
    path = Path(asset_id).expanduser()
    if path.is_absolute():
        return str(path)
    asset_dir = str(params.get("asset_dir") or params.get("button_asset_dir") or "").strip()
    if asset_dir:
        return str((Path(asset_dir).expanduser() / asset_id).resolve())
    return asset_id


def normalize_paths(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if ";" in text:
        return [item.strip().strip('"') for item in text.split(";") if item.strip()]
    return [text.strip('"')]


def paste_text(text: str) -> None:
    if pyperclip:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    else:
        pyautogui.write(text)
    time.sleep(0.4)
