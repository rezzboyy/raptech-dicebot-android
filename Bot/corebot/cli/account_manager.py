"""Multi-account manager (site-agnostic).

Fitur:
- Add/select/remove akun untuk site apa pun (Wolf.bet, Pasino, Nuts, Betfury, dll)
- Background auto-refresh khusus Pasino (satu-satunya site dengan endpoint
  refresh-token). Site lain tetap bisa switch akun manual.

Format storage di apitokens.json (generic untuk semua site):
  {
    "pasino": {
      "accounts": [
        {"label": "Akun 1", "token": "6c21...f7ec"},
        {"label": "Akun 2", "token": "ab12...cd34"}
      ],
      "active": 0
    },
    "wolfbet": {
      "accounts": [
        {"label": "Main", "token": "wolfbet-token-1"},
        {"label": "Backup", "token": "wolfbet-token-2"}
      ],
      "active": 0
    },
    ...
  }

Backward-compat: kalau value site berupa string (format lama), auto-migrate
ke format multi-account dengan 1 akun "Default" saat first read.
"""
from __future__ import annotations

import json
import threading
from typing import Any

try:
    from colorama import Fore  # type: ignore
except Exception:
    class Fore:  # type: ignore[no-redef]
        CYAN = "\x1b[36m"

from ..clients import site_metadata
from ..storage import load_tokens, save_tokens
from ..ui.theme import visible_len
from ._console import clear_screen, pause, section
from ._state import get_theme
from .layout import responsive_width
from .prompts import prompt_select


# Site yang punya endpoint auto-refresh token (background heartbeat).
# Saat ini hanya Pasino yang punya /account/refresh-token endpoint.
# Site lain tidak boleh masuk sini karena refresh-token nya tidak ada,
# hantaman ke endpoint yang tidak tepat akan bikin token invalid.
SITES_WITH_AUTO_REFRESH: frozenset[str] = frozenset({"pasino"})


# ---- Storage helpers (generic) -------------------------------------------

def _load_accounts_for(site: str) -> dict:
    """Load multi-account data untuk site tertentu.

    Return: {"accounts": [...], "active": int}
    Auto-migrate dari format lama (string) ke format baru.
    """
    key = (site or "").lower()
    tokens = load_tokens()
    raw = tokens.get(key)

    if raw is None:
        return {"accounts": [], "active": 0}

    # Format lama: string token tunggal → migrate ke format baru dengan 1 akun
    if isinstance(raw, str):
        return {
            "accounts": [{"label": "Default", "token": raw}],
            "active": 0,
        }

    # Format Betfury-legacy: `token;uid=...` juga masih string, sudah ter-handle
    # di atas. Kalau dict, cek shape.
    if isinstance(raw, dict):
        # Format baru: {"accounts": [...], "active": N}
        accounts = raw.get("accounts")
        if isinstance(accounts, list):
            active = int(raw.get("active", 0))
            clean = [
                {"label": str(a.get("label", f"Akun {i+1}")), "token": str(a.get("token", ""))}
                for i, a in enumerate(accounts)
                if a.get("token")
            ]
            if active >= len(clean):
                active = 0
            return {"accounts": clean, "active": active}

        # Dict lain (dual-credential lama) — treat as single legacy account
        # by JSON-stringifying it (client akan parse balik).
        return {
            "accounts": [{"label": "Default", "token": json.dumps(raw)}],
            "active": 0,
        }

    return {"accounts": [], "active": 0}


def _save_accounts_for(site: str, data: dict) -> None:
    """Simpan multi-account data ke apitokens.json untuk site tertentu."""
    key = (site or "").lower()
    tokens = load_tokens()
    tokens[key] = data
    save_tokens(tokens)


def get_active_token(site: str = "pasino") -> str | None:
    """Ambil token akun aktif untuk site tertentu."""
    data = _load_accounts_for(site)
    accounts = data.get("accounts", [])
    active = data.get("active", 0)
    if not accounts:
        return None
    if active >= len(accounts):
        active = 0
    return accounts[active].get("token")


def get_active_label(site: str = "pasino") -> str:
    """Ambil label akun aktif untuk site tertentu."""
    data = _load_accounts_for(site)
    accounts = data.get("accounts", [])
    active = data.get("active", 0)
    if not accounts:
        return "-"
    if active >= len(accounts):
        active = 0
    return accounts[active].get("label", "Unknown")


