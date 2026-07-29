"""PDF 页面属性（宽、高、旋转）详细报告格式（支持 HTML 标记）。"""

from __future__ import annotations

from html import escape

from adjust_pdf.models import DocumentInfo


def _format_page_line(page_number: int, rotation: int, width: float, height: float) -> str:
    """生成单页属性行，有旋转时包裹红色标记。"""
    line = (
        f"第 {page_number} 页："
        f"旋转角度：{rotation}°，"
        f"{width:.2f}（宽） × {height:.2f}（高）"
    )
    if rotation != 0:
        return f'<span style="color:#cc2222">{escape(line)}</span>'
    return escape(line)


def format_page_property_detail(info: DocumentInfo) -> str:
    """生成单个 PDF 的完整页面属性报告（HTML 片段）。"""
    lines: list[str] = [
        escape(f"文件：{info.path}"),
        escape(f"总页数：{info.page_count}"),
        "",
    ]

    for page in info.pages:
        lines.append(
            _format_page_line(page.page_number, page.rotation, page.width, page.height)
        )

    return "<br>\n".join(lines)


def format_multiple_page_property_reports(infos: list[DocumentInfo]) -> str:
    """生成多个 PDF 的页面属性报告，文件之间用分隔线隔开。"""
    separator = escape("\n\n" + "=" * 70 + "\n\n")
    return separator.join(
        format_page_property_detail(info) for info in infos
    )
