package com.raptech.dicebot.ui.components

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raptech.dicebot.model.BetRecord
import com.raptech.dicebot.ui.theme.RaptechColors
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.Locale

@Composable
fun HistoryTable(
    history: List<BetRecord>,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val listState = rememberLazyListState()

    // Urutan terbalik: Bet terbaru selalu di index 0 teratas
    val displayHistory = remember(history) {
        history.takeLast(200).reversed()
    }

    // Auto-scroll mengunci ke baris teratas secara instan setiap ada roll baru
    LaunchedEffect(history.size) {
        if (displayHistory.isNotEmpty()) {
            listState.scrollToItem(0)
        }
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(RaptechColors.SurfaceWhite)
            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(8.dp))
            .padding(6.dp)
    ) {
        // Toolbar Atas: Judul & Tombol Export JSON
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 2.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "History Bet Records (${history.size})",
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = RaptechColors.OrangePrimary
            )

            if (history.isNotEmpty()) {
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .background(RaptechColors.SurfaceLight)
                        .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(4.dp))
                        .clickable {
                            try {
                                val json = Json { prettyPrint = true }.encodeToString(history)
                                val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                val clip = ClipData.newPlainText("Raptech Bet History", json)
                                clipboard.setPrimaryClip(clip)
                                Toast.makeText(context, "${history.size} record berhasil diekspor ke Clipboard!", Toast.LENGTH_SHORT).show()
                            } catch (e: Exception) {
                                Toast.makeText(context, "Gagal mengekspor: ${e.message}", Toast.LENGTH_SHORT).show()
                            }
                        }
                        .padding(horizontal = 7.dp, vertical = 3.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.FileDownload,
                            contentDescription = "Export JSON",
                            tint = RaptechColors.OrangePrimary,
                            modifier = Modifier.size(12.dp)
                        )
                        Text(
                            text = "Export JSON",
                            fontSize = 9.sp,
                            color = RaptechColors.OrangePrimary,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(4.dp))

        // Grid Container: Header + Lazy List
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(5.dp))
                .border(1.dp, Color(0xFFCBD5E1), RoundedCornerShape(5.dp))
        ) {
            // Table Header 6 Kolom
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFEEF2F6))
                    .padding(vertical = 5.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("#", fontSize = 9.5.sp, fontWeight = FontWeight.Bold, color = Color(0xFF334155), fontFamily = FontFamily.Monospace, modifier = Modifier.weight(0.35f).padding(start = 4.dp))
                GridCellDivider()
                Text("Amount", fontSize = 9.5.sp, fontWeight = FontWeight.Bold, color = Color(0xFF334155), fontFamily = FontFamily.Monospace, modifier = Modifier.weight(1.25f).padding(start = 4.dp))
                GridCellDivider()
                Text("Cond", fontSize = 9.5.sp, fontWeight = FontWeight.Bold, color = Color(0xFF334155), fontFamily = FontFamily.Monospace, modifier = Modifier.weight(0.75f).padding(start = 4.dp))
                GridCellDivider()
                Text("Roll", fontSize = 9.5.sp, fontWeight = FontWeight.Bold, color = Color(0xFF334155), fontFamily = FontFamily.Monospace, modifier = Modifier.weight(0.65f).padding(start = 4.dp))
                GridCellDivider()
                Text("Profit", fontSize = 9.5.sp, fontWeight = FontWeight.Bold, color = Color(0xFF334155), fontFamily = FontFamily.Monospace, modifier = Modifier.weight(1.25f).padding(start = 4.dp))
                GridCellDivider()
                Text("Nonce", fontSize = 9.5.sp, fontWeight = FontWeight.Bold, color = Color(0xFF334155), fontFamily = FontFamily.Monospace, modifier = Modifier.weight(0.45f).padding(start = 4.dp))
            }

            // Divider Pemisah Header & Data
            Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color(0xFFCBD5E1)))

            if (history.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 16.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Belum ada riwayat roll. Tekan START untuk memulai sesi.",
                        color = RaptechColors.TextMuted,
                        fontSize = 10.5.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            } else {
                LazyColumn(
                    state = listState,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(260.dp)
                ) {
                    // Tanpa key agar Compose tidak me-retain anchor lama, index 0 selalu mengunci bet terbaru!
                    items(displayHistory) { item ->
                        val isWin = item.isWin
                        // Full row background sesuai video contoh:
                        val rowBg = if (isWin) Color(0xFFE6F7EC) else Color(0xFFFCE8E8)
                        val profitColor = if (isWin) Color(0xFF1B5E20) else Color(0xFFB71C1C)
                        val condStr = if (item.isHigh) "> " + String.format(Locale.US, "%.2f", item.targetChance) else "< " + String.format(Locale.US, "%.2f", item.targetChance)

                        Column(modifier = Modifier.fillMaxWidth()) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .background(rowBg)
                                    .padding(vertical = 3.5.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                // 1. Roll #
                                Text(
                                    text = "${item.executionNumber}",
                                    fontSize = 9.5.sp,
                                    fontFamily = FontFamily.Monospace,
                                    color = Color(0xFF0F172A),
                                    modifier = Modifier.weight(0.35f).padding(start = 4.dp)
                                )
                                GridCellDivider()

                                // 2. Amount
                                Text(
                                    text = String.format(Locale.US, "%.8f", item.amount),
                                    fontSize = 9.5.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Medium,
                                    color = Color(0xFF0F172A),
                                    modifier = Modifier.weight(1.25f).padding(start = 4.dp)
                                )
                                GridCellDivider()

                                // 3. Condition
                                Text(
                                    text = condStr,
                                    fontSize = 9.5.sp,
                                    fontFamily = FontFamily.Monospace,
                                    color = Color(0xFF334155),
                                    modifier = Modifier.weight(0.75f).padding(start = 4.dp)
                                )
                                GridCellDivider()

                                // 4. Roll Result
                                Text(
                                    text = String.format(Locale.US, "%.2f", item.rollResult),
                                    fontSize = 9.5.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Medium,
                                    color = Color(0xFF0F172A),
                                    modifier = Modifier.weight(0.65f).padding(start = 4.dp)
                                )
                                GridCellDivider()

                                // 5. Profit
                                Text(
                                    text = String.format(Locale.US, "%+.8f", item.netResult),
                                    fontSize = 9.5.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold,
                                    color = profitColor,
                                    modifier = Modifier.weight(1.25f).padding(start = 4.dp)
                                )
                                GridCellDivider()

                                // 6. Nonce
                                Text(
                                    text = "${item.nonce}",
                                    fontSize = 9.5.sp,
                                    fontFamily = FontFamily.Monospace,
                                    color = Color(0xFF334155),
                                    modifier = Modifier.weight(0.45f).padding(start = 4.dp)
                                )
                            }

                            // Garis pembatas horizontal antar baris
                            Box(modifier = Modifier.fillMaxWidth().height(0.5.dp).background(Color(0xFFE2E8F0)))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun GridCellDivider() {
    Box(
        modifier = Modifier
            .width(0.5.dp)
            .height(14.dp)
            .background(Color(0xFFCBD5E1))
    )
}
