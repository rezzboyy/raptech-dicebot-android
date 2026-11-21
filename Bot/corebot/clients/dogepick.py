"""DogePick.io client implementation.

Site PHP-based dengan IconCaptcha di login dan Cloudflare di depan API.
Karena login programatis tidak realistis (captcha), client ini memakai
**cookie-based auth** — user paste cookie hasil login manual di browser.

Endpoint:
- `POST https://dogepick.io/process.php` untuk bet
- `GET  https://dogepick.io/dice.php` untuk render halaman (juga dipakai
  untuk health-check + scrape balance saat connect)

Format body bet: `application/x-www-form-urlencoded`
Auth: cookie session (`user_session`, `cf_clearance`, `remember_token`,
      `csrf_cookie_name`, `fp`).
CSRF: server set cookie `csrf_cookie_name` di tiap response. Request
      berikutnya kirim value cookie itu sebagai field body
      `csrf_test_name`. Token rotate per-request, jadi kita parse
      `Set-Cookie` dan update tracker.

Unit balance & amount di response adalah **satoshi-style integer**:
1 DOGE = 100_000_000 unit (sama dengan BTC).
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_DOWN
from urllib.parse import unquote

from ..http_client import build_http_session


BASE_URL = "https://dogepick.io"
PROCESS_PATH = "/process.php"
DICE_PATH = "/dice.php"
DICE_REFERER = "https://dogepick.io/dice.php"
DEFAULT_TIMEOUT = 30
# DogePick menyimpan saldo dalam satoshi-style integer:
# 1 DOGE = 100_000_000 unit (sama dengan BTC).
# Bukti dari sample response:
#   bet_amount: "0.00010000"  (string DOGE)
#   amount: -10000             (integer unit)
#   10000 / 0.0001 = 100_000_000
UNIT_DIVISOR = 100_000_000


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


def _to_amount(micro: int | float | str | None) -> float:
    """Convert micro-DOGE ke DOGE (float). None → 0."""
    if micro is None:
        return 0.0
    try:
        return float(micro) / UNIT_DIVISOR
    except (TypeError, ValueError):
        return 0.0


def _format_bet_amount(amount: float) -> str:
    """DogePick expect bet_amount dalam satuan DOGE dengan presisi 8 desimal,
    tapi minimum yang masuk akal 0.00000001 DOGE = 1 µDOGE.
    """
    dec = Decimal(str(amount)).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
    if dec < Decimal("0.00000001"):
        dec = Decimal("0.00000001")
    return f"{dec:.8f}"


class DogePickClient:
    """Cookie-based client untuk dogepick.io.

    Auth disuplai sebagai single 'cookie header' string (semua cookie yang
    user copy dari DevTools → Application → Cookies).
    """

    display_name: str = "DogePick"
    default_currencies: tuple[str, ...] = ("DOGE",)
    min_bet: float = 1e-8

    def __init__(self, cookie_header: str, proxy: dict[str, str] | None = None):
        """`cookie_header` adalah string mentah cookie hasil login manual.

        Contoh: "user_session=abc; cf_clearance=xyz; remember_token=...; ..."
        """
        self.cookie_header = (cookie_header or "").strip()
        # Shared HTTP factory — auto pilih backend sesuai env
        self.session, self._http_backend = build_http_session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/148.0.0.0 Safari/537.36"
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

        # Pasang cookie ke session jar
        cookies = _parse_cookie_header(self.cookie_header)
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain="dogepick.io")
        # Track CSRF token (initial value dari cookie). Akan di-update
        # via Set-Cookie response setelah tiap request ke /process.php.
        self._csrf_token: str = cookies.get("csrf_cookie_name", "")

        # Snapshot balance & user info
        self._last_balance_doge: float | None = None
        self._username: str | None = None

    # ---- HTTP layer ------------------------------------------------------

    @staticmethod
    def _is_rate_limit_message(message: str) -> bool:
        """Cek apakah pesan error dari server menandakan rate-limit / temporary block.

        Server dogepick ngebalikin pesan generic 'Connection timeout, please
        try again later!' saat user kirim request terlalu cepat. Kita treat
        ini sebagai rate-limit, bukan network error asli.
        """
        if not message:
            return False
        text = str(message).strip().lower()
        markers = (
            "try again later",
            "too many requests",
            "rate limit",
            "rate-limit",
            "slow down",
            "connection timeout",  # specific dogepick message
            "please wait",
        )
        return any(m in text for m in markers)

    def _post_form(self, payload: dict[str, str], _retry: int = 0) -> dict:
        """POST ke /process.php. Auto-retry sekali dengan backoff kalau
        kena rate-limit dari server."""
        url = f"{BASE_URL}{PROCESS_PATH}"
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

        # Update CSRF token dari Set-Cookie kalau ada
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
                # Backoff: tidur sebentar, lalu retry sekali.
                # Pilihan 2.5 detik cukup untuk hampir semua window rate-limit
                # PHP-based site tanpa bikin user frustrasi.
                import time as _time
                _time.sleep(2.5)
                return self._post_form(payload, _retry=_retry + 1)
            if msg:
                raise RuntimeError(str(msg))
            raise RuntimeError(f"Action failed: {data}")
        return data

    def _scrape_balance_from_dice_page(self) -> tuple[float | None, str | None]:
        """GET /dice.php, parse balance & username dari HTML.

        Mengembalikan (balance_doge, username) atau (None, None) bila gagal.
        Balance di halaman biasanya dalam satuan DOGE (sudah di-format,
        bukan micro-DOGE) — kita coba beberapa pattern umum site PHP.
        Kalau site redirect ke login, return None untuk balance.
        """
        try:
            resp = self.session.get(
                f"{BASE_URL}{DICE_PATH}", timeout=DEFAULT_TIMEOUT, allow_redirects=True
            )
        except Exception:
            return None, None
        # Update CSRF token kalau server kasih cookie baru di GET ini juga
        new_csrf = self.session.cookies.get("csrf_cookie_name")
        if new_csrf:
            self._csrf_token = new_csrf

        final_url = (resp.url or "").lower()
        if any(m in final_url for m in ("login.php", "/login", "/signin")):
            # Redirect ke login → cookie expired/invalid
            return None, None
        if resp.status_code >= 400:
            return None, None
        html = resp.text or ""

        balance: float | None = None
        # Pattern umum di site PHP-based untuk render balance:
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
        """Verifikasi cookie sah dengan GET halaman dice.

        Sekaligus seed `_last_balance_doge` & `_username` dari HTML kalau
        bisa, supaya engine punya data untuk ditampilkan tanpa nunggu
        bet pertama.
        """
        balance, username = self._scrape_balance_from_dice_page()
        if balance is not None:
            self._last_balance_doge = balance
        if username:
            self._username = username
        # Hitung sukses bila dapat salah satu (kalau dua-dua None,
        # kemungkinan cookie expired atau page redirect ke login)
        return balance is not None or bool(username)

    def balances(self) -> dict:
        """Return shape Wolfbet-compatible: {"balances": [{currency, amount}, ...]}.

        Kalau snapshot lokal kosong, scrape `/dice.php` sekali untuk dapet
        balance awal (sekaligus verifikasi cookie). Setelah itu balance
        di-update otomatis dari response tiap bet.
        """
        if self._last_balance_doge is None:
            self.health_check()
        if self._last_balance_doge is None:
            return {"balances": []}
        return {
            "balances": [
                {"currency": "DOGE", "amount": float(self._last_balance_doge)}
            ]
        }

    def stats(self) -> dict:
        """Tidak ada endpoint stats publik yang aku tahu untuk dogepick."""
        return {}

    def profile(self) -> dict:
        """Username didapat dari `/dice.php` HTML atau dari respons bet."""
        if not self._username:
            self.health_check()
        return {"user": {"username": self._username or ""}}

    def place_bet(self, currency: str, amount: float, chance: float, bethigh: bool) -> dict:
        """Place dice bet. DogePick hanya support DOGE.

        - `payout` = round(99 / chance, 2)
        - `bet_on` = "higher" (above) atau "lower" (below)
        """
        if (currency or "").upper() != "DOGE":
            raise RuntimeError(
                f"DogePick hanya support DOGE, currency={currency!r} tidak didukung."
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

        # Extract result
        try:
            roll = float(data.get("num") or 0.0)
        except (TypeError, ValueError):
            roll = 0.0
        # `amount` di response adalah delta saldo dalam micro-DOGE
        # (positif=win, negatif=lose). Kita hitung profit dari situ.
        try:
            profit_micro = float(data.get("amount") or 0.0)
        except (TypeError, ValueError):
            profit_micro = 0.0
        profit = profit_micro / UNIT_DIVISOR
        # Saldo baru juga dalam micro-DOGE
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
            # Bet amount yang ter-record di server (string desimal DOGE)
            try:
                placed_amount = float(bet_data.get("bet_amount") or amount)
            except (TypeError, ValueError):
                placed_amount = float(amount)
        else:
            placed_amount = float(amount)

        win_flag = profit_micro > 0
        # Cache balance untuk balances()
        self._last_balance_doge = new_balance

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
        """DogePick tidak ekspos endpoint reset seed publik.

        Kembalikan dict kosong agar engine fitur 'auto break + resetseed'
        tetap jalan tanpa error.
        """
        return {}
