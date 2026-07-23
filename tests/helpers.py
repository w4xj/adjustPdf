"""测试辅助函数。"""

from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    ByteStringObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)


def create_test_pdf(
    path: Path,
    rotations: tuple[int, ...],
    annotation_pages: tuple[int, ...] = (),
    encrypted_password: str | None = None,
    signed: bool = False,
    empty_signature_field: bool = False,
) -> Path:
    """创建带简单彩色矩形、可选签名结构的测试 PDF。"""
    writer = PdfWriter()

    for page_number, rotation in enumerate(rotations, start=1):
        page = writer.add_blank_page(width=200, height=100)

        content = DecodedStreamObject()
        content.set_data(
            b"q\n1 0 0 rg\n15 20 60 30 re f\n"
            b"0 0 1 rg\n110 55 35 20 re f\nQ\n"
        )
        page[NameObject("/Contents")] = writer._add_object(content)

        if rotation:
            page[NameObject("/Rotate")] = NumberObject(rotation)

        if page_number in annotation_pages:
            annotation = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Annot"),
                    NameObject("/Subtype"): NameObject("/Link"),
                    NameObject("/Rect"): ArrayObject(
                        [
                            FloatObject(15),
                            FloatObject(20),
                            FloatObject(75),
                            FloatObject(50),
                        ]
                    ),
                    NameObject("/Border"): ArrayObject(
                        [NumberObject(0), NumberObject(0), NumberObject(0)]
                    ),
                }
            )
            page[NameObject("/Annots")] = ArrayObject(
                [writer._add_object(annotation)]
            )

    if signed or empty_signature_field:
        page = writer.pages[0]
        field = DictionaryObject(
            {
                NameObject("/FT"): NameObject("/Sig"),
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/T"): TextStringObject("test_signature"),
                NameObject("/Rect"): ArrayObject(
                    [NumberObject(0), NumberObject(0), NumberObject(0), NumberObject(0)]
                ),
                NameObject("/P"): page.indirect_reference,
            }
        )
        if signed:
            signature = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Sig"),
                    NameObject("/Filter"): NameObject("/Adobe.PPKLite"),
                    NameObject("/SubFilter"): NameObject("/adbe.pkcs7.detached"),
                    NameObject("/ByteRange"): ArrayObject(
                        [
                            NumberObject(0),
                            NumberObject(100),
                            NumberObject(200),
                            NumberObject(300),
                        ]
                    ),
                    NameObject("/Contents"): ByteStringObject(b"fake-signature"),
                    NameObject("/Reason"): TextStringObject("测试电子签章"),
                    NameObject("/M"): TextStringObject("D:20260723120000+08'00'"),
                }
            )
            field[NameObject("/V")] = writer._add_object(signature)

        field_reference = writer._add_object(field)
        annotations = page.get("/Annots")
        if annotations is None:
            page[NameObject("/Annots")] = ArrayObject([field_reference])
        else:
            annotations.append(field_reference)

        acroform = DictionaryObject(
            {
                NameObject("/Fields"): ArrayObject([field_reference]),
                NameObject("/SigFlags"): NumberObject(3),
            }
        )
        writer._root_object[NameObject("/AcroForm")] = writer._add_object(acroform)

    writer.add_metadata({"/Title": "旋转固化测试"})
    if encrypted_password is not None:
        writer.encrypt(encrypted_password)

    with path.open("wb") as file:
        writer.write(file)

    return path
