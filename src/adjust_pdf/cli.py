"""命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from adjust_pdf.exceptions import AdjustPdfError
from adjust_pdf.logging_config import configure_logging
from adjust_pdf.models import PageSelectionMode, ProcessOptions
from adjust_pdf.page_ranges import parse_page_numbers as parse_page_range_text
from adjust_pdf.service import PdfProcessingService
from adjust_pdf.signature_report import format_signature_report


def _output_stream() -> TextIO | None:
    return sys.stdout


def safe_print(message: str = "", *, error: bool = False) -> None:
    stream = sys.stderr if error else _output_stream()
    if stream is not None:
        print(message, file=stream)


def parse_page_numbers(value: str) -> tuple[int, ...]:
    """argparse 使用的页码解析包装。"""
    try:
        return parse_page_range_text(value)
    except AdjustPdfError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adjust-pdf-cli",
        description="将 PDF 页面旋转属性固化到页面内容中。",
    )
    parser.add_argument("files", nargs="+", type=Path, help="一个或多个 PDF 文件")
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="只检查 PDF，不生成新文件",
    )
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in PageSelectionMode],
        default=PageSelectionMode.FIRST.value,
        help="rotated=所有旋转页，first=仅第一页，selected=指定页",
    )
    parser.add_argument(
        "--pages",
        type=parse_page_numbers,
        default=(),
        help="指定页码，例如 1,3-5；需要配合 --mode selected",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="输出目录；默认与输入文件相同",
    )
    parser.add_argument(
        "--allow-signed",
        action="store_true",
        help="确认承担签名失效风险后，允许处理已签名 PDF",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    mode = PageSelectionMode(args.mode)
    if mode is PageSelectionMode.SELECTED and not args.pages:
        parser.error("--mode selected 必须同时提供 --pages。")

    service = PdfProcessingService()
    exit_code = 0

    for input_path in args.files:
        try:
            if args.inspect:
                info = service.inspect(input_path)
                safe_print(f"文件：{info.path}")
                safe_print(f"总页数：{info.page_count}")
                safe_print(
                    "旋转页："
                    + ("、".join(map(str, info.rotated_pages)) or "无")
                )
                safe_print(
                    "批注页："
                    + ("、".join(map(str, info.annotation_pages)) or "无")
                )
                safe_print(format_signature_report(info))
                for page in info.pages:
                    safe_print(
                        f"  第 {page.page_number} 页："
                        f"{page.width:.2f} × {page.height:.2f}，"
                        f"Rotate={page.rotation}"
                    )
                continue

            info = service.inspect(input_path)
            if info.has_digital_signatures and not args.allow_signed:
                safe_print(
                    f"处理失败：{input_path}：检测到标准数字签名或电子签章结构。"
                    "为避免签名失效，命令行模式默认拒绝处理；"
                    "如已确认风险，请添加 --allow-signed。",
                    error=True,
                )
                exit_code = 1
                continue

            result = service.process_file(
                input_path=input_path,
                output_dir=args.output_dir,
                options=ProcessOptions(
                    page_mode=mode,
                    selected_pages=args.pages,
                ),
            )
            safe_print(f"处理完成：{result.output_path}")
            safe_print(
                "已处理页面："
                + ("、".join(map(str, result.processed_pages)) or "无")
            )
            for warning in result.warnings:
                safe_print(f"警告：{warning}")
        except AdjustPdfError as error:
            safe_print(f"处理失败：{input_path}：{error}", error=True)
            exit_code = 1
        except Exception as error:
            safe_print(f"发生未预期错误：{input_path}：{error}", error=True)
            exit_code = 2

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
