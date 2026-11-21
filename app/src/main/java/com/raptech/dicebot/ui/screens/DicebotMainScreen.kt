package com.raptech.dicebot.ui.screens

import android.content.res.Configuration
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raptech.dicebot.model.CasinoPlatform
import com.raptech.dicebot.model.DicebotUiState
import com.raptech.dicebot.model.StrategyPreset
import com.raptech.dicebot.ui.components.BatteryOptimizationDialog
import com.raptech.dicebot.ui.components.CasinoWebLoginDialog
import com.raptech.dicebot.ui.components.CoinSelectorDialog
import com.raptech.dicebot.ui.components.ControlBar
import com.raptech.dicebot.ui.components.HeaderBar
import com.raptech.dicebot.ui.components.HistoryTable
import com.raptech.dicebot.ui.components.LiveChart
import com.raptech.dicebot.ui.components.LiveLogConsole
import com.raptech.dicebot.ui.components.LuaEditor
import com.raptech.dicebot.ui.components.MetricsDashboard
import com.raptech.dicebot.ui.components.RiskConfigDialog
import com.raptech.dicebot.ui.theme.RaptechColors

@Composable
fun DicebotMainScreen(
    state: DicebotUiState,
    onStart: () -> Unit,
    onPause: () -> Unit,
    onResume: () -> Unit,
    onStop: () -> Unit,
    onRefreshBalance: () -> Unit,
    onToggleStopOnWin: () -> Unit,
    onPlatformSelected: (CasinoPlatform) -> Unit,
    onScriptChanged: (String) -> Unit,
    onPresetSelected: (StrategyPreset) -> Unit,
    onSessionCaptured: (String) -> Unit,
    onLogout: () -> Unit,
    onSaveRiskLimits: (stopLoss: Double?, takeProfit: Double?, maxBet: Double?) -> Unit,
    onRequestBatteryWhitelist: () -> Unit,
    onCurrencySelected: (String) -> Unit = {},
    onDetectCoins: () -> Unit = {},
    onResetAll: () -> Unit = {},
    onResetStats: () -> Unit = {},
    onResetSeed: () -> Unit = {},
    onCheckUpdate: () -> Unit = {},
    onQuitApp: () -> Unit = {},
    onClearLogs: () -> Unit = {},
    showBatteryOptimizationPrompt: Boolean = false,
    onDismissBatteryPrompt: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    val configuration = LocalConfiguration.current
    val isLandscape = configuration.orientation == Configuration.ORIENTATION_LANDSCAPE

    var selectedTab by remember { mutableIntStateOf(0) }
    var showConfigDialog by remember { mutableStateOf(false) }
    var showRiskDialog by remember { mutableStateOf(false) }
    var showCoinDialog by remember { mutableStateOf(false) }
    var isMetricsCollapsed by remember { mutableStateOf(false) }

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(RaptechColors.Background)
            .statusBarsPadding()
            .navigationBarsPadding()
    ) {
        if (isLandscape) {
            // === Landscape Mode: Dual-Pane Split View ===
            Row(modifier = Modifier.fillMaxSize()) {
                // Left Pane: Header + 12 Metrics + Live Chart + History
                Column(
                    modifier = Modifier
                        .weight(1.1f)
                        .fillMaxHeight()
                        .padding(start = 8.dp, top = 6.dp, bottom = 6.dp, end = 4.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    HeaderBar(
                        state = state,
                        onPlatformSelected = onPlatformSelected,
                        onOpenConfig = { showConfigDialog = true },
                        onOpenRisk = { showRiskDialog = true },
                        onOpenCoinSelector = { showCoinDialog = true },
                        onCheckUpdate = onCheckUpdate,
                        onQuitApp = onQuitApp
                    )
                    MetricsDashboard(
                        state = state,
                        onOpenCoinSelector = { showCoinDialog = true },
                        isCollapsed = isMetricsCollapsed,
                        onToggleCollapse = { isMetricsCollapsed = !isMetricsCollapsed }
                    )
                    LiveChart(points = state.chartPoints)
                    HistoryTable(
                        history = state.history,
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f)
                    )
                }

                // Right Pane: LUA Editor / Logs Tabs + Bottom Sticky Controls
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .padding(start = 4.dp, top = 6.dp, bottom = 6.dp, end = 8.dp)
                ) {
                    // Right Tab Bar
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(6.dp))
                            .background(RaptechColors.SurfaceWhite)
                            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                            .padding(3.dp),
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        TabButton(
                            title = "LUA Editor",
                            isSelected = selectedTab == 0,
                            modifier = Modifier.weight(1f)
                        ) { selectedTab = 0 }

                        TabButton(
                            title = "Console (${state.liveLogs.size})",
                            isSelected = selectedTab == 1,
                            modifier = Modifier.weight(1f)
                        ) { selectedTab = 1 }
                    }

                    Spacer(modifier = Modifier.height(6.dp))

                    Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
                        when (selectedTab) {
                            0 -> LuaEditor(
                                script = state.luaScript,
                                onScriptChange = onScriptChanged,
                                onPresetSelected = onPresetSelected,
                                syntaxResult = state.syntaxValidation,
                                modifier = Modifier.fillMaxSize()
                            )
                            1 -> LiveLogConsole(
                                logs = state.liveLogs,
                                onClearLogs = onClearLogs,
                                modifier = Modifier.fillMaxSize()
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(6.dp))

                    ControlBar(
                        state = state,
                        onStart = onStart,
                        onPause = onPause,
                        onResume = onResume,
                        onStop = onStop,
                        onRefreshBalance = onRefreshBalance,
                        onToggleStopOnWin = onToggleStopOnWin,
                        onResetAll = onResetAll,
                        onResetStats = onResetStats,
                        onResetSeed = onResetSeed
                    )
                }
            }
        } else {
            // === Portrait Mode: Responsive Mobile Tabs ===
            Column(modifier = Modifier.fillMaxSize()) {
                HeaderBar(
                    state = state,
                    onPlatformSelected = onPlatformSelected,
                    onOpenConfig = { showConfigDialog = true },
                    onOpenRisk = { showRiskDialog = true },
                    onOpenCoinSelector = { showCoinDialog = true },
                    onCheckUpdate = onCheckUpdate,
                    onQuitApp = onQuitApp
                )

                Column(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .padding(horizontal = 8.dp)
                ) {
                    Spacer(modifier = Modifier.height(6.dp))

                    // 12-Metrics Financial Dashboard
                    MetricsDashboard(
                        state = state,
                        onOpenCoinSelector = { showCoinDialog = true },
                        isCollapsed = isMetricsCollapsed,
                        onToggleCollapse = { isMetricsCollapsed = !isMetricsCollapsed }
                    )

                    Spacer(modifier = Modifier.height(6.dp))

                    // Tab Navigation Bar
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(6.dp))
                            .background(RaptechColors.SurfaceWhite)
                            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                            .padding(3.dp),
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        TabButton(
                            title = "Chart & Roll",
                            isSelected = selectedTab == 0,
                            modifier = Modifier.weight(1f)
                        ) { selectedTab = 0 }

                        TabButton(
                            title = "LUA Editor",
                            isSelected = selectedTab == 1,
                            modifier = Modifier.weight(1f)
                        ) { selectedTab = 1 }

                        TabButton(
                            title = "Console (${state.liveLogs.size})",
                            isSelected = selectedTab == 2,
                            modifier = Modifier.weight(1f)
                        ) { selectedTab = 2 }
                    }

                    Spacer(modifier = Modifier.height(6.dp))

                    // Tab Pages
                    when (selectedTab) {
                        0 -> {
                            Column(
                                modifier = Modifier.fillMaxSize(),
                                verticalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                LiveChart(points = state.chartPoints)
                                HistoryTable(
                                    history = state.history,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .weight(1f)
                                )
                            }
                        }
                        1 -> {
                            LuaEditor(
                                script = state.luaScript,
                                onScriptChange = onScriptChanged,
                                onPresetSelected = onPresetSelected,
                                syntaxResult = state.syntaxValidation,
                                modifier = Modifier.fillMaxSize()
                            )
                        }
                        2 -> {
                            LiveLogConsole(
                                logs = state.liveLogs,
                                onClearLogs = onClearLogs,
                                modifier = Modifier.fillMaxSize()
                            )
                        }
                    }
                }

                // Sticky Bottom Control Bar
                ControlBar(
                    state = state,
                    onStart = onStart,
                    onPause = onPause,
                    onResume = onResume,
                    onStop = onStop,
                    onRefreshBalance = onRefreshBalance,
                    onToggleStopOnWin = onToggleStopOnWin,
                    onResetAll = onResetAll,
                    onResetStats = onResetStats,
                    onResetSeed = onResetSeed
                )
            }
        }

        // Modal 1: In-App Web Browser Direct Casino Login
        if (showConfigDialog) {
            CasinoWebLoginDialog(
                platform = state.selectedPlatform,
                isAuthenticated = state.isPlatformAuthenticated,
                onDismiss = { showConfigDialog = false },
                onSessionCaptured = { token ->
                    onSessionCaptured(token)
                },
                onLogout = onLogout
            )
        }

        // Modal 2: Risk Management Circuit Breakers
        if (showRiskDialog) {
            RiskConfigDialog(
                currentStopLoss = state.stopLossLimit,
                currentTakeProfit = state.takeProfitLimit,
                currentMaxBet = state.maxBetLimit,
                currency = state.selectedCurrency,
                onDismiss = { showRiskDialog = false },
                onSaveLimits = onSaveRiskLimits
            )
        }

        // Modal 3: Battery Optimization Whitelist Guide
        if (showBatteryOptimizationPrompt) {
            BatteryOptimizationDialog(
                onDismiss = onDismissBatteryPrompt,
                onWhitelistRequested = onRequestBatteryWhitelist
            )
        }

        // Modal 4: Select Coin & Auto-Detect Casino Balances
        if (showCoinDialog) {
            CoinSelectorDialog(
                platform = state.selectedPlatform,
                selectedCurrency = state.selectedCurrency,
                availableCoins = state.availableCoins,
                isDetecting = state.isDetectingCoins,
                onDismiss = { showCoinDialog = false },
                onCoinSelected = onCurrencySelected,
                onRefreshCoins = onDetectCoins
            )
        }
    }
}

@Composable
private fun TabButton(
    title: String,
    isSelected: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(5.dp))
            .background(if (isSelected) RaptechColors.OrangePrimary else RaptechColors.SurfaceLight)
            .then(
                if (!isSelected) Modifier.border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(5.dp))
                else Modifier
            )
            .clickable { onClick() }
            .padding(vertical = 7.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = title,
            color = if (isSelected) Color.White else RaptechColors.TextSecondary,
            fontSize = 11.sp,
            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium
        )
    }
}
