"""VaultDialog — Deposit/Withdraw dana ke Vault Wolfbet.

Vault = brankas di akun Wolfbet untuk melindungi dana dari betting.
Operasi butuh password akun + kode Google Authenticator (2FA).

Keamanan:
- Password & 2FA hanya diketik user di sini, TIDAK disimpan.
- Ada konfirmasi eksplisit (currency, arah, jumlah) sebelum submit.
- Operasi jalan di worker thread (UI tidak beku).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bridge.workers import VaultBalanceWorker, VaultOpWorker
from widgets.theme import COLORS


def parse_vault_balance(data: object, currency: str) -> float | None:
    """Ekstrak saldo vault untuk `currency` dari response (shape belum pasti).

    Toleran terhadap beberapa bentuk umum:
      {"balances":[{"currency","amount"}]}, {"vault":[...]}, {cur: amount}.
    Return None kalau tidak ketemu.
    """
    cur = (currency or "").upper()

    def _from_list(items) -> float | None:
        for it in items or []:
            if isinstance(it, dict):
                c = str(it.get("currency", "")).upper()
                if c == cur:
                    try:
                        return float(it.get("amount", 0))
                    except (TypeError, ValueError):
                        return None
        return None

    if isinstance(data, dict):
        for key in ("balances", "vault", "vaults", "data"):
            node = data.get(key)
            if isinstance(node, list):
                v = _from_list(node)
                if v is not None:
                    return v
            if isinstance(node, dict):
                # {cur: amount} atau {cur: {amount:..}}
                for k, val in node.items():
                    if str(k).upper() == cur:
                        if isinstance(val, dict):
                            try:
                                return float(val.get("amount", 0))
                            except (TypeError, ValueError):
                                return None
                        try:
                            return float(val)
                        except (TypeError, ValueError):
                            return None
        # top-level {cur: amount}
        for k, val in data.items():
            if str(k).upper() == cur:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return None
    return None


class VaultDialog(QDialog):
    def __init__(self, client, currency: str, main_balance: float,
                 mode: str = "deposit", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._currency = (currency or "").upper()
        self._main_balance = float(main_balance or 0.0)
        self._vault_balance: float | None = None
        self._bal_worker = None
        self._op_worker = None
        self.setWindowTitle("Vault — Wolfbet")
        self.setMinimumWidth(400)
        self._build(mode)
        self._fetch_vault_balance()

    def _build(self, mode: str) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        info = QLabel(
            "Vault melindungi dana dari betting. Transfer antar saldo Main ↔ Vault "
            "(akun sendiri). Butuh password + Google Authenticator (2FA)."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {COLORS['text_dim']};")
        root.addWidget(info)

        # Ringkasan saldo
        form = QFormLayout()
        self._lbl_currency = QLabel(self._currency or "-")
        self._lbl_main = QLabel(f"{self._main_balance:.8f}")
        self._lbl_vault = QLabel("(memuat...)")
        for w in (self._lbl_main, self._lbl_vault):
            w.setStyleSheet("font-family: Consolas, monospace; font-weight: bold;")
        form.addRow("Currency", self._lbl_currency)
        form.addRow("Saldo Main", self._lbl_main)
        form.addRow("Saldo Vault", self._lbl_vault)
        root.addLayout(form)

        # Arah operasi
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Aksi:"))
        self._dir = QComboBox()
        self._dir.addItems(["Deposit ke Vault", "Withdraw dari Vault"])
        if mode == "withdraw":
            self._dir.setCurrentIndex(1)
        self._dir.currentIndexChanged.connect(self._update_max_hint)
        dir_row.addWidget(self._dir, stretch=1)
        root.addLayout(dir_row)

        # Input jumlah + Max
        amt_row = QHBoxLayout()
        self._amount = QDoubleSpinBox()
        self._amount.setDecimals(8)
        self._amount.setRange(0.0, 1_000_000_000.0)
        self._amount.setSingleStep(0.001)
        amt_row.addWidget(QLabel("Jumlah:"))
        amt_row.addWidget(self._amount, stretch=1)
        self._btn_max = QPushButton("Max")
        self._btn_max.clicked.connect(self._set_max)
        amt_row.addWidget(self._btn_max)
        root.addLayout(amt_row)

        # Password + 2FA
        cred = QFormLayout()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Password akun Wolfbet")
        self._tfa = QLineEdit()
        self._tfa.setPlaceholderText("Kode Google Authenticator (6 digit)")
        self._tfa.setMaxLength(8)
        cred.addRow("Password", self._password)
        cred.addRow("2FA Code", self._tfa)
        root.addLayout(cred)

        # Status
        self._status = QLabel("")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        # Tombol
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._btn_submit = QPushButton("Submit")
        self._btn_submit.clicked.connect(self._on_submit)
        self._btn_close = QPushButton("Tutup")
        self._btn_close.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_submit)
        btn_row.addWidget(self._btn_close)
        root.addLayout(btn_row)

    # ---- Vault balance ---------------------------------------------------

    def _fetch_vault_balance(self) -> None:
        if not hasattr(self._client, "vault_balance"):
            self._lbl_vault.setText("(tidak didukung)")
            return
        self._set_status("Memuat saldo vault...", "info")
        w = VaultBalanceWorker(self._client, self._currency)
        w.succeeded.connect(self._on_balance)
        w.failed.connect(self._on_balance_failed)
        self._bal_worker = w
        w.start()

    def _on_balance(self, data) -> None:
        val = parse_vault_balance(data, self._currency)
        self._vault_balance = val
        self._lbl_vault.setText(f"{val:.8f}" if val is not None else "0.00000000")
        self._set_status("", "info")
        self._update_max_hint()

    def _on_balance_failed(self, msg: str) -> None:
        self._lbl_vault.setText("(gagal muat)")
        self._set_status(f"Gagal ambil saldo vault: {msg}", "danger")

    # ---- Helpers ---------------------------------------------------------

    def _is_deposit(self) -> bool:
        return self._dir.currentIndex() == 0

    def _source_balance(self) -> float:
        return self._main_balance if self._is_deposit() else (self._vault_balance or 0.0)

    def _set_max(self) -> None:
        self._amount.setValue(self._source_balance())

    def _update_max_hint(self) -> None:
        src = "Main" if self._is_deposit() else "Vault"
        self._btn_max.setToolTip(f"Isi seluruh saldo {src}: {self._source_balance():.8f}")

    def _set_status(self, text: str, role: str = "info") -> None:
        color = {
            "info": COLORS["text_dim"], "danger": COLORS["danger"],
            "success": COLORS["success"], "warn": COLORS["warning"],
        }.get(role, COLORS["text_dim"])
        self._status.setStyleSheet(f"color: {color};")
        self._status.setText(text)

    # ---- Submit ----------------------------------------------------------

    def _on_submit(self) -> None:
        amount = float(self._amount.value())
        password = self._password.text()
        tfa = self._tfa.text().strip()
        deposit = self._is_deposit()
        arah = "Deposit ke Vault" if deposit else "Withdraw dari Vault"

        if amount <= 0:
            self._set_status("Jumlah harus lebih dari 0.", "warn")
            return
        if amount > self._source_balance() + 1e-12:
            self._set_status(
                f"Jumlah melebihi saldo sumber ({self._source_balance():.8f}).", "warn"
            )
            return
        if not password:
            self._set_status("Password wajib diisi.", "warn")
            return
        if not tfa:
            self._set_status("Kode 2FA (Google Authenticator) wajib diisi.", "warn")
            return

        confirm = QMessageBox.question(
            self, "Konfirmasi Vault",
            f"{arah}\n\nCurrency : {self._currency}\nJumlah   : {amount:.8f}\n\nLanjutkan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._btn_submit.setEnabled(False)
        self._set_status(f"Mengirim {arah.lower()}...", "info")
        op = "deposit" if deposit else "withdraw"
        w = VaultOpWorker(self._client, op, self._currency, amount, password, tfa)
        w.succeeded.connect(self._on_op_success)
        w.failed.connect(self._on_op_failed)
        w.finished.connect(lambda: self._btn_submit.setEnabled(True))
        self._op_worker = w
        w.start()

    def _on_op_success(self, data) -> None:
        self._set_status("Berhasil! Menyegarkan saldo vault...", "success")
        self._password.clear()
        self._tfa.clear()
        self._amount.setValue(0.0)
        self._fetch_vault_balance()

    def _on_op_failed(self, msg: str) -> None:
        self._set_status(f"Gagal: {msg}", "danger")
