"""面向 GUI 和命令行的应用服务。"""

from pathlib import Path

from adjust_pdf.engines.base import PdfEngine
from adjust_pdf.engines.pypdf_engine import PypdfEngine
from adjust_pdf.logging_config import get_logger
from adjust_pdf.models import DocumentInfo, ProcessOptions, ProcessResult, StructureRepairResult
from adjust_pdf.paths import make_output_path, make_repair_output_path, validate_input_path


class PdfProcessingService:
    """协调路径验证、输出命名和 PDF 引擎。"""

    def __init__(self, engine: PdfEngine | None = None) -> None:
        self.engine = engine or PypdfEngine()
        self.logger = get_logger("service")

    def inspect(self, input_path: Path) -> DocumentInfo:
        path = validate_input_path(input_path)
        self.logger.info("检查 PDF：%s", path)
        return self.engine.inspect(path)

    def process_file(
        self,
        input_path: Path,
        options: ProcessOptions | None = None,
        output_dir: Path | None = None,
    ) -> ProcessResult:
        path = validate_input_path(input_path)
        output_path = make_output_path(path, output_dir)
        actual_options = options or ProcessOptions()

        self.logger.info(
            "开始处理 PDF：input=%s output=%s mode=%s",
            path,
            output_path,
            actual_options.page_mode.value,
        )
        result = self.engine.process(path, output_path, actual_options)
        self.logger.info(
            "处理完成：output=%s processed_pages=%s warnings=%s",
            result.output_path,
            result.processed_pages,
            len(result.warnings),
        )
        return result

    def repair_structure(
        self,
        input_path: Path,
        output_dir: Path | None = None,
    ) -> StructureRepairResult:
        """对无签章的异常 PDF 重建交叉引用和对象结构。"""
        path = validate_input_path(input_path)
        output_path = make_repair_output_path(path, output_dir)
        self.logger.info("开始修复 PDF 结构：input=%s output=%s", path, output_path)
        result = self.engine.repair_structure(path, output_path)
        self.logger.info(
            "PDF 结构修复完成：output=%s pages=%s",
            result.output_path,
            result.page_count,
        )
        return result
