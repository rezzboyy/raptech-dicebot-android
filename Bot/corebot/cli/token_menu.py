"""Menu Token Status & Refresh khusus Pasino.

Fitur:
- Token Status: cek apakah Web API (token) masih aktif atau expired
- Refresh Token: manual force refresh token via /account/refresh-token

Hanya untuk site Pasino. Caller harus cek site sebelum panggil.
"""
from __future__ import annotations

try:
    from colorama import Fore  # type: ignore
except Exception:
    class Fore:  # type: ignore[no-redef]
        CYAN = "\x1b[36m"

from ..ui.theme import visible_len
from ._console import clear_screen, section
from ._state import get_theme
from .layout import responsive_width


def show_token_status(client) -> None:
    """Cek dan tampilkan status token Pasino."""
    theme = get_theme()
    g = theme.glyphs
    width = responsive_width(max_width=64, min_width=46)

    clear_screen()
    section("TOKEN STATUS — PASINO", Fore.CYAN, False)
    print(theme.c("  Memeriksa status token...", "dim"))
    print()

    try:
        result = client.check_token_status()
    except Exception as exc:
        print(theme.c(f"  Error: {exc}", "danger"))
        return

    active = result.get("active", False)
    message = result.get("message", "")
    token_preview = result.get("token_preview", "***")

    border_top = theme.box_top(width)
    border_mid = theme.box_mid(width)
    border_bot = theme.box_bottom(width)

    def row(text: str = "") -> str:
        content = " " + text
        return theme.box_row(content, width)

    def center(text: str, role: str = "accent") -> str:
        styled = theme.c(text, role, bold=True)
        pad_total = max(0, width - 2 - visible_len(styled))
        left = pad_total // 2
        right = pad_total - left
        v = theme.c(g.v, "dim")
        return f"{v}{' ' * left}{styled}{' ' * right}{v}"

    label = lambda s: theme.c(f"{s:<14}", "dim")

    if active:
        status_text = theme.c("● ACTIVE", "success", bold=True)
        status_title = "TOKEN AKTIF"
        title_role = "success"
    else:
        status_text = theme.c("● EXPIRED / INVALID", "danger", bold=True)
        status_title = "TOKEN TIDAK AKTIF"
        title_role = "danger"

    lines = [
        border_top,
        center(status_title, title_role),
        border_mid,
        row(f"{label('Status')} {status_text}"),
        row(f"{label('Token')} {theme.c(token_preview, 'muted')}"),
        row(f"{label('Detail')} {theme.c(message, 'dim')}"),
        border_mid,
    ]

    if active:
        lines.append(row(theme.c("  Token masih valid. Bot bisa berjalan normal.", "dim")))
        lines.append(row(theme.c("  Auto-refresh aktif setiap 4 menit.", "dim")))
    else:
        lines.append(row(theme.c("  Token sudah expired atau invalid.", "warning")))
        lines.append(row(theme.c("  Coba menu [11] Refresh Token, atau paste ulang", "warning")))
        lines.append(row(theme.c("  token baru dari browser (menu 2).", "warning")))

    lines.append(border_bot)

    for line in lines:
        print(line)


def show_refresh_token(client) -> None:
    """Manual force refresh token Pasino."""
    theme = get_theme()
    g = theme.glyphs
    width = responsive_width(max_width=64, min_width=46)

    clear_screen()
    section("REFRESH TOKEN — PASINO", Fore.CYAN, False)
    print(theme.c("  Memanggil /account/refresh-token...", "dim"))
    print()

    try:
        result = client.force_refresh_token()
    except Exception as exc:
        print(theme.c(f"  Error: {exc}", "danger"))
        return

    success = result.get("success", False)
    message = result.get("message", "")
    token_preview = result.get("new_token_preview", "***")

    border_top = theme.box_top(width)
    border_mid = theme.box_mid(width)
    border_bot = theme.box_bottom(width)

    def row(text: str = "") -> str:
        content = " " + text
        return theme.box_row(content, width)

    def center(text: str, role: str = "accent") -> str:
        styled = theme.c(text, role, bold=True)
        pad_total = max(0, width - 2 - visible_len(styled))
        left = pad_total // 2
        right = pad_total - left
        v = theme.c(g.v, "dim")
        return f"{v}{' ' * left}{styled}{' ' * right}{v}"

    label = lambda s: theme.c(f"{s:<14}", "dim")

    if success:
        lines = [
            border_top,
            center("REFRESH BERHASIL", "success"),
            border_mid,
            row(f"{label('Status')} {theme.c('● SUCCESS', 'success', bold=True)}"),
            row(f"{label('Token Baru')} {theme.c(token_preview, 'muted')}"),
            border_mid,
            row(theme.c("  Token baru aktif dan tersimpan di apitokens.json.", "dim")),
            row(theme.c("  Bot akan terus berjalan tanpa perlu paste ulang.", "dim")),
            border_bot,
        ]
    else:
        lines = [
            border_top,
            center("REFRESH GAGAL", "danger"),
            border_mid,
            row(f"{label('Status')} {theme.c('● FAILED', 'danger', bold=True)}"),
            row(f"{label('Token')} {theme.c(token_preview, 'muted')}"),
            row(f"{label('Detail')} {theme.c(message, 'warning')}"),
            border_mid,
            row(theme.c("  Token tidak bisa di-refresh otomatis.", "warning")),
            row(theme.c("  Paste token baru dari browser via menu 2.", "warning")),
            border_bot,
        ]

    for line in lines:
        print(line)
