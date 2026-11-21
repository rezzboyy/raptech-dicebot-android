"""License file persistence (find/load/save).

Diekstrak dari `license/check.py` (Fase 4 perapihan, Step K-5).
Pure I/O — tidak ada UI.

Public API (di-re-export oleh `license/check.py`):
    - `find_license_path()` -> Path | None
    - `load_license(path)` -> LicenseInfo
    - `save_license_key(key, target)` -> Path
    - `_candidate_paths()` -> tuple[Path, ...]
    - `_read_license_file(path)` -> dict
"""
from __future__ import annotations

import os
from pathlib import Path

from ..config import appdata_root, runtime_root, source_root
from ._codec import _validate_payload, parse_license_input
from ._state import LicenseError, LicenseInfo


# Konstanta sinkron dengan check.py
LICENSE_FILENAME = "license.json"
LICENSE_ENV_VAR = "RAPTECH_LICENSE_PATH"


def _candidate_paths() -> tuple[Path, ...]:
    """Daftar path kandidat lokasi `license.json`. Order:
    env override > runtime_root > source_root > appdata_root."""
    override = os.getenv(LICENSE_ENV_VAR)
    paths: list[Path] = []
    if override:
        paths.append(Path(override).expanduser())
    paths.extend([
        runtime_root() / LICENSE_FILENAME,
        source_root() / LICENSE_FILENAME,
        appdata_root() / LICENSE_FILENAME,
    ])
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return tuple(unique)


def find_license_path() -> Path | None:
    for path in _candidate_paths():
        if path.is_file():
            return path
    return None


def save_license_key(key: str, target: Path | None = None) -> Path:
    """Simpan license key ke file. Default ke runtime_root/license.json."""
    if target is None:
        target = runtime_root() / LICENSE_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(key.strip() + "\n", encoding="utf-8")
    return target


def _read_license_file(path: Path) -> dict:
    """Baca file lisensi - support format baru (key string) dan lama (JSON)."""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise LicenseError(f"Lisensi tidak bisa dibaca ({path}): {exc}") from exc
    if not text:
        raise LicenseError(f"File lisensi kosong: {path}")
    return parse_license_input(text)


def load_license(path: Path | None = None) -> LicenseInfo:
    """Baca dan validasi lisensi. Raise LicenseError kalau invalid/expired."""
    target = path or find_license_path()
    if target is None:
        searched = ", ".join(str(candidate) for candidate in _candidate_paths())
        raise LicenseError(
            "File lisensi tidak ditemukan. Letakkan 'license.json' di salah "
            f"satu path: {searched}"
        )

    raw = _read_license_file(target)
    return _validate_payload(raw, source=target)
