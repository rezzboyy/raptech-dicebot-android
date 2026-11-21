"""Menu Withdraw khusus Pasino.

Fitur:
- Pilih coin untuk withdraw
- Tampilkan info: fee, minimum withdraw, saldo tersedia
- Input alamat tujuan
- Input jumlah
- Konfirmasi sebelum submit
- Submit via POST /withdraw/place-withdrawal

Hanya untuk site Pasino. Caller harus cek site sebelum panggil.
"""
from __future__ import annotations

try:
    from colorama import Fore  # type: ignore
except Exception:
    class Fore:  # type: ignore[no-redef]
        CYAN = "\x1b[36m"

from ..clients.pasino import DEFAULT_CURRENCIES
from ..models import AccountSnapshot
from ..ui.theme import visible_len
from ._console import clear_screen, pause, section
from ._state import get_theme
from .layout import responsive_width
from .prompts import prompt_select


# Coins yang bisa di-withdraw (exclude GEM = internal token).
WITHDRAW_COINS: list[str] = [
    c for c in DEFAULT_CURRENCIES if c != "GEM"
]


def show_withdraw_menu(client, account: AccountSnapshot | None) -> None:
    """Entry point menu withdraw. `client` harus instance PasinoClient."""
    theme = get_theme()
    g = theme.glyphs

    while True:
        clear_screen()
        section("WITHDRAW — PASINO", Fore.CYAN, False)
        print(theme.c("Tarik saldo ke wallet eksternal.", "dim"))
        print(theme.c("Pastikan alamat tujuan benar — transaksi tidak bisa dibatalkan!", "warning"))
        print()

        # Pilih coin
        coin = prompt_select(
            WITHDRAW_COINS,
            "Pilih coin withdraw:",
            "USDT",
            show_list=True,
            no_color=False,
        )
        if not coin:
            return

        # Fetch withdraw info (fee, minimum)
        clear_screen()
        section(f"WITHDRAW {coin}", Fore.CYAN, False)
        print(theme.c("  Mengambil info withdraw...", "dim"))

        try:
            info = client.withdraw_info(coin)
        except Exception as exc:
            print(theme.c(f"  Error: {exc}", "danger"))
            pause()
            continue

        # Tampilkan info
        fee = info.get("fee", "0")
        min_wd = info.get("minimum_withdrawal", "0")
        fp_supported = info.get("fp_supported", False)

        # Ambil saldo coin dari client
        try:
            balances_resp = client.balances()
            bal_list = balances_resp.get("balances", [])
            coin_balance = 0.0
            for b in bal_list:
                if str(b.get("currency", "")).upper() == coin.upper():
                    coin_balance = float(b.get("amount", 0))
                    break
        except Exception:
            coin_balance = 0.0

        clear_screen()
        width = responsive_width(max_width=68, min_width=50)
        _render_withdraw_info(coin, coin_balance, fee, min_wd, fp_supported, info, theme, g, width)
        print()

        # Cek saldo cukup
        if coin_balance <= 0:
            print(theme.c(f"  Saldo {coin} = 0. Tidak bisa withdraw.", "danger"))
            print()
            print(theme.c("  [Enter] Pilih coin lain  |  [Q] Kembali", "dim"))
            raw = input(theme.c(f"  {g.prompt} ", "accent", bold=True)).strip().lower()
            if raw in ("q", "quit", "exit", "back"):
                return
            continue

        # Input alamat
        print(theme.c("  Masukkan alamat tujuan withdraw:", "muted"))
        print(theme.c("  Ketik '/cancel' untuk batal.", "dim"))
        address = _prompt_address(theme, g)
        if not address:
            continue

        # Input jumlah
        amount = _prompt_amount(coin, coin_balance, float(min_wd), float(fee), theme, g)
        if amount is None:
            continue

        # Konfirmasi
        clear_screen()
        confirmed = _confirm_withdraw(
            coin=coin,
            address=address,
            amount=amount,
            fee=float(fee),
            balance_after=coin_balance - amount - float(fee),
            theme=theme,
            g=g,
        )
        if not confirmed:
            print(theme.c("  Withdraw dibatalkan.", "warning"))
            pause()
            continue

        # Submit withdraw
        print()
        print(theme.c("  Mengirim permintaan withdraw...", "dim"))
        try:
            result = client.place_withdrawal(coin, address, amount)
        except Exception as exc:
            print(theme.c(f"  GAGAL: {exc}", "danger"))
            pause()
            continue

        # Sukses
        clear_screen()
        _render_withdraw_success(result, amount, coin, address, theme, g)
        pause()
        return


