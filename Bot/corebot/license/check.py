"""Validasi lisensi berbasis waktu untuk Raptech Engine.

Lisensi diterbitkan oleh website generator (Next.js) yang menandatangani
payload JSON pakai HMAC-SHA256 dengan shared secret. License diserialkan
sebagai SINGLE-STRING KEY format:

    RAPTECH-<base64url(canonical_json_with_signature)>

Format ini gampang di-copy lewat WhatsApp/email dan otomatis di-decode
balik jadi struktur JSON internal:

    {
      "version": 1,
      "customer": "<nama / email>",
      "issued_at": "2025-01-01T00:00:00Z",
      "expires_at": "2025-04-01T00:00:00Z",
      "machine_id": "optional - kalau diisi, harus cocok",
      "signature": "<hex hmac-sha256>"
    }

Signature dihitung dari canonical JSON (sorted keys, no whitespace) atas
field selain `signature` itu sendiri.

File `license.json` di disk menyimpan key string ini, bukan struktur JSON-nya.
Tujuannya supaya bot bisa nge-prompt user paste key sekali lalu auto-save.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


LICENSE_FILENAME = "license.json"
LICENSE_KEY_PREFIX = "RAPTECH-"
LICENSE_ENV_VAR = "RAPTECH_LICENSE_PATH"
SECRET_ENV_VAR = "RAPTECH_LICENSE_SECRET"
REDEEM_API_URL = os.getenv(
    "RAPTECH_REDEEM_URL",
    "https://raptech-license-web.netlify.app/api/redeem",
)
CHECK_API_URL = os.getenv(
    "RAPTECH_CHECK_URL",
    "https://raptech-license-web.netlify.app/api/check",
)

# Heartbeat config
HEARTBEAT_INTERVAL_SECONDS = 3 * 60  # cek revocation tiap 3 menit
HEARTBEAT_GRACE_DAYS = 7  # offline mode masih boleh sampai N hari
HEARTBEAT_CACHE_FILENAME = ".raptech_heartbeat"

# Clock skew tolerance (detik). Penting karena server signing (Netlify) dan
# komputer user bisa beda waktu beberapa detik. Tanpa toleransi, lisensi
# yang baru di-generate kadang ditolak karena issued_at "di masa depan".

# Threshold untuk peringatan visible ke user saat boot.
WARN_DAYS_THRESHOLD = 7

# Info kontak yang ditampilkan ke user saat lisensi error/expired.
# Ganti sesuai channel support yang kamu pakai (telegram, email, whatsapp).
SUPPORT_CONTACT = "Hubungi WhatsApp Raptech: 087875671945"

# Shared secret. WAJIB diset sama persis dengan environment variable
# `RAPTECH_LICENSE_SECRET` di Netlify (server-side) saat generate lisensi.
#
# DI PRODUKSI: jangan hardcode di sini kalau repo public.
# Cara aman:
#   1. Set environment variable RAPTECH_LICENSE_SECRET di mesin user
#      (lewat installer atau dokumentasi setup), atau
#   2. Inject saat build pyinstaller via build-time variable
#      (lihat scripts/build/build_release.py).
#
# Default ini sengaja string kosong â€” bot akan tetap jalan untuk dev,
# tapi license production bertanda tangan secret asli akan ditolak
# karena signature tidak akan cocok. Aman buat repo public.


# Re-export tipe dasar dari `_state` (Step K-2 — bersih back-compat).
from ._state import (  # noqa: E402
    LicenseError,
    LicenseInfo,
    LicenseRevoked,
)


# Re-export crypto helpers dari `_codec` (Step K-2).
from ._codec import (  # noqa: E402
    DEFAULT_SECRET,
    decode_license_key,
    encode_license_key,
    get_machine_id,
    is_short_code,
    normalize_short_code,
    parse_license_input,
    validate_license_string,
)


# Re-export heartbeat helpers dari `_heartbeat` (Step K-3).
from ._heartbeat import (  # noqa: E402
    _delete_license_artifacts,
    heartbeat_check,
    start_background_heartbeat,
)


# Re-export persistence helpers dari `_persistence` (Step K-5).
from ._persistence import (  # noqa: E402
    find_license_path,
    load_license,
    save_license_key,
)


# Re-export UX activation flow dari `_activation` (Step K-4).
from ._activation import (  # noqa: E402
    _prompt_license_interactive,
)
def _client_user_agent() -> str:
    """Build a user-agent string yang informatif untuk admin lihat di
    redemption record (bukan untuk fingerprinting/auth)."""
    parts = [f"RaptechBot/{sys.platform}"]
    try:
        import platform as _pf

        parts.append(_pf.platform(terse=True))
        parts.append(f"hostname={_pf.node()}")
    except Exception:
        pass
    return " ".join(p for p in parts if p)


def redeem_short_code(code: str, machine_id: str | None = None,
                      timeout: float = 20.0) -> str:
    """Tukar short code ke license key string via API server.

    Return: license key (string `RAPTECH-...`).
    Raise LicenseError kalau gagal (network, code invalid, sudah dipakai
    di mesin lain, dll).
    """
    cleaned = normalize_short_code(code)
    if not is_short_code(cleaned):
        raise LicenseError(
            "Format kode salah. Harus 10 karakter (5 huruf + 5 angka)."
        )
    body: dict = {"code": cleaned}
    if machine_id:
        body["machineId"] = machine_id
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        REDEEM_API_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": _client_user_agent(),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            err_body = json.loads(exc.read().decode("utf-8"))
            raise LicenseError(
                err_body.get("error") or f"Server error HTTP {exc.code}"
            ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise LicenseError(f"Server error HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise LicenseError(
            f"Tidak bisa terhubung ke server aktivasi: {exc.reason}. "
            "Periksa koneksi internet."
        ) from exc
    except (TimeoutError, OSError) as exc:
        raise LicenseError(f"Koneksi server timeout: {exc}") from exc

    key = data.get("key")
    if not isinstance(key, str) or not key.startswith(LICENSE_KEY_PREFIX):
        raise LicenseError("Server response tidak punya license key valid.")
    return key
from . import _state as _state_mod  # noqa: E402


def get_revocation_reason() -> str | None:
    """Dipanggil oleh main loop untuk cek apakah harus restart ke prompt
    aktivasi. None kalau tidak ada revoke."""
    return _state_mod.get_revocation_reason()


def clear_revocation_reason() -> None:
    _state_mod.clear_revocation_reason()


def stop_background_heartbeat() -> None:
    """Stop background thread (dipanggil saat bot mau exit / restart)."""
    _state_mod.stop_background_heartbeat()
def verify_license_or_exit() -> LicenseInfo:
    """Entry-point yang dipanggil sebelum bot.py membuka CLI.

    Flow:
      1. Cari license file di candidate paths
      2. Kalau ada -> validate, return atau exit kalau invalid
      3. Kalau tidak ada -> prompt user paste key, validate, save, return
    """
    if os.getenv("RAPTECH_DEV_MODE") == "1":
        from datetime import datetime, timedelta, timezone
        from pathlib import Path
        from ..ui import cyber as ui

        info = LicenseInfo(
            customer="Developer (Bypass Mode)",
            issued_at=datetime.now(timezone.utc) - timedelta(days=1),
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            machine_id=None,
            code=None,
            days_left=365.0,
            path=Path("license.json"),
        )
        expires_str = info.expires_at.strftime("%d %B %Y · %H:%M UTC")
        ui.license_status_line(info.customer, "365.0 hari", expires_str)
        sys.stdout.write(
            f"  {ui.C.MAGENTA}[NET]{ui.C.RESET} server check "
            f"{ui.C.BGREEN}DEV_BYPASS_OK{ui.C.RESET}\n"
        )
        sys.stdout.flush()
        return info

    interactive = bool(sys.stdin and sys.stdin.isatty())
    existing = find_license_path()

    info: LicenseInfo | None = None
    if existing is not None:
        try:
            info = load_license(existing)
        except LicenseError as exc:
            from ..ui import cyber as ui

            ui.screen_activation_error(
                f"Lisensi tidak valid: {exc}", SUPPORT_CONTACT
            )
            sys.stderr.flush()
            _delete_license_artifacts()
            if not interactive:
                raise SystemExit(2)
            existing = None  # fall through ke prompt
    if existing is None or info is None:
        if not interactive:
            sys.stderr.write(
                "\n[LICENSE] License key belum ada dan stdin bukan TTY.\n"
                f"[LICENSE] {SUPPORT_CONTACT}\n"
            )
            raise SystemExit(2)
        info = _prompt_license_interactive()

    days = info.days_left
    if days < 1:
        hours = days * 24
        remaining = f"{hours:.1f} jam"
    else:
        remaining = f"{days:.1f} hari"

    expires_str = info.expires_at.strftime("%d %B %Y · %H:%M UTC")

    # Cyber-style status panel kalau bukan dari prompt baru (saat boot
    # ulang dengan license tersimpan). Saat baru selesai aktivasi,
    # _print_activation_success sudah cetak panel-nya.
    if existing is not None:
        from ..ui import cyber as ui

        ui.license_status_line(info.customer, remaining, expires_str)
    else:
        # Already printed via _print_activation_success during activation.
        pass

    # Online heartbeat: cek server kalau code masih ada / belum revoked.
    # Skip kalau license old-format (no `code` field).
    if info.code:
        from ..ui import cyber as ui

        try:
            status = heartbeat_check(info)
        except LicenseRevoked as exc:
            ui.screen_revoked(str(exc), SUPPORT_CONTACT)
            sys.stderr.flush()
            _delete_license_artifacts()
            if not interactive:
                raise SystemExit(2)
            return verify_license_or_exit()
        if status == "active":
            sys.stdout.write(
                f"  {ui.C.MAGENTA}[NET]{ui.C.RESET} server check "
                f"{ui.C.BGREEN}OK{ui.C.RESET}\n"
            )
            sys.stdout.flush()
        elif status == "offline":
            pass
        start_background_heartbeat(info)

    # Warning ekstra kalau sisa lisensi <= threshold.
    if 0 < days <= WARN_DAYS_THRESHOLD:
        from ..ui import cyber as ui

        ui.screen_warning_expiring(remaining, SUPPORT_CONTACT)
    sys.stdout.flush()
    return info


__all__ = [
    "DEFAULT_SECRET",
    "HEARTBEAT_GRACE_DAYS",
    "HEARTBEAT_INTERVAL_SECONDS",
    "LICENSE_ENV_VAR",
    "LICENSE_FILENAME",
    "LICENSE_KEY_PREFIX",
    "LicenseError",
    "LicenseInfo",
    "LicenseRevoked",
    "SECRET_ENV_VAR",
    "SUPPORT_CONTACT",
    "decode_license_key",
    "encode_license_key",
    "find_license_path",
    "get_machine_id",
    "heartbeat_check",
    "is_short_code",
    "load_license",
    "normalize_short_code",
    "parse_license_input",
    "redeem_short_code",
    "save_license_key",
    "start_background_heartbeat",
    "validate_license_string",
    "verify_license_or_exit",
]
