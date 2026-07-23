"""使用真实 PDF 验证 EXE 的按页码处理功能。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import fitz
from pypdf import PdfReader


SELECTED_TEXT = "1,4-6,8"
SELECTED_PAGES = {1, 4, 5, 6, 8}


def render_page(path: Path, page_number: int) -> tuple[int, int, bytes]:
    document = fitz.open(path)
    try:
        pixmap = document[page_number - 1].get_pixmap(alpha=False)
        return pixmap.width, pixmap.height, pixmap.samples
    finally:
        document.close()


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print("用法：verify_page_selection_exe.py <exe路径> [PDF样本路径]")
        return 2

    executable = Path(sys.argv[1]).resolve()
    fixture = (
        Path(sys.argv[2]).resolve()
        if len(sys.argv) == 3
        else Path(__file__).parents[1] / "testFile" / "20260722.pdf"
    )
    if not executable.is_file() or not fixture.is_file():
        print(f"缺少 EXE 或 PDF：{executable}；{fixture}")
        return 2

    source_reader = PdfReader(str(fixture), strict=False)
    source_rotations = [int(page.rotation or 0) for page in source_reader.pages]
    before = render_page(fixture, 1)

    with tempfile.TemporaryDirectory(prefix="adjust-pdf-selected-") as temp:
        output_directory = Path(temp)
        completed = subprocess.run(
            [
                str(executable),
                "--cli",
                str(fixture),
                "--mode",
                "selected",
                "--pages",
                SELECTED_TEXT,
                "--allow-signed",
                "--output-dir",
                str(output_directory),
            ],
            check=False,
            timeout=180,
        )
        if completed.returncode != 0:
            print(f"EXE 返回错误码：{completed.returncode}")
            return 1

        outputs = list(output_directory.glob("20260722_旋转已固化*.pdf"))
        if len(outputs) != 1:
            print(f"没有找到唯一输出文件：{outputs}")
            return 1

        output_reader = PdfReader(str(outputs[0]), strict=False)
        output_rotations = [int(page.rotation or 0) for page in output_reader.pages]
        expected_rotations = [
            0 if index in SELECTED_PAGES and rotation != 0 else rotation
            for index, rotation in enumerate(source_rotations, start=1)
        ]
        if output_rotations != expected_rotations:
            changed = [
                index
                for index, (actual, expected) in enumerate(
                    zip(output_rotations, expected_rotations, strict=True),
                    start=1,
                )
                if actual != expected
            ]
            print(f"按页码处理结果不正确，异常页码：{changed}")
            return 1

        after = render_page(outputs[0], 1)
        if before[:2] != after[:2]:
            print("第一页处理前后的渲染尺寸不同。")
            return 1
        average_difference = sum(
            abs(left - right)
            for left, right in zip(before[2], after[2], strict=True)
        ) / len(before[2])
        if average_difference >= 1.0:
            print(f"第一页视觉差异过大：{average_difference}")
            return 1

    remaining = sum(1 for rotation in expected_rotations if rotation != 0)
    print(
        f"按页码 EXE 回归测试通过：{SELECTED_TEXT}；"
        f"目标旋转页已归零，仍保留 {remaining} 个未选中的旋转页。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
