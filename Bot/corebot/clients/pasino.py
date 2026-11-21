"""Pasino hash-dice client - REST API.

Site: https://pasino.com/hash-dice
Backend: https://api.pasino.com (REST POST)

Anti-bot bypass:
  1. Cloudflare TLS fingerprint check (JA3) -> curl_cffi impersonate
     Chrome120 supaya request tidak di-block 403 oleh Cloudflare WAF.
  2. ISP DNS block (mis. Biznet "Safesurf") -> resolve api.pasino.com
     via Cloudflare DoH (https://cloudflare-dns.com/dns-query) lalu
     inject ke curl via CurlOpt.RESOLVE supaya bypass system DNS.

Auth method:
  Token dari localStorage > pasino.com > key 'token'.
  Token disertakan di body tiap request.

Token auto-refresh (Path B):
  Pasino punya endpoint POST /account/refresh-token yang accept token
  current dan return token baru tanpa perlu login ulang & tanpa CAPTCHA.
  Client ini menjalankan background heartbeat thread yang call endpoint
  itu setiap PASINO_REFRESH_INTERVAL detik (default 240s = 4 menit) dan
  meng-update token in-memory + persist ke `apitokens.json` supaya bot
  tidak pernah ter-disconnect karena token expired.

  Tambahan: kalau request tetap ditolak dengan auth error (mis. token
  sudah keburu expire diantara heartbeat), `_post()` otomatis refresh +
  retry sekali sebelum raise.

Endpoints:
  POST /coin/get-balances     -> {data: [{coin, balance}, ...]}
  POST /dice/play             -> {bet_id, result, profit, ...}
  POST /dice/rotate-seed      -> success/error
  POST /account/refresh-token -> {success, new_token, message}

Bet payload (dari capture browser real):
  {
    token: <jwt>,
    language: "id" | "en",
    bet_amt: "0.10000000",     # string fixed 8 decimal
    coin: "GEM",                # uppercase
    type: "1" (under) | "2" (over),  # string!
    payout: "1.21794",          # 5 decimal multiplier
    client_seed: <64 char alnum>
  }
"""

from __future__ import annotations

import json
import os
import random
import string
import threading
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable

try:
    from curl_cffi import requests as _curl_requests
    from curl_cffi.curl import CurlOpt as _CurlOpt
    _HAS_CURL_CFFI = True
except ImportError:
    import requests as _curl_requests  # type: ignore[no-redef]
    _CurlOpt = None  # type: ignore[assignment]
    _HAS_CURL_CFFI = False


PASINO_API = "https://api.pasino.com"
PASINO_HOST = "api.pasino.com"
DEFAULT_CURRENCIES = (
    "GEM", "BTC", "ETH", "USDT", "TRX", "DOGE", "LTC", "BCH",
    "POL", "BNB", "SOL", "XRP", "ADA", "AVAX",
    "DAI", "USDC", "TON", "SUI", "APT", "ARB", "OP",
)

# Fallback network list per coin. Dipakai kalau endpoint
# /coin/get-deposit-networks tidak tersedia atau error. Data dari
# observasi halaman deposit Pasino (coin umum -> network yang didukung).
# Update manual kalau Pasino tambah/hapus network.
DEPOSIT_NETWORKS_FALLBACK: dict[str, list[dict]] = {
    "BTC": [{"network": "BTC", "name": "Bitcoin", "min_deposit": "0.0001"}],
    "ETH": [
        {"network": "ERC20", "name": "Ethereum (ERC20)", "min_deposit": "0.001"},
    ],
    "USDT": [
        {"network": "TRC20", "name": "Tron (TRC20)", "min_deposit": "1.0"},
        {"network": "ERC20", "name": "Ethereum (ERC20)", "min_deposit": "10.0"},
        {"network": "BEP20", "name": "BSC (BEP20)", "min_deposit": "1.0"},
    ],
    "TRX": [{"network": "TRC20", "name": "Tron (TRC20)", "min_deposit": "1.0"}],
    "DOGE": [{"network": "DOGE", "name": "Dogecoin", "min_deposit": "1.0"}],
    "LTC": [{"network": "LTC", "name": "Litecoin", "min_deposit": "0.01"}],
    "BCH": [{"network": "BCH", "name": "Bitcoin Cash", "min_deposit": "0.001"}],
    "XRP": [{"network": "XRP", "name": "XRP Ledger", "min_deposit": "1.0"}],
    "SOL": [{"network": "SOL", "name": "Solana", "min_deposit": "0.01"}],
    "BNB": [{"network": "BEP20", "name": "BSC (BEP20)", "min_deposit": "0.01"}],
    "POL": [{"network": "POLYGON", "name": "Polygon", "min_deposit": "1.0"}],
    "GEM": [{"network": "INTERNAL", "name": "Internal (Pasino)", "min_deposit": "0"}],
}

