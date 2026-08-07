"""pypdf 对少数非标准交叉引用表的只读兼容处理。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from pypdf import PdfReader
from pypdf._utils import read_non_whitespace
from pypdf.generic import DictionaryObject, IndirectObject, read_object

_PDF_WHITESPACE = b"\x00\x09\x0a\x0c\x0d\x20"
_XrefKey = tuple[int, int]
_XrefCandidates = dict[_XrefKey, list[int]]


class CompatiblePdfReader(PdfReader):
    """容忍空 xref 段和同一 xref 表中的重复对象映射。

    某些电子签章/合并软件会生成两类非标准结构：

    1. ``xref`` 后直接跟 ``trailer``，没有任何 subsection；
    2. 最新 xref 表为同一对象编号给出多个偏移，并依赖对象类型选择正确版本。

    pypdf 读取第一类结构时会把 ``trailer`` 当成以 ``t`` 开头的 Boolean，
    第二类结构则固定保留第一次出现的偏移。本类只为检查页面信息提供兼容读取，
    不用于重写这类结构异常的 PDF。
    """

    def __init__(
        self,
        stream: str | Path | BinaryIO,
        strict: bool = False,
        password: str | bytes | None = None,
        *,
        root_object_recovery_limit: int | None = 10000,
    ) -> None:
        self.compatibility_repair_applied = False
        self._latest_xref_candidates: _XrefCandidates | None = None
        super().__init__(
            stream,
            strict=strict,
            password=password,
            root_object_recovery_limit=root_object_recovery_limit,
        )
        self._repair_page_tree_mappings()

    def _read_standard_xref_table(self, stream: BinaryIO) -> None:
        """记录最新 xref 的候选偏移，并跳过没有 subsection 的空 xref。"""
        start = stream.tell()
        candidates = self._parse_xref_candidates(stream)
        if candidates and self._latest_xref_candidates is None:
            self._latest_xref_candidates = candidates

        stream.seek(start)
        if self._consume_empty_xref(stream):
            self.compatibility_repair_applied = True
            return

        stream.seek(start)
        super()._read_standard_xref_table(stream)

    @staticmethod
    def _consume_empty_xref(stream: BinaryIO) -> bool:
        """若当前位置是 ``ref + 空白 + trailer``，消费 trailer 并返回 True。"""
        if stream.read(3) != b"ref":
            return False

        token = stream.read(1)
        while token and token in _PDF_WHITESPACE:
            token = stream.read(1)
        if token:
            stream.seek(-1, 1)

        return stream.read(7) == b"trailer"

    @staticmethod
    def _parse_xref_candidates(stream: BinaryIO) -> _XrefCandidates | None:
        """轻量解析一个标准 xref 表，保留重复对象编号的全部候选偏移。"""
        start = stream.tell()
        try:
            if stream.read(3) != b"ref":
                return None

            candidates: _XrefCandidates = {}
            while True:
                line = stream.readline()
                while line and not line.strip():
                    line = stream.readline()

                stripped = line.strip()
                if not stripped:
                    return candidates
                if stripped == b"trailer":
                    return candidates

                header = stripped.split()
                if len(header) != 2:
                    return None
                try:
                    first_object, count = (int(value) for value in header)
                except ValueError:
                    return None

                for index in range(count):
                    entry = stream.readline().strip().split()
                    if len(entry) < 3:
                        return None
                    if entry[2] != b"n":
                        continue
                    try:
                        offset = int(entry[0])
                        generation = int(entry[1])
                    except ValueError:
                        return None
                    key = (generation, first_object + index)
                    candidates.setdefault(key, []).append(offset)
        finally:
            stream.seek(start)

    def _repair_page_tree_mappings(self) -> None:
        """按 /Catalog、/Pages、/Page 类型修复页面树中有歧义的对象映射。"""
        if not self._latest_xref_candidates:
            return

        root_reference = self.trailer.raw_get("/Root")
        if not isinstance(root_reference, IndirectObject):
            return
        if not self._set_reference_to_typed_candidate(root_reference, b"Catalog"):
            return

        root = root_reference.get_object()
        pages_reference = root.raw_get("/Pages")
        if not isinstance(pages_reference, IndirectObject):
            return
        if not self._set_reference_to_typed_candidate(pages_reference, b"Pages"):
            return

        self._repair_page_tree_node(pages_reference, visited=set())

    def _repair_page_tree_node(
        self,
        pages_reference: IndirectObject,
        visited: set[_XrefKey],
    ) -> None:
        key = (pages_reference.generation, pages_reference.idnum)
        if key in visited:
            return
        visited.add(key)

        pages_object = pages_reference.get_object()
        kids = pages_object.raw_get("/Kids")
        for kid_reference in kids:
            if not isinstance(kid_reference, IndirectObject):
                continue

            page_offset = self._typed_candidate_offset(kid_reference, b"Page")
            pages_offset = self._typed_candidate_offset(kid_reference, b"Pages")
            if page_offset is not None and pages_offset is None:
                self._set_reference_offset(kid_reference, page_offset)
            elif pages_offset is not None and page_offset is None:
                self._set_reference_offset(kid_reference, pages_offset)
                self._repair_page_tree_node(kid_reference, visited)

    def _set_reference_to_typed_candidate(
        self,
        reference: IndirectObject,
        type_name: bytes,
    ) -> bool:
        offset = self._typed_candidate_offset(reference, type_name)
        if offset is None:
            return False
        self._set_reference_offset(reference, offset)
        return True

    def _set_reference_offset(self, reference: IndirectObject, offset: int) -> None:
        generation_xref = self.xref.setdefault(reference.generation, {})
        if generation_xref.get(reference.idnum) == offset:
            return

        generation_xref[reference.idnum] = offset
        self.resolved_objects.pop((reference.generation, reference.idnum), None)
        self.compatibility_repair_applied = True

    def _typed_candidate_offset(
        self,
        reference: IndirectObject,
        type_name: bytes,
    ) -> int | None:
        if not self._latest_xref_candidates:
            return None

        offsets = self._latest_xref_candidates.get(
            (reference.generation, reference.idnum),
            (),
        )
        for offset in reversed(offsets):
            if self._candidate_has_type(reference, offset, type_name):
                return offset
        return None

    def _candidate_has_type(
        self,
        reference: IndirectObject,
        offset: int,
        type_name: bytes,
    ) -> bool:
        prefix = self._read_at(offset, 8192)
        object_header = rb"%d\s+%d\s+obj\b" % (
            reference.idnum,
            reference.generation,
        )
        if re.match(object_header, prefix) is None:
            return False

        dictionary_prefix = prefix.split(b"endobj", 1)[0].split(b"stream", 1)[0]
        return re.search(rb"/Type\s*/" + type_name + rb"\b", dictionary_prefix) is not None

    def iter_candidate_objects_of_type(
        self,
        type_name: bytes,
    ) -> Iterator[tuple[int, DictionaryObject]]:
        """按物理偏移返回最新 xref 表中指定 /Type 的独立字典对象。"""
        if not self._latest_xref_candidates:
            return

        seen_offsets: set[int] = set()
        for (generation, idnum), offsets in self._latest_xref_candidates.items():
            reference = IndirectObject(idnum, generation, self)
            for offset in offsets:
                if offset in seen_offsets or not self._candidate_has_type(
                    reference,
                    offset,
                    type_name,
                ):
                    continue
                seen_offsets.add(offset)
                candidate = self._read_indirect_object_at(offset)
                if isinstance(candidate, DictionaryObject):
                    yield offset, candidate

    def _read_indirect_object_at(self, offset: int) -> Any:
        stream = self.stream
        original_position = stream.tell()
        try:
            stream.seek(offset)
            _ = self._read_next_object(stream)
            _ = self._read_next_object(stream)
            marker = read_non_whitespace(stream)
            if marker != b"o" or stream.read(2) != b"bj":
                return None
            return self._read_next_object(stream)
        finally:
            stream.seek(original_position)

    def _read_at(self, offset: int, size: int) -> bytes:
        stream = self.stream
        original_position = stream.tell()
        try:
            stream.seek(offset)
            return stream.read(size)
        finally:
            stream.seek(original_position)

    def _read_next_object(self, stream: BinaryIO) -> Any:
        token = read_non_whitespace(stream)
        if not token:
            return None
        stream.seek(-1, 1)
        return read_object(stream, self)
