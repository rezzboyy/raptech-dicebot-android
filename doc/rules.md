# Rules & Standard Pedoman Pengembangan (Raptech Dicebot Android)

Dokumen ini memuat standar teknis, konvensi penamaan, arsitektur software, standar keamanan modal taruhan, dan aturan kualitas kode untuk proyek **Raptech Dicebot Android** berbasis **Kotlin + Jetpack Compose** (Android Native murni).

---

## 1. Tech Stack & Library Standards

| Komponen | Teknologi / Library | Catatan & Alasan Pemilihan |
|---|---|---|
| **Bahasa Pemrograman** | Kotlin (2.0+) | Null-safety ketat, performa tinggi, modern asynchronous via Coroutines |
| **UI Toolkit** | Jetpack Compose (Compose BOM 2024.x+) | UI deklaratif modern, rendering 60-120 FPS, responsive & adaptif |
| **Design System** | Custom Raptech Cyberpunk Amber Theme | Palet warna Amber (`#FFB300`), Cyber Black (`#0B0E14`), Dark Slate (`#1A1F2C`) |
| **Arsitektur** | Clean Architecture + MVI / MVVM | Presentation (Compose) -> ViewModel -> Domain (UseCases) -> Data (Repository) |
| **State Management** | Kotlin StateFlow & SharedFlow | `collectAsStateWithLifecycle()` untuk lifecycle-safe UI stream |
| **Scripting Engine (LUA)** | `LuaJ` (v3.0.x Pure Java / Android) | Sangat ringan (~300 KB), sandboxed, kompatibel dengan skrip LUA desktop Raptech |
| **Networking & WebSocket** | OkHttp 4 + WebSockets | Low-latency HTTP client, connection pooling, interceptor auto-cookie/token |
| **Serialisasi Data** | Kotlinx Serialization | Serialisasi JSON super cepat dan ringan tanpa overhead reflection |
| **Background Service** | Android `ForegroundService` + `WakeLock` | Wajib agar bot tidak mati/di-kill oleh Android Doze Mode saat layar mati |
| **Data Visualization** | Custom Compose Canvas PnL Chart | Render ribuan titik profit/drawdown secara real-time tanpa lag memori |
| **Editor Kode Mobile** | Custom Compose CodeEditor with LineNumbers | Dilengkapi syntax highlighting LUA & tombol snippet cepat |
| **Keamanan Kredensial** | Android Keystore + EncryptedSharedPreferences | Penyimpanan API Key, Token JWT, Cookie sesi, dan Kunci Lisensi aman |
| **Target Binary** | Target APK: **< 8 MB**, Cold start: **< 180 ms**, Konsumsi RAM: **< 65 MB** | Sangat ringan, hemat baterai, dan responsif |

---

## 2. Arsitektur & Prinsip Kode

### 2.1 Clean Architecture & Pemisahan Thread (Thread Isolation)
Aplikasi Dicebot mengeksekusi roll berulang dengan frekuensi tinggi (bisa mencapai 5-10 bet per detik). Oleh karena itu, isolasi thread adalah hal yang mutlak:

1. **Main / UI Thread:**
   - Murni bertugas merender UI Compose (60/120 FPS).
   - **Dilarang keras** melakukan parsing LUA, kalkulasi matematika berat, atau pemanggilan I/O di UI thread.
2. **Default Dispatcher (`Dispatchers.Default`):**
   - Dikhususkan untuk eksekusi VM `LuaJ`, kompilasi skrip, pemrosesan variabel strategi, dan kalkulasi statistika PnL.
3. **IO Dispatcher (`Dispatchers.IO`):**
   - Menangani HTTP POST roll requests, WebSocket read/write, serta penyimpanan history ke cache disk.

```
+-----------------------------------------------------------------------------+
|                               UI THREAD (Main)                              |
|   Compose UI Screens <---> StateFlow<DicebotUiState> (60/120 FPS Render)    |
+-----------------------------------------------------------------------------+
                                      ^
                                      | State Updates (Debounced / Throttled)
+-----------------------------------------------------------------------------+
|                         BACKGROUND BOT ENGINE SERVICE                       |
|  +-----------------------------------------------------------------------+  |
|  | [Dispatchers.Default] LuaJ Engine VM (Run script, calculate next bet)  |  |
|  +-----------------------------------------------------------------------+  |
|                                     |                                       |
|                                     v Roll Request                          |
|  +-----------------------------------------------------------------------+  |
|  | [Dispatchers.IO] OkHttp Engine (Casino API: Betfury / Stake / Wolf)   |  |
|  +-----------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
```

### 2.2 Pola State Hoisting & Ring Buffer
1. **State Hoisting:**
   - Seluruh screen harus stateless (`DicebotContent`), menerima state immutable dan meneruskan event ke atas melalui lambda (`onStartClick`, `onScriptChange`, dll).
2. **Ring Buffer / Circular History:**
   - History bet yang disimpan di memori RAM dibatasi maksimum (contoh: 200 hingga 1.000 record sesuai input `Max Record`).
   - Gunakan struktur data `CircularArray` / `ArrayDeque` berkapasitas tetap agar memori tidak pernah bocor (*Out Of Memory*).

---

## 3. Konvensi Penamaan (Naming Conventions)

