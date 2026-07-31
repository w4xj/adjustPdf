"""PySide6 图形界面。"""

from __future__ import annotations

import logging
import queue
import sys
import threading
import uuid
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QLinearGradient,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from adjust_pdf import __version__
from adjust_pdf.exceptions import AdjustPdfError
from adjust_pdf.models import DocumentInfo, PageSelectionMode, ProcessOptions, ProcessResult
from adjust_pdf.page_properties_report import format_multiple_page_property_reports
from adjust_pdf.page_ranges import parse_page_numbers
from adjust_pdf.resources import resource_path
from adjust_pdf.rotation_report import format_multiple_rotation_reports, format_rotation_summary
from adjust_pdf.service import PdfProcessingService
from adjust_pdf.signature_report import RISK_BANNER_TEXT, format_signed_documents_warning

MODE_LABELS = {
    "仅处理第一页": PageSelectionMode.FIRST,
    "所有存在旋转属性的页面": PageSelectionMode.ROTATED,
    "按页码处理": PageSelectionMode.SELECTED,
}


class BackgroundWidget(QWidget):
    """按比例铺满窗口的背景画布。"""

    def __init__(self, image_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap(str(image_path)) if image_path.exists() else QPixmap()
        self.setObjectName("backgroundWidget")

    @property
    def background_loaded(self) -> bool:
        return not self._pixmap.isNull()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.fillRect(self.rect(), QColor("#0B1728"))

        # 仅做极轻遮罩，避免文字发飘，同时尽量保留原图细节。
        shade = QLinearGradient(0, 0, 0, self.height())
        shade.setColorAt(0.0, QColor(0, 0, 0, 10))
        shade.setColorAt(0.5, QColor(0, 0, 0, 0))
        shade.setColorAt(1.0, QColor(0, 0, 0, 18))
        painter.fillRect(self.rect(), shade)
        painter.end()


class MainWindow(QMainWindow):
    """PDF·如一 主窗口。"""

    def __init__(
        self,
        initial_files: list[Path] | None = None,
        log_path: Path | None = None,
        service: PdfProcessingService | None = None,
    ) -> None:
        super().__init__()
        self.logger = logging.getLogger("adjust_pdf.gui")
        self.log_path = log_path
        self.service = service or PdfProcessingService()
        self.events: queue.Queue[tuple] = queue.Queue()
        self.file_items: dict[str, Path] = {}
        self.processing = False
        self.successful_results: list[ProcessResult] = []
        self.failed_results: list[tuple[Path, str]] = []
        self.inspection_results: list[DocumentInfo] = []
        self.inspection_failures: list[tuple[Path, str]] = []
        self.page_props_results: list[DocumentInfo] = []
        self.page_props_failures: list[tuple[Path, str]] = []

        self._configure_window()
        self._build_widgets()
        self._apply_style()

        self.event_timer = QTimer(self)
        self.event_timer.setInterval(100)
        self.event_timer.timeout.connect(self._poll_events)
        self.event_timer.start()

        for file_path in initial_files or []:
            self.add_path(file_path)

    def _configure_window(self) -> None:
        self.setWindowTitle(f"PDF·如一 {__version__}")
        self.resize(1100, 790)
        self.setMinimumSize(900, 700)
        self.setAcceptDrops(True)
        icon_path = resource_path("resources/app.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _build_widgets(self) -> None:
        self.background = BackgroundWidget(resource_path("resources/skins/lty.png"))
        self.setCentralWidget(self.background)

        root_layout = QVBoxLayout(self.background)
        root_layout.setContentsMargins(30, 22, 30, 22)
        root_layout.setSpacing(13)

        header_card = self._create_card("headerCard")
        header_card.setMinimumHeight(125)
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(20, 14, 20, 14)
        header_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("PDF·如一")
        title.setObjectName("titleLabel")
        subtitle = QLabel("消除页面旋转属性，保持 PDF 视觉不变——内容与表象，始终如一")
        subtitle.setObjectName("subtitleLabel")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        title_row.addLayout(title_block, 1)
        motto_badge = QLabel("按时下班 · 身体健康")
        motto_badge.setObjectName("mottoBadge")
        motto_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(motto_badge, 0, Qt.AlignmentFlag.AlignTop)
        header_layout.addLayout(title_row)

        self.risk_banner = QLabel("⚠  " + RISK_BANNER_TEXT)
        self.risk_banner.setObjectName("riskBanner")
        self.risk_banner.setWordWrap(True)
        self.risk_banner.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header_layout.addWidget(self.risk_banner)
        root_layout.addWidget(header_card, 0)

        file_card = self._create_card("fileCard")
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(16, 14, 16, 14)
        file_layout.setSpacing(10)

        file_heading_row = QHBoxLayout()
        file_heading = QLabel("待处理 PDF")
        file_heading.setObjectName("sectionTitle")
        self.file_count_label = QLabel("0 个文件")
        self.file_count_label.setObjectName("mutedLabel")
        file_heading_row.addWidget(file_heading)
        file_heading_row.addStretch(1)
        file_heading_row.addWidget(self.file_count_label)
        file_layout.addLayout(file_heading_row)

        self.file_table = QTableWidget(0, 3)
        self.file_table.setObjectName("fileTable")
        self.file_table.setHorizontalHeaderLabels(["PDF 文件", "状态", "检查结果 / 输出文件"])
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.file_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.file_table.setAlternatingRowColors(False)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setShowGrid(True)
        self.file_table.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.file_table.viewport().setAutoFillBackground(False)
        self.file_table.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        table_palette = self.file_table.palette()
        table_palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0, 0))
        table_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(0, 0, 0, 0))
        table_palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        table_palette.setColor(QPalette.ColorRole.Highlight, QColor(209, 132, 61, 150))
        table_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#fff8e8"))
        self.file_table.setPalette(table_palette)
        header = self.file_table.horizontalHeader()
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(1, 150)
        header.setHighlightSections(False)
        header.setSectionsClickable(False)
        file_layout.addWidget(self.file_table, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(9)
        self.add_button = QPushButton("＋ 添加 PDF")
        self.add_button.clicked.connect(self._choose_files)
        self.remove_button = QPushButton("移除选中")
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button = QPushButton("清空列表")
        self.clear_button.clicked.connect(self._clear_files)
        self.inspect_button = QPushButton("检查页面旋转")
        self.inspect_button.setObjectName("secondaryButton")
        self.inspect_button.clicked.connect(self._start_inspection)
        self.page_props_button = QPushButton("检查页面属性")
        self.page_props_button.setObjectName("secondaryButton")
        self.page_props_button.clicked.connect(self._start_page_props)
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.remove_button)
        button_row.addWidget(self.clear_button)
        button_row.addStretch(1)
        button_row.addWidget(self.page_props_button)
        button_row.addWidget(self.inspect_button)
        file_layout.addLayout(button_row)
        root_layout.addWidget(file_card, 1)

        options_card = self._create_card("optionsCard")
        options_card.setMinimumHeight(145)
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(18, 13, 18, 14)
        options_layout.setSpacing(9)
        options_title = QLabel("处理选项")
        options_title.setObjectName("sectionTitle")
        options_layout.addWidget(options_title)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(9)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)

        form.addWidget(QLabel("处理页面"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(list(MODE_LABELS))
        self.mode_combo.setCurrentText("仅处理第一页")
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        form.addWidget(self.mode_combo, 0, 1)
        mode_hint = QLabel("默认仅固化第一页；也可处理全部旋转页或指定页码")
        mode_hint.setObjectName("mutedLabel")
        form.addWidget(mode_hint, 0, 2, 1, 2)

        self.page_label = QLabel("指定页码")
        self.page_entry = QLineEdit()
        self.page_entry.setPlaceholderText("例如：1,5-9,12")
        self.page_hint = QLabel("逗号分隔，短横线表示连续范围")
        self.page_hint.setObjectName("mutedLabel")
        form.addWidget(self.page_label, 1, 0)
        form.addWidget(self.page_entry, 1, 1)
        form.addWidget(self.page_hint, 1, 2, 1, 2)

        form.addWidget(QLabel("输出位置"), 2, 0)
        self.output_entry = QLineEdit()
        self.output_entry.setPlaceholderText("留空时输出到原 PDF 所在目录")
        form.addWidget(self.output_entry, 2, 1)
        choose_output = QPushButton("选择文件夹")
        choose_output.clicked.connect(self._choose_output_directory)
        original_output = QPushButton("使用原目录")
        original_output.clicked.connect(self.output_entry.clear)
        form.addWidget(choose_output, 2, 2)
        form.addWidget(original_output, 2, 3)
        options_layout.addLayout(form)
        self._on_mode_changed(self.mode_combo.currentText())
        root_layout.addWidget(options_card, 0)

        action_card = self._create_card("actionCard")
        action_card.setMinimumHeight(76)
        action_layout = QHBoxLayout(action_card)
        action_layout.setContentsMargins(18, 12, 18, 12)
        action_layout.setSpacing(14)
        status_block = QVBoxLayout()
        status_block.setSpacing(5)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status_label = QLabel("等待添加 PDF 文件")
        self.status_label.setObjectName("statusLabel")
        status_block.addWidget(self.progress)
        status_block.addWidget(self.status_label)
        action_layout.addLayout(status_block, 1)
        self.start_button = QPushButton("开始处理")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setMinimumSize(QSize(142, 46))
        self.start_button.clicked.connect(self._start_processing)
        action_layout.addWidget(self.start_button)
        root_layout.addWidget(action_card, 0)

        self._controls = [
            self.add_button,
            self.remove_button,
            self.clear_button,
            self.page_props_button,
            self.inspect_button,
            self.start_button,
            self.mode_combo,
            self.page_entry,
            self.output_entry,
            choose_output,
            original_output,
        ]

    def _create_card(self, object_name: str) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        card.setProperty("card", True)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 55))
        card.setGraphicsEffect(shadow)
        return card

    def _apply_style(self) -> None:
        """高透明玻璃风格：优先透出原图，仅保留必要边框和文字对比度。"""
        self.setStyleSheet("""
            QMainWindow, QWidget#backgroundWidget { background-color: #0b1728; }
            QFrame[card="true"] {
                background-color: rgba(8, 18, 32, 28);
                border: 1px solid rgba(255, 214, 150, 170);
                border-radius: 14px;
            }
            QLabel {
                color: #fffdf7;
                font-family: "Microsoft YaHei UI";
                font-size: 13px;
                background: transparent;
            }
            QLabel#titleLabel {
                color: #ffffff;
                font-size: 23px;
                font-weight: 700;
            }
            QLabel#subtitleLabel, QLabel#mutedLabel {
                color: #f2f6ff;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#sectionTitle {
                color: #ffd78b;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#mottoBadge {
                color: #fff8ec;
                background-color: rgba(20, 42, 68, 95);
                border: 1px solid rgba(255, 210, 140, 180);
                border-radius: 11px;
                padding: 5px 11px;
                font-weight: 700;
                font-size: 12px;
            }
            QLabel#riskBanner {
                color: #fff7f7;
                background-color: rgba(176, 18, 29, 125);
                border: 1px solid rgba(255, 120, 128, 230);
                border-radius: 8px;
                padding: 9px 12px;
                font-weight: 700;
                font-size: 13px;
            }
            QLabel#statusLabel {
                color: #fffaf0;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton {
                color: #fffaf0;
                background-color: rgba(234, 176, 94, 70);
                border: 1px solid rgba(255, 225, 170, 220);
                border-radius: 7px;
                padding: 8px 15px;
                font-weight: 700;
                min-height: 18px;
            }
            QPushButton:hover {
                background-color: rgba(242, 194, 118, 140);
                border-color: #ffe0a7;
            }
            QPushButton:pressed {
                background-color: rgba(207, 135, 55, 170);
            }
            QPushButton:disabled {
                color: #d5dbe4;
                background-color: rgba(86, 96, 110, 90);
                border-color: rgba(180, 188, 198, 140);
            }
            QPushButton#secondaryButton {
                color: #fff8ed;
                background-color: rgba(27, 71, 105, 70);
                border-color: rgba(150, 210, 245, 210);
            }
            QPushButton#secondaryButton:hover {
                background-color: rgba(39, 91, 129, 140);
            }
            QPushButton#primaryButton {
                font-size: 15px;
                min-height: 28px;
                color: #fffdf8;
                background-color: rgba(240, 170, 79, 85);
                border-color: #ffd18d;
            }
            QLineEdit, QComboBox {
                color: #fffdf8;
                background-color: rgba(10, 24, 40, 45);
                border: 1px solid rgba(255, 214, 150, 190);
                border-radius: 6px;
                padding: 7px 9px;
                selection-background-color: rgba(200, 120, 50, 180);
                selection-color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #f2b866;
                padding: 6px 8px;
                background-color: rgba(10, 24, 40, 60);
            }
            QComboBox QAbstractItemView {
                color: #fffdf8;
                background: rgba(12, 28, 46, 210);
                selection-background-color: rgba(229, 163, 83, 180);
                border: 1px solid rgba(255, 214, 150, 170);
            }
            QTableWidget {
                color: #ffffff;
                background-color: transparent;
                alternate-background-color: transparent;
                border: 1px solid rgba(255, 214, 150, 200);
                border-radius: 7px;
                gridline-color: rgba(255, 214, 150, 165);
                selection-background-color: rgba(209, 132, 61, 120);
                selection-color: #fff8e8;
                outline: none;
            }
            QTableWidget::item {
                color: #ffffff;
                background: transparent;
                border: none;
                padding: 5px 6px;
            }
            QTableWidget::item:selected {
                color: #fff8e8;
                background: rgba(209, 132, 61, 120);
            }
            QHeaderView {
                background: transparent;
                border: none;
            }
            QHeaderView::section {
                color: #ffffff;
                background-color: rgba(234, 176, 94, 185);
                border: none;
                border-right: 1px solid rgba(255, 225, 170, 170);
                border-bottom: 1px solid rgba(255, 214, 150, 180);
                padding: 8px 6px;
                font-weight: 700;
                font-size: 13px;
            }
            QHeaderView::section:last {
                border-right: none;
            }
            QProgressBar {
                background-color: rgba(24, 49, 72, 80);
                border: 1px solid rgba(180, 220, 245, 160);
                border-radius: 5px;
                height: 9px;
            }
            QProgressBar::chunk {
                background-color: rgba(239, 173, 85, 180);
                border-radius: 4px;
            }
            QScrollBar:vertical {
                background: rgba(20, 36, 55, 40);
                width: 11px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(200, 135, 63, 150);
                border-radius: 5px;
                min-height: 28px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

    def add_path(self, path: Path) -> None:
        path = path.expanduser().resolve()
        if not path.is_file() or path.suffix.lower() != ".pdf":
            return
        normalized = str(path).casefold()
        if any(str(existing).casefold() == normalized for existing in self.file_items.values()):
            return

        item_id = uuid.uuid4().hex
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        path_item = QTableWidgetItem(str(path))
        path_item.setData(Qt.ItemDataRole.UserRole, item_id)
        self.file_table.setItem(row, 0, path_item)
        self.file_table.setItem(row, 1, QTableWidgetItem("等待处理"))
        self.file_table.setItem(row, 2, QTableWidgetItem(""))
        self.file_items[item_id] = path
        self._update_file_count()
        self._set_status(f"已添加 {len(self.file_items)} 个 PDF 文件")

    def _update_file_count(self) -> None:
        self.file_count_label.setText(f"{len(self.file_items)} 个文件")

    def _choose_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self, "选择需要固化旋转的 PDF", "", "PDF 文件 (*.pdf);;所有文件 (*.*)"
        )
        for file_name in selected:
            self.add_path(Path(file_name))

    def _remove_selected(self) -> None:
        if self.processing:
            return
        rows = sorted({index.row() for index in self.file_table.selectedIndexes()}, reverse=True)
        for row in rows:
            item = self.file_table.item(row, 0)
            if item is not None:
                self.file_items.pop(item.data(Qt.ItemDataRole.UserRole), None)
            self.file_table.removeRow(row)
        self._update_file_count()
        self._set_status(f"当前有 {len(self.file_items)} 个 PDF 文件")

    def _clear_files(self) -> None:
        if self.processing:
            return
        self.file_table.setRowCount(0)
        self.file_items.clear()
        self._update_file_count()
        self._set_status("等待添加 PDF 文件")

    def _on_mode_changed(self, label: str) -> None:
        selected = MODE_LABELS.get(label)
        visible = selected is PageSelectionMode.SELECTED
        self.page_label.setVisible(visible)
        self.page_entry.setVisible(visible)
        self.page_hint.setVisible(visible)

    def _choose_output_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if directory:
            self.output_entry.setText(directory)

    def _start_inspection(self) -> None:
        if self.processing:
            return
        if not self.file_items:
            QMessageBox.warning(self, "没有文件", "请先添加至少一个 PDF 文件。")
            return
        tasks = list(self.file_items.items())
        self.processing = True
        self.inspection_results.clear()
        self.inspection_failures.clear()
        self._set_controls_enabled(False)
        self._start_busy()
        self._set_status(f"正在检查 0/{len(tasks)}……")
        threading.Thread(target=self._inspect_worker, args=(tasks,), daemon=True).start()

    def _inspect_worker(self, tasks: list[tuple[str, Path]]) -> None:
        for index, (item_id, path) in enumerate(tasks, start=1):
            self.events.put(("inspect_status", item_id, index, len(tasks)))
            try:
                self.events.put(("inspect_success", item_id, path, self.service.inspect(path)))
            except AdjustPdfError as error:
                self.events.put(("inspect_failure", item_id, path, str(error)))
            except Exception as error:
                self.logger.exception("检查 PDF 时发生未预期错误：%s", path)
                self.events.put(("inspect_failure", item_id, path, f"发生未预期错误：{error}"))
        self.events.put(("inspect_done",))

    def _start_page_props(self) -> None:
        """启动检查页面属性。"""
        if self.processing:
            return
        if not self.file_items:
            QMessageBox.warning(self, "没有文件", "请先添加至少一个 PDF 文件。")
            return
        tasks = list(self.file_items.items())
        self.processing = True
        self.page_props_results.clear()
        self.page_props_failures.clear()
        self._set_controls_enabled(False)
        self._start_busy()
        self._set_status(f"正在检查页面属性 0/{len(tasks)}……")
        threading.Thread(target=self._page_props_worker, args=(tasks,), daemon=True).start()

    def _page_props_worker(self, tasks: list[tuple[str, Path]]) -> None:
        for index, (item_id, path) in enumerate(tasks, start=1):
            self.events.put(("page_props_status", item_id, index, len(tasks)))
            try:
                self.events.put(("page_props_success", item_id, path, self.service.inspect(path)))
            except AdjustPdfError as error:
                self.events.put(("page_props_failure", item_id, path, str(error)))
            except Exception as error:
                self.logger.exception("检查页面属性时发生未预期错误：%s", path)
                self.events.put(("page_props_failure", item_id, path, f"发生未预期错误：{error}"))
        self.events.put(("page_props_done",))

    def _start_processing(self) -> None:
        if self.processing:
            return
        if not self.file_items:
            QMessageBox.warning(self, "没有文件", "请先添加至少一个 PDF 文件。")
            return

        output_text = self.output_entry.text().strip()
        output_directory = Path(output_text) if output_text else None
        mode = MODE_LABELS[self.mode_combo.currentText()]
        selected_pages: tuple[int, ...] = ()
        if mode is PageSelectionMode.SELECTED:
            try:
                selected_pages = parse_page_numbers(self.page_entry.text())
            except AdjustPdfError as error:
                QMessageBox.warning(self, "页码格式错误", str(error))
                self.page_entry.setFocus()
                return

        tasks = list(self.file_items.items())
        self.processing = True
        self.successful_results.clear()
        self.failed_results.clear()
        self._set_controls_enabled(False)
        self._start_busy()
        self._set_status(f"正在执行签名预检 0/{len(tasks)}……")
        threading.Thread(
            target=self._signature_preflight_worker,
            args=(tasks, output_directory, mode, selected_pages),
            daemon=True,
        ).start()

    def _signature_preflight_worker(self, tasks, output_directory, mode, selected_pages) -> None:
        checked: list[tuple[str, Path, DocumentInfo]] = []
        failures: list[tuple[str, Path, str]] = []
        for index, (item_id, path) in enumerate(tasks, start=1):
            self.events.put(("preflight_status", item_id, index, len(tasks)))
            try:
                checked.append((item_id, path, self.service.inspect(path)))
            except AdjustPdfError as error:
                failures.append((item_id, path, str(error)))
            except Exception as error:
                self.logger.exception("签名预检时发生未预期错误：%s", path)
                failures.append((item_id, path, f"发生未预期错误：{error}"))
        self.events.put(
            ("preflight_done", checked, failures, tasks, output_directory, mode, selected_pages)
        )

    def _process_worker(self, tasks, output_directory, mode, selected_pages) -> None:
        options = ProcessOptions(page_mode=mode, selected_pages=selected_pages)
        for index, (item_id, path) in enumerate(tasks, start=1):
            self.events.put(("status", item_id, "处理中", index, len(tasks)))
            try:
                result = self.service.process_file(
                    input_path=path, options=options, output_dir=output_directory
                )
                self.events.put(("success", item_id, path, result))
            except AdjustPdfError as error:
                self.events.put(("failure", item_id, path, str(error)))
            except Exception as error:
                self.logger.exception("处理 PDF 时发生未预期错误：%s", path)
                self.events.put(("failure", item_id, path, f"发生未预期错误：{error}"))
        self.events.put(("done",))

    def _poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "preflight_status":
                    _, item_id, index, total = event
                    self._set_table_values(item_id, status="签名预检中")
                    self._set_status(f"正在执行签名预检 {index}/{total}……")
                elif kind == "preflight_done":
                    _, checked, failures, tasks, output_directory, mode, selected_pages = event
                    self._handle_signature_preflight(
                        checked, failures, tasks, output_directory, mode, selected_pages
                    )
                elif kind == "inspect_status":
                    _, item_id, index, total = event
                    self._set_table_values(item_id, status="检查中")
                    self._set_status(f"正在检查 {index}/{total}……")
                elif kind == "inspect_success":
                    _, item_id, _path, info = event
                    self.inspection_results.append(info)
                    self._set_table_values(
                        item_id,
                        status=f"检查完成（{len(info.rotated_pages)} 页）",
                        output=format_rotation_summary(info),
                    )
                elif kind == "inspect_failure":
                    _, item_id, path, error = event
                    self.inspection_failures.append((path, error))
                    self._set_table_values(item_id, status="检查失败", output=error)
                elif kind == "inspect_done":
                    self._finish_inspection()
                elif kind == "page_props_status":
                    _, item_id, index, total = event
                    self._set_table_values(item_id, status="检查页面属性中")
                    self._set_status(f"正在检查页面属性 {index}/{total}……")
                elif kind == "page_props_success":
                    _, item_id, _path, info = event
                    self.page_props_results.append(info)
                    self._set_table_values(item_id, status="检查完成")
                elif kind == "page_props_failure":
                    _, item_id, path, error = event
                    self.page_props_failures.append((path, error))
                    self._set_table_values(item_id, status="检查失败", output=error)
                elif kind == "page_props_done":
                    self._finish_page_props()
                elif kind == "status":
                    _, item_id, status, index, total = event
                    self._set_table_values(item_id, status=status)
                    self._set_status(f"正在处理 {index}/{total}……")
                elif kind == "success":
                    _, item_id, _path, result = event
                    self.successful_results.append(result)
                    self._set_table_values(
                        item_id,
                        status="成功（有警告）" if result.warnings else "成功",
                        output=str(result.output_path),
                    )
                elif kind == "failure":
                    _, item_id, path, error = event
                    self.failed_results.append((path, error))
                    self._set_table_values(item_id, status="失败", output=error)
                elif kind == "done":
                    self._finish_processing()
        except queue.Empty:
            return

    def _handle_signature_preflight(
        self, checked, failures, tasks, output_directory, mode, selected_pages
    ) -> None:
        if failures:
            for item_id, _path, error in failures:
                self._set_table_values(item_id, status="签名预检失败", output=error)
            self.processing = False
            self._stop_busy()
            self._set_controls_enabled(True)
            self._set_status("签名预检失败，未开始处理")
            details = "\n".join(f"{path.name}：{error}" for _, path, error in failures)
            QMessageBox.warning(
                self, "无法安全检查文件", "签名预检没有完成，因此没有处理任何文件。\n\n" + details
            )
            return

        for item_id, _path, info in checked:
            status = (
                f"检测到签名（{len(info.signed_signatures)} 个）"
                if info.has_digital_signatures
                else "预检通过"
            )
            self._set_table_values(item_id, status=status)

        signed_infos = [info for _, _, info in checked if info.has_digital_signatures]
        if signed_infos and not self._confirm_signed_files(signed_infos):
            self.processing = False
            self._stop_busy()
            self._set_controls_enabled(True)
            self._set_status("已取消：检测到数字签名或电子签章")
            for item_id, _path, info in checked:
                if info.has_digital_signatures:
                    self._set_table_values(item_id, status="已取消（签章风险）")
            return

        self._set_status(f"正在处理 0/{len(tasks)}……")
        threading.Thread(
            target=self._process_worker,
            args=(tasks, output_directory, mode, selected_pages),
            daemon=True,
        ).start()

    def _confirm_signed_files(self, infos: list[DocumentInfo]) -> bool:
        dialog = QDialog(self)
        dialog.setWindowTitle("检测到数字签名或电子签章")
        dialog.resize(840, 580)
        dialog.setMinimumSize(650, 440)
        layout = QVBoxLayout(dialog)
        warning = QLabel("⚠  继续处理将使新文件的签名验证失效")
        warning.setObjectName("dialogWarning")
        layout.addWidget(warning)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(format_signed_documents_warning(infos))
        layout.addWidget(text, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        continue_button = QPushButton("我已了解风险，仍然继续")
        continue_button.setObjectName("dangerButton")
        cancel_button = QPushButton("取消处理")
        cancel_button.setDefault(True)
        cancel_button.setFocus()
        continue_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        buttons.addWidget(continue_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)
        dialog.setStyleSheet(
            self.styleSheet()
            + "QLabel#dialogWarning{background:#a4111c;color:white;padding:10px;border-radius:7px;font-weight:700;} QPushButton#dangerButton{background:#8d1720;color:white;border-color:#ef6971;} QTextEdit{background:#f7f2e8;color:#17243a;border:1px solid #d89a4a;padding:8px;}"
        )
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _row_for_id(self, item_id: str) -> int | None:
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == item_id:
                return row
        return None

    def _set_table_values(
        self, item_id: str, *, status: str | None = None, output: str | None = None
    ) -> None:
        row = self._row_for_id(item_id)
        if row is None:
            return
        if status is not None:
            self.file_table.item(row, 1).setText(status)
        if output is not None:
            self.file_table.item(row, 2).setText(output)

    def _finish_inspection(self) -> None:
        self.processing = False
        self._stop_busy()
        self._set_controls_enabled(True)
        success_count = len(self.inspection_results)
        failure_count = len(self.inspection_failures)
        rotated_count = sum(len(info.rotated_pages) for info in self.inspection_results)
        self._set_status(
            f"检查结束：成功 {success_count} 个，失败 {failure_count} 个，发现 {rotated_count} 个旋转页面"
        )
        parts: list[str] = []
        if self.inspection_results:
            parts.append(format_multiple_rotation_reports(self.inspection_results))
        if self.inspection_failures:
            parts.append("检查失败：")
            parts.extend(f"{path.name}：{error}" for path, error in self.inspection_failures)
        self._show_rotation_report("\n\n".join(parts or ["没有可显示的检查结果。"]))

    def _show_rotation_report(self, report: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("页面旋转与签名检查结果")
        dialog.resize(860, 590)
        dialog.setMinimumSize(650, 440)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        text.setPlainText(report)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.accept)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        layout.addWidget(text, 1)
        layout.addLayout(button_row)
        dialog.setStyleSheet(
            self.styleSheet()
            + "QTextEdit{background:#f7f2e8;color:#17243a;border:1px solid #d89a4a;padding:8px;}"
        )
        dialog.exec()

    def _finish_page_props(self) -> None:
        self.processing = False
        self._stop_busy()
        self._set_controls_enabled(True)
        success_count = len(self.page_props_results)
        failure_count = len(self.page_props_failures)
        self._set_status(f"页面属性检查结束：成功 {success_count} 个，失败 {failure_count} 个")
        parts: list[str] = []
        if self.page_props_results:
            parts.append(format_multiple_page_property_reports(self.page_props_results))
        if self.page_props_failures:
            from html import escape

            fail_lines = ["<br>", escape("检查失败：")]
            fail_lines.extend(
                escape(f"{path.name}：{error}") for path, error in self.page_props_failures
            )
            parts.append("<br>\n".join(fail_lines))
        self._show_page_props_report("\n\n".join(parts or ["没有可显示的检查结果。"]))

    def _show_page_props_report(self, report: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("PDF 页面属性检查结果")
        dialog.resize(860, 590)
        dialog.setMinimumSize(650, 440)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        text.setHtml(
            f"<pre style='font-family:Consolas,Courier New,monospace;font-size:13px;margin:0'>{report}</pre>"
        )
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.accept)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        layout.addWidget(text, 1)
        layout.addLayout(button_row)
        dialog.setStyleSheet(
            self.styleSheet()
            + "QTextEdit{background:#f7f2e8;color:#17243a;border:1px solid #d89a4a;padding:8px;}"
        )
        dialog.exec()

    def _finish_processing(self) -> None:
        self.processing = False
        self._stop_busy()
        self._set_controls_enabled(True)
        success_count = len(self.successful_results)
        failure_count = len(self.failed_results)
        warning_count = sum(len(result.warnings) for result in self.successful_results)
        self._set_status(
            f"处理结束：成功 {success_count} 个，失败 {failure_count} 个，警告 {warning_count} 条"
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
            details.extend(f"{path.name}：{error}" for path, error in self.failed_results)
        if warning_count:
            details.append("\n警告信息：")
            for result in self.successful_results:
                details.extend(result.warnings)
        text = "\n".join(details)
        if failure_count:
            QMessageBox.warning(self, "处理完成，但有文件失败", text)
        else:
            QMessageBox.information(self, "处理完成", text)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for control in self._controls:
            control.setEnabled(enabled)
        if enabled:
            self._on_mode_changed(self.mode_combo.currentText())

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _start_busy(self) -> None:
        self.progress.setRange(0, 0)

    def _stop_busy(self) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and any(
            url.toLocalFile().lower().endswith(".pdf") for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            self.add_path(Path(url.toLocalFile()))
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.processing:
            QMessageBox.warning(
                self,
                "正在处理",
                "操作仍在进行中。为避免中断文件读取或写入，请等待完成后再关闭程序。",
            )
            event.ignore()
            return
        event.accept()


def launch_gui(initial_files: list[Path] | None = None, log_path: Path | None = None) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("PDF·如一")
    app.setApplicationVersion(__version__)
    icon_path = resource_path("resources/app.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow(initial_files=initial_files, log_path=log_path)
    window.show()
    app.exec()
