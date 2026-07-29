"""PDF 页面属性（宽、高、旋转）详细报告格式。"""

from __future__ import annotations

from adjust_pdf.models import DocumentInfo


def format_page_property_detail(info: DocumentInfo) -> str:
    """生成单个 PDF 的完整页面属性报告。

    逐页显示：
      - 宽（Width）× 高（Height）
      - 旋转（Rotate）
    """
    lines: list[str] = [
        f"文件：{info.path}",
        f"总页数：{info.page_count}",
        "",
    ]

    for page in info.pages:
        lines.append(f"第 {page.page_number} 页：")
        lines.append(f"  宽（Width）：{page.width:.2f} pt")
        lines.append(f"  高（Height）：{page.height:.2f} pt")
        rotation = page.rotation
        rotation_str = f"{rotation}°"
        lines.append(f"  旋转（Rotate）：{rotation_str}")
        lines.append("")

    return "\n".join(lines).rstrip("\n")


def format_multiple_page_property_reports(infos: list[DocumentInfo]) -> str:
    """生成多个 PDF 的页面属性报告，文件之间用分隔线隔开。"""
    return ("\n\n" + "=" * 70 + "\n\n").join(
        format_page_property_detail(info) for info in infos
    )
