package com.raptech.dicebot.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.BasicAlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raptech.dicebot.R
import com.raptech.dicebot.ui.theme.RaptechColors

data class LuaItemDoc(
    val name: String,
    val type: String,
    val description: String,
    val insertSnippet: String,
    val category: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LuaVariablesDialog(
    onDismiss: () -> Unit,
    onInsert: (String) -> Unit
) {
    val items = remember {
        listOf(
            // === Taruhan (Betting Core) ===
            LuaItemDoc(
                name = "nextbet / NextBet",
                type = "Double (R/W)",
                description = "Nilai taruhan untuk ronde berikutnya.",
                insertSnippet = "nextbet = ",
                category = "Taruhan"
            ),
            LuaItemDoc(
                name = "basebet / base",
                type = "Double (R/W)",
                description = "Taruhan dasar acuan strategi.",
                insertSnippet = "basebet = ",
                category = "Taruhan"
            ),
            LuaItemDoc(
                name = "chance / Chance",
                type = "Double (R/W)",
                description = "Peluang kemenangan dadu (0.01% - 98.0%).",
                insertSnippet = "chance = ",
                category = "Taruhan"
            ),
            LuaItemDoc(
                name = "bethigh / high",
                type = "Boolean (R/W)",
                description = "true untuk Roll Over (Tinggi), false untuk Roll Under (Rendah).",
                insertSnippet = "bethigh = true\n",
                category = "Taruhan"
            ),
            LuaItemDoc(
                name = "previousbet",
                type = "Double (Read)",
                description = "Nilai taruhan pada ronde sebelumnya.",
                insertSnippet = "previousbet",
                category = "Taruhan"
            ),
            LuaItemDoc(
                name = "minbet / MinBet",
                type = "Double (Read)",
                description = "Batas taruhan terendah yang diizinkan kasino aktif.",
                insertSnippet = "minbet",
                category = "Taruhan"
            ),
            LuaItemDoc(
                name = "maxbet / MaxBet",
                type = "Double (Read)",
                description = "Batas taruhan tertinggi yang diizinkan kasino aktif.",
                insertSnippet = "maxbet",
                category = "Taruhan"
            ),
            LuaItemDoc(
                name = "stopnow / StopNow",
                type = "Boolean (R/W)",
                description = "Set true untuk stop darurat bot dari dalam skrip.",
                insertSnippet = "stopnow = true\n",
                category = "Taruhan"
            ),

            // === Sesi & Finansial ===
            LuaItemDoc(
                name = "balance / Balance",
                type = "Double (R/W)",
                description = "Saldo akun kasino saat ini.",
                insertSnippet = "balance",
                category = "Finansial"
            ),
            LuaItemDoc(
                name = "startbalance",
                type = "Double (Read)",
                description = "Saldo awal saat sesi bot dimulai.",
                insertSnippet = "startbalance",
                category = "Finansial"
            ),
            LuaItemDoc(
                name = "profit / Profit",
                type = "Double (Read)",
                description = "Total akumulasi laba/rugi bersih dalam sesi ini.",
                insertSnippet = "profit",
                category = "Finansial"
            ),
            LuaItemDoc(
                name = "currentprofit",
                type = "Double (Read)",
                description = "Profit/loss yang didapat dari roll paling terakhir.",
                insertSnippet = "currentprofit",
                category = "Finansial"
            ),
            LuaItemDoc(
                name = "partialprofit",
                type = "Double (R/W)",
                description = "Akumulasi profit sementara yang dapat di-reset via resetpartialprofit().",
                insertSnippet = "partialprofit",
                category = "Finansial"
            ),
            LuaItemDoc(
                name = "wagered / invested",
                type = "Double (Read)",
                description = "Total volume taruhan yang telah diputar (wager).",
                insertSnippet = "wagered",
                category = "Finansial"
            ),
            LuaItemDoc(
                name = "minbalance / maxbalance",
                type = "Double (Read)",
                description = "Saldo terendah dan tertinggi yang tercapai sesi ini.",
                insertSnippet = "minbalance",
                category = "Finansial"
            ),
            LuaItemDoc(
                name = "highestbet / maxBetAmount",
                type = "Double (Read)",
                description = "Taruhan terbesar yang pernah dipasang sesi ini.",
                insertSnippet = "highestbet",
                category = "Finansial"
            ),
            LuaItemDoc(
                name = "maxloseamount",
                type = "Double (Read)",
                description = "Kekalahan terbesar yang pernah dialami sesi ini.",
                insertSnippet = "maxloseamount",
                category = "Finansial"
            ),
            LuaItemDoc(
                name = "percentProfit",
                type = "Double (Read)",
                description = "Persentase profit terhadap modal awal (%).",
                insertSnippet = "percentProfit",
                category = "Finansial"
            ),

            // === Streak & Hasil ===
            LuaItemDoc(
                name = "win / Win",
                type = "Boolean (Read)",
                description = "true jika ronde terakhir menang, false jika kalah.",
                insertSnippet = "win",
                category = "Streak"
            ),
            LuaItemDoc(
                name = "currentstreak / streak",
                type = "Integer (Read)",
                description = "Streak saat ini (+ untuk win beruntun, - untuk lose beruntun).",
                insertSnippet = "currentstreak",
                category = "Streak"
            ),
            LuaItemDoc(
                name = "winstreak / losestreak",
                type = "Integer (Read)",
                description = "Jumlah streak kemenangan atau kekalahan aktif saat ini.",
                insertSnippet = "winstreak",
                category = "Streak"
            ),
            LuaItemDoc(
                name = "maxwinstreak",
                type = "Integer (Read)",
                description = "Rekor win streak tertinggi sesi ini.",
                insertSnippet = "maxwinstreak",
                category = "Streak"
            ),
            LuaItemDoc(
                name = "maxlosestreak",
                type = "Integer (Read)",
                description = "Rekor lose streak tertinggi sesi ini.",
                insertSnippet = "maxlosestreak",
                category = "Streak"
            ),
            LuaItemDoc(
                name = "bets / totalbets",
                type = "Integer (Read)",
                description = "Total jumlah ronde yang telah dieksekusi sejak bot mulai.",
                insertSnippet = "bets",
                category = "Streak"
            ),
            LuaItemDoc(
                name = "wins / losses",
                type = "Integer (Read)",
                description = "Total ronde yang menang atau kalah.",
                insertSnippet = "wins",
                category = "Streak"
            ),
            LuaItemDoc(
                name = "roll / result / currentroll",
                type = "Double (Read)",
                description = "Angka hasil kocokan dadu yang keluar pada roll terakhir.",
                insertSnippet = "roll",
                category = "Streak"
            ),
            LuaItemDoc(
                name = "target",
                type = "Double (Read)",
                description = "Angka target batas kemenangan pada roll terakhir.",
                insertSnippet = "target",
                category = "Streak"
            ),

            // === lastBet Table ===
            LuaItemDoc(
                name = "lastBet.amount / bet",
                type = "Double",
                description = "Nilai taruhan pada roll terakhir.",
                insertSnippet = "lastBet.amount",
                category = "lastBet"
            ),
            LuaItemDoc(
                name = "lastBet.roll / result",
                type = "Double",
                description = "Angka hasil kocokan dadu yang keluar (0.00 - 99.99).",
                insertSnippet = "lastBet.roll",
                category = "lastBet"
            ),
            LuaItemDoc(
                name = "lastBet.profit",
                type = "Double",
                description = "Laba/rugi bersih yang didapat dari roll terakhir.",
                insertSnippet = "lastBet.profit",
                category = "lastBet"
            ),
            LuaItemDoc(
                name = "lastBet.chance",
                type = "Double",
                description = "Target peluang menang pada roll terakhir.",
                insertSnippet = "lastBet.chance",
                category = "lastBet"
            ),
            LuaItemDoc(
                name = "lastBet.payout",
                type = "Double",
                description = "Pengali kemenangan (multiplier) pada roll terakhir.",
                insertSnippet = "lastBet.payout",
                category = "lastBet"
            ),
            LuaItemDoc(
                name = "lastBet.high / bethigh",
                type = "Boolean",
                description = "Arah taruhan roll terakhir (true=High, false=Low).",
                insertSnippet = "lastBet.high",
                category = "lastBet"
            ),
            LuaItemDoc(
                name = "lastBet.win",
                type = "Boolean",
                description = "Status kemenangan roll terakhir.",
                insertSnippet = "lastBet.win",
                category = "lastBet"
            ),
            LuaItemDoc(
                name = "lastBet.nonce",
                type = "Integer",
                description = "Nomor urut nonce server provably fair.",
                insertSnippet = "lastBet.nonce",
                category = "lastBet"
            ),

            // === Fungsi Kontrol ===
            LuaItemDoc(
                name = "dobet()",
                type = "Hook",
                description = "Fungsi utama strategi yang dipanggil otomatis setiap ronde roll selesai.",
                insertSnippet = "function dobet()\n    if win then\n        nextbet = base\n    else\n        nextbet = previousbet * 2\n    end\nend\n",
                category = "Kontrol"
            ),
            LuaItemDoc(
                name = "stop() / pause()",
                type = "Function",
                description = "Menghentikan eksekusi bot secara otomatis dan aman dari dalam skrip.",
                insertSnippet = "stop()\n",
                category = "Kontrol"
            ),
            LuaItemDoc(
                name = "start() / play()",
                type = "Function",
                description = "Memulai eksekusi bot secara terprogram.",
                insertSnippet = "start()\n",
                category = "Kontrol"
            ),
            LuaItemDoc(
                name = "resume()",
                type = "Function",
                description = "Melanjutkan sesi taruhan dari kondisi jeda terakhir.",
                insertSnippet = "resume()\n",
                category = "Kontrol"
            ),
            LuaItemDoc(
                name = "stopOnWin()",
                type = "Function",
                description = "Mengaktifkan mode berhenti otomatis pada kemenangan berikutnya.",
                insertSnippet = "stopOnWin()\n",
                category = "Kontrol"
            ),
            LuaItemDoc(
                name = "reset() / resetstats()",
                type = "Function",
                description = "Mereset statistik sesi, streak, dan riwayat sambil mempertahankan saldo saat ini.",
                insertSnippet = "resetstats()\n",
                category = "Kontrol"
            ),
            LuaItemDoc(
                name = "resetall()",
                type = "Function",
                description = "Mereset total seluruh metrik, riwayat, grafik PnL, dan log konsol.",
                insertSnippet = "resetall()\n",
                category = "Kontrol"
            ),
            LuaItemDoc(
                name = "resetseed()",
                type = "Function",
                description = "Mengacak dan merotasi client seed provably fair ke server kasino.",
                insertSnippet = "resetseed()\n",
                category = "Kontrol"
            ),
            LuaItemDoc(
                name = "resetchart()",
                type = "Function",
                description = "Mengosongkan tampilan visual grafik keuntungan PnL secara instan.",
                insertSnippet = "resetchart()\n",
                category = "Kontrol"
            ),
            LuaItemDoc(
                name = "resethistory()",
                type = "Function",
                description = "Membersihkan tabel riwayat taruhan di memori.",
                insertSnippet = "resethistory()\n",
                category = "Kontrol"
            ),
            LuaItemDoc(
                name = "resetlog()",
                type = "Function",
                description = "Membersihkan seluruh baris log konsol live.",
                insertSnippet = "resetlog()\n",
                category = "Kontrol"
            ),
            LuaItemDoc(
                name = "resetpartialprofit()",
                type = "Function",
                description = "Mereset nilai variabel partialprofit kembali menjadi 0.",
                insertSnippet = "resetpartialprofit()\n",
                category = "Kontrol"
            ),

            // === Kecepatan & Delay ===
            LuaItemDoc(
                name = "sleep(seconds)",
                type = "Function",
                description = "Menjeda bot secara aman dan non-blocking selama X detik (misal: sleep(0.5)).",
                insertSnippet = "sleep(0.5)\n",
                category = "Kecepatan"
            ),
            LuaItemDoc(
                name = "setdelay(ms) / setinterval(ms)",
                type = "Function",
                description = "Mengatur jeda interval antar taruhan secara langsung dalam milidetik (ms).",
                insertSnippet = "setdelay(200)\n",
                category = "Kecepatan"
            ),
            LuaItemDoc(
                name = "setspeed(bps)",
                type = "Function",
                description = "Mengatur target kecepatan taruhan dalam satuan bet per detik.",
                insertSnippet = "setspeed(5)\n",
                category = "Kecepatan"
            ),
            LuaItemDoc(
                name = "getspeed() / getdelay()",
                type = "Function",
                description = "Mengambil nilai kecepatan riil (bps) atau jeda efektif (ms).",
                insertSnippet = "getspeed()",
                category = "Kecepatan"
            ),
            LuaItemDoc(
                name = "resetdelay() / resetspeed()",
                type = "Function",
                description = "Mereset konfigurasi jeda dan kecepatan kembali ke nilai default bot.",
                insertSnippet = "resetdelay()\n",
                category = "Kecepatan"
            ),

            // === Utilitas & Sistem ===
            LuaItemDoc(
                name = "print(...) / log(...)",
                type = "Function",
                description = "Mencetak teks informasi ke konsol Live Logs bot.",
                insertSnippet = "print(\"Info: \" .. balance)\n",
                category = "Utilitas"
            ),
            LuaItemDoc(
                name = "ching() / alarm() / sound()",
                type = "Function",
                description = "Membunyikan audio notifikasi (chime / bell) penanda event penting.",
                insertSnippet = "ching()\n",
                category = "Utilitas"
            ),
            LuaItemDoc(
                name = "checkbalance()",
                type = "Function",
                description = "Meminta sinkronisasi saldo riil terbaru dari kasino.",
                insertSnippet = "checkbalance()\n",
                category = "Utilitas"
            ),
            LuaItemDoc(
                name = "currency / coin",
                type = "String (Read)",
                description = "Simbol koin permainan aktif saat ini (misal: 'TRX', 'DOGE').",
                insertSnippet = "currency",
                category = "Utilitas"
            ),
            LuaItemDoc(
                name = "casino",
                type = "String (Read)",
                description = "Nama platform kasino aktif saat ini (misal: 'tronpick').",
                insertSnippet = "casino",
                category = "Utilitas"
            ),
            LuaItemDoc(
                name = "houseEdge / edge",
                type = "Double (Read)",
                description = "House edge kasino (default: 1.0%).",
                insertSnippet = "houseEdge",
                category = "Utilitas"
            ),
            LuaItemDoc(
                name = "time / elapsedTime",
                type = "Integer (Read)",
                description = "Total durasi sesi bot berjalan dalam satuan detik.",
                insertSnippet = "time",
                category = "Utilitas"
            )
        )
    }

    val categories = listOf("Semua", "Taruhan", "Finansial", "Streak", "lastBet", "Kontrol", "Kecepatan", "Utilitas")
    var selectedCategoryIndex by remember { mutableIntStateOf(0) }

    val filteredItems = remember(selectedCategoryIndex) {
        if (selectedCategoryIndex == 0) items
        else items.filter { it.category == categories[selectedCategoryIndex] }
    }

    BasicAlertDialog(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.85f)
                .clip(RoundedCornerShape(12.dp))
                .background(RaptechColors.SurfaceWhite)
                .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(12.dp))
                .padding(16.dp)
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        painter = painterResource(id = R.drawable.ic_lua_code),
                        contentDescription = null,
                        tint = RaptechColors.OrangePrimary,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Kamus Variabel & Fungsi LUA",
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp,
                        color = RaptechColors.TextPrimary
                    )
                }
                IconButton(onClick = onDismiss, modifier = Modifier.size(28.dp)) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Tutup",
                        tint = RaptechColors.TextSecondary
                    )
                }
            }

            Text(
                text = "Standar resmi Raptech Dicebot Extension • Tap kartu untuk menyisipkan ke editor.",
                fontSize = 11.sp,
                color = RaptechColors.TextMuted,
                modifier = Modifier.padding(top = 4.dp, bottom = 10.dp)
            )

            // Category Chips (Horizontal Scrollable)
            LazyRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                items(categories.size) { index ->
                    val isSelected = selectedCategoryIndex == index
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(if (isSelected) RaptechColors.OrangePrimary else RaptechColors.SurfaceLight)
                            .border(
                                1.dp,
                                if (isSelected) RaptechColors.OrangePrimary else RaptechColors.BorderSubtle,
                                RoundedCornerShape(6.dp)
                            )
                            .clickable { selectedCategoryIndex = index }
                            .padding(horizontal = 10.dp, vertical = 5.dp)
                    ) {
                        Text(
                            text = categories[index],
                            fontSize = 11.sp,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                            color = if (isSelected) Color.White else RaptechColors.TextPrimary
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Item List
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                items(filteredItems) { item ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(RaptechColors.SurfaceLight)
                            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(8.dp))
                            .clickable {
                                onInsert(item.insertSnippet)
                                onDismiss()
                            }
                            .padding(10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                Text(
                                    text = item.name,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 12.sp,
                                    color = RaptechColors.OrangePrimary
                                )
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(4.dp))
                                        .background(RaptechColors.SurfaceWhite)
                                        .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(4.dp))
                                        .padding(horizontal = 5.dp, vertical = 1.dp)
                                ) {
                                    Text(
                                        text = item.type,
                                        fontSize = 9.5.sp,
                                        color = RaptechColors.TextSecondary
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(3.dp))
                            Text(
                                text = item.description,
                                fontSize = 11.sp,
                                color = RaptechColors.TextSecondary,
                                lineHeight = 15.sp
                            )
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        Icon(
                            imageVector = Icons.Default.Add,
                            contentDescription = "Sisipkan",
                            tint = RaptechColors.OrangePrimary,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }
}