# Endpoint refresh-token (capture browser real, 2026-06-08).
# Body: {"token": <current>, "language": "en"}
# Response: {"success": true, "new_token": <hex64>, "message": ""}
REFRESH_PATH = "/account/refresh-token"

# Interval heartbeat token-refresh dalam detik. Default 240s (4 menit).
# Pasino tidak ekspose TTL token, tapi observasi user: "exp cepat banget"
# -> 4 menit dipilih sebagai aman (token TTL biasanya 5-15 menit di casino).
# Bisa di-override via env var PASINO_REFRESH_INTERVAL kalau perlu tuning.
def _refresh_interval_seconds() -> int:
    raw = os.getenv("PASINO_REFRESH_INTERVAL", "240").strip()
    try:
        value = int(raw)
    except ValueError:
        return 240
    return max(30, value)  # minimum 30 detik biar tidak spam server


# Marker auth error di message body Pasino. Kalau response success=false
# DAN message mengandung salah satu marker ini, anggap token expired
# dan trigger refresh+retry. Daftar konservatif (case-insensitive substring).
# Cover English + Indonesian karena Pasino kadang balikin pesan Indonesia
# ("Tampaknya sesi Anda telah berakhir. Cobalah bersihkan cookie...").
_AUTH_ERROR_MARKERS = (
    # English
    "token",
    "unauthorized",
    "auth",
    "expired",
    "invalid",
    "session",
    "login",
    "not logged",
    "sign in",
    # Indonesian variants
    "sesi",              # "sesi Anda telah berakhir"
    "berakhir",          # "sesi telah berakhir"
    "masuk kembali",     # "silakan masuk kembali"
    "bersihkan cookie",  # "cobalah bersihkan cookie"
    "kadaluarsa",        # "token kadaluarsa"
    "kedaluwarsa",       # variant ejaan
    "tidak sah",         # "token tidak sah"
    "tidak valid",       # "token tidak valid"
    "silakan login",     # "silakan login kembali"
    "silakan masuk",     # "silakan masuk kembali"
)


