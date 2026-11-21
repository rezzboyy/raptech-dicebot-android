# Changelog — Raptech Dicebot

Format: [versi] — ringkasan. Terbaru di atas.
Versi aplikasi desktop (GUI) di `desktop/widgets/theme.py` (`APP_VERSION`);
versi engine di `corebot/__init__.py` (`__version__`).

---

## [1.1.1] — Bets row coloring + Light soft

### Ditambahkan
- **Tabel Bets berwarna per baris**: baris WIN berlatar hijau, LOSE berlatar merah
  (tint lembut, alpha), font Profit/Result tetap tegas. Alternating row dimatikan.
  Ikut tema (Light/Dark/Midnight/High-Contrast) secara live.

### Diubah
- **Tema Light dibuat soft (silver)**: putih tidak lagi menyilaukan — window silver
  lembut (`#e4e7ec`), panel off-white silver (`#f1f2f5`), input `#f7f8fa`. Lebih nyaman di mata.

---

## [1.1.0] — Desktop GUI besar + fix

### Ditambahkan
- **Tema**: Light (default), Dark, Midnight, High-Contrast; toggle SVG live; custom accent;
  font scaling (S/M/L). Preferensi tersimpan (`ui.desktop_theme/accent/font`).
- **SVG icon set** (14) auto-tint; app icon dari `assets/app.svg`.
- **Editor strategy**: Check/lint (F8) + highlight baris error, tab Variables live, Find/Replace.
- **Data & visual**: export Bets → CSV, Chart → PNG; toggle chart Balance/Profit + garis nol.
- **Polish**: simpan layout window/splitter; shortcuts (F5/F6/F7, Ctrl+S/O/R/K/H/D/F);
  status bar kaya; sound alerts opsional.
- **Vault Wolfbet**: client `vault_balance/deposit/withdraw` + dialog (password + 2FA), gated.
- **Dokumentasi**: `docs/STRATEGY_LUA.md`, `docs/TROUBLESHOOTING.md`, `docs/ARCHITECTURE.md`,
  `IMPROVEMENTS.md`, `CHANGELOG.md`.
- **Build**: `build_desktop.py` + `build_manual.sh` / `build_manual.bat`. Versi di title & About.

### Diperbaiki
- **Stake connect 404**: endpoint `api.stake.com/graphql` → `stake.com/_api/graphql` + header
  browser-like; dukung mirror via `RAPTECH_STAKE_URL`.
- **Tema Dark**: nilai session & wallet non-aktif sempat gelap-di-atas-gelap (apply_theme crash
  karena `_wallet_empty` terhapus) — robust + kontras `text_dim` dinaikkan.
- **Console spam**: baris per-bet disaring (detail ada di tabel Bets) + cap 2000 baris.
- **Chart HD**: antialias default ON + pen lebih tebal; icon supersample 2× (anti-burik).

### Catatan
- `pause()` TIDAK tersedia di Lua (hanya `stop()`), `invest()` masih no-op — lihat `docs/STRATEGY_LUA.md`.

---

## [1.0.14] — Engine baseline (corebot)

- Engine multi-site (11 client), runtime Lua + `LuaStateMirror`, profil sesi
  (take-profit, auto-switch, flatbet, auto-break), license + heartbeat, CLI.
