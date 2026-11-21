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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Public
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raptech.dicebot.R
import com.raptech.dicebot.model.CasinoPlatform
import com.raptech.dicebot.model.DicebotUiState
import com.raptech.dicebot.ui.theme.RaptechColors

@Composable
fun HeaderBar(
    state: DicebotUiState,
    onPlatformSelected: (CasinoPlatform) -> Unit,
    onOpenConfig: () -> Unit,
    onOpenRisk: () -> Unit,
    onOpenCoinSelector: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    var platformMenuExpanded by remember { mutableStateOf(false) }
    val hasActiveRiskLimits = state.stopLossLimit != null || state.takeProfitLimit != null || state.maxBetLimit != null

    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(RaptechColors.SurfaceWhite)
            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(bottomStart = 8.dp, bottomEnd = 8.dp))
            .padding(horizontal = 10.dp, vertical = 7.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        // Line 1: App Branding & Live Engine Status + Coin Selector Badge
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(
                    painter = painterResource(id = R.drawable.ic_dice),
                    contentDescription = null,
                    tint = RaptechColors.OrangePrimary,
                    modifier = Modifier.size(20.dp)
                )
                Text(
                    text = "RAPTECH AUTOMATION",
                    color = RaptechColors.TextPrimary,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.SansSerif,
                    letterSpacing = 0.5.sp
                )
            }

            // Right side: Coin Selector Chip & Engine Status
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(5.dp)
            ) {
                // Interactive Coin Selector Pill with Soft Orange Tint
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(5.dp))
                        .background(RaptechColors.OrangeSoft)
                        .border(1.dp, RaptechColors.OrangeBorder, RoundedCornerShape(5.dp))
                        .clickable { onOpenCoinSelector() }
                        .padding(horizontal = 7.dp, vertical = 3.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Icon(
                            painter = painterResource(id = R.drawable.ic_wallet_coin),
                            contentDescription = "Pilih Koin",
                            tint = RaptechColors.OrangePrimary,
                            modifier = Modifier.size(13.dp)
                        )
                        Text(
                            text = state.selectedCurrency,
                            color = RaptechColors.OrangePrimary,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )
                        Icon(
                            imageVector = Icons.Default.ArrowDropDown,
                            contentDescription = null,
                            tint = RaptechColors.OrangePrimary,
                            modifier = Modifier.size(14.dp)
                        )
                    }
                }

                // Engine Running / Ready Indicator
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(5.dp))
                        .background(if (state.isRunning) RaptechColors.OrangeSoft else RaptechColors.SurfaceLight)
                        .border(1.dp, if (state.isRunning) RaptechColors.OrangeBorder else RaptechColors.BorderSubtle, RoundedCornerShape(5.dp))
                        .padding(horizontal = 6.dp, vertical = 3.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .clip(CircleShape)
                                .background(
                                    when {
                                        state.isRunning && !state.isPaused -> RaptechColors.WinSuccess
                                        state.isPaused -> RaptechColors.OrangePrimary
                                        else -> RaptechColors.TextMuted
                                    }
                                )
                        )
                        Text(
                            text = if (state.isRunning) (if (state.isPaused) "PAUSED" else "RUNNING") else "READY",
                            color = if (state.isRunning) RaptechColors.OrangePrimary else RaptechColors.TextSecondary,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }
        }

        // Line 2: Responsive Action Chips (Platform, Login, Risk)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Platform Dropdown Chip
            Box(modifier = Modifier.weight(1.3f)) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(6.dp))
                        .background(RaptechColors.SurfaceLight)
                        .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                        .clickable { platformMenuExpanded = true }
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = state.selectedPlatform.displayName,
                        color = RaptechColors.TextPrimary,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1
                    )
                    Icon(
                        imageVector = Icons.Default.ArrowDropDown,
                        contentDescription = null,
                        tint = RaptechColors.OrangePrimary,
                        modifier = Modifier.size(16.dp)
                    )
                }

                DropdownMenu(
                    expanded = platformMenuExpanded,
                    onDismissRequest = { platformMenuExpanded = false },
                    modifier = Modifier
                        .background(RaptechColors.SurfaceWhite)
                        .border(1.dp, RaptechColors.BorderSubtle)
                ) {
                    CasinoPlatform.values().forEach { platform ->
                        DropdownMenuItem(
                            text = {
                                Text(
                                    text = "${platform.displayName} (${platform.defaultCurrency})",
                                    color = if (platform == state.selectedPlatform) RaptechColors.OrangePrimary else RaptechColors.TextPrimary,
                                    fontSize = 12.sp,
                                    fontWeight = if (platform == state.selectedPlatform) FontWeight.Bold else FontWeight.Normal
                                )
                            },
                            onClick = {
                                onPlatformSelected(platform)
                                platformMenuExpanded = false
                            }
                        )
                    }
                }
            }

            // Direct Web Login / Status Chip
            Box(
                modifier = Modifier
                    .weight(1.2f)
                    .clip(RoundedCornerShape(6.dp))
                    .background(
                        if (state.isPlatformAuthenticated) RaptechColors.WinBackground
                        else RaptechColors.SurfaceLight
                    )
                    .border(
                        1.dp,
                        if (state.isPlatformAuthenticated) RaptechColors.WinBorder
                        else RaptechColors.BorderSubtle,
                        RoundedCornerShape(6.dp)
                    )
                    .clickable { onOpenConfig() }
                    .padding(horizontal = 8.dp, vertical = 6.dp),
                contentAlignment = Alignment.Center
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(6.dp)
                            .clip(CircleShape)
                            .background(
                                if (state.isPlatformAuthenticated) RaptechColors.WinSuccess
                                else RaptechColors.OrangePrimary
                            )
                    )
                    Icon(
                        imageVector = Icons.Default.Public,
                        contentDescription = "Autentikasi Akun",
                        tint = if (state.isPlatformAuthenticated) RaptechColors.WinSuccess else RaptechColors.OrangePrimary,
                        modifier = Modifier.size(13.dp)
                    )
                    Text(
                        text = if (state.isPlatformAuthenticated) "Online" else "Login Sesi",
                        color = if (state.isPlatformAuthenticated) RaptechColors.WinSuccess else RaptechColors.OrangePrimary,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            // Risk Protection Chip
            Box(
                modifier = Modifier
                    .weight(1.1f)
                    .clip(RoundedCornerShape(6.dp))
                    .background(
                        if (hasActiveRiskLimits) RaptechColors.OrangeSoft
                        else RaptechColors.SurfaceLight
                    )
                    .border(
                        1.dp,
                        if (hasActiveRiskLimits) RaptechColors.OrangeBorder
                        else RaptechColors.BorderSubtle,
                        RoundedCornerShape(6.dp)
                    )
                    .clickable { onOpenRisk() }
                    .padding(horizontal = 8.dp, vertical = 6.dp),
                contentAlignment = Alignment.Center
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Icon(
                        painter = painterResource(id = R.drawable.ic_shield_risk),
                        contentDescription = "Proteksi Risiko",
                        tint = if (hasActiveRiskLimits) RaptechColors.OrangePrimary else RaptechColors.TextMuted,
                        modifier = Modifier.size(13.dp)
                    )
                    Text(
                        text = if (hasActiveRiskLimits) "Proteksi [ON]" else "Proteksi",
                        color = if (hasActiveRiskLimits) RaptechColors.OrangePrimary else RaptechColors.TextSecondary,
                        fontSize = 10.sp,
                        fontWeight = if (hasActiveRiskLimits) FontWeight.Bold else FontWeight.Medium
                    )
                }
            }
        }
    }
}
