"""PDF 页面属性报告测试。"""

from pathlib import Path

from adjust_pdf.models import DocumentInfo, PageInfo
from adjust_pdf.page_properties_report import (
    format_multiple_page_property_reports,
    format_page_property_detail,
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


def test_single_page_report_contains_all_properties() -> None:
    info = make_info((270,))
    report = format_page_property_detail(info)

    assert "文件：测试.pdf" in report
    assert "总页数：1" in report
    assert "第 1 页" in report
    assert "旋转角度：270°" in report
    assert "841.92（宽）" in report
    assert "595.20（高）" in report


def test_multiple_pages_show_each_page() -> None:
    info = make_info((270, 0, 90))
    report = format_page_property_detail(info)

    assert "第 1 页" in report
    assert "第 2 页" in report
    assert "第 3 页" in report
    assert report.count("（宽）") == 3


def test_zero_rotation_is_displayed() -> None:
    info = make_info((0,))
    report = format_page_property_detail(info)

    assert "旋转角度：0°" in report


def test_rotated_page_is_wrapped_in_red_span() -> None:
    info = make_info((270, 0))
    report = format_page_property_detail(info)

    assert '<span style="color:#cc2222">' in report
    # 有旋转的页面行在红色 span 内
    assert "第 1 页" in report
    # 无旋转的页面单独存在
    assert "第 2 页" in report
    first_page_end = report.index("第 2 页") if "第 2 页" in report else len(report)
    assert "</span>" in report[:first_page_end]


def test_no_red_span_when_none_rotated() -> None:
    info = make_info((0, 0))
    report = format_page_property_detail(info)

    assert "color:#cc2222" not in report


def test_multiple_files_are_separated() -> None:
    report = format_multiple_page_property_reports(
        [
            make_info((270,)),
            make_info((0,)),
        ]
    )

    assert "=" * 70 in report
    assert report.count("文件：测试.pdf") == 2
