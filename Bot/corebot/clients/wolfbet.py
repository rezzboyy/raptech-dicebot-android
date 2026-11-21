"""Wolf.bet client implementation."""

from __future__ import annotations

import json
import os
import threading
import time
from decimal import Decimal, ROUND_HALF_UP

from ..config import BASE_URL, DEFAULT_CURRENCIES, GAME_NAME, WALLET_URL


# HTTP session builder — support requests (default), curl_cffi
# (RAPTECH_USE_CURL_CFFI=1), atau httpx HTTP/2 (RAPTECH_HTTP_BACKEND=httpx).
# Backend dipilih otomatis sesuai env. Wolfbet tidak butuh Cloudflare
# bypass, jadi default 'requests' cukup. User bisa opt-in httpx untuk
# gain HTTP/2 + connection pool speedup.
from ..http_client import build_http_session


class WolfBetClient:
    """HTTP client untuk Wolf.bet (dice game).

    Mengikuti kontrak `BaseClient` dari `clients.base`.
    """

    display_name: str = "Wolf.bet"
    default_currencies: tuple[str, ...] = tuple(DEFAULT_CURRENCIES)
    min_bet: float = 1e-8
    # Fase 3.3: jangan refresh balance lebih sering dari interval ini
    # (engine pakai untuk dedupe probe).
    min_refresh_interval_s: float = 1.0

    def __init__(self, token: str, proxy: dict[str, str] | None = None):
        self._lock = threading.RLock()
        # Shared factory — backend dipilih via env RAPTECH_HTTP_BACKEND.
        # Retry policy + connection pool sudah di-handle di dalam factory.
        self.session, self._http_backend = build_http_session()
        self._is_curl_cffi = self._http_backend == "curl_cffi"
        headers = {
            "User-Agent": "WolfBetCLI",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        x_hash_api = os.getenv("WOLFBET_X_HASH_API")
        if x_hash_api:
            headers["X-Hash-Api"] = x_hash_api
        self.session.headers.update(headers)
        if proxy:
            self.session.proxies.update(proxy)

    def _send(
        self,
        method: str,
        route: str,
        body: dict | None = None,
        base_url: str | None = None,
    ) -> dict:
        base = base_url or BASE_URL
        url = f"{base.rstrip('/')}/{route.lstrip('/')}"
        with self._lock:
            resp = self.session.request(method, url, json=body, timeout=30)
        # Kompatibel dengan requests dan httpx — keduanya expose
        # raise_for_status() dan status_code/text di response object.
        try:
            resp.raise_for_status()
        except Exception as exc:
            raise RuntimeError(f"HTTP {resp.status_code} for {url}: {resp.text}") from exc
        # Fase 3.4: pakai orjson kalau tersedia (lewat fast_json_loads).
        # Fallback ke resp.json() (stdlib) kalau orjson tidak ada.
        from ..lua_support import fast_json_loads
        try:
            data = fast_json_loads(resp.content)
        except Exception:
            data = resp.json()
        if "errors" in data:
            raise RuntimeError(json.dumps(data["errors"]))
        if "error" in data:
            raise RuntimeError(json.dumps(data["error"]))
        return data

    # ---- BaseClient contract ---------------------------------------------

    def balances(self) -> dict:
        return self._send("GET", "api/v1/user/balances")

    def stats(self) -> dict:
        return self._send("GET", "api/v1/user/stats/bets")

    def profile(self) -> dict:
        return self._send("GET", "api/v1/user/profile", base_url=WALLET_URL)

    def place_bet(self, currency: str, amount: float, chance: float, bethigh: bool) -> dict:
        min_bet_dec = Decimal("0.00000001")
        amount_dec = Decimal(str(amount))
        if amount_dec < min_bet_dec:
            amount_dec = min_bet_dec
        condition = "over" if bethigh else "under"
        if bethigh:
            game = 9999 - int(chance * 100)
        else:
            game = int(chance * 100)
        bet_value = Decimal(game) / Decimal("100")
        if condition == "under":
            chance_used = bet_value
        else:
            chance_used = Decimal("99.99") - bet_value
        if chance_used <= 0:
            chance_used = Decimal(str(max(0.01, min(98.0, chance))))
        if condition == "under" and bet_value >= Decimal("95.0"):
            bet_value = Decimal("94.99")
            chance_used = Decimal("94.99")
        if condition == "over" and bet_value <= Decimal("5.0"):
            bet_value = Decimal("5.01")
            chance_used = Decimal("99.99") - bet_value
        multiplier = (Decimal("99") / chance_used).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        bet_value = bet_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        payload = {
            "currency": currency,
            "game": GAME_NAME,
            "amount": f"{amount_dec:.8f}",
            "rule": condition,
            "multiplier": f"{multiplier}",
            "bet_value": f"{bet_value}",
        }
        return self._send("POST", "api/v1/bet/place", payload)

    def reset_seed(self) -> dict:
        payload = {"client_seed": str(time.time()).replace(".", "")}
        return self._send("POST", "api/v1/user/seed/refresh", payload)

    # ---- Account settings (Wolfbet-specific) -----------------------------

    def change_email(self, new_email: str, captcha_token: str = "") -> dict:
        """Change email address di akun Wolfbet.

        Server akan kirim verification link ke email baru — user harus
        klik link tersebut di inbox untuk konfirmasi.

        Endpoint pakai `wolfbet.win/v1/user/email/change` (bukan
        `wolf.bet/api/v1/...` seperti endpoint lain).

        Args:
            new_email: alamat email baru target
            captcha_token: reCAPTCHA v3 token dari browser. Biasanya
                empty string OK untuk request yang sudah authenticated
                (server lebih lenient). Kalau server reject, isi manual
                dengan cara solve captcha di browser lalu paste.

        Return:
            dict response dari server, contoh:
                {"message": "To complete email update, verify new address via your inbox"}

        Raise:
            RuntimeError kalau server tolak (email invalid, captcha
            required, dst).
        """
        new_email = (new_email or "").strip().lower()
        if not new_email or "@" not in new_email or "." not in new_email:
            raise RuntimeError(f"Format email tidak valid: {new_email!r}")

        payload = {
            "email": new_email,
            "g-recaptcha-response": captcha_token or "",
        }
        # Endpoint tanpa `api/` prefix (verified dari DevTools capture).
        return self._send("POST", "v1/user/email/change", payload, base_url=WALLET_URL)

    # ---- Vault (Wolfbet-specific) ----------------------------------------
    #
    # Vault = "brankas" di akun Wolfbet untuk melindungi dana dari betting.
    # Endpoint berada di WALLET_URL (wolfbet.win), bukan BASE_URL.
    #
    # Capture DevTools:
    #   GET  api/v1/user/vault/balance                 -> saldo vault
    #   POST (deposit/withdraw) body:
    #        { currency, amount, password, <2fa?> }    -> butuh password + 2FA
    #
    # CATATAN: path deposit/withdraw + nama field 2FA masih perlu konfirmasi
    # dari 1 test kecil (lihat task-vault.md). Server menolak bila salah →
    # tidak ada dana berpindah. Amount & 2FA divalidasi di layer pemanggil.

    has_vault: bool = True  # penanda dukungan vault untuk gating di GUI

    def vault_balance(self, currency: str | None = None) -> dict:
        """GET saldo vault (semua currency). Non-destruktif."""
        return self._send("GET", "api/v1/user/vault/balance", base_url=WALLET_URL)

    def _vault_payload(self, currency: str, amount, password: str,
                       two_factor_code: str = "") -> dict:
        # amount dikirim sebagai number (mengikuti capture: 0.0801259).
        payload: dict = {
            "currency": (currency or "").lower(),
            "amount": float(amount),
            "password": password,
        }
        # Nama field 2FA belum 100% pasti; kirim di beberapa kemungkinan key
        # agar kompatibel. Server abaikan key yang tidak dikenal.
        if two_factor_code:
            code = str(two_factor_code).strip()
            payload["two_factor_token"] = code
            payload["otp"] = code
        return payload

    def vault_deposit(self, currency: str, amount, password: str,
                      two_factor_code: str = "") -> dict:
        """Deposit dana dari saldo main ke Vault (butuh password + 2FA)."""
        payload = self._vault_payload(currency, amount, password, two_factor_code)
        return self._send("POST", "api/v1/user/vault/deposit", payload, base_url=WALLET_URL)

    def vault_withdraw(self, currency: str, amount, password: str,
                       two_factor_code: str = "") -> dict:
        """Withdraw dana dari Vault kembali ke saldo main (butuh password + 2FA)."""
        payload = self._vault_payload(currency, amount, password, two_factor_code)
        return self._send("POST", "api/v1/user/vault/withdraw", payload, base_url=WALLET_URL)
