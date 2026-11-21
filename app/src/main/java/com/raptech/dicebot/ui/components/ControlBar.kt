package com.raptech.dicebot.ui.components

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
import com.raptech.dicebot.ui.theme.RaptechColors

@Composable
fun ControlBar(
    state: DicebotUiState,
    onStart: () -> Unit,
    onPause: () -> Unit,
    onResume: () -> Unit,
    onStop: () -> Unit,
    onRefreshBalance: () -> Unit,
    onToggleStopOnWin: () -> Unit,
    onResetAll: () -> Unit,
    onResetStats: () -> Unit,
    onResetSeed: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(RaptechColors.SurfaceWhite)
            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(topStart = 8.dp, topEnd = 8.dp))
            .padding(horizontal = 8.dp, vertical = 6.dp)
    ) {
        // Row 1: Reset & Quick Utility Controls
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(5.dp)
        ) {
            ControlButton(
                text = "RESET ALL",
                bgColor = RaptechColors.SurfaceLight,
                borderColor = RaptechColors.BorderSubtle,
                textColor = RaptechColors.TextPrimary,
                fontSize = 10.5.sp,
                verticalPadding = 7.dp,
                modifier = Modifier.weight(1f),
                onClick = onResetAll
            )

            ControlButton(
                text = "RESET STATS",
                bgColor = RaptechColors.SurfaceLight,
                borderColor = RaptechColors.BorderSubtle,
                textColor = RaptechColors.TextPrimary,
                fontSize = 10.5.sp,
                verticalPadding = 7.dp,
                modifier = Modifier.weight(1f),
                onClick = onResetStats
            )

            ControlButton(
                text = "RESET SEED",
                bgColor = RaptechColors.SurfaceLight,
                borderColor = RaptechColors.BorderSubtle,
                textColor = RaptechColors.TextPrimary,
                fontSize = 10.5.sp,
                verticalPadding = 7.dp,
                modifier = Modifier.weight(1f),
                onClick = onResetSeed
            )

            ControlButton(
                text = "REFRESH BAL",
                bgColor = RaptechColors.SurfaceLight,
                borderColor = RaptechColors.BorderSubtle,
                textColor = RaptechColors.OrangePrimary,
                fontSize = 10.5.sp,
                verticalPadding = 7.dp,
                modifier = Modifier.weight(1f),
                onClick = onRefreshBalance
            )
        }

        Spacer(modifier = Modifier.height(5.dp))

        // Row 2: Primary Engine Controls (Start/Stop, Pause/Resume, Stop On Win)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(5.dp)
        ) {
            // Start / Stop Main Action Button
            if (!state.isRunning) {
                ControlButton(
                    text = "START",
                    bgColor = RaptechColors.OrangePrimary,
                    textColor = Color.White,
                    fontSize = 12.sp,
                    verticalPadding = 9.dp,
                    modifier = Modifier.weight(1.3f),
                    onClick = onStart
                )
            } else {
                ControlButton(
                    text = "STOP",
                    bgColor = RaptechColors.LossDanger,
                    textColor = Color.White,
                    fontSize = 12.sp,
                    verticalPadding = 9.dp,
                    modifier = Modifier.weight(1.3f),
                    onClick = onStop
                )
            }

            // Pause / Resume Button (when running)
            if (state.isRunning) {
                if (state.isPaused) {
                    ControlButton(
                        text = "RESUME",
                        bgColor = RaptechColors.OrangePrimary,
                        textColor = Color.White,
                        fontSize = 11.5.sp,
                        verticalPadding = 9.dp,
                        modifier = Modifier.weight(1.1f),
                        onClick = onResume
                    )
                } else {
                    ControlButton(
                        text = "PAUSE",
                        bgColor = RaptechColors.OrangeSoft,
                        borderColor = RaptechColors.OrangeBorder,
                        textColor = RaptechColors.OrangePrimary,
                        fontSize = 11.5.sp,
                        verticalPadding = 9.dp,
                        modifier = Modifier.weight(1.1f),
                        onClick = onPause
                    )
                }
            }

            // Stop on Win Mode Button
            ControlButton(
                text = if (state.stopOnWin) "WIN-STOP [ON]" else "STOP ON WIN",
                bgColor = if (state.stopOnWin) RaptechColors.OrangeSoft else RaptechColors.SurfaceLight,
                borderColor = if (state.stopOnWin) RaptechColors.OrangeBorder else RaptechColors.BorderSubtle,
                textColor = if (state.stopOnWin) RaptechColors.OrangePrimary else RaptechColors.TextSecondary,
                fontSize = 11.sp,
                verticalPadding = 9.dp,
                modifier = Modifier.weight(1.2f),
                onClick = onToggleStopOnWin
            )
        }

        Spacer(modifier = Modifier.height(4.dp))

        // Row 3: Status Info Line
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "${state.selectedPlatform.displayName} | ${state.statusMessage}",
                color = RaptechColors.TextSecondary,
                fontSize = 10.sp,
                maxLines = 1,
                modifier = Modifier.weight(1f, fill = false)
            )
            Text(
                text = "Speed: ${state.speedBps} bps",
                color = RaptechColors.OrangePrimary,
                fontSize = 10.sp,
                fontWeight = FontWeight.SemiBold,
                fontFamily = FontFamily.Monospace
            )
        }
    }
}

@Composable
private fun ControlButton(
    text: String,
    bgColor: Color,
    textColor: Color,
    modifier: Modifier = Modifier,
    borderColor: Color? = null,
    fontSize: androidx.compose.ui.unit.TextUnit = 11.sp,
    verticalPadding: androidx.compose.ui.unit.Dp = 8.dp,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(bgColor)
            .then(
                if (borderColor != null) Modifier.border(1.dp, borderColor, RoundedCornerShape(6.dp))
                else Modifier
            )
            .clickable { onClick() }
            .padding(vertical = verticalPadding),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = textColor,
            fontSize = fontSize,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.SansSerif,
            maxLines = 1
        )
    }
}