### 3.1 Kode Kotlin & Compose
| Tipe | Format Penamaan | Contoh |
|---|---|---|
| **Composable Function** | PascalCase (Kata Benda/Frasa) | `DicebotDashboardScreen()`, `LivePnLChart()`, `LuaCodeEditor()` |
| **ViewModel** | `<Feature>ViewModel` | `DicebotViewModel`, `LuaEditorViewModel`, `LicenseViewModel` |
| **UI State (Sealed)** | `<Feature>UiState` | `DicebotUiState`, `LuaEditorUiState`, `PlatformUiState` |
| **UI Event / Intent** | `<Feature>UiEvent` | `StartBot`, `StopBot`, `UpdateLuaScript`, `SelectPlatform` |
| **Service** | `<Feature>Service` | `DicebotExecutionService`, `SessionHeartbeatService` |
| **Repository** | `<Feature>Repository` | `CasinoApiRepository`, `StrategyRepository`, `AuthRepository` |
| **Engine Interface** | `<Feature>Engine` | `LuaScriptEngine`, `RiskManagementEngine` |
| **Constants** | UPPER_SNAKE_CASE | `DEFAULT_MAX_RECORDS`, `NOTIFICATION_CHANNEL_ID`, `LUA_TIMEOUT_MS` |

### 3.2 Resources (Drawables, Colors, Strings)
Semua aset Android wajib menggunakan format `lowercase_snake_case`:
- **Vector / Icon Drawables:** `ic_rap_<nama>.xml` (contoh: `ic_rap_dice.xml`, `ic_rap_play.xml`, `ic_rap_chart.xml`).
- **Color Tokens:** `rap_<tujuan>_<shade>` (contoh: `rap_amber_primary`, `rap_bg_dark`, `rap_neon_green`).
- **String Resources:** `<feature>_<deskripsi>` (contoh: `btn_start_bot`, `metric_balance`, `err_lua_syntax`).

---

## 4. Standar UI/UX Raptech Cyberpunk (Mobile High-Fidelity)

1. **Estetika Cyberpunk Amber Dark-Mode:**
   - Warna latar belakang: Hitam pekat modern (`#0B0E14`) dengan permukaan kartu kontras gelap (`#161B26`).
   - Warna aksen utama: **Amber Neon** (`#FFB300` / `#FFA000`) persis identitas Raptech Automation Desktop.
   - Status indikator: Hijau neon (`#00E676`) untuk Profit/Win, Merah terang (`#FF5252`) untuk Loss/Drawdown.
2. **Struktur Layar Adaptif (Portrait & Landscape):**
   - **Mode Portrait (Smartphone):**
     - **Top Bar**: Platform Selector, Currency, Status Bot, dan Quick Balance.
     - **Sticky Metrics Header**: 6 metrik paling penting (Balance, Profit, Win/Lose, Streak, Drawdown).
     - **Tab Navigation**: [1. Dashboard & Chart] [2. LUA Editor] [3. History & Logs].
     - **Bottom Sticky Bar**: Kontrol utama `[START]`, `[PAUSE]`, `[STOP]`, `[STOP ON WIN]`, `[REFRESH]`.
   - **Mode Landscape / Tablet:**
     - Tampilan layar terbagi (*Dual-Pane Split View*) persis seperti tangkapan layar desktop Raptech: Kiri grafik PnL & tabel history, Kanan editor skrip LUA & tombol kontrol.
3. **Sentuhan & Feedback Fisik:**
   - Haptic vibration ringan saat bot mencapai *Take-Profit* atau *Stop-Loss*.
   - Transisi visual tombol halus (*touch scale compression* 0.96x).

---

## 5. Standar Keamanan Bot Kripto & Manajemen Risiko (Risk Management)

Karena aplikasi ini mengelola saldo kripto riil, aturan keamanan berikut bersifat **WAJIB**:

1. **Hardcoded Circuit Breakers (Safety Stops):**
   - **Stop-Loss Protection**: Pengguna wajib dapat menentukan batas maksimal kerugian. Jika saldo menyentuh batas bawah, engine **WAJIB langsung menghentikan taruhan seketika**.
   - **Take-Profit Auto-Stop**: Bot berhenti otomatis saat target profit tercapai.
   - **Max Bet Cap**: Pengguna dapat membatasi nilai taruhan maksimum absolut agar strategi martingal LUA tidak menghabiskan saldo (*bust*) akibat kalkulasi eksponensial liar.
2. **Penyimpanan Kredensial Sensitif:**
   - Token API, Bearer JWT, Cookie kasino, dan User-Agent **DILARANG disimpan dalam SharedPreferences teks biasa**.
   - Wajib menggunakan **Android Keystore System** dengan enkripsi AES-256 GCM.
3. **Sanitasi Logcat:**
   - Dilarang keras menampilkan token otentikasi kasino, session cookies, atau private key di Android Logcat. Log hanya menampilkan angka roll, net result, dan error status HTTP.
4. **Proteksi Infinite Loop LUA:**
   - Eksekusi fungsi LUA setiap ronde diberi batas waktu eksekusi maksimal (*timeout* 500 ms). Jika script macet dalam *infinite loop*, engine otomatis membatalkan eksekusi dan mematikan bot secara aman.
