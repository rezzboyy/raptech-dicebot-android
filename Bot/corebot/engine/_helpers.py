"""Engine utility helpers (lua extraction + bet result parsing).

Diekstrak dari `engine/__init__.py` (Fase 3 perapihan, Step L-B).
Pure helpers — tidak menyentuh state engine.

Public API (di-re-export oleh `engine/__init__.py`):
    - `_lua_for_globs(globs)`
    - `_extract_bet_result(result, fallback_amount, fallback_balance)`
"""
from __future__ import annotations


def _lua_for_globs(globs):
    """Coba ekstrak `LuaRuntime` dari Lua globals table.

    Lupa tidak expose runtime di public API per object, tapi method
    internal `_runtime` ada. Kita try-except supaya kalau berubah di
    versi lupa baru, fallback ke None (mirror pakai dict path).
    """
    try:
        return globs._runtime  # type: ignore[attr-defined]
    except Exception:
        return None


def _extract_bet_result(
    result: dict,
    fallback_amount: float,
    fallback_balance: float,
) -> tuple[float, bool, float, float, float]:
    """Ekstrak `(placed_amount, win, roll, current_profit, balance)` dari
    response `place_bet` dengan path yang dikenali. Helper Fase 1.4 —
    sekali jalan, hindari `.get("x", {}).get("y", default)` chain di
    hot loop.

    Default-default dipertahankan sama dengan kode sebelumnya untuk
    menjaga determinism: kalau field tidak ada, gunakan fallback yang
    diberikan caller.
    """
    bet = result.get("bet") or {}
    user_balance = result.get("userBalance") or {}
    try:
        placed = float(bet.get("amount") or fallback_amount)
    except (TypeError, ValueError):
        placed = fallback_amount
    win = bet.get("state") == "win"
    try:
        roll = float(bet.get("result_value") or 0)
    except (TypeError, ValueError):
        roll = 0.0
    try:
        cprofit = float(bet.get("profit") or 0)
    except (TypeError, ValueError):
        cprofit = 0.0
    try:
        balance = float(user_balance.get("amount") or fallback_balance)
    except (TypeError, ValueError):
        balance = fallback_balance
    return placed, win, roll, cprofit, balance
