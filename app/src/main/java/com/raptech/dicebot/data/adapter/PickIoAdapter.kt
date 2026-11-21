package com.raptech.dicebot.data.adapter

import com.raptech.dicebot.data.model.BetResponse
import com.raptech.dicebot.data.network.CasinoHttpClient
import com.raptech.dicebot.model.CasinoPlatform
import com.raptech.dicebot.model.CoinBalance
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.FormBody
import okhttp3.Request
import org.json.JSONObject
import java.math.BigDecimal
import java.math.RoundingMode
import java.util.Locale
import java.util.UUID
import java.util.regex.Pattern

class PickIoAdapter(
    val platform: CasinoPlatform,
    private var sessionCookie: String = ""
) : CasinoPlatformAdapter {

    private val client = CasinoHttpClient.client
    private var lastKnownBalance: Double = 0.0
    private var csrfToken: String = ""
    private var currentClientSeed: String = generateRandomSeed()

    init {
        extractCsrfFromCookie(sessionCookie)
    }

    override fun getPlatformName(): String = platform.displayName

    fun setCookie(cookie: String) {
        sessionCookie = cookie.trim()
        extractCsrfFromCookie(sessionCookie)
    }

    fun getCookie(): String = sessionCookie

    private fun extractCsrfFromCookie(rawCookie: String) {
        if (rawCookie.isBlank()) return
        val match = Pattern.compile("""(?:csrf_cookie_name|csrf_test_name)=([^;]+)""", Pattern.CASE_INSENSITIVE).matcher(rawCookie)
        if (match.find()) {
            csrfToken = match.group(1)?.trim() ?: csrfToken
        }
    }

    private fun updateCsrfFromHeaders(setCookieHeaders: List<String>) {
        for (header in setCookieHeaders) {
            if (header.contains("csrf_cookie_name=")) {
                val match = Pattern.compile("csrf_cookie_name=([^;]+)").matcher(header)
                if (match.find()) {
                    val newCsrf = match.group(1)?.trim() ?: ""
                    if (newCsrf.isNotBlank()) {
                        csrfToken = newCsrf
                        sessionCookie = if (sessionCookie.contains("csrf_cookie_name=")) {
                            sessionCookie.replace(
                                Regex("csrf_cookie_name=[^;]+"),
                                "csrf_cookie_name=$newCsrf"
                            )
                        } else {
                            "$sessionCookie; csrf_cookie_name=$newCsrf"
                        }
                    }
                }
            }
        }
    }

    override suspend fun fetchBalance(currency: String): Result<Double> = withContext(Dispatchers.IO) {
        runCatching {
            if (sessionCookie.isBlank()) {
                throw IllegalStateException("Kredensial belum diatur. Silakan login ke ${platform.displayName} terlebih dahulu.")
            }

            extractCsrfFromCookie(sessionCookie)

            val request = Request.Builder()
                .url("${platform.defaultLoginUrl}/dice.php")
                .header("User-Agent", CasinoHttpClient.currentUserAgent)
                .header("Cookie", sessionCookie)
                .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8")
                .header("Referer", "${platform.defaultLoginUrl}/dice.php")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                updateCsrfFromHeaders(response.headers("Set-Cookie"))
                val bodyStr = response.body?.string() ?: ""

                val finalPath = response.request.url.encodedPath
                val priorRedirectedToLogin = response.priorResponse?.isRedirect == true && finalPath.contains("login")
                if (finalPath.contains("login.php") || priorRedirectedToLogin) {
                    throw IllegalStateException("Sesi kasino belum login atau telah berakhir (Halaman dialihkan ke login.php)")
                }

                if (bodyStr.contains("id=\"user_email\"") || bodyStr.contains("name=\"user_email\"")) {
                    throw IllegalStateException("Sesi kasino belum login (Formulir login terdeteksi pada ${platform.displayName})")
                }

                // Balance extraction patterns (aligned with Pick.io claim parser)
                val balancePatterns = listOf(
                    Pattern.compile("""class=["']?[^"']*user_balance[^"']*["']?[^>]*>([^<\s][^<]*)<""", Pattern.CASE_INSENSITIVE),
                    Pattern.compile("""id=["']dd_main_balance["']?[^>]*>([^<\s][^<]*)<""", Pattern.CASE_INSENSITIVE),
                    Pattern.compile("""id=["']available_balance["']?[^>]*>([^<\s][^<]*)<""", Pattern.CASE_INSENSITIVE),
                    Pattern.compile("""data-user-balance=["']([0-9][0-9.,]*)["']""", Pattern.CASE_INSENSITIVE),
                    Pattern.compile("""id=["'](?:user_balance|balance)["'][^>]*>\s*([0-9][0-9.,]*)""", Pattern.CASE_INSENSITIVE),
                    Pattern.compile("""class=["'][^"']*(?:user_balance|top_balance)[^"']*["'][^>]*>\s*([0-9][0-9.,]*)""", Pattern.CASE_INSENSITIVE),
                    Pattern.compile(""""balance"\s*:\s*"?(?:\+|-)?([0-9][0-9.,]*)"?""", Pattern.CASE_INSENSITIVE)
                )

                for (pattern in balancePatterns) {
                    val matcher = pattern.matcher(bodyStr)
                    if (matcher.find()) {
                        val numStr = matcher.group(1)?.replace(",", "")?.trim() ?: ""
                        val parsed = numStr.toDoubleOrNull()
                        if (parsed != null) {
                            lastKnownBalance = parsed
                            return@runCatching parsed
                        }
                    }
                }

                // Extract CSRF token from HTML inputs
                val csrfInputPatterns = listOf(
                    Pattern.compile("""name=["']csrf_test_name["'][^>]*value=["']([^"']+)["']""", Pattern.CASE_INSENSITIVE),
                    Pattern.compile("""value=["']([^"']+)["'][^>]*name=["']csrf_test_name["']""", Pattern.CASE_INSENSITIVE)
                )
                for (p in csrfInputPatterns) {
                    val m = p.matcher(bodyStr)
                    if (m.find()) {
                        csrfToken = m.group(1)?.trim() ?: csrfToken
                        break
                    }
                }

                // If user is clearly logged in (e.g. contains logout or profile element)
                val isExplicitlyLoggedIn = bodyStr.contains("action=logout", ignoreCase = true) ||
                        bodyStr.contains("profile-name", ignoreCase = true) ||
                        bodyStr.contains("user_level", ignoreCase = true)

                if (isExplicitlyLoggedIn) {
                    return@runCatching lastKnownBalance
                }

                throw IllegalStateException("Respons dari ${platform.displayName} tidak memuat saldo akun yang valid")
            }
        }
    }

    override suspend fun fetchAvailableBalances(): Result<List<CoinBalance>> = withContext(Dispatchers.IO) {
        runCatching {
            val primaryBalance = fetchBalance(platform.defaultCurrency).getOrDefault(lastKnownBalance)
            platform.supportedCoins.map { coin ->
                CoinBalance(
                    currency = coin,
                    balance = if (coin.equals(platform.defaultCurrency, ignoreCase = true)) primaryBalance else 0.0
                )
            }
        }
    }

    override suspend fun placeDiceBet(
        amount: Double,
        target: Double,
        isHigh: Boolean,
        currency: String
    ): Result<BetResponse> = withContext(Dispatchers.IO) {
        runCatching {
            require(amount > 0) { "Bet amount harus lebih besar dari 0" }

            // Coerce amount to platform minBet
            val finalAmount = amount.coerceAtLeast(platform.minBet)

            // Ensure CSRF token is available
            if (csrfToken.isBlank()) {
                extractCsrfFromCookie(sessionCookie)
                if (csrfToken.isBlank()) {
                    fetchBalance(currency)
                }
            }

            fun executePost(token: String): BetResponse {
                val chanceCoerced = target.coerceIn(0.01, 98.0)
                val payout = (99.0 / chanceCoerced).coerceAtLeast(1.01)
                val formattedPayout = if (payout == Math.round(payout).toDouble()) {
                    String.format(Locale.US, "%.0f", payout)
                } else {
                    String.format(Locale.US, "%.2f", payout)
                }

                val formattedAmount = BigDecimal.valueOf(finalAmount)
                    .setScale(platform.decimalPrecision, RoundingMode.DOWN)
                    .toPlainString()

                val formBuilder = FormBody.Builder()
                    .add("action", "bet_game_dice")
                    .add("bet_amount", formattedAmount)
                    .add("payout", formattedPayout)
                    .add("bet_on", if (isHigh) "higher" else "lower")

                if (token.isNotBlank()) {
                    formBuilder.add("csrf_test_name", token)
                }

                val formBody = formBuilder.build()

                val request = Request.Builder()
                    .url("${platform.defaultLoginUrl}/process.php")
                    .header("User-Agent", CasinoHttpClient.currentUserAgent)
                    .header("Cookie", sessionCookie)
                    .header("Origin", platform.defaultLoginUrl)
                    .header("Referer", "${platform.defaultLoginUrl}/dice.php")
                    .header("X-Requested-With", "XMLHttpRequest")
                    .header("Accept", "application/json, text/javascript, */*; q=0.01")
                    .header("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
                    .post(formBody)
                    .build()

                client.newCall(request).execute().use { response ->
                    updateCsrfFromHeaders(response.headers("Set-Cookie"))
                    val bodyStr = response.body?.string() ?: ""

                    if (response.code == 403) {
                        throw SecurityException("CSRF_403")
                    }

                    if (!response.isSuccessful) {
                        throw IllegalStateException("HTTP ${response.code}: ${bodyStr.take(150)}")
                    }

                    val json = JSONObject(bodyStr)
                    val ret = json.opt("ret")
                    val isSuccess = ret == 1 || ret == "1" || ret == true

                    if (!isSuccess) {
                        val msg = json.optString("mes", json.optString("message", json.optString("error", "Bet ditolak oleh server")))
                        throw IllegalStateException(msg)
                    }

                    val betData = json.optJSONObject("bet_data") ?: json.optJSONObject("data")

                    val roll = betData?.optDouble("number", betData.optDouble("result", json.optDouble("num", json.optDouble("number", 0.0)))) ?: json.optDouble("num", 0.0)
                    val profitRaw = betData?.optDouble("profit", json.optDouble("amount", 0.0)) ?: json.optDouble("amount", 0.0)
                    val profit = profitRaw / platform.unitDivisor

                    val balanceRaw = betData?.optDouble("balance", json.optDouble("balance", 0.0)) ?: json.optDouble("balance", 0.0)
                    val newBalance = if (balanceRaw > 0) balanceRaw / platform.unitDivisor else (lastKnownBalance + profit)
                    lastKnownBalance = newBalance

                    val isWin = if (profit != 0.0) profit > 0 else (betData?.optBoolean("win", false) ?: false)
                    val nonce = betData?.optLong("nonce", System.currentTimeMillis()) ?: System.currentTimeMillis()

                    return BetResponse(
                        success = true,
                        nonce = nonce,
                        rollResult = roll,
                        isWin = isWin,
                        profit = profit,
                        newBalance = newBalance,
                        rawMessage = null
                    )
                }
            }

            try {
                executePost(csrfToken)
            } catch (e: SecurityException) {
                // CSRF token refreshed via fetchBalance and retry once
                fetchBalance(currency)
                executePost(csrfToken)
            }
        }
    }

    override suspend fun resetSeed(): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val newSeed = generateRandomSeed()
            currentClientSeed = newSeed

            // Attempt to notify server of seed rotation
            if (sessionCookie.isNotBlank()) {
                try {
                    if (csrfToken.isBlank()) extractCsrfFromCookie(sessionCookie)
                    val formBody = FormBody.Builder()
                        .add("action", "change_client_seed")
                        .add("client_seed", newSeed)
                        .apply {
                            if (csrfToken.isNotBlank()) add("csrf_test_name", csrfToken)
                        }
                        .build()

                    val request = Request.Builder()
                        .url("${platform.defaultLoginUrl}/process.php")
                        .header("User-Agent", CasinoHttpClient.currentUserAgent)
                        .header("Cookie", sessionCookie)
                        .header("Origin", platform.defaultLoginUrl)
                        .header("Referer", "${platform.defaultLoginUrl}/dice.php")
                        .header("X-Requested-With", "XMLHttpRequest")
                        .post(formBody)
                        .build()

                    client.newCall(request).execute().use { response ->
                        updateCsrfFromHeaders(response.headers("Set-Cookie"))
                    }
                } catch (_: Exception) {
                    // Ignored - seed rotated locally
                }
            }

            "Seed ${platform.displayName} di-rotate: ${newSeed.take(12)}..."
        }
    }

    companion object {
        fun generateRandomSeed(): String {
            return (UUID.randomUUID().toString() + UUID.randomUUID().toString())
                .replace("-", "")
                .take(32)
        }
    }
}
