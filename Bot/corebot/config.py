from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_URL = "https://wolf.bet"
WALLET_URL = "https://wolfbet.win"
DEFAULT_CURRENCIES = ["BTC", "ETH", "DOGE", "LTC", "TRX", "BCH", "XRP"]
TOKEN_FILENAME = "apitoken"
TOKENS_FILENAME = "apitokens.json"
RUNTIME_SETTINGS_FILENAME = "advancedset.json"
LEGACY_TOKEN_FILENAME = ".wolfbet_token"
LEGACY_RUNTIME_SETTINGS_FILENAME = ".wolfbet_runtime_settings.json"
DEFAULT_SITE = "wolfbet"
APPDATA_DIRNAME = "AutomationToolCrypto"
GAME_NAME = "dice"


def source_root() -> Path:
    return Path(__file__).resolve().parent.parent


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return source_root()


def appdata_root() -> Path:
    appdata = os.getenv("APPDATA") or os.path.expanduser("~")
    return Path(appdata) / APPDATA_DIRNAME


def token_paths() -> tuple[Path, ...]:
    """Semua kandidat path untuk membaca token, termasuk nama legacy."""
    return (
        runtime_root() / TOKEN_FILENAME,
        source_root() / TOKEN_FILENAME,
        appdata_root() / TOKEN_FILENAME,
        runtime_root() / LEGACY_TOKEN_FILENAME,
        source_root() / LEGACY_TOKEN_FILENAME,
        appdata_root() / LEGACY_TOKEN_FILENAME,
    )


def token_write_paths() -> tuple[Path, Path]:
    """Path untuk menulis token: utama runtime, fallback appdata. Selalu pakai nama baru."""
    return runtime_root() / TOKEN_FILENAME, appdata_root() / TOKEN_FILENAME


def settings_paths() -> tuple[Path, ...]:
    """Semua kandidat path untuk membaca settings, termasuk nama legacy."""
    return (
        runtime_root() / RUNTIME_SETTINGS_FILENAME,
        source_root() / RUNTIME_SETTINGS_FILENAME,
        appdata_root() / RUNTIME_SETTINGS_FILENAME,
        runtime_root() / LEGACY_RUNTIME_SETTINGS_FILENAME,
        source_root() / LEGACY_RUNTIME_SETTINGS_FILENAME,
        appdata_root() / LEGACY_RUNTIME_SETTINGS_FILENAME,
    )


def settings_write_paths() -> tuple[Path, Path]:
    """Path untuk menulis settings: utama runtime, fallback appdata. Selalu pakai nama baru."""
    return runtime_root() / RUNTIME_SETTINGS_FILENAME, appdata_root() / RUNTIME_SETTINGS_FILENAME


def tokens_paths() -> tuple[Path, ...]:
    """Kandidat path untuk membaca multi-site tokens (apitokens.json)."""
    return (
        runtime_root() / TOKENS_FILENAME,
        source_root() / TOKENS_FILENAME,
        appdata_root() / TOKENS_FILENAME,
    )


def tokens_write_paths() -> tuple[Path, Path]:
    """Path untuk menulis multi-site tokens. Utama runtime, fallback appdata."""
    return runtime_root() / TOKENS_FILENAME, appdata_root() / TOKENS_FILENAME


def lua_dir() -> Path:
    candidates = (
        runtime_root() / "strategies",
        source_root() / "strategies",
        runtime_root() / "script" / "lua",
        source_root() / "script" / "lua",
    )
    for path in candidates:
        if path.is_dir():
            return path
    return source_root() / "strategies"
