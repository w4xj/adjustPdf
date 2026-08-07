"""应用使用的数据模型。"""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class PageSelectionMode(StrEnum):
    """决定哪些页面需要固化旋转。"""

    ROTATED = "rotated"
    FIRST = "first"
    SELECTED = "selected"


@dataclass(frozen=True)
class ProcessOptions:
    """单个 PDF 的处理选项。"""

    page_mode: PageSelectionMode = PageSelectionMode.ROTATED
    selected_pages: tuple[int, ...] = ()
    preserve_metadata: bool = True


@dataclass(frozen=True)
class PageInfo:
    """单页的检查结果，页码从 1 开始。"""

    page_number: int
    width: float
    height: float
    rotation: int
    has_annotations: bool


@dataclass(frozen=True)
class SignatureInfo:
    """标准 PDF 数字签名字段的结构信息。"""

    field_name: str
    page_number: int | None
    filter_name: str | None
    subfilter: str | None
    reason: str | None
    location: str | None
    signing_time: str | None
    has_byte_range: bool
    contents_length: int
    # PKCS7 证书解析信息（同一签署事件内字段共享）
    signer_name: str | None = None
    cert_serial_hex: str | None = None
    cert_issuer_str: str | None = None
    cert_valid_from: str | None = None
    cert_valid_to: str | None = None
    has_timestamp: bool = False

    @property
    def is_signed(self) -> bool:
        """是否存在已写入的签名内容。"""
        return self.has_byte_range and self.contents_length > 0


@dataclass(frozen=True)
class DocumentInfo:
    """PDF 文档的检查结果。"""

    path: Path
    page_count: int
    pages: tuple[PageInfo, ...]
    signatures: tuple[SignatureInfo, ...] = ()

    @property
    def signed_signatures(self) -> tuple[SignatureInfo, ...]:
        return tuple(signature for signature in self.signatures if signature.is_signed)

    @property
    def has_digital_signatures(self) -> bool:
        return bool(self.signed_signatures)

    @property
    def rotated_pages(self) -> tuple[int, ...]:
        return tuple(page.page_number for page in self.pages if page.rotation != 0)

    @property
    def annotation_pages(self) -> tuple[int, ...]:
        return tuple(page.page_number for page in self.pages if page.has_annotations)


@dataclass
class ProcessResult:
    """一次 PDF 处理的结果。"""

    input_path: Path
    output_path: Path
    total_pages: int
    processed_pages: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def processed_count(self) -> int:
        return len(self.processed_pages)


@dataclass
class StructureRepairResult:
    """PDF 结构修复操作的结果。"""

    input_path: Path
    output_path: Path
    page_count: int
    warnings: list[str] = field(default_factory=list)