def get_all_tokens_for(site: str) -> list[str]:
    """Ambil semua token dari semua akun (untuk background refresh)."""
    data = _load_accounts_for(site)
    return [a["token"] for a in data.get("accounts", []) if a.get("token")]


def update_token_in_storage(site: str, old_token: str, new_token: str) -> None:
    """Update token di storage setelah refresh berhasil (untuk background heartbeat)."""
    data = _load_accounts_for(site)
    for account in data.get("accounts", []):
        if account.get("token") == old_token:
            account["token"] = new_token
            break
    _save_accounts_for(site, data)


# ---- Background refresh (Pasino-only) -----------------------------------

_bg_refresh_threads: dict[str, threading.Thread] = {}
_bg_refresh_stop_events: dict[str, threading.Event] = {}


def start_background_refresh_all(site: str = "pasino", interval_seconds: int = 240) -> None:
    """Start background thread yang refresh SEMUA token akun untuk site.

    Saat ini hanya support Pasino. Site lain tidak punya endpoint
    refresh-token, jadi call ini no-op untuk site selain Pasino.
    """
    key = (site or "").lower()
    if key not in SITES_WITH_AUTO_REFRESH:
        return  # No-op untuk site yang tidak punya refresh endpoint

    existing = _bg_refresh_threads.get(key)
    if existing is not None and existing.is_alive():
        return  # Sudah jalan

    stop_ev = threading.Event()
    _bg_refresh_stop_events[key] = stop_ev
    thread = threading.Thread(
        target=_refresh_all_loop,
        args=(key, interval_seconds, stop_ev),
        name=f"{key}-refresh-all-accounts",
        daemon=True,
    )
    thread.start()
    _bg_refresh_threads[key] = thread


def stop_background_refresh_all(site: str = "pasino") -> None:
    """Stop background refresh thread untuk site tertentu."""
    key = (site or "").lower()
    stop_ev = _bg_refresh_stop_events.get(key)
    if stop_ev is not None:
        stop_ev.set()
    thread = _bg_refresh_threads.get(key)
    if thread is not None and thread.is_alive():
        thread.join(timeout=3.0)
    _bg_refresh_threads.pop(key, None)
    _bg_refresh_stop_events.pop(key, None)


def _refresh_all_loop(site: str, interval: int, stop_ev: threading.Event) -> None:
    """Loop: refresh semua token tiap N detik. Khusus Pasino."""
    while not stop_ev.wait(interval):
        try:
            _refresh_all_tokens_once(site)
        except Exception:
            pass


def _refresh_all_tokens_once(site: str) -> None:
    """Refresh semua token akun tersimpan (khusus Pasino)."""
    if site.lower() != "pasino":
        return

    data = _load_accounts_for(site)
    accounts = data.get("accounts", [])
    if not accounts:
        return

    changed = False
    for account in accounts:
        token = account.get("token", "")
        if not token or len(token) < 16:
            continue
        try:
            new_token = _refresh_single_pasino_token(token)
            if new_token and new_token != token:
                account["token"] = new_token
                changed = True
        except Exception:
            pass

    if changed:
        _save_accounts_for(site, data)


def _refresh_single_pasino_token(token: str) -> str | None:
    """Refresh satu token via /account/refresh-token Pasino. Return new token atau None."""
    try:
        from curl_cffi import requests as _curl_requests
        sess = _curl_requests.Session(impersonate="chrome120")
    except ImportError:
        import requests as _req  # type: ignore
        sess = _req.Session()

    sess.headers.update({
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://pasino.com",
        "Referer": "https://pasino.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
    })

    payload = json.dumps({"token": token, "language": "en"})
    try:
        resp = sess.post("https://api.pasino.com/account/refresh-token", data=payload, timeout=15.0)
        result = resp.json()
    except Exception:
        return None

    if not isinstance(result, dict) or not result.get("success"):
        return None

    new_token = str(result.get("new_token") or "").strip()
    if new_token and len(new_token) >= 16:
        return new_token
    return None


# ---- CLI Menu (site-agnostic) --------------------------------------------

