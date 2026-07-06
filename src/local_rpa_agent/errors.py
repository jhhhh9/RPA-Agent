from __future__ import annotations


def friendly_error_message(error: BaseException) -> str:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code == 401:
        return "设备绑定已失效，请重新绑定本地 Agent。"
    if status_code == 403:
        return "当前账号无权限执行该操作，请联系管理员检查工作流或设备权限。"
    if status_code and 500 <= int(status_code) < 600:
        return "SaaS 服务异常，请稍后重试；如果持续失败，请联系管理员查看服务日志。"

    text = str(error)
    lowered = text.lower()
    if "connection refused" in lowered or "actively refused" in lowered or "积极拒绝" in text:
        return "无法连接 SaaS 服务，请确认 SaaS 服务已启动，或检查网络和 SaaS 地址是否正确。"
    if "timed out" in lowered or "timeout" in lowered or "超时" in text:
        return "连接 SaaS 超时，请检查网络后重试。"
    if "name or service not known" in lowered or "nodename nor servname" in lowered or "temporary failure in name resolution" in lowered:
        return "SaaS 地址无法解析，请检查地址是否填写正确。"
    return text or "操作失败，请稍后重试。"
