"""使用用户提供的真实 PDF 样本验证打包后的 EXE。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import fitz
from pypdf import PdfReader


def render_first_page(path: Path) -> tuple[int, int, bytes]:
    document = fitz.open(path)
    try:
        pixmap = document[0].get_pixmap(alpha=False)
        return pixmap.width, pixmap.height, pixmap.samples
    finally:
        document.close()


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print("用法：verify_real_fixture.py <exe路径> [PDF样本路径]")
        return 2

    executable = Path(sys.argv[1]).resolve()
    fixture = (
        Path(sys.argv[2]).resolve()
        if len(sys.argv) == 3
        else Path(__file__).parents[1] / "testFile" / "20260722.pdf"
    )

    if not executable.is_file():
        print(f"EXE 不存在：{executable}")
        return 2
    if not fixture.is_file():
        print(f"真实 PDF 样本不存在，跳过：{fixture}")
        return 0

    source_reader = PdfReader(str(fixture), strict=False)
    source_page = source_reader.pages[0]
    if int(source_page.rotation or 0) != 270:
        print(f"源文件第一页 Rotate 不是 270：{source_page.rotation}")
        return 1

    before = render_first_page(fixture)

    with tempfile.TemporaryDirectory(prefix="adjust-pdf-real-") as temp:
        output_directory = Path(temp)
        completed = subprocess.run(
            [
                str(executable),
                "--cli",
                str(fixture),
                "--mode",
                "rotated",
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
        output_page = output_reader.pages[0]
        if len(output_reader.pages) != len(source_reader.pages):
            print("处理前后 PDF 页数不一致。")
            return 1
        if int(output_page.rotation or 0) != 0:
            print(f"输出第一页 Rotate 不是 0：{output_page.rotation}")
            return 1
        if abs(float(output_page.mediabox.width) - 595.2) > 0.01:
            print("输出第一页宽度不正确。")
            return 1
        if abs(float(output_page.mediabox.height) - 841.92) > 0.01:
            print("输出第一页高度不正确。")
            return 1
        if any(page.rotation for page in output_reader.pages):
            print("输出 PDF 中仍存在非零旋转页面。")
            return 1

        after = render_first_page(outputs[0])
        if before[:2] != after[:2]:
            print(f"处理前后渲染尺寸不同：{before[:2]} != {after[:2]}")
            return 1

        average_difference = sum(
            abs(left - right)
            for left, right in zip(before[2], after[2], strict=True)
        ) / len(before[2])
        if average_difference >= 1.0:
            print(f"处理前后视觉差异过大：{average_difference}")
            return 1

    print(
        "真实 PDF 回归测试通过："
        "第一页显示尺寸保持不变，Rotate=270 已固化为 Rotate=0。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
