"""PDF 处理引擎接口。"""

from pathlib import Path
from typing import Protocol

from adjust_pdf.models import (
    DocumentInfo,
    ProcessOptions,
    ProcessResult,
    StructureRepairResult,
)


class PdfEngine(Protocol):
    """PDF 引擎需要实现的最小接口。"""

    def inspect(self, input_path: Path) -> DocumentInfo:
        """检查 PDF 页面信息，但不修改文件。"""
        ...

    def process(
        self,
        input_path: Path,
        output_path: Path,
        options: ProcessOptions,
    ) -> ProcessResult:
        """处理 PDF 并生成新文件。"""
        ...

    def repair_structure(
        self,
        input_path: Path,
        output_path: Path,
    ) -> StructureRepairResult:
        """在确认无签章后重建 PDF 结构并生成新文件。"""
        ...
