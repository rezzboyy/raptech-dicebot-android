package com.raptech.dicebot.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raptech.dicebot.model.LuaLogEntry
import com.raptech.dicebot.ui.theme.RaptechColors

@Composable
fun LiveLogConsole(
    logs: List<LuaLogEntry>,
    onClearLogs: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    val listState = rememberLazyListState()

    LaunchedEffect(logs.size) {
        if (logs.isNotEmpty()) {
            listState.animateScrollToItem(logs.size - 1)
        }
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(RaptechColors.SurfaceWhite)
            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(8.dp))
            .padding(8.dp)
    ) {
        // Log Header Bar
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Console (${logs.size})",
                color = RaptechColors.OrangePrimary,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.SansSerif
            )

            // Clear Log Button
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(4.dp))
                    .background(RaptechColors.SurfaceLight)
                    .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(4.dp))
                    .clickable { onClearLogs() }
                    .padding(horizontal = 8.dp, vertical = 2.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "Clear",
                    color = RaptechColors.TextSecondary,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.SemiBold,
                    fontFamily = FontFamily.SansSerif
                )
            }
        }

        Spacer(modifier = Modifier.height(6.dp))

        // Log Console Box
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .clip(RoundedCornerShape(6.dp))
                .background(RaptechColors.SurfaceLight)
                .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                .padding(6.dp)
        ) {
            if (logs.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Konsol kosong.\nOutput print(...) akan tampil di sini.",
                        color = RaptechColors.TextMuted,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center
                    )
                }
            } else {
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(2.dp)
                ) {
                    items(logs) { log ->
                        val textColor = when {
                            log.isError -> RaptechColors.LossDanger
                            log.message.contains("WIN", ignoreCase = true) || log.message.contains("PROFIT", ignoreCase = true) -> RaptechColors.WinSuccess
                            log.message.contains("LOSE", ignoreCase = true) || log.message.contains("STOP", ignoreCase = true) -> RaptechColors.LossDanger
                            log.message.contains("TARGET", ignoreCase = true) -> RaptechColors.OrangePrimary
                            else -> RaptechColors.TextPrimary
                        }

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            Text(
                                text = log.formattedTime,
                                color = RaptechColors.TextMuted,
                                fontSize = 9.sp,
                                fontFamily = FontFamily.Monospace
                            )
                            Text(
                                text = log.message,
                                color = textColor,
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = if (log.isError) FontWeight.Bold else FontWeight.Normal
                            )
                        }
                    }
                }
            }
        }
    }
}
