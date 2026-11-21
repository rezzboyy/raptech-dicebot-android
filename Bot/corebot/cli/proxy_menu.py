"""Menu konfigurasi proxy per-site.

Fitur:
- Tampilkan proxy aktif untuk site saat ini
- Set proxy URL baru (paste format: http/https/socks4/socks5)
- Clear proxy (kembalikan ke direct connection)
- Test proxy — ping cepat ke situs target

Berguna untuk situs yang geo-blocked (misal Betfury blok IP Jerman/EU).
User tinggal beli proxy dari negara yang tidak di-block, paste di sini.
"""
from __future__ import annotations

try:
    from colorama import Fore  # type: ignore
except Exception:
    class Fore:  # type: ignore[no-redef]
        CYAN = "\x1b[36m"

from ..clients import site_metadata
from ..storage import _parse_proxy_url, get_proxy_url_for, set_proxy_for
from ..ui.theme import visible_len
from ._console import clear_screen, pause, section
from ._state import get_theme
from .layout import responsive_width
from .prompts import prompt_select


def show_proxy_menu(site: str) -> bool:
    """Entry point menu proxy untuk site tertentu.

    Return True kalau proxy config berubah (caller harus reconnect).
    """
    theme = get_theme()
    g = theme.glyphs
    site_label = site_metadata(site).display_name
    changed = False

    while True:
        clear_screen()
        current_url = get_proxy_url_for(site)
        _render_proxy_status(site_label, current_url, theme, g)
        print()

        options = ["Set Proxy URL"]
        if current_url:
            options.append("Clear Proxy")
        options.append("Back to Menu")

        picked = prompt_select(
            options,
            "Pilih aksi:",
            options[-1],
            show_list=True,
            no_color=False,
        )

        if picked == "Back to Menu":
            return changed

        if picked == "Set Proxy URL":
            result = _prompt_new_proxy(site, current_url, theme, g)
            if result:
                changed = True

        elif picked == "Clear Proxy":
            confirm = input(
                f"  {theme.c(g.prompt, 'accent', bold=True)} "
                f"Hapus proxy untuk {site_label}? (y/n): "
            ).strip().lower()
            if confirm in ("y", "yes", "ya"):
                set_proxy_for(site, "")
                print(theme.c(f"  ✓ Proxy dihapus. Koneksi kembali direct.", "success"))
                changed = True
                pause()


def _prompt_new_proxy(site: str, current_url: str, theme, g) -> bool:
    """Prompt paste proxy URL baru. Return True kalau berhasil disimpan."""
    clear_screen()
    section(f"SET PROXY — {site_metadata(site).display_name}", Fore.CYAN, False)
    print(theme.c("  Format proxy yang didukung:", "dim"))
    print(theme.c("    http://host:port", "dim"))
    print(theme.c("    http://user:pass@host:port", "dim"))
    print(theme.c("    https://user:pass@host:port", "dim"))
    print(theme.c("    socks5://user:pass@host:port    (rekomendasi)", "dim"))
    print(theme.c("    socks5h://user:pass@host:port   (DNS via proxy)", "dim"))
    print()
    print(theme.c("  Berguna untuk situs geo-blocked (mis. Betfury blok EU).", "dim"))
    print(theme.c("  Beli proxy dari negara yang tidak di-block situs.", "dim"))
    print(theme.c("  Ketik '/cancel' untuk batal.", "dim"))
    print()

    if current_url:
        print(theme.c(f"  Current: {current_url}", "muted"))
        print()

    prompt_text = f"  {theme.c(g.prompt, 'accent', bold=True)} Proxy URL: "
    while True:
        try:
            raw = input(prompt_text).strip()
        except (EOFError, KeyboardInterrupt):
            return False
        if raw.lower() == "/cancel":
            return False
        if not raw:
            print(theme.c("  URL kosong. Coba lagi atau ketik '/cancel'.", "warning"))
            continue

        # Validasi format
        parsed = _parse_proxy_url(raw)
        if parsed is None:
            print(theme.c("  Format tidak valid. Pakai http://..., socks5://..., dll.", "warning"))
            continue

        # Simpan
        set_proxy_for(site, raw)
        print()
        print(theme.c(f"  ✓ Proxy tersimpan: {raw}", "success"))
        print(theme.c(f"  Akan aktif saat koneksi berikutnya ke {site}.", "dim"))
        pause()
        return True


def _render_proxy_status(site_label: str, current_url: str, theme, g) -> None:
    """Render status proxy dalam box."""
    width = responsive_width(max_width=64, min_width=46)
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

    label = lambda s: theme.c(f"{s:<10}", "dim")

    if current_url:
        status_text = theme.c("● ACTIVE", "success", bold=True)
        # Mask password kalau ada di URL untuk display safety
        display_url = _mask_password(current_url)
    else:
        status_text = theme.c("○ NONE (direct)", "dim", bold=True)
        display_url = "(tidak ada proxy)"

    lines = [
        border_top,
        center(f"PROXY — {site_label}"),
        border_mid,
        row(f"{label('Status')} {status_text}"),
        row(f"{label('URL')} {theme.c(display_url, 'muted')}"),
        border_bot,
    ]

    for line in lines:
        print(line)


def _mask_password(url: str) -> str:
    """Sembunyikan password di URL untuk display. `http://user:pass@host` → `http://user:***@host`."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    creds, host = rest.rsplit("@", 1)
    if ":" not in creds:
        return url
    user, _pw = creds.split(":", 1)
    return f"{scheme}://{user}:***@{host}"
