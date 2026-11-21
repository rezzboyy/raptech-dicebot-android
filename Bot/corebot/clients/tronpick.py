"""TronPick.io client implementation.

TronPick satu keluarga platform dengan DogePick: login browser manual,
lalu bot memakai cookie hasil sesi yang sudah aktif.

Endpoint:
- `POST https://tronpick.io/api.php` untuk bet
- `GET  https://tronpick.io/dice.php` untuk health-check + scrape akun

Format body bet: `application/x-www-form-urlencoded`
Auth: cookie session (`user_session`, `remember_token`, `fp`,
      `csrf_cookie_name`, dst).
CSRF: request kirim `csrf_test_name`, lalu server bisa rotate cookie
`csrf_cookie_name` lewat `Set-Cookie` setelah request sukses.

Unit balance & amount di response adalah micro-TRX:
1 TRX = 1_000_000 unit.
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_DOWN
from urllib.parse import unquote

from ..http_client import build_http_session


BASE_URL = "https://tronpick.io"
API_PATH = "/api.php"
DICE_PATH = "/dice.php"
DICE_REFERER = "https://tronpick.io/dice.php"
DEFAULT_TIMEOUT = 30
UNIT_DIVISOR = 1_000_000


def _parse_cookie_header(cookie_header: str) -> dict[str, str]:
    """Pecah string cookie 'a=1; b=2; c=3' jadi dict."""
    out: dict[str, str] = {}
    if not cookie_header:
        return out
    for part in cookie_header.split(";"):
        chunk = part.strip()
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name:
            out[name] = unquote(value) if "%" in value else value
    return out


def _format_bet_amount(amount: float) -> str:
    """TronPick menerima jumlah bet TRX dengan 6 desimal."""
    dec = Decimal(str(amount)).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    if dec < Decimal("0.000001"):
        dec = Decimal("0.000001")
    return f"{dec:.6f}"


def _strip_html_number(value: object) -> float:
    """Ambil angka float dari string yang mungkin dibungkus span HTML."""
    if value is None:
        return 0.0
    text = str(value)
    plain = re.sub(r"<[^>]+>", "", text).strip().replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", plain)
    if not match:
        return 0.0
    try:
        return float(match.group(0))
    except ValueError:
        return 0.0


class TronPickClient:
    """Cookie-based client untuk tronpick.io."""

    display_name: str = "TronPick"
    default_currencies: tuple[str, ...] = ("TRX",)
    min_bet: float = 1e-8

    def __init__(self, cookie_header: str, proxy: dict[str, str] | None = None):
        self.cookie_header = (cookie_header or "").strip()
        # Shared HTTP factory — auto pilih backend sesuai env
        self.session, self._http_backend = build_http_session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/149.0.0.0 Safari/537.36"
                ),
                "Accept": "*/*",
                "Accept-Language": "id;q=0.6",
                "Origin": BASE_URL,
                "Referer": DICE_REFERER,
                "X-Requested-With": "XMLHttpRequest",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
        )
        if proxy:
            self.session.proxies.update(proxy)

        cookies = _parse_cookie_header(self.cookie_header)
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain="tronpick.io")
        self._csrf_token: str = cookies.get("csrf_cookie_name", "")
        self._last_balance_trx: float | None = None
        self._username: str | None = None

    @staticmethod
    def _is_rate_limit_message(message: str) -> bool:
        if not message:
            return False
        text = str(message).strip().lower()
        markers = (
            "try again later",
            "too many requests",
            "rate limit",
            "rate-limit",
            "slow down",
            "connection timeout",
            "please wait",
        )
        return any(marker in text for marker in markers)

    def _post_form(self, payload: dict[str, str], _retry: int = 0) -> dict:
        url = f"{BASE_URL}{API_PATH}"
        body = dict(payload)
        if self._csrf_token and "csrf_test_name" not in body:
            body["csrf_test_name"] = self._csrf_token
        try:
            resp = self.session.post(
                url,
                data=body,
                timeout=DEFAULT_TIMEOUT,
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            )
        except Exception as exc:
            raise RuntimeError(f"Network error: {exc}") from exc

        new_csrf = self.session.cookies.get("csrf_cookie_name")
        if new_csrf:
            self._csrf_token = new_csrf

        if resp.status_code >= 400:
            snippet = (resp.text or "")[:240].replace("\n", " ").strip()
            raise RuntimeError(f"HTTP {resp.status_code}: {snippet}")

        # fast_json_loads pakai orjson kalau tersedia (5x lebih cepat).
        try:
            from ..lua_support import fast_json_loads
            data = fast_json_loads(resp.content)
        except (ValueError, Exception):
            snippet = (resp.text or "")[:240].replace("\n", " ").strip()
            raise RuntimeError(f"Non-JSON response: {snippet}")

        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected response: {data!r}")

        ret_value = data.get("ret")
        if ret_value not in (1, "1", True):
            msg = data.get("mes") or data.get("message") or data.get("error") or ""
            if self._is_rate_limit_message(msg) and _retry < 1:
                import time as _time

                _time.sleep(2.5)
                return self._post_form(payload, _retry=_retry + 1)
            if msg:
                raise RuntimeError(str(msg))
            raise RuntimeError(f"Action failed: {data}")
        return data

    def _scrape_balance_from_dice_page(self) -> tuple[float | None, str | None]:
        try:
            resp = self.session.get(
                f"{BASE_URL}{DICE_PATH}", timeout=DEFAULT_TIMEOUT, allow_redirects=True
            )
        except Exception:
            return None, None

        new_csrf = self.session.cookies.get("csrf_cookie_name")
        if new_csrf:
            self._csrf_token = new_csrf

        final_url = (resp.url or "").lower()
        if any(marker in final_url for marker in ("login.php", "/login", "/signin")):
            return None, None
        if resp.status_code >= 400:
            return None, None
        html = resp.text or ""

        balance: float | None = None
        balance_patterns = [
            r'data-user-balance=["\']([0-9][0-9.,]*)["\']',
            r'class=["\'][^"\']*user_balance[^"\']*["\'][^>]*>\s*([0-9][0-9.,]*)',
            r'class=["\'][^"\']*top_balance[^"\']*["\'][^>]*>\s*([0-9][0-9.,]*)',
            r'id=["\'][^"\']*balance[^"\']*["\'][^>]*>\s*([0-9][0-9.,]*)',
            r'"balance"\s*:\s*"?(?:\+|-)?([0-9][0-9.,]*)"?',
        ]
        for pattern in balance_patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if not match:
                continue
            try:
                balance = float(match.group(1).replace(",", ""))
                break
            except (TypeError, ValueError):
                continue

        username: str | None = None
        username_patterns = [
            r'data-user-name=["\']([^"\']+)["\']',
            r'class=["\'][^"\']*username[^"\']*["\'][^>]*>\s*([^<\s][^<]*?)\s*<',
            r'"user_name"\s*:\s*"([^"]+)"',
            r'"username"\s*:\s*"([^"]+)"',
        ]
        for pattern in username_patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                username = match.group(1).strip()
                if username:
                    break

        return balance, username

    def health_check(self) -> bool:
        balance, username = self._scrape_balance_from_dice_page()
        if balance is not None:
            self._last_balance_trx = balance
        if username:
            self._username = username
        return balance is not None or bool(username)

    def balances(self) -> dict:
        if self._last_balance_trx is None:
            self.health_check()
        if self._last_balance_trx is None:
            return {"balances": []}
        return {"balances": [{"currency": "TRX", "amount": float(self._last_balance_trx)}]}

    def stats(self) -> dict:
        return {}

    def profile(self) -> dict:
        if not self._username:
            self.health_check()
        return {"user": {"username": self._username or ""}}

    def place_bet(self, currency: str, amount: float, chance: float, bethigh: bool) -> dict:
        if (currency or "").upper() != "TRX":
            raise RuntimeError(
                f"TronPick hanya support TRX, currency={currency!r} tidak didukung."
            )
        if chance <= 0 or chance >= 100:
            raise RuntimeError("Chance harus 0 < chance < 100.")
        if amount <= 0:
            raise RuntimeError("Bet amount harus > 0.")

        payout = max(1.01, round(99.0 / chance, 2))
        body = {
            "action": "bet_game_dice",
            "bet_amount": _format_bet_amount(amount),
            "payout": f"{payout:g}",
            "bet_on": "higher" if bethigh else "lower",
        }
        data = self._post_form(body)

        try:
            roll = float(data.get("num") or 0.0)
        except (TypeError, ValueError):
            roll = 0.0

        try:
            profit_micro = float(data.get("amount") or 0.0)
        except (TypeError, ValueError):
            profit_micro = 0.0
        profit = profit_micro / UNIT_DIVISOR

        try:
            balance_micro = float(data.get("balance") or 0.0)
        except (TypeError, ValueError):
            balance_micro = 0.0
        new_balance = balance_micro / UNIT_DIVISOR

        bet_data = data.get("bet_data") or {}
        if isinstance(bet_data, dict):
            user_name = bet_data.get("user_name")
            if isinstance(user_name, str) and user_name:
                self._username = user_name
            try:
                placed_amount = float(bet_data.get("bet_amount") or amount)
            except (TypeError, ValueError):
                placed_amount = float(amount)
            profit_from_html = _strip_html_number(bet_data.get("profit"))
            if not profit and profit_from_html:
                profit = profit_from_html
        else:
            placed_amount = float(amount)

        win_flag = profit_micro > 0
        self._last_balance_trx = new_balance

        return {
            "bet": {
                "amount": placed_amount,
                "state": "win" if win_flag else "lose",
                "result_value": roll,
                "profit": profit,
            },
            "userBalance": {"amount": new_balance},
        }

    def reset_seed(self) -> dict:
        return {}
