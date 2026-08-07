"""输入输出路径处理。"""

from pathlib import Path

from adjust_pdf.exceptions import InvalidInputError

OUTPUT_SUFFIX = "_旋转已固化"
REPAIR_OUTPUT_SUFFIX = "_结构已修复"


def validate_input_path(path: Path) -> Path:
    """验证输入路径并返回绝对路径。"""
    resolved = path.expanduser().resolve()

    if not resolved.exists():
        raise InvalidInputError(f"文件不存在：{resolved}")
    if not resolved.is_file():
        raise InvalidInputError(f"路径不是文件：{resolved}")
    if resolved.suffix.lower() != ".pdf":
        raise InvalidInputError(f"请选择 PDF 文件：{resolved.name}")

    return resolved


def make_output_path(
    input_path: Path,
    output_dir: Path | None = None,
) -> Path:
    """生成旋转固化输出路径。"""
    return _make_suffixed_output_path(input_path, OUTPUT_SUFFIX, output_dir)


def make_repair_output_path(
    input_path: Path,
    output_dir: Path | None = None,
) -> Path:
    """生成 PDF 结构修复输出路径。"""
    return _make_suffixed_output_path(input_path, REPAIR_OUTPUT_SUFFIX, output_dir)


def _make_suffixed_output_path(
    input_path: Path,
    suffix: str,
    output_dir: Path | None,
) -> Path:
    """按指定后缀生成不覆盖现有文件的输出路径。"""
    input_path = input_path.resolve()
    directory = output_dir.expanduser().resolve() if output_dir is not None else input_path.parent

    if directory.exists() and not directory.is_dir():
        raise InvalidInputError(f"输出位置不是文件夹：{directory}")

    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f"{input_path.stem}{suffix}.pdf"
    number = 2

    while candidate.exists() or candidate.resolve() == input_path:
        candidate = directory / f"{input_path.stem}{suffix}_{number}.pdf"
        number += 1

    return candidate
