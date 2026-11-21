"""Optional JSON event log + session summary exporter.

Fase 7.1: tulis satu event per baris JSON ke `logs/session-*.jsonl`.
Fase 7.2: tulis ringkasan akhir session ke `reports/session-*.txt`
dengan mini sparkline profit-over-time.

Modul ini sengaja minimal — tidak menambah dependency. Aktif hanya
saat caller (cli.run_engine) menyalakan flag.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .widgets import sparkline


def _runtime_root() -> Path:
    """Root folder untuk simpan logs/reports.

    Mirroring `corebot.config.runtime_root` agar saat dijalankan dari
    .exe (frozen) folder berada di samping executable, bukan di temp.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(os.getcwd())


# Default jumlah file ringkasan/log yang dipertahankan per folder.
# Bisa di-override via env `RAPTECH_REPORTS_KEEP` / `RAPTECH_LOGS_KEEP`.
_DEFAULT_REPORTS_KEEP = 30
_DEFAULT_LOGS_KEEP = 30


def _rotate_dir(folder: Path, pattern: str, keep: int) -> None:
    """Hapus file lama agar `folder` hanya berisi `keep` terbaru.

    Aman terhadap error filesystem — kegagalan rotasi tidak boleh bikin
    bot crash. Dipakai untuk `reports/session-*.txt` dan `logs/session-*.jsonl`.
    """
    if keep <= 0:
        return
    try:
        files = sorted(
            folder.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return
    for stale in files[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass


def _resolve_keep(env_name: str, default: int) -> int:
    raw = os.environ.get(env_name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(0, value)


@dataclass
class JsonEventLog:
    """Buffered JSON event log writer (one line per event).

    Aman dipanggil dari main thread; tidak thread-safe untuk multi
    producer. Engine call di main loop saja.
    """

    enabled: bool = False
    path: Path | None = None
    _fp: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.enabled and self.path is None:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            target = _runtime_root() / "logs"
            target.mkdir(parents=True, exist_ok=True)
            self.path = target / f"session-{stamp}.jsonl"
            # Rotasi keep-N: hapus log session lama, sisakan terbaru.
            _rotate_dir(
                target,
                "session-*.jsonl",
                _resolve_keep("RAPTECH_LOGS_KEEP", _DEFAULT_LOGS_KEEP),
            )

    def open(self) -> None:
        if not self.enabled or self.path is None:
            return
        try:
            self._fp = open(self.path, "a", encoding="utf-8")
        except OSError:
            self.enabled = False
            self._fp = None

    def emit(self, event: str, payload: dict | None = None, *, level: str = "info") -> None:
        if not self.enabled or self._fp is None:
            return
        record = {
            "ts": time.time(),
            "level": level,
            "event": event,
            "payload": payload or {},
        }
        try:
            self._fp.write(json.dumps(record, separators=(",", ":")) + "\n")
            self._fp.flush()
        except OSError:
            self.enabled = False
            try:
                self._fp.close()
            except Exception:
                pass
            self._fp = None

    def close(self) -> None:
        if self._fp is None:
            return
        try:
            self._fp.close()
        except Exception:
            pass
        self._fp = None


def write_session_report(
    *,
    snapshot,
    profit_series,
    started_at: float,
    ended_at: float,
    enabled: bool = True,
) -> Path | None:
    """Tulis text report ringkas. Return path file, atau None saat
    disabled / gagal.

    `profit_series` boleh `list[float]` atau `deque[float]` — keduanya
    iterable + sized.
    """
    if not enabled or snapshot is None:
        return None
    target = _runtime_root() / "reports"
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = target / f"session-{stamp}.txt"
    duration = max(0.0, ended_at - started_at)
    lines = [
        "RAPTECH SESSION REPORT",
        "=" * 60,
        f"Strategy       : {snapshot.strategy_name}",
        f"Currency       : {snapshot.currency}",
        f"Start balance  : {snapshot.start_balance:.8f}",
        f"Final balance  : {snapshot.current_balance:.8f}",
        f"Session profit : {snapshot.session_profit:+.8f} ({snapshot.profit_pct:+.4f}%)",
        f"Cycles         : {snapshot.session_bets:,}",
        f"Wins / Losses  : {snapshot.session_wins} / {snapshot.session_losses}",
        f"Volume         : {snapshot.session_wagered:.8f}",
        f"Peak size      : {snapshot.highest_bet:.8f}",
        f"Max neg streak : {snapshot.max_lose_streak}",
        f"Runtime        : {int(duration // 3600):02d}:{int((duration % 3600) // 60):02d}:{int(duration % 60):02d}",
    ]
    if profit_series:
        spark = sparkline(list(profit_series), width=60)
        lines.append("")
        lines.append("Profit-over-time (mini sparkline):")
        lines.append(spark)
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        return None
    # Rotasi keep-N: hapus report lama supaya folder tidak tumbuh tanpa batas.
    _rotate_dir(
        target,
        "session-*.txt",
        _resolve_keep("RAPTECH_REPORTS_KEEP", _DEFAULT_REPORTS_KEEP),
    )
    return path