def _prompt_address(theme, g) -> str:
    """Prompt user input alamat wallet. Return '' kalau cancel."""
    while True:
        prompt_text = f"  {theme.c(g.prompt, 'accent', bold=True)} Address: "
        try:
            raw = input(prompt_text).strip()
        except (EOFError, KeyboardInterrupt):
            return ""
        if raw.lower() == "/cancel":
            return ""
        if not raw:
            print(theme.c("  Alamat kosong. Coba lagi atau ketik '/cancel'.", "warning"))
            continue
        if len(raw) < 10:
            print(theme.c("  Alamat terlalu pendek. Pastikan copy dengan benar.", "warning"))
            continue
        return raw


def _prompt_amount(coin: str, balance: float, min_wd: float, fee: float, theme, g) -> float | None:
    """Prompt user input jumlah withdraw. Return None kalau cancel."""
    max_amount = balance - fee
    if max_amount <= 0:
        print(theme.c(f"  Saldo tidak cukup untuk cover fee ({fee:.8f} {coin}).", "danger"))
        pause()
        return None

    print()
    print(theme.c(f"  Saldo tersedia : {balance:.8f} {coin}", "muted"))
    print(theme.c(f"  Fee withdraw   : {fee:.8f} {coin}", "dim"))
    print(theme.c(f"  Min withdraw   : {min_wd:.8f} {coin}", "dim"))
    print(theme.c(f"  Max withdraw   : {max_amount:.8f} {coin} (saldo - fee)", "dim"))
    print(theme.c("  Ketik 'max' untuk withdraw maksimal, '/cancel' untuk batal.", "dim"))
    print()

    while True:
        prompt_text = f"  {theme.c(g.prompt, 'accent', bold=True)} Jumlah {coin}: "
        try:
            raw = input(prompt_text).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if raw.lower() == "/cancel":
            return None
        if raw.lower() in ("max", "all"):
            return max_amount

        try:
            amount = float(raw)
        except ValueError:
            print(theme.c("  Masukkan angka yang valid.", "warning"))
            continue

        if amount <= 0:
            print(theme.c("  Jumlah harus lebih dari 0.", "warning"))
            continue
        if amount < min_wd:
            print(theme.c(f"  Minimum withdraw: {min_wd:.8f} {coin}.", "warning"))
            continue
        if amount > max_amount:
            print(theme.c(f"  Melebihi saldo. Max: {max_amount:.8f} {coin}.", "warning"))
            continue
        return amount


