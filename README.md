# Raptech Dicebot Android

Aplikasi otomatisasi strategi dadu kripto (Crypto Dicebot) berbasis **Android Native (Kotlin + Jetpack Compose)**, terinspirasi langsung dari ekosistem [Raptech Automation Desktop / Web Console](file:///E:/My%20Produk/Raptech%20Dicebot/README.md).

---

## 📑 Dokumentasi & Pedoman Rekayasa

Seluruh dokumen spesifikasi, arsitektur, panduan peran agen AI, dan peta jalan tugas tersimpan rapi di direktori [`doc/`](file:///E:/My%20Produk/App%20Android/Dicebot%20Android/doc):

1. 📋 [**`task.md`**](file:///E:/My%20Produk/App%20Android/Dicebot%20Android/doc/task.md) — *Roadmap, Task Breakdown, & Progress Tracker (Fase 1 s/d 9)*.
2. 📏 [**`rules.md`**](file:///E:/My%20Produk/App%20Android/Dicebot%20Android/doc/rules.md) — *Standar Teknis, Konvensi Penamaan, Clean Architecture, & Prinsip Keamanan*.
3. 🎨 [**`design.md`**](file:///E:/My%20Produk/App%20Android/Dicebot%20Android/doc/design.md) — *Arsitektur Sistem, Design System Cyberpunk Amber, Sequence Diagram, & State Models*.
4. 🤖 [**`agents.md`**](file:///E:/My%20Produk/App%20Android/Dicebot%20Android/doc/agents.md) — *Pembagian Peran AI Agent, Tanggung Jawab, Workflow, & Definition of Done (DoD)*.
5. 🚀 [**`production.md`**](file:///E:/My%20Produk/App%20Android/Dicebot%20Android/doc/production.md) — *Panduan Rilis Produksi, ProGuard/R8 Rules, Tolok Ukur Kinerja, & Izin Android 15*.

---

## ⚡ Karakteristik Utama Stack
- **Bahasa & UI**: Kotlin 2.0+ & Jetpack Compose (Modern, Declarative, 60-120 FPS).
- **Scripting Engine**: `LuaJ` Pure Java / Android sandboxed VM (~300 KB).
- **Background Persistence**: Android `ForegroundService` + `PARTIAL_WAKE_LOCK` (Anti-Kill di latar belakang).
- **Networking**: OkHttp 4 + WebSockets berlatensi rendah.
- **Efisiensi**: Target APK < 8 MB, Cold start < 180 ms, RAM < 65 MB.
