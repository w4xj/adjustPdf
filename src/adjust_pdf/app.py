"""应用总入口。"""

from __future__ import annotations

import sys
from pathlib import Path

from adjust_pdf.cli import main as cli_main
from adjust_pdf.logging_config import configure_logging, get_logger


def _initial_pdf_files(arguments: list[str]) -> list[Path]:
    files: list[Path] = []
    for argument in arguments:
        if argument.startswith("-"):
            continue
        path = Path(argument)
        if path.suffix.lower() == ".pdf":
            files.append(path)
    return files


def main() -> int:
    log_path = configure_logging()
    logger = get_logger("app")
    arguments = sys.argv[1:]

    if "--cli" in arguments:
        cli_arguments = [argument for argument in arguments if argument != "--cli"]
        return cli_main(cli_arguments)

    try:
        from adjust_pdf.gui.main_window import launch_gui

        launch_gui(
            initial_files=_initial_pdf_files(arguments),
            log_path=log_path,
        )
        return 0
    except Exception:
        logger.exception("图形界面启动失败")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
