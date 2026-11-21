"""Helper koneksi akun untuk GUI.

Reuse core logic dari `corebot` (get_client_class + build_account_snapshot)
TANPA stdout/spinner/debug print yang ada di versi CLI (`cli/account.py`).
GUI butuh hasil bersih (client + AccountSnapshot), bukan output terminal.
"""
from __future__ import annotations

from corebot.clients import (
    BaseClient,
    available_sites,
    build_account_snapshot,
    get_client_class,
    site_metadata,
)
from corebot.models import AccountSnapshot
from corebot.storage import get_proxy_for


def list_sites() -> list[tuple[str, str]]:
    """Return [(slug, display_name), ...] untuk semua site tersedia."""
    out: list[tuple[str, str]] = []
    for slug in available_sites():
        try:
            name = site_metadata(slug).display_name
        except Exception:
            name = slug.title()
        out.append((slug, name))
    return out


def list_strategies() -> list[str]:
    """Return daftar nama file .lua di folder strategies/."""
    from corebot.config import lua_dir

    d = lua_dir()
    if not d.is_dir():
        return []
    return sorted((p.name for p in d.glob("*.lua")), key=str.lower)


def site_requires_token(site: str) -> bool:
    try:
        client_cls = get_client_class(site)
    except Exception:
        return True
    return bool(getattr(client_cls, "requires_token", True))


# Site dengan tipe kredensial khusus (sinkron dgn cli/prompts.py).
_COOKIE_SITES = {"dogepick", "tronpick"}
_JWT_SITES = {"nuts", "betfury", "pasino"}


def credential_info(site: str) -> dict:
    """Return metadata cara input kredensial untuk sebuah site.

    Return dict:
        kind   : 'none' | 'betfury' | 'cookie' | 'jwt' | 'webapi'
        label  : judul field
        hint   : petunjuk singkat (multi-baris pakai \\n)
    """
    s = (site or "").lower()
    if not site_requires_token(s):
        return {"kind": "none", "label": "Test Mode", "hint": "Simulator lokal — tidak butuh kredensial."}
    if s == "betfury":
        return {
            "kind": "betfury",
            "label": "Auth Token + UID",
            "hint": (
                "Login di browser -> DevTools -> Application -> Local Storage\n"
                "-> https://betfury.com\n"
                "Isi TOKEN (key 'token') dan UID (key 'uid') di dua kolom."
            ),
        }
    if s in _JWT_SITES:
        hints = {
            "nuts": "https://nuts.gg -> Local Storage -> key 'auth_token' (JWT 'eyJ...').",
            "pasino": "https://pasino.com -> Local Storage -> key 'token' (64-char hex). Auto-refresh.",
        }
        return {
            "kind": "jwt",
            "label": "Auth Token",
            "hint": "Login di browser -> DevTools -> Application -> Local Storage.\n"
                    + hints.get(s, f"{s}: copy auth token dari Local Storage."),
        }
    if s in _COOKIE_SITES:
        return {
            "kind": "cookie",
            "label": "Cookie Header",
            "hint": (
                "Login manual di browser -> DevTools -> Application -> Cookies\n"
                "(atau Network tab -> copy header 'cookie').\n"
                "Format: 'name=value; name=value; ...' (1 baris)."
            ),
        }
    return {
        "kind": "webapi",
        "label": "Web API",
        "hint": "Paste Web API / token dari akun kamu.",
    }


def build_betfury_token(token: str, uid: str) -> str:
    """Gabungkan token+uid Betfury jadi format tersimpan."""
    return f"{token.strip()};uid={uid.strip()}"


def parse_betfury_token(stored: str) -> tuple[str, str]:
    """Pecah token Betfury tersimpan (token;uid=xxx) → (token, uid)."""
    token, uid = "", ""
    if stored and ";" in stored:
        parts = stored.split(";", 1)
        token = parts[0].strip()
        rest = parts[1].strip()
        if rest.lower().startswith("uid="):
            uid = rest[4:].strip()
    else:
        token = (stored or "").strip()
    return token, uid


def connect(
    site: str,
    token: str,
    currency: str | None = None,
) -> tuple[BaseClient, AccountSnapshot]:
    """Connect ke situs. Return (client, account_snapshot).

    Raise Exception (dilempar apa adanya) kalau gagal — caller GUI yang
    tangani & tampilkan pesan error.
    """
    client_cls = get_client_class(site)
    proxy = get_proxy_for(site)
    client = client_cls(token, proxy=proxy) if proxy else client_cls(token)
    account = build_account_snapshot(client, currency, include_profile=True)
    return client, account


def refresh(
    client: BaseClient,
    account: AccountSnapshot | None,
    currency: str | None = None,
) -> AccountSnapshot:
    """Refresh balance tanpa reload profile."""
    refreshed = build_account_snapshot(client, currency, include_profile=False)
    if account:
        refreshed.username = account.username
        refreshed.email = account.email
    return refreshed
