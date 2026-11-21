#!/usr/bin/env python
"""Entry-point bot. Lakukan license check dulu, baru buka CLI.

Wrapping pake try/except global supaya kalau ada exception tak terduga
(termasuk error startup) window cmd nggak langsung force-close - user
sempat baca tracebacknya.

Outer loop: kalau license revoked di tengah session, kembali ke prompt
aktivasi. User bisa input kode baru tanpa restart bot manual.
"""
from __future__ import annotations

import os
import sys
import traceback

# Force UTF-8 di stdout/stderr supaya Unicode box-drawing chars di CLI
# nggak crash di Windows dengan default codepage cp1252. Penting untuk
# distribusi pyinstaller di mesin user yang locale-nya beda-beda.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    pass


def _pause_if_interactive(message: str = "\nTekan Enter untuk keluar...") -> None:
    if sys.stdin and sys.stdin.isatty():
        try:
            input(message)
        except (EOFError, KeyboardInterrupt):
            pass


def _run_session() -> int:
    """Run satu session: license check + CLI main loop.

    Return value:
       0 = exit normal (user pilih Exit dari menu)
      99 = license revoked di tengah session, harus restart ke prompt
    """
    from corebot.cli import main
    from corebot.license.check import (
        clear_revocation_reason,
        get_revocation_reason,
        stop_background_heartbeat,
        verify_license_or_exit,
    )

    # Reset revocation flag dari session sebelumnya
    clear_revocation_reason()

    verify_license_or_exit()

    # CLI main loop
    try:
        rc = main() or 0
    finally:
        # Saat CLI exit, cek apakah karena revocation (heartbeat trigger
        # KeyboardInterrupt simulation lewat menu hot-key, atau license
        # check di main detect mid-session change) atau exit normal.
        if get_revocation_reason() is not None:
            stop_background_heartbeat()
            return 99
    return rc


if __name__ == "__main__":
    try:
        # Outer loop: restart kalau license revoked ATAU unhandled error
        while True:
            try:
                rc = _run_session()
            except KeyboardInterrupt:
                # KeyboardInterrupt bisa berasal dari:
                #   (a) user tekan Ctrl+C real -> exit
                #   (b) heartbeat trigger _interrupt_main_thread() saat
                #       license revoked -> restart ke prompt
                from corebot.license.check import get_revocation_reason
                if get_revocation_reason() is not None:
                    rc = 99
                else:
                    raise
            except Exception as exc:
                # Fase 8.1: Exception tidak terduga di layer bot HARUS
                # ditangkap, ditampilkan, lalu kembali ke menu — BOT
                # TIDAK BOLEH force-close. User bisa baca error + retry
                # tanpa buka ulang terminal.
                import traceback
                sys.stderr.write("\n[BOT] ERROR TIDAK TERDUGA — bot tetap berjalan:\n")
                traceback.print_exc()
                sys.stderr.write(
                    "\n[BOT] Kembali ke menu utama dalam 3 detik...\n"
                )
                sys.stderr.flush()
                import time as _time
                _time.sleep(3)
                rc = 99  # trigger restart ke activation prompt / menu
            if rc != 0:
                # rc=99: license revoked → prompt aktivasi
                # rc=1 atau lainnya: error di CLI/engine → tampilkan dan
                #   kembali ke menu. BOT TIDAK BOLEH force-close.
                if rc == 99:
                    msg = "\n[BOT] Mengembalikan ke menu aktivasi lisensi...\n\n"
                else:
                    msg = f"\n[BOT] Sesi berakhir (rc={rc}). Kembali ke menu...\n\n"
                sys.stdout.write(msg)
                sys.stdout.flush()
                continue
            sys.exit(rc)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        sys.stderr.write("\n[BOT] Dihentikan oleh user.\n")
        sys.exit(130)
    except Exception:
        # Absolute last-resort fallback — hanya untuk error yang lolos
        # dari semua lapisan di atas (harusnya sangat jarang).
        sys.stderr.write("\n[BOT] Critical error — bot tidak bisa melanjutkan:\n")
        traceback.print_exc()
        _pause_if_interactive()
        sys.exit(1)
