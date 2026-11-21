"""License key codec + signature + payload validator.

Diekstrak dari `license/check.py` (Fase 4 perapihan, Step K-2).
Pure crypto/parsing layer — tidak ada I/O selain reading
`SECRET_ENV_VAR` dari environment dan baca machine ID.

Public API (di-re-export oleh `license/check.py`):
    - `encode_license_key(payload)` -> str
    - `decode_license_key(raw)` -> dict
    - `parse_license_input(raw)` -> dict
    - `validate_license_string(raw)` -> LicenseInfo
    - `_compute_signature(data)` -> str (private — dipakai issue_license CLI)
    - `_canonical_payload(data)` -> bytes (private)
    - `_parse_iso(value, field)` -> datetime
    - `_validate_payload(raw, source)` -> LicenseInfo
    - `normalize_short_code(raw)` -> str
    - `is_short_code(raw)` -> bool
    - `get_machine_id()` -> str
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ._state import LicenseError, LicenseInfo


# Konstanta yang dipakai modul ini. Sinkron dengan `check.py`.
LICENSE_KEY_PREFIX = "RAPTECH-"
SECRET_ENV_VAR = "RAPTECH_LICENSE_SECRET"

# Clock skew tolerance (detik). Penting karena server signing (Netlify)
# dan komputer user bisa beda waktu beberapa detik. Tanpa toleransi,
# lisensi yang baru di-generate kadang ditolak karena issued_at
# "di masa depan".
CLOCK_SKEW_SECONDS = 120

# Default secret. WAJIB diset sama persis dengan environment variable
# `RAPTECH_LICENSE_SECRET` di Netlify saat generate lisensi.
DEFAULT_SECRET = ""


def _shared_secret() -> bytes:
    return (os.getenv(SECRET_ENV_VAR) or DEFAULT_SECRET).encode("utf-8")


def _canonical_payload(data: dict) -> bytes:
    payload = {key: value for key, value in data.items() if key != "signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _compute_signature(data: dict) -> str:
    return hmac.new(_shared_secret(), _canonical_payload(data), hashlib.sha256).hexdigest()


def _parse_iso(value: str, field: str) -> datetime:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise LicenseError(f"Field '{field}' bukan tanggal ISO valid: {value}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_machine_id() -> str:
    """Stable machine identifier. Best-effort cross-platform.

    Windows: pakai registry MachineGuid kalau tersedia.
    Fallback: hash dari uuid.getnode() (MAC address).
    """
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                value, _ = winreg.QueryValueEx(key, "MachineGuid")
                return str(value).strip().lower()
        except OSError:
            pass
    node = uuid.getnode()
    return hashlib.sha256(f"node-{node}".encode("utf-8")).hexdigest()[:32]


def encode_license_key(payload: dict) -> str:
    """Bungkus payload signed jadi single-string key:
    RAPTECH-<base64url(canonical_json)>
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(canonical).decode("ascii").rstrip("=")
    return LICENSE_KEY_PREFIX + encoded


