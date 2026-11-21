"""Menu Deposit khusus Pasino.

Fitur:
- Tampilkan daftar coin yang bisa di-deposit
- User pilih coin → langsung fetch address dari API
- Endpoint: POST /deposit/get-deposit-information
- Tampilkan address, min deposit, confirmations, QR URL
- Format copy-paste friendly

Catatan: Pasino tidak pakai pemilihan network — 1 coin = 1 address
(network fix per coin di backend mereka). Jadi flow-nya:
  Pilih coin → fetch → tampilkan address.

Hanya untuk site Pasino. Caller harus cek site sebelum panggil.
"""
from __future__ import annotations

try:
    from colorama import Fore  # type: ignore
except Exception:
    class Fore:  # type: ignore[no-redef]
        CYAN = "\x1b[36m"
        YELLOW = "\x1b[33m"

from ..clients.pasino import DEFAULT_CURRENCIES
from ..ui.strings import S as STR
from ..ui.theme import visible_len
from ._console import clear_screen, pause, section
from ._state import get_theme
from .layout import responsive_width
from .prompts import prompt_select


# Coins yang bisa di-deposit (exclude GEM karena internal token Pasino).
DEPOSIT_COINS: list[str] = [
    c for c in DEFAULT_CURRENCIES if c != "GEM"
]


def show_deposit_menu(client) -> None:
    """Entry point menu deposit. `client` harus instance PasinoClient."""
    theme = get_theme()
    g = theme.glyphs

    while True:
        clear_screen()
        section("DEPOSIT — PASINO", Fore.CYAN, False)
        print(theme.c("Pilih coin untuk melihat alamat deposit.", "dim"))
        print(theme.c("Kirim crypto ke alamat yang ditampilkan untuk top-up saldo.", "dim"))
        print()

        # Pilih coin
        coin = prompt_select(
            DEPOSIT_COINS,
            "Pilih coin deposit:",
            "USDT",
            show_list=True,
            no_color=False,
        )
        if not coin:
            return

        # Fetch deposit address langsung (Pasino: 1 coin = 1 address)
        clear_screen()
        section(f"DEPOSIT {coin}", Fore.CYAN, False)
        print(theme.c("  Mengambil alamat deposit...", "dim"))

        try:
            result = client.deposit_address(coin)
        except Exception as exc:
            print()
            print(theme.c(f"  Error: {exc}", "danger"))
            print()
            print(theme.c("  Tips: Buka pasino.com > Wallet > Deposit untuk verifikasi.", "warning"))
            pause()
            continue

        # Tampilkan hasil
        clear_screen()
        width = responsive_width(max_width=72, min_width=50)
        _render_deposit_result(result, theme, g, width)

        # Loop: user bisa pilih coin lain atau kembali
        print()
        print(theme.c("  [Enter] Deposit coin lain  |  [Q] Kembali ke menu", "dim"))
        try:
            raw = input(theme.c(f"  {g.prompt} ", "accent", bold=True)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if raw in ("q", "quit", "exit", "back"):
            return


def _render_deposit_result(result: dict, theme, g, width: int) -> None:
    """Render alamat deposit dalam box rapi — data dari endpoint real Pasino.

    Response fields:
      address, coin, confirmations_required, min_deposit,
      min_deposit_fp, qr_url, requires_payment_tag, fp_supported
    """
    coin = result.get("coin", "")
    address = result.get("address", "")
    confirmations = result.get("confirmations_required", "0")
    min_deposit = result.get("min_deposit", "0")
    min_deposit_fp = result.get("min_deposit_fp", "0")
    qr_url = result.get("qr_url", "")
    requires_tag = result.get("requires_payment_tag", False)
    fp_supported = result.get("fp_supported", False)

    border_top = theme.box_top(width)
    border_mid = theme.box_mid(width)
    border_bot = theme.box_bottom(width)

    def row(text: str = "") -> str:
        content = " " + text
        return theme.box_row(content, width)

    def center(text: str) -> str:
        styled = theme.c(text, "accent", bold=True)
        pad_total = max(0, width - 2 - visible_len(styled))
        left = pad_total // 2
        right = pad_total - left
        v = theme.c(g.v, "dim")
        return f"{v}{' ' * left}{styled}{' ' * right}{v}"

    label = lambda s: theme.c(f"{s:<20}", "dim")

    lines = [
        border_top,
        center(f"DEPOSIT {coin}"),
        border_mid,
        row(f"{label('Coin')} {theme.c(coin, 'accent', bold=True)}"),
        row(f"{label('Min Deposit')} {theme.c(min_deposit + ' ' + coin, 'warning')}"),
        row(f"{label('Confirmations')} {theme.c(confirmations + 'x', 'muted')}"),
    ]

    if fp_supported:
        lines.append(row(f"{label('Min Deposit (FP)')} {theme.c(min_deposit_fp + ' ' + coin, 'dim')}"))

    lines += [
        border_mid,
        row(theme.c("  DEPOSIT ADDRESS:", "dim", bold=True)),
        row(""),
        row(f"  {theme.c(address, 'success', bold=True)}"),
        row(""),
    ]

    if requires_tag:
        lines += [
            border_mid,
            row(theme.c("  ⚠ Coin ini memerlukan Payment Tag / Memo!", "danger", bold=True)),
            row(theme.c("    Pastikan sertakan tag saat transfer.", "warning")),
        ]

    if qr_url:
        lines += [
            border_mid,
            row(f"{label('QR Code URL')}"),
            row(f"  {theme.c(qr_url, 'dim')}"),
        ]

    lines += [
        border_mid,
        row(theme.c("  Copy alamat di atas, kirim dari wallet/exchange.", "dim")),
        row(theme.c("  Pastikan coin BENAR — salah coin = dana hilang!", "warning")),
        row(theme.c(f"  Saldo masuk setelah {confirmations} konfirmasi network.", "dim")),
        border_bot,
    ]

    for line in lines:
        print(line)
