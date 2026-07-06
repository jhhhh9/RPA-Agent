from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from .capabilities import LOCAL_CAPABILITIES, capability_label, capability_labels, missing_capabilities
from .client import SaaSClient
from .config import AgentConfig
from .errors import friendly_error_message
from .runner import execute_run, preview_data_pipeline
from .storage import AgentState, clear_state, delete_local_template, list_local_templates, load_state, save_local_template, save_state
from .workflow_metadata import asset_requirements, field_help, usage_blocks, validate_asset_directories

HEARTBEAT_INTERVAL_SECONDS = 20


class AgentApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title('AI Business 本地 RPA Agent')
        self.root.geometry('1180x820')
        self.cfg = AgentConfig.load()
        self.state = load_state(self.cfg.config_path)
        self.client = SaaSClient(self.cfg.base_url)
        self.workflows: list[dict[str, Any]] = []
        self.workflow_by_label: dict[str, dict[str, Any]] = {}
        self.template_by_label: dict[str, dict[str, Any]] = {}
        self.dynamic_fields: dict[str, tuple[str, dict[str, Any], tk.Variable]] = {}
        self.heartbeat_stop = threading.Event()
        self.heartbeat_thread: threading.Thread | None = None
        self.stop_requested = threading.Event()
        self.run_button: ttk.Button | None = None
        self.stop_button: ttk.Button | None = None
        self.template_box: ttk.Combobox | None = None

        self.base_url = tk.StringVar(value=self.cfg.base_url)
        self.base_url_editing = False
        self.bind_code = tk.StringVar()
        self.status = tk.StringVar(value=self.bound_status())
        self.workflow_label = tk.StringVar()
        self.template_label = tk.StringVar()
        self.output_dir = tk.StringVar()

        self.build()
        self.refresh_bind_state()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        if self.state:
            self.start_heartbeat_loop()
            self.refresh_workflows()

    def build(self) -> None:
        pad = {'padx': 10, 'pady': 6}
        top = ttk.LabelFrame(self.root, text='连接与绑定')
        top.pack(fill='x', **pad)
        ttk.Label(top, text='SaaS 地址').grid(row=0, column=0, sticky='w', **pad)
        self.base_url_entry = ttk.Entry(top, textvariable=self.base_url, width=48, state='readonly')
        self.base_url_entry.grid(row=0, column=1, sticky='ew', **pad)
        self.base_url_button = ttk.Button(top, text='高级修改地址', command=self.toggle_base_url_edit)
        self.base_url_button.grid(row=0, column=2, **pad)
        ttk.Label(top, text='绑定码').grid(row=1, column=0, sticky='w', **pad)
        self.bind_entry = ttk.Entry(top, textvariable=self.bind_code, width=24)
        self.bind_entry.grid(row=1, column=1, sticky='w', **pad)
        self.bind_button = ttk.Button(top, text='绑定设备', command=self.bind)
        self.bind_button.grid(row=1, column=2, **pad)
        ttk.Button(top, text='解除绑定', command=self.clear_local_bind).grid(row=1, column=3, **pad)
        ttk.Label(top, textvariable=self.status).grid(row=2, column=0, columnspan=4, sticky='w', **pad)
        top.columnconfigure(1, weight=1)

        run = ttk.LabelFrame(self.root, text='运行工作流')
        run.pack(fill='x', expand=False, **pad)
        ttk.Label(run, text='工作流').grid(row=0, column=0, sticky='w', **pad)
        self.workflow_box = ttk.Combobox(run, textvariable=self.workflow_label, width=58, state='readonly')
        self.workflow_box.grid(row=0, column=1, sticky='ew', **pad)
        self.workflow_box.bind('<<ComboboxSelected>>', lambda _: self.rebuild_dynamic_form())
        ttk.Button(run, text='刷新工作流', command=self.refresh_workflows).grid(row=0, column=2, **pad)
        run.columnconfigure(1, weight=1)

        content = ttk.Frame(self.root)
        content.pack(fill='both', expand=True, **pad)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        self.form_frame = ttk.LabelFrame(content, text='工作流输入')
        self.form_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        self.form_canvas = tk.Canvas(self.form_frame, height=260, highlightthickness=0)
        self.form_scrollbar = ttk.Scrollbar(self.form_frame, orient='vertical', command=self.form_canvas.yview)
        self.form_body = ttk.Frame(self.form_canvas)
        self.form_window = self.form_canvas.create_window((0, 0), window=self.form_body, anchor='nw')
        self.form_canvas.configure(yscrollcommand=self.form_scrollbar.set)
        self.form_canvas.pack(side='left', fill='both', expand=True)
        self.form_scrollbar.pack(side='right', fill='y')
        self.form_body.bind('<Configure>', lambda _event: self._refresh_form_scrollregion())
        self.form_canvas.bind('<Configure>', lambda event: self.form_canvas.itemconfigure(self.form_window, width=event.width))
        self.form_canvas.bind('<Enter>', self._bind_mousewheel)
        self.form_canvas.bind('<Leave>', self._unbind_mousewheel)

        self.guide_frame = ttk.LabelFrame(content, text='工作流说明')
        self.guide_frame.grid(row=0, column=1, sticky='nsew', padx=(6, 0))
        self.guide_canvas = tk.Canvas(self.guide_frame, highlightthickness=0)
        self.guide_scrollbar = ttk.Scrollbar(self.guide_frame, orient='vertical', command=self.guide_canvas.yview)
        self.guide_body = ttk.Frame(self.guide_canvas)
        self.guide_window = self.guide_canvas.create_window((0, 0), window=self.guide_body, anchor='nw')
        self.guide_canvas.configure(yscrollcommand=self.guide_scrollbar.set)
        self.guide_canvas.pack(side='left', fill='both', expand=True)
        self.guide_scrollbar.pack(side='right', fill='y')
        self.guide_body.bind('<Configure>', lambda _event: self.guide_canvas.configure(scrollregion=self.guide_canvas.bbox('all')))
        self.guide_canvas.bind('<Configure>', lambda event: self.guide_canvas.itemconfigure(self.guide_window, width=event.width))
        self.guide_canvas.bind('<Enter>', self._bind_guide_mousewheel)
        self.guide_canvas.bind('<Leave>', self._unbind_guide_mousewheel)

        log_frame = ttk.LabelFrame(self.root, text='运行日志')
        log_frame.pack(fill='both', expand=True, **pad)
        self.log_text = tk.Text(log_frame, height=14)
        self.log_text.pack(fill='both', expand=True, padx=10, pady=8)

    def bind(self) -> None:
        if self.state:
            messagebox.showinfo('已绑定', '本机已绑定 SaaS。需要更换账号时，请先解除绑定。')
            return
        code = self.bind_code.get().strip()
        if not code:
            messagebox.showwarning('缺少绑定码', '请先在 SaaS 页面生成绑定码。')
            return
        try:
            self.cfg = AgentConfig.load(base_url=self.base_url.get().strip())
            self.client = SaaSClient(self.cfg.base_url)
            data = self.client.bind(code, self.cfg.device_name, self.cfg.os_type, self.cfg.version, self.cfg.device_fingerprint, LOCAL_CAPABILITIES)
            agent = data['agent']
            token = data['token']
            self.state = AgentState(agent_id=agent['id'], tenant_id=agent['tenant_id'], user_id=agent['user_id'], token=token)
            save_state(self.cfg.config_path, self.state)
            self.status.set(self.bound_status())
            self.refresh_bind_state()
            self.start_heartbeat_loop()
            self.log('绑定成功')
            self.refresh_workflows()
        except Exception as exc:  # noqa: BLE001 - GUI must show readable error.
            messagebox.showerror('绑定失败', friendly_error_message(exc))

    def clear_local_bind(self) -> None:
        if not self.state:
            clear_state(self.cfg.config_path)
            self.refresh_bind_state()
            return
        if not messagebox.askyesno('确认解除绑定', '将停用 SaaS 后台设备记录，并清除本机 token。确认继续？'):
            return
        try:
            self.client = SaaSClient(self.base_url.get().strip())
            self.client.revoke(self.state.token)
        except Exception as exc:  # noqa: BLE001
            message = friendly_error_message(exc)
            if not messagebox.askyesno('服务端解除失败', f'未能停用 SaaS 后台设备记录：{message}\n仍然只清除本机 token 吗？'):
                return
        self.stop_heartbeat_loop()
        clear_state(self.cfg.config_path)
        self.state = None
        self.status.set(self.bound_status())
        self.refresh_bind_state()
        self.workflows = []
        self.workflow_by_label = {}
        self.workflow_box['values'] = []
        self.workflow_label.set('')
        self.rebuild_dynamic_form()
        self.log('已解除绑定')

    def refresh_bind_state(self) -> None:
        bound = self.state is not None
        self.bind_entry.configure(state='disabled' if bound else 'normal')
        self.bind_button.configure(state='disabled' if bound else 'normal')
        if bound:
            self.base_url_entry.configure(state='disabled')
            self.base_url_button.configure(state='disabled')
        else:
            self.base_url_entry.configure(state='normal' if self.base_url_editing else 'readonly')
            self.base_url_button.configure(state='normal')

    def toggle_base_url_edit(self) -> None:
        if self.state:
            return
        self.base_url_editing = not self.base_url_editing
        self.base_url_entry.configure(state='normal' if self.base_url_editing else 'readonly')
        self.base_url_button.configure(text='锁定地址' if self.base_url_editing else '高级修改地址')

    def refresh_workflows(self) -> None:
        if not self.ensure_bound():
            return
        try:
            self.client = SaaSClient(self.base_url.get().strip())
            self.workflows = self.client.workflows(self.state.token)  # type: ignore[union-attr]
            self.workflow_by_label = {f"{item.get('name')} ({item.get('id')})": item for item in self.workflows}
            labels = list(self.workflow_by_label.keys())
            self.workflow_box['values'] = labels
            if labels:
                self.workflow_label.set(labels[0])
            self.rebuild_dynamic_form()
            self.log(f'已加载 {len(labels)} 个可用工作流')
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('加载工作流失败', friendly_error_message(exc))

    def rebuild_dynamic_form(self) -> None:
        for child in self.form_body.winfo_children():
            child.destroy()
        self.dynamic_fields = {}
        self.template_box = None
        self.template_by_label = {}
        self.template_label.set('')
        workflow = self.workflow_by_label.get(self.workflow_label.get())
        if not workflow:
            ttk.Label(self.form_body, text='请选择工作流').grid(row=0, column=0, sticky='w', padx=10, pady=8)
            self.rebuild_usage_guide({})
            self._refresh_form_scrollregion()
            return
        definition = workflow.get('definition') or {}
        if isinstance(definition, str):
            definition = json.loads(definition)
        self.rebuild_usage_guide(definition)
        row = 0
        row = self.add_capability_notice(row, definition)
        row = self.add_template_section(row, workflow)
        row = self.add_schema_section(row, '运行输入', definition.get('input_schema') or [], 'input')
        row = self.add_schema_section(row, '按钮/截图资产', definition.get('assets') or [], 'input', definition)
        row = self.add_schema_section(row, '运行参数', definition.get('runtime_schema') or [], 'runtime')
        ttk.Label(self.form_body, text='输出目录').grid(row=row, column=0, sticky='w', padx=10, pady=6)
        ttk.Entry(self.form_body, textvariable=self.output_dir, width=72).grid(row=row, column=1, sticky='ew', padx=10, pady=6)
        ttk.Button(self.form_body, text='选择目录', command=lambda: self.pick_directory(self.output_dir)).grid(row=row, column=2, padx=10, pady=6)
        row += 1
        preview_button = ttk.Button(self.form_body, text='预检数据管道', command=self.preview_pipeline)
        preview_button.grid(row=row, column=0, sticky='w', padx=10, pady=12)
        self.run_button = ttk.Button(self.form_body, text='创建并运行', command=self.start_run)
        self.run_button.grid(row=row, column=1, sticky='w', padx=10, pady=12)
        self.stop_button = ttk.Button(self.form_body, text='停止当前任务', command=self.request_stop_current, state='disabled')
        self.stop_button.grid(row=row, column=2, sticky='w', padx=10, pady=12)
        self.form_body.columnconfigure(1, weight=1)
        self._refresh_form_scrollregion()

    def rebuild_usage_guide(self, definition: dict[str, Any]) -> None:
        for child in self.guide_body.winfo_children():
            child.destroy()
        blocks = usage_blocks(definition)
        if not blocks:
            ttk.Label(
                self.guide_body,
                text='选择工作流后，这里会显示使用说明、输入要求和按钮截图要求。',
                wraplength=360,
            ).pack(fill='x', padx=10, pady=10)
            return
        colors = {
            'summary': '#e8f1ff',
            'input': '#eaf8ef',
            'naming': '#fff7e6',
            'notes': '#f5efff',
            'asset': '#fff1f0',
        }
        for block in blocks:
            frame = tk.Frame(
                self.guide_body,
                bg=colors.get(str(block.get('kind')), '#f8fafc'),
                bd=0,
                highlightthickness=1,
                highlightbackground='#d8dee9',
            )
            frame.pack(fill='x', padx=10, pady=8)
            tk.Label(
                frame,
                text=str(block.get('title') or ''),
                anchor='w',
                bg=frame['bg'],
                font=('TkDefaultFont', 10, 'bold'),
            ).pack(fill='x', padx=10, pady=(8, 4))
            for item in block.get('items') or []:
                tk.Label(frame, text='• ' + str(item), anchor='w', justify='left', wraplength=360, bg=frame['bg']).pack(fill='x', padx=12, pady=2)
            tk.Frame(frame, height=6, bg=frame['bg']).pack(fill='x')

    def add_template_section(self, row: int, workflow: dict[str, Any]) -> int:
        workflow_id = str(workflow.get('id') or '')
        self.refresh_local_templates(workflow_id)
        ttk.Label(self.form_body, text='本地参数模板', font=('TkDefaultFont', 10, 'bold')).grid(row=row, column=0, columnspan=3, sticky='w', padx=10, pady=(10, 4))
        row += 1
        self.template_box = ttk.Combobox(self.form_body, textvariable=self.template_label, values=list(self.template_by_label.keys()), state='readonly', width=42)
        self.template_box.grid(row=row, column=0, columnspan=2, sticky='ew', padx=10, pady=5)
        button_bar = ttk.Frame(self.form_body)
        button_bar.grid(row=row, column=2, sticky='w', padx=10, pady=5)
        ttk.Button(button_bar, text='应用', command=self.apply_local_template).pack(side='left', padx=(0, 4))
        ttk.Button(button_bar, text='保存当前', command=self.save_current_local_template).pack(side='left', padx=4)
        ttk.Button(button_bar, text='删除', command=self.delete_selected_local_template).pack(side='left', padx=4)
        row += 1
        ttk.Label(self.form_body, text='模板保存在本机，只保存路径和参数，不上传云端。', foreground='gray').grid(row=row, column=0, columnspan=3, sticky='w', padx=10, pady=(0, 8))
        return row + 1

    def refresh_local_templates(self, workflow_id: str) -> None:
        rows = list_local_templates(self.cfg.config_path, workflow_id) if workflow_id else []
        self.template_by_label = {f"{row.get('name')} / {str(row.get('updated_at') or '')[:19]}": row for row in rows}
        labels = list(self.template_by_label.keys())
        if self.template_box:
            self.template_box.configure(values=labels)
        if self.template_label.get() not in labels:
            self.template_label.set(labels[0] if labels else '')

    def apply_local_template(self) -> None:
        row = self.template_by_label.get(self.template_label.get())
        if not row:
            messagebox.showwarning('请选择模板', '请先选择一个本地参数模板。')
            return
        self.output_dir.set(str(row.get('output_dir') or ''))
        values = {**(row.get('input_files') or {}), **(row.get('runtime_params') or {})}
        for key, (_bucket, _spec, var) in self.dynamic_fields.items():
            if key in values:
                var.set(values[key])
        self.log(f"已应用本地模板：{row.get('name')}")

    def save_current_local_template(self) -> None:
        workflow = self.workflow_by_label.get(self.workflow_label.get())
        if not workflow:
            messagebox.showwarning('请选择工作流', '请先选择工作流。')
            return
        name = simpledialog.askstring('保存本地模板', '请输入模板名称：', parent=self.root)
        if not name or not name.strip():
            return
        input_files, runtime_params, output_dir = self.collect_run_values(require_all=False)
        row = save_local_template(
            self.cfg.config_path,
            workflow_id=str(workflow.get('id') or ''),
            name=name.strip(),
            input_files=input_files,
            runtime_params=runtime_params,
            output_dir=output_dir,
        )
        self.refresh_local_templates(str(workflow.get('id') or ''))
        for label, value in self.template_by_label.items():
            if value.get('id') == row.get('id'):
                self.template_label.set(label)
                break
        self.log(f"已保存本地模板：{name.strip()}")

    def delete_selected_local_template(self) -> None:
        workflow = self.workflow_by_label.get(self.workflow_label.get())
        row = self.template_by_label.get(self.template_label.get())
        if not workflow or not row:
            messagebox.showwarning('请选择模板', '请先选择要删除的本地模板。')
            return
        if not messagebox.askyesno('确认删除', f"确认删除本地模板“{row.get('name')}”吗？"):
            return
        delete_local_template(self.cfg.config_path, str(workflow.get('id') or ''), str(row.get('id') or ''))
        self.refresh_local_templates(str(workflow.get('id') or ''))
        self.log(f"已删除本地模板：{row.get('name')}")

    def add_capability_notice(self, row: int, definition: dict[str, Any]) -> int:
        required = definition.get('required_capabilities') or []
        missing = missing_capabilities(required, LOCAL_CAPABILITIES)
        if required:
            ttk.Label(
                self.form_body,
                text='Agent能力: ' + '、'.join(capability_labels(required)),
                foreground='red' if missing else 'gray',
            ).grid(row=row, column=0, columnspan=3, sticky='w', padx=10, pady=4)
            row += 1
        if missing:
            ttk.Label(
                self.form_body,
                text='当前本地 Agent 缺少能力：' + '、'.join(capability_label(item) for item in missing),
                foreground='red',
            ).grid(row=row, column=0, columnspan=3, sticky='w', padx=10, pady=4)
            row += 1
        return row

    def add_schema_section(self, row: int, title: str, specs: list[dict[str, Any]], bucket: str, definition: dict[str, Any] | None = None) -> int:
        if not specs:
            return row
        ttk.Label(self.form_body, text=title, font=('TkDefaultFont', 10, 'bold')).grid(row=row, column=0, columnspan=3, sticky='w', padx=10, pady=(10, 4))
        row += 1
        for spec in specs:
            key = str(spec.get('key') or '')
            if not key:
                continue
            label = str(spec.get('label') or key) + (' *' if spec.get('required') else '')
            ttk.Label(self.form_body, text=label).grid(row=row, column=0, sticky='w', padx=10, pady=5)
            var: tk.Variable
            help_extra = ''
            if definition and spec.get('type') == 'image_directory':
                required_assets = asset_requirements(definition, key)
                if required_assets:
                    help_extra = '需要包含按钮截图：' + '、'.join(required_assets)
            if spec.get('type') == 'boolean':
                var = tk.BooleanVar(value=bool(spec.get('default') or False))
                ttk.Checkbutton(self.form_body, variable=var).grid(row=row, column=1, sticky='w', padx=10, pady=5)
            elif spec.get('type') == 'select':
                var = tk.StringVar(value=str(spec.get('default') or ''))
                options = [str(item.get('value') or item.get('label') or '') for item in spec.get('options') or []]
                ttk.Combobox(self.form_body, textvariable=var, values=options, state='readonly').grid(row=row, column=1, sticky='ew', padx=10, pady=5)
            else:
                var = tk.StringVar(value=str(spec.get('default') or ''))
                ttk.Entry(self.form_body, textvariable=var, width=72).grid(row=row, column=1, sticky='ew', padx=10, pady=5)
                if spec.get('type') in {'file', 'directory', 'image_directory'}:
                    picker = self.pick_file if spec.get('type') == 'file' else self.pick_directory
                    ttk.Button(self.form_body, text='选择', command=lambda v=var, p=picker: p(v)).grid(row=row, column=2, padx=10, pady=5)
                elif spec.get('type') == 'number' and key.endswith('_x') and any(str(item.get('key') or '') == key[:-2] + '_y' for item in specs):
                    ttk.Button(self.form_body, text='3秒取点', command=lambda x_key=key, y_key=key[:-2] + '_y': self.capture_coordinate_pair(x_key, y_key)).grid(row=row, column=2, padx=10, pady=5)
            self.dynamic_fields[key] = (bucket, spec, var)
            row += 1
            help_text = field_help(spec, help_extra)
            if help_text:
                ttk.Label(self.form_body, text=help_text, foreground='gray', wraplength=680).grid(row=row, column=1, columnspan=2, sticky='w', padx=10, pady=(0, 5))
                row += 1
        return row

    def pick_file(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(title='选择文件', filetypes=[('数据/图片文件', '*.xlsx *.xls *.csv *.txt *.png *.jpg *.jpeg'), ('所有文件', '*.*')])
        if path:
            var.set(path)

    def pick_directory(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title='选择目录')
        if path:
            var.set(path)

    def start_run(self) -> None:
        if not self.ensure_bound():
            return
        workflow = self.workflow_by_label.get(self.workflow_label.get())
        if not workflow:
            messagebox.showwarning('请选择工作流', '请先选择一个可用工作流。')
            return
        try:
            input_files, runtime_params, output_dir = self.collect_run_values(require_all=True)
            definition = workflow_definition(workflow)
            missing = missing_capabilities(definition.get('required_capabilities') or [], LOCAL_CAPABILITIES)
            if missing:
                raise ValueError('当前本地 Agent 缺少工作流能力：' + '、'.join(capability_label(item) for item in missing))
            asset_errors = validate_asset_directories(definition, input_files)
            if asset_errors:
                raise ValueError('\n'.join(asset_errors))
            self.stop_requested.clear()
            if self.run_button:
                self.run_button.configure(state='disabled')
            if self.stop_button:
                self.stop_button.configure(state='normal')
            thread = threading.Thread(target=self._run_background, args=(workflow['id'], output_dir, input_files, runtime_params), daemon=True)
            thread.start()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('参数错误', friendly_error_message(exc))

    def collect_run_values(self, require_all: bool = True) -> tuple[dict[str, Any], dict[str, Any], str]:
        input_files: dict[str, Any] = {}
        runtime_params: dict[str, Any] = {}
        for key, (bucket, spec, var) in self.dynamic_fields.items():
            value = var.get()
            if require_all and spec.get('required') and (value is None or str(value).strip() == ''):
                raise ValueError(f"请填写：{spec.get('label') or key}")
            if spec.get('type') == 'number' and value != '':
                value = float(value)
            target = runtime_params if bucket == 'runtime' else input_files
            target[key] = value
        return input_files, runtime_params, self.output_dir.get().strip()

    def preview_pipeline(self) -> None:
        workflow = self.workflow_by_label.get(self.workflow_label.get())
        if not workflow:
            messagebox.showwarning('请选择工作流', '请先选择一个可用工作流。')
            return
        try:
            input_files, runtime_params, output_dir = self.collect_run_values(require_all=True)
            base_row: dict[str, Any] = {**input_files, **runtime_params}
            base_row['__input'] = input_files
            base_row['__runtime'] = runtime_params
            if output_dir:
                base_row['output_dir'] = output_dir
            definition = workflow_definition(workflow)
            asset_errors = validate_asset_directories(definition, input_files)
            if asset_errors:
                raise ValueError('\n'.join(asset_errors))
            result = preview_data_pipeline(definition, base_row)
            if not result.get('ok'):
                raise ValueError(str(result.get('error') or '预检失败'))
            self.log(f"预检通过：数据管道生成 {result.get('total', 0)} 组执行数据")
            for step in result.get('trace') or []:
                self.log(
                    f"数据步骤 {step.get('step_id')}: "
                    f"输入 {step.get('input_count')}，输出 {step.get('output_count')}，写入 {step.get('output') or '-'}"
                )
                sample = step.get('sample') or []
                if sample:
                    self.log(f"  样例：{json.dumps(sample[:2], ensure_ascii=False)[:800]}")
            for index, item in enumerate(result.get('sample') or [], start=1):
                self.log(f"最终执行样例 {index}: {json.dumps(item, ensure_ascii=False)[:800]}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('预检失败', friendly_error_message(exc))

    def capture_coordinate_pair(self, x_key: str, y_key: str) -> None:
        messagebox.showinfo('准备取点', '点击确定后，请在 3 秒内把鼠标移动到目标位置。Agent 会自动读取当前鼠标坐标。')
        self.log(f'准备读取坐标：{x_key}/{y_key}，请在 3 秒内移动鼠标到目标位置。')

        def do_capture() -> None:
            try:
                import pyautogui

                x, y = pyautogui.position()
                if x_key in self.dynamic_fields:
                    self.dynamic_fields[x_key][2].set(str(x))
                if y_key in self.dynamic_fields:
                    self.dynamic_fields[y_key][2].set(str(y))
                self.log(f'已读取坐标：{x_key}={x}, {y_key}={y}')
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror('取点失败', f'无法读取鼠标坐标：{friendly_error_message(exc)}')

        self.root.after(3000, do_capture)

    def request_stop_current(self) -> None:
        self.stop_requested.set()
        self.log('已请求停止，当前步骤结束后会停止。')

    def _run_background(self, workflow_id: str, output_dir: str, input_files: dict[str, Any], params: dict[str, Any]) -> None:
        try:
            self.log('正在创建本地运行任务...')
            run = self.client.create_run(self.state.token, workflow_id, output_dir, input_files, params)  # type: ignore[union-attr]
            execute_run(self.client, self.state.token, run, log=self.log, should_stop=self.stop_requested.is_set)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            message = friendly_error_message(exc)
            self.log(f'运行失败：{message}')
            self.root.after(0, lambda: messagebox.showerror('运行失败', message))
        finally:
            self.root.after(0, self._finish_run_ui)

    def _finish_run_ui(self) -> None:
        if self.run_button:
            self.run_button.configure(state='normal')
        if self.stop_button:
            self.stop_button.configure(state='disabled')
        self.stop_requested.clear()

    def start_heartbeat_loop(self) -> None:
        self.stop_heartbeat_loop()
        self.heartbeat_stop = threading.Event()
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def stop_heartbeat_loop(self) -> None:
        self.heartbeat_stop.set()
        self.heartbeat_thread = None

    def _heartbeat_loop(self) -> None:
        while not self.heartbeat_stop.is_set():
            state = self.state
            if state:
                try:
                    self.client = SaaSClient(self.base_url.get().strip())
                    self.client.heartbeat(state.token, self.cfg.version, LOCAL_CAPABILITIES)
                    self.root.after(0, lambda: self.status.set(self.bound_status()))
                except Exception as exc:  # noqa: BLE001
                    self.root.after(0, lambda e=exc: self.status.set(f'{self.bound_status()} / 心跳失败：{friendly_error_message(e)}'))
            if self.heartbeat_stop.wait(HEARTBEAT_INTERVAL_SECONDS):
                break

    def _refresh_form_scrollregion(self) -> None:
        self.form_canvas.configure(scrollregion=self.form_canvas.bbox('all'))

    def _bind_mousewheel(self, _event: tk.Event) -> None:
        self.form_canvas.bind_all('<MouseWheel>', self._on_mousewheel)

    def _unbind_mousewheel(self, _event: tk.Event) -> None:
        self.form_canvas.unbind_all('<MouseWheel>')

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.form_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _bind_guide_mousewheel(self, _event: tk.Event) -> None:
        self.guide_canvas.bind_all('<MouseWheel>', self._on_guide_mousewheel)

    def _unbind_guide_mousewheel(self, _event: tk.Event) -> None:
        self.guide_canvas.unbind_all('<MouseWheel>')

    def _on_guide_mousewheel(self, event: tk.Event) -> None:
        self.guide_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def ensure_bound(self) -> bool:
        if self.state:
            return True
        messagebox.showwarning('未绑定', '请先输入绑定码并绑定本机。')
        return False

    def bound_status(self) -> str:
        if not self.state:
            return '未绑定'
        return f'已绑定设备：{self.cfg.device_name} / Agent {self.state.agent_id} / 版本 {self.cfg.version}'

    def log(self, message: str) -> None:
        self.root.after(0, lambda: self._append_log(message))

    def _append_log(self, message: str) -> None:
        self.log_text.insert('end', message + '\n')
        self.log_text.see('end')

    def close(self) -> None:
        self.stop_heartbeat_loop()
        self.stop_requested.set()
        self.root.destroy()


def workflow_definition(workflow: dict[str, Any]) -> dict[str, Any]:
    definition = workflow.get('definition') or {}
    if isinstance(definition, str):
        try:
            definition = json.loads(definition)
        except json.JSONDecodeError:
            definition = {}
    return definition if isinstance(definition, dict) else {}


def main() -> None:
    root = tk.Tk()
    AgentApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
