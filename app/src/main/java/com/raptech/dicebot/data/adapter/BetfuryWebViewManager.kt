package com.raptech.dicebot.data.adapter

import android.annotation.SuppressLint
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import com.raptech.dicebot.data.model.BetResponse
import com.raptech.dicebot.data.network.CasinoHttpClient
import com.raptech.dicebot.model.CoinBalance
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong

@SuppressLint("SetJavaScriptEnabled", "StaticFieldLeak")
object BetfuryWebViewManager {

    private const val TAG = "BetfuryWebViewManager"
    const val BETFURY_DICE_URL = "https://betfury.com/casino/games/dice"

    private val mainHandler by lazy {
        try {
            Handler(Looper.getMainLooper())
        } catch (_: Throwable) {
            null
        }
    }
    private var persistentWebView: WebView? = null

    val cachedBalances = ConcurrentHashMap<String, Double>()
    private val nonceCounter = AtomicLong(1)

    @Volatile var isPageLoaded: Boolean = false
    @Volatile var isWebSocketCaptured: Boolean = false
    @Volatile var capturedToken: String = ""
    @Volatile var capturedUid: String = ""
    @Volatile var capturedFingerprint: String = ""

    private var pendingBetDeferred: CompletableDeferred<BetResponse>? = null
    private var pendingBetAmount: Double = 0.0
    private var pendingBetCurrency: String = "BFG"

    private fun logD(msg: String) {
        try { Log.d(TAG, msg) } catch (_: Throwable) { println("[$TAG] $msg") }
    }
    private fun logW(msg: String) {
        try { Log.w(TAG, msg) } catch (_: Throwable) { println("[$TAG] WARN: $msg") }
    }
    private fun logE(msg: String) {
        try { Log.e(TAG, msg) } catch (_: Throwable) { System.err.println("[$TAG] ERROR: $msg") }
    }

