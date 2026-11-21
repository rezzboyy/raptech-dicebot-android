from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import (
    DEFAULT_SITE,
    settings_paths,
    settings_write_paths,
    token_paths,
    token_write_paths,
    tokens_paths,
    tokens_write_paths,
)
from .models import SessionProfile


def _load_text(paths: tuple[Path, ...]) -> tuple[str | None, Path | None]:
    for path in paths:
        if not path.is_file():
            continue
        try:
            return path.read_text(encoding="utf-8").strip() or None, path
        except OSError:
            continue
    return None, None


def _save_text(value: str, primary: Path, fallback: Path) -> Path | None:
    for path in (primary, fallback):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")
            return path
        except OSError:
            continue
    return None


def load_saved_token() -> tuple[str | None, Path | None]:
    return _load_text(token_paths())


def save_token(token: str) -> Path | None:
    primary, fallback = token_write_paths()
    return _save_text(token, primary, fallback)


# ---------- Multi-site tokens (apitokens.json) ----------------------------


def load_tokens() -> dict[str, Any]:
    """Baca apitokens.json (dict per-situs).

    Value tiap entry boleh berbentuk:
    - **string**: untuk situs single-credential (bearer/cookie tunggal)
    - **dict**: untuk situs yang butuh lebih dari satu credential

    Kalau file belum ada tapi token legacy (apitoken/.wolfbet_token) ada,
    seed otomatis ke entry untuk DEFAULT_SITE agar transisi mulus.
    """
    for path in tokens_paths():
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict):
            out: dict[str, Any] = {}
            for site, value in raw.items():
                key = str(site).lower()
                if isinstance(value, str) and value.strip():
                    out[key] = value.strip()
                elif isinstance(value, dict):
                    # Drop empty/None values, lower-case keys.
                    out[key] = {
                        str(k): v for k, v in value.items() if v not in (None, "")
                    }
            return out
    legacy_token, _ = load_saved_token()
    if legacy_token:
        return {DEFAULT_SITE: legacy_token}
    return {}


def save_tokens(tokens: dict[str, Any]) -> Path | None:
    payload: dict[str, Any] = {}
    for site, value in tokens.items():
        key = str(site).lower()
        if isinstance(value, str) and value.strip():
            payload[key] = value.strip()
        elif isinstance(value, dict) and value:
            payload[key] = dict(value)
    primary, fallback = tokens_write_paths()
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    for path in (primary, fallback):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(serialized, encoding="utf-8")
            return path
        except OSError:
            continue
    return None


def get_token_for(site: str) -> str | None:
    """Ambil token untuk situs tertentu sebagai string.

    Multi-account format (semua site): kalau value berupa dict dengan
    key "accounts", ambil token dari akun aktif.

    Untuk situs dual-credential lain (value dict tanpa key "accounts"),
    kembalikan **JSON-stringified** dict — client bersangkutan akan
    parse balik. Ini menjaga interface tetap `str | None` agar
    engine/CLI generic ngga perlu peduli detail.

    Fallback ke legacy single-token untuk DEFAULT_SITE biar user lama
    ngga perlu paste ulang.
    """
    tokens = load_tokens()
    key = (site or "").lower()
    if key in tokens:
        value = tokens[key]
        # Multi-account format: {"accounts": [...], "active": N}
        if isinstance(value, dict) and "accounts" in value:
            accounts = value.get("accounts", [])
            active = int(value.get("active", 0))
            if accounts and active < len(accounts):
                return str(accounts[active].get("token", ""))
            elif accounts:
                return str(accounts[0].get("token", ""))
            return None
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
    if key == DEFAULT_SITE:
        legacy_token, _ = load_saved_token()
        return legacy_token
    return None


