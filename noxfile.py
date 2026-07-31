"""Common development tasks exposed through nox."""

from __future__ import annotations

import nox

nox.options.sessions = ["tests", "lint"]


@nox.session(reuse_venv=True)
def tests(session: nox.Session) -> None:
    """Run the test suite with coverage."""
    session.install("-e", ".[dev]")
    session.run(
        "pytest",
        "--cov=adjust_pdf",
        "--cov-report=term-missing",
        "--cov-report=xml",
        *session.posargs,
    )


@nox.session(reuse_venv=True)
def lint(session: nox.Session) -> None:
    """Run Ruff lint and format checks."""
    session.install("ruff")
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")


@nox.session(reuse_venv=True)
def format(session: nox.Session) -> None:
    """Fix Ruff violations and format Python files."""
    session.install("ruff")
    session.run("ruff", "check", "--fix", ".")
    session.run("ruff", "format", ".")
