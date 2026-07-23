"""Tkinter 图形界面。"""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path
from tkinter import (
    Canvas,
    Label,
    PhotoImage,
    StringVar,
    Tk,
    Toplevel,
    filedialog,
    messagebox,
)
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from adjust_pdf import __version__
from adjust_pdf.exceptions import AdjustPdfError
from adjust_pdf.models import (
    DocumentInfo,
    PageSelectionMode,
    ProcessOptions,
    ProcessResult,
)
from adjust_pdf.page_ranges import parse_page_numbers
from adjust_pdf.resources import resource_path
from adjust_pdf.signature_report import (
    RISK_BANNER_TEXT,
    format_signed_documents_warning,
)
from adjust_pdf.rotation_report import (
    format_multiple_rotation_reports,
    format_rotation_summary,
)
from adjust_pdf.service import PdfProcessingService


SKIN_WINDOW_BG = "#0D1726"
SKIN_PANEL_BG = "#14243A"
SKIN_TEXT = "#F8F3E8"
SKIN_MUTED_TEXT = "#D5DCE7"
SKIN_ACCENT = "#E6A24A"
SKIN_ACCENT_ACTIVE = "#C97732"
SKIN_TABLE_BG = "#F7F1E5"
SKIN_TABLE_TEXT = "#172235"


MODE_LABELS = {
    "仅处理第一页": PageSelectionMode.FIRST,
    "所有存在旋转属性的页面": PageSelectionMode.ROTATED,
    "按页码处理": PageSelectionMode.SELECTED,
}