def set_token_for(site: str, token: str) -> Path | None:
    """Simpan token. `token` boleh string biasa atau JSON object string
    (untuk situs dual-credential — akan auto-decoded ke dict di file).

    Multi-account (semua site): kalau storage sudah pakai format
    `{accounts: [...], active: N}`, update token di akun aktif — jangan
    overwrite seluruh struct.
    """
    tokens = load_tokens()
    key = (site or "").lower()
    raw = (token or "").strip()

    # Multi-account format: update token akun aktif
    existing = tokens.get(key)
    if isinstance(existing, dict) and "accounts" in existing:
        accounts = existing.get("accounts", [])
        active = int(existing.get("active", 0))
        if accounts and active < len(accounts):
            accounts[active]["token"] = raw
            existing["accounts"] = accounts
            tokens[key] = existing
            return save_tokens(tokens)

    # Coba decode kalau user paste JSON object — simpan jadi dict di file
    # supaya enak dibaca/dibedit manual oleh user.
    if raw.startswith("{") and raw.endswith("}"):
        try:
            decoded = json.loads(raw)
            if isinstance(decoded, dict):
                tokens[key] = decoded
                return save_tokens(tokens)
        except json.JSONDecodeError:
            pass
    tokens[key] = raw
    return save_tokens(tokens)


# ---------- Proxy per-site (advancedset.json > proxies) -------------------


def _parse_proxy_url(url: str) -> dict[str, str] | None:
    """Parse proxy URL → dict format yang dipahami requests/curl_cffi.

    Terima format:
      http://host:port
      http://user:pass@host:port
      https://host:port
      socks5://user:pass@host:port
      socks4://host:port

    Return dict {"http": url, "https": url} atau None kalau invalid.
    """
    raw = (url or "").strip()
    if not raw:
        return None
    if not any(raw.lower().startswith(p) for p in ("http://", "https://", "socks5://", "socks4://", "socks5h://")):
        # Auto-tambah scheme http:// kalau user cuma paste host:port
        if ":" in raw and "//" not in raw:
            raw = "http://" + raw
        else:
            return None
    return {"http": raw, "https": raw}


def get_proxy_for(site: str) -> dict[str, str] | None:
    """Ambil proxy config untuk situs tertentu. Return dict format
    requests-compatible atau None kalau tidak ada.
    """
    store = load_settings_store()
    proxies = store.get("proxies") or {}
    if not isinstance(proxies, dict):
        return None
    url = proxies.get((site or "").lower())
    if not url:
        return None
    return _parse_proxy_url(str(url))


def get_proxy_url_for(site: str) -> str:
    """Ambil proxy URL raw (untuk display di UI). Return string kosong
    kalau tidak ada.
    """
    store = load_settings_store()
    proxies = store.get("proxies") or {}
    if not isinstance(proxies, dict):
        return ""
    return str(proxies.get((site or "").lower(), "") or "")


def set_proxy_for(site: str, url: str) -> Path | None:
    """Set atau clear proxy untuk situs. Passing string kosong = clear."""
    store = load_settings_store()
    proxies = store.setdefault("proxies", {})
    if not isinstance(proxies, dict):
        proxies = {}
        store["proxies"] = proxies
    key = (site or "").lower()
    clean = (url or "").strip()
    if not clean:
        proxies.pop(key, None)
    else:
        proxies[key] = clean
    return save_settings_store(store)


def load_settings_store() -> dict[str, Any]:
    default_store: dict[str, Any] = {"profiles": {}, "ui": {}, "proxies": {}}
    for path in settings_paths():
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        profiles = raw.get("profiles")
        ui = raw.get("ui")
        proxies = raw.get("proxies")
        if not isinstance(profiles, dict):
            profiles = {}
        if not isinstance(ui, dict):
            ui = {}
        if not isinstance(proxies, dict):
            proxies = {}
        return {"profiles": profiles, "ui": ui, "proxies": proxies}
    return default_store


def save_settings_store(store: dict[str, Any]) -> Path | None:
    payload = {
        "profiles": dict(store.get("profiles", {})),
        "ui": dict(store.get("ui", {})),
        "proxies": dict(store.get("proxies", {})),
    }
    # Drop empty proxies key kalau tidak ada isi supaya file tetap bersih
    if not payload["proxies"]:
        payload.pop("proxies")
    primary, fallback = settings_write_paths()
    for path in (primary, fallback):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            return path
        except OSError:
            continue
    return None


def runtime_profile_key(strategy_name: str, currency: str) -> str:
    """Format key lama (untuk back-compat). Format baru pakai site-prefixed."""
    return f"{strategy_name.lower()}::{currency.upper()}"


def runtime_profile_key_for_site(site: str, strategy_name: str, currency: str) -> str:
    """Format key baru: <site>::<strategy>::<CURRENCY>."""
    return f"{(site or DEFAULT_SITE).lower()}::{strategy_name.lower()}::{currency.upper()}"


