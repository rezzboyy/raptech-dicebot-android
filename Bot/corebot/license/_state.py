"""State global + tipe dasar untuk paket license.

Diekstrak dari `license/check.py` (Fase 4 perapihan, Step K-1/K-2).
Berisi:
  - `LicenseInfo`, `LicenseError`, `LicenseRevoked` (tipe dasar)
  - State global revocation (`_REVOCATION_REASON`)
  - State global heartbeat thread (`_HEARTBEAT_THREAD`, `_HEARTBEAT_STOP`)

Public API (di-re-export oleh `license/check.py`):
    - `LicenseInfo`, `LicenseError`, `LicenseRevoked`
    - `get_revocation_reason()` -> str | None
    - `set_revocation_reason(reason)`
    - `clear_revocation_reason()`
    - `stop_background_heartbeat()`
    - `heartbeat_thread_state()` -> (thread, stop_event)
    - `set_heartbeat_thread(thread)`
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class LicenseInfo:
    customer: str
    issued_at: datetime
    expires_at: datetime
    machine_id: str | None
    code: str | None
    days_left: float
    path: Path

    @property
    def is_expired(self) -> bool:
        return self.days_left <= 0


class LicenseError(Exception):
    """Raised saat lisensi tidak valid, expired, atau tidak ditemukan."""


class LicenseRevoked(LicenseError):
    """Raised saat server bilang lisensi sudah revoked / expired."""


_HEARTBEAT_THREAD: threading.Thread | None = None
_HEARTBEAT_STOP = threading.Event()
_REVOCATION_REASON: str | None = None  # set kalau bot harus restart ke prompt


def get_revocation_reason() -> str | None:
    """Dipanggil oleh main loop untuk cek apakah harus restart ke prompt
    aktivasi. None kalau tidak ada revoke."""
    return _REVOCATION_REASON


def set_revocation_reason(reason: str | None) -> None:
    """Set flag revocation. Heartbeat thread set string, main loop cek
    via `get_revocation_reason()`."""
    global _REVOCATION_REASON
    _REVOCATION_REASON = reason


def clear_revocation_reason() -> None:
    global _REVOCATION_REASON
    _REVOCATION_REASON = None


def stop_background_heartbeat() -> None:
    """Stop background thread (dipanggil saat bot mau exit / restart)."""
    _HEARTBEAT_STOP.set()


def heartbeat_thread_state() -> tuple[threading.Thread | None, threading.Event]:
    """Return (current thread, stop event). Dipakai modul `check.py`
    untuk re-use stop event saat start ulang thread."""
    return _HEARTBEAT_THREAD, _HEARTBEAT_STOP


def set_heartbeat_thread(thread: threading.Thread | None) -> None:
    global _HEARTBEAT_THREAD
    _HEARTBEAT_THREAD = thread


def reset_stop_event() -> None:
    """Reset stop event sehingga thread baru bisa berjalan setelah
    `stop_background_heartbeat()` dipanggil di session sebelumnya.

    Saat ini main loop sebenarnya tidak panggil ini eksplisit; thread
    baru di-start saat verify ulang. Disediakan untuk safety jaga-jaga.
    """
    global _HEARTBEAT_STOP
    _HEARTBEAT_STOP = threading.Event()
