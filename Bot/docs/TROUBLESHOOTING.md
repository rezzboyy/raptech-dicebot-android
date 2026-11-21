# Troubleshooting — Raptech Dicebot

Kumpulan masalah umum + solusinya. Cari gejalamu di bawah.

---

## Koneksi Site

### Stake: `HTTP 404: Cannot POST /graphql`
Endpoint lama `api.stake.com/graphql` sudah mati. Versi terbaru sudah memakai
`https://stake.com/_api/graphql`. Kalau masih 404:
- Pastikan pakai build terbaru.
- Pastikan token adalah **API token Stake** (stake.com → Settings → API), bukan sekadar cookie.

### Stake: `HTTP 403` / Cloudflare
Cloudflare menantang koneksi. Coba:
- Pakai proxy region yang diizinkan (menu Site — bila tersedia).
- Set mirror region via environment sebelum jalankan:
  ```cmd
  set RAPTECH_STAKE_URL=https://stake.bet/_api/graphql
  builds\desktop\raptech-dicebot.exe
  ```
  Ganti `stake.bet` dengan domain Stake yang bisa kamu buka di browser + `/_api/graphql`.

### Geo-block umum (site apa pun)
- Situs judi sering diblokir ISP/DNS. Pakai **Set Proxy** (kalau tersedia) atau VPN.
- Beberapa client (mis. Pasino) sudah bypass DNS block via DoH.

### Token salah / expired
- Ambil ulang token dari browser (DevTools → Application → Local Storage / atau menu API site).
- Format token berbeda tiap site — lihat hint di dialog **Select Site & Connect**.
- Betfury: format `TOKEN;uid=UID`.

### Connect lama lalu timeout (maks 30 detik)
- Jaringan lambat / site down / geo-block. Cek koneksi, coba proxy.

---

## Aplikasi (GUI)

### App tidak terbuka / langsung tertutup
- Jalankan dari CMD untuk lihat error:
  ```cmd
  builds\desktop\raptech-dicebot.exe
  ```
- Pastikan folder `_internal\` ada di sebelah `.exe` (jangan dihapus/dipisah).

### `ModuleNotFoundError: No module named 'corebot'` (saat dev `python desktop/app.py`)
- Folder `corebot/` belum ada di root project. Salin dari sumber ke root.

### Teks gelap-di-atas-gelap di tema Dark (sudah diperbaiki)
- Sudah difix. Kalau masih, update ke build terbaru.

### Chart terlihat pecah / kurang halus
- Antialias default ON. Kalau RDP sangat lambat dan mau ringan:
  `set RAPTECH_CHART_AA=0` sebelum jalankan.

### GUI lambat/lag di RDP
- `set RAPTECH_REDRAW_FPS=10` untuk kurangi beban render.

### Console terlalu ramai
- Baris per-bet sudah otomatis disaring dari console (detailnya ada di tabel Bets).

---

## Sesi / Betting

### "Sesi tiba-tiba berhenti tapi saldo masih ada"
- Itu sesi **PAUSED** (bukan stop) karena taruhan berikutnya > saldo sesi yang tersedia.
  Status bar menampilkan alasannya. Klik Resume setelah menyesuaikan, atau Reset.
- "Balance" di WALLETS (atas) = snapshot dompet saat connect; saldo sesi live ada di panel SESSION.

### Strategy error saat jalan
- Cek strategy pakai tombol **Check** (F8) dulu.
- **`pause()` tidak tersedia di Lua** — pakai `stop()`. Lihat `docs/STRATEGY_LUA.md`.
- Pastikan `dobet()` selalu men-set `nextbet` valid (> 0).

### Bet terlalu cepat / kena limit
- Naikkan interval (ms) di toolbar bawah.

---

## Vault (Wolfbet)

### Tombol Vault disabled
- Vault hanya untuk site yang mendukung (Wolfbet). Connect ke Wolfbet dulu.

### Deposit/Withdraw vault gagal
- Butuh **password akun** + **kode Google Authenticator (2FA)** yang valid.
- Kalau error endpoint, kirim pesan error + capture request dari DevTools.

---

## Build

### Build gagal `No module named ...`
- Install dependency: `pip install -r requirements.txt -r desktop/requirements-desktop.txt`
- Update PyInstaller: `pip install --upgrade pyinstaller`

### Icon/tema tidak muncul di hasil build
- Pastikan `assets/icons/*.svg` ter-bundle (`--add-data`) dan `PySide6.QtSvg` ikut.
  Script build (`build_desktop.py` / `build_manual.*`) sudah menangani ini.

### Warning `pyqtgraph.opengl ... No module named 'OpenGL'` saat build
- **Normal & aman diabaikan.** Chart tidak pakai OpenGL.

---

## Environment Variables (ringkas)

| Variable | Fungsi |
|----------|--------|
| `RAPTECH_IDR=1` | Aktifkan konversi IDR di panel |
| `RAPTECH_STAKE_URL=...` | Override endpoint GraphQL Stake (mirror region) |
| `RAPTECH_HTTP_BACKEND=httpx` | HTTP/2 client (lebih cepat) |
| `RAPTECH_CHART_AA=0` | Matikan antialias chart (RDP lambat) |
| `RAPTECH_REDRAW_FPS=10` | Kurangi refresh rate panel |
| `RAPTECH_LUA=luajit21` | Pilih runtime Lua |

---

*Kalau masalahmu belum ada di sini, catat pesan error persisnya + langkah reproduksi.*
