"""MainWindow — jendela utama Raptech Dicebot (menu, panel, sesi, tema)."""
from __future__ import annotations

import re

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QColorDialog,
    QLabel,
    QMainWindow,
    QMenuBar,
    QSplitter,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from panels.bets_table import BetsPanel
from panels.chart_panel import ChartPanel
from panels.code_editor import CodeEditorPanel
from panels.control_panel import ControlPanel
from panels.stats_panel import StatsPanel
from panels.toolbar import SessionToolbar
from widgets.icons import get_icon, icon_size
from widgets.theme import (
    APP_NAME,
    APP_VERSION,
    build_stylesheet,
    engine_version,
    get_active_theme,
    register_theme_listener,
    toggle_theme,
)


class MainWindow(QMainWindow):
    """Jendela utama aplikasi."""

    def __init__(self) -> None:
        super().__init__()
        self._base_title = f"{APP_NAME} v{APP_VERSION}"
        self.setWindowTitle(self._base_title)
        self.resize(1280, 720)
        # State koneksi
        self._client = None
        self._account = None
        self._site = ""
        self._bridge = None
        self._prev_session_profit = 0.0
        self._connect_worker = None
        self._refresh_worker = None
        self._pending_site = ""
        self._pending_token = ""
        # Advanced strategy settings (dimuat dari storage kalau ada)
        from panels.settings_dialog import DEFAULTS as _ADV_DEFAULTS

        self._advanced = dict(_ADV_DEFAULTS)
        # Alert & status-bar state
        self._alerts_enabled = False
        self._last_alert_streak = 0
        self._load_advanced_settings()
        self._load_alerts_setting()
        self._build_menu_bar()
        self._build_central_layout()
        self._build_status_bar()
        self._wire_toolbar()
        self._wire_control()
        self._install_shortcuts()
        self._load_default_strategy()
        # Reapply QSS global tiap tema berganti (panel restyle sendiri via
        # listener masing-masing).
        register_theme_listener(self._apply_global_stylesheet)
        # Pulihkan ukuran window + posisi splitter dari sesi sebelumnya.
        self._restore_layout()

    # ---- Menu bar --------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menubar: QMenuBar = self.menuBar()

        # File
        file_menu = menubar.addMenu("File")
        self._act_open = QAction(get_icon("folder-open"), "Open Strategy...", self)
        self._act_save = QAction(get_icon("save"), "Save Strategy...", self)
        self._act_open.triggered.connect(lambda: self.editor_panel.open_file())
        self._act_save.triggered.connect(lambda: self.editor_panel.save_file())
        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(self._act_open)
        file_menu.addAction(self._act_save)
        file_menu.addSeparator()
        file_menu.addAction(act_exit)

        # View — Toggle Chart + Theme + Font + Accent
        view_menu = menubar.addMenu("View")
        self._act_toggle_chart = QAction(get_icon("chart"), "Toggle Chart", self)
        self._act_toggle_chart.triggered.connect(self._toggle_chart_action)
        view_menu.addAction(self._act_toggle_chart)
        self._act_theme = QAction("Toggle Light/Dark Theme", self)
        self._act_theme.triggered.connect(self._toggle_theme)
        view_menu.addAction(self._act_theme)
        self._build_theme_menus(view_menu)

        # Site — Select Site & Connect
        site_menu = menubar.addMenu("Site")
        self._act_connect = QAction(get_icon("plug"), "Select Site && Connect...", self)
        self._act_connect.triggered.connect(self._open_connect_dialog)
        site_menu.addAction(self._act_connect)
        self._act_refresh = QAction(get_icon("refresh"), "Refresh Balance", self)
        self._act_refresh.triggered.connect(self._refresh_balance)
        site_menu.addAction(self._act_refresh)

        # Game
        game_menu = menubar.addMenu("Game")
        game_menu.addAction(QAction(get_icon("dice"), "Dice", self))

        # Settings
        settings_menu = menubar.addMenu("Settings")
        self._act_advanced = QAction(get_icon("settings"), "Advanced Strategies...", self)
        self._act_advanced.triggered.connect(self._open_advanced_settings)
        settings_menu.addAction(self._act_advanced)
        settings_menu.addSeparator()
        self._act_alerts = QAction("Sound Alerts", self)
        self._act_alerts.setCheckable(True)
        self._act_alerts.setChecked(self._alerts_enabled)
        self._act_alerts.toggled.connect(self._on_toggle_alerts)
        settings_menu.addAction(self._act_alerts)

        # Help
        help_menu = menubar.addMenu("Help")
        act_about = QAction("About", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

        # Telegram — coming soon (disabled)
        tele_action = QAction("Telegram", self)
        tele_action.setEnabled(False)
        tele_action.setToolTip("Coming soon")
        menubar.addAction(tele_action)

        # --- Tombol toggle tema (SVG sun/moon) di pojok kanan menu bar ---
        self._theme_btn = QToolButton(self)
        self._theme_btn.setIconSize(icon_size(20))
        self._theme_btn.setAutoRaise(True)
        self._theme_btn.clicked.connect(self._toggle_theme)
        self._update_theme_button()
        menubar.setCornerWidget(self._theme_btn, Qt.Corner.TopRightCorner)

    # ---- Central layout (3 area) ----------------------------------------

    def _build_central_layout(self) -> None:
        """Rakit layout utama:

            ┌─────────┬──────────────────┬──────────┐
            │ LEFT    │ CENTER           │ RIGHT    │
            │ Stats   │ Chart (atas)     │ Code     │
            │ Control │ Bets tbl (bawah) │ Editor   │
            └─────────┴──────────────────┴──────────┘

        Semua pakai QSplitter supaya resizable. Fase 2 masih placeholder.
        """
        # --- LEFT: stats + control (vertikal) ---
        self.stats_panel = StatsPanel()
        self.control_panel = ControlPanel()

        self._left_split = QSplitter(Qt.Orientation.Vertical)
        self._left_split.addWidget(self.stats_panel)
        self._left_split.addWidget(self.control_panel)
        self._left_split.setSizes([420, 260])

        # --- CENTER: chart + bets table (vertikal) ---
        self.chart_panel = ChartPanel()
        self.bets_panel = BetsPanel()

        self._center_split = QSplitter(Qt.Orientation.Vertical)
        self._center_split.addWidget(self.chart_panel)
        self._center_split.addWidget(self.bets_panel)
        self._center_split.setSizes([360, 320])

        # --- RIGHT: code editor ---
        self.editor_panel = CodeEditorPanel()

        # --- Gabung horizontal ---
        self._main_split = QSplitter(Qt.Orientation.Horizontal)
        self._main_split.addWidget(self._left_split)
        self._main_split.addWidget(self._center_split)
        self._main_split.addWidget(self.editor_panel)
        self._main_split.setSizes([300, 560, 420])
        self._main_split.setStretchFactor(0, 0)
        self._main_split.setStretchFactor(1, 1)
        self._main_split.setStretchFactor(2, 0)

        # --- Bottom: session toolbar (Start/Stop/Pause + pilihan) ---
        self.toolbar = SessionToolbar()

        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)
        vbox.addWidget(self._main_split, stretch=1)
        vbox.addWidget(self.toolbar)
        self.setCentralWidget(container)

    # ---- Status bar ------------------------------------------------------

    def _build_status_bar(self) -> None:
        status: QStatusBar = self.statusBar()
        status.showMessage("Ready")

        # Indikator permanen di kanan: State · Elapsed · Speed · Bets · Profit
        def _ind(initial: str = "-") -> QLabel:
            lbl = QLabel(initial)
            lbl.setContentsMargins(8, 0, 8, 0)
            return lbl

        self._sb_state = _ind("idle")
        self._sb_elapsed = _ind("00:00:00")
        self._sb_speed = _ind("0.00 b/s")
        self._sb_bets = _ind("0 bets")
        self._sb_profit = _ind("+0.00000000")
        # Separator visual sederhana antar indikator
        for w in (self._sb_state, self._sb_elapsed, self._sb_speed, self._sb_bets, self._sb_profit):
            status.addPermanentWidget(self._sb_sep())
            status.addPermanentWidget(w)

    def _sb_sep(self) -> QLabel:
        sep = QLabel("|")
        sep.setEnabled(False)
        return sep

    @staticmethod
    def _fmt_elapsed(seconds: float) -> str:
        s = int(max(0, seconds))
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    # ---- Theme -----------------------------------------------------------

    def _toggle_theme(self) -> None:
        """Ganti tema light <-> dark secara live (tersimpan otomatis)."""
        new = toggle_theme()  # mutasi COLORS + notify listener + persist
        self._update_theme_button()
        self._refresh_menu_icons()
        self._sync_theme_checks()
        self.statusBar().showMessage(f"Tema: {new.capitalize()}")

    def _apply_global_stylesheet(self) -> None:
        """Listener tema: pasang ulang QSS global ke aplikasi."""
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet())

    # ---- Theme presets / font / accent (Paket D) ------------------------

    def _build_theme_menus(self, view_menu) -> None:
        from widgets.theme import (
            DEFAULT_FONT_SCALE,
            available_themes,
            get_active_theme,
            get_font_scale,
        )

        view_menu.addSeparator()

        # Submenu Theme (semua preset, radio)
        theme_menu = view_menu.addMenu("Theme")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_actions = {}
        for name in available_themes():
            act = QAction(name.replace("-", " ").title(), self, checkable=True)
            act.setChecked(name == get_active_theme())
            act.triggered.connect(lambda _=False, n=name: self._set_theme(n))
            self._theme_group.addAction(act)
            theme_menu.addAction(act)
            self._theme_actions[name] = act

        # Submenu Font Size
        font_menu = view_menu.addMenu("Font Size")
        self._font_group = QActionGroup(self)
        self._font_group.setExclusive(True)
        self._font_actions = {}
        for label, title in (("S", "Small"), ("M", "Medium"), ("L", "Large")):
            act = QAction(title, self, checkable=True)
            act.setChecked(label == get_font_scale())
            act.triggered.connect(lambda _=False, ln=label: self._set_font(ln))
            self._font_group.addAction(act)
            font_menu.addAction(act)
            self._font_actions[label] = act

        # Accent
        view_menu.addSeparator()
        act_accent = QAction("Custom Accent Color...", self)
        act_accent.triggered.connect(self._pick_accent)
        view_menu.addAction(act_accent)
        act_accent_reset = QAction("Reset Accent", self)
        act_accent_reset.triggered.connect(self._reset_accent)
        view_menu.addAction(act_accent_reset)

    def _set_theme(self, name: str) -> None:
        from widgets.theme import set_active_theme

        set_active_theme(name)
        self._sync_theme_checks()
        self._update_theme_button()
        self._refresh_menu_icons()
        self.statusBar().showMessage(f"Tema: {name.replace('-', ' ').title()}")

    def _sync_theme_checks(self) -> None:
        from widgets.theme import get_active_theme

        active = get_active_theme()
        for name, act in getattr(self, "_theme_actions", {}).items():
            act.setChecked(name == active)

    def _set_font(self, label: str) -> None:
        from widgets.theme import set_font_scale

        set_font_scale(label)  # notify → _apply_global_stylesheet reapply QSS
        self.statusBar().showMessage(f"Ukuran font: {label}")

    def _pick_accent(self) -> None:
        from PySide6.QtGui import QColor

        from widgets.theme import COLORS, get_accent, set_accent

        current = QColor(get_accent() or COLORS.get("accent", "#0969da"))
        color = QColorDialog.getColor(current, self, "Pilih Warna Accent")
        if color.isValid():
            set_accent(color.name())  # live-apply + persist
            self._refresh_menu_icons()
            self.statusBar().showMessage(f"Accent: {color.name()}")

    def _reset_accent(self) -> None:
        from widgets.theme import set_accent

        set_accent(None)
        self._refresh_menu_icons()
        self.statusBar().showMessage("Accent dikembalikan ke default tema.")

    def _update_theme_button(self) -> None:
        """Icon tombol toggle: matahari saat dark (klik→terang),
        bulan saat light (klik→gelap)."""
        if not hasattr(self, "_theme_btn"):
            return
        if get_active_theme() == "light":
            self._theme_btn.setIcon(get_icon("moon", size=20))
            self._theme_btn.setToolTip("Beralih ke tema Dark")
        else:
            self._theme_btn.setIcon(get_icon("sun", size=20))
            self._theme_btn.setToolTip("Beralih ke tema Light")

    def _refresh_menu_icons(self) -> None:
        """Re-tint icon action menu setelah ganti tema."""
        pairs = [
            ("_act_open", "folder-open"),
            ("_act_save", "save"),
            ("_act_toggle_chart", "chart"),
            ("_act_connect", "plug"),
            ("_act_refresh", "refresh"),
            ("_act_advanced", "settings"),
        ]
        for attr, name in pairs:
            act = getattr(self, attr, None)
            if act is not None:
                act.setIcon(get_icon(name))

    def _toggle_chart_action(self) -> None:
        """Toggle visibilitas chart dari menu View."""
        self.chart_panel.setVisible(not self.chart_panel.isVisible())

    # ---- Keyboard shortcuts (P9) ----------------------------------------

    def _install_shortcuts(self) -> None:
        """Pasang shortcut keyboard. Menu action pakai setShortcut, kontrol
        engine pakai QShortcut global."""
        # Menu actions
        self._act_open.setShortcut(QKeySequence.StandardKey.Open)      # Ctrl+O
        self._act_save.setShortcut(QKeySequence.StandardKey.Save)      # Ctrl+S
        self._act_refresh.setShortcut(QKeySequence("Ctrl+R"))
        self._act_connect.setShortcut(QKeySequence("Ctrl+K"))
        self._act_toggle_chart.setShortcut(QKeySequence("Ctrl+H"))
        self._act_theme.setShortcut(QKeySequence("Ctrl+D"))

        # Kontrol engine (global shortcut)
        def _sc(seq: str, fn) -> None:
            s = QShortcut(QKeySequence(seq), self)
            s.activated.connect(fn)

        _sc("F5", self.toolbar.request_start)
        _sc("F6", self.toolbar.request_pause_or_resume)
        _sc("F7", self.toolbar.request_stop)
        _sc("F8", self.editor_panel.check_script)
        _sc("Ctrl+F", self.editor_panel.toggle_find)

    # ---- Alerts (P8) -----------------------------------------------------

    def _on_toggle_alerts(self, enabled: bool) -> None:
        self._alerts_enabled = bool(enabled)
        self._save_alerts_setting()
        self.statusBar().showMessage(
            "Sound alerts: " + ("ON" if enabled else "OFF")
        )

    def _beep_alert(self, reason: str = "") -> None:
        if not self._alerts_enabled:
            return
        from PySide6.QtWidgets import QApplication

        QApplication.beep()
        if reason:
            self._console("info", f"[alert] {reason}")

    def _maybe_streak_alert(self, streak: int, threshold: int = 20) -> None:
        """Bunyi sekali tiap kali lose-streak menembus kelipatan threshold."""
        if streak < threshold:
            return
        milestone = (streak // threshold) * threshold
        if milestone > self._last_alert_streak:
            self._last_alert_streak = milestone
            self._beep_alert(f"Lose-streak {streak}")

    def _load_alerts_setting(self) -> None:
        try:
            from corebot.storage import load_settings_store

            store = load_settings_store()
            val = store.get("ui", {}).get("desktop_alerts")
            if isinstance(val, bool):
                self._alerts_enabled = val
        except Exception:
            pass

    def _save_alerts_setting(self) -> None:
        try:
            from corebot.storage import load_settings_store, save_settings_store

            store = load_settings_store()
            store.setdefault("ui", {})["desktop_alerts"] = bool(self._alerts_enabled)
            save_settings_store(store)
        except Exception:
            pass

    # ---- Layout persistence (P1) ----------------------------------------

    def _restore_layout(self) -> None:
        """Pulihkan geometry window + posisi splitter dari storage."""
        try:
            from corebot.storage import load_settings_store

            layout = load_settings_store().get("ui", {}).get("desktop_layout")
        except Exception:
            layout = None
        if not isinstance(layout, dict):
            return

        def _restore(widget, key: str, method: str) -> None:
            b64 = layout.get(key)
            if isinstance(b64, str) and b64:
                data = QByteArray.fromBase64(b64.encode("ascii"))
                getattr(widget, method)(data)

        _restore(self, "window", "restoreGeometry")
        _restore(self._main_split, "main_split", "restoreState")
        _restore(self._left_split, "left_split", "restoreState")
        _restore(self._center_split, "center_split", "restoreState")

    def _save_layout(self) -> None:
        """Simpan geometry window + posisi splitter ke storage."""
        def _b64(qba: QByteArray) -> str:
            return bytes(qba.toBase64()).decode("ascii")

        try:
            from corebot.storage import load_settings_store, save_settings_store

            store = load_settings_store()
            store.setdefault("ui", {})["desktop_layout"] = {
                "window": _b64(self.saveGeometry()),
                "main_split": _b64(self._main_split.saveState()),
                "left_split": _b64(self._left_split.saveState()),
                "center_split": _b64(self._center_split.saveState()),
            }
            save_settings_store(store)
        except Exception:
            pass

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._save_layout()
        super().closeEvent(event)

    # ---- Actions ---------------------------------------------------------

    def _show_about(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"{APP_NAME}\n"
            f"Versi aplikasi : v{APP_VERSION}\n"
            f"Engine (corebot): v{engine_version()}\n\n"
            "Desktop GUI untuk Raptech Terminal Core.\n"
            "Reuse engine Python (corebot) — UI dengan PySide6.",
        )

    # ---- Connection ------------------------------------------------------

    def _open_connect_dialog(self) -> None:
        from PySide6.QtWidgets import QDialog, QMessageBox

        from panels.connect_dialog import ConnectDialog

        dialog = ConnectDialog(current_site=self._site, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        site = dialog.result_site()
        token = dialog.result_token()
        if not site:
            return

        self._connect(site, token)

    # ---- Console helpers -------------------------------------------------

    def _console(self, level: str, message: str, *, show_tab: bool = False) -> None:
        """Tulis pesan ke Console tab + status bar singkat."""
        self.editor_panel.append_console(f"[{level}] {message}")
        if show_tab:
            self.editor_panel.show_console_tab()

    # ---- Advanced settings ----------------------------------------------

    def _open_advanced_settings(self) -> None:
        from PySide6.QtWidgets import QDialog

        from panels.settings_dialog import AdvancedSettingsDialog

        dialog = AdvancedSettingsDialog(current=self._advanced, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._advanced = dialog.result_state()
            self._save_advanced_settings()
            self._console("info", "Advanced strategies tersimpan.")

    def _load_advanced_settings(self) -> None:
        """Muat advanced settings dari settings store corebot.

        Disimpan di bawah key 'ui' karena save_settings_store() hanya
        mempertahankan key profiles/ui/proxies (key top-level lain di-drop).
        """
        try:
            from corebot.storage import load_settings_store

            store = load_settings_store()
            saved = store.get("ui", {}).get("desktop_advanced")
            if isinstance(saved, dict):
                self._advanced.update({k: v for k, v in saved.items() if k in self._advanced})
        except Exception:
            pass

    def _save_advanced_settings(self) -> None:
        try:
            from corebot.storage import load_settings_store, save_settings_store

            store = load_settings_store()
            store.setdefault("ui", {})["desktop_advanced"] = dict(self._advanced)
            save_settings_store(store)
        except Exception as exc:
            self._console("warn", f"Gagal simpan advanced settings: {exc}")

    def _connect(self, site: str, token: str) -> None:
        """Connect ASINKRON (worker thread) supaya UI tidak beku.

        Semua status & error dikirim ke Console tab.
        """
        from bridge.connection import site_requires_token
        from bridge.workers import ConnectWorker

        if site_requires_token(site) and not token:
            self._console("error", "Token kosong — situs ini butuh token untuk connect.", show_tab=True)
            self.statusBar().showMessage("Token kosong.")
            return

        # Cegah double-connect saat worker masih jalan
        if getattr(self, "_connect_worker", None) is not None and self._connect_worker.isRunning():
            self._console("warn", "Koneksi sebelumnya masih berjalan, tunggu dulu...")
            return

        self._pending_site = site
        self._pending_token = token
        self.editor_panel.show_console_tab()
        self._console("info", f"Connecting to {site}... (timeout maks 30 detik)")
        self.statusBar().showMessage(f"Connecting to {site}... (mohon tunggu)")

        worker = ConnectWorker(site, token)
        worker.succeeded.connect(self._on_connect_success)
        worker.failed.connect(self._on_connect_failed)
        worker.finished.connect(self._on_connect_finished)
        self._connect_worker = worker
        worker.start()

    def _on_connect_success(self, client, account) -> None:
        site = getattr(self, "_pending_site", "")
        self._client = client
        self._account = account
        self._site = site

        from bridge.engine_bridge import EngineBridge

        self._bridge = EngineBridge(client)
        self._wire_bridge()

        # Simpan token ke storage JSON supaya tidak perlu paste ulang.
        token = getattr(self, "_pending_token", "")
        if token:
            try:
                from bridge.connection import site_requires_token
                from corebot.storage import set_token_for

                if site_requires_token(site):
                    set_token_for(site, token)
                    self._console("info", f"API token untuk {site} tersimpan.")
            except Exception as exc:
                self._console("warn", f"Gagal simpan token: {exc}")

        self.stats_panel.update_account(account, site=site)
        self._populate_toolbar_currencies()
        self._refresh_idr_price(account.currency or "")
        # Aktifkan tombol Vault hanya untuk site yang mendukung (mis. Wolfbet).
        self.control_panel.set_vault_enabled(hasattr(client, "vault_deposit"))
        user = account.username or "-"
        self.setWindowTitle(f"{self._base_title} — {user} @ {site}")
        msg = f"Connected: {user} @ {site} | {account.balance:.8f} {account.currency or ''}".strip()
        self.statusBar().showMessage(msg)
        self._console("success", msg)

    def _on_connect_failed(self, message: str) -> None:
        site = getattr(self, "_pending_site", "")
        self.statusBar().showMessage("Connect gagal — lihat Console.")
        self._console("error", f"Gagal connect ke {site}: {message}", show_tab=True)
        self._console("info", "Tips: cek token benar, atau coba Set Proxy kalau situs geo-blocked.")

    def _on_connect_finished(self) -> None:
        self._connect_worker = None

    def _refresh_balance(self) -> None:
        """Refresh balance ASINKRON (worker thread)."""
        from bridge.workers import RefreshWorker

        if self._client is None:
            self._console("warn", "Belum connect. Connect ke site dulu (menu Site).", show_tab=True)
            return
        if getattr(self, "_refresh_worker", None) is not None and self._refresh_worker.isRunning():
            self._console("warn", "Refresh sebelumnya masih berjalan...")
            return

        self.statusBar().showMessage("Refreshing balance...")
        self._console("info", "Refreshing balance...")
        worker = RefreshWorker(
            self._client, self._account,
            self._account.currency if self._account else None,
        )
        worker.succeeded.connect(self._on_refresh_success)
        worker.failed.connect(self._on_refresh_failed)
        worker.finished.connect(lambda: setattr(self, "_refresh_worker", None))
        self._refresh_worker = worker
        worker.start()

    def _on_refresh_success(self, account) -> None:
        self._account = account
        self.stats_panel.update_account(account, site=self._site)
        self._populate_toolbar_currencies()
        msg = f"Balance refreshed: {account.balance:.8f} {account.currency or ''}".strip()
        self.statusBar().showMessage(msg)
        self._console("success", msg)

    def _on_refresh_failed(self, message: str) -> None:
        self.statusBar().showMessage("Refresh gagal — lihat Console.")
        self._console("error", f"Gagal refresh balance: {message}", show_tab=True)

    # ---- Session control -------------------------------------------------

    def _wire_toolbar(self) -> None:
        """Sambung sinyal toolbar ke handler."""
        self.toolbar.start_requested.connect(self._start_session)
        self.toolbar.pause_requested.connect(self._pause_session)
        self.toolbar.resume_requested.connect(self._resume_session)
        self.toolbar.stop_requested.connect(self._stop_session)
        self.toolbar.pause_on_win_toggled.connect(self._on_pause_on_win)
        self.toolbar.currency_changed.connect(self._on_currency_changed)

    def _on_currency_changed(self, currency: str) -> None:
        """Currency di toolbar berubah → update stats identity balance
        dari cache balance_list (tanpa network)."""
        if not self._account or not currency:
            return
        from corebot.clients import currency_balance

        self._account.currency = currency.upper()
        try:
            self._account.balance = currency_balance(self._account.balance_list, currency)
        except Exception:
            pass
        self.stats_panel.update_account(self._account, site=self._site)
        self._refresh_idr_price(currency)

    def _populate_toolbar_currencies(self) -> None:
        if not self._account:
            return
        currencies = [c for c, _ in self._account.balance_list] or [self._account.currency or "BTC"]
        self.toolbar.set_currencies(currencies, active=self._account.currency or "")

    def _wire_bridge(self) -> None:
        """Sambung sinyal engine bridge ke panel (dipanggil tiap connect)."""
        if self._bridge is None:
            return
        self._bridge.log_received.connect(self._on_log)
        self._bridge.state_changed.connect(self._on_state)
        self._bridge.snapshot_updated.connect(self._on_snapshot)

    def _start_session(self, currency: str, interval_ms: int) -> None:
        """Start engine memakai kode Lua dari CODE editor (bukan pilih file)."""
        from bridge.session import build_config
        from corebot.clients import currency_balance

        if self._bridge is None or self._client is None:
            self._console("warn", "Belum connect. Connect ke site dulu (menu Site).", show_tab=True)
            return

        code = self.editor_panel.current_text().strip()
        if not code:
            self._console("warn", "Editor kode kosong. Tulis/Open strategy di panel CODE dulu.", show_tab=True)
            return

        # Tulis isi editor ke file .lua supaya engine bisa load.
        strategy_path = self._write_editor_strategy(code)
        if strategy_path is None:
            return
        strategy_name = strategy_path.name

        # Set balance dari cache balance_list (TANPA network call).
        self._account.currency = currency
        try:
            self._account.balance = currency_balance(self._account.balance_list, currency)
        except Exception:
            pass

        self._refresh_idr_price(currency)

        profile = self._build_profile(max(0, interval_ms))
        config = build_config(strategy_name, currency, profile, [], strategy_path=strategy_path)

        # Reset panel live
        self.bets_panel.reset()
        self.chart_panel.reset()
        self._prev_session_profit = 0.0
        self.editor_panel.show_console_tab()
        self._console("info", f"Starting engine dari editor @ {currency}, interval {interval_ms}ms")

        try:
            self._bridge.start(config, self._account)
        except Exception as exc:
            self._console("error", f"Gagal start engine: {exc}", show_tab=True)

    def _build_profile(self, interval_ms: int):
        """Bangun SessionProfile dari interval + advanced settings.

        Fitur advanced hanya diterapkan kalau checkbox-nya ON di dialog
        Settings > Advanced Strategies.
        """
        from corebot.models import SessionProfile

        adv = self._advanced
        profile = SessionProfile(interval_ms=interval_ms)

        applied = []
        if adv.get("take_profit_enabled"):
            profile.take_profit_pct = float(adv.get("take_profit_pct", 0.0))
            applied.append(f"take-profit {profile.take_profit_pct:.4f}%")
        if adv.get("stop_on_win"):
            profile.pause_on_win = True
            applied.append("stop-on-win")
        if adv.get("max_cycles_enabled"):
            profile.max_bets = int(adv.get("max_cycles", 0))
            applied.append(f"max-cycles {profile.max_bets}")
        if adv.get("auto_break_enabled"):
            profile.run_break_seconds = float(adv.get("run_break_seconds", 0.0))
            profile.break_seconds = float(adv.get("break_seconds", 0.0))
            applied.append(f"auto-break {profile.run_break_seconds:.0f}s/{profile.break_seconds:.0f}s")
        if adv.get("flat_enabled"):
            profile.flatbet_trigger_pct = float(adv.get("flat_trigger_pct", 0.0))
            profile.flatbet_minutes = float(adv.get("flat_minutes", 0.0))
            profile.flatbet_amount = float(adv.get("flat_amount", 0.0))
            applied.append("flat-alloc")

        if applied:
            self._console("info", "Advanced aktif: " + ", ".join(applied))
        return profile

    def _write_editor_strategy(self, code: str):
        """Tulis kode editor ke file .lua di folder strategies. Return Path
        atau None kalau gagal."""
        from pathlib import Path

        from corebot.config import lua_dir

        try:
            d = lua_dir()
            d.mkdir(parents=True, exist_ok=True)
            # Kalau editor sedang mengedit file tertentu, pakai nama itu;
            # kalau tidak, pakai file khusus editor.
            cur = self.editor_panel.current_path()
            target = Path(cur) if cur else (d / "_editor_active.lua")
            target.write_text(code, encoding="utf-8")
            return target
        except Exception as exc:
            self._console("error", f"Gagal menulis strategy dari editor: {exc}", show_tab=True)
            return None

    def _pause_session(self) -> None:
        if self._bridge:
            self._bridge.pause()

    def _resume_session(self) -> None:
        if self._bridge:
            self._bridge.resume()

    def _stop_session(self) -> None:
        if self._bridge:
            self._bridge.stop()

    def _on_pause_on_win(self, enabled: bool) -> None:
        if self._bridge:
            self._bridge.set_pause_on_win(enabled)

    # ---- Bridge event handlers (main thread via Qt signals) -------------

    # Baris log per-bet dari engine (format: " NN | POS/NEG | size=... | ...").
    # Ini redundan dengan tabel Bets → disaring dari console biar tidak ramai.
    _BET_LINE_RE = re.compile(r"^\s*\d+\s*\|\s*(POS|NEG)\s*\|")

    def _on_log(self, level: str, message: str) -> None:
        if self._BET_LINE_RE.match(message):
            return  # skip spam per-bet; detailnya ada di tabel Bets
        self.editor_panel.append_console(f"[{level}] {message}")
        # Surface kejadian penting ke status bar (mis. dana kurang → paused).
        low = message.lower()
        if "available funds below" in low:
            self.statusBar().showMessage("Sesi paused: dana sesi tidak cukup untuk bet berikutnya.")
        elif "target growth reached" in low or "max cycles reached" in low:
            self.statusBar().showMessage(message)

    def _on_state(self, state: str) -> None:
        self.toolbar.set_state(state)
        self.statusBar().showMessage(f"Engine: {state}")
        self._sb_state.setText(state)
        # Alert saat sesi berhenti (dari kondisi aktif) — tanda sesi selesai.
        if state == "stopped" and getattr(self, "_was_active", False):
            self._beep_alert("Sesi berhenti")
        self._was_active = state in ("starting", "running", "paused")
        if state in ("idle", "stopped"):
            self._last_alert_streak = 0

    def _on_snapshot(self, snap) -> None:
        self.stats_panel.update_snapshot(snap)
        self.bets_panel.add_snapshot(snap, self._prev_session_profit)
        self.chart_panel.add_point(
            snap.session_bets, snap.current_balance, snap.last_bet_win, snap.session_profit
        )
        self.editor_panel.update_variables(snap)
        self._prev_session_profit = snap.session_profit
        # Status bar live
        self._sb_elapsed.setText(self._fmt_elapsed(snap.runtime_seconds))
        self._sb_speed.setText(f"{snap.speed_bps:.2f} b/s")
        self._sb_bets.setText(f"{snap.session_bets:,} bets")
        cur = (snap.currency or "").upper()
        self._sb_profit.setText(f"{snap.session_profit:+.8f} {cur}".strip())
        # Alert lose-streak: bunyi sekali tiap kelipatan threshold baru.
        self._maybe_streak_alert(snap.max_lose_streak)

    # ---- User Control ----------------------------------------------------

    def _load_default_strategy(self) -> None:
        """Muat strategy pertama (mis. sample.lua) ke editor saat startup,
        supaya CODE editor tidak kosong. User bisa Open file lain / edit."""
        from bridge.connection import list_strategies
        from corebot.config import lua_dir

        try:
            names = list_strategies()
            if not names:
                return
            # Prioritaskan sample.lua kalau ada
            pick = "sample.lua" if "sample.lua" in names else names[0]
            # Jangan muat file editor-active internal
            if pick == "_editor_active.lua" and len(names) > 1:
                pick = next((n for n in names if n != "_editor_active.lua"), pick)
            self.editor_panel.load_path(lua_dir() / pick)
        except Exception:
            pass

    def _wire_control(self) -> None:
        self.control_panel.reset_stats_requested.connect(self._reset_stats)
        self.control_panel.reset_seed_requested.connect(self._reset_seed)
        self.control_panel.reset_chart_requested.connect(self.chart_panel.reset)
        self.control_panel.hide_chart_toggled.connect(self._toggle_chart)
        self.control_panel.vault_requested.connect(lambda: self._open_vault("deposit"))
        self.control_panel.deposit_requested.connect(lambda: self._open_vault("deposit"))

    def _open_vault(self, mode: str = "deposit") -> None:
        """Buka dialog Vault (khusus site yang mendukung, mis. Wolfbet)."""
        if self._client is None:
            self._console("warn", "Belum connect. Connect ke site dulu.", show_tab=True)
            return
        if not hasattr(self._client, "vault_deposit"):
            self._console("warn", "Site ini tidak mendukung Vault (hanya Wolfbet).", show_tab=True)
            return
        from panels.vault_dialog import VaultDialog

        currency = (self._account.currency if self._account else "") or ""
        main_balance = self._account.balance if self._account else 0.0
        dialog = VaultDialog(self._client, currency, main_balance, mode=mode, parent=self)
        dialog.exec()
        # Setelah dialog ditutup, refresh balance (vault op mungkin ubah main).
        self._refresh_balance()

    def _reset_stats(self) -> None:
        self.bets_panel.reset()
        self.chart_panel.reset()
        self.stats_panel.reset_session()
        self._prev_session_profit = 0.0
        self.statusBar().showMessage("Stats display di-reset.")

    def _reset_seed(self) -> None:
        if self._client is None:
            self._console("warn", "Belum connect. Connect ke site dulu.", show_tab=True)
            return
        reset_fn = getattr(self._client, "reset_seed", None)
        if not callable(reset_fn):
            self._console("warn", "Site ini tidak mendukung reset seed.", show_tab=True)
            return
        try:
            reset_fn()
            self.statusBar().showMessage("Seed di-reset.")
            self._console("success", "Seed di-reset.")
        except Exception as exc:
            self._console("error", f"Gagal reset seed: {exc}", show_tab=True)

    def _toggle_chart(self, hide: bool) -> None:
        self.chart_panel.setVisible(not hide)

    # ---- FIAT / IDR ------------------------------------------------------

    def _refresh_idr_price(self, currency: str) -> None:
        """Fetch harga IDR untuk currency aktif (kalau RAPTECH_IDR=1).

        Pricing di-cache 60s di corebot.pricing, jadi call ini murah
        setelah first fetch. Dijalankan di main thread — acceptable karena
        jarang (connect/start) dan cached.
        """
        import os

        if os.getenv("RAPTECH_IDR") != "1":
            return
        cur = (currency or "").upper()
        if not cur:
            return
        try:
            from corebot.pricing import get_prices_idr, is_supported

            if not is_supported(cur):
                self.stats_panel.set_idr_price(cur, None)
                return
            prices = get_prices_idr([cur])
            self.stats_panel.set_idr_price(cur, prices.get(cur))
        except Exception:
            # Gagal fetch (offline dll) — jangan ganggu flow utama
            self.stats_panel.set_idr_price(cur, None)
