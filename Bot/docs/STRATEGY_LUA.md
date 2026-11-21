# Panduan Strategy Lua — Raptech Dicebot

Strategy ditulis dalam **Lua**, disimpan sebagai file `*.lua` di folder `strategies/`.
Engine memanggil fungsi `dobet()` setiap satu siklus taruhan, membaca variabel yang kamu
set (mis. `nextbet`, `chance`, `bethigh`), lalu menaruh taruhan ke site.

> Referensi ini akurat terhadap runtime engine saat ini (`corebot/engine/_lua_runtime.py`).
> Fungsi/variabel di luar daftar ini **tidak dijamin ada**.

---

## 1. Kerangka minimum

```lua
chance   = 49.5      -- peluang menang (%) 0.01–98
basebet  = 0.00000001
bethigh  = false     -- true = taruhan "high/over", false = "low/under"
nextbet  = basebet   -- WAJIB di-set: jumlah taruhan siklus berikutnya

function dobet()
  if win then
    nextbet = basebet          -- menang → balik ke basebet
  else
    nextbet = previousbet * 2  -- kalah → gandakan (martingale)
  end
end
```

Engine loop tiap siklus:
1. Baca `nextbet`, `chance`, `bethigh` (di-clamp ke rentang valid).
2. Taruh bet ke site.
3. Update variabel hasil (`win`, `currentprofit`, `balance`, dll).
4. Panggil `dobet()` — di sinilah kamu menghitung `nextbet` berikutnya.

---

## 2. Variabel yang tersedia

### Dibaca kamu (di-update engine tiap bet)

| Variabel | Tipe | Arti |
|----------|------|------|
| `balance` | number | Saldo terkini currency aktif |
| `startbalance` | number | Saldo saat sesi mulai |
| `win` | boolean | Hasil bet terakhir (menang?) |
| `previousbet` | number | Jumlah bet sebelumnya |
| `currentprofit` | number | Profit dari bet terakhir (+/−) |
| `currentroll` | number | Angka hasil roll terakhir (0–99.99) |
| `currentstreak` | number | Streak berjalan (+ menang, − kalah) |
| `profit` | number | Profit sesi kumulatif |
| `partialprofit` | number | Profit parsial (bisa di-reset) |
| `wagered` | number | Total taruhan sesi |
| `bets` / `wins` / `losses` | number | Hitungan sesi |
| `totalbets` / `totalwins` / `totallosses` | number | Hitungan akun (all-time) |
| `totalprofit` / `totalwagered` | number | Total akun |
| `lastBet` | table | `{ Roll = <angka>, Nonce = <n> }` |
| `currency` | string | Currency aktif (lowercase) |

### Kamu set (dibaca engine)

| Variabel | Tipe | Arti |
|----------|------|------|
| `nextbet` | number | **Wajib** — jumlah bet siklus berikutnya |
| `chance` | number | Peluang menang (%) — di-clamp ke 0.01–98 |
| `bethigh` | boolean | Arah taruhan (true=high/over) |
| `basebet` (alias `base`) | number | Bet dasar (referensi) |

> Kalau `nextbet` ≤ 0, engine fallback ke `basebet`. Kalau `basebet` ≤ 0, fallback ke `0.00000001`.

---

## 3. Fungsi yang tersedia

| Fungsi | Efek |
|--------|------|
| `stop()` | Hentikan sesi (engine keluar dari loop) |
| `resetseed()` | Panggil reset seed di site (kalau didukung) |
| `resetstats()` | Reset `partialprofit`, `currentprofit`, `currentstreak`, `profit` |
| `resetpartialprofit()` | Set `partialprofit = 0` |
| `resetchart()` | No-op (chart dikelola GUI) |
| `sleep(ms)` | Jeda eksekusi `ms` milidetik |
| `invest(amount)` | **No-op** (placeholder — belum berfungsi) |

### ⚠ Gotchas penting

- **`pause()` TIDAK tersedia di Lua.** Hanya `stop()` yang ada. Memanggil `pause()` dari
  strategy akan error `attempt to call a nil value`. (Pause sesi dilakukan lewat tombol GUI,
  bukan dari strategy.)
- `invest()` saat ini **tidak melakukan apa-apa** — jangan andalkan untuk vaulting.
  Vault dilakukan lewat tombol Vault di GUI (khusus site yang mendukung, mis. Wolfbet).
- `chance` otomatis di-clamp ke 0.01–98. Nilai di luar itu disesuaikan engine.
- Standard Lua library tersedia (`math`, `string`, `table`, `pairs`, `tonumber`, dll)
  sesuai runtime (LuaJIT/5.x). `print(...)` muncul di Console GUI.

---

## 4. Contoh strategy

### Flat bet
```lua
chance = 49.5
basebet = 0.00000010
nextbet = basebet
bethigh = false

function dobet()
  nextbet = basebet   -- selalu sama
end
```

### Martingale dengan stop-loss & take-profit
```lua
chance   = 49.5
basebet  = 0.00000010
nextbet  = basebet
bethigh  = false
maxlose  = 0.00010000   -- batas rugi sesi
target   = 0.00010000   -- target profit sesi

function dobet()
  if win then
    nextbet = basebet
  else
    nextbet = previousbet * 2
  end

  if profit >= target then
    print("Target tercapai, stop.")
    stop()
  end
  if profit <= -maxlose then
    print("Stop-loss kena, stop.")
    stop()
  end
end
```

### Ganti chance acak tiap menang
```lua
basebet = 0.00000010
nextbet = basebet
chance  = 49.5

function dobet()
  if win then
    nextbet = basebet
    chance  = math.random(20, 70) + 0.5
  else
    nextbet = previousbet * 1.5
  end
end
```

---

## 5. Tips praktik

- Uji dulu di **Test Mode** (tanpa dana nyata) sebelum ke site asli.
- Pakai tombol **Check** (F8) di editor untuk validasi sebelum Start — cek `chance`,
  `basebet`, `nextbet`, dan dry-run `dobet()` untuk state win & lose.
- Tabel **Bets** menampilkan tiap taruhan; tab **Variables** menampilkan nilai runtime live.
- Martingale murni berisiko habis saldo saat lose-streak panjang — selalu pasang `stop()`
  berbasis `profit`/streak.
