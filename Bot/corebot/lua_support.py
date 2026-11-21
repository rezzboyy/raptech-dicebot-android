from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Fase 5.1 (perf plan): lazy import LuaRuntime supaya cold start cli +
# license check tidak ikut paksa load `lupa` (LuaJIT bridge ~6-8ms).
# `LuaRuntime` baru di-load saat strategy benar-benar dijalankan.


def _lua_runtime_cls():
    """Return LuaRuntime class. Auto-select LuaJIT 2.1 kalau tersedia
    (10x lebih cepat dari Lua 5.5), fallback ke versi lain.

    Override via env var RAPTECH_LUA:
        auto (default)   - prefer LuaJIT 2.1, fallback ke lua55/54/dst
        luajit21         - force LuaJIT 2.1 (10x faster, Lua 5.1 semantic)
        luajit20         - force LuaJIT 2.0
        lua55/54/53/52/51 - force plain Lua versi tsb
    """
    import os as _os
    prefer = (_os.getenv("RAPTECH_LUA") or "auto").lower().strip()

    # Urutan preferensi: LuaJIT 2.1 (paling cepat) -> lua55 (paling baru)
    order = ("luajit21", "luajit20", "lua55", "lua54", "lua53", "lua52", "lua51")
    if prefer != "auto" and prefer in order:
        # Force specific runtime
        try:
            mod = __import__(f"lupa.{prefer}", fromlist=[prefer])
            return mod.LuaRuntime
        except ImportError:
            pass  # fall through to auto

    # Auto mode - coba dari yang paling cepat
    for variant in order:
        try:
            mod = __import__(f"lupa.{variant}", fromlist=[variant])
            return mod.LuaRuntime
        except ImportError:
            continue

    # Last resort - lupa default (biasanya versi terbaru)
    from lupa import LuaRuntime
    return LuaRuntime


# ---- Preprocess cache (Fase 2.3) -----------------------------------------
# Cache hasil `preprocess_lua` per (path, mtime, size, sha256) supaya
# auto-switch strategy yang sering ganti tidak re-jalankan regex setiap
# load. Catatan: kita TIDAK cache `LuaRuntime` itu sendiri (state Lua
# tidak boleh di-share lintas session).


@dataclass(frozen=True, slots=True)
class _PreprocessCacheKey:
    path: str
    mtime_ns: int
    size: int


_PREPROCESS_CACHE: dict[_PreprocessCacheKey, str] = {}


def preprocess_lua(text: str) -> str:
    normalized = re.sub(r"!(?!=)", "not ", text)
    normalized = normalized.replace("!=", "~=")

    def expand_compound(match: re.Match[str]) -> str:
        indent = match.group(1)
        target = match.group(2)
        operator = match.group(3)
        expression = match.group(4)
        return f"{indent}{target} = {target} {operator} {expression}"

    return re.sub(
        r"(?m)^(\s*)([A-Za-z_][A-Za-z0-9_\.]*)\s*([+\-*/])=\s*(.+)$",
        expand_compound,
        normalized,
    )


# Helper baru untuk Lua math.random patch — di-load sekali sebagai snippet
# konstan supaya tidak alokasi string baru tiap load.
_RANDOM_PATCH = """
local _orig_random = math.random
function math.random(a, b)
    if a == nil and b == nil then
        return _orig_random()
    end
    if b == nil then
        if type(a) == "number" and a % 1 ~= 0 then
            return _orig_random() * a
        end
        return _orig_random(a)
    end
    if type(a) == "number" and type(b) == "number" then
        if a % 1 ~= 0 or b % 1 ~= 0 then
            return a + (_orig_random() * (b - a))
        end
    end
    return _orig_random(a, b)
end
"""


def _read_preprocessed(lua_path: Path) -> str:
    try:
        stat = lua_path.stat()
        key = _PreprocessCacheKey(
            path=str(lua_path),
            mtime_ns=stat.st_mtime_ns,
            size=stat.st_size,
        )
    except OSError:
        # Stat gagal — fallback ke load tanpa cache.
        return preprocess_lua(lua_path.read_text(encoding="utf-8"))
    cached = _PREPROCESS_CACHE.get(key)
    if cached is not None:
        return cached
    raw = lua_path.read_text(encoding="utf-8")
    processed = preprocess_lua(raw)
    _PREPROCESS_CACHE[key] = processed
    # Bound cache size supaya tidak unbounded di session panjang
    if len(_PREPROCESS_CACHE) > 32:
        # Drop oldest insertion (Python dict preserves order)
        _PREPROCESS_CACHE.pop(next(iter(_PREPROCESS_CACHE)))
    return processed


