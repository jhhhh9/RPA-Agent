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
- 执行 workflow DAG 的基础解释器，优先使用 `edges` 连线流向，兼容旧版 `next`。
- 根据工作流 schema 动态渲染输入、参数、输出和按钮截图资产。
- 回写任务 `running/completed/failed` 状态。
- 对 `focus_window`、`click_image`、`click_coordinate`、`type_text`、`select_option`、`upload_file`、`scroll` 等节点执行本地动作。
- 通用 `data_pipeline` 能读取任务表、按字段分组、匹配本地目录文件、校验必填资源，并把结果作为 `row` 数据流传给后续动作节点。
- Agent 会在绑定和心跳时上报 `required_capabilities` 对应的能力，SaaS 和本地执行前都会做能力匹配校验。
- GUI 左侧展示运行表单，右侧分层展示工作流说明、输入要求、命名规则、按钮截图要求和运行注意事项。
- GUI 支持“预检数据管道”，先确认输入文件、资源目录、按钮截图目录和匹配结果，再创建正式任务。
- 坐标类运行参数支持“3 秒取点”，用户把鼠标移动到目标位置后自动写入 X/Y 坐标。
- 参数模板保存在本机配置目录，只保存本机路径、运行参数和输出目录，不上传云端。
- SaaS 地址默认只读，普通用户只需要填写绑定码；需要切换环境时通过“高级修改地址”显式解锁。
- 网络错误会转换成用户可读提示，例如 SaaS 未启动、绑定失效、权限不足、服务异常等。


## 面向普通用户的交付方式

普通用户不应该安装 Python，也不应该敲命令启动。正式交付流程是：

1. 开发者在 Windows 构建机执行 `powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1`，生成 `dist\local-rpa-agent.exe`。
2. 在 GitHub 仓库创建 Release，例如 `v0.1.0`，把 `dist\local-rpa-agent.exe` 作为 release asset 上传。
3. 超级管理员在 SaaS 的“模块管理 -> automation 配置 -> 平台自动化配置”里发布 Agent 版本，填写版本号、平台和 GitHub Release 下载地址。
4. 用户在 SaaS 的“本地 RPA 自动化”模块点击“下载本地 Agent”，下载安装即可。

当前项目已经具备面向普通用户的基础 GUI：绑定设备、刷新可用工作流，并根据 SaaS workflow 的 `input_schema/runtime_schema/output_schema/assets/usage_guide` 动态生成运行表单和说明面板。绑定后本机不允许重复填写绑定码；如需更换绑定，可先清除本机 token。动作适配层已接入基础 pyautogui/OpenCV 能力，用于图片点击、坐标点击、输入、上传文件和滚动。

## 快速开始

```bash
cd ~/code/local-rpa-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 推荐：打开 GUI，普通用户在窗口里绑定、选择工作流并运行
local-rpa-agent-gui

# 命令行仍保留给调试使用
local-rpa-agent bind ABCD1234 --base-url http://127.0.0.1:8080
local-rpa-agent once
local-rpa-agent service --interval 5
```

GUI 使用建议：

1. 在 SaaS 里生成绑定码，打开 Agent 后输入绑定码完成绑定。
2. 选择工作流后，先阅读右侧说明面板，按要求准备任务文件、资源目录和按钮截图目录。
3. 在“本地参数模板”里可保存常用路径和参数，下次选择同一工作流后直接应用。
4. 坐标参数可点击“3秒取点”，确认后把鼠标移动到目标位置，Agent 会自动填入坐标。
5. 点击“预检数据管道”，确认文件匹配和资源检查通过后，再点击“创建并运行”。

Windows PowerShell 可把 `source .venv/bin/activate` 换成：

```powershell
.venv\Scripts\Activate.ps1
```

## 和 SaaS 的接口

- `POST /api/automation/agents/bind`：绑定码换取 agent token。
- `POST /api/automation/agents/heartbeat`：心跳。
- `GET /api/automation/agents/workflows`：本地 GUI 拉取当前公司可用工作流。
- `POST /api/automation/agents/runs`：本地 GUI 创建并运行本机任务，携带输入文件、输入目录、输出目录和运行参数。
- `GET /api/automation/agents/runs/next`：领取下一条任务。
- `POST /api/automation/agents/runs/{id}/status`：回写任务状态。

## 后续执行器扩展点

主要扩展文件是 `src/local_rpa_agent/actions.py`：

- `focus_window`：按窗口标题请求聚焦紫鸟浏览器或目标软件。
- `click_image`：用 OpenCV/pyautogui 模板匹配按钮截图。
- `click_coordinate`：点击固定坐标。
- `type_text`：向当前焦点输入文本。
- `upload_file`：在系统文件选择框中填入本地文件路径，支持多文件。
- `select_option`：操作下拉框。
- `scroll`：滚动页面。
- `data_pipeline`：通用本地数据准备引擎，支持读取表格、分组、列出目录文件、匹配文件、校验必填字段和设置字段。

这些能力需要本机 GUI 权限。后续若升级成 Electron/Wails 桌面应用，可复用现有 SaaS 协议、workflow schema、能力上报和 data_pipeline，只替换本地 UI 壳。
