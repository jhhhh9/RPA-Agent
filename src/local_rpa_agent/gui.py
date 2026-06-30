from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .client import SaaSClient
from .config import AgentConfig
from .runner import execute_run
from .storage import AgentState, load_state, save_state


class AgentApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AI Business 本地 RPA Agent")
        self.root.geometry("920x680")
        self.cfg = AgentConfig.load()
        self.state = load_state(self.cfg.config_path)
        self.client = SaaSClient(self.cfg.base_url)
        self.workflows: list[dict[str, Any]] = []
        self.workflow_by_label: dict[str, dict[str, Any]] = {}

        self.base_url = tk.StringVar(value=self.cfg.base_url)
        self.bind_code = tk.StringVar()
        self.status = tk.StringVar(value="未绑定" if not self.state else f"已绑定：{self.state.agent_id}")
        self.workflow_label = tk.StringVar()
        self.input_file = tk.StringVar()
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()

        self.build()
        if self.state:
            self.refresh_workflows()

    def build(self) -> None:
        pad = {"padx": 10, "pady": 6}
        top = ttk.LabelFrame(self.root, text="连接与绑定")
        top.pack(fill="x", **pad)
        ttk.Label(top, text="SaaS 地址").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(top, textvariable=self.base_url, width=48).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Label(top, text="绑定码").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(top, textvariable=self.bind_code, width=24).grid(row=1, column=1, sticky="w", **pad)
        ttk.Button(top, text="绑定设备", command=self.bind).grid(row=1, column=2, **pad)
        ttk.Label(top, textvariable=self.status).grid(row=2, column=0, columnspan=3, sticky="w", **pad)
        top.columnconfigure(1, weight=1)

        run = ttk.LabelFrame(self.root, text="运行工作流")
        run.pack(fill="x", **pad)
        ttk.Label(run, text="工作流").grid(row=0, column=0, sticky="w", **pad)
        self.workflow_box = ttk.Combobox(run, textvariable=self.workflow_label, width=58, state="readonly")
        self.workflow_box.grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(run, text="刷新工作流", command=self.refresh_workflows).grid(row=0, column=2, **pad)

        ttk.Label(run, text="输入文件").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(run, textvariable=self.input_file).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(run, text="选择文件", command=self.pick_input_file).grid(row=1, column=2, **pad)

        ttk.Label(run, text="输入目录").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(run, textvariable=self.input_dir).grid(row=2, column=1, sticky="ew", **pad)
        ttk.Button(run, text="选择目录", command=self.pick_input_dir).grid(row=2, column=2, **pad)

        ttk.Label(run, text="输出目录").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(run, textvariable=self.output_dir).grid(row=3, column=1, sticky="ew", **pad)
        ttk.Button(run, text="选择目录", command=self.pick_output_dir).grid(row=3, column=2, **pad)

        ttk.Label(run, text="运行参数 JSON").grid(row=4, column=0, sticky="nw", **pad)
        self.params_text = tk.Text(run, height=6)
        self.params_text.insert("1.0", "{}")
        self.params_text.grid(row=4, column=1, columnspan=2, sticky="ew", **pad)
        ttk.Button(run, text="创建并运行", command=self.start_run).grid(row=5, column=1, sticky="w", **pad)
        run.columnconfigure(1, weight=1)

        log_frame = ttk.LabelFrame(self.root, text="运行日志")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(log_frame, height=18)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=8)

    def bind(self) -> None:
        code = self.bind_code.get().strip()
        if not code:
            messagebox.showwarning("缺少绑定码", "请先在 SaaS 页面生成绑定码。")
            return
        try:
            self.cfg = AgentConfig.load(base_url=self.base_url.get().strip())
            self.client = SaaSClient(self.cfg.base_url)
            data = self.client.bind(code, self.cfg.device_name, self.cfg.os_type, self.cfg.version)
            agent = data["agent"]
            token = data["token"]
            self.state = AgentState(agent_id=agent["id"], tenant_id=agent["tenant_id"], user_id=agent["user_id"], token=token)
            save_state(self.cfg.config_path, self.state)
            self.status.set(f"已绑定：{agent['id']}")
            self.log("绑定成功")
            self.refresh_workflows()
        except Exception as exc:  # noqa: BLE001 - GUI must show readable error.
            messagebox.showerror("绑定失败", str(exc))

    def refresh_workflows(self) -> None:
        if not self.ensure_bound():
            return
        try:
            self.client = SaaSClient(self.base_url.get().strip())
            self.workflows = self.client.workflows(self.state.token)  # type: ignore[union-attr]
            self.workflow_by_label = {f"{item.get('name')} ({item.get('id')})": item for item in self.workflows}
            labels = list(self.workflow_by_label.keys())
            self.workflow_box["values"] = labels
            if labels and not self.workflow_label.get():
                self.workflow_label.set(labels[0])
            self.log(f"已加载 {len(labels)} 个可用工作流")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("加载工作流失败", str(exc))

    def pick_input_file(self) -> None:
        path = filedialog.askopenfilename(title="选择输入文件", filetypes=[("数据文件", "*.xlsx *.xls *.csv *.txt"), ("所有文件", "*.*")])
        if path:
            self.input_file.set(path)

    def pick_input_dir(self) -> None:
        path = filedialog.askdirectory(title="选择输入目录")
        if path:
            self.input_dir.set(path)

    def pick_output_dir(self) -> None:
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_dir.set(path)

    def start_run(self) -> None:
        if not self.ensure_bound():
            return
        workflow = self.workflow_by_label.get(self.workflow_label.get())
        if not workflow:
            messagebox.showwarning("请选择工作流", "请先选择一个可用工作流。")
            return
        try:
            params = json.loads(self.params_text.get("1.0", "end").strip() or "{}")
            if not isinstance(params, dict):
                raise ValueError("运行参数必须是 JSON 对象")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("参数错误", str(exc))
            return
        input_files = {"input_file": self.input_file.get().strip(), "input_dir": self.input_dir.get().strip()}
        output_dir = self.output_dir.get().strip()
        thread = threading.Thread(target=self._run_background, args=(workflow["id"], output_dir, input_files, params), daemon=True)
        thread.start()

    def _run_background(self, workflow_id: str, output_dir: str, input_files: dict[str, str], params: dict[str, Any]) -> None:
        try:
            self.log("正在创建本地运行任务...")
            run = self.client.create_run(self.state.token, workflow_id, output_dir, input_files, params)  # type: ignore[union-attr]
            execute_run(self.client, self.state.token, run, log=self.log)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            self.log(f"运行失败：{exc}")
            messagebox.showerror("运行失败", str(exc))

    def ensure_bound(self) -> bool:
        if self.state:
            return True
        messagebox.showwarning("未绑定", "请先输入绑定码并绑定本机。")
        return False

    def log(self, message: str) -> None:
        self.root.after(0, lambda: self._append_log(message))

    def _append_log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")


def main() -> None:
    root = tk.Tk()
    AgentApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
