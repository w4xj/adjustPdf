"""工具可以识别并向用户友好展示的异常。"""


class AdjustPdfError(Exception):
    """应用层可预期异常的基类。"""


class InvalidInputError(AdjustPdfError):
    """输入文件无效。"""


class InvalidPdfError(AdjustPdfError):
    """文件不是可读取的 PDF。"""


class EncryptedPdfError(AdjustPdfError):
    """PDF 需要密码。"""


class SignedPdfError(AdjustPdfError):
    """PDF 包含已写入的数字签名，禁止执行要求无签章的操作。"""


class OutputWriteError(AdjustPdfError):
    """输出文件无法写入。"""
