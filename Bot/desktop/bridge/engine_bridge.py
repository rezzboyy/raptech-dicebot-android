"""EngineBridge — wrap `corebot.engine.BotEngine` sebagai QObject.

Engine jalan di thread sendiri dan emit event via callback biasa
`emit(event_type, payload)`. Bridge menangkap callback itu lalu
memancarkannya sebagai **Qt Signal**. Karena signal Qt otomatis
di-marshal ke thread penerima (QueuedConnection lintas-thread), slot di
main thread aman meng-update widget.

Kontrak event dari engine (lihat corebot/engine/__init__.py):
    ("log",   {"level": str, "message": str})
    ("state", str)                       # idle/starting/running/paused/stopping/stopped
    ("stats", SessionSnapshot)

Bridge memetakan:
    "log"   -> log_received(level, message)
    "state" -> state_changed(state)
    "stats" -> snapshot_updated(snapshot)   # payload object (SessionSnapshot)
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from corebot.engine import BotEngine
from corebot.models import AccountSnapshot, SessionConfig


class EngineBridge(QObject):
    """Adapter Qt untuk BotEngine.

    Buat instance ini di MAIN THREAD supaya signal ter-marshal dengan
    benar ke slot UI.
    """

    # Signals (dikonsumsi UI)
    log_received = Signal(str, str)      # (level, message)
    state_changed = Signal(str)          # state
    snapshot_updated = Signal(object)    # SessionSnapshot

    def __init__(self, client, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client = client
        # Engine dikonstruksi dengan callback bridge sebagai emit.
        self._engine = BotEngine(client, self._on_engine_event)

    # ---- Callback dari engine (dipanggil di thread engine) --------------

    def _on_engine_event(self, event_type: str, payload: object) -> None:
        """Dipanggil engine (thread lain). Ubah jadi Qt signal.

        Emit signal di sini aman lintas-thread: Qt akan antri
        (QueuedConnection) dan eksekusi slot di thread objek penerima.
        """
        if event_type == "log":
            if isinstance(payload, dict):
                level = str(payload.get("level", "info"))
                message = str(payload.get("message", ""))
            else:
                level, message = "info", str(payload)
            self.log_received.emit(level, message)
        elif event_type == "state":
            self.state_changed.emit(str(payload))
        elif event_type == "stats":
            self.snapshot_updated.emit(payload)
        # event_type lain diabaikan (forward-compat)

    # ---- Kontrol engine (dipanggil dari UI / main thread) ---------------

    def start(self, config: SessionConfig, account: AccountSnapshot) -> None:
        self._engine.start(config, account)

    def pause(self) -> None:
        self._engine.pause()

    def resume(self) -> None:
        self._engine.resume()

    def stop(self) -> None:
        self._engine.stop()

    def set_pause_on_win(self, enabled: bool) -> None:
        self._engine.set_pause_on_win(enabled)

    def is_alive(self) -> bool:
        return self._engine.is_alive()

    def wait(self, timeout: float | None = None) -> None:
        self._engine.wait(timeout)

    @property
    def state(self) -> str:
        return self._engine.state

    @property
    def client(self):
        return self._client
