# Local RPA Agent

本项目是 AI Business SaaS 的本地 RPA Agent，独立于云端 Go SaaS 服务运行。它负责在用户电脑上领取 SaaS 下发的自动化工作流任务，并在本地执行浏览器/桌面软件操作。

## 为什么独立项目

- 云端 SaaS 不能读取用户电脑路径，也不能直接控制紫鸟浏览器或桌面软件。
- 本地 Agent 持有一次性绑定得到的 `agent_token`，只和 SaaS 通信，不保存 OSS 永久密钥。
- 工作流定义、运行记录、Agent 发布元数据仍由 SaaS 管理。

## 当前能力

- 使用 SaaS 生成的绑定码绑定设备。
- 定时心跳上报在线状态。
- 轮询 `/api/automation/agents/runs/next` 拉取待执行任务。
- 执行 workflow DAG 的基础解释器。
- 回写任务 `running/completed/failed` 状态。
- 对 `focus_window`、`click_image`、`type_text`、`select_option`、`upload_file` 等节点先输出结构化日志，占位后续接入 pyautogui/OpenCV。


## 面向普通用户的交付方式

普通用户不应该安装 Python，也不应该敲命令启动。正式交付流程是：

1. 开发者在 Windows 构建机执行 `scripts\build-windows.ps1`，生成 `dist\local-rpa-agent.exe`。
2. 将 exe 或安装包上传到 SaaS 配置的系统 OSS。
3. 超级管理员在 SaaS 的“平台自动化工作流”页面发布 Agent 版本，填写 OSS object key、版本号和 hash。
4. 用户在 SaaS 的“本地 RPA 自动化”模块点击“下载本地 Agent”，下载安装即可。

当前项目仍是 Agent 执行器骨架：已经打通绑定、心跳、拉任务、回写状态和 workflow 解释器；真正的鼠标键盘、截图识别、紫鸟浏览器窗口控制需要继续在 `src/local_rpa_agent/actions.py` 接入 pyautogui/OpenCV 或更稳定的系统自动化库。

## 快速开始

```bash
cd ~/code/local-rpa-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# SaaS 页面生成绑定码后执行
local-rpa-agent bind ABCD1234 --base-url http://127.0.0.1:8080

# 单次拉取并执行一个任务
local-rpa-agent once

# 常驻服务模式
local-rpa-agent service --interval 5
```

Windows PowerShell 可把 `source .venv/bin/activate` 换成：

```powershell
.venv\Scripts\Activate.ps1
```

## 和 SaaS 的接口

- `POST /api/automation/agents/bind`：绑定码换取 agent token。
- `POST /api/automation/agents/heartbeat`：心跳。
- `GET /api/automation/agents/runs/next`：领取下一条任务。
- `POST /api/automation/agents/runs/{id}/status`：回写任务状态。

## 后续执行器扩展点

主要扩展文件是 `src/local_rpa_agent/actions.py`：

- `focus_window`：按窗口标题激活紫鸟浏览器或目标软件。
- `click_image`：用 OpenCV 模板匹配用户上传的按钮截图。
- `type_text`：向当前焦点输入文本。
- `upload_file`：在系统文件选择框中填入本地文件路径。
- `select_option`：操作下拉框。

这些能力需要本机 GUI 权限，建议后续打包成 Electron/Wails 桌面应用时统一申请权限和展示运行日志。
