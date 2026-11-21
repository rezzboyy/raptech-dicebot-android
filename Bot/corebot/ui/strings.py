"""Central registry untuk string user-facing.

Saat ini default ID (Indonesia) untuk pesan ke customer dan EN untuk
diagnostik teknis. Belum i18n full — registry ini sengaja sederhana
supaya di kemudian hari tinggal dipetakan ke loader berbasis lokal.

Cara pakai:
    from corebot.ui.strings import S
    print(S.MENU_TITLE)
    print(S.confirm_quit_hint(2))

Panduan: hindari mencampur string user-facing langsung di logic.
Tambah field baru di sini, baru rujuk dari call site.
"""
from __future__ import annotations


class _Strings:
    # Branding
    APP_NAME: str = "RAPTECH ENGINE"
    APP_TAGLINE: str = "TERMINAL CORE · LICENSE GATEWAY"

    # Console
    PAUSE_RETURN: str = "Press Enter to return to menu..."

    # Menu sections
    MENU_SECTION_CONNECTION: str = "Connection"
    MENU_SECTION_ENGINE: str = "Engine"
    MENU_SECTION_EXIT: str = "Exit"

    # Menu prompt
    MENU_PROMPT: str = "Choose an option"
    MENU_INVALID: str = "Please enter a number."

    # Connection
    SITE_LABEL: str = "Site   "
    ACCOUNT_LABEL: str = "Account"
    ACTIVE_LABEL: str = "Active "

    # Engine session
    SESSION_ARMED: str = "Session armed. Ctrl+C to stop."
    SESSION_STOPPED: str = "Session stopped."
    SESSION_RESTARTED: str = "Session restarted."
    STOP_REQUESTED: str = "Stop requested by operator."

    # Hotkey help
    HOTKEY_HELP_TITLE: str = "RUNTIME KEYS"
    HOTKEY_HELP_LINES: tuple[str, ...] = (
        "C  Pause          R  Resume          S  Restart",
        "A  Toggle Stop-On-Win                Q  Quit",
        "L  Cycle log_every (1·5·10·25·100)",
        "+  interval +50ms        -  interval -50ms",
        "?  Toggle this help",
    )

    # Quit confirm
    @staticmethod
    def confirm_quit_hint(seconds: int = 2) -> str:
        return f"Press Q again within {seconds}s to quit."

    @staticmethod
    def confirm_restart_hint(seconds: int = 2) -> str:
        return f"Press S again within {seconds}s to restart."

    # Toast titles (dipakai engine/cli)
    TOAST_STRATEGY_SWITCH: str = "STRATEGY SWITCH"
    TOAST_FLATBET_ON: str = "FLAT ALLOCATION ON"
    TOAST_FLATBET_OFF: str = "FLAT ALLOCATION OFF"
    TOAST_TAKE_PROFIT: str = "TAKE PROFIT REACHED"
    TOAST_LICENSE_WARN: str = "LICENSE EXPIRING"

    # Account
    ACCOUNT_NO_WALLET: str = "Wallet belum tersedia dari API."
    ACCOUNT_SECTION_WALLETS: str = "Wallets"
    ACCOUNT_SECTION_LIFETIME: str = "Lifetime"

    # Strategy
    STRATEGY_NO_META: str = "(no metadata)"

    # Errors / states
    ERR_INVALID_NUMBER: str = "Please enter a valid number."
    ERR_NOT_FOUND: str = "Not found."

    # Dry run
    DRY_RUN_TITLE: str = "READY TO ENGAGE"
    DRY_RUN_HINT: str = "ENTER = launch · E = edit · ESC = cancel"

    # Additional menu / layout strings
    MENU_SECTION_QUICK_LAUNCH: str = "Quick Launch"
    MENU_QUICK_START: str = "Quick Start (wizard)"
    MENU_SELECT_SITE: str = "Select Site"
    MENU_SET_BALANCE: str = "Set Test Balance"
    MENU_PASTE_API: str = "Paste Web API"
    MENU_REFRESH_BALANCE: str = "Refresh Balance"
    MENU_START_ENGINE: str = "Start Engine"
    MENU_ACCOUNT_OVERVIEW: str = "Account Overview"
    MENU_CHECK_SCRIPT: str = "Check Script"
    MENU_DEPOSIT: str = "Deposit (Pasino)"
    MENU_WITHDRAW: str = "Withdraw (Pasino)"
    MENU_TOKEN_STATUS: str = "Token Status"
    MENU_REFRESH_TOKEN: str = "Refresh Token"
    MENU_ACCOUNT_MANAGER: str = "Manage Accounts"
    MENU_SET_PROXY: str = "Set Proxy"
    MENU_CHANGE_EMAIL: str = "Change Email"

    # Runtime keys
    KEYS_LABEL: str = "KEYS"
    KEY_PAUSE: str = "Pause"
    KEY_RESUME: str = "Resume"
    KEY_RESTART: str = "Restart"
    KEY_STOP_ON_WIN: str = "StopOnWin"
    KEY_HELP: str = "Help"
    KEY_QUIT: str = "Quit"

    # Engine log strings
    LOG_RESTART_REQUESTED: str = "Restart requested. Stopping current session..."
    LOG_HELP_DISMISSED: str = "Help dismissed."
    LOG_STOPPED_UNEXPECTEDLY: str = "Engine stopped unexpectedly."
    LOG_ENGINE_CRASH: str = "Session terhenti karena error. Bot tetap berjalan — cek error di atas dan coba lagi."


S = _Strings()
