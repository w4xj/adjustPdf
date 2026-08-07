"""基于 pypdf 的 PDF 旋转固化实现。"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from adjust_pdf.engines.compatible_reader import CompatiblePdfReader
from adjust_pdf.exceptions import (
    EncryptedPdfError,
    InvalidInputError,
    InvalidPdfError,
    OutputWriteError,
    SignedPdfError,
)
from adjust_pdf.models import (
    DocumentInfo,
    PageInfo,
    PageSelectionMode,
    ProcessOptions,
    ProcessResult,
    SignatureInfo,
    StructureRepairResult,
)
from adjust_pdf.signature_parser import (
    extract_signing_time_from_pdf_timestamp,
    parse_pkcs7_signed_data,
)


class PypdfEngine:
    """使用 pypdf 检查并固化 PDF 页面旋转。"""

    def inspect(self, input_path: Path) -> DocumentInfo:
        reader = self._open_reader(input_path, allow_compatibility_repair=True)
        return self._document_info_from_reader(input_path, reader)

    def _document_info_from_reader(
        self,
        input_path: Path,
        reader: PdfReader,
    ) -> DocumentInfo:
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
        signatures = (
            self._inspect_compatible_signatures(reader)
            if isinstance(reader, CompatiblePdfReader) and reader.compatibility_repair_applied
            else self._inspect_signatures(reader)
        )
        return DocumentInfo(
            path=input_path,
            page_count=len(pages),
            pages=pages,
            signatures=signatures,
        )

    @classmethod
    def _inspect_compatible_signatures(
        cls,
        reader: CompatiblePdfReader,
    ) -> tuple[SignatureInfo, ...]:
        """同时检查可访问字段和 xref 物理候选，避免异常结构漏报签章。"""
        try:
            standard = cls._inspect_signatures(reader)
        except Exception:
            standard = ()
        recovered = cls._inspect_recovered_signatures(reader)

        combined = [*standard, *recovered]
        if any(signature.is_signed for signature in combined):
            combined = [signature for signature in combined if signature.is_signed]

        results: list[SignatureInfo] = []
        seen: set[tuple[object, ...]] = set()
        for signature in combined:
            key = (
                signature.field_name,
                signature.filter_name,
                signature.subfilter,
                signature.signing_time,
                signature.contents_length,
                signature.cert_serial_hex,
            )
            if key not in seen:
                seen.add(key)
                results.append(signature)
        return tuple(results)

    @classmethod
    def _inspect_recovered_signatures(
        cls,
        reader: CompatiblePdfReader,
    ) -> tuple[SignatureInfo, ...]:
        """从歧义 xref 的物理候选对象中保守识别数字签名字典。"""
        results: list[SignatureInfo] = []
        pkcs7_cache: dict[int, dict[str, object]] = {}
        for _, value_object in reader.iter_candidate_objects_of_type(b"Sig"):
            field_name = cls._text_value(value_object.get("/Name")) or "兼容模式签名"
            cls._append_signature_info(
                field_name=field_name,
                field_object=None,
                value_reference=value_object,
                page_numbers={},
                results=results,
                pkcs7_cache=pkcs7_cache,
            )
        return tuple(results)

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
        # 缓存已解析的 PKCS7 信息，键为 /V 对象的 idnum
        pkcs7_cache: dict[int, dict[str, object]] = {}

        acroform_reference = root.get("/AcroForm")
        if acroform_reference is not None:
            acroform = acroform_reference.get_object()
            fields = acroform.get("/Fields", [])
            for field in fields:
                cls._walk_signature_field(
                    field_reference=field,
                    page_numbers=page_numbers,
                    results=results,
                    pkcs7_cache=pkcs7_cache,
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
                    pkcs7_cache=pkcs7_cache,
                )

        return tuple(results)

    @classmethod
    def _walk_signature_field(
        cls,
        field_reference: object,
        page_numbers: dict[int, int],
        results: list[SignatureInfo],
        pkcs7_cache: dict[int, dict[str, object]],
        parent_name: str = "",
        inherited_field_type: object | None = None,
    ) -> None:
        field = field_reference.get_object()
        field_type = field.get("/FT", inherited_field_type)
        local_name = cls._text_value(field.get("/T"))
        field_name = (
            ".".join(part for part in (parent_name, local_name) if part) or "未命名签名字段"
        )

        if field_type == "/Sig":
            cls._append_signature_info(
                field_name=field_name,
                field_object=field,
                value_reference=field.get("/V"),
                page_numbers=page_numbers,
                results=results,
                pkcs7_cache=pkcs7_cache,
            )

        children = field.get("/Kids", [])
        for child in children:
            cls._walk_signature_field(
                field_reference=child,
                page_numbers=page_numbers,
                results=results,
                pkcs7_cache=pkcs7_cache,
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
        pkcs7_cache: dict[int, dict[str, object]],
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

        # ── 解析 PKCS7 签名数据，提取证书/签名者信息 ──
        value_id = getattr(value_reference, "idnum", id(value_object))
        if value_id not in pkcs7_cache:
            pkcs7_info: dict[str, object] = {}
            try:
                raw = (
                    contents.original_bytes
                    if hasattr(contents, "original_bytes")
                    else bytes(contents)
                )  # type: ignore[arg-type]
                raw = raw.rstrip(b"\x00")
                signers = parse_pkcs7_signed_data(raw)
                if signers:
                    si = signers[0]
                    pkcs7_info["signer_name"] = si.signer_name
                    pkcs7_info["cert_serial_hex"] = si.cert_serial_hex
                    pkcs7_info["cert_issuer_str"] = si.cert_issuer_str
                    pkcs7_info["cert_valid_from"] = si.cert_valid_from
                    pkcs7_info["cert_valid_to"] = si.cert_valid_to
                    pkcs7_info["has_timestamp"] = si.has_timestamp
                    # 优先用 PKCS7 中的签署时间，否则用 PDF /M 字段
                    pkcs7_info["signing_time"] = (
                        si.signing_time
                        or extract_signing_time_from_pdf_timestamp(
                            cls._text_value(value_object.get("/M"))
                        )
                    )
            except Exception:
                pass
            pkcs7_cache[value_id] = pkcs7_info
        else:
            pkcs7_info = pkcs7_cache[value_id]

        results.append(
            SignatureInfo(
                field_name=field_name,
                page_number=page_number,
                filter_name=cls._text_value(value_object.get("/Filter")),
                subfilter=cls._text_value(value_object.get("/SubFilter")),
                reason=cls._text_value(value_object.get("/Reason")),
                location=cls._text_value(value_object.get("/Location")),
                signing_time=(
                    str(pkcs7_info.get("signing_time") or "")
                    or cls._text_value(value_object.get("/M"))
                ),
                has_byte_range=value_object.get("/ByteRange") is not None,
                contents_length=contents_length,
                signer_name=str(pkcs7_info.get("signer_name") or ""),
                cert_serial_hex=str(pkcs7_info.get("cert_serial_hex") or ""),
                cert_issuer_str=str(pkcs7_info.get("cert_issuer_str") or ""),
                cert_valid_from=str(pkcs7_info.get("cert_valid_from") or ""),
                cert_valid_to=str(pkcs7_info.get("cert_valid_to") or ""),
                has_timestamp=bool(pkcs7_info.get("has_timestamp")),
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
                        f"第 {page_number} 页包含链接、批注或表单区域，请在处理后检查其点击位置。"
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
            raise OutputWriteError(f"无法写入输出文件：{output_path}。原因：{error}") from error
        except Exception as error:
            raise OutputWriteError(f"生成的 PDF 未通过完整性检查：{error}") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        return result

    def repair_structure(
        self,
        input_path: Path,
        output_path: Path,
    ) -> StructureRepairResult:
        """对无签章的异常 PDF 重建 xref 和对象引用。"""
        if output_path.exists():
            raise OutputWriteError(f"为避免覆盖文件，输出文件必须不存在：{output_path}")
        if output_path.resolve() == input_path.resolve():
            raise OutputWriteError("输出文件不能与输入文件相同。")

        reader = self._open_reader(input_path, allow_compatibility_repair=True)
        if not isinstance(reader, CompatiblePdfReader) or not reader.compatibility_repair_applied:
            raise InvalidInputError(f"未检测到需要修复的 PDF 交叉引用异常：{input_path.name}")

        info = self._document_info_from_reader(input_path, reader)
        if info.has_digital_signatures:
            raise SignedPdfError(
                f"禁止修复：{input_path.name} 检测到 "
                f"{len(info.signed_signatures)} 个已写入的数字签名或电子签章。"
            )
        stamp_pages = self._stamp_annotation_pages(reader)
        if stamp_pages:
            page_text = "、".join(str(page_number) for page_number in stamp_pages)
            raise SignedPdfError(
                f"禁止修复：{input_path.name} 的第 {page_text} 页检测到 Stamp 印章批注。"
            )

        source_fingerprints = tuple(self._page_fingerprint(page) for page in reader.pages)
        writer = PdfWriter(clone_from=reader)
        result = StructureRepairResult(
            input_path=input_path,
            output_path=output_path,
            page_count=info.page_count,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

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

            self._validate_repaired_output(
                temporary_path,
                source_fingerprints=source_fingerprints,
            )
            os.replace(temporary_path, output_path)
            temporary_path = None
        except (OutputWriteError, SignedPdfError):
            raise
        except OSError as error:
            raise OutputWriteError(f"无法写入结构修复文件：{output_path}。原因：{error}") from error
        except Exception as error:
            raise OutputWriteError(f"PDF 结构修复失败：{error}") from error
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
    def _stamp_annotation_pages(reader: PdfReader) -> tuple[int, ...]:
        """返回包含 /Subtype /Stamp 印章批注的页码；无法安全解析时拒绝修复。"""
        pages: list[int] = []
        try:
            for page_number, page in enumerate(reader.pages, start=1):
                annotations = page.get("/Annots")
                if annotations is None:
                    continue
                for annotation_reference in annotations.get_object():
                    annotation = annotation_reference.get_object()
                    if annotation.get("/Subtype") == "/Stamp":
                        pages.append(page_number)
                        break
        except Exception as error:
            raise SignedPdfError("禁止修复：无法完整检查页面批注中是否存在电子印章。") from error
        return tuple(pages)

    @classmethod
    def _page_fingerprint(cls, page: object) -> tuple[object, ...]:
        """记录与页面显示内容相关的稳定指纹。"""
        media_box = page.mediabox  # type: ignore[attr-defined]
        crop_box = page.cropbox  # type: ignore[attr-defined]
        contents = page.get_contents()  # type: ignore[attr-defined]
        content_data = b"" if contents is None else contents.get_data()
        return (
            tuple(float(value) for value in media_box),
            tuple(float(value) for value in crop_box),
            int(page.rotation or 0),  # type: ignore[attr-defined]
            hashlib.sha256(content_data).digest(),
            cls._has_annotations(page),
        )

    @classmethod
    def _validate_repaired_output(
        cls,
        output_path: Path,
        source_fingerprints: tuple[tuple[object, ...], ...],
    ) -> None:
        """确认修复文件可被标准 pypdf 读取，且页面内容指纹不变。"""
        try:
            reader = PdfReader(str(output_path), strict=False)
            if len(reader.pages) != len(source_fingerprints):
                raise OutputWriteError("修复后 PDF 的页数与原文件不一致。")
            output_fingerprints = tuple(cls._page_fingerprint(page) for page in reader.pages)
            if output_fingerprints != source_fingerprints:
                raise OutputWriteError("修复后 PDF 的页面尺寸、旋转、内容流或批注状态发生变化。")
        except OutputWriteError:
            raise
        except Exception as error:
            raise OutputWriteError(f"无法重新读取结构修复后的 PDF：{error}") from error

    @staticmethod
    def _open_reader(
        input_path: Path,
        allow_compatibility_repair: bool = False,
    ) -> PdfReader:
        try:
            try:
                reader = PdfReader(str(input_path), strict=False)
            except PdfReadError as error:
                if not allow_compatibility_repair or str(error) != "Could not read Boolean object":
                    raise
                reader = CompatiblePdfReader(str(input_path), strict=False)
            if reader.is_encrypted:
                try:
                    decrypted = reader.decrypt("")
                except Exception as error:
                    raise EncryptedPdfError(f"PDF 已加密，需要密码：{input_path.name}") from error
                if not decrypted:
                    raise EncryptedPdfError(f"PDF 已加密，需要密码：{input_path.name}")
            _ = len(reader.pages)
            return reader
        except EncryptedPdfError:
            raise
        except (PdfReadError, ValueError, OSError) as error:
            raise InvalidPdfError(f"无法读取 PDF：{input_path.name}。原因：{error}") from error

    @staticmethod
    def _validate_output(
        output_path: Path,
        expected_page_count: int,
        processed_pages: list[int],
    ) -> None:
        try:
            reader = PdfReader(str(output_path), strict=False)
            if len(reader.pages) != expected_page_count:
                raise OutputWriteError("输出 PDF 的页数与输入文件不一致。")
            for page_number in processed_pages:
                rotation = int(reader.pages[page_number - 1].rotation or 0)
                if rotation != 0:
                    raise OutputWriteError(f"第 {page_number} 页的旋转属性没有成功归零。")
        except OutputWriteError:
            raise
        except Exception as error:
            raise OutputWriteError(f"无法重新读取输出 PDF：{error}") from error
