from __future__ import annotations

from typing import Iterable

LOCAL_CAPABILITIES: list[str] = [
    "data_pipeline@1",
    "read_table@1",
    "group_rows@1",
    "filter_completed@1",
    "derive_regex_list@1",
    "list_files@1",
    "match_files@1",
    "validate_required_fields@1",
    "set_field@1",
    "focus_window@1",
    "click_image@1",
    "click_coordinate@1",
    "type_text@1",
    "select_option@1",
    "upload_file@1",
    "scroll@1",
    "sleep@1",
    "append_log@1",
    "log@1",
    "condition@1",
]

CAPABILITY_LABELS: dict[str, str] = {
    "data_pipeline@1": "数据管道",
    "read_table@1": "读取表格",
    "group_rows@1": "按字段分组",
    "filter_completed@1": "过滤已完成",
    "derive_regex_list@1": "正则提取列表",
    "list_files@1": "列出目录文件",
    "match_files@1": "匹配本地文件",
    "validate_required_fields@1": "校验必填字段",
    "set_field@1": "设置字段",
    "focus_window@1": "聚焦窗口",
    "click_image@1": "点击图片",
    "click_coordinate@1": "点击坐标",
    "type_text@1": "输入文本",
    "select_option@1": "选择下拉项",
    "upload_file@1": "上传文件",
    "scroll@1": "滚动页面",
    "sleep@1": "等待",
    "append_log@1": "追加日志",
    "log@1": "记录日志",
    "condition@1": "条件分支",
}


def normalize_capabilities(values: Iterable[object] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def missing_capabilities(required: Iterable[object] | None, available: Iterable[object] | None = None) -> list[str]:
    available_set = set(normalize_capabilities(available or LOCAL_CAPABILITIES))
    return [item for item in normalize_capabilities(required) if item not in available_set]


def capability_label(value: object) -> str:
    item = str(value or "").strip()
    return CAPABILITY_LABELS.get(item, item)


def capability_labels(values: Iterable[object] | None) -> list[str]:
    return [capability_label(item) for item in normalize_capabilities(values)]
