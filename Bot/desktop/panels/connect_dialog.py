"""ConnectDialog — pilih site + input kredensial yang ADAPTIF per site.

Tiap site punya cara input berbeda:
    - betfury : dua field (Token + UID) → digabung 'token;uid=xxx'
    - cookie  : satu field Cookie Header (dogepick, tronpick)
    - jwt     : satu field Auth Token (nuts, pasino)
    - webapi  : satu field Web API (stake, wolfbet, dll)
    - none    : testmode, tanpa kredensial

Token tersimpan (JSON storage) di-prefill otomatis.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from bridge.connection import (
    build_betfury_token,
    credential_info,
    list_sites,
    parse_betfury_token,
    site_requires_token,
)
from widgets.theme import COLORS


class ConnectDialog(QDialog):
    """Dialog modal: pilih site + input kredensial adaptif."""

    def __init__(self, current_site: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Site & Connect")
        self.setMinimumWidth(460)
        self._sites = list_sites()
        self._build(current_site)

    def _build(self, current_site: str) -> None:
        self._form = QFormLayout(self)

        # Dropdown site
        self._combo = QComboBox()
        for slug, name in self._sites:
            self._combo.addItem(f"{name}  ({slug})", userData=slug)
        if current_site:
            idx = self._combo.findData(current_site)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
        self._form.addRow("Site:", self._combo)

        # Field kredensial utama
        self._token = QLineEdit()
        self._token_row_label = QLabel("Token:")
        self._form.addRow(self._token_row_label, self._token)

        # Field UID (khusus betfury) — disembunyikan untuk site lain
        self._uid = QLineEdit()
        self._uid.setPlaceholderText("Paste UID (key 'uid')")
        self._uid_row_label = QLabel("UID:")
        self._form.addRow(self._uid_row_label, self._uid)

        # Hint
        self._hint = QLabel("")
        self._hint.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        self._hint.setWordWrap(True)
        self._form.addRow("", self._hint)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Connect")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._form.addRow(buttons)

        self._combo.currentIndexChanged.connect(self._on_site_changed)
        self._on_site_changed()

    def _set_uid_visible(self, visible: bool) -> None:
        self._uid.setVisible(visible)
        self._uid_row_label.setVisible(visible)

    def _prefill(self, slug: str, kind: str) -> None:
        """Isi field dari token tersimpan (JSON storage)."""
        try:
            from corebot.storage import get_token_for

            saved = get_token_for(slug)
        except Exception:
            saved = None

        if not saved:
            self._token.clear()
            self._uid.clear()
            return

        saved = str(saved)
        if kind == "betfury":
            token, uid = parse_betfury_token(saved)
            self._token.setText(token)
            self._uid.setText(uid)
        else:
            self._token.setText(saved)

    def _on_site_changed(self) -> None:
        slug = self.result_site()
        info = credential_info(slug)
        kind = info["kind"]
        needs_token = site_requires_token(slug)

        # Label & visibility
        self._token_row_label.setText(
            "Token:" if kind == "betfury" else f"{info['label']}:"
        )
        self._set_uid_visible(kind == "betfury")
        self._token.setEnabled(needs_token)
        self._uid.setEnabled(kind == "betfury")

        # Placeholder
        placeholders = {
            "betfury": "Paste TOKEN (key 'token')",
            "cookie": "Paste cookie header",
            "jwt": "Paste auth token",
            "webapi": "Paste Web API / token",
            "none": "(tidak perlu — simulator lokal)",
        }
        self._token.setPlaceholderText(placeholders.get(kind, "Paste token"))
        self._hint.setText(info["hint"])

        if needs_token:
            self._prefill(slug, kind)
        else:
            self._token.clear()
            self._uid.clear()

    # ---- Result accessors ------------------------------------------------

    def result_site(self) -> str:
        return str(self._combo.currentData() or "")

    def result_token(self) -> str:
        """Return kredensial final (untuk betfury digabung token;uid=xxx)."""
        info = credential_info(self.result_site())
        if info["kind"] == "betfury":
            token = self._token.text().strip()
            uid = self._uid.text().strip()
            if not token or not uid:
                return ""
            return build_betfury_token(token, uid)
        return self._token.text().strip()
