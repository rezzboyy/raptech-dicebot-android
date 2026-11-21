package com.raptech.dicebot.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material3.Icon
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
import com.raptech.dicebot.ui.theme.RaptechColors
import java.util.Locale

@Composable
fun MetricsDashboard(
    state: DicebotUiState,
    onOpenCoinSelector: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    val elapsedSeconds = state.sessionElapsedTimeMs / 1000
    val hours = elapsedSeconds / 3600
    val minutes = (elapsedSeconds % 3600) / 60
    val seconds = elapsedSeconds % 60
    val timeFormatted = String.format(Locale.US, "%02d:%02d:%02d", hours, minutes, seconds)

    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(RaptechColors.SurfaceWhite)
            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(8.dp))
            .padding(10.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        // Row 1: Time, Volume, Executions, Outcomes
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            MetricItem("Time", timeFormatted, RaptechColors.TextPrimary)
            MetricItem("Volume", String.format(Locale.US, "%.4f", state.totalVolume), RaptechColors.TextPrimary)
            MetricItem("Executions", "${state.executions}", RaptechColors.TextPrimary)
            MetricItem("Win / Lose", "${state.positiveOutcomes} / ${state.negativeOutcomes}", RaptechColors.InfoBlue)
        }

        // Row 2: Balance & Net Result (Highlight Primary)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(6.dp))
                .background(RaptechColors.SurfaceLight)
                .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                .padding(horizontal = 8.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier
                    .clip(RoundedCornerShape(4.dp))
                    .clickable { onOpenCoinSelector() }
                    .padding(vertical = 2.dp, horizontal = 4.dp)
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(3.dp)
                ) {
                    Text("Balance (${state.selectedCurrency})", fontSize = 10.sp, color = RaptechColors.TextSecondary)
                    Icon(
                        imageVector = Icons.Default.ArrowDropDown,
                        contentDescription = "Pilih Koin",
                        tint = RaptechColors.OrangePrimary,
                        modifier = Modifier.size(14.dp)
                    )
                }
                Text(
                    text = String.format(Locale.US, "%.8f", state.balance),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = RaptechColors.OrangePrimary
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = "Net Result (${String.format(Locale.US, "%+.1f", state.netResultPercent)}%)",
                    fontSize = 10.sp,
                    color = RaptechColors.TextSecondary
                )
                Text(
                    text = String.format(Locale.US, "%+.8f", state.netResult),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = if (state.netResult >= 0) RaptechColors.WinSuccess else RaptechColors.LossDanger
                )
            }
        }

        // Row 3: Streaks & Drawdown
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            MetricItem("Streak", "${state.currentStreak}", if (state.currentStreak >= 0) RaptechColors.WinSuccess else RaptechColors.LossDanger)
            MetricItem("Best Streak", "+${state.bestPositiveStreak}", RaptechColors.WinSuccess)
            MetricItem("Worst Streak", "${state.longestNegativeStreak}", RaptechColors.LossDanger)
            MetricItem("Drawdown", String.format(Locale.US, "%.4f", state.largestDrawdown), RaptechColors.LossDanger)
        }
    }
}

@Composable
private fun MetricItem(
    label: String,
    value: String,
    valueColor: Color
) {
    Column {
        Text(text = label, fontSize = 9.sp, color = RaptechColors.TextSecondary)
        Text(
            text = value,
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
            fontFamily = FontFamily.Monospace,
            color = valueColor
        )
    }
}
