"""Prompt helpers untuk CLI.

Diekstrak dari `cli/__init__.py` (Fase 2 perapihan, Step F).
Tidak menyentuh state runtime selain `get_theme()` untuk styling.

Public API (di-re-export oleh `cli/__init__.py`):
    - `prompt_web_api`
    - `prompt_select`
    - `prompt_float_default`
    - `_drain_input_buffer`
"""
from __future__ import annotations

try:
    import msvcrt  # type: ignore
except Exception:
    msvcrt = None  # type: ignore

try:
    from colorama import Fore  # type: ignore
except Exception:
    class Fore:  # type: ignore[no-redef]
        CYAN = "\x1b[36m"

from ..clients import COOKIE_BASED_SITES, JWT_BASED_SITES
from ..config import DEFAULT_SITE
from ._console import clear_screen, normalize_token, section
from ._state import get_theme


def _drain_input_buffer() -> None:
    """Bersihkan keystroke yang nyangkut di buffer sebelum prompt baru.

    Berguna untuk cegah kasus user paste cookie panjang yang isinya pecah
    ke beberapa input prompt karena newline tersembunyi dari clipboard.
    """
    if msvcrt is None:
        return
    try:
        while msvcrt.kbhit():
            msvcrt.getwch()
    except Exception:
        pass


def prompt_web_api(default: str = "", no_color: bool = False, *, site: str = DEFAULT_SITE) -> str:
    site_lower = site.lower()
    is_cookie_site = site_lower in COOKIE_BASED_SITES
    is_jwt_site = site_lower in JWT_BASED_SITES
    is_betfury = site_lower == "betfury"

    if is_betfury:
        return _prompt_betfury(default=default, no_color=no_color)

    if is_jwt_site:
        label = "AUTH TOKEN"
    elif is_cookie_site:
        label = "COOKIE HEADER"
    else:
        label = "WEB API"
    section(label, Fore.CYAN, no_color)

    theme = get_theme()
    if is_jwt_site:
        is_nuts = site_lower == "nuts"
        is_pasino = site_lower == "pasino"
        print(theme.c("Site ini pakai auth token dari localStorage browser.", "dim"))
        print(theme.c("Login di browser, buka DevTools -> Application -> Local Storage", "dim"))
        if is_nuts:
            print(theme.c("-> https://nuts.gg, copy value dari key 'auth_token'.", "dim"))
            print(theme.c("Format: paste full JWT (mulai 'eyJ...').", "dim"))
        elif is_pasino:
            print(theme.c("-> https://pasino.com, login lalu buka DevTools (F12).", "dim"))
            print(theme.c("Application > Local Storage > https://pasino.com", "dim"))
            print(theme.c("> copy value dari key 'token' (64-char hex).", "dim"))
            print(theme.c("Cloudflare di-bypass otomatis (TLS impersonation),", "dim"))
            print(theme.c("tidak butuh cookie tambahan.", "dim"))
            print(theme.c(
                "Token di-refresh otomatis tiap 4 menit (Pasino /account/refresh-token),",
                "dim",
            ))
            print(theme.c("jadi cukup paste sekali — bot tidak akan disconnect.", "dim"))
        else:
            print(theme.c(f"-> {site_lower}, copy auth token dari Local Storage.", "dim"))
    elif is_cookie_site:
        print(theme.c("Site ini pakai cookie-based auth (login email+password punya captcha).", "dim"))
        print(theme.c("Login manual di browser, buka DevTools -> Application -> Cookies", "dim"))
        print(theme.c("(atau Network tab -> request /process.php -> copy header 'cookie').", "dim"))
        print(theme.c("Format: 'name=value; name=value; ...' (paste sekaligus 1 baris).", "dim"))
    if default:
        print(theme.c("Enter kosong saat default tersedia = pakai nilai tersimpan.", "dim"))
    print(theme.c("Ketik '/cancel' untuk kembali ke menu.", "dim"))

    g = theme.glyphs
    if is_jwt_site:
        placeholder = "Paste auth token"
    elif is_cookie_site:
        placeholder = "Paste cookie header"
    else:
        placeholder = "Paste Web API"
    prompt_text = f"{theme.c(g.prompt, 'accent', bold=True)} {placeholder}: "

    _drain_input_buffer()

    while True:
        raw = input(prompt_text).strip()
        if raw.lower() == "/cancel":
            return ""
        if not raw:
            if default:
                return default
            print(theme.c(
                "Input kosong. Paste lagi, atau ketik '/cancel' untuk kembali.",
                "warning",
            ))
            continue
        if is_jwt_site or is_cookie_site:
            return raw
        return normalize_token(raw)


