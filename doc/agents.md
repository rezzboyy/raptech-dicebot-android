# AI Agent Collaboration & Roles (Raptech Dicebot Android)

Dokumen ini mendefinisikan pembagian peran (*persona*), tanggung jawab teknis, batas kerja, dan protokol kolaborasi multi-agent dalam proses rekayasa aplikasi **Raptech Dicebot Android** berbasis **Kotlin + Jetpack Compose**.

---

## 1. Daftar Persona Agen

### 1.1 Lead Android & Architecture Specialist (`@lead-architect`)
- **Fokus:** Fondasi arsitektur Clean Architecture, Gradle build lifecycle, struktur modular, dan state machine.
- **Tanggung Jawab:**
  - Mengonfigurasi `build.gradle.kts` (Project & App level), versi SDK 35 (Android 15), compiler plugins, dan dependensi minimal.
  - Memastikan *Clean Architecture boundaries* tidak bocor (Presentation tidak boleh mengakses Network I/O secara langsung tanpa UseCases/Domain).
  - Menyusun `DicebotUiState` immutable dan mengelola alur komunikasi antara `ViewModel` dengan `ForegroundService`.
  - Menjaga ukuran binary tetap ramping dengan menolak penambahan pustaka pihak ketiga yang tidak esensial.

### 1.2 Core LUA & Automation Engine Specialist (`@engine-lua-specialist`)
- **Fokus:** Integrasi virtual machine `LuaJ`, eksekusi skrip strategi, *sandboxing*, dan *variable binding*.
- **Tanggung Jawab:**
  - Mengonfigurasi library `LuaJ` (Pure Java / Android) agar dapat mengompilasi dan mengeksekusi skrip strategi LUA dengan latensi rendah.
  - Menginjeksi variabel runtime global standar Raptech (`balance`, `nextbet`, `chance`, `bethigh`, `win`, `currentstreak`, `lastBet`).
  - Menangani siklus *hook* taruhan (`dobet()`, `onWin()`, `onLose()`).
  - Memasang pengaman *watchdog timer* (maksimal eksekusi 500 ms) agar skrip yang mengalami *infinite loop* tidak membekukan aplikasi.

### 1.3 Casino Network & Reverse-Engineering Engineer (`@casino-network-engineer`)
- **Fokus:** Komunikasi jaringan berkecepatan tinggi, integrasi API/WebSocket kasino, dan manajemen sesi.
- **Tanggung Jawab:**
  - Membangun OkHttp client dengan connection pooling optimal, keep-alive, dan latensi minimal.
  - Mengadaptasi payload taruhan dari basis kode [`Raptech Dicebot`](file:///E:/My%20Produk/Raptech%20Dicebot/README.md):
    - **Betfury**: WebSocket + REST GraphQL payload.
    - **Stake**: GraphQL API endpoint dengan JWT bearer auth.
    - **Wolf.bet**: REST API v2 direct calls.
    - **Pasino / Tronpick / Dogepick**: Direct endpoints dengan CSRF cookie interceptor.
  - Mengimplementasikan penanganan error HTTP 429 (Rate Limit) dan *auto-reconnect* jika jaringan seluler terputus.

### 1.4 Jetpack Compose UI/UX Specialist (`@compose-ui-specialist`)
- **Fokus:** Implementasi antarmuka deklaratif Jetpack Compose dengan estetika Cyberpunk Amber khas Raptech.
- **Tanggung Jawab:**
  - Membangun `RaptechTheme`, warna neon amber (`#FFB300`), dan background hitam kontras tinggi.
  - Membuat komponen visual utama:
    - **Dashboard Header**: Menampilkan 12 metrik finansial secara padat dan rapi.
    - **Live PnL Chart**: Komponen Canvas kustom berkecepatan tinggi yang menggambar garis profit/drawdown real-time.
    - **LUA Code Editor**: Editor kode mobile dengan nomor baris, pewarnaan sintaks (*syntax highlighting*), dan tombol *snippet* cepat.
    - **Tabel History Virtual**: `LazyColumn` yang mampu menampilkan ratusan data roll tanpa memory lag.
  - Menyediakan responsivitas layar ganda: Mode Portrait (Tab-based) dan Mode Landscape (Dual-Pane Split View).

### 1.5 Android Background Service & Persistence Specialist (`@background-service-engineer`)
- **Fokus:** Stabilitas eksekusi bot di latar belakang (*background persistence*) dan manajemen daya baterai.
- **Tanggung Jawab:**
  - Membangun `DicebotForegroundService` dengan persistent notification yang menampilkan saldo dan profit langsung di status bar HP.
  - Mengelola `WakeLock` (`PARTIAL_WAKE_LOCK`) agar CPU tetap aktif mengeksekusi taruhan saat layar HP padam.
  - Memandu pengguna untuk mengecualikan aplikasi dari optimasi baterai agresif vendor HP (*Battery Optimization Whitelist*).
  - Menyimpan data riwayat ke *Ring Buffer* memori dan mengekspornya ke format JSON saat diminta pengguna.

### 1.6 Risk Management & Security Auditor (`@qa-security-auditor`)
- **Fokus:** Perlindungan modal taruhan, pembatasan risiko, dan pengujian performa binary.
- **Tanggung Jawab:**
  - Memastikan *circuit breakers* (Stop-Loss, Take-Profit, Max-Bet Limit) selalu dievaluasi **sebelum** request taruhan dikirim ke jaringan.
  - Mengamankan penyimpanan kredensial (API Key & Cookie) menggunakan **Android Keystore System**.
  - Mengaudit alokasi memori agar tidak terjadi kebocoran memori (*memory leak*) setelah 10.000+ kali roll.
  - Memverifikasi ukuran file APK Release berada di bawah **8.0 MB** dengan optimasi ProGuard/R8.

---

## 2. Protokol Kolaborasi & Alur Kerja (Workflow Pipeline)

```
[1. Lead Architect] Setup Clean Architecture & State Flow Contract
        |
        v
[2. Casino Engineer & Lua Specialist] Bangun Network Client + LuaJ Engine Binding
        |
        v
[3. Background Service Engineer] Bungkus Engine ke dalam Foreground Service & WakeLock
        |
        v
[4. Compose UI Specialist] Bangun UI Cyberpunk Amber, Canvas Chart & LUA Editor
        |
        v
[5. QA & Security Auditor] Uji Safety Stops, Uji Ketahanan 2 Jam Non-Stop, Build Release APK
```

---

## 3. Definition of Done (DoD) per Komponen

1. **Komponen UI Compose:**
   - Rendering 60-120 FPS tanpa frame drop.
   - Responsif pada layar HP 360dp hingga tablet/landscape 840dp.
   - Memiliki preview `@Preview` untuk mode Portrait dan Landscape.
2. **Komponen Engine LUA:**
   - Mampu mengeksekusi skrip strategi standar (Martingale, Fibonacci, D'Alembert) dengan benar.
   - Waktu eksekusi tiap roll di bawah 5 milidetik.
   - Terbukti aman dari *crash* saat skrip pengguna mengandung sintaks salah.
3. **Komponen Background Service:**
   - Bot terus berjalan lancar saat layar HP dimatikan selama 30 menit pengujian.
   - Ongoing notification selalu menampilkan saldo dan profit terkini.
4. **Komponen Keamanan:**
   - Fitur Stop-Loss 100% mematikan bot saat saldo menyentuh batas bawah.
   - Tidak ada token rahasia yang tercetak di Logcat.
