"""页码列表和范围的解析。"""

from adjust_pdf.exceptions import InvalidInputError


def parse_page_numbers(value: str) -> tuple[int, ...]:
    """将 ``1,5-9,12`` 解析为去重并排序后的页码元组。"""
    text = value.strip()
    if not text:
        raise InvalidInputError("请输入页码，例如：1,5-9,12。")
    if "，" in text:
        raise InvalidInputError("请使用英文逗号 , 分隔页码，例如：1,5-9,12。")

    pages: set[int] = set()
    try:
        for part in text.split(","):
            part = part.strip()
            if not part:
                raise ValueError

            if "-" in part:
                if part.count("-") != 1:
                    raise ValueError
                start_text, end_text = part.split("-", maxsplit=1)
                start = int(start_text.strip())
                end = int(end_text.strip())
                if start < 1 or end < start:
                    raise ValueError
                pages.update(range(start, end + 1))
            else:
                page = int(part)
                if page < 1:
                    raise ValueError
                pages.add(page)
    except ValueError as error:
        raise InvalidInputError(
            "页码格式错误，请使用类似 1,5-9,12 的格式；页码必须从 1 开始。"
        ) from error

    if not pages:
        raise InvalidInputError("请输入至少一个有效页码。")
    return tuple(sorted(pages))