def _gen_client_seed() -> str:
    """64 char alphanumeric mix-case (dari capture browser real)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(64))


def _resolve_via_doh(host: str, timeout: float = 8.0) -> str | None:
    """Resolve hostname via Cloudflare DNS-over-HTTPS.

    Banyak ISP Indonesia (Biznet "Safesurf", Telkom DNS filter, dll)
    block DNS untuk domain casino. Browser modern lolos karena pakai
    DoH built-in. Untuk bypass dari Python, kita query Cloudflare DoH
    langsung supaya dapat IP asli (bukan IP redirect ISP).

    Return None kalau gagal (mis. DoH juga di-block) -> caller fallback
    ke system DNS.
    """
    url = f"https://cloudflare-dns.com/dns-query?name={host}&type=A"
    req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None
    answers = [
        a.get("data") for a in data.get("Answer", [])
        if a.get("type") == 1 and a.get("data")
    ]
    return answers[0] if answers else None


def _floor_to(value: float, decimals: int) -> float:
    """Floor ke N decimal."""
    factor = Decimal(10) ** decimals
    dec = (Decimal(str(value)) + Decimal("0.000000000001")) * factor
    return float(int(dec) / factor)


def _round_to(value: float, decimals: int) -> float:
    factor = Decimal(10) ** decimals
    dec = Decimal(str(value)).quantize(Decimal(1) / factor, rounding=ROUND_HALF_UP)
    return float(dec)


def _is_auth_error_message(message: str | None) -> bool:
    """Cek apakah `message` mengindikasikan token expired / invalid auth.

    Pasino pakai response shape `{"success": false, "message": "..."}`
    dengan pesan dalam bahasa Inggris. Kita cek substring case-insensitive
    biar match variasi kata seperti "token expired", "invalid token",
    "session timed out", "please login", dst.
    """
    if not message:
        return False
    text = str(message).lower()
    return any(marker in text for marker in _AUTH_ERROR_MARKERS)


class PasinoClient:
    """REST client untuk Pasino hash-dice."""

    display_name: str = "Pasino"
    default_currencies: tuple[str, ...] = DEFAULT_CURRENCIES
    min_bet: float = 1e-8
    requires_token: bool = True

    def __init__(
        self,
        token: str,
        proxy: dict[str, str] | None = None,
        *,
        on_token_refresh: Callable[[str], None] | None = None,
    ):
        # Token: paste JWT dari localStorage > pasino.com > 'token'
        # Cloudflare anti-bot di-bypass via curl_cffi TLS impersonation,
        # tidak butuh cookie tambahan.
        #
        # `on_token_refresh` callback opsional yang dipanggil saat token
        # berhasil di-refresh. Kalau None (default), client otomatis
        # persist ke `apitokens.json` via storage.set_token_for("pasino", ...).
        # Pass callback explicit kalau caller mau handle persistence sendiri
        # (mis. test mode atau custom backend).
        raw = (token or "").strip()
        # Strip ;cookie=... kalau user paste format lama (back-compat,
        # cookie tetap di-set kalau ada tapi tidak strictly required)
        cookie_str = ""
        if ";cookie=" in raw:
            jwt_part, cookie_part = raw.split(";cookie=", 1)
            self._token = jwt_part.strip()
            cookie_str = cookie_part.strip()
        else:
            self._token = raw

        if not self._token:
            raise RuntimeError("Token Pasino kosong (paste JWT dari localStorage).")

        self._lock = threading.RLock()
        self._client_seed = _gen_client_seed()
        self._balances: dict[str, float] = {}
        self._username: str = ""
        self._proxy = proxy
        self._on_token_refresh = on_token_refresh

        # Heartbeat / auto-refresh state
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        # Lock terpisah untuk refresh — supaya refresh+retry concurrent dari
        # heartbeat dan dari _post() reactive tidak race (yang satu menunggu
        # yang lain selesai, lalu lihat token sudah di-update -> skip).
        self._refresh_lock = threading.Lock()

        # Pakai curl_cffi Session dengan Chrome impersonation. Ini bypass
        # Cloudflare TLS fingerprint check (JA3). Fallback ke requests
        # plain kalau curl_cffi tidak ter-install.
        if _HAS_CURL_CFFI:
            self._session = _curl_requests.Session(impersonate="chrome120")
        else:
            self._session = _curl_requests.Session()

        self._session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://pasino.com",
            "Referer": "https://pasino.com/",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "id;q=0.5",
            "Cache-Control": "max-age=0",
            "Priority": "u=1, i",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            ),
            "Sec-Ch-Ua": (
                '"Chromium";v="148", "Brave";v="148", "Not/A)Brand";v="99"'
            ),
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Sec-Gpc": "1",
        })
        if cookie_str:
            self._session.headers["Cookie"] = cookie_str
        if self._proxy:
            self._session.proxies = self._proxy

        # Bypass ISP DNS block (Biznet "Safesurf" dll) dengan resolve
        # api.pasino.com via Cloudflare DoH. CurlOpt.RESOLVE harus
        # di-inject SETIAP request karena curl_cffi reset handle option
        # antar request. Kita simpan IP-nya di self._resolved_ip dan
        # inject di `_post` setiap kali. Refresh kalau lebih dari 5 menit.
        self._resolved_ip: str | None = None
        self._resolved_at: float = 0.0
        self._refresh_resolved_ip(force=True)

        # Initial fetch balance untuk verify token + populate _balances
        self._fetch_balances()

        # Start background heartbeat untuk auto-refresh token. Dimulai
        # SETELAH initial fetch sukses biar token salah ketauan di awal
        # (RuntimeError dari _fetch_balances) bukan di background thread.
        self._start_heartbeat()

    def _refresh_resolved_ip(self, force: bool = False) -> None:
        """Refresh resolved IP via Cloudflare DoH. Best-effort: kalau gagal
        biarkan None supaya curl pakai system DNS (mungkin sukses kalau
        ISP customer tidak block)."""
        import time as _time

        if not _HAS_CURL_CFFI or _CurlOpt is None:
            return
        now = _time.time()
        # Cache 5 menit, hindari DoH spam tiap bet
        if not force and self._resolved_ip and (now - self._resolved_at) < 300:
            return
        ip = _resolve_via_doh(PASINO_HOST)
        if ip:
            self._resolved_ip = ip
            self._resolved_at = now

    # ---- Token auto-refresh -----------------------------------------------

    def _refresh_token(self) -> bool:
        """Panggil POST /account/refresh-token, update `self._token` kalau
        sukses. Return True kalau token berhasil di-refresh.

        Thread-safe: dipakai dari heartbeat thread (proactive) DAN dari
        _post() retry path (reactive). Lock `self._refresh_lock` mencegah
        double-refresh concurrent — kalau thread B masuk saat thread A
        sudah refresh, token di self._token sudah baru, B tinggal pakai.
        """
        # Try-acquire dengan timeout supaya thread tidak block lama kalau
        # refresh lain lagi jalan. Kalau gagal acquire dalam 10 detik,
        # asumsikan thread lain sudah refresh -> return True optimistically
        # (caller akan retry dengan token baru).
        acquired = self._refresh_lock.acquire(timeout=10.0)
        if not acquired:
            return True
        try:
            with self._lock:
                current = self._token
            try:
                # Pakai _allow_auth_retry=False supaya kalau refresh sendiri
                # ditolak kita tidak loop infinite (refresh -> auth error
                # -> refresh -> ...).
                data = self._post(
                    REFRESH_PATH,
                    {"token": current, "language": "en"},
                    timeout=15.0,
                    _allow_auth_retry=False,
                )
            except Exception:
                return False
            if not isinstance(data, dict) or not data.get("success"):
                return False
            new_token = str(data.get("new_token") or "").strip()
            # Sanity check: 64-char hex token (format Pasino current).
            # Kalau format berubah suatu saat, longgar-kan jadi length>=16
            # supaya tidak break.
            if not new_token or len(new_token) < 16:
                return False
            with self._lock:
                self._token = new_token
            self._persist_refreshed_token(new_token)
            return True
        finally:
            self._refresh_lock.release()

    def _persist_refreshed_token(self, new_token: str) -> None:
        """Save token baru ke storage (atau panggil callback custom).

        Default behavior: lazy-import `corebot.storage` dan panggil
        `set_token_for("pasino", new_token)`. Ini membuat token tetap
        valid lintas restart bot — user tidak perlu paste ulang token
        setiap kali bot di-restart.

        Kalau caller pass `on_token_refresh` di __init__, callback itu
        yang dipanggil (override default storage). Berguna untuk test
        mode atau custom backend. Exception dari callback di-swallow
        supaya tidak crash heartbeat thread.
        """
        if self._on_token_refresh is not None:
            try:
                self._on_token_refresh(new_token)
            except Exception:
                pass
            return
        try:
            # Lazy import: hindari circular import antar package
            # corebot.clients <-> corebot.storage saat module load.
            from ..storage import set_token_for
            set_token_for("pasino", new_token)
        except Exception:
            # Best-effort: kalau storage gagal (mis. disk full / read-only
            # filesystem), token in-memory tetap ter-update. Bot lanjut
            # bekerja sampai shutdown, user perlu paste ulang setelah restart.
            pass

    def _start_heartbeat(self) -> None:
        """Spawn daemon thread yang call _refresh_token() periodik."""
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        thread = threading.Thread(
            target=self._heartbeat_loop,
            name="pasino-token-heartbeat",
            daemon=True,
        )
        thread.start()
        self._heartbeat_thread = thread

    def _heartbeat_loop(self) -> None:
        """Loop heartbeat: tunggu N detik, refresh token, ulang.

        Pakai Event.wait() bukan time.sleep() supaya bisa di-interrupt
        cepat saat shutdown via _stop_heartbeat().
        """
        interval = _refresh_interval_seconds()
        while not self._heartbeat_stop.wait(interval):
            try:
                self._refresh_token()
            except Exception:
                # Silent: heartbeat tidak boleh crash. Kalau refresh gagal,
                # request berikutnya yang trigger reactive retry akan coba
                # lagi.
                pass

    def _stop_heartbeat(self) -> None:
        """Sinyal shutdown ke heartbeat thread + tunggu join singkat."""
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._heartbeat_thread = None

    def close(self) -> None:
        """Graceful shutdown. Stop heartbeat thread."""
        self._stop_heartbeat()

    def __del__(self):
        # Best-effort cleanup kalau caller lupa close(). Daemon thread
        # akan otomatis mati saat interpreter exit, tapi explicit stop
        # lebih cepat untuk testing.
        try:
            self._stop_heartbeat()
        except Exception:
            pass

    def _post(
        self,
        path: str,
        payload: dict,
        timeout: float = 20.0,
        *,
        _allow_auth_retry: bool = True,
    ) -> dict:
        """POST ke Pasino API. Body di-stringify JSON walau content-type
        urlencoded - sesuai dengan cara axios di source. curl_cffi
        impersonate Chrome TLS supaya bypass Cloudflare 403.

        CurlOpt.RESOLVE di-inject sebelum SETIAP request karena
        curl_cffi reset session handle antar request, jadi setopt di
        __init__ tidak persistent.

        Auto-refresh: kalau payload mengandung field `token`, di-replace
        dengan token TERBARU dari `self._token` sebelum kirim. Ini penting
        karena heartbeat thread bisa update token kapan saja, dan caller
        mungkin sudah build payload dengan token lama. Caller yang ingin
        kirim token spesifik (mis. internal refresh-token call yang pakai
        token current) tetap bisa karena value di payload akan match
        `self._token` saat itu.

        Reactive retry: kalau `_allow_auth_retry=True` (default) dan
        response ngembaliin success=false dengan auth-error marker,
        client coba refresh token + retry sekali. Endpoint refresh-token
        sendiri set `_allow_auth_retry=False` untuk hindari loop.
        """
        # Inject token terbaru kalau payload pakai field 'token'
        if isinstance(payload, dict) and "token" in payload:
            with self._lock:
                payload = {**payload, "token": self._token}

        # Refresh IP DoH kalau cache expired
        self._refresh_resolved_ip()

        # Inject RESOLVE option pada session.curl sebelum request.
        # Format: ["host:port:ip", ...]. Ini override system DNS hanya
        # untuk hostname ini.
        if (
            _HAS_CURL_CFFI
            and _CurlOpt is not None
            and self._resolved_ip
        ):
            try:
                self._session.curl.setopt(
                    _CurlOpt.RESOLVE,
                    [f"{PASINO_HOST}:443:{self._resolved_ip}"],
                )
            except Exception:
                pass  # best-effort

        url = PASINO_API + path
        body = json.dumps(payload)
        try:
            resp = self._session.post(url, data=body, timeout=timeout)
        except Exception as exc:
            # Kalau SSL/network error, refresh IP dan retry sekali
            err_str = str(exc).lower()
            if "ssl" in err_str or "resolve" in err_str or "connect" in err_str:
                self._refresh_resolved_ip(force=True)
                if (
                    _HAS_CURL_CFFI
                    and _CurlOpt is not None
                    and self._resolved_ip
                ):
                    try:
                        self._session.curl.setopt(
                            _CurlOpt.RESOLVE,
                            [f"{PASINO_HOST}:443:{self._resolved_ip}"],
                        )
                    except Exception:
                        pass
                try:
                    resp = self._session.post(url, data=body, timeout=timeout)
                except Exception as exc2:
                    raise RuntimeError(f"Network error: {exc2}") from exc2
            else:
                raise RuntimeError(f"Network error: {exc}") from exc
        # fast_json_loads pakai orjson kalau tersedia (5x lebih cepat).
        try:
            from ..lua_support import fast_json_loads
            data = fast_json_loads(resp.content)
        except (ValueError, json.JSONDecodeError):
            raise RuntimeError(
                f"Response Pasino bukan JSON ({resp.status_code}): "
                f"{resp.text[:200]}"
            )

        # Reactive auth-error retry. Kalau dapat success=false dengan
        # marker token-expired, refresh + retry sekali. Skip untuk endpoint
        # refresh-token sendiri (_allow_auth_retry=False).
        if (
            _allow_auth_retry
            and isinstance(data, dict)
            and data.get("success") is False
        ):
            msg = str(data.get("message") or data.get("error") or "")
            if _is_auth_error_message(msg):
                refreshed = self._refresh_token()
                if refreshed:
                    # Token sudah ter-update di self._token, _post() akan
                    # auto-inject saat retry karena field 'token' ada di
                    # payload. Set _allow_auth_retry=False supaya tidak
                    # nested retry kalau kebetulan masih gagal.
                    return self._post(
                        path,
                        payload,
                        timeout=timeout,
                        _allow_auth_retry=False,
                    )
        # Fase 8.1: kalau response bukan dict (mis. list, string, None),
        # bungkus sebagai error ketimbang return mentah yang akan bikin
        # crash di caller (place_bet, _fetch_balances, dll).
        if not isinstance(data, dict):
            raw_preview = str(data)[:300] if data is not None else "null"
            raise RuntimeError(
                f"Response Pasino bukan object ({resp.status_code}): "
                f"{raw_preview}"
            )
        return data

    # ---- BaseClient contract ---------------------------------------------

    def _fetch_balances(self) -> None:
        data = self._post(
            "/coin/get-balances",
            {"token": self._token, "language": "en"},
            timeout=15.0,
        )
        # Response shape (capture real):
        #   {"message": "", "coins": [{"coin": "BTC", "balance": "0.00001355", ...}, ...]}
        # Back-compat: kalau Pasino kembali pakai "data" suatu hari.
        items = data.get("coins") or data.get("data")
        if not items or not isinstance(items, list):
            err = data.get("message") or data.get("error")
            if not err:
                err = f"shape tidak dikenal: {json.dumps(data)[:300]}"
            raise RuntimeError(f"Pasino auth gagal: {err}")
        with self._lock:
            self._balances = {
                str(item.get("coin", "")).upper(): float(item.get("balance") or 0)
                for item in items
                if item.get("coin")
            }

    def balances(self) -> dict:
        with self._lock:
            return {
                "balances": [
                    {"currency": cur, "amount": amt}
                    for cur, amt in self._balances.items()
                ]
            }

    def stats(self) -> dict:
        return {}

    def profile(self) -> dict:
        with self._lock:
            return {"user": {"name": self._username or "pasino-user"}}

    def place_bet(
        self, currency: str, amount: float, chance: float, bethigh: bool
    ) -> dict:
        """Place 1 dice bet via /dice/play.

        Payload format (dari capture browser real, bukan source obfuscated):
          {
            token: <jwt>,
            language: "id" | "en",
            bet_amt: "0.10000000",     # string fixed 8 decimal
            coin: "GEM",                # UPPERCASE (real format)
            type: "2",                  # string "1"=under, "2"=over
            payout: "1.21794",          # 5 decimal multiplier
            client_seed: <64 char hex/alnum>
          }

        Note: source nuts-pasino.md punya field `winning_chance` + `profit`
        tapi capture browser real tidak ada. Field-field itu mungkin
        di-derive server-side, atau opsional. Kita pakai format minimal.
        """
        # Pasino RTP 95%
        payout_base = 95
        chance_clamped = max(0.01, min(94.99, float(chance)))
        local_chance = _round_to(chance_clamped, 2)

        multiplier = _floor_to(payout_base / local_chance, 5)
        bet_amt = _floor_to(float(amount), 8)

        bet_type = "2" if bethigh else "1"
        currency_upper = str(currency).upper()

        payload = {
            "token": self._token,
            "language": "id",
            "bet_amt": f"{bet_amt:.8f}",
            "coin": currency_upper,
            "type": bet_type,
            "payout": f"{multiplier:.5f}",
            "client_seed": self._client_seed,
        }

        data = self._post("/dice/play", payload, timeout=15.0)
        # Response Pasino native:
        # success: true  -> bet OK, parse hasil
        # success: false -> error, ada `message`
        if data.get("success") is False:
            err_msg = data.get("message") or "Bet gagal"
            err_code = data.get("error") or data.get("code")
            raise RuntimeError(f"Server error: {err_msg} (code={err_code})")

        return self._normalize_bet_response(data, bet_amt, currency_upper)

    def reset_seed(self) -> dict:
        try:
            self._post(
                "/dice/rotate-seed",
                {"token": self._token, "language": "en"},
                timeout=10.0,
            )
            self._client_seed = _gen_client_seed()
            return {"ok": True}
        except RuntimeError:
            return {"ok": False}

    # ---- Deposit ---------------------------------------------------------

    def deposit_address(self, coin: str, network: str = "") -> dict:
        """Fetch alamat deposit untuk coin tertentu.

        Endpoint (capture real 2026):
          POST /deposit/get-deposit-information
          Payload: {token, coin, language}
          Response:
            {
              "success": true,
              "message": "",
              "address": "0xEA7200Cf...",
              "confirmations_required": "14",
              "fp_supported": "0",
              "minimum_deposit_direct": "0.00010000",
              "minimum_deposit_fp": "0.01422031",
              "qr": "https://quickchart.io/qr?text=...&size=200&margin=3",
              "requires_payment_tag": "0"
            }

        Note: Pasino tidak pakai field `network` di payload — 1 coin = 1
        address (network sudah fix per coin di backend mereka).
        Parameter `network` tetap diterima untuk compatibility tapi tidak
        dikirim ke API.
        """
        coin_upper = str(coin).upper()
        payload: dict = {
            "token": self._token,
            "coin": coin_upper,
            "language": "en",
        }

        data = self._post("/deposit/get-deposit-information", payload, timeout=15.0)

        if data.get("success") is False:
            err_msg = data.get("message") or "Gagal ambil alamat deposit"
            raise RuntimeError(f"Deposit address error: {err_msg}")

        # Parse response real
        address = str(data.get("address") or "").strip()
        confirmations = str(data.get("confirmations_required") or "0")
        min_deposit = str(data.get("minimum_deposit_direct") or "0")
        min_deposit_fp = str(data.get("minimum_deposit_fp") or "0")
        qr_url = str(data.get("qr") or "")
        requires_tag = str(data.get("requires_payment_tag") or "0") == "1"
        fp_supported = str(data.get("fp_supported") or "0") == "1"

        if not address:
            raise RuntimeError(
                "Server tidak mengembalikan alamat deposit. "
                "Coba buka pasino.com dan deposit manual untuk verifikasi."
            )

        return {
            "address": address,
            "network": network.upper() if network else "",
            "coin": coin_upper,
            "confirmations_required": confirmations,
            "min_deposit": min_deposit,
            "min_deposit_fp": min_deposit_fp,
            "qr_url": qr_url,
            "requires_payment_tag": requires_tag,
            "fp_supported": fp_supported,
        }

    def deposit_networks(self, coin: str) -> list[dict]:
        """Return daftar network yang tersedia untuk deposit coin.

        Pasino tidak punya endpoint terpisah untuk list network — endpoint
        `/deposit/get-deposit-information` langsung return address per coin.
        Jadi kita pakai hardcoded fallback per coin (dari observasi halaman
        deposit Pasino).

        Untuk coin single-network (BTC, DOGE, LTC, dll) return 1 entry.
        Untuk coin multi-network (USDT, ETH, dll) return semua opsi.
        """
        coin_upper = str(coin).upper()
        return DEPOSIT_NETWORKS_FALLBACK.get(
            coin_upper,
            [{"network": coin_upper, "name": coin_upper, "min_deposit": "0"}],
        )

    # ---- Withdraw --------------------------------------------------------

    def withdraw_info(self, coin: str) -> dict:
        """Fetch info withdrawal (fee, minimum) untuk coin tertentu.

        Endpoint (capture real 2026):
          POST /withdraw/get-coin-information
          Payload: {"token": "...", "coin": "POL", "language": "en"}
          Response:
            {
              "success": true,
              "message": "",
              "fp_supported": "0",
              "minimum_withdrawal_direct": "0.01000000",
              "minimum_withdrawal_fp": "0.00300000",
              "withdrawal_fee_direct": "0.00090000",
              "withdrawal_fee_fp": "0.00000000"
            }
        """
        coin_upper = str(coin).upper()
        payload = {
            "token": self._token,
            "coin": coin_upper,
            "language": "en",
        }

        data = self._post("/withdraw/get-coin-information", payload, timeout=15.0)

        if data.get("success") is False:
            err_msg = data.get("message") or "Gagal ambil info withdraw"
            raise RuntimeError(f"Withdraw info error: {err_msg}")

        return {
            "coin": coin_upper,
            "minimum_withdrawal": str(data.get("minimum_withdrawal_direct") or "0"),
            "minimum_withdrawal_fp": str(data.get("minimum_withdrawal_fp") or "0"),
            "fee": str(data.get("withdrawal_fee_direct") or "0"),
            "fee_fp": str(data.get("withdrawal_fee_fp") or "0"),
            "fp_supported": str(data.get("fp_supported") or "0") == "1",
        }

    def place_withdrawal(self, coin: str, address: str, amount: float) -> dict:
        """Submit withdrawal request.

        Endpoint (capture real 2026):
          POST /withdraw/place-withdrawal
          Payload:
            {
              "token": "...",
              "language": "en",
              "coin": "POL",
              "method": "DIRECT",
              "address": "0x80A7E5...",
              "amount": "2.00000000"
            }
          Response:
            {
              "success": true,
              "message": "Your withdrawal has been placed successfully...",
              "coin": "POL",
              "balance": "16.92734812"
            }
        """
        coin_upper = str(coin).upper()
        address_stripped = str(address).strip()

        if not address_stripped:
            raise RuntimeError("Alamat withdraw kosong.")

        payload = {
            "token": self._token,
            "language": "en",
            "coin": coin_upper,
            "method": "DIRECT",
            "address": address_stripped,
            "amount": f"{float(amount):.8f}",
        }

        data = self._post("/withdraw/place-withdrawal", payload, timeout=20.0)

        if data.get("success") is False:
            err_msg = data.get("message") or "Withdraw gagal"
            raise RuntimeError(f"Withdraw error: {err_msg}")

        # Update balance internal
        new_balance = data.get("balance")
        if new_balance is not None:
            try:
                with self._lock:
                    self._balances[coin_upper] = float(new_balance)
            except (TypeError, ValueError):
                pass

        return {
            "success": True,
            "message": str(data.get("message") or "Withdrawal placed."),
            "coin": coin_upper,
            "balance": str(new_balance or ""),
        }

    # ---- Helpers ---------------------------------------------------------

    def check_token_status(self) -> dict:
        """Cek apakah token masih aktif dengan memanggil endpoint ringan.

        Pakai /coin/get-balances sebagai probe. Kalau sukses = token aktif.
        Kalau gagal dengan auth error = token expired/invalid.

        Return:
          {"active": True/False, "message": "...", "token_preview": "6c21...f7ec"}
        """
        with self._lock:
            token_preview = self._token[:4] + "..." + self._token[-4:] if len(self._token) > 8 else "***"

        try:
            data = self._post(
                "/coin/get-balances",
                {"token": self._token, "language": "en"},
                timeout=10.0,
                _allow_auth_retry=False,  # Jangan auto-retry, kita mau tahu status asli
            )
            if data.get("success") is False:
                msg = str(data.get("message") or "")
                if _is_auth_error_message(msg):
                    return {"active": False, "message": f"Token expired: {msg}", "token_preview": token_preview}
                return {"active": False, "message": msg or "Unknown error", "token_preview": token_preview}
            # Sukses = token aktif
            coins = data.get("coins") or data.get("data")
            coin_count = len(coins) if isinstance(coins, list) else 0
            return {
                "active": True,
                "message": f"Token aktif ({coin_count} coins loaded)",
                "token_preview": token_preview,
            }
        except RuntimeError as exc:
            err = str(exc)
            if "auth" in err.lower() or "token" in err.lower():
                return {"active": False, "message": err, "token_preview": token_preview}
            return {"active": False, "message": f"Connection error: {err}", "token_preview": token_preview}

    def force_refresh_token(self) -> dict:
        """Manual force refresh token via /account/refresh-token.

        Return:
          {"success": True/False, "message": "...", "new_token_preview": "ab12...cd34"}
        """
        ok = self._refresh_token()
        with self._lock:
            token_preview = self._token[:4] + "..." + self._token[-4:] if len(self._token) > 8 else "***"
        if ok:
            return {
                "success": True,
                "message": "Token berhasil di-refresh dan tersimpan.",
                "new_token_preview": token_preview,
            }
        return {
            "success": False,
            "message": "Refresh gagal. Token mungkin sudah expired — paste ulang dari browser.",
            "new_token_preview": token_preview,
        }

    def _normalize_bet_response(
        self, raw: dict, wager: float, currency: str
    ) -> dict:
        """Convert Pasino response ke shape generic engine.

        Native shape (capture real):
          {
            "success": true,
            "win": 1 | 0,
            "payout": "1.91919",
            "roll_number": 816,         # 0..9999, divide /100 -> 0.00..99.99
            "coin": "GEM",
            "balance": "6299.73550700", # saldo authoritative dari server
            "profit": "0.09191900",     # signed delta sebagai string
            "bet_id": "...",
            "lootbox": null,
            "message": ""
          }
        """
        profit = float(raw.get("profit") or 0)
        # roll_number 0..9999 -> result_value 0.00..99.99
        roll_number = raw.get("roll_number")
        if roll_number is None:
            result_value = 0.0
        else:
            result_value = float(roll_number) / 100.0

        # Pasino kasih flag `win` explicit (1=win, 0=lose). Lebih reliable
        # daripada infer dari profit (kalau ada bet 0% chance ribet).
        win_flag = raw.get("win")
        if win_flag is not None:
            is_win = bool(int(win_flag))
        else:
            is_win = profit > 0

        # Pakai balance authoritative dari server kalau ada (paling akurat).
        # Kalau tidak ada, hitung manual dari profit.
        cur_upper = currency.upper()
        with self._lock:
            server_balance = raw.get("balance")
            if server_balance is not None:
                try:
                    new_balance = float(server_balance)
                    self._balances[cur_upper] = new_balance
                except (TypeError, ValueError):
                    self._balances[cur_upper] = (
                        self._balances.get(cur_upper, 0.0) + profit
                    )
                    new_balance = self._balances[cur_upper]
            else:
                self._balances[cur_upper] = (
                    self._balances.get(cur_upper, 0.0) + profit
                )
                new_balance = self._balances[cur_upper]

        return {
            "bet": {
                "amount": float(wager),
                "state": "win" if is_win else "lose",
                "result_value": result_value,
                "profit": profit,
            },
            "userBalance": {"amount": new_balance},
        }
