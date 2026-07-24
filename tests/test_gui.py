from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from adjust_pdf.gui.main_window import MainWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_pyside_skin_loads_and_defaults_to_first_page() -> None:
    app = _app()
    window = MainWindow()
    window.resize(1100, 790)
    window.show()
    app.processEvents()

    assert window.background.background_loaded
    assert window.mode_combo.currentText() == "仅处理第一页"
    assert not window.page_entry.isVisible()
    assert window.risk_banner.objectName() == "riskBanner"
    assert "rgba(9, 22, 39, 166)" in window.styleSheet()
    assert window.findChild(object, "headerCard") is not None
    assert window.findChild(object, "fileCard") is not None
    assert window.findChild(object, "optionsCard") is not None
    assert window.findChild(object, "actionCard") is not None
    window.close()


def test_selected_page_mode_reveals_page_input() -> None:
    app = _app()
    window = MainWindow()
    window.resize(1100, 790)
    window.show()
    window.mode_combo.setCurrentText("按页码处理")
    app.processEvents()

    assert window.page_entry.isVisible()
    assert window.page_label.isVisible()
    assert window.page_hint.isVisible()
    window.close()


def test_add_path_updates_table(tmp_path: Path) -> None:
    app = _app()
    pdf_path = tmp_path / "示例.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    window = MainWindow(initial_files=[pdf_path])
    window.show()
    app.processEvents()

    assert window.file_table.rowCount() == 1
    assert window.file_table.item(0, 0).text() == str(pdf_path.resolve())
    assert window.file_count_label.text() == "1 个文件"
    window.close()
