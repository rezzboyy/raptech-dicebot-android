"""Menu Change Email khusus Wolfbet.

Fitur:
- Prompt user input email baru
- Validasi format basic (ada '@' dan '.')
- Kirim ke endpoint POST /v1/user/email/change (di wolfbet.win)
- Coba dulu dengan captcha token kosong (kebanyakan request yang sudah
  authenticated via Bearer diterima server).
- Kalau server tolak dengan pesan captcha/recaptcha, fallback ke manual
  paste captcha token (user solve di browser lalu paste).
- Tampilkan response message dari server ke user.

Setelah request sukses, user perlu klik link konfirmasi di inbox email
baru untuk finalize perubahan (server hanya kirim verification email).

Hanya untuk site Wolfbet. Caller harus cek site sebelum panggil.
"""
from __future__ import annotations

import re

try:
    from colorama import Fore  # type: ignore
except Exception:
    class Fore:  # type: ignore[no-redef]
        CYAN = "\x1b[36m"


from ._console import clear_screen, pause, section
from ._state import get_theme


# Regex email sederhana — hanya validasi struktur dasar, biar server
# yang punya kata final. Kita gak strict di sisi client.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Marker untuk deteksi bahwa server butuh captcha manual.
_CAPTCHA_MARKERS = ("captcha", "recaptcha", "g-recaptcha", "robot")


def _looks_like_email(value: str) -> bool:
    return bool(_EMAIL_RE.match((value or "").strip()))


def _is_captcha_error(err_msg: str) -> bool:
    low = (err_msg or "").lower()
    return any(m in low for m in _CAPTCHA_MARKERS)


def _prompt_email(theme, current: str = "") -> str:
    """Prompt user input email baru. Return string kosong kalau cancel."""
    print(theme.c("  Masukkan email baru (kosongkan untuk batal).", "dim"))
    if current:
        print(theme.c(f"  Email saat ini: {current}", "dim"))
    try:
        raw = input(theme.c("  Email baru: ", "accent", bold=True)).strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    return raw


def _prompt_captcha_token(theme) -> str:
    """Fallback: minta user paste captcha token manual."""
    print()
    print(theme.c("  Server meminta captcha untuk verifikasi.", "warning"))
    print(theme.c("  Cara ambil token:", "dim"))
    print(theme.c("    1. Buka wolfbet.win di browser (login dulu).", "dim"))
    print(theme.c("    2. F12 -> Network tab.", "dim"))
    print(theme.c("    3. Coba ubah email dari halaman Settings.", "dim"))
    print(theme.c("    4. Cari request 'email/change' -> tab Payload.", "dim"))
    print(theme.c("    5. Copy value 'g-recaptcha-response' dan paste di sini.", "dim"))
    print(theme.c("    Enter kosong = batal.", "dim"))
    print()
    try:
        raw = input(theme.c("  Captcha token: ", "accent", bold=True)).strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    return raw


def _render_result(theme, message: str, new_email: str) -> None:
    """Render success box dengan instruksi next-step."""
    print()
    print(theme.c("  Permintaan terkirim.", "success", bold=True))
    if message:
        print(theme.c(f"  Server: {message}", "muted"))
    print()
    print(theme.c(f"  Cek inbox email: {new_email}", "accent", bold=True))
    print(theme.c("  Klik link verifikasi di email tersebut untuk", "dim"))
    print(theme.c("  finalisasi perubahan alamat email di Wolfbet.", "dim"))
    print()
    print(theme.c("  Kalau tidak muncul, cek folder Spam / Promosi.", "dim"))


def _extract_message(response: dict) -> str:
    """Ambil field 'message' dari response (Wolfbet biasanya kirim ini)."""
    if not isinstance(response, dict):
        return ""
    for key in ("message", "msg", "detail"):
        val = response.get(key)
        if val:
            return str(val)
    return ""


def show_change_email(client) -> None:
    """Entry point menu change email.

    Args:
        client: instance WolfBetClient. Caller harus pastikan.
    """
    theme = get_theme()

    clear_screen()
    section("CHANGE EMAIL - WOLFBET", Fore.CYAN, False)
    print(theme.c("  Ubah alamat email akun Wolfbet.", "dim"))
    print(theme.c("  Server akan kirim link konfirmasi ke email baru.", "dim"))
    print()

    # Coba ambil email lama dari profile (best effort)
    current_email = ""
    try:
        profile = client.profile()
        current_email = (
            profile.get("email")
            or profile.get("user", {}).get("email")
            or ""
        )
    except Exception:
        pass

    new_email = _prompt_email(theme, current_email)
    if not new_email:
        print(theme.c("  Dibatalkan.", "dim"))
        pause()
        return

    if not _looks_like_email(new_email):
        print(theme.c(f"  Format email tidak valid: {new_email}", "danger"))
        pause()
        return

    if current_email and new_email.lower() == current_email.lower():
        print(theme.c("  Email baru sama dengan email saat ini. Dibatalkan.", "warning"))
        pause()
        return

    # Attempt 1: kirim dengan captcha token kosong.
    # Wolfbet reCAPTCHA v3 (invisible), untuk request authenticated
    # via Bearer biasanya server lebih toleran.
    print()
    print(theme.c("  Mengirim permintaan...", "dim"))
    try:
        response = client.change_email(new_email, captcha_token="")
    except Exception as exc:
        err_msg = str(exc)
        if _is_captcha_error(err_msg):
            # Fallback: prompt captcha token
            captcha_token = _prompt_captcha_token(theme)
            if not captcha_token:
                print(theme.c("  Dibatalkan.", "dim"))
                pause()
                return
            print()
            print(theme.c("  Mengirim ulang dengan captcha token...", "dim"))
            try:
                response = client.change_email(new_email, captcha_token=captcha_token)
            except Exception as exc2:
                print()
                print(theme.c(f"  Gagal: {exc2}", "danger"))
                pause()
                return
        else:
            print()
            print(theme.c(f"  Gagal: {err_msg}", "danger"))
            pause()
            return

    message = _extract_message(response)
    _render_result(theme, message, new_email)
    pause()