    /**
     * JavaScript hook script to intercept WebSocket, DOM balances, and dice roll events
     */
    val INJECTION_SCRIPT = """
        (function() {
            if (window.__dicebot_installed) return;
            window.__dicebot_installed = true;
            console.log('[DicebotBridge] Injecting Betfury in-page automation hooks...');

            window.__dicebot_ws = null;
            window.__dicebot_last_result = null;

            // 1. Monkey-patch window.WebSocket to capture Betfury official connection
            var _OrigWS = window.WebSocket;
            window.WebSocket = function(url, protocols) {
                var ws = protocols ? new _OrigWS(url, protocols) : new _OrigWS(url);
                try {
                    var urlStr = (url || '').toString();
                    if (urlStr.indexOf('betfury') !== -1 || urlStr.indexOf('socket.io') !== -1) {
                        window.__dicebot_ws = ws;
                        console.log('[DicebotBridge] Official Betfury WebSocket intercepted:', urlStr);
                        if (window.DicebotBridge && window.DicebotBridge.onWebSocketIntercepted) {
                            window.DicebotBridge.onWebSocketIntercepted(urlStr);
                        }

                        // Intercept outgoing packets
                        var origSend = ws.send.bind(ws);
                        ws.send = function(data) {
                            try {
                                if (typeof data === 'string') {
                                    if (data.indexOf('profile.token') !== -1) {
                                        console.log('[DicebotBridge] Captured profile.token packet:', data);
                                        if (window.DicebotBridge && window.DicebotBridge.onRawTokenPacket) {
                                            window.DicebotBridge.onRawTokenPacket(data);
                                        }
                                    }
                                }
                            } catch(e) {}
                            return origSend(data);
                        };

                        // Intercept incoming packets
                        ws.addEventListener('message', function(ev) {
                            try {
                                var msg = ev.data;
                                if (typeof msg === 'string') {
                                    if (msg.indexOf('winAmount') !== -1 || msg.indexOf('roll_number') !== -1 || msg.indexOf('games.dice.bet') !== -1) {
                                        console.log('[DicebotBridge] Intercepted dice response:', msg);
                                        if (window.DicebotBridge && window.DicebotBridge.onRawBetResult) {
                                            window.DicebotBridge.onRawBetResult(msg);
                                        }
                                    }
                                    if (msg.indexOf('currencies') !== -1 || msg.indexOf('user') !== -1) {
                                        if (window.DicebotBridge && window.DicebotBridge.onCurrenciesUpdate) {
                                            window.DicebotBridge.onCurrenciesUpdate(msg);
                                        }
                                    }
                                }
                            } catch(e) {}
                        });
                    }
                } catch(e) {}
                return ws;
            };
            window.WebSocket.prototype = _OrigWS.prototype;

            // 2. Continuous Balance Scanner
            window.__dicebotScanBalances = function() {
                try {
                    // Try Nuxt store
                    if (window.${'$'}nuxt && window.${'$'}nuxt.${'$'}store && window.${'$'}nuxt.${'$'}store.state) {
                        var u = window.${'$'}nuxt.${'$'}store.state.user;
                        if (u && u.currencies && window.DicebotBridge && window.DicebotBridge.onCurrenciesUpdate) {
                            window.DicebotBridge.onCurrenciesUpdate(JSON.stringify(u.currencies));
                        }
                    }
                    // Try DOM balance scan
                    var allElements = document.querySelectorAll('span, div, p');
                    for (var e = 0; e < allElements.length; e++) {
                        var el = allElements[e];
                        if (el.children.length === 0 && el.innerText) {
                            var txt = el.innerText.trim();
                            if (/^\d+\.\d{4,8}${'$'}/.test(txt)) {
                                var parsed = parseFloat(txt);
                                if (parsed > 0 && window.DicebotBridge && window.DicebotBridge.onBalanceUpdated) {
                                    window.DicebotBridge.onBalanceUpdated('BFG', parsed);
                                    break;
                                }
                            }
                        }
                    }
                } catch(e) {}
            };

            // 3. Execution Function: Place Bet
            window.__dicebotPlaceBet = function(amountStr, prediction, isUnder, currency) {
                try {
                    // A. Fast path: Send directly via the intercepted official WebSocket
                    if (window.__dicebot_ws && window.__dicebot_ws.readyState === 1) {
                        var payload = {
                            amount: amountStr,
                            frontID: Date.now(),
                            isBonusBet: false,
                            isFast: true,
                            is_under: isUnder,
                            prediction: prediction,
                            strategyName: "",
                            version: "main"
                        };
                        var ackId = Math.floor(Math.random() * 900000) + 100000;
                        var packet = "42" + ackId + JSON.stringify(["games.dice.bet", payload]);
                        window.__dicebot_ws.send(packet);
                        console.log('[DicebotBridge] Dispatched bet via intercepted WebSocket:', packet);
                        return "DISPATCHED_WS";
                    }

                    // B. Fallback path: Trigger DOM Bet Button
                    var rollBtn = document.querySelector('button[type="submit"], button.dice-play, button.bet-btn');
                    if (rollBtn) {
                        var inputs = document.querySelectorAll('input');
                        for (var i = 0; i < inputs.length; i++) {
                            if (inputs[i].value !== undefined && /amount|bet/i.test(inputs[i].getAttribute('name') || inputs[i].getAttribute('placeholder') || inputs[i].className)) {
                                inputs[i].value = amountStr;
                                inputs[i].dispatchEvent(new Event('input', { bubbles: true }));
                                inputs[i].dispatchEvent(new Event('change', { bubbles: true }));
                                break;
                            }
                        }
                        rollBtn.click();
                        console.log('[DicebotBridge] Dispatched bet via DOM button click');
                        return "DISPATCHED_DOM";
                    }

                    if (window.DicebotBridge && window.DicebotBridge.onError) {
                        window.DicebotBridge.onError("WebSocket Betfury belum terhubung. Pastikan halaman selesai dimuat.");
                    }
                    return "NOT_READY";
                } catch(err) {
                    if (window.DicebotBridge && window.DicebotBridge.onError) {
                        window.DicebotBridge.onError("Error eksekusi: " + err.message);
                    }
                    return "EXCEPTION";
                }
            };
        })();
    """.trimIndent()

    class BridgeInterface {
        @JavascriptInterface
        fun onWebSocketIntercepted(url: String) {
            logD("WebSocket resmi Betfury berhasil dicegat: $url")
            isWebSocketCaptured = true
        }

