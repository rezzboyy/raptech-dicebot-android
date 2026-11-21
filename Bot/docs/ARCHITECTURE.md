# Arsitektur — Raptech Dicebot

Dokumen ringkas struktur sistem untuk onboarding developer.

---

## 1. Gambaran besar

```
┌───────────────────────────────────────────────────────────────┐
│                     FRONTEND (pilih salah satu)                 │
│                                                                 │
│   desktop/  (GUI PySide6)          corebot/cli/  (CLI)          │
│   - main_window, panels, widgets   - menu, runner, prompts      │
│   - bridge/ (EngineBridge, workers)                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │  emit(event_type, payload)
                            │  ("log"/"state"/"stats")
                ┌───────────▼───────────────┐
                │      corebot/engine        │
                │      BotEngine(client,emit)│
                │  - loop taruhan (thread)   │
                │  - Lua runtime + mirror    │
                │  - profil: take-profit,    │
                │    auto-switch, flatbet    │
                └───────┬───────────┬────────┘
                        │           │
          place_bet()   │           │  load_lua_strategy()
          balances()    │           │  dobet()
                ┌───────▼──────┐  ┌─▼──────────────┐
                │ corebot/     │  │ Strategy .lua  │
                │ clients/*    │  │ (user)         │
                │ (11 site)    │  └────────────────┘
                └──────┬───────┘
                       │ HTTP (requests/curl_cffi/httpx)
                ┌──────▼───────┐
                │  Site API    │  wolf.bet, stake.com, pasino, dll
                └──────────────┘
```

---

## 2. Layer & tanggung jawab

### `corebot/` — Engine core (UI-agnostic)
| Modul | Tanggung jawab |
|-------|----------------|
| `engine/` | `BotEngine`: loop taruhan di thread, jalankan Lua `dobet()`, emit event |
| `clients/` | Adapter per site (11) → kontrak `BaseClient` (balances/stats/profile/place_bet/reset_seed) |
| `lua_support.py` | Load strategy Lua + `LuaStateMirror` (bridge Python↔Lua buffered) |
| `models.py` | Dataclass: `SessionProfile`, `SessionConfig`, `AccountSnapshot`, `SessionSnapshot` |
| `storage.py` | Settings store (token, profil, `ui.*`) di file JSON |
| `pricing.py` | Konversi harga IDR (cache 60s) |
| `license/` | Aktivasi + heartbeat lisensi |
| `config.py` | URL, currency default, konstanta |
| `machine_id.py` | ID mesin (untuk lisensi / bisa untuk enkripsi token) |
| `cli/` | Frontend CLI (menu, runner, engine_view) |
| `ui/` | Tema + widget CLI |

### `desktop/` — Frontend GUI (PySide6)
| Modul | Tanggung jawab |
|-------|----------------|
| `app.py` | Entry point QApplication + high-DPI + tema |
| `main_window.py` | Rakit menu/panel, wiring sinyal, sesi, tema, vault |
| `bridge/engine_bridge.py` | Bungkus `BotEngine` → Qt Signal (thread-safe) |
| `bridge/connection.py` | Connect/refresh site (bersih tanpa noise CLI) |
| `bridge/workers.py` | QThread: connect, refresh, vault balance/op |
| `panels/` | stats, chart, bets, code editor, control, toolbar, dialog (connect/settings/vault) |
| `widgets/` | theme, icons (SVG tint), code_edit, lua_highlighter, panel_frame, find_bar |

---

## 3. Kontrak event engine

`BotEngine` menerima callback `emit(event_type, payload)`:

| event_type | payload | Konsumen |
|------------|---------|----------|
| `"log"` | `{"level": str, "message": str}` | Console GUI / CLI |
| `"state"` | `str` (idle/starting/running/paused/stopping/stopped) | Toolbar, status bar |
| `"stats"` | `SessionSnapshot` | Stats panel, chart, bets table, Variables |

Di GUI, `EngineBridge` mengubah callback ini jadi **Qt Signal** (`log_received`,
`state_changed`, `snapshot_updated`) sehingga aman lintas-thread.

---

## 4. Prinsip desain

- **Engine UI-agnostic:** `corebot` tidak tahu ada GUI/CLI. Frontend cuma pasang `emit`.
- **Thread-safety GUI:** update widget HANYA dari main thread lewat Qt Signal/Slot.
- **Client = adapter:** tiap site menormalkan respons native ke bentuk generik
  (`{"balances":[{currency,amount}]}`, dll) yang dipahami engine.
- **Reuse maksimal:** GUI & CLI berbagi engine yang sama; zero logika bisnis di GUI.
- **Tema live:** widget berwarna daftar listener → restyle saat tema diganti.

---

## 5. Alur sesi (ringkas)

1. User connect → `connection.connect()` → `client` + `AccountSnapshot`.
2. GUI buat `EngineBridge(client)`; wire sinyal.
3. User Start → `build_config(...)` → `bridge.start(config, account)`.
4. Engine (thread) loop: baca Lua vars → `place_bet` → update mirror → `dobet()` → emit.
5. GUI terima signal → update stats/chart/bets/variables.
6. Stop/pause/take-profit/insufficient-funds → engine keluar/pause → emit state.