def decode_license_key(raw: str) -> dict:
    """Decode key string balik jadi dict payload. Raise LicenseError
    kalau format salah."""
    cleaned = (raw or "").strip().replace("\n", "").replace("\r", "").replace(" ", "")
    if not cleaned:
        raise LicenseError("License key kosong.")
    if not cleaned.startswith(LICENSE_KEY_PREFIX):
        raise LicenseError(
            f"License key harus diawali '{LICENSE_KEY_PREFIX}'. "
            "Pastikan tidak ada karakter terpotong saat copy-paste."
        )
    body = cleaned[len(LICENSE_KEY_PREFIX):]
    # base64url tanpa padding -> tambahkan padding
    padding = "=" * (-len(body) % 4)
    try:
        decoded = base64.urlsafe_b64decode(body + padding)
    except (binascii.Error, ValueError) as exc:
        raise LicenseError(f"License key tidak bisa di-decode: {exc}") from exc
    try:
        payload = json.loads(decoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LicenseError(f"License key tidak valid (JSON): {exc}") from exc
    if not isinstance(payload, dict):
        raise LicenseError("License key payload bukan object JSON.")
    return payload


def parse_license_input(raw: str) -> dict:
    """Smart-parse: kalau input mulai dengan 'RAPTECH-', treat as key string.
    Kalau dimulai '{', treat as raw JSON (untuk backward compat)."""
    cleaned = (raw or "").strip()
    if not cleaned:
        raise LicenseError("Input lisensi kosong.")
    if cleaned.startswith(LICENSE_KEY_PREFIX):
        return decode_license_key(cleaned)
    if cleaned.startswith("{"):
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LicenseError(f"JSON lisensi tidak valid: {exc}") from exc
        if not isinstance(data, dict):
            raise LicenseError("JSON lisensi bukan object.")
        return data
    raise LicenseError(
        f"Format lisensi tidak dikenal. Harus diawali '{LICENSE_KEY_PREFIX}' "
        "atau berupa JSON object."
    )


_SHORT_CODE_RE = re.compile(r"^[A-Z0-9]{10}$")


def normalize_short_code(raw: str) -> str:
    """Bersihkan input: uppercase, hapus dash/spasi/non-alphanumeric."""
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


def is_short_code(raw: str) -> bool:
    """True kalau input cocok format short code 10-char (5 huruf + 5 angka)."""
    cleaned = normalize_short_code(raw)
    if not _SHORT_CODE_RE.match(cleaned):
        return False
    letters = sum(1 for ch in cleaned if ch.isalpha())
    digits = sum(1 for ch in cleaned if ch.isdigit())
    return letters == 5 and digits == 5


def _validate_payload(raw: dict, source: Path | None) -> LicenseInfo:
    required = ("customer", "issued_at", "expires_at", "signature")
    missing = [field for field in required if field not in raw]
    if missing:
        raise LicenseError(f"Lisensi kekurangan field: {', '.join(missing)}")

    expected_signature = _compute_signature(raw)
    provided_signature = str(raw.get("signature") or "")
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise LicenseError("Signature lisensi tidak cocok. File mungkin sudah dimodifikasi.")

    issued_at = _parse_iso(str(raw["issued_at"]), "issued_at")
    expires_at = _parse_iso(str(raw["expires_at"]), "expires_at")
    if expires_at <= issued_at:
        raise LicenseError("Tanggal expires_at harus lebih besar dari issued_at.")

    machine_id_required = raw.get("machine_id")
    if machine_id_required:
        current = get_machine_id()
        if str(machine_id_required).lower() != current.lower():
            raise LicenseError(
                "Lisensi terikat ke mesin lain. Hubungi admin untuk lisensi baru."
            )

    now = datetime.now(timezone.utc)
    skew = timedelta(seconds=CLOCK_SKEW_SECONDS)
    if now + skew < issued_at:
        raise LicenseError(
            "Lisensi belum aktif (issued_at di masa depan). Periksa jam sistem."
        )
    delta = expires_at - now
    days_left = delta.total_seconds() / 86400.0
    if delta + skew <= timedelta(0):
        raise LicenseError(
            f"Lisensi sudah expired sejak {expires_at.isoformat()}."
        )

    return LicenseInfo(
        customer=str(raw.get("customer") or "-"),
        issued_at=issued_at,
        expires_at=expires_at,
        machine_id=str(machine_id_required) if machine_id_required else None,
        code=str(raw.get("code")).upper() if raw.get("code") else None,
        days_left=days_left,
        path=source if source else Path("(memory)"),
    )


def validate_license_string(raw: str) -> LicenseInfo:
    """Validasi license key/JSON tanpa baca file. Dipakai saat user paste
    key di prompt."""
    payload = parse_license_input(raw)
    return _validate_payload(payload, source=None)