        @JavascriptInterface
        fun onRawTokenPacket(raw: String) {
            logD("Paket profile.token resmi tertangkap: $raw")
            try {
                // Parse token, uid, fingerprint from intercepted packet
                val tokenRegex = Regex("""["']?(?:token|auth_token)["']?\s*:\s*["']([^"']+)["']""")
                val uidRegex = Regex("""["']?(?:uid|userId|user_id)["']?\s*:\s*["']([^"']+)["']""")
                val fpRegex = Regex("""["']?(?:fingerprint)["']?\s*:\s*["']([^"']+)["']""")

                tokenRegex.find(raw)?.groupValues?.get(1)?.let { capturedToken = it }
                uidRegex.find(raw)?.groupValues?.get(1)?.let { capturedUid = it }
                fpRegex.find(raw)?.groupValues?.get(1)?.let { capturedFingerprint = it }

                logD("Ekstraksi kredensial resmi sukses: token=${capturedToken.take(15)}... uid=$capturedUid")
            } catch (e: Exception) {
                logW("Gagal parse raw token packet: ${e.message}")
            }
        }

        @JavascriptInterface
        fun onRawBetResult(rawJson: String) {
            logD("Hasil taruhan dadu tertangkap: $rawJson")
            val def = pendingBetDeferred ?: return

            try {
                // Find JSON substring
                val firstBrace = rawJson.indexOf('{')
                val lastBrace = rawJson.lastIndexOf('}')
                if (firstBrace == -1 || lastBrace <= firstBrace) {
                    def.completeExceptionally(IOException("Format respon taruhan tidak valid: $rawJson"))
                    return
                }

                val cleanJson = rawJson.substring(firstBrace, lastBrace + 1)
                val root = JSONObject(cleanJson)
                val resp = root.optJSONObject("response") ?: root

                val winAmountStr = resp.optString("winAmount", "")
                val winAmount = if (winAmountStr.isNotBlank()) {
                    winAmountStr.toDoubleOrNull() ?: 0.0
                } else {
                    resp.optDouble("winAmount", 0.0)
                }
                val isWin = winAmount > 0.0

                // Betfury official calculation:
                // When WIN: profit = winAmount - wageredAmount
                // When LOSE: profit = -wageredAmount
                val profit = if (isWin) {
                    val p = resp.optDouble("profit", Double.NaN)
                    if (!p.isNaN() && p > 0.0) p else (winAmount - pendingBetAmount)
                } else {
                    -pendingBetAmount
                }

                val rollResult = resp.optDouble("roll_number", resp.optDouble("roll", if (isWin) 75.0 else 25.0))

                // Update cached balance
                val user = resp.optJSONObject("user")
                var curBal = cachedBalances[pendingBetCurrency] ?: 0.0
                if (user != null) {
                    val currencies = user.optJSONObject("currencies")
                    if (currencies != null) {
                        val keys = currencies.keys()
                        while (keys.hasNext()) {
                            val k = keys.next()
                            val cObj = currencies.optJSONObject(k)
                            val b = cObj?.optDouble("balance", 0.0) ?: 0.0
                            cachedBalances[k.uppercase(Locale.ROOT)] = b
                        }
                    }
                    curBal = cachedBalances[pendingBetCurrency] ?: (curBal + profit)
                } else {
                    curBal += profit
                    cachedBalances[pendingBetCurrency] = curBal
                }

                val nonce = nonceCounter.getAndIncrement()
                val betResponse = BetResponse(
                    success = true,
                    nonce = nonce,
                    rollResult = rollResult,
                    isWin = isWin,
                    profit = profit,
                    newBalance = curBal,
                    rawMessage = cleanJson
                )

                pendingBetDeferred = null
                def.complete(betResponse)
            } catch (e: Exception) {
                pendingBetDeferred = null
                def.completeExceptionally(e)
            }
        }

        @JavascriptInterface
        fun onCurrenciesUpdate(raw: String) {
            try {
                val firstBrace = raw.indexOf('{')
                val lastBrace = raw.lastIndexOf('}')
                if (firstBrace != -1 && lastBrace > firstBrace) {
                    val root = JSONObject(raw.substring(firstBrace, lastBrace + 1))
                    val curObj = root.optJSONObject("currencies")
                        ?: root.optJSONObject("response")?.optJSONObject("user")?.optJSONObject("currencies")
                        ?: root.optJSONObject("response")?.optJSONObject("currencies")
                        ?: root.optJSONObject("user")?.optJSONObject("currencies")
                        ?: root

                    val keys = curObj.keys()
                    while (keys.hasNext()) {
                        val k = keys.next()
                        if (k.equals("response", ignoreCase = true) || k.equals("user", ignoreCase = true)) continue
                        val v = curObj.opt(k)
                        val bal = when (v) {
                            is JSONObject -> v.optDouble("balance", 0.0)
                            is Number -> v.toDouble()
                            is String -> v.toDoubleOrNull() ?: 0.0
                            else -> 0.0
                        }
                        cachedBalances[k.uppercase(Locale.ROOT)] = bal
                    }
                    logD("Saldo diperbarui dari Nuxt/Store: ${cachedBalances.size} koin terdeteksi: ${cachedBalances.keys().toList()}")
                }
            } catch (_: Exception) {}
        }

