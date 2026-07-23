"""pypdf 处理引擎测试。"""

from pathlib import Path

import fitz
import pytest
from pypdf import PdfReader

from adjust_pdf.engines.pypdf_engine import PypdfEngine
from adjust_pdf.exceptions import EncryptedPdfError, InvalidInputError
from adjust_pdf.models import PageSelectionMode, ProcessOptions
from adjust_pdf.service import PdfProcessingService
from tests.helpers import create_test_pdf


@pytest.mark.parametrize(
    ("rotation", "expected_width", "expected_height"),
    [
        (0, 200, 100),
        (90, 100, 200),
        (180, 200, 100),
        (270, 100, 200),
    ],
)
def test_rotation_is_flattened_and_page_size_is_correct(
    tmp_path: Path,
    rotation: int,
    expected_width: int,
    expected_height: int,
) -> None:
    input_path = create_test_pdf(tmp_path / f"rotation-{rotation}.pdf", (rotation,))
    service = PdfProcessingService()

    result = service.process_file(input_path)
    output_reader = PdfReader(str(result.output_path))
    page = output_reader.pages[0]

    assert int(page.rotation or 0) == 0
    assert float(page.mediabox.width) == pytest.approx(expected_width)
    assert float(page.mediabox.height) == pytest.approx(expected_height)
    assert result.processed_pages == ([] if rotation == 0 else [1])
    assert input_path.exists()


def test_mixed_pages_are_processed(tmp_path: Path) -> None:
    input_path = create_test_pdf(
        tmp_path / "混合页面.pdf",
        (270, 0, 90, 180),
    )

    result = PdfProcessingService().process_file(input_path)
    reader = PdfReader(str(result.output_path))

    assert result.processed_pages == [1, 3, 4]
    assert [int(page.rotation or 0) for page in reader.pages] == [0, 0, 0, 0]


def test_first_page_mode_only_processes_first_page(tmp_path: Path) -> None:
    input_path = create_test_pdf(tmp_path / "仅首页.pdf", (270, 90))
    options = ProcessOptions(page_mode=PageSelectionMode.FIRST)

    result = PdfProcessingService().process_file(input_path, options=options)
    reader = PdfReader(str(result.output_path))

    assert result.processed_pages == [1]
    assert int(reader.pages[0].rotation or 0) == 0
    assert int(reader.pages[1].rotation or 0) == 90


def test_selected_page_mode(tmp_path: Path) -> None:
    input_path = create_test_pdf(tmp_path / "指定页面.pdf", (90, 180, 270))
    options = ProcessOptions(
        page_mode=PageSelectionMode.SELECTED,
        selected_pages=(2, 3),
    )

    result = PdfProcessingService().process_file(input_path, options=options)
    reader = PdfReader(str(result.output_path))

    assert result.processed_pages == [2, 3]
    assert [int(page.rotation or 0) for page in reader.pages] == [90, 0, 0]


def test_selected_page_out_of_range(tmp_path: Path) -> None:
    input_path = create_test_pdf(tmp_path / "超范围.pdf", (90,))
    options = ProcessOptions(
        page_mode=PageSelectionMode.SELECTED,
        selected_pages=(2,),
    )

    with pytest.raises(InvalidInputError, match="页码超出范围"):
        PdfProcessingService().process_file(input_path, options=options)


def test_annotation_page_generates_warning(tmp_path: Path) -> None:
    input_path = create_test_pdf(
        tmp_path / "带链接.pdf",
        (270,),
        annotation_pages=(1,),
    )

    result = PdfProcessingService().process_file(input_path)

    assert len(result.warnings) == 1
    assert "第 1 页" in result.warnings[0]


def test_encrypted_pdf_is_rejected(tmp_path: Path) -> None:
    input_path = create_test_pdf(
        tmp_path / "加密.pdf",
        (270,),
        encrypted_password="secret",
    )

    with pytest.raises(EncryptedPdfError, match="需要密码"):
        PdfProcessingService().process_file(input_path)