def _confirm_withdraw(
    *,
    coin: str,
    address: str,
    amount: float,
    fee: float,
    balance_after: float,
    theme,
    g,
) -> bool:
    """Tampilkan ringkasan dan minta konfirmasi Y/N."""
    width = responsive_width(max_width=68, min_width=50)
    border_top = theme.box_top(width)
    border_mid = theme.box_mid(width)
    border_bot = theme.box_bottom(width)

    def row(text: str = "") -> str:
        content = " " + text
        return theme.box_row(content, width)

    def center(text: str) -> str:
        styled = theme.c(text, "warning", bold=True)
        pad_total = max(0, width - 2 - visible_len(styled))
        left = pad_total // 2
        right = pad_total - left
        v = theme.c(g.v, "dim")
        return f"{v}{' ' * left}{styled}{' ' * right}{v}"

    label = lambda s: theme.c(f"{s:<16}", "dim")
    receive = amount - fee if fee > 0 else amount

    lines = [
        border_top,
        center("KONFIRMASI WITHDRAW"),
        border_mid,
        row(f"{label('Coin')} {theme.c(coin, 'accent', bold=True)}"),
        row(f"{label('Jumlah')} {theme.c(f'{amount:.8f} {coin}', 'muted', bold=True)}"),
        row(f"{label('Fee')} {theme.c(f'{fee:.8f} {coin}', 'warning')}"),
        row(f"{label('Diterima')} {theme.c(f'{receive:.8f} {coin}', 'success', bold=True)}"),
        row(f"{label('Sisa saldo')} {theme.c(f'{max(0, balance_after):.8f} {coin}', 'dim')}"),
        border_mid,
        row(f"{label('Tujuan')}"),
        row(f"  {theme.c(address, 'success', bold=True)}"),
        border_mid,
        row(theme.c("  ⚠ PERINGATAN: Transaksi TIDAK bisa dibatalkan!", "danger", bold=True)),
        row(theme.c("  Pastikan alamat dan jumlah sudah benar.", "warning")),
        border_bot,
    ]

    for line in lines:
        print(line)

    print()
    prompt_text = f"  {theme.c(g.prompt, 'accent', bold=True)} Konfirmasi withdraw? (y/n): "
    try:
        raw = input(prompt_text).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return raw in ("y", "yes", "ya")


def _render_withdraw_info(
    coin: str,
    balance: float,
    fee: str,
    min_wd: str,
    fp_supported: bool,
    info: dict,
    theme,
    g,
    width: int,
) -> None:
    """Render info withdraw sebelum input."""
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
        center(f"WITHDRAW {coin}"),
        border_mid,
        row(f"{label('Saldo')} {theme.c(f'{balance:.8f} {coin}', 'success', bold=True)}"),
        row(f"{label('Fee Withdraw')} {theme.c(f'{fee} {coin}', 'warning')}"),
        row(f"{label('Min Withdraw')} {theme.c(f'{min_wd} {coin}', 'muted')}"),
    ]

    if fp_supported:
        lines.append(row(f"{label('Fee (FaucetPay)')} {theme.c(info.get('fee_fp', '0') + ' ' + coin, 'dim')}"))
        lines.append(row(f"{label('Min (FaucetPay)')} {theme.c(info.get('minimum_withdrawal_fp', '0') + ' ' + coin, 'dim')}"))

    lines.append(border_bot)

    for line in lines:
        print(line)


def _render_withdraw_success(result: dict, amount: float, coin: str, address: str, theme, g) -> None:
    """Render hasil withdraw sukses."""
    width = responsive_width(max_width=68, min_width=50)
    border_top = theme.box_top(width)
    border_mid = theme.box_mid(width)
    border_bot = theme.box_bottom(width)

    def row(text: str = "") -> str:
        content = " " + text
        return theme.box_row(content, width)

    def center(text: str) -> str:
        styled = theme.c(text, "success", bold=True)
        pad_total = max(0, width - 2 - visible_len(styled))
        left = pad_total // 2
        right = pad_total - left
        v = theme.c(g.v, "dim")
        return f"{v}{' ' * left}{styled}{' ' * right}{v}"

    label = lambda s: theme.c(f"{s:<16}", "dim")
    message = result.get("message", "Withdraw berhasil.")
    new_balance = result.get("balance", "")

    lines = [
        border_top,
        center("WITHDRAW BERHASIL"),
        border_mid,
        row(f"{label('Coin')} {theme.c(coin, 'accent', bold=True)}"),
        row(f"{label('Jumlah')} {theme.c(f'{amount:.8f} {coin}', 'muted', bold=True)}"),
        row(f"{label('Tujuan')} {theme.c(address, 'success')}"),
    ]
    if new_balance:
        lines.append(row(f"{label('Sisa Saldo')} {theme.c(f'{new_balance} {coin}', 'muted')}"))
    lines += [
        border_mid,
        row(f"  {theme.c(message, 'dim')}"),
        border_bot,
    ]

    for line in lines:
        print(line)
