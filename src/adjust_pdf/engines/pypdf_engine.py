"""基于 pypdf 的 PDF 旋转固化实现。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from adjust_pdf.exceptions import (
    EncryptedPdfError,
    InvalidInputError,
    InvalidPdfError,
    OutputWriteError,
)
from adjust_pdf.models import (
    DocumentInfo,
    PageInfo,
    PageSelectionMode,
    ProcessOptions,
    ProcessResult,
    SignatureInfo,
)


class PypdfEngine:
    """使用 pypdf 检查并固化 PDF 页面旋转。"""

    def inspect(self, input_path: Path) -> DocumentInfo:
        reader = self._open_reader(input_path)
        pages = tuple(
            PageInfo(
                page_number=index,
                width=float(page.mediabox.width),
                height=float(page.mediabox.height),
                rotation=int(page.rotation or 0),
                has_annotations=self._has_annotations(page),
            )
            for index, page in enumerate(reader.pages, start=1)
        )
        return DocumentInfo(
            path=input_path,
            page_count=len(pages),
            pages=pages,
            signatures=self._inspect_signatures(reader),
        )

    @classmethod
    def _inspect_signatures(cls, reader: PdfReader) -> tuple[SignatureInfo, ...]:
        """检查标准 PDF 数字签名字段，不验证证书和密码学有效性。"""
        page_numbers: dict[int, int] = {}
        for page_number, page in enumerate(reader.pages, start=1):
            reference = page.indirect_reference
            if reference is not None:
                page_numbers[reference.idnum] = page_number

        root_reference = reader.trailer.get("/Root")
        if root_reference is None:
            return ()
        root = root_reference.get_object()
        results: list[SignatureInfo] = []

        acroform_reference = root.get("/AcroForm")
        if acroform_reference is not None:
            acroform = acroform_reference.get_object()
            fields = acroform.get("/Fields", [])
            for field in fields:
                cls._walk_signature_field(
                    field_reference=field,
                    page_numbers=page_numbers,
                    results=results,
                )

        permissions = root.get("/Perms")
        if permissions is not None:
            permissions = permissions.get_object()
            doc_mdp = permissions.get("/DocMDP")
            if doc_mdp is not None:
                cls._append_signature_info(
                    field_name="文档认证签名",
                    field_object=None,
                    value_reference=doc_mdp,
                    page_numbers=page_numbers,
                    results=results,
                )

        return tuple(results)

    @classmethod
    def _walk_signature_field(
        cls,
        field_reference: object,
        page_numbers: dict[int, int],
        results: list[SignatureInfo],
        parent_name: str = "",
        inherited_field_type: object | None = None,
    ) -> None:
        field = field_reference.get_object()
        field_type = field.get("/FT", inherited_field_type)
        local_name = cls._text_value(field.get("/T"))
        field_name = ".".join(
            part for part in (parent_name, local_name) if part
        ) or "未命名签名字段"

        if field_type == "/Sig":
            cls._append_signature_info(
                field_name=field_name,
                field_object=field,
                value_reference=field.get("/V"),
                page_numbers=page_numbers,
                results=results,
            )

        children = field.get("/Kids", [])
        for child in children:
            cls._walk_signature_field(
                field_reference=child,
                page_numbers=page_numbers,
                results=results,
                parent_name=field_name,
                inherited_field_type=field_type,
            )

    @classmethod
    def _append_signature_info(
        cls,
        field_name: str,
        field_object: object | None,
        value_reference: object | None,
        page_numbers: dict[int, int],
        results: list[SignatureInfo],
    ) -> None:
        page_number = cls._page_number_from_field(field_object, page_numbers)
        if value_reference is None:
            results.append(
                SignatureInfo(
                    field_name=field_name,
                    page_number=page_number,
                    filter_name=None,
                    subfilter=None,
                    reason=None,
                    location=None,
                    signing_time=None,
                    has_byte_range=False,
                    contents_length=0,
                )
            )
            return

        value_object = value_reference.get_object()

        contents = value_object.get("/Contents")
        try:
            contents_length = len(contents.original_bytes)
        except AttributeError:
            try:
                contents_length = len(contents) if contents is not None else 0
            except TypeError:
                contents_length = 0

        results.append(
            SignatureInfo(
                field_name=field_name,
                page_number=page_number,
                filter_name=cls._text_value(value_object.get("/Filter")),
                subfilter=cls._text_value(value_object.get("/SubFilter")),
                reason=cls._text_value(value_object.get("/Reason")),
                location=cls._text_value(value_object.get("/Location")),
                signing_time=cls._text_value(value_object.get("/M")),
                has_byte_range=value_object.get("/ByteRange") is not None,
                contents_length=contents_length,
            )
        )

    @staticmethod
    def _page_number_from_field(
        field_object: object | None,
        page_numbers: dict[int, int],
    ) -> int | None:
        if field_object is None:
            return None
        page_reference = field_object.get("/P")  # type: ignore[attr-defined]
        page_id = getattr(page_reference, "idnum", None)
        return page_numbers.get(page_id)

    @staticmethod
    def _text_value(value: object | None) -> str | None:
        if value is None:
            return None
        return str(value)

    def process(
        self,
        input_path: Path,
        output_path: Path,
        options: ProcessOptions,
    ) -> ProcessResult:
        if output_path.exists():
            raise OutputWriteError(f"为避免覆盖文件，输出文件必须不存在：{output_path}")
        if output_path.resolve() == input_path.resolve():
            raise OutputWriteError("输出文件不能与输入文件相同。")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        reader = self._open_reader(input_path)
        writer = PdfWriter(clone_from=reader)
        result = ProcessResult(
            input_path=input_path,
            output_path=output_path,
            total_pages=len(reader.pages),
        )

        selected_pages = set(options.selected_pages)
        if options.page_mode is PageSelectionMode.SELECTED and not selected_pages:
            raise InvalidInputError("选择指定页模式时，必须提供至少一个页码。")

        invalid_pages = sorted(
            page_number
            for page_number in selected_pages
            if page_number < 1 or page_number > len(reader.pages)
        )
        if invalid_pages:
            numbers = "、".join(str(number) for number in invalid_pages)
            raise InvalidInputError(f"页码超出范围：{numbers}")

        # clone_from 会复制完整文档结构，尽量保留书签、附件、表单和文档级信息。
        # 同时，writer.pages 中的页面已经归属于输出文档，可以安全修改页面内容。
        source_pages = list(reader.pages)

        for page_number, (source_page, output_page) in enumerate(
            zip(source_pages, writer.pages, strict=True),
            start=1,
        ):
            rotation = int(output_page.rotation or 0)
            if self._should_process(
                page_number=page_number,
                rotation=rotation,
                options=options,
                selected_pages=selected_pages,
            ):
                if self._has_annotations(source_page):
                    result.warnings.append(
                        f"第 {page_number} 页包含链接、批注或表单区域，"
                        "请在处理后检查其点击位置。"
                    )
                output_page.transfer_rotation_to_content()
                result.processed_pages.append(page_number)

        if not options.preserve_metadata:
            writer.metadata = None

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w+b",
                prefix=f".{output_path.stem}.",
                suffix=".tmp",
                dir=output_path.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                writer.write(temporary_file)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            self._validate_output(
                temporary_path,
                expected_page_count=result.total_pages,
                processed_pages=result.processed_pages,
            )
            os.replace(temporary_path, output_path)
            temporary_path = None
        except OutputWriteError:
            raise
        except OSError as error:
            raise OutputWriteError(
                f"无法写入输出文件：{output_path}。原因：{error}"
            ) from error
        except Exception as error:
            raise OutputWriteError(
                f"生成的 PDF 未通过完整性检查：{error}"
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        return result

    @staticmethod
    def _should_process(
        page_number: int,
        rotation: int,
        options: ProcessOptions,
        selected_pages: set[int],
    ) -> bool:
        if rotation == 0:
            return False
        if options.page_mode is PageSelectionMode.ROTATED:
            return True
        if options.page_mode is PageSelectionMode.FIRST:
            return page_number == 1
        return page_number in selected_pages

    @staticmethod
    def _has_annotations(page: object) -> bool:
        try:
            annotations = page.get("/Annots")  # type: ignore[attr-defined]
            if annotations is None:
                return False
            annotations = annotations.get_object()
            return len(annotations) > 0
        except Exception:
            return True

    @staticmethod
    def _open_reader(input_path: Path) -> PdfReader:
        try:
            reader = PdfReader(str(input_path), strict=False)
            if reader.is_encrypted:
                try:
                    decrypted = reader.decrypt("")
                except Exception as error:
                    raise EncryptedPdfError(
                        f"PDF 已加密，需要密码：{input_path.name}"
                    ) from error
                if not decrypted:
                    raise EncryptedPdfError(
                        f"PDF 已加密，需要密码：{input_path.name}"
                    )
            _ = len(reader.pages)
            return reader
        except EncryptedPdfError:
            raise
        except (PdfReadError, ValueError, OSError) as error:
            raise InvalidPdfError(
                f"无法读取 PDF：{input_path.name}。原因：{error}"
            ) from error

    @staticmethod
    def _validate_output(
        output_path: Path,
        expected_page_count: int,
        processed_pages: list[int],
    ) -> None:
        try:
            reader = PdfReader(str(output_path), strict=False)
            if len(reader.pages) != expected_page_count:
                raise OutputWriteError(
                    "输出 PDF 的页数与输入文件不一致。"
                )
            for page_number in processed_pages:
                rotation = int(reader.pages[page_number - 1].rotation or 0)
                if rotation != 0:
                    raise OutputWriteError(
                        f"第 {page_number} 页的旋转属性没有成功归零。"
                    )
        except OutputWriteError:
            raise
        except Exception as error:
            raise OutputWriteError(f"无法重新读取输出 PDF：{error}") from error
