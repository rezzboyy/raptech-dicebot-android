"""Worker thread untuk operasi network yang lambat (connect/refresh).

Operasi network (connect ke site, refresh balance) bisa makan waktu
sampai timeout (30s). Kalau dijalankan di main thread, UI beku ("not
responding"). Worker ini menjalankannya di QThread terpisah dan
mengirim hasil via Qt signal ke main thread.
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from bridge.connection import connect, refresh


class ConnectWorker(QThread):
    """Jalankan connect(site, token) di thread terpisah."""

    succeeded = Signal(object, object)  # (client, account)
    failed = Signal(str)

    def __init__(self, site: str, token: str, currency: str | None = None) -> None:
        super().__init__()
        self._site = site
        self._token = token
        self._currency = currency

    def run(self) -> None:
        try:
            client, account = connect(self._site, self._token, self._currency)
            self.succeeded.emit(client, account)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class RefreshWorker(QThread):
    """Jalankan refresh(client, account, currency) di thread terpisah."""

    succeeded = Signal(object)  # account
    failed = Signal(str)

    def __init__(self, client, account, currency: str | None = None) -> None:
        super().__init__()
        self._client = client
        self._account = account
        self._currency = currency

    def run(self) -> None:
        try:
            account = refresh(self._client, self._account, self._currency)
            self.succeeded.emit(account)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class VaultBalanceWorker(QThread):
    """Ambil saldo vault (GET, non-destruktif) di thread terpisah."""

    succeeded = Signal(object)  # dict response
    failed = Signal(str)

    def __init__(self, client, currency: str | None = None) -> None:
        super().__init__()
        self._client = client
        self._currency = currency

    def run(self) -> None:
        try:
            data = self._client.vault_balance(self._currency)
            self.succeeded.emit(data)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class VaultOpWorker(QThread):
    """Deposit/Withdraw vault di thread terpisah (butuh password + 2FA).

    `op` = "deposit" | "withdraw".
    """

    succeeded = Signal(object)  # dict response
    failed = Signal(str)

    def __init__(self, client, op: str, currency: str, amount: float,
                 password: str, two_factor_code: str = "") -> None:
        super().__init__()
        self._client = client
        self._op = op
        self._currency = currency
        self._amount = amount
        self._password = password
        self._tfa = two_factor_code

    def run(self) -> None:
        try:
            if self._op == "deposit":
                fn = self._client.vault_deposit
            elif self._op == "withdraw":
                fn = self._client.vault_withdraw
            else:
                raise ValueError(f"op tidak dikenal: {self._op}")
            data = fn(self._currency, self._amount, self._password, self._tfa)
            self.succeeded.emit(data)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
