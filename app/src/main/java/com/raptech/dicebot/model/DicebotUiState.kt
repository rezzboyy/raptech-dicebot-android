package com.raptech.dicebot.model

const val DEFAULT_SAMPLE_SCRIPT = """chance = 49.5
bethigh = true
basebet = 0.00000001
nextbet = basebet

function dobet()
  if win then
    nextbet = basebet
  else
    nextbet = previousbet * 2
  end
end"""

data class DicebotUiState(
    val isRunning: Boolean = false,
    val isPaused: Boolean = false,
    val selectedPlatform: CasinoPlatform = CasinoPlatform.TRONPICK,
    val selectedCurrency: String = "TRX",
    val availableCoins: List<CoinBalance> = emptyList(),
    val isDetectingCoins: Boolean = false,
    val isCoinSelectorOpen: Boolean = false,
    val maxRecords: Int = 200,
    val balance: Double = 0.0,
    val initialBalance: Double = 0.0,
    val minBalance: Double = 0.0,
    val maxBalance: Double = 0.0,
    val netResult: Double = 0.00000000,
    val netResultPercent: Double = 0.0,
    val totalVolume: Double = 0.00000000,
    val executions: Long = 0,
    val positiveOutcomes: Long = 0,
    val negativeOutcomes: Long = 0,
    val currentStreak: Int = 0,
    val bestPositiveStreak: Int = 0,
    val longestNegativeStreak: Int = 0,
    val peakAmount: Double = 0.00000000,
    val largestDrawdown: Double = 0.00000000,
    val minResult: Double = 0.00000000,
    val maxResult: Double = 0.00000000,
    val speedBps: Double = 0.0,
    val sessionElapsedTimeMs: Long = 0L,
    val history: List<BetRecord> = emptyList(),
    val chartPoints: List<ChartPoint> = emptyList(),
    val liveLogs: List<LuaLogEntry> = emptyList(),
    val luaScript: String = DEFAULT_SAMPLE_SCRIPT,
    val scriptLanguage: ScriptLanguage = ScriptLanguage.LUA,
    val scriptName: String = "Editor LUA",
    val statusMessage: String = "Ready",
    val isPlatformAuthenticated: Boolean = false,
    val platformUsername: String = "",
    val syntaxValidation: SyntaxValidationResult? = null,
    val stopOnWin: Boolean = false,
    val stopLossLimit: Double? = null,
    val takeProfitLimit: Double? = null,
    val maxBetLimit: Double? = null,
    val isRiskModalOpen: Boolean = false
) {
    val currentTrend: Int
        get() = currentStreak
}