def show_account_manager(site: str, current_client=None) -> dict | None:
    """Menu utama account manager untuk site tertentu.

    Return:
      {"action": "switched", "token": "...", "label": "..."} kalau user switch akun
      {"action": "added", "token": "...", "label": "..."} kalau user tambah akun baru
      None kalau user kembali tanpa perubahan
    """
    theme = get_theme()
    g = theme.glyphs
    site_display = site_metadata(site).display_name

    while True:
        clear_screen()
        data = _load_accounts_for(site)
        accounts = data.get("accounts", [])
        active_idx = data.get("active", 0)

        section(f"ACCOUNT MANAGER — {site_display.upper()}", Fore.CYAN, False)
        print(theme.c(f"  Total akun tersimpan: {len(accounts)}", "dim"))
        if accounts:
            active_label = accounts[active_idx]["label"] if active_idx < len(accounts) else "-"
            print(theme.c(f"  Akun aktif: {active_label}", "accent"))
        if site.lower() in SITES_WITH_AUTO_REFRESH:
            print(theme.c(f"  Auto-refresh: ON (semua token di-refresh tiap 4 menit)", "success"))
        else:
            print(theme.c(f"  Auto-refresh: OFF ({site_display} tidak support refresh endpoint)", "dim"))
        print()

        # Tampilkan list akun
        if accounts:
            for i, acc in enumerate(accounts):
                is_active = i == active_idx
                dot = theme.c("●", "success", bold=True) if is_active else theme.c("○", "dim")
                lbl = theme.c(acc["label"], "accent" if is_active else "muted", bold=is_active)
                token_val = acc["token"]
                tok_preview = token_val[:6] + "..." + token_val[-4:] if len(token_val) > 10 else "***"
                tok_styled = theme.c(tok_preview, "dim")
                tag = theme.c(" (active)", "success") if is_active else ""
                print(f"  {dot} [{i+1}] {lbl}  {tok_styled}{tag}")
            print()

        options = []
        if len(accounts) > 1:
            options.append("Select Account")
        options.append("Add Account")
        if accounts:
            options.append("Remove Account")
        options.append("Back to Menu")

        picked = prompt_select(
            options,
            "Pilih aksi:",
            options[-1],
            show_list=True,
            no_color=False,
        )

        if picked == "Back to Menu":
            return None

        if picked == "Add Account":
            result = _add_account(site, site_display, theme, g)
            if result:
                return result

        elif picked == "Select Account":
            result = _select_account(site, accounts, active_idx, theme, g)
            if result:
                return result

        elif picked == "Remove Account":
            _remove_account(site, accounts, active_idx, theme, g)


def _add_account(site: str, site_display: str, theme, g) -> dict | None:
    """Prompt user untuk paste token + label baru."""
    clear_screen()
    section(f"ADD ACCOUNT — {site_display.upper()}", Fore.CYAN, False)

    site_lower = site.lower()
    if site_lower == "pasino":
        print(theme.c("  Paste token dari browser (LocalStorage > 'token').", "dim"))
    elif site_lower == "betfury":
        print(theme.c("  Format: <token>;uid=<uid>", "dim"))
        print(theme.c("  Ambil token & uid dari LocalStorage betfury.com.", "dim"))
    elif site_lower == "nuts":
        print(theme.c("  Paste 'auth_token' dari LocalStorage nuts.gg.", "dim"))
    elif site_lower in ("dogepick", "tronpick"):
        print(theme.c("  Paste cookie header dari browser (name=value; ...).", "dim"))
    else:
        print(theme.c(f"  Paste Web API/token untuk {site_display}.", "dim"))
    print(theme.c("  Ketik '/cancel' untuk batal.", "dim"))
    print()

    # Input token
    prompt_token = f"  {theme.c(g.prompt, 'accent', bold=True)} Token/Web API: "
    while True:
        try:
            raw_token = input(prompt_token).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if raw_token.lower() == "/cancel":
            return None
        if not raw_token or len(raw_token) < 10:
            print(theme.c("  Token terlalu pendek. Minimal 10 karakter.", "warning"))
            continue
        break

    # Input label
    print()
    prompt_label = f"  {theme.c(g.prompt, 'accent', bold=True)} Label (nama akun): "
    try:
        raw_label = input(prompt_label).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not raw_label:
        raw_label = f"Akun {len(_load_accounts_for(site).get('accounts', [])) + 1}"

    # Simpan
    data = _load_accounts_for(site)
    accounts = data.get("accounts", [])
    accounts.append({"label": raw_label, "token": raw_token})
    # Set akun baru sebagai aktif
    data["accounts"] = accounts
    data["active"] = len(accounts) - 1
    _save_accounts_for(site, data)

    print()
    print(theme.c(f"  ✓ Akun '{raw_label}' ditambahkan dan dijadikan aktif.", "success"))
    pause()
    return {"action": "added", "token": raw_token, "label": raw_label}


