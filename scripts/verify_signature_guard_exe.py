"""验证 EXE 对已签名 PDF 的默认阻止和显式放行策略。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print("用法：verify_signature_guard_exe.py <exe路径> [PDF样本路径]")
        return 2

    executable = Path(sys.argv[1]).resolve()
    fixture = (
        Path(sys.argv[2]).resolve()
        if len(sys.argv) == 3
        else Path(__file__).parents[1] / "testFile" / "20260722.pdf"
    )
    if not executable.is_file() or not fixture.is_file():
        print(f"缺少 EXE 或已签名 PDF：{executable}；{fixture}")
        return 2

    with tempfile.TemporaryDirectory(prefix="adjust-pdf-signature-") as temp:
        output_directory = Path(temp)
        blocked = subprocess.run(
            [
                str(executable),
                "--cli",
                str(fixture),
                "--mode",
                "first",
                "--output-dir",
                str(output_directory),
            ],
            check=False,
            timeout=180,
        )
        if blocked.returncode != 1:
            print(f"未确认风险时应返回 1，实际：{blocked.returncode}")
            return 1
        if list(output_directory.glob("*.pdf")):
            print("未确认风险时不应生成输出 PDF。")
            return 1

        allowed = subprocess.run(
            [
                str(executable),
                "--cli",
                str(fixture),
                "--mode",
                "first",
                "--allow-signed",
                "--output-dir",
                str(output_directory),
            ],
            check=False,
            timeout=180,
        )
        if allowed.returncode != 0:
            print(f"明确允许后应返回 0，实际：{allowed.returncode}")
            return 1
        if len(list(output_directory.glob("*.pdf"))) != 1:
            print("明确允许后应生成一个输出 PDF。")
            return 1

    print("EXE 签名安全策略测试通过：默认阻止，明确确认后允许。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