def load_lua_strategy(lua_path: Path, initial_globals: dict | None = None):
    """Load strategy ke LuaRuntime baru.

    Source di-cache hasil preprocess-nya per file mtime+size. LuaRuntime
    sendiri tetap baru tiap call (state tidak di-share).
    """
    processed = _read_preprocessed(lua_path)
    LuaRuntime = _lua_runtime_cls()
    lua = LuaRuntime(unpack_returned_tuples=True)
    if initial_globals:
        globals_table = lua.globals()
        for key, value in initial_globals.items():
            globals_table[key] = value
    lua.execute(_RANDOM_PATCH)
    lua.execute(processed)
    return lua


def get_global(globals_table, name: str, default):
    try:
        value = globals_table[name]
    except Exception:
        return default
    return default if value is None else value


# ---- Fase 1.2 + 2.1 + 2.2: LuaStateMirror --------------------------------


# Field yang ditulis Python → Lua tiap cycle. Urutan tetap konsisten
# dengan engine sebelumnya untuk menjaga determinism.
_MIRROR_WRITE_KEYS: tuple[str, ...] = (
    "previousbet", "win", "currentroll", "currentprofit", "currentstreak",
    "balance", "bets", "wins", "losses", "profit", "wagered",
    "totalbets", "totalwins", "totallosses", "totalprofit", "totalwagered",
    "partialprofit",
)

# Field yang dibaca-balik dari Lua setelah `dobet()` (strategy boleh
# memodifikasi). Hanya 3 key utama yang dipakai engine — selebihnya
# strategy-private.
_MIRROR_READ_KEYS: tuple[str, ...] = ("chance", "nextbet", "bethigh")