def get_profile_entry(
    settings_store: dict[str, Any],
    site: str,
    strategy_name: str,
    currency: str,
) -> dict[str, Any] | None:
    """Cari entry profile dengan urutan: (1) site-prefixed, (2) legacy unscoped (cuma DEFAULT_SITE).

    Mengembalikan dict mentah atau None bila belum tersimpan.
    """
    profiles = settings_store.setdefault("profiles", {})
    new_key = runtime_profile_key_for_site(site, strategy_name, currency)
    if new_key in profiles:
        return profiles[new_key]
    if (site or "").lower() == DEFAULT_SITE:
        legacy_key = runtime_profile_key(strategy_name, currency)
        if legacy_key in profiles:
            return profiles[legacy_key]
    return None


def put_profile_entry(
    settings_store: dict[str, Any],
    site: str,
    strategy_name: str,
    currency: str,
    payload: dict[str, Any],
) -> None:
    """Simpan ke key site-prefixed (format baru)."""
    profiles = settings_store.setdefault("profiles", {})
    profiles[runtime_profile_key_for_site(site, strategy_name, currency)] = payload


def sanitize_session_profile(raw: dict[str, Any] | None) -> SessionProfile:
    min_bet = 1e-8
    profile = SessionProfile()
    if not isinstance(raw, dict):
        return profile
    try:
        profile.interval_ms = max(0, int(raw.get("interval_ms", profile.interval_ms)))
    except (TypeError, ValueError):
        pass
    try:
        profile.max_bets = max(0, int(raw.get("max_bets", profile.max_bets)))
    except (TypeError, ValueError):
        pass
    try:
        profile.log_every = max(1, int(raw.get("log_every", profile.log_every)))
    except (TypeError, ValueError):
        pass
    try:
        profile.take_profit_pct = max(0.0, float(raw.get("take_profit_pct", profile.take_profit_pct)))
    except (TypeError, ValueError):
        pass
    profile.pause_on_win = bool(raw.get("pause_on_win", profile.pause_on_win))
    try:
        profile.auto_switch_profit_pct = max(
            0.0,
            float(raw.get("auto_switch_profit_pct", profile.auto_switch_profit_pct)),
        )
    except (TypeError, ValueError):
        pass
    try:
        profile.run_break_seconds = max(
            0.0,
            float(raw.get("run_break_seconds", raw.get("run_break_minutes", 0.0))) *
            (60.0 if "run_break_seconds" not in raw and "run_break_minutes" in raw else 1.0),
        )
    except (TypeError, ValueError):
        pass
    try:
        profile.break_seconds = max(
            0.0,
            float(raw.get("break_seconds", raw.get("break_minutes", 0.0))) *
            (60.0 if "break_seconds" not in raw and "break_minutes" in raw else 1.0),
        )
    except (TypeError, ValueError):
        pass
    try:
        profile.flatbet_trigger_pct = max(
            0.0,
            float(raw.get("flatbet_trigger_pct", profile.flatbet_trigger_pct)),
        )
    except (TypeError, ValueError):
        pass
    try:
        profile.flatbet_minutes = max(
            0.0,
            float(raw.get("flatbet_minutes", profile.flatbet_minutes)),
        )
    except (TypeError, ValueError):
        pass
    try:
        profile.flatbet_amount = max(
            0.0,
            float(raw.get("flatbet_amount", profile.flatbet_amount)),
        )
    except (TypeError, ValueError):
        pass
    if 0 < profile.flatbet_amount < min_bet:
        profile.flatbet_amount = min_bet
    return profile


def profile_to_dict(profile: SessionProfile) -> dict[str, Any]:
    return {
        "interval_ms": int(profile.interval_ms),
        "max_bets": int(profile.max_bets),
        "log_every": int(profile.log_every),
        "take_profit_pct": float(profile.take_profit_pct),
        "pause_on_win": bool(profile.pause_on_win),
        "auto_switch_profit_pct": float(profile.auto_switch_profit_pct),
        "run_break_seconds": float(profile.run_break_seconds),
        "break_seconds": float(profile.break_seconds),
        "flatbet_trigger_pct": float(profile.flatbet_trigger_pct),
        "flatbet_minutes": float(profile.flatbet_minutes),
        "flatbet_amount": float(profile.flatbet_amount),
    }
