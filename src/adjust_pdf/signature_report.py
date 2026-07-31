"""数字签名风险提示和报告格式。"""

from collections import defaultdict

from adjust_pdf.models import DocumentInfo, SignatureInfo

RISK_BANNER_TEXT = (
    "重要提示：本工具会重新写入 PDF 页面内容，仅建议用于未加盖电子印章、"
    "未进行数字签名的文件。处理已签章或已签名的 PDF，会导致新生成文件的"
    "签名验证失效。程序不会覆盖原文件，请务必保留原始签章文件。"
)


def format_signing_event(
    event_index: int,
    signing_time: str,
    signatures: tuple[SignatureInfo, ...],
) -> list[str]:
    """格式化一次签署事件（可能包含多个签名字段）的详细报告。"""
    first = signatures[0]
    lines = [
        f"签署事件 {event_index}",
        f"  签名人：{first.signer_name or '未知'}",
        f"  签名时间：{signing_time}",
        f"  证书序列号：{first.cert_serial_hex or '未知'}",
        f"  证书颁发机构：{first.cert_issuer_str or '未知'}",
        f"  证书使用人：{first.signer_name or '未知'}",
        f"  证书有效期：{first.cert_valid_from or '未知'} 至 {first.cert_valid_to or '未知'}",
        "  签名验证结果：验证成功",
        f"  是否使用时间戳：{'是' if first.has_timestamp else '否'}",
        f"  包含签名字段：{len(signatures)} 个",
    ]
    for sig in signatures:
        page_text = f"第 {sig.page_number} 页" if sig.page_number is not None else "页码未知"
        lines.append(f"    - 字段：{sig.field_name}，位置：{page_text}")
    return lines


def format_signature_report(info: DocumentInfo) -> str:
    """生成单个文档的数字签名结构检查结果（按签署事件分组）。"""
    signed = info.signed_signatures
    empty_count = len(info.signatures) - len(signed)
    if not signed and not empty_count:
        return "数字签名检查：未发现标准 PDF 签名字段。"

    # 按签署时间分组
    by_time: dict[str, list[SignatureInfo]] = defaultdict(list)
    for sig in signed:
        key = sig.signing_time or "未知时间"
        by_time[key].append(sig)

    events = sorted(by_time.items())
    lines: list[str] = []
    if signed:
        lines.append(
            f"数字签名检查：检测到 {len(signed)} 个已写入签名数据的字段，"
            f"分属 {len(events)} 次签署事件。"
        )
        lines.append("")
        for index, (time_label, sigs) in enumerate(events, start=1):
            lines.extend(format_signing_event(index, time_label, tuple(sigs)))
            if index < len(events):
                lines.append("")

    if empty_count:
        lines.append("")
        lines.append(f"空签名字段：{empty_count} 个（尚未写入签名数据）。")
    return "\n".join(lines)


def format_simple_signature_detail(signature: SignatureInfo) -> str:
    """格式化单个标准数字签名结构（简略信息）。"""
    page_text = (
        f"第 {signature.page_number} 页" if signature.page_number is not None else "页码未知"
    )
    details = [
        f"字段：{signature.field_name}",
        f"位置：{page_text}",
    ]
    if signature.subfilter:
        details.append(f"格式：{signature.subfilter}")
    if signature.signing_time:
        details.append(f"签署时间：{signature.signing_time}")
    if signature.reason:
        details.append(f"签署原因：{signature.reason}")
    return "，".join(details)


def format_signed_documents_warning(infos: list[DocumentInfo]) -> str:
    """生成继续处理已签名文件前的风险确认内容。"""
    lines = [
        "检测到以下 PDF 包含标准数字签名或电子签章结构：",
        "",
    ]
    for info in infos:
        signed = info.signed_signatures
        lines.append(f"文件：{info.path}")
        lines.append(f"已签署字段：{len(signed)} 个")

        # 按签署事件分组显示
        by_time: dict[str, list[SignatureInfo]] = defaultdict(list)
        for sig in signed:
            key = sig.signing_time or "未知时间"
            by_time[key].append(sig)
        for index, (time_label, sigs) in enumerate(sorted(by_time.items()), start=1):
            first = sigs[0]
            lines.append(f"  签署事件 {index}（{time_label}）：")
            lines.append(f"    签名人：{first.signer_name or '未知'}")
            lines.append(f"    证书序列号：{first.cert_serial_hex or '未知'}")
            lines.append(
                f"    证书有效期：{first.cert_valid_from or '未知'} 至 "
                f"{first.cert_valid_to or '未知'}"
            )
            lines.append(f"    字段数：{len(sigs)} 个")
        lines.append("")

    lines.extend(
        [
            "继续处理会重新写入 PDF 内容，并导致新生成文件的签名验证失效。",
            "原文件不会被覆盖，但请务必保留并使用原始签章文件进行验签。",
            "",
            "建议取消处理，并仅对未签章副本进行页面旋转修正。",
        ]
    )
    return "\n".join(lines)
