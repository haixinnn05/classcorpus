from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
from importlib.metadata import PackageNotFoundError, version
import shutil
import sqlite3
import sys
import tempfile

from classcorpus.database import Database
from classcorpus.parsers import supported_suffixes
from classcorpus.paths import data_root, database_path


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    name: str
    status: str
    required: bool
    message: str
    action: str | None = None


def doctor_report() -> dict[str, object]:
    checks = [
        _python_check(),
        _fts_check(),
        _data_directory_check(),
        _database_check(),
        _optional_module_check(
            "sentence-transformers",
            "sentence_transformers",
            'Install with: pip install -e ".[embeddings]"',
        ),
        _optional_module_check(
            "FastEmbed",
            "fastembed",
            'Install with: pip install -e ".[fastembed]"',
        ),
        _optional_module_check(
            "Tesseract Python adapter",
            "pytesseract",
            'Install with: pip install -e ".[ocr]"',
        ),
        _tesseract_executable_check(),
    ]
    required_ok = all(
        check.status == "pass" for check in checks if check.required
    )
    reported_data_root, reported_database_path = _reported_paths()
    return {
        "ok": required_ok,
        "version": _package_version(),
        "python": sys.version.split()[0],
        "data_root": reported_data_root,
        "database_path": reported_database_path,
        "supported_formats": sorted(supported_suffixes()),
        "checks": [asdict(check) for check in checks],
    }


def _python_check() -> DiagnosticCheck:
    supported = sys.version_info >= (3, 11)
    return DiagnosticCheck(
        name="Python",
        status="pass" if supported else "fail",
        required=True,
        message=f"Python {sys.version.split()[0]}",
        action=None if supported else "Install Python 3.11 or newer.",
    )


def _fts_check() -> DiagnosticCheck:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE VIRTUAL TABLE test_fts USING fts5(content)")
    except sqlite3.Error as error:
        return DiagnosticCheck(
            name="SQLite FTS5",
            status="fail",
            required=True,
            message=str(error),
            action="Install a Python build whose SQLite includes FTS5.",
        )
    finally:
        connection.close()
    return DiagnosticCheck(
        name="SQLite FTS5",
        status="pass",
        required=True,
        message=f"SQLite {sqlite3.sqlite_version} includes FTS5.",
    )


def _data_directory_check() -> DiagnosticCheck:
    try:
        root = data_root()
        with tempfile.NamedTemporaryFile(dir=root):
            pass
    except OSError as error:
        return DiagnosticCheck(
            name="Data directory",
            status="fail",
            required=True,
            message=str(error),
            action="Choose a writable CLASSCORPUS_DATA_DIR.",
        )
    return DiagnosticCheck(
        name="Data directory",
        status="pass",
        required=True,
        message=f"Writable: {root}",
    )


def _database_check() -> DiagnosticCheck:
    try:
        database = Database()
        database.initialize()
        database.connection.execute("SELECT COUNT(*) FROM courses").fetchone()
        database.connection.close()
    except (OSError, sqlite3.Error) as error:
        return DiagnosticCheck(
            name="Database",
            status="fail",
            required=True,
            message=str(error),
            action="Check database permissions or choose a new data directory.",
        )
    return DiagnosticCheck(
        name="Database",
        status="pass",
        required=True,
        message=f"Ready: {database_path()}",
    )


def _optional_module_check(
    label: str,
    module: str,
    action: str,
) -> DiagnosticCheck:
    available = importlib.util.find_spec(module) is not None
    return DiagnosticCheck(
        name=label,
        status="pass" if available else "optional",
        required=False,
        message="Available." if available else "Not installed.",
        action=None if available else action,
    )


def _tesseract_executable_check() -> DiagnosticCheck:
    executable = shutil.which("tesseract")
    return DiagnosticCheck(
        name="Tesseract executable",
        status="pass" if executable else "optional",
        required=False,
        message=executable or "Not installed.",
        action=(
            None
            if executable
            else "Install Tesseract with your operating system package manager."
        ),
    )


def _package_version() -> str:
    try:
        return version("classcorpus")
    except PackageNotFoundError:
        return "development"


def _reported_paths() -> tuple[str, str]:
    try:
        return str(data_root()), str(database_path())
    except OSError:
        return "unavailable", "unavailable"


__all__ = ["DiagnosticCheck", "doctor_report"]
