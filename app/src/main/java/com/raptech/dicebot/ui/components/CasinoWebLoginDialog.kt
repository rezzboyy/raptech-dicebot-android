package com.raptech.dicebot.ui.components

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.net.http.SslError
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.SslErrorHandler
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import org.json.JSONObject
import androidx.activity.compose.BackHandler
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
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.Key
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Public
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.BasicAlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.raptech.dicebot.data.adapter.BetfuryAdapter
import com.raptech.dicebot.data.adapter.CasinoPlatformAdapter
import com.raptech.dicebot.data.adapter.PickIoAdapter
import com.raptech.dicebot.model.CasinoPlatform
import com.raptech.dicebot.ui.theme.RaptechColors
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@SuppressLint("SetJavaScriptEnabled")
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CasinoWebLoginDialog(
    platform: CasinoPlatform,
    isAuthenticated: Boolean,
    onDismiss: () -> Unit,
    onSessionCaptured: (String) -> Unit,
    onLogout: () -> Unit
) {
    if (platform == CasinoPlatform.SIMULATOR) {
        BasicAlertDialog(onDismissRequest = onDismiss) {
            Column(
                modifier = Modifier
                    .clip(RoundedCornerShape(12.dp))
                    .background(RaptechColors.SurfaceWhite)
                    .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(12.dp))
                    .padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Icon(
                    imageVector = Icons.Default.Public,
                    contentDescription = null,
                    tint = RaptechColors.InfoBlue,
                    modifier = Modifier.size(36.dp)
                )
                Text(
                    text = "Mode Simulasi Lokal (Offline)",
                    color = RaptechColors.OrangePrimary,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "Mode simulasi berjalan 100% offline tanpa perlu koneksi internet atau login akun kasino.",
                    color = RaptechColors.TextSecondary,
                    fontSize = 12.sp,
                    lineHeight = 17.sp
                )
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(6.dp))
                        .background(RaptechColors.OrangePrimary)
                        .clickable { onDismiss() }
                        .padding(vertical = 10.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Mengerti",
                        color = Color.White,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
        return
    }

    BackHandler(onBack = onDismiss)

    val coroutineScope = rememberCoroutineScope()
    var selectedLoginTab by remember { mutableIntStateOf(0) } // 0: In-App Browser, 1: Manual Token/Cookie Input

    val loginUrl = remember(platform) {
        if (platform == CasinoPlatform.BETFURY) {
            "https://betfury.com"
        } else if (platform.defaultLoginUrl.isNotBlank()) {
            "${platform.defaultLoginUrl}/login.php"
        } else ""
    }

    // State Browser
    var webViewRef by remember { mutableStateOf<WebView?>(null) }
    var detectedSession by remember { mutableStateOf<String?>(null) }
    var isDetectedSuccess by remember { mutableStateOf(false) }
    var currentUrlDisplay by remember { mutableStateOf(loginUrl) }
    var loadProgress by remember { mutableIntStateOf(0) }
    var hasLoadError by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf("") }
    var verificationStatusMessage by remember { mutableStateOf<String?>(null) }
    var isVerifyingSession by remember { mutableStateOf(false) }

    // Autofill Credentials State (Preloaded for convenient 1-tap fill)
    var autofillEmail by remember { mutableStateOf("ohlinsktc5@gmail.com") }
    var autofillPassword by remember { mutableStateOf("tdrrcbarm") }
    var autofillNotice by remember { mutableStateOf<String?>(null) }

    // State Manual Token
    var manualTokenInput by remember { mutableStateOf("") }
    var manualStatusMessage by remember { mutableStateOf<String?>(null) }
    var isManualVerifying by remember { mutableStateOf(false) }

    fun executeAutofill() {
        val emailEscaped = autofillEmail.replace("'", "\\'").trim()
        val passEscaped = autofillPassword.replace("'", "\\'").trim()
        val script = """
            (function() {
                var emailInput = document.getElementById('user_email') || document.querySelector('input[name="user_email"]') || document.querySelector('input[type="email"]');
                var passInput = document.getElementById('password') || document.querySelector('input[name="password"]') || document.querySelector('input[type="password"]');
                var filled = false;
                if (emailInput) {
                    emailInput.value = '$emailEscaped';
                    emailInput.dispatchEvent(new Event('input', { bubbles: true }));
                    emailInput.dispatchEvent(new Event('change', { bubbles: true }));
                    filled = true;
                }
                if (passInput) {
                    passInput.value = '$passEscaped';
                    passInput.dispatchEvent(new Event('input', { bubbles: true }));
                    passInput.dispatchEvent(new Event('change', { bubbles: true }));
                    filled = true;
                }
                return filled;
            })();
        """.trimIndent()

        webViewRef?.evaluateJavascript(script) { result ->
            val ok = result == "true"
            autofillNotice = if (ok) "⚡ Email & Password berhasil diisi!" else "⚠ Form belum siap"
            coroutineScope.launch {
                delay(2500)
                autofillNotice = null
            }
        }
    }

    fun verifyAndConnectSession(cookiesRaw: String, fallbackBalance: Double = 0.0) {
        val clean = cookiesRaw.trim()
        if (clean.isBlank()) {
            verificationStatusMessage = "⚠ Belum ada cookie/sesi yang ditemukan."
            return
        }

        isVerifyingSession = true
        verificationStatusMessage = "Memverifikasi sesi dengan ${platform.displayName}..."

        coroutineScope.launch {
            val testAdapter: CasinoPlatformAdapter = if (platform == CasinoPlatform.BETFURY) {
                val bAdapter = BetfuryAdapter(clean)
                if (fallbackBalance > 0.0) {
                    bAdapter.setInitialBalance(platform.defaultCurrency, fallbackBalance)
                }
                bAdapter
            } else {
                PickIoAdapter(platform, clean)
            }
            val balanceRes = testAdapter.fetchBalance(platform.defaultCurrency)

            withContext(Dispatchers.Main) {
                isVerifyingSession = false
                if (balanceRes.isSuccess || (platform == CasinoPlatform.BETFURY && fallbackBalance > 0.0)) {
                    val bal = if (balanceRes.isSuccess) balanceRes.getOrThrow() else fallbackBalance
                    isDetectedSuccess = true
                    detectedSession = clean
                    verificationStatusMessage = "✅ Berhasil Terhubung! Saldo: $bal ${platform.defaultCurrency}"
                    onSessionCaptured(clean)
                    delay(1200)
                    onDismiss()
                } else {
                    val err = balanceRes.exceptionOrNull()?.message ?: "Sesi belum terautentikasi"
                    verificationStatusMessage = "⚠ $err. Selesaikan login & captcha di atas."
                }
            }
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(RaptechColors.SurfaceWhite)
            .statusBarsPadding()
            .navigationBarsPadding()
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            // Top Header Bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(RaptechColors.SurfaceWhite)
                    .border(1.dp, RaptechColors.BorderSubtle)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Kembali",
                            tint = RaptechColors.TextPrimary,
                            modifier = Modifier.size(20.dp)
                        )
                    }

                    Icon(
                        imageVector = Icons.Default.Lock,
                        contentDescription = "Autentikasi Akun",
                        tint = if (isDetectedSuccess || isAuthenticated) RaptechColors.WinSuccess else RaptechColors.OrangePrimary,
                        modifier = Modifier.size(18.dp)
                    )
                    Column {
                        Text(
                            text = "Autentikasi Sesi ${platform.displayName}",
                            color = RaptechColors.TextPrimary,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = if (selectedLoginTab == 0) currentUrlDisplay else "Input Cookie / Sesi Manual",
                            color = RaptechColors.TextSecondary,
                            fontSize = 10.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (selectedLoginTab == 0) {
                        IconButton(
                            onClick = {
                                hasLoadError = false
                                webViewRef?.reload()
                            },
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Refresh,
                                contentDescription = "Reload",
                                tint = RaptechColors.OrangePrimary,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }

                    if (isAuthenticated) {
                        IconButton(
                            onClick = {
                                val cookieManager = CookieManager.getInstance()
                                cookieManager.removeAllCookies(null)
                                cookieManager.flush()
                                onLogout()
                                isDetectedSuccess = false
                                detectedSession = null
                                verificationStatusMessage = "Sesi telah dihapus / logout."
                                webViewRef?.loadUrl(loginUrl)
                            },
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.Logout,
                                contentDescription = "Logout",
                                tint = RaptechColors.LossDanger,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }

                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Tutup",
                            tint = RaptechColors.TextPrimary,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }

            // Dual Mode Tab Selector: In-App Browser vs Manual Input
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(RaptechColors.SurfaceWhite)
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(5.dp))
                        .background(if (selectedLoginTab == 0) RaptechColors.OrangePrimary else RaptechColors.SurfaceLight)
                        .then(
                            if (selectedLoginTab != 0) Modifier.border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(5.dp))
                            else Modifier
                        )
                        .clickable { selectedLoginTab = 0 }
                        .padding(vertical = 7.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "🌐 Browser Login (WebView)",
                        fontSize = 11.sp,
                        fontWeight = if (selectedLoginTab == 0) FontWeight.Bold else FontWeight.Medium,
                        color = if (selectedLoginTab == 0) Color.White else RaptechColors.TextSecondary
                    )
                }

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(5.dp))
                        .background(if (selectedLoginTab == 1) RaptechColors.OrangePrimary else RaptechColors.SurfaceLight)
                        .then(
                            if (selectedLoginTab != 1) Modifier.border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(5.dp))
                            else Modifier
                        )
                        .clickable { selectedLoginTab = 1 }
                        .padding(vertical = 7.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "🔑 Input Cookie / Sesi Manual",
                        fontSize = 11.sp,
                        fontWeight = if (selectedLoginTab == 1) FontWeight.Bold else FontWeight.Medium,
                        color = if (selectedLoginTab == 1) Color.White else RaptechColors.TextSecondary
                    )
                }
            }

            // Content View based on Tab
            when (selectedLoginTab) {
                0 -> {
                    // === TAB 0: IN-APP BROWSER (WITH AUTOFILL & SMART VERIFY) ===
                    Column(modifier = Modifier.weight(1f).fillMaxWidth()) {
                        // Autofill & Navigation Helper Bar
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(RaptechColors.SurfaceLight)
                                .border(1.dp, RaptechColors.BorderSubtle)
                                .padding(horizontal = 10.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            // Autofill Button
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(RaptechColors.OrangePrimary)
                                    .clickable { executeAutofill() }
                                    .padding(horizontal = 8.dp, vertical = 5.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Bolt,
                                        contentDescription = null,
                                        tint = Color.White,
                                        modifier = Modifier.size(13.dp)
                                    )
                                    Text(
                                        text = "Autofill Akun",
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color.White
                                    )
                                }
                            }

                            // Quick Navigation Buttons
                            if (platform == CasinoPlatform.BETFURY) {
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(4.dp))
                                        .background(RaptechColors.SurfaceWhite)
                                        .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(4.dp))
                                        .clickable {
                                            hasLoadError = false
                                            webViewRef?.loadUrl("https://betfury.com")
                                        }
                                        .padding(horizontal = 8.dp, vertical = 5.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "Ke Betfury",
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = RaptechColors.TextPrimary
                                    )
                                }

                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(4.dp))
                                        .background(RaptechColors.SurfaceWhite)
                                        .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(4.dp))
                                        .clickable {
                                            hasLoadError = false
                                            webViewRef?.loadUrl("https://betfury.com/casino/games/dice")
                                        }
                                        .padding(horizontal = 8.dp, vertical = 5.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "Ke Game Dice",
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = RaptechColors.TextPrimary
                                    )
                                }
                            } else {
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(4.dp))
                                        .background(RaptechColors.SurfaceWhite)
                                        .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(4.dp))
                                        .clickable {
                                            hasLoadError = false
                                            webViewRef?.loadUrl(loginUrl)
                                        }
                                        .padding(horizontal = 8.dp, vertical = 5.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "Ke Login.php",
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = RaptechColors.TextPrimary
                                    )
                                }
                            }

                            // Notice message
                            if (autofillNotice != null) {
                                Text(
                                    text = autofillNotice!!,
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = RaptechColors.WinSuccess,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f)
                                )
                            } else {
                                Text(
                                    text = if (platform == CasinoPlatform.BETFURY) "Login / Sign in di atas ➔ Verifikasi Sesi" else "Isi form ➔ pecahkan captcha ➔ Log in",
                                    fontSize = 10.sp,
                                    color = RaptechColors.TextMuted,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }

                        // Progress Indicator
                        if (loadProgress in 1..99) {
                            LinearProgressIndicator(
                                progress = { loadProgress / 100f },
                                modifier = Modifier.fillMaxWidth().height(2.dp),
                                color = RaptechColors.OrangePrimary,
                                trackColor = RaptechColors.SurfaceLight
                            )
                        }

                        // Main WebView
                        Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
                            AndroidView(
                                modifier = Modifier.fillMaxSize(),
                                factory = { ctx ->
                                    WebView(ctx).apply {
                                        webViewRef = this
                                        layoutParams = ViewGroup.LayoutParams(
                                            ViewGroup.LayoutParams.MATCH_PARENT,
                                            ViewGroup.LayoutParams.MATCH_PARENT
                                        )

                                        settings.apply {
                                            javaScriptEnabled = true
                                            domStorageEnabled = true
                                            databaseEnabled = true
                                            useWideViewPort = true
                                            loadWithOverviewMode = true
                                            javaScriptCanOpenWindowsAutomatically = true
                                            setSupportMultipleWindows(false)
                                            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                                            cacheMode = WebSettings.LOAD_DEFAULT
                                            allowContentAccess = true
                                            allowFileAccess = true

                                            // System native User Agent matching device hardware exactly
                                            userAgentString = WebSettings.getDefaultUserAgent(ctx)
                                        }

                                        val cookieManager = CookieManager.getInstance()
                                        cookieManager.setAcceptCookie(true)
                                        cookieManager.setAcceptThirdPartyCookies(this, true)

                                        webChromeClient = object : WebChromeClient() {
                                            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                                                loadProgress = newProgress
                                                super.onProgressChanged(view, newProgress)
                                            }
                                        }

                                        // Javascript Bridge for secure auth capture
                                        addJavascriptInterface(object {
                                            @JavascriptInterface
                                            fun onAuthSuccess(cookies: String) {
                                                post {
                                                    verifyAndConnectSession(cookies)
                                                }
                                            }

                                            @JavascriptInterface
                                            fun onBetfuryAuthCaptured(jsonStr: String) {
                                                post {
                                                    try {
                                                        val obj = JSONObject(jsonStr)
                                                        val token = obj.optString("token")
                                                        val uid = obj.optString("uid")
                                                        val bal = obj.optDouble("balance", 0.0)
                                                        val cookieManager = CookieManager.getInstance()
                                                        val cookies = cookieManager.getCookie("https://betfury.com") ?: ""
                                                        var s = if (token.isNotBlank()) token else "betfury_session"
                                                        if (uid.isNotBlank()) s += ";uid=$uid"
                                                        if (bal > 0.0) s += ";bal=$bal"
                                                        if (cookies.isNotBlank()) s += ";cookies=$cookies"
                                                        verifyAndConnectSession(s, bal)
                                                    } catch (_: Exception) {
                                                        verifyAndConnectSession(jsonStr)
                                                    }
                                                }
                                            }
                                        }, "DicebotBridge")

                                        webViewClient = object : WebViewClient() {
                                            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                                                super.onPageStarted(view, url, favicon)
                                                hasLoadError = false
                                                url?.let { currentUrlDisplay = it }
                                            }

                                            override fun onPageFinished(view: WebView?, url: String?) {
                                                super.onPageFinished(view, url)
                                                url?.let { currentUrlDisplay = it }

                                                // Inject hook to catch successful AJAX login response
                                                val xhrHookScript = """
                                                    (function() {
                                                        if (window._dicebotHookInstalled) return;
                                                        window._dicebotHookInstalled = true;
                                                        var origOpen = XMLHttpRequest.prototype.open;
                                                        var origSend = XMLHttpRequest.prototype.send;
                                                        XMLHttpRequest.prototype.open = function(method, url) {
                                                            this._diceUrl = url;
                                                            return origOpen.apply(this, arguments);
                                                        };
                                                        XMLHttpRequest.prototype.send = function() {
                                                            this.addEventListener('load', function() {
                                                                if (this._diceUrl && this._diceUrl.indexOf('process.php') !== -1) {
                                                                    try {
                                                                        var res = JSON.parse(this.responseText);
                                                                        if (res && (res.ret == 1 || res.ret === '1' || res.ret === true)) {
                                                                            if (window.DicebotBridge) {
                                                                                window.DicebotBridge.onAuthSuccess(document.cookie);
                                                                            }
                                                                        }
                                                                    } catch(e) {}
                                                                }
                                                            });
                                                            return origSend.apply(this, arguments);
                                                        };
                                                    })();
                                                """.trimIndent()
                                                view?.evaluateJavascript(xhrHookScript, null)

                                                // If page is on internal logged-in page (not login.php or signup.php)
                                                val isLoginPage = url?.contains("login.php", ignoreCase = true) == true ||
                                                        url?.contains("signup.php", ignoreCase = true) == true

                                                if (!isLoginPage && url != null && url.contains(platform.defaultLoginUrl)) {
                                                    val loggedInCheckScript = """
                                                        (function() {
                                                            var hasLogout = document.body && (document.body.innerHTML.indexOf('action=logout') !== -1 || document.body.innerHTML.indexOf('Logout') !== -1);
                                                            var hasBal = document.getElementById('user_balance') || document.getElementById('available_balance') || document.getElementById('dd_main_balance') || document.querySelector('[data-user-balance]');
                                                            var hasProfile = document.querySelector('.profile-name') || document.querySelector('.user_level');
                                                            if (hasLogout || hasBal || hasProfile) {
                                                                if (window.DicebotBridge) {
                                                                    window.DicebotBridge.onAuthSuccess(document.cookie);
                                                                }
                                                            }
                                                        })();
                                                    """.trimIndent()
                                                    view?.evaluateJavascript(loggedInCheckScript, null)
                                                }

                                                if (platform == CasinoPlatform.BETFURY) {
                                                    val betfuryCheckScript = """
                                                        (function() {
                                                            try {
                                                                var res = { token: '', uid: '', balance: 0.0, currency: 'BFG' };
                                                                if (window.${'$'}nuxt && window.${'$'}nuxt.${'$'}store && window.${'$'}nuxt.${'$'}store.state) {
                                                                    var s = window.${'$'}nuxt.${'$'}store.state;
                                                                    var u = s.user || s.auth || s.profile;
                                                                    if (u) {
                                                                        if (u.token) res.token = u.token;
                                                                        if (u.userId || u.id || u.uid) res.uid = String(u.userId || u.id || u.uid);
                                                                        if (u.currencies) {
                                                                            var bfg = u.currencies.bfg || u.currencies.BFG;
                                                                            if (bfg && bfg.balance != null) res.balance = parseFloat(bfg.balance);
                                                                        }
                                                                    }
                                                                }
                                                                if (!res.token) {
                                                                    var directKeys = ['token', 'auth_token', 'jwt', 'bf_token', 'accessToken', 'session_token'];
                                                                    for (var i = 0; i < directKeys.length; i++) {
                                                                        var v = window.localStorage.getItem(directKeys[i]);
                                                                        if (v && v.length > 10) { res.token = v.replace(/^"|"$/g, ''); break; }
                                                                    }
                                                                }
                                                                if (res.balance <= 0) {
                                                                    var all = document.querySelectorAll('span, div, p');
                                                                    for (var j = 0; j < all.length; j++) {
                                                                        var el = all[j];
                                                                        if (el.children.length === 0 && el.innerText) {
                                                                            var t = el.innerText.trim();
                                                                            if (/^\d+\.\d{4,8}$/.test(t)) {
                                                                                var num = parseFloat(t);
                                                                                if (num > 0) { res.balance = num; break; }
                                                                            }
                                                                        }
                                                                    }
                                                                }
                                                                if ((res.token || res.balance > 0) && window.DicebotBridge) {
                                                                    window.DicebotBridge.onBetfuryAuthCaptured(JSON.stringify(res));
                                                                }
                                                            } catch(e) {}
                                                        })();
                                                    """.trimIndent()
                                                    view?.evaluateJavascript(betfuryCheckScript, null)
                                                }
                                            }

                                            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                                                if (request?.isForMainFrame == true) {
                                                    hasLoadError = true
                                                    errorMessage = "Gagal memuat: ${error?.description ?: "Koneksi terputus"}"
                                                }
                                                super.onReceivedError(view, request, error)
                                            }

                                            override fun onReceivedSslError(view: WebView?, handler: SslErrorHandler?, error: SslError?) {
                                                handler?.proceed()
                                            }
                                        }

                                        loadUrl(loginUrl)
                                    }
                                }
                            )

                            // Fallback error overlay
                            if (hasLoadError) {
                                Column(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .background(RaptechColors.SurfaceWhite.copy(alpha = 0.98f))
                                        .padding(24.dp),
                                    verticalArrangement = Arrangement.Center,
                                    horizontalAlignment = Alignment.CenterHorizontally
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Error,
                                        contentDescription = null,
                                        tint = RaptechColors.LossDanger,
                                        modifier = Modifier.size(42.dp)
                                    )
                                    Spacer(modifier = Modifier.height(10.dp))
                                    Text(
                                        text = "Gagal Memuat Halaman",
                                        color = RaptechColors.TextPrimary,
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text(
                                        text = "$errorMessage\n\nSilakan coba lagi atau gunakan Tab Input Cookie Manual.",
                                        color = RaptechColors.TextSecondary,
                                        fontSize = 11.sp,
                                        lineHeight = 16.sp
                                    )
                                    Spacer(modifier = Modifier.height(14.dp))
                                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        Box(
                                            modifier = Modifier
                                                .clip(RoundedCornerShape(6.dp))
                                                .background(RaptechColors.OrangePrimary)
                                                .clickable {
                                                    hasLoadError = false
                                                    webViewRef?.reload()
                                                }
                                                .padding(horizontal = 14.dp, vertical = 8.dp)
                                        ) {
                                            Text(
                                                text = "Coba Ulang",
                                                color = Color.White,
                                                fontSize = 11.sp,
                                                fontWeight = FontWeight.Bold
                                            )
                                        }

                                        Box(
                                            modifier = Modifier
                                                .clip(RoundedCornerShape(6.dp))
                                                .background(RaptechColors.SurfaceLight)
                                                .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                                                .clickable { selectedLoginTab = 1 }
                                                .padding(horizontal = 14.dp, vertical = 8.dp)
                                        ) {
                                            Text(
                                                text = "Input Manual",
                                                color = RaptechColors.OrangePrimary,
                                                fontSize = 11.sp,
                                                fontWeight = FontWeight.Bold
                                            )
                                        }
                                    }
                                }
                            }
                        }

                        // Bottom Session Connect & Verification Bar
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(RaptechColors.SurfaceWhite)
                                .border(1.dp, RaptechColors.BorderSubtle)
                                .padding(horizontal = 12.dp, vertical = 8.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            if (verificationStatusMessage != null) {
                                Text(
                                    text = verificationStatusMessage!!,
                                    color = if (isDetectedSuccess) RaptechColors.WinSuccess else RaptechColors.OrangePrimary,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }

                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(if (isVerifyingSession) RaptechColors.SurfaceLight else RaptechColors.OrangePrimary)
                                    .clickable(enabled = !isVerifyingSession) {
                                        if (platform == CasinoPlatform.BETFURY) {
                                            val extractScript = """
                                                (function() {
                                                    var res = {
                                                        token: '',
                                                        uid: '',
                                                        balance: 0.0,
                                                        currency: 'BFG'
                                                    };

                                                    // 1. Nuxt store extraction
                                                    try {
                                                        if (window.${'$'}nuxt && window.${'$'}nuxt.${'$'}store && window.${'$'}nuxt.${'$'}store.state) {
                                                            var s = window.${'$'}nuxt.${'$'}store.state;
                                                            var u = s.user || s.auth || s.profile;
                                                            if (u) {
                                                                if (u.token) res.token = u.token;
                                                                if (u.userId || u.id || u.uid) res.uid = String(u.userId || u.id || u.uid);
                                                                if (u.currencies) {
                                                                    var bfg = u.currencies.bfg || u.currencies.BFG;
                                                                    if (bfg && bfg.balance != null) res.balance = parseFloat(bfg.balance);
                                                                }
                                                            }
                                                            if (!res.token && s.auth && s.auth.token) res.token = s.auth.token;
                                                        }
                                                    } catch(e) {}

                                                    // 2. Direct localStorage scan
                                                    try {
                                                        var directKeys = ['token', 'auth_token', 'jwt', 'bf_token', 'accessToken', 'session_token'];
                                                        for (var i = 0; i < directKeys.length; i++) {
                                                            var v = window.localStorage.getItem(directKeys[i]);
                                                            if (v && v.length > 10 && !res.token) {
                                                                res.token = v.replace(/^"|"$/g, '');
                                                                break;
                                                            }
                                                        }
                                                        if (!res.token) {
                                                            for (var j = 0; j < window.localStorage.length; j++) {
                                                                var k = window.localStorage.key(j);
                                                                var val = window.localStorage.getItem(k);
                                                                if (val && val.indexOf('eyJ') !== -1) {
                                                                    var m = val.match(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/);
                                                                    if (m) { res.token = m[0]; break; }
                                                                }
                                                            }
                                                        }
                                                        if (!res.uid) {
                                                            var uKeys = ['uid', 'userId', 'user_id', 'id'];
                                                            for (var u2 = 0; u2 < uKeys.length; u2++) {
                                                                var uv = window.localStorage.getItem(uKeys[u2]);
                                                                if (uv) { res.uid = uv.replace(/^"|"$/g, ''); break; }
                                                            }
                                                        }
                                                    } catch(e) {}

                                                    // 3. Extract DOM balance (e.g. 24.5006732)
                                                    try {
                                                        if (res.balance <= 0) {
                                                            var allElements = document.querySelectorAll('span, div, p');
                                                            for (var e = 0; e < allElements.length; e++) {
                                                                var el = allElements[e];
                                                                if (el.children.length === 0 && el.innerText) {
                                                                    var txt = el.innerText.trim();
                                                                    if (/^\d+\.\d{4,8}$/.test(txt)) {
                                                                        var parsed = parseFloat(txt);
                                                                        if (parsed > 0) {
                                                                            res.balance = parsed;
                                                                            break;
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    } catch(e) {}

                                                    return JSON.stringify(res);
                                                })()
                                            """.trimIndent()

                                            webViewRef?.evaluateJavascript(extractScript) { res ->
                                                var tokenExtracted = ""
                                                var uidExtracted = ""
                                                var domBal = 0.0

                                                try {
                                                    val rawJson = res?.trim('"', '\'')?.replace("\\\"", "\"")?.replace("\\\\", "\\") ?: ""
                                                    if (rawJson.startsWith("{") && rawJson.endsWith("}")) {
                                                        val obj = JSONObject(rawJson)
                                                        tokenExtracted = obj.optString("token", "")
                                                        uidExtracted = obj.optString("uid", "")
                                                        domBal = obj.optDouble("balance", 0.0)
                                                    }
                                                } catch (_: Exception) {}

                                                val cookieManager = CookieManager.getInstance()
                                                val currentCookies = cookieManager.getCookie(currentUrlDisplay) ?: cookieManager.getCookie("https://betfury.com") ?: ""

                                                var finalSession = if (tokenExtracted.isNotBlank()) tokenExtracted else "betfury_session"
                                                if (uidExtracted.isNotBlank()) finalSession += ";uid=$uidExtracted"
                                                if (domBal > 0.0) finalSession += ";bal=$domBal"
                                                if (currentCookies.isNotBlank()) finalSession += ";cookies=$currentCookies"

                                                verifyAndConnectSession(finalSession, domBal)
                                            }
                                        } else {
                                            val cookieManager = CookieManager.getInstance()
                                            val currentCookies = cookieManager.getCookie(currentUrlDisplay) ?: cookieManager.getCookie(platform.defaultLoginUrl) ?: ""
                                            verifyAndConnectSession(currentCookies)
                                        }
                                    }
                                    .padding(vertical = 10.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                                ) {
                                    if (isVerifyingSession) {
                                        CircularProgressIndicator(
                                            modifier = Modifier.size(14.dp),
                                            strokeWidth = 2.dp,
                                            color = RaptechColors.OrangePrimary
                                        )
                                    } else {
                                        Icon(
                                            imageVector = Icons.Default.CheckCircle,
                                            contentDescription = null,
                                            tint = Color.White,
                                            modifier = Modifier.size(15.dp)
                                        )
                                    }
                                    Text(
                                        text = if (isVerifyingSession) "Memverifikasi Akun..." else "Verifikasi & Hubungkan Sesi Saat Ini",
                                        color = if (isVerifyingSession) RaptechColors.TextSecondary else Color.White,
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                        }
                    }
                }

                1 -> {
                    // === TAB 1: MANUAL COOKIE / TOKEN INPUT WITH INSTANT TEST ===
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth()
                            .verticalScroll(rememberScrollState())
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Key,
                                contentDescription = null,
                                tint = RaptechColors.OrangePrimary,
                                modifier = Modifier.size(24.dp)
                            )
                            Column {
                                Text(
                                    text = "Input Kredensial Langsung",
                                    color = RaptechColors.TextPrimary,
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.Bold
                                )
                                Text(
                                    text = "Tempelkan string Cookie (user_session & csrf_cookie_name) dari browser untuk login instan.",
                                    color = RaptechColors.TextSecondary,
                                    fontSize = 10.sp
                                )
                            }
                        }

                        // Panduan per platform
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(6.dp))
                                .background(RaptechColors.OrangeSoft)
                                .border(1.dp, RaptechColors.OrangeBorder, RoundedCornerShape(6.dp))
                                .padding(10.dp)
                        ) {
                            Text(
                                text = if (platform == CasinoPlatform.BETFURY) {
                                    "Format Kredensial ${platform.displayName}:\n- JWT Token: eyJhbGciOi...\n- Atau Cookie: token=eyJ...; uid=123...\n\nAnda dapat menyalin token dari Application > Local Storage > token atau dari Cookies di browser."
                                } else {
                                    "Format Cookie ${platform.displayName}:\nuser_session=abc123...; csrf_cookie_name=xyz789...\n\nAnda dapat menyalin cookie dari Chrome DevTools (Application > Cookies) saat login di browser."
                                },
                                color = RaptechColors.OrangePrimary,
                                fontSize = 11.sp,
                                lineHeight = 16.sp
                            )
                        }

                        // Input Box
                        Column {
                            Text(
                                text = if (platform == CasinoPlatform.BETFURY) "Token JWT / Cookie Betfury:" else "String Cookie / Sesi Akun:",
                                color = RaptechColors.TextPrimary,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(110.dp)
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(RaptechColors.SurfaceLight)
                                    .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                                    .padding(8.dp)
                            ) {
                                if (manualTokenInput.isEmpty()) {
                                    Text(
                                        text = if (platform == CasinoPlatform.BETFURY) "Tempel token JWT (eyJ...) atau cookie sesi di sini..." else "Tempel string cookie sesi di sini...",
                                        color = RaptechColors.TextMuted,
                                        fontSize = 11.sp
                                    )
                                }
                                BasicTextField(
                                    value = manualTokenInput,
                                    onValueChange = { manualTokenInput = it },
                                    modifier = Modifier.fillMaxSize(),
                                    textStyle = androidx.compose.ui.text.TextStyle(
                                        color = RaptechColors.TextPrimary,
                                        fontSize = 11.sp,
                                        fontFamily = FontFamily.Monospace,
                                        lineHeight = 15.sp
                                    ),
                                    cursorBrush = SolidColor(RaptechColors.OrangePrimary)
                                )
                            }
                        }

                        if (manualStatusMessage != null) {
                            Text(
                                text = manualStatusMessage!!,
                                color = if (manualStatusMessage!!.startsWith("✅")) RaptechColors.WinSuccess else RaptechColors.LossDanger,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }

                        // Test & Connect Button
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(6.dp))
                                .background(if (isManualVerifying) RaptechColors.SurfaceLight else RaptechColors.OrangePrimary)
                                .clickable(enabled = !isManualVerifying) {
                                    val clean = manualTokenInput.trim()
                                    if (clean.isBlank()) {
                                        manualStatusMessage = "❌ Masukkan string cookie terlebih dahulu."
                                        return@clickable
                                    }

                                    isManualVerifying = true
                                    manualStatusMessage = "Menguji koneksi ke ${platform.displayName}..."

                                    coroutineScope.launch {
                                        val testAdapter: CasinoPlatformAdapter = if (platform == CasinoPlatform.BETFURY) {
                                            BetfuryAdapter(clean)
                                        } else {
                                            PickIoAdapter(platform, clean)
                                        }
                                        val balRes = testAdapter.fetchBalance(platform.defaultCurrency)

                                        withContext(Dispatchers.Main) {
                                            isManualVerifying = false
                                            if (balRes.isSuccess) {
                                                val bal = balRes.getOrThrow()
                                                manualStatusMessage = "✅ Sesi Valid! Saldo: $bal ${platform.defaultCurrency}"
                                                onSessionCaptured(clean)
                                                delay(1200)
                                                onDismiss()
                                            } else {
                                                val err = balRes.exceptionOrNull()?.message ?: "Sesi tidak valid"
                                                manualStatusMessage = "❌ $err"
                                            }
                                        }
                                    }
                                }
                                .padding(vertical = 11.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                if (isManualVerifying) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(14.dp),
                                        strokeWidth = 2.dp,
                                        color = RaptechColors.OrangePrimary
                                    )
                                }
                                Text(
                                    text = if (isManualVerifying) "Menguji Koneksi..." else "Test & Hubungkan Sesi ${platform.displayName}",
                                    color = if (isManualVerifying) RaptechColors.TextSecondary else Color.White,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            webViewRef?.destroy()
            webViewRef = null
        }
    }
}
