package com.raptech.dicebot.data.adapter

import android.util.Log
import com.raptech.dicebot.data.model.BetResponse
import com.raptech.dicebot.data.network.CasinoHttpClient
import com.raptech.dicebot.model.CasinoPlatform
import com.raptech.dicebot.model.CoinBalance
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.math.BigDecimal
import java.math.RoundingMode
import java.util.Base64
import java.util.Locale
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong

class BetfuryAdapter(
    private var rawCredential: String = "",
    private var defaultCurrency: String = "BFG"
) : CasinoPlatformAdapter {

    companion object {
        private const val TAG = "BetfuryAdapter"
        private const val BASE_URL = "https://betfury.com"
        private const val BASE_WS = "wss://betfury.com"

        private fun logD(msg: String) {
            try { Log.d(TAG, msg) } catch (_: Throwable) { println("[$TAG] $msg") }
        }
        private fun logW(msg: String) {
            try { Log.w(TAG, msg) } catch (_: Throwable) { println("[$TAG] WARN: $msg") }
        }
        private fun logE(msg: String) {
            try { Log.e(TAG, msg) } catch (_: Throwable) { System.err.println("[$TAG] ERROR: $msg") }
        }

        fun parseCredentials(raw: String): Triple<String, String, String> {
            val trimmed = raw.trim().trim('"', '\'')
            var token = ""
            var uid = ""

            // 0. Check BetfuryWebViewManager captured credentials first if available
            if (BetfuryWebViewManager.capturedToken.isNotBlank()) {
                token = BetfuryWebViewManager.capturedToken
                uid = BetfuryWebViewManager.capturedUid
                val fp = if (BetfuryWebViewManager.capturedFingerprint.isNotBlank()) {
                    BetfuryWebViewManager.capturedFingerprint
                } else if (uid.contains("_")) {
                    uid.split("_")[0]
                } else {
                    uid
                }
                if (token.isNotBlank()) {
                    return Triple(token, uid, fp)
                }
            }

            // 1. Check for JWT pattern anywhere (starts with eyJ... with 2 or 3 segments)
            val jwtRegex = Regex("""eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_.-]+""")
            val jwtMatch = jwtRegex.find(trimmed)
            if (jwtMatch != null) {
                token = jwtMatch.value.trim()
            }

            // 2. If not found via regex, check JSON object
            if (token.isBlank() && trimmed.startsWith("{") && trimmed.endsWith("}")) {
                val tokenRegex = Regex("""["']?(?:token|auth_token|jwt|accessToken|session_token)["']?\s*:\s*["']([^"']+)["']""")
                val uidRegex = Regex("""["']?(?:uid|userId|user_id)["']?\s*:\s*["']([^"']+)["']""")
                tokenRegex.find(trimmed)?.groupValues?.get(1)?.let { token = it.trim() }
                uidRegex.find(trimmed)?.groupValues?.get(1)?.let { uid = it.trim() }
            }

            // 3. Check delimited key-value pairs (cookies or query style)
            if (trimmed.contains("=") || trimmed.contains(";")) {
                val parts = trimmed.split(";")
                for (p in parts) {
                    val trimmedPart = p.trim()
                    if (trimmedPart.contains("=")) {
                        val kv = trimmedPart.split("=", limit = 2)
                        val key = kv[0].trim().lowercase(Locale.ROOT)
                        val value = kv[1].trim().trim('"', '\'')
                        if (token.isBlank() && (key == "token" || key == "auth_token" || key == "bf_token" || key == "jwt" || key == "accesstoken")) {
                            token = value
                        }
                        if (uid.isBlank() && (key == "uid" || key == "userid" || key == "user_id")) {
                            uid = value
                        }
                    } else if (token.isBlank() && trimmedPart.isNotBlank()) {
                        token = trimmedPart
                    }
                }
            }

            // 4. Fallback: single raw string
            if (token.isBlank() && !trimmed.contains(";") && !trimmed.contains("=")) {
                token = trimmed
            }

            token = token.removePrefix("Bearer ").trim()
            uid = uid.removePrefix("uid=").trim()

            // 5. If uid is still empty, attempt to extract userId from JWT payload
            if (uid.isBlank() && token.contains(".")) {
                uid = extractUidFromJwt(token)
            }

            val fingerprint = if (uid.contains("_")) uid.split("_")[0] else uid
            return Triple(token, uid, fingerprint)
        }

        private fun extractUidFromJwt(jwt: String): String {
            try {
                val parts = jwt.split(".")
                if (parts.size >= 2) {
                    var b64 = parts[1].replace('-', '+').replace('_', '/')
                    while (b64.length % 4 != 0) {
                        b64 += "="
                    }
                    val decoded = String(Base64.getDecoder().decode(b64), Charsets.UTF_8)
                    val uidRegex = Regex("""["']?(?:userId|user_id|id|sub|uid)["']?\s*:\s*["']?([^"',}]+)["']?""")
                    return uidRegex.find(decoded)?.groupValues?.get(1)?.trim() ?: ""
                }
            } catch (_: Exception) { }
            return ""
        }
    }

    private val client = CasinoHttpClient.client
    private val connectMutex = Mutex()
    private val ackCallbacks = ConcurrentHashMap<Int, CompletableDeferred<String>>()
    private val ackCounter = AtomicInteger(0)
    private val nonceCounter = AtomicLong(1)

    private var pureToken: String = ""
    private var uid: String = ""
    private var fingerprint: String = ""

    private var webSocket: WebSocket? = null
    @Volatile private var isConnected: Boolean = false
    @Volatile private var isAuthed: Boolean = false
    @Volatile private var joinedDiceRoom: Boolean = false
    @Volatile private var activeCurrency: String = defaultCurrency.uppercase(Locale.ROOT)

    private val cachedBalances = ConcurrentHashMap<String, Double>()
    private var authDeferred: CompletableDeferred<Boolean>? = null

    init {
        setCredentials(rawCredential)
    }

    fun setCredentials(credential: String) {
        rawCredential = credential.trim()
        val parsed = parseCredentials(rawCredential)
        pureToken = parsed.first
        uid = parsed.second
        fingerprint = parsed.third

        // Parse initial balance if present (e.g. bal=24.5006732)
        val balRegex = Regex("""(?:bal|balance)=([0-9.]+)""")
        balRegex.find(rawCredential)?.groupValues?.get(1)?.toDoubleOrNull()?.let { b ->
            if (b > 0.0) {
                cachedBalances[activeCurrency] = b
            }
        }
        disconnect()
    }

    fun setInitialBalance(currency: String, balance: Double) {
        if (balance > 0.0) {
            val cur = currency.uppercase(Locale.ROOT)
            cachedBalances[cur] = balance
            isAuthed = true
        }
    }

    fun getCredentials(): String = rawCredential

    override fun getPlatformName(): String = CasinoPlatform.BETFURY.displayName

    private fun nextAckId(): Int = ackCounter.incrementAndGet()

    suspend fun ensureConnected(): Unit = withContext(Dispatchers.IO) {
        if (isConnected && isAuthed && webSocket != null) return@withContext

        connectMutex.withLock {
            if (isConnected && isAuthed && webSocket != null) return@withLock

            if (pureToken.isBlank()) {
                throw IllegalStateException("Token Betfury belum diatur. Harap login atau masukkan token Betfury.")
            }

            disconnect()

            val ts = System.currentTimeMillis()
            val pollUrl = "$BASE_URL/socket.io/?mobile=false&EIO=4&transport=polling&t=$ts"
            val pollReqBuilder = Request.Builder()
                .url(pollUrl)
                .header("User-Agent", CasinoHttpClient.currentUserAgent)
                .header("Origin", BASE_URL)

            if (pureToken.isNotBlank()) {
                pollReqBuilder.header("Authorization", "Bearer $pureToken")
            }
            if (rawCredential.contains("=")) {
                pollReqBuilder.header("Cookie", rawCredential)
            }

            val pollRequest = pollReqBuilder.build()

            val pollResp = client.newCall(pollRequest).execute().use { response ->
                if (!response.isSuccessful) {
                    throw IOException("Gagal polling handshake Betfury: HTTP ${response.code}")
                }
                response.body?.string() ?: ""
            }

            if (!pollResp.startsWith("0{")) {
                throw IOException("Format handshake Betfury invalid: $pollResp")
            }

            val handshakeJson = JSONObject(pollResp.substring(1))
            val sid = handshakeJson.optString("sid")
            if (sid.isBlank()) {
                throw IOException("Gagal mendapatkan Session ID (SID) dari Betfury.")
            }

            val wsUrl = "$BASE_WS/socket.io/?mobile=false&EIO=4&transport=websocket&sid=$sid"
            val wsReqBuilder = Request.Builder()
                .url(wsUrl)
                .header("User-Agent", CasinoHttpClient.currentUserAgent)
                .header("Origin", BASE_URL)

            if (pureToken.isNotBlank()) {
                wsReqBuilder.header("Authorization", "Bearer $pureToken")
            }
            if (rawCredential.contains("=")) {
                wsReqBuilder.header("Cookie", rawCredential)
            }

            val wsRequest = wsReqBuilder.build()

            val deferred = CompletableDeferred<Boolean>()
            authDeferred = deferred

            webSocket = client.newWebSocket(wsRequest, object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    logD("WebSocket open. Sending probe...")
                    webSocket.send("2probe")
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    handleIncomingPacket(webSocket, text)
                }

                override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                    logD("WebSocket closing: $code / $reason")
                    isConnected = false
                    isAuthed = false
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    logE("WebSocket failure: ${t.message}")
                    isConnected = false
                    isAuthed = false
                    authDeferred?.completeExceptionally(t)
                }
            })

            // Wait for auth verification with 12s timeout
            withTimeout(12000L) {
                deferred.await()
            }

            // Join dice room
            try {
                joinDiceRoom()
            } catch (e: Exception) {
                logW("Dice room join warning: ${e.message}")
            }
        }
    }

    private fun handleIncomingPacket(ws: WebSocket, msg: String) {
        if (msg.isBlank()) return

        // 1. Probe response
        if (msg == "3probe") {
            ws.send("5") // upgrade confirmation
            ws.send("40") // connect namespace /
            return
        }

        // 1b. Socket.IO Namespace connected: 40 or 40{"sid":"..."}
        if (msg.startsWith("40")) {
            logD("Socket.IO namespace connected. Sending auth token packet...")
            sendAuthTokenPacket(ws)
            return
        }

        // 2. Engine.IO Ping -> Pong
        if (msg == "2") {
            ws.send("3")
            return
        }

        // 3. Token error detection
        if (msg.contains("token_error", ignoreCase = true)) {
            logE("Betfury server returned token_error!")
            authDeferred?.completeExceptionally(IllegalStateException("Token Betfury ditolak oleh server (token_error / expired)."))
            ackCallbacks.values.forEach { it.completeExceptionally(IllegalStateException("Token Betfury expired.")) }
            ackCallbacks.clear()
            return
        }

        // 4. Socket.IO ACK: 43{ackId}[data]
        if (msg.startsWith("43")) {
            val rest = msg.substring(2)
            var digitCount = 0
            while (digitCount < rest.length && rest[digitCount].isDigit()) digitCount++
            if (digitCount > 0) {
                val ackId = rest.substring(0, digitCount).toIntOrNull()
                val payload = rest.substring(digitCount)
                if (ackId != null) {
                    ackCallbacks.remove(ackId)?.complete(payload)
                }
            }
            return
        }

        // 5. Socket.IO Event: 42{ackId}[eventName, payload] or 42[eventName, payload]
        if (msg.startsWith("42")) {
            var jsonStart = 2
            while (jsonStart < msg.length && msg[jsonStart].isDigit()) jsonStart++
            val eventPayload = msg.substring(jsonStart)
            try {
                val array = JSONArray(eventPayload)
                if (array.length() >= 2) {
                    val eventName = array.optString(0)
                    val data = array.opt(1)
                    if (eventName.equals("profile.token", ignoreCase = true) ||
                        eventName.equals("profile", ignoreCase = true) ||
                        eventName.equals("user", ignoreCase = true)) {
                        if (data is JSONObject) {
                            processCurrenciesData(data)
                            isConnected = true
                            isAuthed = true
                            authDeferred?.complete(true)
                            ackCallbacks.forEach { (_, def) ->
                                if (!def.isCompleted) def.complete(data.toString())
                            }
                        }
                    }
                }
            } catch (_: Exception) { }
        }
    }

    private fun sendAuthTokenPacket(ws: WebSocket) {
        val ackId = nextAckId()
        val payload = JSONObject().apply {
            put("currency", activeCurrency.lowercase(Locale.ROOT))
            put("token", pureToken)
            put("fingerprint", fingerprint)
            put("tz", -420)
        }
        val packet = "42$ackId" + JSONArray().put("profile.token").put(payload).toString()

        val authAck = CompletableDeferred<String>()
        ackCallbacks[ackId] = authAck

        ws.send(packet)

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val result = withTimeout(9000L) { authAck.await() }
                if (result.contains("token_error", ignoreCase = true)) {
                    authDeferred?.completeExceptionally(IllegalStateException("Token Betfury ditolak."))
                } else {
                    try {
                        val array = JSONArray(result)
                        if (array.length() > 0 && array.opt(0) is JSONObject) {
                            processCurrenciesData(array.getJSONObject(0))
                        }
                    } catch (_: Exception) {
                        try {
                            val obj = JSONObject(result)
                            processCurrenciesData(obj)
                        } catch (_: Exception) {}
                    }
                    isConnected = true
                    isAuthed = true
                    authDeferred?.complete(true)
                }
            } catch (e: Exception) {
                if (isAuthed || cachedBalances.isNotEmpty()) {
                    logD("Auth ack timed out but session already authenticated via event 42.")
                    authDeferred?.complete(true)
                } else {
                    authDeferred?.completeExceptionally(e)
                }
            }
        }
    }

    private fun processCurrenciesData(data: JSONObject) {
        val resp = data.optJSONObject("response") ?: data
        val user = resp.optJSONObject("user") ?: resp
        val currencies = user.optJSONObject("currencies") ?: return

        val keys = currencies.keys()
        while (keys.hasNext()) {
            val coin = keys.next()
            val coinObj = currencies.optJSONObject(coin)
            val bal = coinObj?.optDouble("balance", 0.0) ?: 0.0
            cachedBalances[coin.uppercase(Locale.ROOT)] = bal
        }
        logD("Auto-detected ${cachedBalances.size} currencies from Betfury wallet.")
    }

    private suspend fun emitWithAck(eventName: String, payload: Any, timeoutMs: Long = 8000L): String {
        val ws = webSocket ?: throw IllegalStateException("WebSocket Betfury belum terhubung.")
        val ackId = nextAckId()
        val deferred = CompletableDeferred<String>()
        ackCallbacks[ackId] = deferred

        val packet = "42$ackId" + JSONArray().put(eventName).put(payload).toString()
        ws.send(packet)

        return withTimeout(timeoutMs) {
            deferred.await()
        }
    }

    suspend fun joinDiceRoom(): Boolean {
        return try {
            emitWithAck("games.dice.join", JSONObject(), 5000L)
            joinedDiceRoom = true
            true
        } catch (_: Exception) {
            // Fallback unacknowledged emit
            webSocket?.send("42" + JSONArray().put("games.dice.join").put(JSONObject()).toString())
            joinedDiceRoom = true
            false
        }
    }

    suspend fun changeCurrency(newCurrency: String): Boolean {
        val target = newCurrency.uppercase(Locale.ROOT)
        return try {
            emitWithAck("auth.changeCurrency", JSONObject().put("currency", target.lowercase(Locale.ROOT)), 5000L)
            activeCurrency = target
            // Refresh wallet
            val refreshAck = emitWithAck("profile.token", JSONObject().apply {
                put("token", pureToken)
                put("currency", target.lowercase(Locale.ROOT))
                put("fingerprint", fingerprint)
                put("tz", -420)
            }, 6000L)
            val array = JSONArray(refreshAck)
            if (array.length() > 0 && array.opt(0) is JSONObject) {
                processCurrenciesData(array.getJSONObject(0))
            }
            true
        } catch (e: Exception) {
            logW("Gagal changeCurrency Betfury ke $target: ${e.message}")
            false
        }
    }

    override suspend fun fetchBalance(currency: String): Result<Double> = withContext(Dispatchers.IO) {
        val cur = currency.uppercase(Locale.ROOT)

        // 1. Prioritas Utama: In-WebView Bridge (Imun Cloudflare & Sinkron Langsung ke Browser)
        if (BetfuryWebViewManager.isReady()) {
            val bridgeBal = BetfuryWebViewManager.fetchBalance(cur)
            if (bridgeBal.isSuccess && bridgeBal.getOrThrow() > 0.0) {
                cachedBalances[cur] = bridgeBal.getOrThrow()
                return@withContext bridgeBal
            }
        }

        // 2. Fallback: Background OkHttp Socket.IO
        try {
            ensureConnected()
            if (!cachedBalances.containsKey(cur) || cur != activeCurrency) {
                changeCurrency(cur)
            }
            val bal = cachedBalances[cur] ?: 0.0
            Result.success(bal)
        } catch (e: Exception) {
            val fallbackBal = cachedBalances[cur] ?: BetfuryWebViewManager.cachedBalances[cur]
            if (fallbackBal != null && fallbackBal > 0.0) {
                logW("WebSocket background ditahan Cloudflare, menggunakan saldo aktif bridge: $fallbackBal")
                Result.success(fallbackBal)
            } else {
                Result.failure(e)
            }
        }
    }

    override suspend fun fetchAvailableBalances(): Result<List<CoinBalance>> = withContext(Dispatchers.IO) {
        // Inisialisasi seluruh koin resmi yang didukung Betfury agar selalu muncul di daftar selector
        CasinoPlatform.BETFURY.supportedCoins.forEach { coin ->
            if (!cachedBalances.containsKey(coin)) {
                cachedBalances[coin] = BetfuryWebViewManager.cachedBalances[coin] ?: 0.0
            }
        }
        // Sinkronkan seluruh saldo dari BetfuryWebViewManager
        BetfuryWebViewManager.cachedBalances.forEach { (coin, bal) ->
            if (bal > 0.0 || !cachedBalances.containsKey(coin)) {
                cachedBalances[coin] = bal
            }
        }

        try {
            if (!BetfuryWebViewManager.isReady() && !isConnected) {
                ensureConnected()
            }
            val list = cachedBalances.map { (coin, bal) ->
                CoinBalance(currency = coin, balance = bal, isAvailable = true)
            }.sortedWith(
                compareByDescending<CoinBalance> { it.balance > 0 }
                    .thenByDescending { it.balance }
                    .thenBy { it.currency }
            )
            Result.success(list)
        } catch (e: Exception) {
            val list = cachedBalances.map { (coin, bal) ->
                CoinBalance(currency = coin, balance = bal, isAvailable = true)
            }.sortedWith(
                compareByDescending<CoinBalance> { it.balance > 0 }
                    .thenByDescending { it.balance }
                    .thenBy { it.currency }
            )
            Result.success(list)
        }
    }

    override suspend fun placeDiceBet(
        amount: Double,
        target: Double,
        isHigh: Boolean,
        currency: String
    ): Result<BetResponse> = withContext(Dispatchers.IO) {
        val cur = currency.uppercase(Locale.ROOT)

        // 1. Prioritas Utama: Direct OkHttp WebSocket jika sudah terkoneksi (Ultra-Fast < 100ms)
        if (isConnected && webSocket != null) {
            try {
                if (cur != activeCurrency) {
                    changeCurrency(cur)
                }
                if (!joinedDiceRoom) {
                    joinDiceRoom()
                }

                val chance = target.coerceIn(0.01, 98.0)
                val prediction = if (isHigh) (99.0 - chance).toInt() else chance.toInt()
                val formattedAmount = String.format(Locale.US, "%.8f", amount)

                val payload = JSONObject().apply {
                    put("amount", formattedAmount)
                    put("frontID", System.currentTimeMillis())
                    put("isBonusBet", false)
                    put("isFast", true) // Fast Bet Mode!
                    put("is_under", !isHigh)
                    put("prediction", prediction)
                    put("strategyName", "")
                    put("version", "main")
                }

                val betResultJson = emitWithAck("games.dice.bet", payload, 5000L)
                val array = JSONArray(betResultJson)
                if (array.length() > 0) {
                    val root = array.getJSONObject(0)
                    if (root.has("error") && !root.isNull("error")) {
                        val err = root.optString("error")
                        val code = root.optInt("code", 0)
                        if (code == 7305 || err.contains("Join the room first", ignoreCase = true)) {
                            joinedDiceRoom = false
                            joinDiceRoom()
                            val retryJson = emitWithAck("games.dice.bet", payload, 5000L)
                            val retryArr = JSONArray(retryJson)
                            return@withContext parseBetPayload(retryArr.getJSONObject(0), cur, amount)
                        }
                        throw IOException("Betfury Bet Error: $err (code=$code)")
                    }
                    return@withContext parseBetPayload(root, cur, amount)
                }
            } catch (e: Exception) {
                logW("Direct OkHttp socket roll error (${e.message}), mencoba bridge/reconnect...")
            }
        }

        // 2. Jika OkHttp belum connect, coba In-WebView Bridge (Fast 3s timeout)
        if (BetfuryWebViewManager.isReady() && BetfuryWebViewManager.isWebSocketCaptured) {
            val bridgeRes = BetfuryWebViewManager.placeBet(amount, target, isHigh, cur)
            if (bridgeRes.isSuccess) {
                val data = bridgeRes.getOrThrow()
                cachedBalances[cur] = data.newBalance
                return@withContext bridgeRes
            }
        }

        // 3. Fallback: Hubungkan OkHttp Socket dan kirim taruhan
        try {
            ensureConnected()
            if (cur != activeCurrency) {
                changeCurrency(cur)
            }

            if (!joinedDiceRoom) {
                joinDiceRoom()
            }

            val chance = target.coerceIn(0.01, 98.0)
            val prediction = if (isHigh) (99.0 - chance).toInt() else chance.toInt()
            val formattedAmount = String.format(Locale.US, "%.8f", amount)

            val payload = JSONObject().apply {
                put("amount", formattedAmount)
                put("frontID", System.currentTimeMillis())
                put("isBonusBet", false)
                put("isFast", true) // Fast Bet Mode!
                put("is_under", !isHigh)
                put("prediction", prediction)
                put("strategyName", "")
                put("version", "main")
            }

            var betResultJson: String
            try {
                betResultJson = emitWithAck("games.dice.bet", payload, 5000L)
            } catch (e: Exception) {
                joinedDiceRoom = false
                joinDiceRoom()
                betResultJson = emitWithAck("games.dice.bet", payload, 5000L)
            }

            val array = JSONArray(betResultJson)
            if (array.length() == 0) {
                throw IOException("Respon kosong dari Betfury dice bet.")
            }

            val root = array.getJSONObject(0)
            if (root.has("error") && !root.isNull("error")) {
                val err = root.optString("error")
                val code = root.optInt("code", 0)
                if (code == 7305 || err.contains("Join the room first", ignoreCase = true)) {
                    joinedDiceRoom = false
                    joinDiceRoom()
                    val retryJson = emitWithAck("games.dice.bet", payload, 5000L)
                    val retryArr = JSONArray(retryJson)
                    val retryRoot = retryArr.getJSONObject(0)
                    return@withContext parseBetPayload(retryRoot, cur, amount)
                }
                throw IOException("Betfury Bet Error: $err (code=$code)")
            }

            parseBetPayload(root, cur, amount)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun parseBetPayload(root: JSONObject, cur: String, wageredAmount: Double): Result<BetResponse> {
        val resp = root.optJSONObject("response") ?: root
        val winAmountStr = resp.optString("winAmount", "")
        val winAmount = if (winAmountStr.isNotBlank()) {
            winAmountStr.toDoubleOrNull() ?: 0.0
        } else {
            resp.optDouble("winAmount", 0.0)
        }
        val isWin = winAmount > 0.0

        // Betfury official calculation:
        // When WIN: profit = winAmount - wageredAmount (positive net profit)
        // When LOSE: profit = -wageredAmount (negative loss)
        val profit = if (isWin) {
            val p = resp.optDouble("profit", Double.NaN)
            if (!p.isNaN() && p > 0.0) p else (winAmount - wageredAmount)
        } else {
            -wageredAmount
        }

        val rollResult = resp.optDouble("roll_number", resp.optDouble("roll", if (isWin) 75.0 else 25.0))

        // Update cached balance
        val user = resp.optJSONObject("user")
        var currentBal = cachedBalances[cur] ?: 0.0
        if (user != null) {
            processCurrenciesData(user)
            currentBal = cachedBalances[cur] ?: (currentBal + profit)
        } else {
            currentBal += profit
            cachedBalances[cur] = currentBal
        }

        val nonce = nonceCounter.getAndIncrement()
        return Result.success(
            BetResponse(
                success = true,
                nonce = nonce,
                rollResult = rollResult,
                isWin = isWin,
                profit = profit,
                newBalance = currentBal,
                rawMessage = resp.toString()
            )
        )
    }

    override suspend fun resetSeed(): Result<String> = withContext(Dispatchers.IO) {
        try {
            ensureConnected()
            val newSeed = UUID.randomUUID().toString().replace("-", "")
            val payload = JSONObject().apply {
                put("client_seed", newSeed)
            }
            try {
                emitWithAck("games.dice.seed.change", payload, 4000L)
            } catch (_: Exception) { }
            Result.success(newSeed)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun disconnect() {
        try {
            webSocket?.close(1000, "disconnect")
        } catch (_: Exception) { }
        webSocket = null
        isConnected = false
        isAuthed = false
        joinedDiceRoom = false
        ackCallbacks.clear()
    }
}