def _prompt_betfury(default: str = "", no_color: bool = False) -> str:
    """Prompt khusus Betfury: token dan UID diinput terpisah."""
    section("AUTH TOKEN — BETFURY", Fore.CYAN, no_color)
    theme = get_theme()
    g = theme.glyphs

    print(theme.c("Login di browser, buka DevTools -> Application -> Local Storage", "dim"))
    print(theme.c("-> https://betfury.com", "dim"))
    print(theme.c("Ketik '/cancel' untuk kembali ke menu.", "dim"))
    print()

    # Parse default kalau ada (format: token;uid=xxx)
    default_token = ""
    default_uid = ""
    if default and ";" in default:
        parts = default.split(";", 1)
        default_token = parts[0].strip()
        rest = parts[1].strip()
        if rest.lower().startswith("uid="):
            default_uid = rest[4:].strip()

    # --- Step 1: token ---
    print(theme.c("Step 1/2 — Copy value dari key 'token'", "accent", bold=True))
    prompt_token = f"{theme.c(g.prompt, 'accent', bold=True)} Paste TOKEN: "
    _drain_input_buffer()
    while True:
        raw = input(prompt_token).strip()
        if raw.lower() == "/cancel":
            return ""
        if not raw:
            if default_token:
                raw = default_token
            else:
                print(theme.c("Token kosong. Paste lagi atau ketik '/cancel'.", "warning"))
                continue
        token = raw
        break

    # --- Step 2: UID ---
    print()
    print(theme.c("Step 2/2 — Copy value dari key 'uid'", "accent", bold=True))
    prompt_uid = f"{theme.c(g.prompt, 'accent', bold=True)} Paste UID: "
    _drain_input_buffer()
    while True:
        raw = input(prompt_uid).strip()
        if raw.lower() == "/cancel":
            return ""
        if not raw:
            if default_uid:
                raw = default_uid
            else:
                print(theme.c("UID kosong. Paste lagi atau ketik '/cancel'.", "warning"))
                continue
        uid = raw
        break

    return f"{token};uid={uid}"


def prompt_select(
    options: list[str],
    prompt: str,
    default: str | None = None,
    *,
    show_list: bool = True,
    no_color: bool = False,
) -> str:
    if not options:
        return ""
    default_index = 0
    if default:
        for index, value in enumerate(options):
            if value.upper() == default.upper():
                default_index = index
                break
    theme = get_theme()
    g = theme.glyphs
    while True:
        if prompt:
            print(theme.section(prompt.rstrip(":"), role="primary"))
        if show_list:
            width = len(str(len(options)))
            for index, option in enumerate(options, 1):
                is_default = index - 1 == default_index
                marker = theme.c(g.arrow, "accent", bold=True) if is_default else " "
                num = theme.c(f"{str(index).rjust(width)}", "accent" if is_default else "dim")
                label = theme.c(option, "muted", bold=is_default)
                print(f" {marker} [{num}] {label}")
        prompt_text = (
            f"{theme.c(g.prompt, 'accent', bold=True)} Select "
            f"[{theme.c(str(default_index + 1), 'accent', bold=True)}] "
        )
        raw = input(prompt_text).strip()
        clear_screen()
        if not raw:
            return options[default_index]
        if raw.isdigit():
            picked = int(raw)
            if 1 <= picked <= len(options):
                return options[picked - 1]
        print(theme.c("Pilihan tidak valid.", "warning"))


def prompt_float_default(label: str, current: float, min_value: float = 0.0) -> float:
    theme = get_theme()
    g = theme.glyphs
    while True:
        hint = theme.c(f"[Enter={current}]", "dim")
        prompt_text = f"{theme.c(g.prompt, 'accent', bold=True)} {label} {hint}: "
        raw = input(prompt_text).strip()
        clear_screen()
        if raw == "":
            return float(current)
        try:
            value = float(raw)
        except ValueError:
            print(theme.c("Please enter a valid number.", "warning"))
            continue
        if value < min_value:
            print(theme.c(f"Minimum value is {min_value}.", "warning"))
            continue
        return value


def prompt_select_site(default_site: str, *, no_color: bool = False) -> str:
    """Pilih situs dari daftar `available_sites()`. Return slug terpilih."""
    from ..clients import available_sites, site_metadata

    sites = available_sites()
    if not sites:
        return default_site
    metas = [site_metadata(s) for s in sites]
    section("SELECT SITE", Fore.CYAN, no_color)
    theme = get_theme()
    g = theme.glyphs
    width_idx = len(str(len(sites)))
    default_index = next(
        (i for i, s in enumerate(sites) if s == default_site.lower()),
        0,
    )
    for index, meta in enumerate(metas, 1):
        is_default = (index - 1) == default_index
        marker = theme.c(g.arrow, "accent", bold=True) if is_default else " "
        num = theme.c(
            f"{str(index).rjust(width_idx)}",
            "accent" if is_default else "dim",
        )
        label = theme.c(meta.display_name, "muted", bold=is_default)
        slug = theme.c(f"  ({meta.slug})", "dim")
        print(f" {marker} [{num}] {label}{slug}")
    prompt_text = (
        f"{theme.c(g.prompt, 'accent', bold=True)} Pilih situs "
        f"[{theme.c(str(default_index + 1), 'accent', bold=True)}] "
    )
    while True:
        raw = input(prompt_text).strip()
        clear_screen()
        if not raw:
            return sites[default_index]
        if raw.isdigit():
            picked = int(raw)
            if 1 <= picked <= len(sites):
                return sites[picked - 1]
        print(theme.c("Pilihan tidak valid.", "warning"))
