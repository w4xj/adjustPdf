"""验证 PyInstaller 生成的 EXE 可以在命令行模式处理 PDF。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject, NumberObject


def create_sample(path: Path) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=100)
    page[NameObject("/Rotate")] = NumberObject(270)

    content = DecodedStreamObject()
    content.set_data(b"q 1 0 0 rg 20 20 60 30 re f Q")
    page[NameObject("/Contents")] = writer._add_object(content)

    with path.open("wb") as file:
        writer.write(file)


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：smoke_test_exe.py <exe路径>")
        return 2

    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        print(f"EXE 不存在：{executable}")
        return 2

    with tempfile.TemporaryDirectory(prefix="adjust-pdf-smoke-") as temp:
        directory = Path(temp)
        input_path = directory / "冒烟测试.pdf"
        create_sample(input_path)

        completed = subprocess.run(
            [
                str(executable),
                "--cli",
                str(input_path),
                "--output-dir",
                str(directory),
            ],
            check=False,
            timeout=60,
        )
        if completed.returncode != 0:
            print(f"EXE 返回错误码：{completed.returncode}")
            return 1

        outputs = list(directory.glob("冒烟测试_旋转已固化*.pdf"))
        if len(outputs) != 1:
            print(f"没有找到唯一的输出文件，实际找到：{outputs}")
            return 1

        reader = PdfReader(str(outputs[0]))
        page = reader.pages[0]
        if int(page.rotation or 0) != 0:
            print("输出页面的 Rotate 没有归零。")
            return 1
        if float(page.mediabox.width) != 100:
            print("输出页面宽度不正确。")
            return 1
        if float(page.mediabox.height) != 200:
            print("输出页面高度不正确。")
            return 1

    print("EXE 冒烟测试通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