def _select_account(site: str, accounts: list, active_idx: int, theme, g) -> dict | None:
    """Pilih akun aktif dari list."""
    clear_screen()
    site_display = site_metadata(site).display_name
    section(f"SELECT ACCOUNT — {site_display.upper()}", Fore.CYAN, False)

    labels = [
        f"{acc['label']}  ({acc['token'][:6]}...{acc['token'][-4:]})"
        + (" ← active" if i == active_idx else "")
        for i, acc in enumerate(accounts)
    ]

    picked = prompt_select(
        labels,
        "Pilih akun:",
        labels[active_idx] if active_idx < len(labels) else labels[0],
        show_list=True,
        no_color=False,
    )

    picked_idx = labels.index(picked) if picked in labels else 0

    if picked_idx == active_idx:
        print(theme.c("  Akun ini sudah aktif.", "dim"))
        pause()
        return None

    # Switch
    data = _load_accounts_for(site)
    data["active"] = picked_idx
    _save_accounts_for(site, data)

    new_acc = data["accounts"][picked_idx]
    print(theme.c(f"  ✓ Switched ke '{new_acc['label']}'.", "success"))
    pause()
    return {"action": "switched", "token": new_acc["token"], "label": new_acc["label"]}


def _remove_account(site: str, accounts: list, active_idx: int, theme, g) -> None:
    """Hapus akun dari list."""
    clear_screen()
    site_display = site_metadata(site).display_name
    section(f"REMOVE ACCOUNT — {site_display.upper()}", Fore.CYAN, False)

    if len(accounts) <= 1:
        print(theme.c("  Tidak bisa hapus — minimal 1 akun harus ada.", "warning"))
        pause()
        return

    labels = [f"{acc['label']}  ({acc['token'][:6]}...)" for acc in accounts]
    picked = prompt_select(
        labels,
        "Pilih akun yang mau dihapus:",
        labels[-1],
        show_list=True,
        no_color=False,
    )

    picked_idx = labels.index(picked) if picked in labels else -1
    if picked_idx < 0:
        return

    # Konfirmasi
    confirm = input(
        f"  {theme.c(g.prompt, 'accent', bold=True)} "
        f"Hapus '{accounts[picked_idx]['label']}'? (y/n): "
    ).strip().lower()
    if confirm not in ("y", "yes", "ya"):
        print(theme.c("  Batal.", "dim"))
        pause()
        return

    # Hapus
    data = _load_accounts_for(site)
    data["accounts"].pop(picked_idx)
    # Adjust active index
    if data["active"] >= len(data["accounts"]):
        data["active"] = max(0, len(data["accounts"]) - 1)
    elif picked_idx < data["active"]:
        data["active"] -= 1
    _save_accounts_for(site, data)

    print(theme.c(f"  ✓ Akun dihapus. Sisa: {len(data['accounts'])} akun.", "success"))
    pause()


# ---- Backward-compat aliases (Pasino-only functions) ---------------------

def _load_pasino_accounts() -> dict:
    """Alias untuk backward-compat dengan kode lama yang panggil ini
    langsung. Baru kode hendaknya pakai `_load_accounts_for("pasino")`.
    """
    return _load_accounts_for("pasino")


def _save_pasino_accounts(data: dict) -> None:
    """Alias untuk backward-compat."""
    _save_accounts_for("pasino", data)


def get_all_tokens() -> list[str]:
    """Alias untuk backward-compat: return semua token Pasino."""
    return get_all_tokens_for("pasino")


def update_token_for_account(old_token: str, new_token: str) -> None:
    """Alias untuk backward-compat."""
    update_token_in_storage("pasino", old_token, new_token)
