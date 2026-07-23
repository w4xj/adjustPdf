"""页码范围解析测试。"""

import pytest

from adjust_pdf.exceptions import InvalidInputError
from adjust_pdf.page_ranges import parse_page_numbers


def test_parse_page_numbers_supports_list_and_ranges() -> None:
    assert parse_page_numbers("1,5-9,12") == (1, 5, 6, 7, 8, 9, 12)


def test_parse_page_numbers_strips_spaces_and_deduplicates() -> None:
    assert parse_page_numbers(" 1, 3-5, 5, 3 ") == (1, 3, 4, 5)


@pytest.mark.parametrize(
    "value",
    ["", "0", "1,", "5-3", "1--3", "第1页", "1，5-9"],
)
def test_parse_page_numbers_rejects_invalid_input(value: str) -> None:
    with pytest.raises(InvalidInputError):
        parse_page_numbers(value)
