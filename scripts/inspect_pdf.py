"""用可读方式检查 PDF 的文件头、对象、页面和内容流。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from pypdf import PdfReader


def format_value(value: Any) -> str:
    text = str(value)
    return text if len(text) <= 240 else text[:237] + "..."


def print_raw_summary(path: Path) -> None:
    raw = path.read_bytes()
    print("[原始文件]")
    print(f"文件大小：{len(raw):,} bytes")
    print(f"文件头：{raw[:12]!r}")
    print("关键字出现次数（仅供参考，不代表对象数量）：")
    for marker in (
        b"obj",
        b"endobj",
        b"stream",
        b"endstream",
        b"xref",
        b"trailer",
        b"/ObjStm",
        b"/Type /Page",
        b"/Rotate",
        b"/Contents",
        b"/Annots",
    ):
        print(f"  {marker.decode('latin1')}: {raw.count(marker)}")

    startxref = raw.rfind(b"startxref")
    if startxref >= 0:
        tail = raw[startxref:].decode("latin1", errors="replace")
        print("文件尾部：")
        print(tail[:300].rstrip())


def print_page_info(reader: PdfReader, page_number: int) -> None:
    page = reader.pages[page_number - 1]
    print(f"[第 {page_number} 页]")
    print(f"对象引用：{page.indirect_reference}")
    print(f"页面字典键：{list(page.keys())}")
    print(f"有效 Rotate：{int(page.rotation or 0)}")
    print(f"MediaBox：{format_value(page.mediabox)}")
    print(f"CropBox：{format_value(page.cropbox)}")
    print(f"Parent：{format_value(page.get('/Parent'))}")
    print(f"Contents：{format_value(page.get('/Contents'))}")
    print(f"Resources：{format_value(page.get('/Resources'))}")

    annotations = page.get("/Annots")
    if annotations:
        print(f"Annots：{len(annotations)} 个")
        for index, annotation in enumerate(annotations, start=1):
            print(f"  Annots[{index}]：{format_value(annotation.get_object())}")
    else:
        print("Annots：无")

    content = page.get_contents()
    if content is None:
        print("解压后的 Contents：无")
    else:
        content_data = content.get_data()
        print(f"解压后的 Contents 长度：{len(content_data)} bytes")
        print("解压后的 Contents 前 1,000 字节：")
        print(content_data[:1000].decode("latin1", errors="replace"))

    resources = page.get("/Resources")
    if resources:
        resources = resources.get_object()
        xobjects = resources.get("/XObject")
        if xobjects:
            print("XObject：")
            for name, reference in xobjects.get_object().items():
                obj = reference.get_object()
                print(
                    f"  {name} -> {reference}; "
                    f"Type={obj.get('/Type')}; "
                    f"Subtype={obj.get('/Subtype')}; "
                    f"Width={obj.get('/Width')}; "
                    f"Height={obj.get('/Height')}; "
                    f"Filter={obj.get('/Filter')}"
                )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="以适合初学者阅读的方式检查 PDF 结构。"
    )
    parser.add_argument("pdf", type=Path, help="要检查的 PDF 文件")
    parser.add_argument(
        "--page",
        type=int,
        default=1,
        help="要展开显示的页码，默认是第 1 页",
    )
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    path = args.pdf.resolve()
    if not path.is_file():
        print(f"文件不存在：{path}")
        return 2
    if args.page < 1:
        print("页码必须从 1 开始。")
        return 2

    print_raw_summary(path)
    reader = PdfReader(str(path), strict=False)
    print("\n[文档结构]")
    header = reader.pdf_header
    if isinstance(header, bytes):
        header = header.decode("latin1", errors="replace")
    print(f"PDF 版本：{header}")
    print(f"页数：{len(reader.pages)}")
    print(f"Trailer 键：{list(reader.trailer.keys())}")
    root = reader.trailer.get("/Root")
    print(f"Root：{root}")
    if root:
        root_object = root.get_object()
        print(f"Catalog 键：{list(root_object.keys())}")
        pages = root_object.get("/Pages")
        if pages:
            pages_object = pages.get_object()
            print(f"Pages：{pages}")
            print(f"Pages 键：{list(pages_object.keys())}")
            print(f"Pages Count：{pages_object.get('/Count')}")

    if args.page > len(reader.pages):
        print(f"页码超出范围，最大页码是 {len(reader.pages)}。")
        return 2

    print()
    print_page_info(reader, args.page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
