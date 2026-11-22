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
    // Time formatted as Days:Hours:Minutes:Seconds (e.g. 0:0:0:3)
    val totalSeconds = state.sessionElapsedTimeMs / 1000L
    val days = totalSeconds / 86400L
    val hours = (totalSeconds % 86400L) / 3600L
    val minutes = (totalSeconds % 3600L) / 60L
    val seconds = totalSeconds % 60L
    val timeFormatted = "$days:$hours:$minutes:$seconds"

    // Volume Multiplier (e.g. (0.01x) 0.08300000)
    val volMultiplier = if (state.initialBalance > 0.0) state.totalVolume / state.initialBalance else 0.0
    val volMultiplierStr = if (volMultiplier == 0.0) "0x" else String.format(Locale.US, "%.2fx", volMultiplier)
    val volumeFormatted = "($volMultiplierStr) ${String.format(Locale.US, "%.8f", state.totalVolume)}"

    // Net Result Percent & Net Result (e.g. (0.03%) 0.00413760)
    val netPercentFormatted = if (state.netResultPercent == 0.0) "(0%)" else "(${String.format(Locale.US, "%.2f%%", state.netResultPercent)})"
    val netResultFormatted = "$netPercentFormatted ${String.format(Locale.US, "%.8f", state.netResult)}"
    val netResultColor = when {
        state.netResult > 0.0 -> Color(0xFF2E7D32) // Soft Green
        state.netResult < 0.0 -> Color(0xFFC62828) // Soft Red
        else -> Color(0xFF1E293B)
    }

    val minResultColor = if (state.minResult < 0.0) Color(0xFFC62828) else Color(0xFF1E293B)
    val maxResultColor = if (state.maxResult > 0.0) Color(0xFF2E7D32) else Color(0xFF1E293B)

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(Color(0xFFEEF2F6))
            .border(1.dp, Color(0xFFCBD5E1), RoundedCornerShape(6.dp))
            .padding(horizontal = 10.dp, vertical = 6.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Kolom Kiri
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp)
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
                    label = "Min Balance:",
                    value = String.format(Locale.US, "%.8f", state.minBalance),
                    valueColor = Color(0xFF1E293B)
                )
                MetricRow(
                    label = "Max Balance:",
                    value = String.format(Locale.US, "%.8f", state.maxBalance),
                    valueColor = Color(0xFF1E293B)
                )
            }

            // Kolom Kanan
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp)
            ) {
                MetricRow(
                    label = "Volume:",
                    value = volumeFormatted,
                    valueColor = Color(0xFF1E293B)
                )
                MetricRow(
                    label = "Net Result:",
                    value = netResultFormatted,
                    valueColor = netResultColor
                )
                MetricRow(
                    label = "Min Result:",
                    value = String.format(Locale.US, "%.8f", state.minResult),
                    valueColor = minResultColor
                )
                MetricRow(
                    label = "Max Result:",
                    value = String.format(Locale.US, "%.8f", state.maxResult),
                    valueColor = maxResultColor
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
            fontSize = 10.5.sp,
            fontFamily = FontFamily.Monospace,
            color = Color(0xFF334155),
            fontWeight = FontWeight.Medium
        )
        Text(
            text = value,
            fontSize = 10.5.sp,
            fontFamily = FontFamily.Monospace,
            color = valueColor,
            fontWeight = FontWeight.Medium
        )
    }
}