class LuaStateMirror:
    """Buffered mirror antara Python dan Lua globals.

    Tujuan: hindari per-attribute Lua bridge call tiap cycle. Engine
    update field via setattr di mirror, lalu satu kali flush sebelum
    panggil `dobet()`. Setelah `dobet` selesai, `read_back()` ambil
    field user-modifiable kembali ke Python.

    Reuse `lastBet` table: alokasi sekali, mutate field setelahnya
    (Fase 2.2). Tabel di-share dengan strategy via globals.
    """

    __slots__ = (
        "_globs",
        "_setitem",
        "_getitem",
        "_last_bet_table",
        # Slot mirror — di-set engine, di-flush ke Lua via flush().
        "previousbet", "win", "currentroll", "currentprofit", "currentstreak",
        "balance", "bets", "wins", "losses", "profit", "wagered",
        "totalbets", "totalwins", "totallosses", "totalprofit", "totalwagered",
        "partialprofit",
        # Read-back slot
        "chance", "nextbet", "bethigh",
    )

    def __init__(self, globs):
        self._globs = globs
        # Cache bound method untuk dict-like access supaya skip attribute
        # lookup tiap call.
        self._setitem = globs.__setitem__
        self._getitem = globs.__getitem__
        self._last_bet_table = None
        # Initialize slot dari Lua globals (atau default aman).
        self.previousbet = float(get_global(globs, "previousbet", 0.0))
        self.win = bool(get_global(globs, "win", False))
        self.currentroll = float(get_global(globs, "currentroll", 0.0))
        self.currentprofit = float(get_global(globs, "currentprofit", 0.0))
        self.currentstreak = int(get_global(globs, "currentstreak", 0))
        self.balance = float(get_global(globs, "balance", 0.0))
        self.bets = int(get_global(globs, "bets", 0))
        self.wins = int(get_global(globs, "wins", 0))
        self.losses = int(get_global(globs, "losses", 0))
        self.profit = float(get_global(globs, "profit", 0.0))
        self.wagered = float(get_global(globs, "wagered", 0.0))
        self.totalbets = int(get_global(globs, "totalbets", 0))
        self.totalwins = int(get_global(globs, "totalwins", 0))
        self.totallosses = int(get_global(globs, "totallosses", 0))
        self.totalprofit = float(get_global(globs, "totalprofit", 0.0))
        self.totalwagered = float(get_global(globs, "totalwagered", 0.0))
        self.partialprofit = float(get_global(globs, "partialprofit", 0.0))
        self.chance = float(get_global(globs, "chance", 49.5))
        self.nextbet = float(get_global(globs, "nextbet", 0.0))
        self.bethigh = bool(get_global(globs, "bethigh", False))

    def init_last_bet_table(self, lua) -> None:
        """Alokasi `lastBet` table sekali, share via globals (Fase 2.2).

        `lua` boleh None — fallback ke Python dict yang setiap update
        rebuild penuh (sama behavior dengan kode sebelum optimasi).
        """
        if lua is not None:
            try:
                tbl = lua.table_from({"Roll": 0.0, "Nonce": 0})
            except Exception:
                tbl = None
        else:
            tbl = None
        self._last_bet_table = tbl
        try:
            if tbl is not None:
                self._setitem("lastBet", tbl)
            else:
                self._setitem("lastBet", {"Roll": 0.0, "Nonce": 0})
        except Exception:
            pass

    def update_last_bet(self, roll: float, nonce: int) -> None:
        tbl = self._last_bet_table
        if tbl is None:
            # Fallback path
            try:
                self._setitem("lastBet", {"Roll": roll, "Nonce": nonce})
            except Exception:
                pass
            return
        try:
            tbl["Roll"] = roll
            tbl["Nonce"] = nonce
        except Exception:
            # Lua table tidak support __setitem__? Fallback rebuild.
            try:
                self._setitem("lastBet", {"Roll": roll, "Nonce": nonce})
            except Exception:
                pass

    def flush(self) -> None:
        """Tulis semua slot mirror ke Lua globals sekali jalan.

        Urutan write konsisten dengan engine sebelumnya untuk menjaga
        determinism strategy yang sensitif terhadap urutan baca.
        """
        s = self._setitem
        s("previousbet", self.previousbet)
        s("win", self.win)
        s("currentroll", self.currentroll)
        s("currentprofit", self.currentprofit)
        s("currentstreak", self.currentstreak)
        s("balance", self.balance)
        s("bets", self.bets)
        s("wins", self.wins)
        s("losses", self.losses)
        s("profit", self.profit)
        s("wagered", self.wagered)
        s("totalbets", self.totalbets)
        s("totalwins", self.totalwins)
        s("totallosses", self.totallosses)
        s("totalprofit", self.totalprofit)
        s("totalwagered", self.totalwagered)
        s("partialprofit", self.partialprofit)

    def read_back(self) -> None:
        """Baca field user-modifiable dari Lua globals ke slot Python.

        Strategy `dobet()` boleh memodifikasi `chance`, `nextbet`,
        `bethigh`. Mirror sync ulang setelah `dobet` selesai.
        """
        g = self._getitem
        try:
            self.chance = float(g("chance"))
        except Exception:
            pass
        try:
            self.nextbet = float(g("nextbet"))
        except Exception:
            pass
        try:
            self.bethigh = bool(g("bethigh"))
        except Exception:
            pass

    def write_clamps(self, chance_clamped: float, nextbet_clamped: float, bethigh_b: bool) -> None:
        """Push back nilai chance/nextbet/bethigh yang sudah di-clamp engine.

        Dipakai saat engine override (mis. flatbet_active memaksa
        nextbet ke flatbet_amount). Strategy melihat nilai ter-clamp.
        """
        self.chance = chance_clamped
        self.nextbet = nextbet_clamped
        self.bethigh = bethigh_b
        s = self._setitem
        s("chance", chance_clamped)
        s("nextbet", nextbet_clamped)
        s("bethigh", bethigh_b)


# ---- Fase 3.4: orjson opsional -------------------------------------------


def fast_json_loads(data):
    """Loader JSON yang otomatis pakai `orjson` kalau tersedia.

    `requests.Response.json()` tidak akan otomatis pakai ini — caller
    perlu lakukan `fast_json_loads(resp.content)` secara eksplisit.
    Kalau orjson tidak terinstall, fallback ke stdlib `json.loads`.
    """
    try:
        import orjson  # type: ignore
        return orjson.loads(data)
    except ImportError:
        import json as _json
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        return _json.loads(data)
    except Exception:
        import json as _json
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        return _json.loads(data)


def is_insufficient_balance_error(exc: Exception) -> bool:
    text = str(exc).lower()
    if "insufficient" in text:
        return True
    if "not enough" in text and ("balance" in text or "fund" in text):
        return True
    if "saldo" in text and ("kurang" in text or "tidak cukup" in text):
        return True
    if "exceeds" in text and ("balance" in text or "fund" in text):
        return True
    return False


def is_authentication_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "unauthorized",
            "forbidden",
            "not authenticated",
            "invalid token",
            "jwt expired",
            "token expired",
            "invalid authorization",
        )
    )
