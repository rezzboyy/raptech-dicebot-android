package com.raptech.dicebot.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import com.raptech.dicebot.MainActivity
import com.raptech.dicebot.R
import com.raptech.dicebot.data.repository.CasinoRepository
import com.raptech.dicebot.engine.LuaEngine
import com.raptech.dicebot.model.BetRecord
import com.raptech.dicebot.model.CasinoPlatform
import com.raptech.dicebot.model.ChartPoint
import com.raptech.dicebot.model.DicebotUiState
import com.raptech.dicebot.model.LuaLogEntry
import com.raptech.dicebot.model.StrategyPreset
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.Locale

class DicebotForegroundService : Service() {

    private val binder = LocalBinder()
    private val serviceScope = CoroutineScope(Dispatchers.Default + Job())
    private var executionJob: Job? = null
    private var wakeLock: PowerManager.WakeLock? = null

    private lateinit var casinoRepository: CasinoRepository

    private val luaEngine = LuaEngine(
        onLog = { msg -> addLiveLog(msg, isError = false) },
        onStopRequested = { stopBot() },
        onStartRequested = { startBot() },
        onResumeRequested = { resumeBot() },
        onStopOnWinRequested = { toggleStopOnWin() },
        onCheckBalanceRequested = { refreshBalance() },
        onResetRequested = { resetStats() },
        onResetStatsRequested = { resetStats() },
        onResetAllRequested = { resetAll() },
        onResetSeedRequested = { resetSeed() },
        onResetChartRequested = {
            _uiState.update { it.copy(chartPoints = emptyList()) }
        },
        onResetHistoryRequested = {
            _uiState.update { it.copy(history = emptyList()) }
        },
        onResetLogRequested = {
            _uiState.update { it.copy(liveLogs = emptyList()) }
        }
    )

    inner class LocalBinder : Binder() {
        fun getService(): DicebotForegroundService = this@DicebotForegroundService
    }

    override fun onBind(intent: Intent?): IBinder = binder

    companion object {
        const val CHANNEL_ID = "dicebot_exec_channel"
        const val NOTIFICATION_ID = 888

        const val ACTION_START = "ACTION_START"
        const val ACTION_PAUSE = "ACTION_PAUSE"
        const val ACTION_RESUME = "ACTION_RESUME"
        const val ACTION_STOP = "ACTION_STOP"

        private val _uiState = MutableStateFlow(DicebotUiState())
        val uiState: StateFlow<DicebotUiState> = _uiState.asStateFlow()
    }

