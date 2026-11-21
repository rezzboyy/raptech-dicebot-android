"""Heartbeat checker untuk lisensi.

Diekstrak dari `license/check.py` (Fase 4 perapihan, Step K-3).

Bertanggung jawab:
  - Cache heartbeat di disk (offline grace period)
  - Background thread yang ping server tiap N menit
  - Trigger revocation flag + interrupt main thread saat license dibatalkan

Public API (di-re-export oleh `license/check.py`):
    - `heartbeat_check(info, *, silent)` -> str
    - `start_background_heartbeat(info)`
    - `_check_revocation(code, timeout)` (private — dipakai modul ini)
    - `_heartbeat_cache_path()`, `_read_heartbeat_cache()`, `_write_heartbeat_cache()`
    - `_interrupt_main_thread()`, `_delete_license_artifacts()`
"""
from __future__ import annotations

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ..config import runtime_root
from . import _state as _state_mod
from ._state import LicenseInfo, LicenseRevoked


# ---- Constants -------------------------------------------------------
# Heartbeat config — sinkron dengan check.py.
HEARTBEAT_INTERVAL_SECONDS = 3 * 60  # cek revocation tiap 3 menit
HEARTBEAT_GRACE_DAYS = 7  # offline mode masih boleh sampai N hari
HEARTBEAT_CACHE_FILENAME = ".raptech_heartbeat"

CHECK_API_URL = os.getenv(
    "RAPTECH_CHECK_URL",
    "https://raptech-license-web.netlify.app/api/check",
)

SUPPORT_CONTACT = "Hubungi WhatsApp Raptech: 087875671945"


def _client_user_agent() -> str:
    """Build user-agent string untuk admin lihat di redemption record."""
    parts = [f"RaptechBot/{sys.platform}"]
    try:
        import platform as _pf

        parts.append(_pf.platform(terse=True))
        parts.append(f"hostname={_pf.node()}")
    except Exception:
        pass
    return " ".join(p for p in parts if p)


def _heartbeat_cache_path() -> Path:
    return runtime_root() / HEARTBEAT_CACHE_FILENAME


def _read_heartbeat_cache() -> dict | None:
    path = _heartbeat_cache_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_heartbeat_cache(payload: dict) -> None:
    path = _heartbeat_cache_path()
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass


def _check_revocation(code: str, timeout: float = 10.0) -> dict:
    """Panggil /api/check dengan code. Return dict status atau raise."""
    payload = json.dumps({"code": code}).encode("utf-8")
    req = urllib.request.Request(
        CHECK_API_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": _client_user_agent(),
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def heartbeat_check(info: LicenseInfo, *, silent: bool = False) -> str:
    """Lakukan heartbeat ke server.

    Return: status string ("active", "revoked", "expired", "offline").
    Raise LicenseRevoked kalau status revoked/expired (caller harus exit).

    Strategi:
      - Kalau ga ada `code` di license (license old format), skip check (return "skipped")
      - Kalau call sukses dan status="active": update cache, return "active"
      - Kalau status="revoked": raise LicenseRevoked langsung
      - Kalau status="expired": raise LicenseRevoked
      - Kalau network error: cek cache. Kalau cache umurnya < grace period,
        return "offline". Kalau lebih dari grace, raise LicenseRevoked.
    """
    if not info.code:
        return "skipped"

    try:
        result = _check_revocation(info.code)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        cache = _read_heartbeat_cache()
        if cache and cache.get("code") == info.code:
            try:
                last_ok_iso = cache.get("last_ok_at")
                if last_ok_iso:
                    last_ok = datetime.fromisoformat(str(last_ok_iso))
                    if last_ok.tzinfo is None:
                        last_ok = last_ok.replace(tzinfo=timezone.utc)
                    age = datetime.now(timezone.utc) - last_ok
                    if age.total_seconds() < HEARTBEAT_GRACE_DAYS * 86400:
                        if not silent:
                            sys.stdout.write(
                                "[LICENSE] Mode offline (server tidak bisa dihubungi). "
                                f"Grace {HEARTBEAT_GRACE_DAYS - int(age.total_seconds()/86400)} hari tersisa.\n"
                            )
                        return "offline"
            except (TypeError, ValueError):
                pass
        # Tidak ada cache valid -> tolak
        raise LicenseRevoked(
            "Tidak bisa terhubung ke server aktivasi dan grace period habis. "
            "Periksa koneksi internet."
        )

    status = str(result.get("status", "unknown"))
    if status == "active":
        _write_heartbeat_cache({
            "code": info.code,
            "last_ok_at": datetime.now(timezone.utc).isoformat(),
            "customer": info.customer,
        })
        return "active"
    if status == "revoked":
        raise LicenseRevoked(
            "Lisensi sudah dibatalkan oleh admin. " + SUPPORT_CONTACT
        )
    if status == "expired":
        raise LicenseRevoked(
            "Lisensi sudah expired di server. " + SUPPORT_CONTACT
        )
    # invalid / unknown - reject
    raise LicenseRevoked(f"Status lisensi tidak valid: {status}")


def _interrupt_main_thread() -> None:
    """Simulasi Ctrl+C ke main thread, supaya `input()` blocking di CLI
    bisa break. Pakai _thread.interrupt_main() di Windows."""
    try:
        import _thread
        _thread.interrupt_main()
    except Exception:
        pass


def _delete_license_artifacts() -> None:
    """Hapus license.json + heartbeat cache supaya next launch ngga
    auto-load license yang sudah revoked.

    Lazy import `find_license_path` dari `check.py` (top-level module)
    karena persistence belum diekstrak ke modul terpisah.
    """
    from .check import find_license_path

    license_path = find_license_path()
    if license_path:
        try:
            license_path.unlink()
        except OSError:
            pass
    cache = _heartbeat_cache_path()
    if cache.exists():
        try:
            cache.unlink()
        except OSError:
            pass


def start_background_heartbeat(info: LicenseInfo) -> None:
    """Start daemon thread yang panggil heartbeat tiap interval. Kalau
    server bilang revoked, set flag revocation. Bot main loop cek flag
    ini dan restart ke prompt aktivasi (tidak force-exit)."""
    if not info.code:
        return  # license old format, skip
    existing, _stop = _state_mod.heartbeat_thread_state()
    if existing and existing.is_alive():
        return  # already running
    # Reset stop event supaya thread baru bisa berjalan. Tanpa ini, kalau
    # _stop sudah di-set dari session sebelumnya (revokasi / restart),
    # loop langsung exit tanpa nunggu interval pertama.
    _stop.clear()

    def loop() -> None:
        from ..ui import cyber as ui

        _, stop_event = _state_mod.heartbeat_thread_state()
        while not stop_event.wait(HEARTBEAT_INTERVAL_SECONDS):
            try:
                status = heartbeat_check(info, silent=True)
                if status == "active":
                    sys.stdout.write(
                        ui.heartbeat_tick(datetime.now().strftime("%H:%M:%S")) + "\n"
                    )
                    sys.stdout.flush()
            except LicenseRevoked as exc:
                ui.screen_revoked(str(exc), SUPPORT_CONTACT)
                sys.stderr.flush()
                _state_mod.set_revocation_reason(str(exc))
                _delete_license_artifacts()
                _state_mod.stop_background_heartbeat()
                _interrupt_main_thread()
                return
            except Exception:
                continue

    thread = threading.Thread(target=loop, daemon=True, name="raptech-heartbeat")
    _state_mod.set_heartbeat_thread(thread)
    thread.start()
