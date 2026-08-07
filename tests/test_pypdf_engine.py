"""pypdf 处理引擎测试。"""

import re
from pathlib import Path

import fitz
import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import NameObject

from adjust_pdf.engines.pypdf_engine import PypdfEngine
from adjust_pdf.exceptions import EncryptedPdfError, InvalidInputError, SignedPdfError
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


def _append_ambiguous_xref_revision(path: Path) -> None:
    """Append the two malformed xref patterns found in the reported PDF."""
    reader = PdfReader(str(path), strict=False)
    root_reference = reader.trailer.raw_get("/Root")
    root = root_reference.get_object()
    pages_reference = root.raw_get("/Pages")
    page_reference = reader.pages[0].indirect_reference
    references = (root_reference, pages_reference, page_reference)

    correct_offsets = {
        (reference.generation, reference.idnum): reader.xref[reference.generation][reference.idnum]
        for reference in references
    }
    original = path.read_bytes()
    original_startxref = int(re.findall(rb"startxref\s+(\d+)", original)[-1])

    chunks = [original]
    current_offset = len(original)
    wrong_offsets: dict[tuple[int, int], int] = {}
    wrong_objects = {
        root_reference.idnum: b"<< /Type /Annot /Subtype /Stamp >>",
        pages_reference.idnum: b"<< /Type /XObject /Subtype /Form >>",
        page_reference.idnum: b"<< /Type /ExtGState >>",
    }
    for reference in references:
        key = (reference.generation, reference.idnum)
        wrong_offsets[key] = current_offset
        object_bytes = (
            f"\n{reference.idnum} {reference.generation} obj\n".encode()
            + wrong_objects[reference.idnum]
            + b"\nendobj\n"
        )
        chunks.append(object_bytes)
        current_offset += len(object_bytes)

    empty_xref_offset = current_offset
    size = max(int(reader.trailer.get("/Size", 0)), max(ref.idnum for ref in references) + 1)
    empty_xref = (
        "xref\n"
        "trailer\n"
        f"<< /Root {root_reference.idnum} {root_reference.generation} R "
        f"/Size {size} /Prev {original_startxref} >>\n"
        f"startxref\n{empty_xref_offset}\n%%EOF\n"
    ).encode()
    chunks.append(empty_xref)
    current_offset += len(empty_xref)

    latest_xref_offset = current_offset
    latest_xref_parts = [b"xref\n"]
    for reference in references:
        key = (reference.generation, reference.idnum)
        latest_xref_parts.extend(
            (
                f"{reference.idnum} 1\n".encode(),
                f"{wrong_offsets[key]:010d} {reference.generation:05d} n \n".encode(),
                f"{reference.idnum} 1\n".encode(),
                f"{correct_offsets[key]:010d} {reference.generation:05d} n \n".encode(),
            )
        )
    latest_xref_parts.append(
        (
            "trailer\n"
            f"<< /Root {root_reference.idnum} {root_reference.generation} R "
            f"/Size {size} /Prev {empty_xref_offset} >>\n"
            f"startxref\n{latest_xref_offset}\n%%EOF\n"
        ).encode()
    )
    chunks.extend(latest_xref_parts)
    path.write_bytes(b"".join(chunks))


def test_inspect_recovers_empty_and_ambiguous_xref_tables(tmp_path: Path) -> None:
    input_path = create_test_pdf(tmp_path / "malformed-xref.pdf", (90,))
    _append_ambiguous_xref_revision(input_path)

    with pytest.raises(PdfReadError, match="Could not read Boolean object"):
        PdfReader(str(input_path), strict=False)

    info = PdfProcessingService().inspect(input_path)

    assert info.page_count == 1
    assert info.pages[0].width == pytest.approx(200)
    assert info.pages[0].height == pytest.approx(100)
    assert info.pages[0].rotation == 90


def test_reported_malformed_xref_fixture_can_be_inspected() -> None:
    fixture = Path(__file__).parents[1] / "testFile" / "2084826826567786498_1.pdf"
    if not fixture.exists():
        pytest.skip("reported malformed-xref PDF fixture is not available")

    info = PdfProcessingService().inspect(fixture)

    assert info.page_count == 169
    assert len(info.pages) == 169
    assert all(page.width == pytest.approx(595.276) for page in info.pages)
    assert all(page.height == pytest.approx(841.89) for page in info.pages)
    assert info.rotated_pages == ()
    assert len(info.annotation_pages) == 169
    assert info.has_digital_signatures


def test_repair_structure_rewrites_unsigned_malformed_pdf_without_content_changes(
    tmp_path: Path,
) -> None:
    input_path = create_test_pdf(
        tmp_path / "repair-source.pdf",
        (90, 0),
        annotation_pages=(1,),
    )
    original_reader = PdfReader(str(input_path), strict=False)
    original_contents = tuple(page.get_contents().get_data() for page in original_reader.pages)
    _append_ambiguous_xref_revision(input_path)
    malformed_bytes = input_path.read_bytes()

    result = PdfProcessingService().repair_structure(input_path, output_dir=tmp_path / "out")

    assert input_path.read_bytes() == malformed_bytes
    assert result.output_path.name == "repair-source_结构已修复.pdf"
    assert result.page_count == 2
    repaired = PdfReader(str(result.output_path), strict=False)
    assert len(repaired.pages) == 2
    assert [int(page.rotation or 0) for page in repaired.pages] == [90, 0]
    assert [float(page.mediabox.width) for page in repaired.pages] == [200, 200]
    assert [float(page.mediabox.height) for page in repaired.pages] == [100, 100]
    assert tuple(page.get_contents().get_data() for page in repaired.pages) == original_contents
    assert repaired.pages[0].get("/Annots") is not None


def test_repair_structure_strictly_rejects_signed_malformed_pdf(tmp_path: Path) -> None:
    input_path = create_test_pdf(tmp_path / "signed-malformed.pdf", (0,), signed=True)
    _append_ambiguous_xref_revision(input_path)

    with pytest.raises(SignedPdfError, match="禁止修复"):
        PdfProcessingService().repair_structure(input_path)

    assert not (tmp_path / "signed-malformed_结构已修复.pdf").exists()


def test_repair_structure_rejects_pdf_without_target_xref_problem(tmp_path: Path) -> None:
    input_path = create_test_pdf(tmp_path / "normal.pdf", (0,))

    with pytest.raises(InvalidInputError, match="未检测到需要修复"):
        PdfProcessingService().repair_structure(input_path)

    assert not (tmp_path / "normal_结构已修复.pdf").exists()


def test_repair_structure_rejects_stamp_annotation(tmp_path: Path) -> None:
    input_path = create_test_pdf(
        tmp_path / "stamp-malformed.pdf",
        (0,),
        annotation_pages=(1,),
    )
    reader = PdfReader(str(input_path), strict=False)
    writer = PdfWriter(clone_from=reader)
    annotation = writer.pages[0]["/Annots"][0].get_object()
    annotation[NameObject("/Subtype")] = NameObject("/Stamp")
    writer.write(input_path)
    _append_ambiguous_xref_revision(input_path)

    with pytest.raises(SignedPdfError, match="Stamp 印章批注"):
        PdfProcessingService().repair_structure(input_path)

    assert not (tmp_path / "stamp-malformed_结构已修复.pdf").exists()
