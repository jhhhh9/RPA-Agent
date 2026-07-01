from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .client import SaaSClient
from .config import AgentConfig
from .runner import execute_run
from .storage import AgentState, clear_state, load_state, save_state


class AgentApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AI Business 本地 RPA Agent")
        self.root.geometry("980x760")
        self.cfg = AgentConfig.load()
        self.state = load_state(self.cfg.config_path)
        self.client = SaaSClient(self.cfg.base_url)
        self.workflows: list[dict[str, Any]] = []
        self.workflow_by_label: dict[str, dict[str, Any]] = {}
        self.dynamic_fields: dict[str, tuple[str, dict[str, Any], tk.Variable]] = {}

        self.base_url = tk.StringVar(value=self.cfg.base_url)
        self.bind_code = tk.StringVar()
        self.status = tk.StringVar(value=self.bound_status())
        self.workflow_label = tk.StringVar()
        self.output_dir = tk.StringVar()

        self.build()
        self.refresh_bind_state()
        if self.state:
            self.refresh_workflows()

    def build(self) -> None:
        pad = {"padx": 10, "pady": 6}
        top = ttk.LabelFrame(self.root, text="连接与绑定")
        top.pack(fill="x", **pad)
        ttk.Label(top, text="SaaS 地址").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(top, textvariable=self.base_url, width=48).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Label(top, text="绑定码").grid(row=1, column=0, sticky="w", **pad)
        self.bind_entry = ttk.Entry(top, textvariable=self.bind_code, width=24)
        self.bind_entry.grid(row=1, column=1, sticky="w", **pad)
        self.bind_button = ttk.Button(top, text="绑定设备", command=self.bind)
        self.bind_button.grid(row=1, column=2, **pad)
        ttk.Button(top, text="清除本机绑定信息", command=self.clear_local_bind).grid(row=1, column=3, **pad)
        ttk.Label(top, textvariable=self.status).grid(row=2, column=0, columnspan=4, sticky="w", **pad)
        top.columnconfigure(1, weight=1)

        run = ttk.LabelFrame(self.root, text="运行工作流")
        run.pack(fill="both", expand=False, **pad)
        ttk.Label(run, text="工作流").grid(row=0, column=0, sticky="w", **pad)
        self.workflow_box = ttk.Combobox(run, textvariable=self.workflow_label, width=58, state="readonly")
        self.workflow_box.grid(row=0, column=1, sticky="ew", **pad)
        self.workflow_box.bind("<<ComboboxSelected>>", lambda _: self.rebuild_dynamic_form())
        ttk.Button(run, text="刷新工作流", command=self.refresh_workflows).grid(row=0, column=2, **pad)
        run.columnconfigure(1, weight=1)

        self.form_frame = ttk.LabelFrame(self.root, text="工作流输入")
        self.form_frame.pack(fill="x", **pad)
        self.form_body = ttk.Frame(self.form_frame)
        self.form_body.pack(fill="x")

        log_frame = ttk.LabelFrame(self.root, text="运行日志")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(log_frame, height=18)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=8)

    def bind(self) -> None:
        if self.state:
            messagebox.showinfo("已绑定", "本机已绑定 SaaS。需要更换账号时，请先清除本机绑定信息。")
            return
        code = self.bind_code.get().strip()
        if not code:
            messagebox.showwarning("缺少绑定码", "请先在 SaaS 页面生成绑定码。")
            return
        try:
            self.cfg = AgentConfig.load(base_url=self.base_url.get().strip())
            self.client = SaaSClient(self.cfg.base_url)
            data = self.client.bind(code, self.cfg.device_name, self.cfg.os_type, self.cfg.version, self.cfg.device_fingerprint)
            agent = data["agent"]
            token = data["token"]
            self.state = AgentState(agent_id=agent["id"], tenant_id=agent["tenant_id"], user_id=agent["user_id"], token=token)
            save_state(self.cfg.config_path, self.state)
            self.status.set(self.bound_status())
            self.refresh_bind_state()
            self.log("绑定成功")
            self.refresh_workflows()
        except Exception as exc:  # noqa: BLE001 - GUI must show readable error.
            messagebox.showerror("绑定失败", str(exc))

    def clear_local_bind(self) -> None:
        if not messagebox.askyesno("确认清除", "仅清除本机保存的 token，不会删除 SaaS 后台设备记录。确认继续？"):
            return
        clear_state(self.cfg.config_path)
        self.state = None
        self.status.set(self.bound_status())
        self.refresh_bind_state()
        self.log("已清除本机绑定信息")

    def refresh_bind_state(self) -> None:
        bound = self.state is not None
        self.bind_entry.configure(state="disabled" if bound else "normal")
        self.bind_button.configure(state="disabled" if bound else "normal")

    def refresh_workflows(self) -> None:
        if not self.ensure_bound():
            return
        try:
            self.client = SaaSClient(self.base_url.get().strip())
            self.workflows = self.client.workflows(self.state.token)  # type: ignore[union-attr]
            self.workflow_by_label = {f"{item.get('name')} ({item.get('id')})": item for item in self.workflows}
            labels = list(self.workflow_by_label.keys())
            self.workflow_box["values"] = labels
            if labels:
                self.workflow_label.set(labels[0])
            self.rebuild_dynamic_form()
            self.log(f"已加载 {len(labels)} 个可用工作流")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("加载工作流失败", str(exc))

    def rebuild_dynamic_form(self) -> None:
        for child in self.form_body.winfo_children():
            child.destroy()
        self.dynamic_fields = {}
        workflow = self.workflow_by_label.get(self.workflow_label.get())
        if not workflow:
            ttk.Label(self.form_body, text="请选择工作流").grid(row=0, column=0, sticky="w", padx=10, pady=8)
            return
        definition = workflow.get("definition") or {}
        if isinstance(definition, str):
            definition = json.loads(definition)
        row = 0
        row = self.add_schema_section(row, "运行输入", definition.get("input_schema") or [], "input")
        row = self.add_schema_section(row, "按钮/截图资产", definition.get("assets") or [], "input")
        row = self.add_schema_section(row, "运行参数", definition.get("runtime_schema") or [], "runtime")
        ttk.Label(self.form_body, text="输出目录").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        ttk.Entry(self.form_body, textvariable=self.output_dir, width=72).grid(row=row, column=1, sticky="ew", padx=10, pady=6)
        ttk.Button(self.form_body, text="选择目录", command=lambda: self.pick_directory(self.output_dir)).grid(row=row, column=2, padx=10, pady=6)
        row += 1
        ttk.Button(self.form_body, text="创建并运行", command=self.start_run).grid(row=row, column=1, sticky="w", padx=10, pady=12)
        self.form_body.columnconfigure(1, weight=1)

    def add_schema_section(self, row: int, title: str, specs: list[dict[str, Any]], bucket: str) -> int:
        if not specs:
            return row
        ttk.Label(self.form_body, text=title, font=("TkDefaultFont", 10, "bold")).grid(row=row, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 4))
        row += 1
        for spec in specs:
            key = str(spec.get("key") or "")
            if not key:
                continue
            label = str(spec.get("label") or key) + (" *" if spec.get("required") else "")
            ttk.Label(self.form_body, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=5)
            var: tk.Variable
            if spec.get("type") == "boolean":
                var = tk.BooleanVar(value=bool(spec.get("default") or False))
                ttk.Checkbutton(self.form_body, variable=var).grid(row=row, column=1, sticky="w", padx=10, pady=5)
            elif spec.get("type") == "select":
                var = tk.StringVar(value=str(spec.get("default") or ""))
                options = [str(item.get("value") or item.get("label") or "") for item in spec.get("options") or []]
                ttk.Combobox(self.form_body, textvariable=var, values=options, state="readonly").grid(row=row, column=1, sticky="ew", padx=10, pady=5)
            else:
                var = tk.StringVar(value=str(spec.get("default") or ""))
                ttk.Entry(self.form_body, textvariable=var, width=72).grid(row=row, column=1, sticky="ew", padx=10, pady=5)
                if spec.get("type") in {"file", "directory", "image_directory"}:
                    picker = self.pick_file if spec.get("type") == "file" else self.pick_directory
                    ttk.Button(self.form_body, text="选择", command=lambda v=var, p=picker: p(v)).grid(row=row, column=2, padx=10, pady=5)
            self.dynamic_fields[key] = (bucket, spec, var)
            row += 1
        return row

    def pick_file(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(title="选择文件", filetypes=[("数据文件", "*.xlsx *.xls *.csv *.txt *.png *.jpg *.jpeg"), ("所有文件", "*.*")])
        if path:
            var.set(path)

    def pick_directory(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="选择目录")
        if path:
            var.set(path)

    def start_run(self) -> None:
        if not self.ensure_bound():
            return
        workflow = self.workflow_by_label.get(self.workflow_label.get())
        if not workflow:
            messagebox.showwarning("请选择工作流", "请先选择一个可用工作流。")
            return
        try:
            input_files: dict[str, Any] = {}
            runtime_params: dict[str, Any] = {}
            for key, (bucket, spec, var) in self.dynamic_fields.items():
                value = var.get()
                if spec.get("required") and (value is None or str(value).strip() == ""):
                    raise ValueError(f"请填写：{spec.get('label') or key}")
                if spec.get("type") == "number" and value != "":
                    value = float(value)
                target = runtime_params if bucket == "runtime" else input_files
                target[key] = value
            output_dir = self.output_dir.get().strip()
            thread = threading.Thread(target=self._run_background, args=(workflow["id"], output_dir, input_files, runtime_params), daemon=True)
            thread.start()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("参数错误", str(exc))

    def _run_background(self, workflow_id: str, output_dir: str, input_files: dict[str, Any], params: dict[str, Any]) -> None:
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

    def bound_status(self) -> str:
        if not self.state:
            return "未绑定"
        return f"已绑定设备：{self.cfg.device_name} / Agent {self.state.agent_id}"

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