def test_inspect_reports_rotations_and_annotations(tmp_path: Path) -> None:
    input_path = create_test_pdf(
        tmp_path / "检查.pdf",
        (270, 0, 90),
        annotation_pages=(1,),
    )

    info = PypdfEngine().inspect(input_path)

    assert info.page_count == 3
    assert info.rotated_pages == (1, 3)
    assert info.annotation_pages == (1,)


def _render_first_page(path: Path) -> tuple[int, int, bytes]:
    document = fitz.open(path)
    try:
        pixmap = document[0].get_pixmap(alpha=False)
        return pixmap.width, pixmap.height, pixmap.samples
    finally:
        document.close()


def test_visual_result_stays_the_same_after_flattening(tmp_path: Path) -> None:
    input_path = create_test_pdf(tmp_path / "视觉一致性.pdf", (270,))
    before = _render_first_page(input_path)

    result = PdfProcessingService().process_file(input_path)
    after = _render_first_page(result.output_path)

    assert before[:2] == after[:2]
    assert len(before[2]) == len(after[2])
    average_difference = sum(
        abs(left - right) for left, right in zip(before[2], after[2], strict=True)
    ) / len(before[2])
    assert average_difference < 1.0

def test_real_pdf_fixture_keeps_first_page_visual_and_clears_rotation(
    tmp_path: Path,
) -> None:
    fixture = Path(__file__).parents[1] / "testFile" / "20260722.pdf"
    if not fixture.exists():
        pytest.skip("真实 PDF 测试文件不存在")

    service = PdfProcessingService()
    source_info = service.inspect(fixture)
    assert source_info.pages[0].rotation == 270
    assert source_info.pages[0].width == pytest.approx(841.92)
    assert source_info.pages[0].height == pytest.approx(595.2)
    assert source_info.has_digital_signatures
    assert len(source_info.signed_signatures) == 1
    assert source_info.signed_signatures[0].page_number == 1

    result = service.process_file(fixture, output_dir=tmp_path)
    output_reader = PdfReader(str(result.output_path), strict=False)
    output_page = output_reader.pages[0]

    assert result.total_pages == 397
    assert 1 in result.processed_pages
    assert int(output_page.rotation or 0) == 0
    assert float(output_page.mediabox.width) == pytest.approx(595.2)
    assert float(output_page.mediabox.height) == pytest.approx(841.92)
    assert not [page for page in output_reader.pages if page.rotation]
    assert any("第 1 页" in warning for warning in result.warnings)

    before = _render_first_page(fixture)
    after = _render_first_page(result.output_path)
    assert before[:2] == after[:2]
    average_difference = sum(
        abs(left - right) for left, right in zip(before[2], after[2], strict=True)
    ) / len(before[2])
    assert average_difference < 1.0


def test_inspect_detects_standard_signed_signature(tmp_path: Path) -> None:
    input_path = create_test_pdf(
        tmp_path / "已签名.pdf",
        (270,),
        signed=True,
    )

    info = PdfProcessingService().inspect(input_path)

    assert info.has_digital_signatures
    assert len(info.signatures) == 1
    assert len(info.signed_signatures) == 1
    signature = info.signed_signatures[0]
    assert signature.field_name == "test_signature"
    assert signature.page_number == 1
    assert signature.filter_name == "/Adobe.PPKLite"
    assert signature.subfilter == "/adbe.pkcs7.detached"
    assert signature.has_byte_range
    assert signature.contents_length > 0


def test_empty_signature_field_is_not_treated_as_signed(tmp_path: Path) -> None:
    input_path = create_test_pdf(
        tmp_path / "空签名框.pdf",
        (0,),
        empty_signature_field=True,
    )

    info = PdfProcessingService().inspect(input_path)

    assert len(info.signatures) == 1
    assert not info.has_digital_signatures
    assert info.signed_signatures == ()
