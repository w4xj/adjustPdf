"""输出路径测试。"""

from pathlib import Path

import pytest

from adjust_pdf.exceptions import InvalidInputError
from adjust_pdf.paths import make_output_path, validate_input_path


def test_validate_input_path_accepts_chinese_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "聊天记录.pdf"
    pdf_path.write_bytes(b"%PDF-placeholder")

    assert validate_input_path(pdf_path) == pdf_path.resolve()


def test_validate_input_path_rejects_non_pdf(tmp_path: Path) -> None:
    text_path = tmp_path / "说明.txt"
    text_path.write_text("test", encoding="utf-8")

    with pytest.raises(InvalidInputError, match="请选择 PDF"):
        validate_input_path(text_path)


def test_make_output_path_avoids_overwrite(tmp_path: Path) -> None:
    input_path = tmp_path / "聊天记录.pdf"
    input_path.write_bytes(b"input")
    first_output = tmp_path / "聊天记录_旋转已固化.pdf"
    first_output.write_bytes(b"existing")

    output_path = make_output_path(input_path)

    assert output_path.name == "聊天记录_旋转已固化_2.pdf"
    assert first_output.read_bytes() == b"existing"
