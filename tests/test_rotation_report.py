"""旋转检查报告测试。"""

from pathlib import Path

from adjust_pdf.models import DocumentInfo, PageInfo
from adjust_pdf.rotation_report import (
    format_multiple_rotation_reports,
    format_rotation_report,
    format_rotation_summary,
)


def make_info(rotations: tuple[int, ...]) -> DocumentInfo:
    return DocumentInfo(
        path=Path("测试.pdf"),
        page_count=len(rotations),
        pages=tuple(
            PageInfo(
                page_number=index,
                width=841.92,
                height=595.2,
                rotation=rotation,
                has_annotations=False,
            )
            for index, rotation in enumerate(rotations, start=1)
        ),
    )


def test_rotation_summary_reports_rotated_pages() -> None:
    info = make_info((270, 0, 90))

    summary = format_rotation_summary(info)

    assert "旋转页：1(270°)、3(90°)" == summary


def test_rotation_summary_reports_no_rotation() -> None:
    info = make_info((0, 0))

    assert format_rotation_summary(info) == "未发现页面旋转属性"


def test_rotation_report_contains_page_details() -> None:
    report = format_rotation_report(make_info((270, 0, 90)))

    assert "总页数：3" in report
    assert "发现 2 个带旋转属性的页面" in report
    assert "第 1 页：旋转角度：270°" in report
    assert "第 3 页：旋转角度：90°" in report


def test_multiple_reports_are_separated() -> None:
    report = format_multiple_rotation_reports([
        make_info((270,)),
        make_info((0,)),
    ])

    assert "=" * 70 in report
    assert report.count("文件：测试.pdf") == 2


def test_signature_report_shows_signed_structure() -> None:
    from adjust_pdf.models import SignatureInfo
    from adjust_pdf.signature_report import (
        format_signature_report,
        format_signed_documents_warning,
    )

    info = DocumentInfo(
        path=Path("已签名.pdf"),
        page_count=1,
        pages=(),
        signatures=(
            SignatureInfo(
                field_name="签名字段",
                page_number=1,
                filter_name="/Adobe.PPKLite",
                subfilter="/adbe.pkcs7.detached",
                reason="测试电子签章",
                location=None,
                signing_time="D:20260723120000+08'00'",
                has_byte_range=True,
                contents_length=10,
            ),
        ),
    )

    report = format_signature_report(info)
    warning = format_signed_documents_warning([info])

    assert "检测到 1 个已写入签名数据的字段" in report
    assert "签名字段" in report
    assert "签名验证失效" in warning
