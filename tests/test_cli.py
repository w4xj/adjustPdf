"""命令行参数测试。"""

import pytest

from adjust_pdf.cli import build_parser, parse_page_numbers


def test_parse_page_numbers() -> None:
    assert parse_page_numbers("1,3-5,8") == (1, 3, 4, 5, 8)


def test_parse_page_numbers_rejects_invalid_range() -> None:
    with pytest.raises(Exception):
        parse_page_numbers("5-3")


def test_cli_default_mode_is_first_page() -> None:
    args = build_parser().parse_args(["input.pdf"])
    assert args.mode == "first"