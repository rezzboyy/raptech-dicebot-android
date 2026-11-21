from __future__ import annotations

import gc
import threading
import time
from pathlib import Path
from typing import Callable

from ..clients import balance_list_from_response, currency_balance
from ..clients.base import BaseClient
from ..lua_support import (
    LuaStateMirror,
    get_global,
    is_authentication_error,
    is_insufficient_balance_error,
    load_lua_strategy,
)
from ..models import AccountSnapshot, SessionConfig, SessionProfile, SessionSnapshot

EventCallback = Callable[[str, object], None]


# Re-export utility helpers dari `_helpers.py` (Step L-B).
from ._helpers import (  # noqa: E402
    _extract_bet_result,
    _lua_for_globs,
)


class BotEngine:
    def __init__(self, client: BaseClient, emit: EventCallback):
        self._client = client
        self._emit = emit
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._state = "idle"
        self._pause_on_win_override: bool | None = None

    @property
    def state(self) -> str:
        with self._state_lock:
            return self._state

    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def set_pause_on_win(self, enabled: bool) -> None:
        with self._state_lock:
            self._pause_on_win_override = bool(enabled)

    def start(self, config: SessionConfig, account: AccountSnapshot) -> None:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Session is already running.")
        self._stop_event.clear()
        with self._state_lock:
            self._pause_on_win_override = None
        self._thread = threading.Thread(
            target=self._run_session,
            args=(config, account),
            daemon=True,
            name="raptech-engine",
        )
        self._set_state("starting")
        self._thread.start()

    def pause(self) -> None:
        if self.state in {"running", "starting"}:
            self._set_state("paused")
            self._emit("log", {"level": "warn", "message": "Session paused."})

    def resume(self) -> None:
        if self.state == "paused":
            self._set_state("running")
            self._emit("log", {"level": "success", "message": "Session resumed."})

    def stop(self) -> None:
        if self.state not in {"idle", "stopped"}:
            self._stop_event.set()
            self._set_state("stopping")
            self._emit("log", {"level": "warn", "message": "Stopping session..."})

    def _set_state(self, value: str) -> None:
        with self._state_lock:
            self._state = value
        self._emit("state", value)

    def _pause_on_win_enabled(self, default: bool) -> bool:
        with self._state_lock:
            return default if self._pause_on_win_override is None else self._pause_on_win_override

    def _build_snapshot(
        self,
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
        # Pindah ke `engine/_snapshot.py` (Step L-C). Method ini jadi
        # delegate untuk back-compat dengan call site positional di
        # `_run_session`.
        from ._snapshot import build_snapshot
        return build_snapshot(
            state=state,
            config=config,
            started_at=started_at,
            start_balance=start_balance,
            balance=balance,
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
        )

    def _run_session(self, config: SessionConfig, account: AccountSnapshot) -> None:
        try:
            self.__run_session_inner(config, account)
        except Exception as exc:
            import traceback
            details = traceback.format_exc().strip()
            self._emit("log", {"level": "error", "message": f"FATAL: Session crashed — {exc}"})
            # Emit traceback line-by-line supaya user bisa baca
            for line in details.split("\n"):
                self._emit("log", {"level": "error", "message": f"TRACEBACK | {line}"})
            self._set_state("stopped")

    def __run_session_inner(self, config: SessionConfig, account: AccountSnapshot) -> None:
        min_bet = 1e-8
        start_balance = account.balance
        balance = account.balance
        total_bets = account.total_bets
        total_wins = account.total_wins
        total_losses = account.total_losses
        total_profit = account.total_profit
        total_wagered = account.total_wagered
        session_bets = 0
        session_wins = 0
        session_losses = 0
        session_profit = 0.0
        session_wagered = 0.0
        highest_bet = 0.0
        max_lose_streak = 0
        current_streak = 0
        started_at = time.monotonic()
        run_started_at = started_at
        consecutive_errors = 0
        max_errors = 8
        overall_steps = 0
        flatbet_active = False
        flatbet_start_at = 0.0
        flatbet_last_level = 0
        deferred_balance_probe_attempted = False
        strategy_base_dir = config.strategy_path.parent

        # Fase 3.3: throttle frequency `balances()` panggilan saat balance
        # kurang. Default 1.0s; client boleh override via attribute.
        min_refresh_interval = float(getattr(self._client, "min_refresh_interval_s", 1.0))
        last_balance_refresh_at = 0.0

        strategy_order = list(config.strategy_order or (config.strategy_name,))
        if config.strategy_name not in strategy_order:
            strategy_order.append(config.strategy_name)
        current_strategy_index = strategy_order.index(config.strategy_name)

        def resolve_strategy_path(strategy_name: str) -> Path:
            return strategy_base_dir / strategy_name

        def default_profile() -> SessionProfile:
            return SessionProfile(
                interval_ms=config.interval_ms,
                max_bets=config.max_bets,
                log_every=config.log_every,
                take_profit_pct=config.take_profit_pct,
                pause_on_win=config.pause_on_win,
                auto_switch_profit_pct=config.auto_switch_profit_pct,
                run_break_seconds=config.run_break_seconds,
                break_seconds=config.break_seconds,
                flatbet_trigger_pct=config.flatbet_trigger_pct,
                flatbet_minutes=config.flatbet_minutes,
                flatbet_amount=config.flatbet_amount,
            )

        def resolve_profile(strategy_name: str) -> SessionProfile:
            return config.strategy_profiles.get(strategy_name, default_profile())

        active_profile = resolve_profile(config.strategy_name)
        interval_ms = active_profile.interval_ms
        log_every = active_profile.log_every
        max_bets = active_profile.max_bets
        take_profit_pct = active_profile.take_profit_pct
        pause_on_win = active_profile.pause_on_win
        auto_switch_profit_pct = active_profile.auto_switch_profit_pct
        run_break_seconds = active_profile.run_break_seconds
        break_seconds = active_profile.break_seconds
        flatbet_trigger_pct = active_profile.flatbet_trigger_pct
        flatbet_minutes = active_profile.flatbet_minutes
        flatbet_amount = active_profile.flatbet_amount

        try:
            globs, chance, basebet, nextbet, bethigh = self._prepare_strategy_runtime(
                config.strategy_path,
                config.currency,
                balance,
                account,
                remote_config=config.remote_config,
                license_status=config.license_status,
            )
        except Exception as exc:
            self._emit("log", {"level": "error", "message": f"Cannot load strategy: {exc}"})
            self._set_state("stopped")
            return
        if 0 < flatbet_amount < min_bet:
            flatbet_amount = min_bet

        # Fase 1.5: cache `dobet` reference. Re-resolve hanya saat strategy
        # switch supaya tidak panggil get_global tiap iterasi.
        dobet_cached = get_global(globs, "dobet", None)

        # Fase 1.2 + 2.1 + 2.2: state mirror — buffered Python <-> Lua
        # bridge. Engine update slot Python, flush sekali sebelum dobet,
        # read_back sesudahnya. Pakai persistent `lastBet` table.
        mirror = LuaStateMirror(globs)
        mirror.chance = chance
        mirror.nextbet = nextbet
        mirror.bethigh = bethigh
        mirror.balance = balance
        mirror.totalbets = total_bets
        mirror.totalwins = total_wins
        mirror.totallosses = total_losses
        mirror.totalprofit = total_profit
        mirror.totalwagered = total_wagered
        # Init persistent lastBet table — butuh akses `lua` runtime.
        # Cara robust: ambil dari globs.metatable atau langsung gunakan
        # `lua = globs._lua` kalau lupa expose. Fallback dict tetap ada.
        try:
            from lupa import LuaRuntime  # type: ignore
            # lupa tidak expose globs->runtime publicly; kita simpan
            # reference Lua runtime saat prepare. Untuk minimasi diff,
            # init via globs sendiri (lupa table_from masih bisa via
            # call ke `globs._lua` tapi tidak guaranteed). Fallback dict
            # cukup karena code-path tetap benar.
        except Exception:
            pass
        mirror.init_last_bet_table(_lua_for_globs(globs))

        self._set_state("running")
        self._emit(
            "log",
            {
                "level": "info",
                "message": (
                    f"Session started. Strategy={config.strategy_name} "
                    f"Asset={config.currency}"
                ),
            },
        )

        while not self._stop_event.is_set():
            if self.state == "paused":
                time.sleep(0.1)
                continue

            # Fase 1.1: cache `time.monotonic()` per cycle untuk semua
            # check yang butuh "now"
            now_t = time.monotonic()

            if max_bets and overall_steps >= max_bets:
                self._emit("log", {"level": "warn", "message": "Stopped: max cycles reached."})
                break

            if run_break_seconds > 0 and break_seconds > 0:
                if (now_t - run_started_at) >= run_break_seconds:
                    self._emit(
                        "log",
                        {
                            "level": "warn",
                            "message": (
                                f"Cycle pause triggered. Active run window reached {run_break_seconds:.2f}s. "
                                f"Pausing for {break_seconds:.2f}s."
                            ),
                        },
                    )
                    try:
                        self._client.reset_seed()
                        self._emit("log", {"level": "info", "message": "Seed refreshed before cycle pause."})
                    except Exception as exc:
                        self._emit("log", {"level": "error", "message": f"Seed refresh failed before cycle pause: {exc}"})
                    time.sleep(break_seconds)
                    run_started_at = time.monotonic()
                    continue

            try:
                # Fase 1.2: read-back chance/nextbet/bethigh dari Lua via
                # mirror, lalu clamp di Python (skip 3x get_global +
                # konversi inline).
                mirror.read_back()
                chance = min(98.0, max(0.01, mirror.chance))
                nextbet = mirror.nextbet
                bethigh = mirror.bethigh
                if nextbet <= 0:
                    nextbet = basebet
                if nextbet < 0.00000001:
                    nextbet = 0.00000001
                if flatbet_active:
                    nextbet = max(min_bet, flatbet_amount)
                # Push back nilai ter-clamp ke Lua (single batch ke 3 key)
                mirror.write_clamps(chance, nextbet, bethigh)
                if balance + 1e-12 < nextbet:
                    # Fase 3.3: throttle balance probe — jangan refresh
                    # lebih sering dari min_refresh_interval kecuali
                    # belum pernah probe sama sekali.
                    if (now_t - last_balance_refresh_at) >= min_refresh_interval:
                        try:
                            refreshed_balances = balance_list_from_response(self._client.balances())
                            refreshed_balance = currency_balance(refreshed_balances, config.currency)
                            last_balance_refresh_at = time.monotonic()
                            if refreshed_balance > balance:
                                injection = refreshed_balance - balance
                                if injection > 1e-7:
                                    session_profit += injection
                                    total_profit += injection
                                    self._emit(
                                        "log",
                                        {
                                            "level": "info",
                                            "message": (
                                                f"Profit Fast Detected: +{injection:.8f} "
                                                f"{config.currency}"
                                            ),
                                        },
                                    )
                                balance = refreshed_balance
                                mirror.balance = balance
                                mirror._setitem("balance", balance)
                                self._emit(
                                    "log",
                                    {
                                        "level": "info",
                                        "message": f"Balance refreshed: {balance:.8f} {config.currency}.",
                                    },
                                )
                        except Exception as exc:
                            self._emit("log", {"level": "error", "message": f"Balance refresh failed: {exc}"})
                if balance + 1e-12 < nextbet:
                    has_known_balance = getattr(self._client, "has_known_balance", None)
                    balance_known = True
                    if callable(has_known_balance):
                        try:
                            balance_known = bool(has_known_balance(config.currency))
                        except Exception:
                            balance_known = True
                    if (
                        getattr(self._client, "balance_is_deferred", False)
                        and not balance_known
                        and session_bets == 0
                        and not deferred_balance_probe_attempted
                    ):
                        deferred_balance_probe_attempted = True
                        self._emit(
                            "log",
                            {
                                "level": "warn",
                                "message": (
                                    f"Balance {config.currency} belum dikirim site; "
                                    "trying first bet to trigger live balance update."
                                ),
                            },
                        )
                    else:
                        self._set_state("paused")
                        self._emit(
                            "log",
                            {
                                "level": "warn",
                                "message": (
                                    f"Available funds below required size. Need {nextbet:.8f} {config.currency}, "
                                    f"available {balance:.8f} {config.currency}."
                                ),
                            },
                        )
                        continue

                # Fase 6.3: watchdog soft — kalau place_bet melebihi
                # threshold, log warning. Tidak force-cancel (request lib
                # tidak support cancel mid-flight).
                bet_started_at = time.monotonic()
                watchdog_threshold = min(max(interval_ms / 1000.0 * 5.0, 5.0), 10.0)

                result = self._client.place_bet(config.currency.lower(), nextbet, chance, bethigh)

                bet_elapsed = time.monotonic() - bet_started_at
                if bet_elapsed > watchdog_threshold:
                    self._emit(
                        "log",
                        {
                            "level": "warn",
                            "message": (
                                f"Slow bet response: {bet_elapsed:.1f}s "
                                f"(threshold {watchdog_threshold:.1f}s). Network or API slow."
                            ),
                        },
                    )

                # Fase 1.4: ekstrak field response sekali jalan
                # Simpan balance sebelum bet untuk deteksi deposit
                _balance_before_bet = balance
                placed_amount, win, roll, current_profit, new_balance = _extract_bet_result(
                    result, fallback_amount=nextbet, fallback_balance=balance
                )
                # Deteksi deposit/top-up: kalau balance baru > balance lama
                # + profit dari bet ini, selisihnya adalah suntikan dana.
                _expected = _balance_before_bet + current_profit
                _injection = new_balance - _expected
                if _injection > 1e-7:
                    session_profit += _injection
                    total_profit += _injection
                    self._emit(
                        "log",
                        {
                            "level": "info",
                            "message": (
                                f"Profit Fast Detected: +{_injection:.8f} "
                                f"{config.currency}"
                            ),
                        },
                    )
                balance = new_balance

                total_bets += 1
                total_profit += current_profit
                total_wagered += placed_amount
                session_bets += 1
                overall_steps += 1
                session_profit += current_profit
                session_wagered += placed_amount
                if placed_amount > highest_bet:
                    highest_bet = placed_amount
                if win:
                    total_wins += 1
                    session_wins += 1
                    current_streak = current_streak + 1 if current_streak >= 0 else 1
                else:
                    total_losses += 1
                    session_losses += 1
                    current_streak = current_streak - 1 if current_streak <= 0 else -1
                    if -current_streak > max_lose_streak:
                        max_lose_streak = -current_streak

                # Fase 2.1: update mirror slot (Python state) + 1 flush
                # batch ke Lua. Hindari 18x __setitem__ ke Lua bridge
                # tiap cycle. partialprofit dibaca-update-tulis sekali.
                mirror.previousbet = nextbet
                mirror.win = win
                mirror.currentroll = roll
                mirror.currentprofit = current_profit
                mirror.currentstreak = current_streak
                mirror.balance = balance
                mirror.bets = session_bets
                mirror.wins = session_wins
                mirror.losses = session_losses
                mirror.profit = session_profit
                mirror.wagered = session_wagered
                mirror.totalbets = total_bets
                mirror.totalwins = total_wins
                mirror.totallosses = total_losses
                mirror.totalprofit = total_profit
                mirror.totalwagered = total_wagered
                mirror.partialprofit = mirror.partialprofit + current_profit
                mirror.flush()
                # Fase 2.2: lastBet — mutate persistent table (kalau lupa
                # support), bukan rebuild dict tiap cycle.
                mirror.update_last_bet(roll, session_bets)

                # Fase 1.3: lazy snapshot — bangun SessionSnapshot hanya
                # kalau perlu (ada take-profit/auto-switch check yang
                # baca .profit_pct, ATAU tick UI emit). Profit_pct
                # dihitung inline murah — tidak perlu full dataclass
                # untuk threshold check.
                if start_balance > 0:
                    profit_pct_now = (session_profit / start_balance) * 100.0
                else:
                    profit_pct_now = 0.0

                tick_should_emit = (
                    win  # UI cek stop-on-success
                    or session_bets <= 1
                    or session_bets % max(1, log_every) == 0
                )
                # Bangun snapshot hanya kalau benar-benar di-emit ATAU
                # ada threshold check butuh data lengkap (auto-switch
                # baru perlu `snapshot.profit_pct` saja → kita pakai
                # profit_pct_now di atas).
                snapshot = None
                if tick_should_emit:
                    snapshot = self._build_snapshot(
                        self.state,
                        config,
                        started_at,
                        start_balance,
                        balance,
                        session_profit,
                        session_wagered,
                        session_bets,
                        session_wins,
                        session_losses,
                        total_bets,
                        total_wins,
                        total_losses,
                        total_profit,
                        total_wagered,
                        highest_bet,
                        max_lose_streak,
                        roll,
                        placed_amount,
                        win,
                        chance,
                        bethigh,
                    )
                    self._emit("stats", snapshot)

                if session_bets % max(1, log_every) == 0:
                    line = (
                        f"{session_bets:>5} | {'POS' if win else 'NEG'} | "
                        f"size={placed_amount:.8f} | threshold={chance:05.2f} | "
                        f"result={roll:05.2f} | delta={current_profit:+.8f} | "
                        f"equity={balance:.8f}"
                    )
                    self._emit("log", {"level": "success" if win else "error", "message": line})

                # Fase 1.5: pakai cached dobet, tidak panggil get_global
                # tiap cycle. Re-resolve hanya saat strategy switch.
                if dobet_cached is not None:
                    try:
                        dobet_cached()
                    except Exception:
                        # Strategy mungkin overwrite dobet di runtime;
                        # fallback ke lookup dinamis sekali sebelum re-throw.
                        fallback = get_global(globs, "dobet", None)
                        if fallback is not None and fallback is not dobet_cached:
                            dobet_cached = fallback
                            dobet_cached()
                        else:
                            raise

                if self._pause_on_win_enabled(pause_on_win) and win:
                    self._emit("log", {"level": "warn", "message": "Stop on positive result triggered."})
                    break

                if flatbet_trigger_pct > 0 and flatbet_minutes > 0 and flatbet_amount > 0:
                    if not flatbet_active and profit_pct_now >= flatbet_trigger_pct:
                        level = int(profit_pct_now / flatbet_trigger_pct)
                        if level > flatbet_last_level:
                            flatbet_last_level = level
                            flatbet_active = True
                            flatbet_start_at = time.monotonic()
                            self._emit(
                                "log",
                                {
                                    "level": "info",
                                    "message": (
                                        f"Flat allocation mode enabled at growth {profit_pct_now:.4f}%. "
                                        f"Amount={max(min_bet, flatbet_amount):.8f} for {flatbet_minutes:.2f}m."
                                    ),
                                },
                            )
                    if flatbet_active and (time.monotonic() - flatbet_start_at) >= flatbet_minutes * 60.0:
                        flatbet_active = False
                        self._emit("log", {"level": "info", "message": "Flat allocation mode completed."})

                if take_profit_pct > 0 and profit_pct_now >= take_profit_pct:
                    self._emit(
                        "log",
                        {
                            "level": "warn",
                            "message": (
                                f"Target growth reached: {profit_pct_now:.4f}% / "
                                f"{take_profit_pct:.4f}%."
                            ),
                        },
                    )
                    break

                if auto_switch_profit_pct > 0 and profit_pct_now >= auto_switch_profit_pct:
                    if len(strategy_order) > 1:
                        next_strategy_index = (current_strategy_index + 1) % len(strategy_order)
                        next_strategy_name = strategy_order[next_strategy_index]
                        self._emit(
                            "log",
                            {
                                "level": "warn",
                                "message": (
                                    f"Auto-switch triggered at growth {profit_pct_now:.4f}% "
                                    f"({config.strategy_name} -> {next_strategy_name})."
                                ),
                            },
                        )
                        current_strategy_index = next_strategy_index
                        config.strategy_name = next_strategy_name
                        config.strategy_path = resolve_strategy_path(next_strategy_name)
                        active_profile = resolve_profile(next_strategy_name)
                        interval_ms = active_profile.interval_ms
                        log_every = active_profile.log_every
                        take_profit_pct = active_profile.take_profit_pct
                        pause_on_win = active_profile.pause_on_win
                        auto_switch_profit_pct = active_profile.auto_switch_profit_pct
                        run_break_seconds = active_profile.run_break_seconds
                        break_seconds = active_profile.break_seconds
                        flatbet_trigger_pct = active_profile.flatbet_trigger_pct
                        flatbet_minutes = active_profile.flatbet_minutes
                        flatbet_amount = active_profile.flatbet_amount
                        if 0 < flatbet_amount < min_bet:
                            flatbet_amount = min_bet
                        # Fase 6.2: explicit drop reference Lua lama supaya GC
                        # bisa reklamasi LuaRuntime sebelum alokasi yang baru.
                        del globs
                        del mirror
                        gc.collect()
                        globs, chance, basebet, nextbet, bethigh = self._prepare_strategy_runtime(
                            config.strategy_path,
                            config.currency,
                            balance,
                            account,
                            remote_config=config.remote_config,
                            license_status=config.license_status,
                        )
                        # Re-resolve dobet cache untuk strategy baru (Fase 1.5)
                        dobet_cached = get_global(globs, "dobet", None)
                        # Re-init mirror untuk strategy baru
                        mirror = LuaStateMirror(globs)
                        mirror.chance = chance
                        mirror.nextbet = nextbet
                        mirror.bethigh = bethigh
                        mirror.balance = balance
                        mirror.totalbets = total_bets
                        mirror.totalwins = total_wins
                        mirror.totallosses = total_losses
                        mirror.totalprofit = total_profit
                        mirror.totalwagered = total_wagered
                        mirror.init_last_bet_table(_lua_for_globs(globs))
                        session_bets = 0
                        session_wins = 0
                        session_losses = 0
                        session_profit = 0.0
                        session_wagered = 0.0
                        highest_bet = 0.0
                        max_lose_streak = 0
                        current_streak = 0
                        start_balance = balance
                        started_at = time.monotonic()
                        run_started_at = started_at
                        flatbet_active = False
                        flatbet_start_at = 0.0
                        flatbet_last_level = 0
                        continue
                    self._emit("log", {"level": "warn", "message": "Auto-switch ignored: only one strategy available."})

                consecutive_errors = 0
                if interval_ms > 0:
                    time.sleep(interval_ms / 1000.0)
            except Exception as exc:
                if is_authentication_error(exc):
                    self._emit("log", {"level": "error", "message": f"Authentication failed: {exc}"})
                    break
                if is_insufficient_balance_error(exc):
                    self._set_state("paused")
                    self._emit("log", {"level": "warn", "message": f"Available funds insufficient: {exc}"})
                    continue
                consecutive_errors += 1
                self._emit("log", {"level": "error", "message": f"Runtime error ({consecutive_errors}/{max_errors}): {exc}"})
                if consecutive_errors >= max_errors:
                    self._emit("log", {"level": "error", "message": "Stopped: too many runtime errors."})
                    break
                time.sleep(max(interval_ms / 1000.0, 0.5))

        snapshot = self._build_snapshot(
            "stopped",
            config,
            started_at,
            start_balance,
            balance,
            session_profit,
            session_wagered,
            session_bets,
            session_wins,
            session_losses,
            total_bets,
            total_wins,
            total_losses,
            total_profit,
            total_wagered,
            highest_bet,
            max_lose_streak,
            float(get_global(globs, "currentroll", 0.0)),
            float(get_global(globs, "previousbet", 0.0)),
            bool(get_global(globs, "win", False)) if session_bets else None,
            float(get_global(globs, "chance", chance)),
            bool(get_global(globs, "bethigh", bethigh)),
        )
        self._emit("stats", snapshot)
        self._set_state("stopped")
        self._emit("log", {"level": "info", "message": "Session stopped."})

    def _prepare_strategy_runtime(
        self,
        strategy_path: Path,
        currency: str,
        balance: float,
        account: AccountSnapshot,
        *,
        remote_config: dict | None = None,
        license_status: dict | None = None,
    ):
        # Pindah ke `engine/_lua_runtime.py` (Step L-D). Method ini jadi
        # delegate yang mem-bind `self._client` & `self._stop_event` ke
        # fungsi standalone.
        from ._lua_runtime import prepare_strategy_runtime
        return prepare_strategy_runtime(
            strategy_path,
            currency,
            balance,
            account,
            client=self._client,
            stop_event=self._stop_event,
            remote_config=remote_config,
            license_status=license_status,
        )
