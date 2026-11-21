"""Builder untuk `SessionSnapshot` dari raw counter state.

Diekstrak dari `engine/__init__.py` (Fase 3 perapihan, Step L-C).
Pure compute — tidak menyentuh state engine atau client.

Public API:
    - `build_snapshot(state, config, started_at, ...)` -> SessionSnapshot
"""
from __future__ import annotations

import time

from ..models import SessionConfig, SessionSnapshot


def build_snapshot(
    *,
    state: str,
    config: SessionConfig,
    started_at: float,
    start_balance: float,
    balance: float,
    session_profit: float,
    session_wagered: float,
    session_bets: int,
    session_wins: int,
    session_losses: int,
    total_bets: int,
    total_wins: int,
    total_losses: int,
    total_profit: float,
    total_wagered: float,
    highest_bet: float,
    max_lose_streak: int,
    last_roll: float,
    last_bet_amount: float,
    last_bet_win: bool | None,
    chance: float,
    bethigh: bool,
) -> SessionSnapshot:
    """Hitung `runtime_seconds`, `profit_pct`, `speed_bps` lalu compose
    `SessionSnapshot` lengkap. Dipanggil per-cycle dari `_run_session`."""
    runtime_seconds = max(0.0, time.monotonic() - started_at)
    profit_pct = 0.0 if start_balance <= 0 else (session_profit / start_balance) * 100.0
    speed_bps = (session_bets / runtime_seconds) if runtime_seconds > 0 else 0.0
    return SessionSnapshot(
        state=state,
        strategy_name=config.strategy_name,
        currency=config.currency,
        start_balance=start_balance,
        current_balance=balance,
        session_profit=session_profit,
        session_wagered=session_wagered,
        session_bets=session_bets,
        session_wins=session_wins,
        session_losses=session_losses,
        total_bets=total_bets,
        total_wins=total_wins,
        total_losses=total_losses,
        total_profit=total_profit,
        total_wagered=total_wagered,
        highest_bet=highest_bet,
        max_lose_streak=max_lose_streak,
        last_roll=last_roll,
        last_bet_amount=last_bet_amount,
        last_bet_win=last_bet_win,
        chance=chance,
        bethigh=bethigh,
        runtime_seconds=runtime_seconds,
        speed_bps=speed_bps,
        profit_pct=profit_pct,
    )
