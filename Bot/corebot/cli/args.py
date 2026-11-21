"""Argparse parser untuk Raptech Engine CLI.

Diekstrak dari `cli/__init__.py` (Fase 2 perapihan, Step D).
Tidak menyentuh state runtime â€” pure factory `argparse.ArgumentParser`.

Public API (di-re-export oleh `cli/__init__.py`):
    - `build_parser()`
"""
from __future__ import annotations

import argparse

from ..clients import available_sites
from ..config import DEFAULT_SITE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Raptech Engine (multi-site automation)")
    parser.add_argument(
        "--site",
        choices=available_sites(),
        help=f"Pilih situs target. Default: {DEFAULT_SITE}",
    )
    parser.add_argument("--token", help="Web API bearer token; untuk testmode bisa berisi JSON seed/balance")
    parser.add_argument("--currency", help="Currency, contoh: DOGE/TRX/BTC")
    parser.add_argument("--strategy", help="Nama file strategy Lua")
    parser.add_argument("--interval-ms", type=int, help="Delay antar cycle dalam millisecond")
    parser.add_argument("--max-bets", type=int, help="Stop setelah jumlah cycle ini, 0=unlimited")
    parser.add_argument("--log-every", type=int, help="Print metrics setiap N cycle")
    parser.add_argument("--take-profit-pct", type=float, help="Stop saat profit percent tercapai")
    parser.add_argument("--pause-on-win", action="store_true", help="Stop/pause setelah hasil positif")
    parser.add_argument("--auto-switch-profit-pct", type=float, help="Switch strategy saat profit percent tercapai")
    parser.add_argument("--run-break-seconds", type=float, help="Durasi run sebelum break")
    parser.add_argument("--break-seconds", type=float, help="Durasi break")
    parser.add_argument("--flatbet-trigger-pct", type=float, help="Trigger flat allocation dari profit percent")
    parser.add_argument("--flatbet-minutes", type=float, help="Durasi flat allocation dalam menit")
    parser.add_argument("--flatbet-amount", type=float, help="Nominal flat allocation")
    parser.add_argument("--quiet", action="store_true", help="Reduce per-cycle output")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument(
        "--theme",
        choices=("cyber", "minimal", "mono", "accessible"),
        default="cyber",
        help="Pilih preset tema. 'mono' otomatis disable warna.",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Plain text mode: skip ASCII art / box drawing (cocok untuk screen reader / SSH minimal).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact mode: layout kompak untuk terminal pendek (auto-on saat tinggi <30 baris).",
    )
    parser.add_argument(
        "--no-toast",
        action="store_false",
        dest="toast",
        help="Disable toast notifikasi event runtime (biarkan event muncul sebagai log line biasa).",
    )
    parser.add_argument(
        "--confirm-quit",
        action="store_true",
        default=True,
        help="Tekan Q dua kali untuk benar-benar quit dari engine (default ON).",
    )
    parser.add_argument(
        "--no-confirm-quit",
        action="store_false",
        dest="confirm_quit",
        help="Quit langsung tanpa konfirmasi (1x tekan Q).",
    )
    parser.add_argument(
        "--log-format",
        choices=("text", "json"),
        default="text",
        help="Tulis log session ke logs/session-*.jsonl (Fase 7.1). Default text-only ke layar.",
    )
    parser.add_argument(
        "--no-report",
        action="store_false",
        dest="write_report",
        help="Jangan tulis ringkasan session ke reports/.",
    )
    parser.add_argument(
        "--quick-start",
        action="store_true",
        help="Buka quick-start wizard dan langsung mulai (Fase 4.3).",
    )
    parser.add_argument(
        "--profile",
        nargs="?",
        const="profile.out",
        metavar="OUT",
        help="Bungkus session engine dengan cProfile dan dump ke OUT (default profile.out). Lihat dengan snakeviz.",
    )
    parser.add_argument("--no-sticky-footer", action="store_false", dest="sticky_footer", help="Disable sticky footer")
    parser.add_argument("--non-interactive", action="store_true", help="Jalan tanpa menu, pakai argumen/saved/default")
    parser.add_argument("--no-save-token", action="store_true", help="Jangan simpan Web API")
    parser.add_argument("--list-strategies", action="store_true", help="Tampilkan strategy Lua lalu exit")
    parser.add_argument("--list-sites", action="store_true", help="Tampilkan list situs lalu exit")
    parser.add_argument(
        "--check-script",
        nargs="?",
        const="all",
        metavar="NAME",
        help="Cek kompatibilitas script Lua lalu exit. Pakai tanpa NAME untuk cek semua.",
    )
    parser.set_defaults(sticky_footer=True, toast=True, write_report=True)
    return parser
