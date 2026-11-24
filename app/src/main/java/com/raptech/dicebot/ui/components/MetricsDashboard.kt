package com.raptech.dicebot.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raptech.dicebot.model.DicebotUiState
import java.util.Locale

@Composable
fun MetricsDashboard(
    state: DicebotUiState,
    onOpenCoinSelector: () -> Unit = {},
    isCollapsed: Boolean = false,
    onToggleCollapse: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    // Standard Time format: HH:mm:ss atau D:HH:mm:ss
    val totalSeconds = state.sessionElapsedTimeMs / 1000L
    val days = totalSeconds / 86400L
    val hours = (totalSeconds % 86400L) / 3600L
    val minutes = (totalSeconds % 3600L) / 60L
    val seconds = totalSeconds % 60L
    val timeFormatted = if (days > 0) {
        String.format(Locale.US, "%dd %02d:%02d:%02d", days, hours, minutes, seconds)
    } else {
        String.format(Locale.US, "%02d:%02d:%02d", hours, minutes, seconds)
    }

    // Volume Multiplier (misal (0.01x) 0.08300000)
    val volMultiplier = if (state.initialBalance > 0.0) state.totalVolume / state.initialBalance else 0.0
    val volMultiplierStr = if (volMultiplier == 0.0) "0x" else String.format(Locale.US, "%.2fx", volMultiplier)
    val volumeFormatted = "($volMultiplierStr) ${String.format(Locale.US, "%.8f", state.totalVolume)}"

    // Net Result Percent & Net Result
    val netPercentFormatted = if (state.netResultPercent == 0.0) "(0%)" else "(${String.format(Locale.US, "%.2f%%", state.netResultPercent)})"
    val netResultFormatted = "$netPercentFormatted ${String.format(Locale.US, "%.8f", state.netResult)}"
    val netResultColor = when {
        state.netResult > 0.0 -> Color(0xFF2E7D32) // Soft Green
        state.netResult < 0.0 -> Color(0xFFC62828) // Soft Red
        else -> Color(0xFF1E293B)
    }

    val minResultColor = if (state.minResult < 0.0) Color(0xFFC62828) else Color(0xFF1E293B)
    val maxResultColor = if (state.maxResult > 0.0) Color(0xFF2E7D32) else Color(0xFF1E293B)

    // MaxWin dan MaxLose (format: 12W/120L)
    val maxWin = state.bestPositiveStreak
    val maxLose = Math.abs(state.longestNegativeStreak)
    val maxWinLoseFormatted = "${maxWin}W/${maxLose}L"

    // Streak berjalan saat ini
    val streakFormatted = when {
        state.currentStreak > 0 -> "+${state.currentStreak}W"
        state.currentStreak < 0 -> "${Math.abs(state.currentStreak)}L"
        else -> "0"
    }
    val streakColor = when {
        state.currentStreak > 0 -> Color(0xFF2E7D32)
        state.currentStreak < 0 -> Color(0xFFC62828)
        else -> Color(0xFF1E293B)
    }

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(Color(0xFFEEF2F6))
            .border(1.dp, Color(0xFFCBD5E1), RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 6.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // Kolom Kiri
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.5.dp)
            ) {
                MetricRow(
                    label = "Time:",
                    value = timeFormatted,
                    valueColor = Color(0xFF1E293B)
                )
                MetricRow(
                    label = "Balance:",
                    value = String.format(Locale.US, "%.8f", state.balance),
                    valueColor = Color(0xFF0F172A),
                    modifier = Modifier.clickable { onOpenCoinSelector() }
                )
                MetricRow(
                    label = "Min Bal:",
                    value = String.format(Locale.US, "%.8f", state.minBalance),
                    valueColor = Color(0xFF1E293B)
                )
                MetricRow(
                    label = "Max Bal:",
                    value = String.format(Locale.US, "%.8f", state.maxBalance),
                    valueColor = Color(0xFF1E293B)
                )
                MetricRow(
                    label = "Streak:",
                    value = streakFormatted,
                    valueColor = streakColor
                )
            }

            // Kolom Kanan
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.5.dp)
            ) {
                MetricRow(
                    label = "Volume:",
                    value = volumeFormatted,
                    valueColor = Color(0xFF1E293B)
                )
                MetricRow(
                    label = "Net:",
                    value = netResultFormatted,
                    valueColor = netResultColor
                )
                MetricRow(
                    label = "Min Res:",
                    value = String.format(Locale.US, "%.8f", state.minResult),
                    valueColor = minResultColor
                )
                MetricRow(
                    label = "Max Res:",
                    value = String.format(Locale.US, "%.8f", state.maxResult),
                    valueColor = maxResultColor
                )
                MetricRow(
                    label = "Max W/L:",
                    value = maxWinLoseFormatted,
                    valueColor = Color(0xFF1E293B)
                )
            }
        }
    }
}

@Composable
private fun MetricRow(
    label: String,
    value: String,
    valueColor: Color,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            fontSize = 9.5.sp,
            fontFamily = FontFamily.Monospace,
            color = Color(0xFF334155),
            fontWeight = FontWeight.Medium,
            maxLines = 1,
            softWrap = false
        )
        Text(
            text = value,
            fontSize = 9.5.sp,
            fontFamily = FontFamily.Monospace,
            color = valueColor,
            fontWeight = FontWeight.Medium,
            maxLines = 1,
            softWrap = false
        )
    }
}
