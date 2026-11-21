# Task v1.1.2 — Rencana

> **Versi target:** 1.1.2
> **Status:** 📋 Planning — pilih scope (Fokus A/B/C) lalu eksekusi.
> Riwayat versi sebelumnya ada di `CHANGELOG.md`.

---

## 0. Konteks

v1.1.1 sudah membawa: tabel Bets full-row solid (win hijau / lose pink, teks hitam) +
tema Light soft silver. Referensi DiceBot klasik yang dipakai punya kolom lebih lengkap:
`Bet ID · Amount · Profit · Chance · Payout · Result · High · Game · Time · Nonce`.

Tabel Bets sekarang baru punya: `Bet# · Amount · Profit · Chance · Roll · Result · High`.

---

## 1. Usulan Scope (pilih salah satu fokus)

### 🅰 Fokus A — "Bets & Session Insight" (rekomendasi) 🔴
Lengkapi tabel Bets + ringkasan sesi. Paling nyambung dengan referensi & v1.1.1.
- **A1** Kolom tambahan di tabel Bets: **Payout** (multiplier), **Time** (jam bet), **Nonce**.
  - Butuh cek: apakah `SessionSnapshot` mengekspos payout/nonce? Kalau tidak → derive
    (payout = 99/chance; time = waktu terima snapshot; nonce = counter) **tanpa ubah engine**.
- **A2** **Ringkasan sesi** saat stop: profit, total bets, win/lose, win-rate, durasi, wagered
  → tampil di dialog kecil atau blok Console.
- **A3** **Copy** Bet row / Bet# ke clipboard (klik kanan / tombol).
- **A4** (opsi) Export CSV ikut kolom baru.

### 🅱 Fokus B — "Selesaikan Vault Wolfbet" 🟡
Vault client + dialog sudah ada; tinggal validasi endpoint deposit/withdraw + field 2FA.
- **B1** Uji nyata (mas Yuda): deposit kecil → konfirmasi path & field 2FA.
- **B2** Sesuaikan `wolfbet.py` bila field/endpoint beda dari asumsi.
- **B3** Tampilkan saldo Vault di StatsPanel + auto-refresh setelah operasi.
- **B4** (opsi) Auto-vault % profit.
> Catatan: butuh capture DevTools dari akun asli (situs uang nyata).

### 🅲 Fokus C — "Strategy Library + Docs in-app" 🟢
- **C1** Beberapa strategy bawaan di `strategies/` (flat, martingale, fibonacci, d'alembert)
  — semua dengan `stop()` proteksi (bukan `pause()` yang tidak ada di Lua).
- **C2** Menu **Help → Lua Reference** buka `docs/STRATEGY_LUA.md` / dialog ringkas.
- **C3** Template/snippet di editor (tombol "New from template").

---

## 2. Keputusan yang perlu dikonfirmasi

| # | Pertanyaan |
|---|-----------|
| Q1 | Fokus mana untuk v1.1.2? (A / B / C / kombinasi) |
| Q2 | Kalau A: kolom mana yang wajib? (Payout / Time / Nonce / semua) |
| Q3 | Kalau A2: ringkasan sesi via **dialog** atau **blok di Console**? |

> Rekomendasi: **Fokus A** (nilai langsung terlihat, tanpa dependency eksternal seperti Vault).

---

## 3. Rencana teknis (kalau Fokus A dipilih)

- `panels/bets_table.py`:
  - Tambah kolom ke `_HEADERS` + perluas tuple baris di `add_snapshot()`.
  - Payout = `99 / chance` (atau dari snapshot bila ada); Time = `datetime.now().strftime('%H:%M:%S')`
    saat baris dibuat; Nonce = `session_bets` (atau field snapshot bila tersedia).
  - Update `export_csv` mengikuti header baru.
  - Pertahankan warna full-row (win hijau / lose pink, teks hitam) + `_MAX_ROWS`.
- `_on_state` (main_window): saat `stopped`, susun ringkasan sesi dari snapshot terakhir →
  tampilkan (dialog/console).
- **Cek dulu** field `SessionSnapshot` (payout/nonce) sebelum derive, agar akurat.

---

## 4. Versioning (bagian rilis 1.1.2)

- [ ] `APP_VERSION` `1.1.1` → **`1.1.2`** (`desktop/widgets/theme.py`).
- [ ] `pyproject.toml` version → `1.1.2`.
- [ ] `CHANGELOG.md`: tambah entri `[1.1.2]`.
- [ ] Rebuild exe + selftest.

---

## 5. Definition of Done (disesuaikan setelah fokus dipilih)

- [ ] Fitur fokus terpasang & berfungsi.
- [ ] Ikut tema (Light/Dark) & tidak merusak fitur existing (bets coloring, dll).
- [ ] Verifikasi headless + cek visual RDP.
- [ ] Versi naik ke 1.1.2, changelog terisi, build exe OK.

---

*Konfirmasi Q1–Q3 (atau "gas Fokus A"), lalu saya eksekusi + audit.*
