package com.raptech.dicebot.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raptech.dicebot.R
import com.raptech.dicebot.model.ChartPoint
import com.raptech.dicebot.ui.theme.RaptechColors
import java.util.Locale

/**
 * Raptech Live PnL Chart (Extension Style).
 * - Multi-colored segments: Win -> Green (RaptechColors.WinSuccess), Lose -> Red (RaptechColors.LossDanger).
 * - Dynamic scaling with zero-reference baseline and subtle grid lines.
 * - Max buffer capacity: 200 records (Ring Buffer).
 * - Active glowing head indicator on the latest bet.
 */
@Composable
fun LiveChart(
    points: List<ChartPoint>,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(RaptechColors.SurfaceWhite)
            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(8.dp))
            .padding(8.dp)
    ) {
        // Header Bar
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                painter = painterResource(id = R.drawable.ic_chart_pnl),
                contentDescription = null,
                tint = RaptechColors.OrangePrimary,
                modifier = Modifier.size(16.dp)
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = "Live PnL Chart",
                color = RaptechColors.OrangePrimary,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.SansSerif
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "${points.size}/200 records",
                color = RaptechColors.TextMuted,
                fontSize = 10.sp
            )

            Spacer(modifier = Modifier.weight(1f))

            if (points.isNotEmpty()) {
                val latestPnl = points.last().netResult
                val isProfit = latestPnl >= 0
                val pnlColor = if (isProfit) RaptechColors.WinSuccess else RaptechColors.LossDanger
                val pnlBg = if (isProfit) RaptechColors.WinBackground else RaptechColors.LossBackground
                val pnlBorder = if (isProfit) RaptechColors.WinBorder else RaptechColors.LossBorder

                Surface(
                    shape = RoundedCornerShape(4.dp),
                    color = pnlBg,
                    border = BorderStroke(1.dp, pnlBorder)
                ) {
                    Text(
                        text = "PnL: ${String.format(Locale.US, "%+.6f", latestPnl)}",
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        color = pnlColor,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(6.dp))

        // Chart Canvas Box
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(160.dp)
                .clip(RoundedCornerShape(6.dp))
                .background(RaptechColors.SurfaceLight)
                .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                .padding(2.dp)
        ) {
            if (points.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Grafik PnL siap. Klik [START] untuk memulai.",
                        color = RaptechColors.TextMuted,
                        fontSize = 11.sp
                    )
                }
            } else {
                Canvas(modifier = Modifier.fillMaxSize()) {
                    val width = size.width
                    val height = size.height

                    val padX = 10.dp.toPx()
                    val padY = 16.dp.toPx()
                    val usableW = (width - (padX * 2)).coerceAtLeast(1f)
                    val usableH = (height - (padY * 2)).coerceAtLeast(1f)

                    val rawMin = points.minOf { it.netResult }
                    val rawMax = points.maxOf { it.netResult }

                    // Always anchor zero line for clear profit/loss context
                    val minVal = minOf(0.0, rawMin)
                    val maxVal = maxOf(0.0, rawMax)
                    val rawSpan = (maxVal - minVal).coerceAtLeast(0.00002)
                    val yPad = rawSpan * 0.12
                    val plotMin = minVal - yPad
                    val plotMax = maxVal + yPad
                    val plotSpan = (plotMax - plotMin).coerceAtLeast(0.00001)

                    fun getY(value: Double): Float {
                        val ratio = ((value - plotMin) / plotSpan).toFloat()
                        return (padY + (1f - ratio) * usableH).coerceIn(padY, height - padY)
                    }

                    // 1. Subtle horizontal grid lines (3 divisions)
                    for (i in 1..3) {
                        val gridY = padY + (usableH * (i / 4f))
                        drawLine(
                            color = RaptechColors.BorderSubtle.copy(alpha = 0.6f),
                            start = Offset(padX, gridY),
                            end = Offset(width - padX, gridY),
                            strokeWidth = 0.8.dp.toPx()
                        )
                    }

                    // 2. Zero reference baseline (dashed slate line)
                    val zeroY = getY(0.0)
                    drawLine(
                        color = RaptechColors.BorderStrong,
                        start = Offset(padX, zeroY),
                        end = Offset(width - padX, zeroY),
                        strokeWidth = 1.dp.toPx(),
                        pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 6f), 0f)
                    )

                    // 3. Multi-colored PnL trajectory (Win: Green, Lose: Red)
                    val trajPoints = listOf(
                        ChartPoint(
                            executionIndex = 0L,
                            netResult = 0.0,
                            balance = points.first().balance,
                            isWin = true
                        )
                    ) + points

                    val stepX = usableW / (trajPoints.size - 1).coerceAtLeast(1)

                    for (i in 1 until trajPoints.size) {
                        val prevPt = trajPoints[i - 1]
                        val currPt = trajPoints[i]

                        val x0 = padX + (i - 1) * stepX
                        val y0 = getY(prevPt.netResult)
                        val x1 = padX + i * stepX
                        val y1 = getY(currPt.netResult)

                        // Raptech Extension Rule: Win -> Green (#059669), Lose -> Red (#DC2626)
                        val isWin = currPt.isWin || (currPt.netResult >= prevPt.netResult)
                        val segmentColor = if (isWin) RaptechColors.WinSuccess else RaptechColors.LossDanger

                        drawLine(
                            color = segmentColor,
                            start = Offset(x0, y0),
                            end = Offset(x1, y1),
                            strokeWidth = 2.4.dp.toPx(),
                            cap = StrokeCap.Round
                        )

                        // Small vertex joint dots for small dataset clarity
                        if (trajPoints.size <= 40) {
                            drawCircle(
                                color = segmentColor,
                                radius = 2.dp.toPx(),
                                center = Offset(x1, y1)
                            )
                        }
                    }

                    // 4. Active head indicator on the latest point
                    val lastIdx = trajPoints.size - 1
                    val lastX = padX + lastIdx * stepX
                    val lastY = getY(trajPoints.last().netResult)
                    val lastIsWin = trajPoints.last().let {
                        it.isWin || (trajPoints.size >= 2 && it.netResult >= trajPoints[trajPoints.size - 2].netResult)
                    }
                    val headColor = if (lastIsWin) RaptechColors.WinSuccess else RaptechColors.LossDanger

                    // Outer pulse halo
                    drawCircle(
                        color = headColor.copy(alpha = 0.25f),
                        radius = 6.dp.toPx(),
                        center = Offset(lastX, lastY)
                    )
                    // White border ring
                    drawCircle(
                        color = RaptechColors.SurfaceWhite,
                        radius = 3.8.dp.toPx(),
                        center = Offset(lastX, lastY)
                    )
                    // Core point
                    drawCircle(
                        color = headColor,
                        radius = 2.4.dp.toPx(),
                        center = Offset(lastX, lastY)
                    )
                }

                // Overlay Max & Min indicators (Top-End)
                val maxPnl = points.maxOf { it.netResult }
                val minPnl = points.minOf { it.netResult }

                Row(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(6.dp),
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Surface(
                        shape = RoundedCornerShape(3.dp),
                        color = RaptechColors.WinBackground,
                        border = BorderStroke(1.dp, RaptechColors.WinBorder)
                    ) {
                        Text(
                            text = "Max: ${String.format(Locale.US, "%+.6f", maxPnl)}",
                            fontSize = 8.5.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            color = RaptechColors.WinSuccess,
                            modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp)
                        )
                    }

                    Surface(
                        shape = RoundedCornerShape(3.dp),
                        color = RaptechColors.LossBackground,
                        border = BorderStroke(1.dp, RaptechColors.LossBorder)
                    ) {
                        Text(
                            text = "Min: ${String.format(Locale.US, "%+.6f", minPnl)}",
                            fontSize = 8.5.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            color = RaptechColors.LossDanger,
                            modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp)
                        )
                    }
                }
            }
        }
    }
}
