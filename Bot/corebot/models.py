from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class SessionProfile:
    interval_ms: int = 120
    max_bets: int = 0
    log_every: int = 1
    take_profit_pct: float = 0.0
    pause_on_win: bool = False
    auto_switch_profit_pct: float = 0.0
    run_break_seconds: float = 0.0
    break_seconds: float = 0.0
    flatbet_trigger_pct: float = 0.0
    flatbet_minutes: float = 0.0
    flatbet_amount: float = 0.0


@dataclass(slots=True)
class AccountSnapshot:
    username: str = ""
    email: str = ""
    currency: str = ""
    balance: float = 0.0
    balance_list: list[tuple[str, float]] = field(default_factory=list)
    total_bets: int = 0
    total_wins: int = 0
    total_losses: int = 0
    total_profit: float = 0.0
    total_wagered: float = 0.0


@dataclass(slots=True)
class SessionConfig:
    currency: str
    strategy_name: str
    strategy_path: Path
    strategy_order: tuple[str, ...]
    strategy_profiles: dict[str, SessionProfile]
    interval_ms: int = 120
    max_bets: int = 0
    log_every: int = 1
    take_profit_pct: float = 0.0
    pause_on_win: bool = False
    auto_switch_profit_pct: float = 0.0
    run_break_seconds: float = 0.0
    break_seconds: float = 0.0
    flatbet_trigger_pct: float = 0.0
    flatbet_minutes: float = 0.0
    flatbet_amount: float = 0.0
    remote_config: dict = field(default_factory=dict)
    license_status: dict = field(default_factory=dict)


@dataclass(slots=True)
class SessionSnapshot:
    state: str
    strategy_name: str
    currency: str
    start_balance: float = 0.0
    current_balance: float = 0.0
    session_profit: float = 0.0
    session_wagered: float = 0.0
    session_bets: int = 0
    session_wins: int = 0
    session_losses: int = 0
    total_bets: int = 0
    total_wins: int = 0
    total_losses: int = 0
    total_profit: float = 0.0
    total_wagered: float = 0.0
    highest_bet: float = 0.0
    max_lose_streak: int = 0
    last_roll: float = 0.0
    last_bet_amount: float = 0.0
    last_bet_win: bool | None = None
    chance: float = 49.5
    bethigh: bool = False
    runtime_seconds: float = 0.0
    speed_bps: float = 0.0
    profit_pct: float = 0.0
