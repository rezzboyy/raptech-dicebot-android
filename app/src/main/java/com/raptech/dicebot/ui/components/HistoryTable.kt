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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
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

    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(RaptechColors.SurfaceWhite)
            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(8.dp))
            .padding(8.dp)
    ) {
        // Bar Toolbar: Title & Export JSON Action
        Row(
            modifier = Modifier.fillMaxWidth(),
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
                        .clip(RoundedCornerShape(5.dp))
                        .background(RaptechColors.SurfaceLight)
                        .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(5.dp))
                        .clickable {
                            try {
                                val json = Json { prettyPrint = true }.encodeToString(history)
                                val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                val clip = ClipData.newPlainText("Raptech Bet History", json)
                                clipboard.setPrimaryClip(clip)
                                Toast.makeText(context, "${history.size} record berhasil diekspor ke Clipboard (JSON)!", Toast.LENGTH_SHORT).show()
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

        Spacer(modifier = Modifier.height(6.dp))

        // Table Header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(5.dp))
                .background(RaptechColors.SurfaceLight)
                .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(5.dp))
                .padding(horizontal = 6.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("#", fontSize = 9.sp, color = RaptechColors.TextSecondary, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(0.7f))
            Text("Amount", fontSize = 9.sp, color = RaptechColors.TextSecondary, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1.8f))
            Text("Target", fontSize = 9.sp, color = RaptechColors.TextSecondary, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1.1f))
            Text("Roll", fontSize = 9.sp, color = RaptechColors.TextSecondary, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1.1f))
            Text("Net Result", fontSize = 9.sp, color = RaptechColors.TextSecondary, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1.8f))
            Text("Nonce", fontSize = 9.sp, color = RaptechColors.TextSecondary, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(0.9f))
        }

        Spacer(modifier = Modifier.height(4.dp))

        if (history.isEmpty()) {
            Text(
                text = "Belum ada riwayat roll. Tekan START untuk memulai sesi.",
                color = RaptechColors.TextMuted,
                fontSize = 11.sp,
                modifier = Modifier.padding(vertical = 16.dp, horizontal = 8.dp)
            )
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(230.dp),
                verticalArrangement = Arrangement.spacedBy(3.dp),
                reverseLayout = true
            ) {
                items(history.takeLast(100), key = { it.executionNumber }) { item ->
                    val isWin = item.isWin
                    val rowBg = if (isWin) RaptechColors.WinBackground else RaptechColors.LossBackground
                    val rowBorder = if (isWin) RaptechColors.WinBorder else RaptechColors.LossBorder
                    val resultColor = if (isWin) RaptechColors.WinSuccess else RaptechColors.LossDanger

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(4.dp))
                            .background(rowBg)
                            .border(0.5.dp, rowBorder, RoundedCornerShape(4.dp))
                            .padding(horizontal = 6.dp, vertical = 4.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "${item.executionNumber}",
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            color = RaptechColors.TextSecondary,
                            modifier = Modifier.weight(0.7f)
                        )
                        Text(
                            text = String.format(Locale.US, "%.6f", item.amount),
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Medium,
                            color = RaptechColors.TextPrimary,
                            modifier = Modifier.weight(1.8f)
                        )
                        Text(
                            text = "${String.format(Locale.US, "%.1f", item.targetChance)}%",
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            color = RaptechColors.TextSecondary,
                            modifier = Modifier.weight(1.1f)
                        )
                        Text(
                            text = String.format(Locale.US, "%.2f", item.rollResult),
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace,
                            color = resultColor,
                            modifier = Modifier.weight(1.1f)
                        )
                        Text(
                            text = String.format(Locale.US, "%+.6f", item.netResult),
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace,
                            color = resultColor,
                            modifier = Modifier.weight(1.8f)
                        )
                        Text(
                            text = "${item.nonce}",
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            color = RaptechColors.TextMuted,
                            modifier = Modifier.weight(0.9f)
                        )
                    }
                }
            }
        }
    }
}
