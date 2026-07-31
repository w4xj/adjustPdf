"""PKCS#7 / CMS 签名数据解析器，从 PDF 签名的 /Contents 中提取证书和签名者信息。

专用于解析符合 GB/T 33560 (SM2/SM3) 标准的国密证书和 PKCS7 结构，
不依赖 OpenSSL 或 cryptography 等对外国算法支持有限的库。
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SignerInfo:
    """从 PKCS7 SignedData 中提取的一位签名者信息。"""

    signer_name: str | None
    cert_serial_hex: str | None
    cert_issuer_str: str | None
    cert_valid_from: str | None
    cert_valid_to: str | None
    signing_time: str | None
    has_timestamp: bool


# ── 底层 DER 解析 ──────────────────────────────────────────────────


def _parse_tag(data: bytes, offset: int) -> tuple[int, int, bytes, int]:
    """解析一个 DER TLV 元素，返回 (tag, length, value, next_offset)。"""
    tag = data[offset]
    offset += 1
    length = data[offset]
    offset += 1
    if length & 0x80:
        num_bytes = length & 0x7F
        length = int.from_bytes(data[offset : offset + num_bytes], "big")
        offset += num_bytes
    value = data[offset : offset + length]
    return tag, length, value, offset + length


def _decode_oid(value: bytes) -> str:
    """将 DER OID 编码的字节解码为点分字符串。"""
    parts: list[str] = []
    first = value[0]
    parts.append(str(first // 40))
    parts.append(str(first % 40))
    pos = 1
    while pos < len(value):
        val = 0
        while pos < len(value):
            byte = value[pos]
            pos += 1
            val = (val << 7) | (byte & 0x7F)
            if not (byte & 0x80):
                break
        parts.append(str(val))
    return ".".join(parts)


def _parse_int_value(data: bytes, offset: int = 0) -> int:
    """解析 DER INTEGER 并返回整数值（不检查 tag）。"""
    _, _, value, _ = _parse_tag(data, offset)
    return int.from_bytes(value, "big")


def _skip_tlv(data: bytes, offset: int) -> int:
    """跳过当前 TLV 元素并返回后面的偏移量。"""
    _, _, _, next_offset = _parse_tag(data, offset)
    return next_offset


# ── X.509 证书提取 ────────────────────────────────────────────────


def _parse_rdn_sequence(data: bytes, offset: int) -> dict[str, str]:
    """解析 SET → SEQUENCE → (OID, value) 的 RDN 序列。

    返回 {短名称: 值} 字典。
    """
    result: dict[str, str] = {}
    tag, length, value, _ = _parse_tag(data, offset)
    if tag not in (0x30, 0x31):
        return result

    OID_MAP = {
        "2.5.4.6": "C",
        "2.5.4.10": "O",
        "2.5.4.11": "OU",
        "2.5.4.3": "CN",
        "2.5.4.4": "SN",
        "2.5.4.5": "serialNumber",
        "2.5.4.7": "L",
        "2.5.4.8": "ST",
    }

    pos = 0
    while pos < len(value):
        # SET
        set_tag, set_len, set_value, _ = _parse_tag(value, pos)
        if set_tag != 0x31:
            break
        # SEQUENCE inside SET (AttributeTypeAndValue)
        inner_pos = 0
        while inner_pos < len(set_value):
            seq_tag, seq_len, seq_value, _ = _parse_tag(set_value, inner_pos)
            if seq_tag != 0x30:
                break
            # OID
            oid_tag, oid_len, oid_bytes, sv_pos = _parse_tag(seq_value, 0)
            attr_name = ""
            if oid_tag == 0x06:
                oid_str = _decode_oid(oid_bytes)
                attr_name = OID_MAP.get(oid_str, oid_str)
            # Value (any string type)
            if sv_pos < len(seq_value):
                val_tag, val_len, val_bytes, _ = _parse_tag(seq_value, sv_pos)
                try:
                    val_str = val_bytes.decode("utf-8", errors="replace")
                except Exception:
                    val_str = val_bytes.decode("ascii", errors="replace")
                # 有些字段（如 OU）可以是数组，取第一个非数组值
                if attr_name in result:
                    existing = result[attr_name]
                    if not isinstance(existing, list):
                        result[attr_name] = [existing]
                    if isinstance(result[attr_name], list):
                        (result[attr_name]).append(val_str)
                else:
                    result[attr_name] = val_str
            inner_pos = _skip_tlv(set_value, inner_pos)
        pos = _skip_tlv(value, pos)
    return result


def _parse_time(data: bytes, offset: int) -> str | None:
    """解析 UTCTime (0x17) 或 GeneralizedTime (0x18) 并返回格式化字符串。"""
    if offset >= len(data):
        return None
    tag = data[offset]
    if tag not in (0x17, 0x18):
        return None
    _, _, value, _ = _parse_tag(data, offset)
    try:
        text = value.decode("ascii")
    except Exception:
        return None
    return _format_time(text, tag)


def _format_time(text: str, tag: int) -> str | None:
    """将 DER 时间文本格式化为 YYYY-MM-DD HH:MM 字符串 (UTC+8)。"""
    try:
        if tag == 0x17:  # UTCTime: YYMMDDHHMMSSZ
            year = 2000 + int(text[0:2]) if int(text[0:2]) < 50 else 1900 + int(text[0:2])
            month = int(text[2:4])
            day = int(text[4:6])
            hour = int(text[6:8])
            minute = int(text[8:10])
            second = int(text[10:12])
        else:  # GeneralizedTime
            year = int(text[0:4])
            month = int(text[4:6])
            day = int(text[6:8])
            hour = int(text[8:10])
            minute = int(text[10:12])
            second = int(text[12:14])

        # 转换为 UTC+8 显示
        dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
        local = dt.astimezone(datetime.timezone(datetime.timedelta(hours=8)))
        return local.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return None


# ── PKCS7 SignedData 解析 ─────────────────────────────────────────


def parse_pkcs7_signed_data(raw: bytes) -> list[SignerInfo]:
    """从 PKCS7 / CMS SignedData 的 DER 编码中提取签名者信息。

    Args:
        raw: PDF 签名字段 /Contents 的原始字节。

    Returns:
        SignerInfo 列表，通常含 1 个条目（一个签署事件一个签名者）。
    """
    # ── 0. ContentInfo SEQUENCE ──
    offset = 0
    _, _, ci_value, _ = _parse_tag(raw, offset)  # SEQUENCE

    # content_type OID
    _, _, oid_value, offset = _parse_tag(ci_value, 0)
    oid = _decode_oid(oid_value)
    if oid != "1.2.840.113549.1.7.2":
        return []  # 不是 SignedData

    # [0] EXPLICIT wrapper
    _, _, explicit_value, _ = _parse_tag(ci_value, offset)

    # ── 1. SignedData SEQUENCE ──
    _, _, sd_value, _ = _parse_tag(explicit_value, 0)

    pos = 0
    # version (INTEGER)
    _, _, version_value, pos = _parse_tag(sd_value, pos)  # INTEGER

    # digestAlgorithms (SET of AlgorithmIdentifier)
    _, _, dig_algs_value, pos = _parse_tag(sd_value, pos)  # SET

    # contentInfo (SEQUENCE) - 要签名的原始内容信息
    _, _, enc_content_value, pos = _parse_tag(sd_value, pos)  # SEQUENCE

    # ── 2. Certificates (隐式 [0] 标签) ──
    # 如果存在证书，将以 IMPLICIT [0] tag (0xa0) 开始
    cert_raw: bytes | None = None
    if pos < len(sd_value):
        next_tag = sd_value[pos]
        if next_tag == 0xA0:  # [0] IMPLICIT - CertificateSet
            _, _, cert_set_value, pos = _parse_tag(sd_value, pos)
            # CertificateSet 是 SET (0x31) 或 SEQUENCE (0x30)
            if pos <= len(sd_value):
                # 在 cert_set_value 内部
                cp = 0
                while cp < len(cert_set_value):
                    ctag, _, cv, _ = _parse_tag(cert_set_value, cp)
                    if ctag == 0x30:  # SEQUENCE (Certificate)
                        cert_raw = cv
                        break
                    cp = _skip_tlv(cert_set_value, cp)
        elif next_tag == 0x31 or next_tag == 0x30:
            # 直接是 SEQUENCE/SET（没有 [0] 包装）
            _, _, cert_set_value, pos = _parse_tag(sd_value, pos)
            cp = 0
            while cp < len(cert_set_value):
                ctag, _, cv, _ = _parse_tag(cert_set_value, cp)
                if ctag == 0x30:  # Certificate
                    cert_raw = cv
                    break
                cp = _skip_tlv(cert_set_value, cp)

    # ── 3. 提取证书信息 ──
    cert_info = _extract_cert_info(cert_raw) if cert_raw else {}

    # ── 4. CRLs (跳过，[1] IMPLICIT 标签 0xa1) ──
    while pos < len(sd_value):
        if sd_value[pos] in (0xA0, 0xA1):
            pos = _skip_tlv(sd_value, pos)
        else:
            break

    # ── 5. SignerInfos (SET of SignerInfo) ──
    signers: list[SignerInfo] = []
    _, _, signers_value, _ = _parse_tag(sd_value, pos)  # SET

    sp = 0
    while sp < len(signers_value):
        # SignerInfo SEQUENCE
        _, _, si_value, sp = _parse_tag(signers_value, sp)

        si_pos = 0
        # version (INTEGER)
        _, _, _, si_pos = _parse_tag(si_value, si_pos)

        # sid (IssuerAndSerialNumber 或 SubjectKeyIdentifier)
        sid_tag = si_value[si_pos]
        if sid_tag == 0x30:  # SEQUENCE = IssuerAndSerialNumber
            _, _, ias_value, si_pos = _parse_tag(si_value, si_pos)
            # 里面是 IssuerName (SEQUENCE) + SerialNumber (INTEGER)
            rdn_offset = 0
            # IssuerName is SEQUENCE of SETs
            _, _, issuer_seq, rdn_pos = _parse_tag(ias_value, rdn_offset)
            # 跳过 issuer 内容 (SETs)
            rdn_pos = len(issuer_seq)  # fast-forward through issuer
            # Serial number
            if rdn_pos < len(ias_value):
                serial_int = _parse_int_value(ias_value, rdn_pos)
                serial_hex = format(serial_int, "x")
                if not cert_info.get("serial_hex"):
                    cert_info = dict(cert_info)
                    cert_info["serial_hex"] = serial_hex
        elif sid_tag == 0x80:  # SubjectKeyIdentifier
            _, _, _, si_pos = _parse_tag(si_value, si_pos)

        # digestAlgorithm (SEQUENCE)
        _, _, _, si_pos = _parse_tag(si_value, si_pos)

        # ── signedAttrs [0] IMPLICIT (0xa0) - OPTIONAL ──
        signing_time_from_pkcs7: str | None = None
        if si_pos < len(si_value) and si_value[si_pos] == 0xA0:
            _, _, signed_attrs_value, si_pos = _parse_tag(si_value, si_pos)
            # 解析 signedAttrs 中的 signing-time (OID 1.2.840.113549.1.9.5)
            attr_pos = 0
            while attr_pos < len(signed_attrs_value):
                # Each Attribute: SEQUENCE { OID, SET of values }
                _, _, attr_value, attr_pos = _parse_tag(signed_attrs_value, attr_pos)
                apos = 0
                _, _, attr_oid_bytes, apos = _parse_tag(attr_value, 0)
                attr_oid = _decode_oid(attr_oid_bytes)
                if attr_oid == "1.2.840.113549.1.9.5":  # signing-time
                    # 从 SET 中提取时间
                    _, _, _, _ = _parse_tag(attr_value, apos)
                # 不需要提取 signing_time，PDF /M 字段更可靠

        # signatureAlgorithm (SEQUENCE)
        _, _, _, si_pos = _parse_tag(si_value, si_pos)

        # signature (OCTET STRING, tag 0x04 或 BIT STRING, tag 0x03)
        if si_pos < len(si_value):
            sig_tag = si_value[si_pos]
            if sig_tag in (0x03, 0x04):
                si_pos = _skip_tlv(si_value, si_pos)

        # ── unsignedAttrs [1] IMPLICIT (0xa1) - OPTIONAL ──
        has_timestamp = False
        if si_pos < len(si_value) and si_value[si_pos] == 0xA1:
            has_timestamp = True
            # unsignedAttrs 中包含 TSA 时间戳令牌，可提取签名时间作为备选
            _, _, unsigned_attrs_value, _ = _parse_tag(si_value, si_pos)
            # 也许有其他属性需要提取，暂时只检测是否存在
            if not signing_time_from_pkcs7:
                # 尝试从 unsignedAttrs 中提取 TSA 时间戳的签署时间
                # 查找 signing-time OID (1.2.840.113549.1.9.5)
                st_oid_bytes = bytes(
                    [0x06, 0x09, 0x2A, 0x86, 0x48, 0x86, 0xF7, 0x0D, 0x01, 0x09, 0x05]
                )
                st_idx = unsigned_attrs_value.find(st_oid_bytes)
                if st_idx >= 0:
                    # 在 OID 后面应该有 SET → UTCTime/GeneralizedTime
                    search_pos = st_idx + len(st_oid_bytes)
                    tlv_pos = search_pos
                    while tlv_pos < len(unsigned_attrs_value):
                        if unsigned_attrs_value[tlv_pos] in (0x17, 0x18):
                            t = _parse_time(unsigned_attrs_value, tlv_pos)
                            if t:
                                signing_time_from_pkcs7 = t
                            break
                        tlv_pos += 1

        signers.append(
            SignerInfo(
                signer_name=cert_info.get("cn"),
                cert_serial_hex=cert_info.get("serial_hex"),
                cert_issuer_str=cert_info.get("issuer_str"),
                cert_valid_from=cert_info.get("valid_from"),
                cert_valid_to=cert_info.get("valid_to"),
                signing_time=signing_time_from_pkcs7,
                has_timestamp=has_timestamp,
            )
        )

    return (
        signers
        if signers
        else [
            SignerInfo(
                signer_name=cert_info.get("cn"),
                cert_serial_hex=cert_info.get("serial_hex"),
                cert_issuer_str=cert_info.get("issuer_str"),
                cert_valid_from=cert_info.get("valid_from"),
                cert_valid_to=cert_info.get("valid_to"),
                signing_time=None,
                has_timestamp=False,
            )
        ]
    )


def _extract_cert_info(cert_outer_value: bytes) -> dict[str, Any]:
    """从 Certificate SEQUENCE value 中提取关键信息。

    cert_outer_value 是整个 Certificate SEQUENCE 的 value（不含外层的 30 tag+length），
    其第一个元素即为 TBSCertificate SEQUENCE。
    """
    result: dict[str, Any] = {}

    # ── 解包 TBSCertificate SEQUENCE ──
    if not cert_outer_value or cert_outer_value[0] != 0x30:
        return result
    _, _, tbs_value, _ = _parse_tag(cert_outer_value, 0)

    pos = 0
    # 跳过 version [0] EXPLICIT (可能不存在)
    if pos < len(tbs_value) and tbs_value[pos] == 0xA0:
        pos = _skip_tlv(tbs_value, pos)

    # serialNumber (INTEGER)
    if pos < len(tbs_value):
        serial_int = _parse_int_value(tbs_value, pos)
        result["serial_hex"] = format(serial_int, "x")
        pos = _skip_tlv(tbs_value, pos)

    # signature (AlgorithmIdentifier SEQUENCE)
    if pos < len(tbs_value):
        pos = _skip_tlv(tbs_value, pos)

    # issuer (SEQUENCE of RDNs)
    if pos < len(tbs_value):
        issuer = _parse_rdn_sequence(tbs_value, pos)
        result["issuer"] = issuer
        # 格式化为 C=...,O=...,OU=...,CN=...
        issuer_parts = []
        for key in ("C", "O", "OU", "CN"):
            val = issuer.get(key)
            if val:
                if isinstance(val, list):
                    val = val[0]
                issuer_parts.append(f"{key}={val}")
        result["issuer_str"] = ",".join(issuer_parts)
        pos = _skip_tlv(tbs_value, pos)

    # validity (SEQUENCE of UTCTime/GeneralizedTime)
    if pos < len(tbs_value):
        _, _, validity_value, pos = _parse_tag(tbs_value, pos)
        vp = 0
        not_before = _parse_time(validity_value, vp)
        if not_before:
            vp = _skip_tlv(validity_value, vp)
            not_after = _parse_time(validity_value, vp)
            result["valid_from"] = not_before
            result["valid_to"] = not_after

    # subject (SEQUENCE of RDNs)
    if pos < len(tbs_value):
        subject = _parse_rdn_sequence(tbs_value, pos)
        result["subject"] = subject
        result["cn"] = subject.get("CN")
        if not result.get("cn"):
            # 备选：SN 或 organizationName
            result["cn"] = subject.get("SN", subject.get("O", subject.get("OU", "")))

    return result


def extract_signing_time_from_pdf_timestamp(
    pdf_time_str: str | None,
) -> str | None:
    """将 PDF 时间戳格式 (D:YYYYMMDDHHMMSS+HH'MM') 转为可读格式。"""
    if not pdf_time_str:
        return None
    # 格式: D:20260728143115+08'00'
    match = re.match(
        r"D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})([+-]\d{2})'?(\d{2})?'?",
        pdf_time_str,
    )
    if match:
        parts = match.groups()
        return f"{parts[0]}-{parts[1]}-{parts[2]} {parts[3]}:{parts[4]}:{parts[5]}"
    return pdf_time_str