        @JavascriptInterface
        fun onBalanceUpdated(coin: String, balance: Double) {
            if (balance > 0.0) {
                cachedBalances[coin.uppercase(Locale.ROOT)] = balance
            }
        }

        @JavascriptInterface
        fun onError(msg: String) {
            logE("Bridge error: $msg")
            pendingBetDeferred?.completeExceptionally(IOException(msg))
            pendingBetDeferred = null
        }
    }

    fun getOrCreateWebView(context: Context): WebView {
        persistentWebView?.let { return it }

        logD("Membuat instance Persistent WebView untuk Betfury In-App Bridge...")
        val wv = WebView(context.applicationContext)
        configureWebView(wv)
        persistentWebView = wv
        return wv
    }

    private fun configureWebView(wv: WebView) {
        wv.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            userAgentString = CasinoHttpClient.currentUserAgent
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            useWideViewPort = true
            loadWithOverviewMode = true
            setSupportZoom(false)
        }

        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(wv, true)
        }

        wv.addJavascriptInterface(BridgeInterface(), "DicebotBridge")

        wv.webChromeClient = WebChromeClient()
        wv.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                super.onPageStarted(view, url, favicon)
                logD("Halaman mulai dimuat: $url, menyuntikkan early WebSocket hook...")
                view?.evaluateJavascript(INJECTION_SCRIPT, null)
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                logD("Halaman selesai dimuat: $url")
                isPageLoaded = true
                view?.evaluateJavascript(INJECTION_SCRIPT) {
                    view.evaluateJavascript("window.__dicebotScanBalances();", null)
                }
            }
        }

        // Preload Dice Page
        wv.loadUrl(BETFURY_DICE_URL)
    }

    suspend fun placeBet(
        amount: Double,
        target: Double,
        isHigh: Boolean,
        currency: String
    ): Result<BetResponse> = withContext(Dispatchers.IO) {
        val wv = persistentWebView ?: return@withContext Result.failure(
            IllegalStateException("WebView Betfury belum diinisialisasi.")
        )

        val deferred = CompletableDeferred<BetResponse>()
        pendingBetDeferred = deferred
        pendingBetAmount = amount
        pendingBetCurrency = currency.uppercase(Locale.ROOT)

        val chance = target.coerceIn(0.01, 98.0)
        val prediction = if (isHigh) (99.0 - chance).toInt() else chance.toInt()
        val amountStr = String.format(Locale.US, "%.8f", amount)
        val isUnder = !isHigh

        withContext(Dispatchers.Main) {
            val js = "window.__dicebotPlaceBet('$amountStr', $prediction, $isUnder, '${currency.lowercase(Locale.ROOT)}');"
            wv.evaluateJavascript(js) { res ->
                logD("Respon evaluateJavascript placeBet: $res")
            }
        }

        try {
            val response = withTimeout(3500L) {
                deferred.await()
            }
            Result.success(response)
        } catch (e: Exception) {
            pendingBetDeferred = null
            Result.failure(e)
        }
    }

    suspend fun fetchBalance(currency: String): Result<Double> = withContext(Dispatchers.IO) {
        val cur = currency.uppercase(Locale.ROOT)
        // Check memory cache
        cachedBalances[cur]?.let {
            if (it > 0.0) return@withContext Result.success(it)
        }

        // Trigger balance scan on WebView
        withContext(Dispatchers.Main) {
            persistentWebView?.evaluateJavascript("window.__dicebotScanBalances();", null)
        }

        // Recheck cache
        val bal = cachedBalances[cur] ?: 0.0
        Result.success(bal)
    }

    fun isReady(): Boolean {
        return persistentWebView != null && (isWebSocketCaptured || isPageLoaded || cachedBalances.isNotEmpty())
    }
}
