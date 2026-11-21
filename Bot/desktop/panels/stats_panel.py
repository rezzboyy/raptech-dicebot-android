"""StatsPanel — panel statistik akun & sesi.

Menampilkan identitas akun (user, site, balance aktif), daftar wallet,
dan live session metrics. Mendukung live theme via `apply_theme()`.
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from corebot.models import AccountSnapshot
from widgets.panel_frame import PanelFrame
from widgets.theme import COLORS


class StatsPanel(PanelFrame):
    """Panel identitas akun + wallet + live stats (+ FIAT/IDR opsional)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Stats", parent)
        # Fitur IDR hanya aktif kalau env RAPTECH_IDR=1 (build pribadi).
        self._idr_enabled = os.getenv("RAPTECH_IDR") == "1"
        self._idr_price: float | None = None  # IDR per 1 unit currency aktif
        self._active_currency = ""
        self._captions: list[QLabel] = []       # label caption (redup)
        self._headers: list[QLabel] = []         # header section (accent)
        self._values: list[QLabel] = []          # nilai umum (text bold)
        self._wallet_rows: list[tuple[QLabel, bool]] = []  # (label, is_active)
        self._last_profit_sign = True            # untuk warna profit saat restyle
        self._build()

    # ---- Style helpers (dipakai di build & apply_theme) ------------------

    def _style_caption(self, w: QLabel) -> None:
        w.setStyleSheet(f"color: {COLORS['text_dim']};")

    def _style_value(self, w: QLabel) -> None:
        w.setStyleSheet(f"color: {COLORS['text']}; font-weight: bold;")

    def _style_header(self, w: QLabel) -> None:
        w.setStyleSheet(
            f"color: {COLORS['accent']}; font-weight: bold; "
            f"padding-top: 6px; border-top: 1px solid {COLORS['border']};"
        )

    def _style_mono_value(self, w: QLabel) -> None:
        w.setStyleSheet(
            f"color: {COLORS['text']}; font-weight: bold; font-family: Consolas, monospace;"
        )

    def _style_fiat(self, w: QLabel) -> None:
        """FIAT (IDR) ditonjolkan: badge kecil + font sedikit lebih besar."""
        w.setStyleSheet(
            f"color: {COLORS['warning']}; font-weight: bold; font-size: 14px; "
            f"padding: 2px 6px; border: 1px solid {COLORS['warning']}; border-radius: 4px;"
        )

    def _build(self) -> None:
        # --- Identity grid ---
        ident = QWidget()
        grid = QGridLayout(ident)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setVerticalSpacing(4)
        grid.setHorizontalSpacing(8)

        def _lbl(text: str) -> QLabel:
            w = QLabel(text)
            self._style_caption(w)
            self._captions.append(w)
            return w

        def _val() -> QLabel:
            w = QLabel("-")
            self._style_value(w)
            self._values.append(w)
            return w

        self._v_user = _val()
        self._v_site = _val()
        self._v_balance = _val()
        self._v_balance.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")

        self._v_fiat = _val()
        self._style_fiat(self._v_fiat)

        grid.addWidget(_lbl("User"), 0, 0)
        grid.addWidget(self._v_user, 0, 1)
        grid.addWidget(_lbl("Site"), 1, 0)
        grid.addWidget(self._v_site, 1, 1)
        grid.addWidget(_lbl("Balance"), 2, 0)
        grid.addWidget(self._v_balance, 2, 1)
        # FIAT row — hanya ditampilkan kalau IDR enabled
        self._lbl_fiat = _lbl("FIAT")
        grid.addWidget(self._lbl_fiat, 3, 0)
        grid.addWidget(self._v_fiat, 3, 1)
        self._lbl_fiat.setVisible(self._idr_enabled)
        self._v_fiat.setVisible(self._idr_enabled)
        grid.setColumnStretch(1, 1)
        self.content_layout.addWidget(ident)

        # --- Wallet header ---
        wallet_hdr = QLabel("WALLETS")
        self._style_header(wallet_hdr)
        self._headers.append(wallet_hdr)
        self.content_layout.addWidget(wallet_hdr)

        # --- Wallet list container ---
        self._wallet_box = QWidget()
        self._wallet_layout = QVBoxLayout(self._wallet_box)
        self._wallet_layout.setContentsMargins(0, 0, 0, 0)
        self._wallet_layout.setSpacing(2)
        self.content_layout.addWidget(self._wallet_box)

        self._wallet_empty = QLabel("(belum connect)")
        self._wallet_empty.setStyleSheet(f"color: {COLORS['text_dim']}; font-style: italic;")
        self._wallet_layout.addWidget(self._wallet_empty)

        # --- Live session metrics ---
        session_hdr = QLabel("SESSION")
        self._style_header(session_hdr)
        self._headers.append(session_hdr)
        self.content_layout.addWidget(session_hdr)

        sess = QWidget()
        sgrid = QGridLayout(sess)
        sgrid.setContentsMargins(0, 0, 0, 0)
        sgrid.setVerticalSpacing(3)
        sgrid.setHorizontalSpacing(8)

        def _mk(label_text: str, row: int, col: int = 0):
            lbl = QLabel(label_text)
            self._style_caption(lbl)
            self._captions.append(lbl)
            val = QLabel("-")
            self._style_mono_value(val)
            sgrid.addWidget(lbl, row, col * 2)
            sgrid.addWidget(val, row, col * 2 + 1)
            return val

        self._s_profit = _mk("Profit", 0, 0)
        self._s_pct = _mk("Profit %", 1, 0)
        self._s_cur_balance = _mk("Balance", 2, 0)
        self._s_bets = _mk("Cycles", 3, 0)
        self._s_wins = _mk("Wins", 4, 0)
        self._s_losses = _mk("Losses", 5, 0)
        self._s_streak = _mk("Max neg", 6, 0)
        self._s_speed = _mk("Speed", 7, 0)
        self._s_wagered = _mk("Volume", 8, 0)
        sgrid.setColumnStretch(1, 1)
        self.content_layout.addWidget(sess)

        self.content_layout.addStretch(1)

    # ---- Theming ---------------------------------------------------------

    def apply_theme(self) -> None:
        super().apply_theme()
        # Guard: dipanggil dari PanelFrame.__init__ sebelum _build selesai.
        if not hasattr(self, "_captions"):
            return
        for w in self._captions:
            self._style_caption(w)
        for w in self._headers:
            self._style_header(w)
        for w in self._values:
            self._style_value(w)
        # Warna khusus
        self._v_balance.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
        self._style_fiat(self._v_fiat)
        # _wallet_empty bisa sudah terhapus setelah connect → guard.
        if getattr(self, "_wallet_empty", None) is not None:
            try:
                self._wallet_empty.setStyleSheet(
                    f"color: {COLORS['text_dim']}; font-style: italic;"
                )
            except RuntimeError:
                self._wallet_empty = None
        # Session mono values
        for w in (
            self._s_pct, self._s_cur_balance, self._s_bets, self._s_wins,
            self._s_losses, self._s_streak, self._s_speed, self._s_wagered,
        ):
            self._style_mono_value(w)
        # Profit dengan warna sesuai sign terakhir
        self._restyle_profit()
        # Wallet rows
        for row, is_active in self._wallet_rows:
            color = COLORS["accent"] if is_active else COLORS["text"]
            weight = "bold" if is_active else "normal"
            row.setStyleSheet(
                f"color: {color}; font-weight: {weight}; font-family: Consolas, monospace;"
            )

    def _restyle_profit(self) -> None:
        color = COLORS["success"] if self._last_profit_sign else COLORS["danger"]
        self._s_profit.setStyleSheet(
            f"color: {color}; font-weight: bold; font-family: Consolas, monospace;"
        )

    # ---- Data updates ----------------------------------------------------

    def reset_session(self) -> None:
        """Kosongkan tampilan live session metrics ke '-'."""
        for w in (
            self._s_profit, self._s_pct, self._s_cur_balance, self._s_bets,
            self._s_wins, self._s_losses, self._s_streak, self._s_speed,
            self._s_wagered,
        ):
            w.setText("-")

    def update_snapshot(self, snap) -> None:
        """Update live session metrics dari SessionSnapshot."""
        self._last_profit_sign = snap.session_profit >= 0
        self._s_profit.setText(f"{snap.session_profit:+.8f}")
        self._restyle_profit()
        # Profit + IDR estimasi (kalau enabled)
        idr_profit = self._fmt_idr(snap.session_profit, sign=True)
        if idr_profit:
            self._s_profit.setText(f"{snap.session_profit:+.8f}  ≈ {idr_profit}")
        self._s_pct.setText(f"{snap.profit_pct:+.4f}%")
        self._s_cur_balance.setText(f"{snap.current_balance:.8f}")
        # Update FIAT balance live
        self._last_balance = snap.current_balance
        self._refresh_fiat_balance()
        self._s_bets.setText(f"{snap.session_bets:,}")
        self._s_wins.setText(f"{snap.session_wins:,}")
        self._s_losses.setText(f"{snap.session_losses:,}")
        self._s_streak.setText(f"{snap.max_lose_streak}")
        self._s_speed.setText(f"{snap.speed_bps:.2f} b/s")
        self._s_wagered.setText(f"{snap.session_wagered:.8f}")

    def _clear_wallets(self) -> None:
        while self._wallet_layout.count():
            item = self._wallet_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._wallet_rows = []
        # Placeholder "(belum connect)" ikut terhapus di atas → jangan biarkan
        # referensi menggantung (apply_theme akan crash pada objek terhapus).
        self._wallet_empty = None

    def set_idr_price(self, currency: str, price: float | None) -> None:
        """Set harga IDR per 1 unit currency aktif (dari main window)."""
        self._active_currency = (currency or "").upper()
        self._idr_price = price
        self._refresh_fiat_balance()

    def _fmt_idr(self, amount: float, *, sign: bool = False) -> str:
        """Format nilai crypto → 'Rp ...' pakai helper corebot."""
        if not self._idr_enabled or self._idr_price is None:
            return ""
        try:
            from corebot.pricing import format_idr

            return format_idr(float(amount) * self._idr_price, sign=sign)
        except Exception:
            return ""

    def _refresh_fiat_balance(self) -> None:
        if not self._idr_enabled:
            return
        try:
            bal = float(self._last_balance)
        except (AttributeError, TypeError, ValueError):
            return
        txt = self._fmt_idr(bal)
        self._v_fiat.setText(txt or "-")

    def update_account(self, account: AccountSnapshot, site: str = "") -> None:
        """Refresh tampilan dengan data akun baru."""
        self._v_user.setText(account.username or "-")
        self._v_site.setText(site or "-")
        active_cur = (account.currency or "").upper()
        self._last_balance = account.balance
        self._v_balance.setText(
            f"{account.balance:.8f} {active_cur}".strip() if active_cur else "-"
        )
        self._refresh_fiat_balance()

        self._clear_wallets()
        # Filter: tampilkan hanya saldo > 0 (kecuali active coin selalu tampil).
        wallets = [(c, a) for c, a in account.balance_list if a and a > 0]
        if active_cur and not any(c.upper() == active_cur for c, _ in wallets):
            for c, a in account.balance_list:
                if c.upper() == active_cur:
                    wallets.insert(0, (c, a))
                    break

        if not wallets:
            empty = QLabel("(tidak ada saldo)")
            empty.setStyleSheet(f"color: {COLORS['text_dim']}; font-style: italic;")
            self._wallet_layout.addWidget(empty)
            self._wallet_rows.append((empty, False))
            return

        for cur, amt in wallets:
            is_active = cur.upper() == active_cur
            row = QLabel(f"{cur.upper():<6}  {amt:.8f}")
            color = COLORS["accent"] if is_active else COLORS["text"]
            weight = "bold" if is_active else "normal"
            row.setStyleSheet(
                f"color: {color}; font-weight: {weight}; font-family: Consolas, monospace;"
            )
            self._wallet_layout.addWidget(row)
            self._wallet_rows.append((row, is_active))
