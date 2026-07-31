"""页面旋转检查结果的格式化。"""

from adjust_pdf.models import DocumentInfo
from adjust_pdf.signature_report import format_signature_report


def format_rotation_summary(info: DocumentInfo, max_pages: int = 8) -> str:
    """生成适合显示在文件列表中的简短结果。"""
    rotated = [page for page in info.pages if page.rotation != 0]
    signature_suffix = (
        f"；检测到数字签名：{len(info.signed_signatures)} 个" if info.has_digital_signatures else ""
    )
    if not rotated:
        return "未发现页面旋转属性" + signature_suffix

    preview = "、".join(f"{page.page_number}({page.rotation}°)" for page in rotated[:max_pages])
    if len(rotated) > max_pages:
        preview += f"……共 {len(rotated)} 页"
    return f"旋转页：{preview}" + signature_suffix


def format_rotation_report(info: DocumentInfo) -> str:
    """生成单个 PDF 的完整中文旋转和签名检查报告。"""
    lines = [
        f"文件：{info.path}",
        f"总页数：{info.page_count}",
    ]
    rotated = [page for page in info.pages if page.rotation != 0]
    if not rotated:
        lines.append("检查结果：未发现页面旋转属性。")
    else:
        lines.append(f"检查结果：发现 {len(rotated)} 个带旋转属性的页面。")
        lines.append("")
        for page in rotated:
            lines.append(
                f"第 {page.page_number} 页："
                f"旋转角度：{page.rotation}°，"
                f"{page.width:.2f}（宽） × {page.height:.2f}（高）"
            )

    lines.append("")
    lines.append(format_signature_report(info))
    return "\n".join(lines)


def format_multiple_rotation_reports(infos: list[DocumentInfo]) -> str:
    """生成多个 PDF 的完整检查报告。"""
    return ("\n\n" + "=" * 70 + "\n\n").join(format_rotation_report(info) for info in infos)
