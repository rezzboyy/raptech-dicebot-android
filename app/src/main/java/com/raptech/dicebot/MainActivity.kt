package com.raptech.dicebot

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import com.raptech.dicebot.data.network.CasinoHttpClient
import com.raptech.dicebot.data.updater.DicebotUpdateManager
import com.raptech.dicebot.data.updater.UpdateCheckResult
import com.raptech.dicebot.data.updater.UpdateInfo
import com.raptech.dicebot.service.DicebotForegroundService
import com.raptech.dicebot.ui.components.DicebotUpdateDialog
import com.raptech.dicebot.ui.components.SplashScreen
import com.raptech.dicebot.ui.screens.DicebotMainScreen
import com.raptech.dicebot.ui.theme.RaptechDicebotTheme
import com.raptech.dicebot.util.BatteryOptimizationHelper
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private var botService: DicebotForegroundService? = null
    private var isBound = false

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as DicebotForegroundService.LocalBinder
            botService = binder.getService()
            isBound = true
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            botService = null
            isBound = false
        }
    }

    private val requestNotificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { _ ->
            // Permission result handled
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Synchronize OkHttp User-Agent with system Chromium WebView engine
        CasinoHttpClient.syncUserAgent(this)

        checkPermissions()
        bindBotService()

        setContent {
            RaptechDicebotTheme {
                val state by DicebotForegroundService.uiState.collectAsState()
                val coroutineScope = rememberCoroutineScope()
                val context = LocalContext.current

                var showBatteryPrompt by remember {
                    mutableStateOf(!BatteryOptimizationHelper.isBatteryOptimizationIgnored(this@MainActivity))
                }

                var availableUpdate by remember { mutableStateOf<UpdateInfo?>(null) }
                var isDownloadingUpdate by remember { mutableStateOf(false) }
                var updateDownloadProgress by remember { mutableFloatStateOf(0f) }
                var showSplash by remember { mutableStateOf(true) }

                fun performUpdateCheck(isManual: Boolean = false) {
                    coroutineScope.launch {
                        try {
                            val currentVersion = packageManager.getPackageInfo(packageName, 0).versionName ?: "1.0.0"
                            when (val res = DicebotUpdateManager.checkForUpdate(currentVersion)) {
                                is UpdateCheckResult.UpdateAvailable -> {
                                    availableUpdate = res.info
                                }
                                is UpdateCheckResult.UpToDate -> {
                                    if (isManual) {
                                        android.widget.Toast.makeText(
                                            this@MainActivity,
                                            "Aplikasi sudah versi terbaru (v$currentVersion)",
                                            android.widget.Toast.LENGTH_SHORT
                                        ).show()
                                    }
                                }
                                is UpdateCheckResult.Error -> {
                                    if (isManual) {
                                        android.widget.Toast.makeText(
                                            this@MainActivity,
                                            "Gagal memeriksa pembaruan: ${res.message}",
                                            android.widget.Toast.LENGTH_LONG
                                        ).show()
                                    }
                                }
                            }
                        } catch (_: Exception) {
                            if (isManual) {
                                android.widget.Toast.makeText(
                                    this@MainActivity,
                                    "Gagal terhubung ke server pembaruan",
                                    android.widget.Toast.LENGTH_SHORT
                                ).show()
                            }
                        }
                    }
                }

                // Check GitHub Releases for updates in background on launch
                LaunchedEffect(Unit) {
                    performUpdateCheck(isManual = false)
                }

                Crossfade(
                    targetState = showSplash,
                    animationSpec = tween(400),
                    label = "SplashCrossfade"
                ) { isSplash ->
                    if (isSplash) {
                        SplashScreen(
                            onAnimationFinished = { showSplash = false }
                        )
                    } else {
                        DicebotMainScreen(
                            state = state,
                            onStart = {
                                startBotService(DicebotForegroundService.ACTION_START)
                                botService?.startBot()
                            },
                            onPause = {
                                botService?.pauseBot()
                            },
                            onResume = {
                                botService?.resumeBot()
                            },
                            onStop = {
                                botService?.stopBot()
                            },
                            onRefreshBalance = {
                                botService?.refreshBalance()
                            },
                            onToggleStopOnWin = {
                                botService?.toggleStopOnWin()
                            },
                            onPlatformSelected = { platform ->
                                botService?.updatePlatform(platform)
                            },
                            onScriptChanged = { script ->
                                botService?.updateScript(script)
                            },
                            onSessionCaptured = { token ->
                                botService?.savePlatformToken(state.selectedPlatform, token)
                            },
                            onLogout = {
                                botService?.logoutPlatform(state.selectedPlatform)
                            },
                            onSaveRiskLimits = { stopLoss, takeProfit, maxBet ->
                                botService?.updateRiskLimits(stopLoss, takeProfit, maxBet)
                            },
                            onCurrencySelected = { coin ->
                                botService?.selectCurrency(coin)
                            },
                            onDetectCoins = {
                                botService?.detectAvailableCoins(autoSelectActive = false)
                            },
                            onResetAll = {
                                botService?.resetAll()
                            },
                            onResetStats = {
                                botService?.resetStats()
                            },
                            onResetSeed = {
                                botService?.resetSeed()
                            },
                            onCheckUpdate = {
                                performUpdateCheck(isManual = true)
                            },
                            onQuitApp = {
                                botService?.stopBot()
                                startBotService(DicebotForegroundService.ACTION_STOP)
                                if (isBound) {
                                    unbindService(serviceConnection)
                                    isBound = false
                                }
                                finishAffinity()
                            },
                            onClearLogs = {
                                botService?.clearLogs()
                            },
                            onRequestBatteryWhitelist = {
                                BatteryOptimizationHelper.requestIgnoreBatteryOptimization(this@MainActivity)
                            },
                            showBatteryOptimizationPrompt = showBatteryPrompt,
                            onDismissBatteryPrompt = {
                                showBatteryPrompt = false
                            }
                        )
                    }
                }

                // Smooth In-App OTA Update Dialog
                if (availableUpdate != null) {
                    DicebotUpdateDialog(
                        updateInfo = availableUpdate!!,
                        isDownloading = isDownloadingUpdate,
                        downloadProgress = updateDownloadProgress,
                        onDismiss = { availableUpdate = null },
                        onConfirmUpdate = {
                            isDownloadingUpdate = true
                            coroutineScope.launch {
                                DicebotUpdateManager.downloadAndInstallApk(
                                    context = context,
                                    downloadUrl = availableUpdate!!.apkDownloadUrl,
                                    onProgress = { updateDownloadProgress = it },
                                    onError = {
                                        isDownloadingUpdate = false
                                        availableUpdate = null
                                    }
                                )
                            }
                        }
                    )
                }
            }
        }
    }

    private fun checkPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(
                    this,
                    Manifest.permission.POST_NOTIFICATIONS
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                requestNotificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    private fun bindBotService() {
        val intent = Intent(this, DicebotForegroundService::class.java)
        bindService(intent, serviceConnection, Context.BIND_AUTO_CREATE)
    }

    private fun startBotService(action: String) {
        val intent = Intent(this, DicebotForegroundService::class.java).apply {
            this.action = action
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        if (isBound) {
            unbindService(serviceConnection)
            isBound = false
        }
    }
}
