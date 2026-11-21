"""Shared HTTP client factory dengan multi-backend support.

Backend yang tersedia (dipilih via env var):
    - `requests`    (default) - stdlib compatible, stable
    - `httpx`       (RAPTECH_HTTP_BACKEND=httpx) - HTTP/2, connection pool
                    bikin request ke API site lebih cepat 30-50% terutama
                    untuk site dengan banyak call per detik.
    - `curl_cffi`   (RAPTECH_USE_CURL_CFFI=1) - Chrome TLS impersonation
                    untuk bypass Cloudflare (dipakai Pasino).

httpx punya API mirip requests. Untuk kompatibilitas, semua backend
kembalikan session object yang bisa dipakai dengan pattern:

    session.request(method, url, json=..., timeout=...)
    resp.status_code, resp.content, resp.text, resp.headers
    resp.raise_for_status()

Client code tidak perlu tahu backend apa yang aktif — pakai wrapper ini
supaya perubahan backend future-proof.
"""
from __future__ import annotations

import os
from typing import Any


def _env_flag(name: str) -> bool:
    """Return True kalau env var name berisi '1', 'true', 'yes', atau 'on'."""
    return (os.getenv(name, "") or "").lower() in ("1", "true", "yes", "on")


def _http_backend_pref() -> str:
    """Return backend preference dari env RAPTECH_HTTP_BACKEND.

    Values: 'httpx', 'curl_cffi', 'requests' (default).
    """
    val = (os.getenv("RAPTECH_HTTP_BACKEND", "") or "").lower().strip()
    if val in ("httpx", "curl_cffi", "requests"):
        return val
    # Legacy fallback: RAPTECH_USE_CURL_CFFI=1
    if _env_flag("RAPTECH_USE_CURL_CFFI"):
        return "curl_cffi"
    return "requests"


def build_http_session(
    *,
    prefer_curl_cffi: bool = False,
    impersonate: str = "chrome120",
    http2: bool = True,
    pool_size: int = 4,
) -> tuple[Any, str]:
    """Bangun HTTP session sesuai preferensi backend.

    Args:
        prefer_curl_cffi: kalau True, prioritaskan curl_cffi tanpa
            perlu env var (dipakai Pasino yang butuh Cloudflare bypass).
        impersonate: TLS fingerprint untuk curl_cffi.
        http2: enable HTTP/2 kalau backend support (httpx).
        pool_size: connection pool size (httpx dan requests).

    Return:
        Tuple `(session, backend_name)`. Backend name: 'requests',
        'httpx', atau 'curl_cffi'.
    """
    backend = _http_backend_pref()
    if prefer_curl_cffi:
        backend = "curl_cffi"

    # Try curl_cffi first kalau di-preferer atau env-force
    if backend == "curl_cffi":
        try:
            from curl_cffi import requests as cffi_requests  # type: ignore
            sess = cffi_requests.Session(impersonate=impersonate)
            return sess, "curl_cffi"
        except ImportError:
            pass  # fallback ke default

    # Try httpx kalau di-request
    if backend == "httpx":
        try:
            import httpx  # type: ignore

            # httpx.Client() blocks & syncronous - mirip requests.
            # HTTP/2 hanya aktif kalau lib 'h2' terinstall (biasanya
            # ikut dengan httpx[http2]).
            limits = httpx.Limits(
                max_connections=pool_size * 2,
                max_keepalive_connections=pool_size,
            )
            timeout = httpx.Timeout(30.0, connect=10.0)
            client = httpx.Client(
                http2=http2,
                limits=limits,
                timeout=timeout,
                follow_redirects=True,
            )
            # Adapter shim: wrap sedikit supaya API mirip requests.Session
            return _HttpxRequestsAdapter(client), "httpx"
        except ImportError:
            pass  # fallback ke requests

    # Default: requests dengan HTTPAdapter + Retry
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    sess = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=1,
        backoff_factor=0.3,
        status_forcelist=(502, 503, 504),
        allowed_methods=("GET", "POST"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        pool_connections=pool_size // 2 or 1,
        pool_maxsize=pool_size,
        pool_block=True,
        max_retries=retry,
    )
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess, "requests"


class _HttpxRequestsAdapter:
    """Thin wrapper httpx.Client supaya API-nya kompatibel dengan
    `requests.Session` untuk pattern yang paling umum di codebase.

    Yang di-cover:
        - session.headers (dict-like update via .update)
        - session.proxies (dict-like)
        - session.request(method, url, json=, data=, timeout=, ...)
        - session.get(...), session.post(...)
        - session.close()

    Response object dari httpx sudah punya:
        - .status_code, .text, .content, .headers
        - .raise_for_status()
        - .json()

    Yang tidak di-cover (jarang dipakai): mount adapter, retry policy
    (httpx handle sendiri).
    """

    def __init__(self, client):
        self._client = client
        # Dict-like accessors — httpx pakai attribute berbeda
        self.headers = _HeadersProxy(client)
        self.proxies = _ProxiesProxy(client)

    def request(self, method: str, url: str, **kwargs):
        # httpx pakai 'content' bukan 'data' untuk raw body, tapi
        # `data` (dict) di-encode form-urlencoded — sama seperti requests.
        # `json` sama-sama di-support.
        return self._client.request(method, url, **kwargs)

    def get(self, url: str, **kwargs):
        return self._client.get(url, **kwargs)

    def post(self, url: str, **kwargs):
        return self._client.post(url, **kwargs)

    def close(self):
        try:
            self._client.close()
        except Exception:
            pass


class _HeadersProxy:
    """Proxy untuk `session.headers` yang mirror ke httpx.Client.headers."""

    def __init__(self, client):
        self._client = client

    def update(self, other):
        for k, v in other.items():
            self._client.headers[k] = v

    def __setitem__(self, key, value):
        self._client.headers[key] = value

    def __getitem__(self, key):
        return self._client.headers[key]

    def __contains__(self, key):
        return key in self._client.headers


class _ProxiesProxy:
    """Proxy untuk `session.proxies` yang set httpx proxy config."""

    def __init__(self, client):
        self._client = client

    def update(self, other):
        # httpx pakai `.proxies` attribute yang perlu di-set saat init.
        # Untuk update runtime, kita simpan tapi tidak apply sepenuhnya
        # (limitation httpx). Client yang butuh proxy dinamis harus
        # rebuild session.
        for k, v in other.items():
            self[k] = v

    def __setitem__(self, key, value):
        # Best-effort: coba set httpx internal state
        try:
            transport = getattr(self._client, "_transport", None)
            if transport and hasattr(transport, "_proxy"):
                transport._proxy = value
        except Exception:
            pass


__all__ = ["build_http_session"]
