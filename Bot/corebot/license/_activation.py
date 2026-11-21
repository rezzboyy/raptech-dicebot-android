"""UX activation prompt + verification animation.

Diekstrak dari `license/check.py` (Fase 4 perapihan, Step K-4).
Bridge antara user input (terminal) dan API redeem.

Public API (di-re-export oleh `license/check.py`):
    - `_run_verification_animation(duration, stop_event, final_event)`
    - `_verify_with_animation(code, machine_id, min_duration)`
    - `_prompt_license_interactive()` -> LicenseInfo
    - `_try_save_key(key)` -> Path | None
    - `_print_activation_success(info, saved_path)`
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from ._codec import (
    get_machine_id,
    is_short_code,
    normalize_short_code,
    validate_license_string,
)
from ._persistence import save_license_key
from ._state import LicenseError, LicenseInfo


# Konstanta sinkron dengan check.py.
ACTIVATION_ANIMATION_SECONDS = 5.0
SUPPORT_CONTACT = "Hubungi WhatsApp Raptech: 087875671945"
REDEEM_API_URL = "https://raptech-license-web.netlify.app/api/redeem"
# Note: REDEEM_API_URL tidak baca env karena `redeem_short_code` masih
# di `check.py` yang punya copy sendiri. Aman duplikasi karena URL
# konstanta default.


def _run_verification_animation(
    duration: float,
    stop_event: threading.Event,
    final_event: threading.Event,
) -> None:
    """Animasi spinner verifikasi. Loop sampai stop_event di-set ATAU
    duration tercapai, mana yang lebih dulu. Kalau final_event di-set,
    spinner berhenti dan baris di-clear."""
    frames = "|/-\\"
    messages = [
        "Menghubungkan ke server Raptech",
        "Memverifikasi kode aktivasi",
        "Mengecek validitas kode",
        "Menerbitkan lisensi",
        "Menyiapkan akses bot",
    ]
    start = time.monotonic()
    frame_idx = 0
    while not final_event.is_set():
        elapsed = time.monotonic() - start
        if elapsed >= duration and stop_event.is_set():
            break
        msg_idx = min(int(elapsed / max(duration / len(messages), 0.5)), len(messages) - 1)
        spinner = frames[frame_idx % len(frames)]
        line = f"  [{spinner}] {messages[msg_idx]}..."
        sys.stdout.write("\r" + line.ljust(60))
        sys.stdout.flush()
        frame_idx += 1
        time.sleep(0.1)
    # Clear baris animasi
    sys.stdout.write("\r" + " " * 64 + "\r")
    sys.stdout.flush()


def _verify_with_animation(
    code: str,
    machine_id: str | None,
    min_duration: float = ACTIVATION_ANIMATION_SECONDS,
) -> str:
    """Jalankan redeem API call sambil tampilkan animasi minimal `min_duration`
    detik. Return license key kalau sukses, raise LicenseError kalau gagal."""
    # Lazy import `redeem_short_code` dari `check.py` untuk hindari
    # circular dep (check.py meng-re-export modul ini).
    from .check import redeem_short_code

    stop_event = threading.Event()  # signal: API done
    final_event = threading.Event()  # signal: animation should fully stop
    result_holder: dict = {}

    def worker() -> None:
        try:
            result_holder["key"] = redeem_short_code(code, machine_id=machine_id)
        except LicenseError as exc:
            result_holder["error"] = exc
        finally:
            stop_event.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    animation_thread = threading.Thread(
        target=_run_verification_animation,
        args=(min_duration, stop_event, final_event),
        daemon=True,
    )
    animation_thread.start()

    # Tunggu API selesai
    thread.join(timeout=30)
    elapsed = 0.0
    # Pastikan animasi minimal jalan `min_duration` detik (UX lebih meyakinkan)
    start = time.monotonic()
    while elapsed < min_duration:
        if not animation_thread.is_alive():
            break
        time.sleep(0.05)
        elapsed = time.monotonic() - start

    final_event.set()
    animation_thread.join(timeout=1.0)

    if "error" in result_holder:
        raise result_holder["error"]
    key = result_holder.get("key")
    if not key:
        raise LicenseError("Verifikasi gagal: server tidak return license.")
    return key


def _prompt_license_interactive() -> LicenseInfo:
    """Tampilkan banner Raptech, minta user input kode aktivasi, validate &
    save. Loop sampai dapet aktivasi sukses atau user cancel."""
    from ..ui import cyber as ui

    ui.screen_activation_prompt(SUPPORT_CONTACT)

    while True:
        try:
            raw = input(ui.cyber_input_prompt()).strip()
        except (EOFError, KeyboardInterrupt):
            sys.stdout.write(f"\n  {ui.C.RED}[!]{ui.C.RESET} Aktivasi dibatalkan.\n")
            raise SystemExit(2) from None

        if not raw:
            sys.stdout.write(f"  {ui.C.YELLOW}[!]{ui.C.RESET} Input kosong. Coba lagi.\n")
            continue
        if raw.lower() in {"cancel", "exit", "quit", "/cancel"}:
            sys.stdout.write(f"\n  {ui.C.RED}[!]{ui.C.RESET} Aktivasi dibatalkan.\n")
            raise SystemExit(2)

        # Path A: short code 10-char -> redeem ke server
        if is_short_code(raw):
            cleaned = normalize_short_code(raw)
            pretty = f"{cleaned[:5]}-{cleaned[5:]}"
            ui.screen_verifying(pretty)
            try:
                machine_id = get_machine_id()
                key = _verify_with_animation(cleaned, machine_id=machine_id)
                info = validate_license_string(key)
            except LicenseError as exc:
                ui.screen_activation_error(str(exc), SUPPORT_CONTACT)
                continue
            saved_path = _try_save_key(key)
            _print_activation_success(info, saved_path)
            return info

        # Path B: full license key (RAPTECH-...) atau JSON - validate offline
        try:
            info = validate_license_string(raw)
        except LicenseError as exc:
            ui.screen_activation_error(str(exc), SUPPORT_CONTACT)
            continue

        saved_path = _try_save_key(raw)
        _print_activation_success(info, saved_path)
        return info


def _try_save_key(key: str) -> Path | None:
    try:
        return save_license_key(key)
    except OSError as exc:
        sys.stdout.write(
            f"[LICENSE] Gagal simpan license: {exc}\n"
            "          Lanjut tanpa save (next launch akan minta lagi).\n"
        )
        return None


def _print_activation_success(info: LicenseInfo, saved_path: Path | None) -> None:
    from ..ui import cyber as ui

    expires_str = info.expires_at.strftime("%d %B %Y %H:%M UTC")
    days = info.days_left
    if days < 1:
        remaining = f"{days * 24:.1f} jam"
    else:
        remaining = f"{days:.1f} hari"
    ui.screen_activation_success(
        info.customer, expires_str, remaining,
        str(saved_path.name) if saved_path else "(memory only)",
    )
