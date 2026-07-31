from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_project_version_is_consistent() -> None:
    with (ROOT / "pyproject.toml").open("rb") as file:
        project = tomllib.load(file)["project"]

    pyproject_version = project["version"]
    package_text = (ROOT / "src" / "adjust_pdf" / "__init__.py").read_text(encoding="utf-8")
    version_info = (ROOT / "resources" / "version_info.txt").read_text(encoding="utf-8")

    package_match = re.search(r"__version__\s*=\s*[\"']([^\"']+)", package_text)
    resource_versions = re.findall(r"(?:FileVersion|ProductVersion)'?, '([^']+)'", version_info)

    assert package_match is not None
    assert package_match.group(1) == pyproject_version
    assert resource_versions == [pyproject_version, pyproject_version]
