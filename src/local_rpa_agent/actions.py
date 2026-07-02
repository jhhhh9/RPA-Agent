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
        mode = str(params.get("input_mode") or params.get("mode") or "replace").strip()
        if not pyautogui:
            return ActionResult(True, f"type_text placeholder: mode={mode}, text={text}")
        if mode in {"replace", "clear_only"}:
            pyautogui.hotkey("ctrl", "a")
            pyautogui.press("backspace")
            time.sleep(float(params.get("clear_sleep") or 0.1))
        if mode == "clear_only":
            return ActionResult(True, "cleared text input")
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
        upload_mode = str(params.get("upload_mode") or "multi_select").strip()
        if upload_mode == "one_by_one":
            for item in paths:
                paste_text(f'"{item}"')
                pyautogui.press("enter")
                time.sleep(float(params.get("after_sleep") or 1.8))
                self.secure_confirm(params)
        else:
            multi = " ".join([f'"{item}"' for item in paths])
            paste_text(multi)
            pyautogui.press("enter")
            time.sleep(float(params.get("after_sleep") or 1.8))
            self.secure_confirm(params)
        return ActionResult(True, f"uploaded {len(paths)} file(s)")

    def optional_click(self, params: dict[str, Any]) -> ActionResult:
        strategy = str(params.get("strategy") or "coordinate_click_twice").strip()
        if strategy != "coordinate_click_twice":
            return ActionResult(False, f"unsupported optional_click strategy: {strategy}")
        if "guard_value" in params and is_blank(params.get("guard_value")):
            return ActionResult(True, "optional_click skipped empty guard_value")
        x = int(float(params.get("x") or params.get("secure_confirm_x") or 0))
        y = int(float(params.get("y") or params.get("secure_confirm_y") or 0))
        if not x or not y:
            return ActionResult(True, "optional_click skipped empty coordinate")
        if not pyautogui:
            return ActionResult(True, f"optional_click placeholder: {x},{y}")
        clicks = max(1, int(float(params.get("clicks") or 2)))
        interval = max(0.0, float(params.get("interval") or 0.4))
        before_sleep = max(0.0, float(params.get("before_sleep") or 0.4))
        time.sleep(before_sleep)
        for index in range(clicks):
            pyautogui.click(x, y, duration=0.12)
            if index < clicks - 1:
                time.sleep(interval)
        return ActionResult(True, f"optional_click coordinate {x},{y} x{clicks}")

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

    def append_log(self, params: dict[str, Any]) -> ActionResult:
        path = Path(str(params.get("path") or "")).expanduser()
        if not str(path):
            return ActionResult(False, "append_log missing path")
        lines = normalize_paths(params.get("content"))
        if not lines:
            return ActionResult(True, "append_log skipped empty content")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for line in lines:
                fh.write(str(line) + "\n")
        return ActionResult(True, f"append_log wrote {len(lines)} line(s)")

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
        return [normalize_path_text(str(item)) for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if ";" in text:
        return [normalize_path_text(item.strip().strip('"')) for item in text.split(";") if item.strip()]
    return [normalize_path_text(text.strip('"'))]


def normalize_path_text(value: str) -> str:
    text = value.strip().strip('"')
    if re_drive_path(text):
        return text.replace("/", "\\")
    return text


def re_drive_path(value: str) -> bool:
    return len(value) >= 3 and value[1] == ":" and value[0].isalpha()


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return str(value).strip() == ""


def paste_text(text: str) -> None:
    if pyperclip:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    else:
        pyautogui.write(text)
    time.sleep(0.4)