    override fun onCreate() {
        super.onCreate()
        casinoRepository = CasinoRepository(this)
        createNotificationChannel()
        _uiState.update {
            it.copy(isPlatformAuthenticated = casinoRepository.hasCredentials(it.selectedPlatform))
        }
        detectAvailableCoins(autoSelectActive = false)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startBot()
            ACTION_PAUSE -> pauseBot()
            ACTION_RESUME -> resumeBot()
            ACTION_STOP -> stopBot()
        }
        return START_NOT_STICKY
    }

    fun startBot() {
        if (_uiState.value.isRunning && !_uiState.value.isPaused) return

        val script = _uiState.value.luaScript

        val syntaxCheck = LuaEngine.validateSyntax(script)
        if (!syntaxCheck.isValid) {
            val err = "Sintaks LUA Error${syntaxCheck.errorLine?.let { " baris $it" } ?: ""}: ${syntaxCheck.errorMessage}"
            addLiveLog(err, isError = true)
            _uiState.update { it.copy(statusMessage = err, syntaxValidation = syntaxCheck) }
            return
        }

        acquireWakeLock()
        startForeground(NOTIFICATION_ID, buildNotification("Bot Berjalan - Menginisialisasi Engine LUA..."))

        val initRes = luaEngine.initScript(
            script = script,
            initialBalance = _uiState.value.balance,
            currency = _uiState.value.selectedCurrency,
            casino = _uiState.value.selectedPlatform.name.lowercase(),
            minBet = _uiState.value.selectedPlatform.minBet
        )

        if (initRes.isFailure) {
            val errMsg = "Gagal memuat skrip LUA: ${initRes.exceptionOrNull()?.message}"
            addLiveLog(errMsg, isError = true)
            _uiState.update { it.copy(statusMessage = errMsg) }
            stopBot()
            return
        }

        addLiveLog("⚡ Script LUA terinisialisasi. Menghubungkan ke ${_uiState.value.selectedPlatform.displayName}...", isError = false)

        _uiState.update {
            it.copy(
                isRunning = true,
                isPaused = false,
                statusMessage = "Running strategy on ${it.selectedPlatform.displayName}",
                syntaxValidation = syntaxCheck
            )
        }

        executionJob?.cancel()
        executionJob = serviceScope.launch {
            val startTime = System.currentTimeMillis() - _uiState.value.sessionElapsedTimeMs
            var lastBetDecision = luaEngine.getInitialBetDecision()

            while (isActive && _uiState.value.isRunning) {
                if (_uiState.value.isPaused) {
                    delay(200)
                    continue
                }

                val currentElapsed = System.currentTimeMillis() - startTime

                // Taruhan murni 100% mengikuti keputusan skrip LUA (Script is King)
                if (lastBetDecision.amount <= 0.0) {
                    lastBetDecision = lastBetDecision.copy(amount = 0.00000001)
                }

                // Circuit Breaker: Batasi nilai taruhan maksimum jika maxBetLimit diatur
                val maxBet = _uiState.value.maxBetLimit
                if (maxBet != null && maxBet > 0.0 && lastBetDecision.amount > maxBet) {
                    addLiveLog("⚠ Nilai taruhan (${String.format(Locale.US, "%.8f", lastBetDecision.amount)}) melebihi Max Bet Limit ($maxBet). Dibatasi ke $maxBet.", isError = true)
                    lastBetDecision = lastBetDecision.copy(amount = maxBet)
                }

                // Panggilan API taruhan melalui CasinoRepository (OkHttp / Real API / Simulation)
                val betResult = casinoRepository.placeDiceBet(
                    platform = _uiState.value.selectedPlatform,
                    amount = lastBetDecision.amount,
                    target = lastBetDecision.chance,
                    isHigh = lastBetDecision.isHigh,
                    currency = _uiState.value.selectedCurrency
                )

                if (betResult.isFailure) {
                    val err = betResult.exceptionOrNull()?.message ?: "Network error"
                    addLiveLog("⚠ $err", isError = true)
                    delay(1000)
                    continue
                }

                val betData = betResult.getOrThrow()
                val roll = betData.rollResult
                val isWin = betData.isWin
                val profit = betData.profit
                val newExecCount = _uiState.value.executions + 1
                val newBalance = if (betData.newBalance > 0) betData.newBalance else (_uiState.value.balance + profit).coerceAtLeast(0.0)
                val newNetResult = _uiState.value.netResult + profit
                val newVolume = _uiState.value.totalVolume + lastBetDecision.amount
                val newWins = _uiState.value.positiveOutcomes + (if (isWin) 1 else 0)
                val newLosses = _uiState.value.negativeOutcomes + (if (!isWin) 1 else 0)
                val nonce = if (betData.nonce > 0) betData.nonce else newExecCount

                val newStreak = if (isWin) {
                    if (_uiState.value.currentStreak > 0) _uiState.value.currentStreak + 1 else 1
                } else {
                    if (_uiState.value.currentStreak < 0) _uiState.value.currentStreak - 1 else -1
                }

                val bestPos = maxOf(_uiState.value.bestPositiveStreak, if (newStreak > 0) newStreak else 0)
                val longestNeg = minOf(_uiState.value.longestNegativeStreak, if (newStreak < 0) newStreak else 0)
                val minBal = minOf(_uiState.value.minBalance, newBalance)
                val maxBal = maxOf(_uiState.value.maxBalance, newBalance)
                val peak = maxOf(_uiState.value.peakAmount, lastBetDecision.amount)
                val drawdown = minOf(_uiState.value.largestDrawdown, newNetResult)

                val record = BetRecord(
                    executionNumber = newExecCount,
                    amount = lastBetDecision.amount,
                    targetChance = lastBetDecision.chance,
                    isHigh = lastBetDecision.isHigh,
                    rollResult = roll,
                    isWin = isWin,
                    netResult = profit,
                    nonce = nonce
                )

                // Evaluasi fungsi dobet() di VM LUA
                lastBetDecision = luaEngine.onRollCompleted(
                    lastRecord = record,
                    currentBalance = newBalance,
                    totalProfit = newNetResult,
                    totalBets = newExecCount,
                    totalWins = newWins,
                    totalLosses = newLosses,
                    totalVolume = newVolume,
                    currency = _uiState.value.selectedCurrency,
                    initialBalance = _uiState.value.initialBalance,
                    minBalance = minBal,
                    maxBalance = maxBal,
                    currentProfit = profit,
                    winStreak = if (newStreak > 0) newStreak else 0,
                    loseStreak = if (newStreak < 0) Math.abs(newStreak) else 0,
                    maxWinStreak = bestPos,
                    maxLoseStreak = Math.abs(longestNeg),
                    peakAmount = peak,
                    largestDrawdown = drawdown,
                    casino = _uiState.value.selectedPlatform.name.lowercase(),
                    minBet = _uiState.value.selectedPlatform.minBet,
                    elapsedSeconds = currentElapsed / 1000L,
                    speedBps = _uiState.value.speedBps
                )

                // Terapkan script sleep / delay jika diminta oleh LUA (sleep() atau setdelay())
                val scriptSleep = luaEngine.consumeSleepDelayMs()
                if (scriptSleep > 0) {
                    delay(scriptSleep)
                }
                val customDelay = luaEngine.getCustomScriptDelayMs()
                if (customDelay > 0) {
                    delay(customDelay)
                }

                // Update Ring Buffer data & chart
                val updatedHistory = (_uiState.value.history + record).takeLast(_uiState.value.maxRecords)
                val newChartPoint = ChartPoint(
                    executionIndex = newExecCount,
                    netResult = newNetResult,
                    balance = newBalance,
                    isWin = isWin
                )
                val updatedChartPoints = (_uiState.value.chartPoints + newChartPoint).takeLast(_uiState.value.maxRecords)

                _uiState.update {
                    it.copy(
                        balance = newBalance,
                        netResult = newNetResult,
                        netResultPercent = if (it.initialBalance > 0) (newNetResult / it.initialBalance) * 100 else 0.0,
                        totalVolume = newVolume,
                        executions = newExecCount,
                        positiveOutcomes = newWins,
                        negativeOutcomes = newLosses,
                        currentStreak = newStreak,
                        bestPositiveStreak = bestPos,
                        longestNegativeStreak = longestNeg,
                        minBalance = minBal,
                        maxBalance = maxBal,
                        peakAmount = peak,
                        largestDrawdown = drawdown,
                        sessionElapsedTimeMs = currentElapsed,
                        history = updatedHistory,
                        chartPoints = updatedChartPoints,
                        statusMessage = "Roll #$newExecCount: ${if (isWin) "WIN" else "LOSE"} (${String.format(Locale.US, "%+.8f", profit)})"
                    )
                }

                // Proteksi Circuit Breaker 1: Stop on Win
                if (_uiState.value.stopOnWin && isWin) {
                    addLiveLog("🎯 Target 'Stop on Win' tercapai pada roll #$newExecCount! Menghentikan bot...", isError = false)
                    stopBot()
                    break
                }

                // Proteksi Circuit Breaker 2: Take Profit Auto-Stop
                val takeProfit = _uiState.value.takeProfitLimit
                if (takeProfit != null && takeProfit > 0.0 && newNetResult >= takeProfit) {
                    addLiveLog("🏆 CIRCUIT BREAKER: Target Take-Profit (+${String.format(Locale.US, "%.6f", takeProfit)}) tercapai! Menghentikan bot secara aman.", isError = false)
                    stopBot()
                    break
                }

                // Proteksi Circuit Breaker 3: Hard Stop Loss
                val stopLoss = _uiState.value.stopLossLimit
                if (stopLoss != null && stopLoss > 0.0 && newNetResult <= -stopLoss) {
                    addLiveLog("🛑 CIRCUIT BREAKER: Batas Stop-Loss (-${String.format(Locale.US, "%.6f", stopLoss)}) tersentuh! Bot dihentikan seketika untuk melindungi modal.", isError = true)
                    stopBot()
                    break
                }

                // Update Notification setiap 5 roll
                if (newExecCount % 5 == 0L) {
                    updateNotification(
                        "Bal: ${String.format(Locale.US, "%.4f", newBalance)} | PnL: ${String.format(Locale.US, "%+.4f", newNetResult)} | Bets: $newExecCount"
                    )
                }

                delay(100) // Kecepatan interval taruhan
            }
        }
    }

    fun pauseBot() {
        _uiState.update { it.copy(isPaused = true, statusMessage = "Paused") }
        addLiveLog("⏸ Bot Dijeda.", isError = false)
        updateNotification("Bot Dijeda")
    }

    fun resumeBot() {
        _uiState.update { it.copy(isPaused = false, statusMessage = "Resumed") }
        addLiveLog("▶ Bot Melanjutkan eksekusi.", isError = false)
        updateNotification("Bot Melanjutkan...")
    }

    fun stopBot() {
        executionJob?.cancel()
        executionJob = null
        _uiState.update { it.copy(isRunning = false, isPaused = false, statusMessage = "Stopped") }
        addLiveLog("⏹ Bot Dihentikan.", isError = false)
        releaseWakeLock()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    fun resetStats() {
        _uiState.update {
            it.copy(
                netResult = 0.0,
                netResultPercent = 0.0,
                executions = 0,
                positiveOutcomes = 0,
                negativeOutcomes = 0,
                currentStreak = 0,
                bestPositiveStreak = 0,
                longestNegativeStreak = 0,
                totalVolume = 0.0,
                peakAmount = 0.0,
                largestDrawdown = 0.0,
                speedBps = 0.0,
                history = emptyList(),
                chartPoints = emptyList()
            )
        }
        addLiveLog("🔄 Statistik sesi berhasil di-reset.", isError = false)
    }

    fun resetAll() {
        _uiState.update {
            val currBal = it.balance
            it.copy(
                netResult = 0.0,
                netResultPercent = 0.0,
                executions = 0,
                positiveOutcomes = 0,
                negativeOutcomes = 0,
                currentStreak = 0,
                bestPositiveStreak = 0,
                longestNegativeStreak = 0,
                totalVolume = 0.0,
                peakAmount = 0.0,
                largestDrawdown = 0.0,
                speedBps = 0.0,
                initialBalance = currBal,
                minBalance = currBal,
                maxBalance = currBal,
                history = emptyList(),
                chartPoints = emptyList(),
                liveLogs = emptyList(),
                statusMessage = "Ready"
            )
        }
        addLiveLog("⚡ Reset All: Seluruh statistik, riwayat, chart, dan log dibersihkan.", isError = false)
    }

    fun resetSeed() {
        serviceScope.launch {
            val platform = _uiState.value.selectedPlatform
            addLiveLog("🌱 Merotasi seed untuk ${platform.displayName}...", isError = false)
            val res = casinoRepository.resetSeed(platform)
            res.onSuccess { msg ->
                addLiveLog("✅ $msg", isError = false)
            }.onFailure { err ->
                addLiveLog("❌ Gagal reset seed: ${err.message ?: "Unknown error"}", isError = true)
            }
        }
    }

    fun clearLogs() {
        _uiState.update { it.copy(liveLogs = emptyList()) }
    }

    fun updateScript(newScript: String) {
        val syntaxCheck = LuaEngine.validateSyntax(newScript)
        _uiState.update { it.copy(luaScript = newScript, syntaxValidation = syntaxCheck) }
    }

    fun loadPreset(preset: StrategyPreset) {
        val syntaxCheck = LuaEngine.validateSyntax(preset.script)
        _uiState.update {
            it.copy(
                luaScript = preset.script,
                scriptName = preset.name,
                syntaxValidation = syntaxCheck
            )
        }
        addLiveLog("📄 Preset strategi '${preset.name}' berhasil dimuat.", isError = false)
    }

    fun updatePlatform(platform: CasinoPlatform) {
        val isAuth = casinoRepository.hasCredentials(platform)
        _uiState.update {
            it.copy(
                selectedPlatform = platform,
                selectedCurrency = platform.defaultCurrency,
                isPlatformAuthenticated = isAuth,
                availableCoins = emptyList()
            )
        }
        addLiveLog("🌐 Platform berganti ke ${platform.displayName} (${platform.defaultCurrency})${if (isAuth) " [Tersimpan Sesi]" else " [Belum Login]"}", isError = false)
        refreshBalance()
    }

    fun savePlatformToken(platform: CasinoPlatform, token: String) {
        casinoRepository.saveToken(platform, token)
        _uiState.update { it.copy(isPlatformAuthenticated = true) }
        addLiveLog("🌐 Sesi login ${platform.displayName} tersimpan.", isError = false)
        refreshBalance()
    }

    fun logoutPlatform(platform: CasinoPlatform) {
        casinoRepository.clearToken(platform)
        _uiState.update { it.copy(isPlatformAuthenticated = !platform.isDirectApi) }
        addLiveLog("🚪 Sesi login ${platform.displayName} telah dihapus / logout.", isError = false)
    }

    fun getPlatformToken(platform: CasinoPlatform): String {
        return casinoRepository.getToken(platform)
    }

    fun toggleStopOnWin() {
        _uiState.update { it.copy(stopOnWin = !it.stopOnWin) }
        val status = if (_uiState.value.stopOnWin) "AKTIF" else "NONAKTIF"
        addLiveLog("🎯 Mode 'Stop on Win' kini $status.", isError = false)
    }

    fun updateRiskLimits(stopLoss: Double?, takeProfit: Double?, maxBet: Double?) {
        _uiState.update {
            it.copy(
                stopLossLimit = stopLoss,
                takeProfitLimit = takeProfit,
                maxBetLimit = maxBet
            )
        }
        addLiveLog("🛡 Batas Risiko Diperbarui: StopLoss=${stopLoss ?: "Off"}, TakeProfit=${takeProfit ?: "Off"}, MaxBet=${maxBet ?: "Off"}", isError = false)
    }

    fun setRiskModalOpen(isOpen: Boolean) {
        _uiState.update { it.copy(isRiskModalOpen = isOpen) }
    }

    fun refreshBalance() {
        serviceScope.launch {
            val res = casinoRepository.fetchBalance(_uiState.value.selectedPlatform, _uiState.value.selectedCurrency)
            if (res.isSuccess) {
                val bal = res.getOrThrow()
                _uiState.update { it.copy(balance = bal, isPlatformAuthenticated = true, statusMessage = "Saldo: $bal ${it.selectedCurrency}") }
                addLiveLog("💰 Saldo ${_uiState.value.selectedPlatform.displayName}: $bal ${_uiState.value.selectedCurrency}", isError = false)
            } else {
                val errMsg = res.exceptionOrNull()?.message ?: "Gagal terhubung"
                if (errMsg.contains("belum login") || errMsg.contains("dialihkan ke login") || errMsg.contains("terakhir") || errMsg.contains("belum diatur")) {
                    _uiState.update { it.copy(isPlatformAuthenticated = false) }
                }
                addLiveLog("⚠ Gagal refresh saldo: $errMsg", isError = true)
            }
            detectAvailableCoins(autoSelectActive = false)
        }
    }

    fun detectAvailableCoins(autoSelectActive: Boolean = true) {
        serviceScope.launch {
            _uiState.update { it.copy(isDetectingCoins = true) }
            val platform = _uiState.value.selectedPlatform
            val res = casinoRepository.fetchAvailableBalances(platform)
            if (res.isSuccess) {
                val coins = res.getOrThrow()
                var currentCurr = _uiState.value.selectedCurrency
                var currentBal = _uiState.value.balance

                if (autoSelectActive) {
                    val currentCoin = coins.firstOrNull { it.currency.equals(currentCurr, true) }
                    if (currentCoin == null || currentCoin.balance <= 0.0) {
                        val positiveCoin = coins.firstOrNull { it.balance > 0.0 }
                        if (positiveCoin != null) {
                            currentCurr = positiveCoin.currency
                            currentBal = positiveCoin.balance
                            addLiveLog("🪙 Deteksi Koin: Koin otomatis dialihkan ke [${positiveCoin.currency}] dengan saldo aktif ${positiveCoin.formattedBalance}", isError = false)
                        } else if (currentCoin != null) {
                            currentBal = currentCoin.balance
                        }
                    } else {
                        currentBal = currentCoin.balance
                    }
                } else {
                    val matching = coins.firstOrNull { it.currency.equals(currentCurr, true) }
                    if (matching != null) {
                        currentBal = matching.balance
                    }
                }

                _uiState.update {
                    it.copy(
                        availableCoins = coins,
                        selectedCurrency = currentCurr,
                        balance = currentBal,
                        isDetectingCoins = false,
                        statusMessage = "Koin: $currentCurr ($currentBal)"
                    )
                }
                val activeCount = coins.count { it.balance > 0.0 }
                addLiveLog("🪙 Deteksi Koin: ${coins.size} koin terdata ($activeCount koin aktif bersaldo) pada ${platform.displayName}.", isError = false)
            } else {
                _uiState.update { it.copy(isDetectingCoins = false) }
                addLiveLog("⚠ Gagal mendeteksi saldo koin: ${res.exceptionOrNull()?.message}", isError = true)
            }
        }
    }

    fun selectCurrency(currency: String) {
        val clean = currency.uppercase(Locale.US).trim()
        if (clean == _uiState.value.selectedCurrency) return

        serviceScope.launch {
            val coin = _uiState.value.availableCoins.firstOrNull { it.currency.equals(clean, true) }
            val balance = if (coin != null && coin.balance > 0) {
                coin.balance
            } else {
                val res = casinoRepository.fetchBalance(_uiState.value.selectedPlatform, clean)
                res.getOrDefault(0.0)
            }

            _uiState.update {
                it.copy(
                    selectedCurrency = clean,
                    balance = balance,
                    initialBalance = balance,
                    minBalance = balance,
                    maxBalance = balance,
                    netResult = 0.0,
                    netResultPercent = 0.0,
                    statusMessage = "Koin aktif: $clean ($balance)"
                )
            }
            addLiveLog("🪙 Koin aktif diubah ke [$clean] | Saldo: $balance $clean", isError = false)
        }
    }

    fun addLiveLog(message: String, isError: Boolean = false) {
        val entry = LuaLogEntry(message = message, isError = isError)
        _uiState.update {
            val updated = (it.liveLogs + entry).takeLast(200)
            it.copy(liveLogs = updated)
        }
    }

    private fun acquireWakeLock() {
        if (wakeLock == null) {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "RaptechDicebot::ExecutionLock")
            wakeLock?.acquire(12 * 60 * 60 * 1000L)
        }
    }

    private fun releaseWakeLock() {
        wakeLock?.let {
            if (it.isHeld) it.release()
        }
        wakeLock = null
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Raptech Dicebot Runner",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Status eksekusi dadu kripto dan PnL aktif"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(text: String): Notification {
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        // Quick action: Tombol [STOP BOT] langsung dari Notification bar
        val stopIntent = Intent(this, DicebotForegroundService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPendingIntent = PendingIntent.getService(
            this,
            1,
            stopIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val stopAction = NotificationCompat.Action.Builder(
            android.R.drawable.ic_media_pause,
            "STOP BOT",
            stopPendingIntent
        ).build()

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Raptech Automation Running")
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_launcher)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .addAction(stopAction)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateNotification(text: String) {
        val notification = buildNotification(text)
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, notification)
    }

    override fun onDestroy() {
        super.onDestroy()
        stopBot()
    }
}