class MainWindow:
    """PDF 旋转固化工具主窗口。"""

    def __init__(
        self,
        root: Tk,
        initial_files: list[Path] | None = None,
        log_path: Path | None = None,
    ) -> None:
        self.root = root
        self.log_path = log_path
        self.logger = logging.getLogger("adjust_pdf.gui")
        self.service = PdfProcessingService()
        self.events: queue.Queue[tuple] = queue.Queue()
        self.file_items: dict[str, Path] = {}
        self.processing = False
        self.successful_results: list[ProcessResult] = []
        self.failed_results: list[tuple[Path, str]] = []
        self.inspection_results: list[DocumentInfo] = []
        self.inspection_failures: list[tuple[Path, str]] = []

        self.mode_variable = StringVar(
            value="仅处理第一页"
        )
        self.page_numbers_variable = StringVar(value="")
        self.output_directory_variable = StringVar(value="")
        self.status_variable = StringVar(value="等待添加 PDF 文件")

        self._configure_window()
        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        for path in initial_files or []:
            self.add_path(path)

    def _configure_window(self) -> None:
        self.root.title(f"PDF 页面旋转固化工具 {__version__}")
        self.root.geometry("1000x720")
        self.root.minsize(820, 600)
        self.root.configure(background=SKIN_WINDOW_BG)
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self._configure_skin_style()

    def _configure_skin_style(self) -> None:
        """配置 LTY 背景皮肤的控件配色。"""
        self.style.configure("TFrame", background=SKIN_PANEL_BG)
        self.style.configure(
            "TLabel",
            background=SKIN_PANEL_BG,
            foreground=SKIN_TEXT,
        )
        self.style.configure(
            "TLabelframe",
            background=SKIN_PANEL_BG,
            foreground=SKIN_ACCENT,
            bordercolor=SKIN_ACCENT,
            lightcolor=SKIN_ACCENT,
            darkcolor=SKIN_ACCENT,
        )
        self.style.configure(
            "TLabelframe.Label",
            background=SKIN_PANEL_BG,
            foreground=SKIN_ACCENT,
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.style.configure(
            "TButton",
            background=SKIN_ACCENT,
            foreground="#172235",
            padding=(10, 6),
            borderwidth=0,
        )
        self.style.map(
            "TButton",
            background=[
                ("active", SKIN_ACCENT_ACTIVE),
                ("pressed", SKIN_ACCENT_ACTIVE),
                ("disabled", "#6F7885"),
            ],
            foreground=[("disabled", "#D8DCE3")],
        )
        self.style.configure(
            "TEntry",
            fieldbackground=SKIN_TABLE_BG,
            foreground=SKIN_TABLE_TEXT,
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=SKIN_TABLE_BG,
            background=SKIN_ACCENT,
            foreground=SKIN_TABLE_TEXT,
            arrowcolor=SKIN_TABLE_TEXT,
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", SKIN_TABLE_BG)],
            foreground=[("readonly", SKIN_TABLE_TEXT)],
        )
        self.style.configure(
            "Treeview",
            background=SKIN_TABLE_BG,
            fieldbackground=SKIN_TABLE_BG,
            foreground=SKIN_TABLE_TEXT,
            rowheight=27,
            borderwidth=0,
        )
        self.style.configure(
            "Treeview.Heading",
            background=SKIN_ACCENT,
            foreground="#172235",
            relief="flat",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.style.map(
            "Treeview",
            background=[("selected", SKIN_ACCENT_ACTIVE)],
            foreground=[("selected", "#FFFFFF")],
        )
        self.style.configure(
            "Horizontal.TProgressbar",
            troughcolor="#23364C",
            background=SKIN_ACCENT,
            bordercolor="#23364C",
        )

    def _on_skin_canvas_configure(self, event) -> None:
        """让背景居中，并让内容面板随窗口缩放。"""
        if self.skin_background_item is not None:
            self.background_canvas.coords(
                self.skin_background_item,
                event.width // 2,
                event.height // 2,
            )
        self.background_canvas.itemconfigure(
            self.skin_container_window,
            width=max(0, event.width - 64),
            height=max(0, event.height - 48),
        )

    def _build_widgets(self) -> None:
        self.background_canvas = Canvas(
            self.root,
            background=SKIN_WINDOW_BG,
            highlightthickness=0,
            borderwidth=0,
        )
        self.background_canvas.pack(fill="both", expand=True)

        self.skin_background_image: PhotoImage | None = None
        skin_path = resource_path("resources/skins/lty.png")
        if skin_path.exists():
            try:
                self.skin_background_image = PhotoImage(file=str(skin_path))
            except Exception:
                self.logger.exception("加载 LTY 背景皮肤失败：%s", skin_path)

        self.skin_background_item: int | None = None
        if self.skin_background_image is not None:
            self.skin_background_item = self.background_canvas.create_image(
                0,
                0,
                anchor="center",
                image=self.skin_background_image,
            )

        container = ttk.Frame(self.background_canvas, padding=16)
        self.skin_container_window = self.background_canvas.create_window(
            32,
            24,
            anchor="nw",
            window=container,
        )
        self.background_canvas.bind(
            "<Configure>",
            self._on_skin_canvas_configure,
        )
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        title_frame = ttk.Frame(container)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        title_frame.columnconfigure(0, weight=1)
        ttk.Label(
            title_frame,
            text="PDF 页面旋转固化工具",
            font=("Microsoft YaHei UI", 15, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_frame,
            text="保持显示方向不变，将 /Rotate 归零",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        Label(
            title_frame,
            text=RISK_BANNER_TEXT,
            background=SKIN_PANEL_BG,
            foreground="#FFD58A",
            justify="left",
            anchor="w",
            wraplength=900,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).grid(row=2, column=0, sticky="ew", pady=(8, 0))

        table_frame = ttk.Frame(container)
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.file_table = ttk.Treeview(
            table_frame,
            columns=("file", "status", "output"),
            show="headings",
            selectmode="extended",
        )
        self.file_table.heading("file", text="PDF 文件")
        self.file_table.heading("status", text="状态")
        self.file_table.heading("output", text="检查结果 / 输出文件")
        self.file_table.column("file", width=360, minwidth=180)
        self.file_table.column("status", width=110, minwidth=90, anchor="center")
        self.file_table.column("output", width=260, minwidth=150)
        self.file_table.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.file_table.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_table.configure(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(container)
        button_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.add_button = ttk.Button(
            button_frame,
            text="添加 PDF",
            command=self._choose_files,
        )
        self.add_button.pack(side="left")
        self.remove_button = ttk.Button(
            button_frame,
            text="移除选中",
            command=self._remove_selected,
        )
        self.remove_button.pack(side="left", padx=(8, 0))
        self.clear_button = ttk.Button(
            button_frame,
            text="清空列表",
            command=self._clear_files,
        )
        self.clear_button.pack(side="left", padx=(8, 0))
        self.inspect_button = ttk.Button(
            button_frame,
            text="检查页面旋转",
            command=self._start_inspection,
        )
        self.inspect_button.pack(side="left", padx=(8, 0))

        options = ttk.LabelFrame(container, text="处理选项", padding=10)
        options.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        options.columnconfigure(1, weight=1)

        ttk.Label(options, text="处理页面：").grid(row=0, column=0, sticky="w")
        self.mode_combo = ttk.Combobox(
            options,
            state="readonly",
            textvariable=self.mode_variable,
            values=list(MODE_LABELS),
            width=28,
        )
        self.mode_combo.grid(row=0, column=1, sticky="w")
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_changed)

        self.page_label = ttk.Label(options, text="页码：")
        self.page_label.grid(row=1, column=0, sticky="w", pady=(9, 0))
        self.page_entry = ttk.Entry(
            options,
            textvariable=self.page_numbers_variable,
            width=28,
        )
        self.page_entry.grid(row=1, column=1, sticky="ew", pady=(9, 0))
        ttk.Label(
            options,
            text="格式：1,5-9,12（逗号分隔，短横线表示范围）",
        ).grid(row=1, column=2, columnspan=2, sticky="w", padx=(8, 0), pady=(9, 0))

        ttk.Label(options, text="输出位置：").grid(
            row=2,
            column=0,
            sticky="w",
            pady=(9, 0),
        )
        output_entry = ttk.Entry(
            options,
            textvariable=self.output_directory_variable,
        )
        output_entry.grid(row=2, column=1, sticky="ew", pady=(9, 0))
        ttk.Button(
            options,
            text="选择文件夹",
            command=self._choose_output_directory,
        ).grid(row=2, column=2, padx=(8, 0), pady=(9, 0))
        ttk.Button(
            options,
            text="使用原目录",
            command=lambda: self.output_directory_variable.set(""),
        ).grid(row=2, column=3, padx=(8, 0), pady=(9, 0))
        ttk.Label(
            options,
            text="留空时输出到原 PDF 所在目录；程序不会覆盖原文件。",
        ).grid(row=3, column=1, columnspan=3, sticky="w", pady=(5, 0))
        self._on_mode_changed()

        action_frame = ttk.Frame(container)
        action_frame.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        action_frame.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(action_frame, mode="indeterminate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.start_button = ttk.Button(
            action_frame,
            text="开始处理",
            command=self._start_processing,
        )
        self.start_button.grid(row=0, column=1)

        ttk.Label(
            container,
            textvariable=self.status_variable,
            anchor="w",
        ).grid(row=5, column=0, sticky="ew", pady=(10, 0))

    def add_path(self, path: Path) -> None:
        path = path.expanduser().resolve()
        if not path.is_file() or path.suffix.lower() != ".pdf":
            return

        normalized = str(path).casefold()
        if any(str(existing).casefold() == normalized for existing in self.file_items.values()):
            return

        item_id = self.file_table.insert(
            "",
            "end",
            values=(str(path), "等待处理", ""),
        )
        self.file_items[item_id] = path
        self.status_variable.set(f"已添加 {len(self.file_items)} 个 PDF 文件")

    def _choose_files(self) -> None:
        selected = filedialog.askopenfilenames(
            parent=self.root,
            title="选择需要固化旋转的 PDF",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
        )
        for file_name in selected:
            self.add_path(Path(file_name))

    def _remove_selected(self) -> None:
        if self.processing:
            return
        for item_id in self.file_table.selection():
            self.file_table.delete(item_id)
            self.file_items.pop(item_id, None)
        self.status_variable.set(f"当前有 {len(self.file_items)} 个 PDF 文件")

    def _clear_files(self) -> None:
        if self.processing:
            return
        for item_id in tuple(self.file_items):
            self.file_table.delete(item_id)
        self.file_items.clear()
        self.status_variable.set("等待添加 PDF 文件")

    def _on_mode_changed(self, _event=None) -> None:
        """只在选择按页码处理时显示页码输入框。"""
        selected = MODE_LABELS.get(self.mode_variable.get())
        if selected is PageSelectionMode.SELECTED:
            self.page_label.grid()
            self.page_entry.grid()
        else:
            self.page_label.grid_remove()
            self.page_entry.grid_remove()

    def _choose_output_directory(self) -> None:
        directory = filedialog.askdirectory(
            parent=self.root,
            title="选择输出文件夹",
        )
        if directory:
            self.output_directory_variable.set(directory)

    def _start_inspection(self) -> None:
        """在不修改 PDF 的情况下检查所有已添加文件的页面旋转。"""
        if self.processing:
            return
        if not self.file_items:
            messagebox.showwarning(
                "没有文件",
                "请先添加至少一个 PDF 文件。",
                parent=self.root,
            )
            return

        tasks = list(self.file_items.items())
        self.processing = True
        self.inspection_results.clear()
        self.inspection_failures.clear()
        self._set_controls_enabled(False)
        self.progress.start(10)
        self.status_variable.set(f"正在检查 0/{len(tasks)}……")

        worker = threading.Thread(
            target=self._inspect_worker,
            args=(tasks,),
            daemon=True,
        )
        worker.start()
        self.root.after(100, self._poll_events)

    def _inspect_worker(self, tasks: list[tuple[str, Path]]) -> None:
        for index, (item_id, path) in enumerate(tasks, start=1):
            self.events.put(
                ("inspect_status", item_id, index, len(tasks))
            )
            try:
                info = self.service.inspect(path)
                self.events.put(("inspect_success", item_id, path, info))
            except AdjustPdfError as error:
                self.events.put(
                    ("inspect_failure", item_id, path, str(error))
                )
            except Exception as error:
                self.logger.exception("检查 PDF 时发生未预期错误：%s", path)
                self.events.put(
                    (
                        "inspect_failure",
                        item_id,
                        path,
                        f"发生未预期错误：{error}",
                    )
                )
        self.events.put(("inspect_done",))

    def _start_processing(self) -> None:
        if self.processing:
            return
        if not self.file_items:
            messagebox.showwarning(
                "没有文件",
                "请先添加至少一个 PDF 文件。",
                parent=self.root,
            )
            return

        output_text = self.output_directory_variable.get().strip()
        output_directory = Path(output_text) if output_text else None
        mode = MODE_LABELS[self.mode_variable.get()]
        selected_pages: tuple[int, ...] = ()
        if mode is PageSelectionMode.SELECTED:
            try:
                selected_pages = parse_page_numbers(
                    self.page_numbers_variable.get()
                )
            except AdjustPdfError as error:
                messagebox.showwarning(
                    "页码格式错误",
                    str(error),
                    parent=self.root,
                )
                self.page_entry.focus_set()
                return
        tasks = list(self.file_items.items())

        self.processing = True
        self.successful_results.clear()
        self.failed_results.clear()
        self._set_controls_enabled(False)
        self.progress.start(10)
        self.status_variable.set(f"正在执行签名预检 0/{len(tasks)}……")

        worker = threading.Thread(
            target=self._signature_preflight_worker,
            args=(tasks, output_directory, mode, selected_pages),
            daemon=True,
        )
        worker.start()
        self.root.after(100, self._poll_events)

    def _signature_preflight_worker(
        self,
        tasks: list[tuple[str, Path]],
        output_directory: Path | None,
        mode: PageSelectionMode,
        selected_pages: tuple[int, ...],
    ) -> None:
        checked: list[tuple[str, Path, DocumentInfo]] = []
        failures: list[tuple[str, Path, str]] = []
        for index, (item_id, path) in enumerate(tasks, start=1):
            self.events.put(
                ("preflight_status", item_id, index, len(tasks))
            )
            try:
                info = self.service.inspect(path)
                checked.append((item_id, path, info))
            except AdjustPdfError as error:
                failures.append((item_id, path, str(error)))
            except Exception as error:
                self.logger.exception("签名预检时发生未预期错误：%s", path)
                failures.append(
                    (item_id, path, f"发生未预期错误：{error}")
                )

        self.events.put(
            (
                "preflight_done",
                checked,
                failures,
                tasks,
                output_directory,
                mode,
                selected_pages,
            )
        )

    def _process_worker(
        self,
        tasks: list[tuple[str, Path]],
        output_directory: Path | None,
        mode: PageSelectionMode,
        selected_pages: tuple[int, ...],
    ) -> None:
        options = ProcessOptions(
            page_mode=mode,
            selected_pages=selected_pages,
        )
        for index, (item_id, path) in enumerate(tasks, start=1):
            self.events.put(("status", item_id, "处理中", index, len(tasks)))
            try:
                result = self.service.process_file(
                    input_path=path,
                    options=options,
                    output_dir=output_directory,
                )
                self.events.put(("success", item_id, path, result))
            except AdjustPdfError as error:
                self.events.put(("failure", item_id, path, str(error)))
            except Exception as error:
                self.logger.exception("处理 PDF 时发生未预期错误：%s", path)
                self.events.put(
                    (
                        "failure",
                        item_id,
                        path,
                        f"发生未预期错误：{error}",
                    )
                )
        self.events.put(("done",))

    def _poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                event_type = event[0]

                if event_type == "preflight_status":
                    _, item_id, index, total = event
                    self._set_table_values(item_id, status="签名预检中")
                    self.status_variable.set(
                        f"正在执行签名预检 {index}/{total}……"
                    )
                elif event_type == "preflight_done":
                    (
                        _,
                        checked,
                        failures,
                        tasks,
                        output_directory,
                        mode,
                        selected_pages,
                    ) = event
                    self._handle_signature_preflight(
                        checked=checked,
                        failures=failures,
                        tasks=tasks,
                        output_directory=output_directory,
                        mode=mode,
                        selected_pages=selected_pages,
                    )
                    return
                elif event_type == "inspect_status":
                    _, item_id, index, total = event
                    self._set_table_values(item_id, status="检查中")
                    self.status_variable.set(f"正在检查 {index}/{total}……")
                elif event_type == "inspect_success":
                    _, item_id, _path, info = event
                    self.inspection_results.append(info)
                    rotated_count = len(info.rotated_pages)
                    self._set_table_values(
                        item_id,
                        status=f"检查完成（{rotated_count} 页）",
                        output=format_rotation_summary(info),
                    )
                elif event_type == "inspect_failure":
                    _, item_id, path, error = event
                    self.inspection_failures.append((path, error))
                    self._set_table_values(
                        item_id,
                        status="检查失败",
                        output=error,
                    )
                elif event_type == "inspect_done":
                    self._finish_inspection()
                    return
                elif event_type == "status":
                    _, item_id, status, index, total = event
                    self._set_table_values(item_id, status=status)
                    self.status_variable.set(f"正在处理 {index}/{total}……")
                elif event_type == "success":
                    _, item_id, _path, result = event
                    self.successful_results.append(result)
                    status = "成功（有警告）" if result.warnings else "成功"
                    self._set_table_values(
                        item_id,
                        status=status,
                        output=str(result.output_path),
                    )
                elif event_type == "failure":
                    _, item_id, path, error = event
                    self.failed_results.append((path, error))
                    self._set_table_values(item_id, status="失败", output=error)
                elif event_type == "done":
                    self._finish_processing()
                    return
        except queue.Empty:
            pass

        if self.processing:
            self.root.after(100, self._poll_events)

    def _handle_signature_preflight(
        self,
        checked: list[tuple[str, Path, DocumentInfo]],
        failures: list[tuple[str, Path, str]],
        tasks: list[tuple[str, Path]],
        output_directory: Path | None,
        mode: PageSelectionMode,
        selected_pages: tuple[int, ...],
    ) -> None:
        if failures:
            for item_id, path, error in failures:
                self._set_table_values(
                    item_id,
                    status="签名预检失败",
                    output=error,
                )
            self.processing = False
            self.progress.stop()
            self._set_controls_enabled(True)
            self.status_variable.set("签名预检失败，未开始处理")
            details = "\n".join(
                f"{path.name}：{error}" for _, path, error in failures
            )
            messagebox.showwarning(
                "无法安全检查文件",
                "签名预检没有完成，因此没有处理任何文件。\n\n" + details,
                parent=self.root,
            )
            return

        for item_id, _path, info in checked:
            status = (
                f"检测到签名（{len(info.signed_signatures)} 个）"
                if info.has_digital_signatures
                else "预检通过"
            )
            self._set_table_values(item_id, status=status)

        signed_infos = [
            info for _, _, info in checked if info.has_digital_signatures
        ]
        if signed_infos and not self._confirm_signed_files(signed_infos):
            self.processing = False
            self.progress.stop()
            self._set_controls_enabled(True)
            self.status_variable.set("已取消：检测到数字签名或电子签章")
            for item_id, _path, info in checked:
                if info.has_digital_signatures:
                    self._set_table_values(
                        item_id,
                        status="已取消（签章风险）",
                    )
            return

        self.status_variable.set(f"正在处理 0/{len(tasks)}……")
        worker = threading.Thread(
            target=self._process_worker,
            args=(tasks, output_directory, mode, selected_pages),
            daemon=True,
        )
        worker.start()
        self.root.after(100, self._poll_events)

    def _confirm_signed_files(self, infos: list[DocumentInfo]) -> bool:
        """显示签章风险确认窗口，默认选择取消。"""
        window = Toplevel(self.root)
        window.title("检测到数字签名或电子签章")
        window.geometry("820x560")
        window.minsize(620, 420)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", window.destroy)

        result = {"confirmed": False}
        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        text = ScrolledText(
            frame,
            wrap="word",
            font=("Microsoft YaHei UI", 10),
        )
        text.grid(row=0, column=0, sticky="nsew")
        text.insert("1.0", format_signed_documents_warning(infos))
        text.configure(state="disabled")

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=1, column=0, sticky="e", pady=(12, 0))

        def cancel() -> None:
            result["confirmed"] = False
            window.destroy()

        def confirm() -> None:
            result["confirmed"] = True
            window.destroy()

        cancel_button = ttk.Button(
            button_frame,
            text="取消处理",
            command=cancel,
        )
        cancel_button.pack(side="right", padx=(8, 0))
        confirm_button = ttk.Button(
            button_frame,
            text="我已了解风险，仍然继续",
            command=confirm,
        )
        confirm_button.pack(side="right")
        window.bind("<Escape>", lambda _event: cancel())
        window.bind("<Return>", lambda _event: cancel())
        window.grab_set()
        cancel_button.focus_set()
        self.root.wait_window(window)
        return result["confirmed"]

    def _set_table_values(
        self,
        item_id: str,
        *,
        status: str | None = None,
        output: str | None = None,
    ) -> None:
        if not self.file_table.exists(item_id):
            return
        values = list(self.file_table.item(item_id, "values"))
        if status is not None:
            values[1] = status
        if output is not None:
            values[2] = output
        self.file_table.item(item_id, values=values)

    def _finish_inspection(self) -> None:
        self.processing = False
        self.progress.stop()
        self._set_controls_enabled(True)

        success_count = len(self.inspection_results)
        failure_count = len(self.inspection_failures)
        rotated_count = sum(
            len(info.rotated_pages) for info in self.inspection_results
        )
        self.status_variable.set(
            f"检查结束：成功 {success_count} 个，失败 {failure_count} 个，"
            f"发现 {rotated_count} 个旋转页面"
        )

        report_parts: list[str] = []
        if self.inspection_results:
            report_parts.append(
                format_multiple_rotation_reports(self.inspection_results)
            )
        if self.inspection_failures:
            report_parts.append("检查失败：")
            report_parts.extend(
                f"{path.name}：{error}"
                for path, error in self.inspection_failures
            )
        if not report_parts:
            report_parts.append("没有可显示的检查结果。")

        self._show_rotation_report("\n\n".join(report_parts))

    def _show_rotation_report(self, report: str) -> None:
        """用可滚动窗口展示完整的旋转检查结果。"""
        window = Toplevel(self.root)
        window.title("页面旋转与签名检查结果")
        window.geometry("820x560")
        window.minsize(620, 420)
        window.transient(self.root)

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        text = ScrolledText(
            frame,
            wrap="none",
            font=("Microsoft YaHei UI", 10),
        )
        text.grid(row=0, column=0, sticky="nsew")
        text.insert("1.0", report)
        text.configure(state="disabled")

        ttk.Button(
            frame,
            text="关闭",
            command=window.destroy,
        ).grid(row=1, column=0, sticky="e", pady=(10, 0))

    def _finish_processing(self) -> None:
        self.processing = False
        self.progress.stop()
        self._set_controls_enabled(True)

        success_count = len(self.successful_results)
        failure_count = len(self.failed_results)
        warning_count = sum(
            len(result.warnings) for result in self.successful_results
        )
        self.status_variable.set(
            f"处理结束：成功 {success_count} 个，失败 {failure_count} 个，"
            f"警告 {warning_count} 条"
        )

        details = [
            f"成功：{success_count} 个",
            f"失败：{failure_count} 个",
            f"警告：{warning_count} 条",
        ]
        if self.successful_results:
            details.append("\n输出文件：")
            details.extend(str(result.output_path) for result in self.successful_results)
        if self.failed_results:
            details.append("\n失败原因：")
            details.extend(
                f"{path.name}：{error}" for path, error in self.failed_results
            )
        if warning_count:
            details.append("\n警告信息：")
            for result in self.successful_results:
                details.extend(result.warnings)

        if failure_count:
            messagebox.showwarning(
                "处理完成，但有文件失败",
                "\n".join(details),
                parent=self.root,
            )
        else:
            messagebox.showinfo(
                "处理完成",
                "\n".join(details),
                parent=self.root,
            )

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.add_button.configure(state=state)
        self.remove_button.configure(state=state)
        self.clear_button.configure(state=state)
        self.inspect_button.configure(state=state)
        self.start_button.configure(state=state)
        self.mode_combo.configure(state="readonly" if enabled else "disabled")
        self.page_entry.configure(state=state)

    def _on_close(self) -> None:
        if self.processing:
            messagebox.showwarning(
                "正在处理",
                "操作仍在进行中。为避免中断文件读取或写入，请等待完成后再关闭程序。",
                parent=self.root,
            )
            return
        self.root.destroy()


def launch_gui(
    initial_files: list[Path] | None = None,
    log_path: Path | None = None,
) -> None:
    root = Tk()
    icon_path = resource_path("resources/app.ico")
    if icon_path.exists():
        try:
            root.iconbitmap(default=str(icon_path))
        except Exception:
            pass
    MainWindow(root, initial_files=initial_files, log_path=log_path)
    root.mainloop()
