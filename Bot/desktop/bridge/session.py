"""Helper konstruksi SessionConfig untuk GUI.

Versi ringkas dari `corebot.cli.runner.build_config` — tanpa perlu
settings_store. GUI kirim strategy + currency + profile langsung.
"""
from __future__ import annotations

from corebot.config import lua_dir
from corebot.models import SessionConfig, SessionProfile


def build_config(
    strategy_name: str,
    currency: str,
    profile: SessionProfile,
    strategies: list[str],
    strategy_path=None,
) -> SessionConfig:
    """Compose SessionConfig dari pilihan GUI.

    `strategy_path` opsional — kalau di-set, dipakai langsung (mis. file
    hasil dump editor). Kalau None, default ke lua_dir()/strategy_name.
    """
    from pathlib import Path

    path = Path(strategy_path) if strategy_path else (lua_dir() / strategy_name)
    # Auto-switch butuh >1 strategy; editor mode = 1 strategy saja.
    order = (strategy_name,)
    return SessionConfig(
        currency=currency,
        strategy_name=strategy_name,
        strategy_path=path,
        strategy_order=order,
        strategy_profiles={strategy_name: profile},
        interval_ms=profile.interval_ms,
        max_bets=profile.max_bets,
        log_every=profile.log_every,
        take_profit_pct=profile.take_profit_pct,
        pause_on_win=profile.pause_on_win,
        auto_switch_profit_pct=profile.auto_switch_profit_pct,
        run_break_seconds=profile.run_break_seconds,
        break_seconds=profile.break_seconds,
        flatbet_trigger_pct=profile.flatbet_trigger_pct,
        flatbet_minutes=profile.flatbet_minutes,
        flatbet_amount=profile.flatbet_amount,
        remote_config={},
        license_status={},
    )
