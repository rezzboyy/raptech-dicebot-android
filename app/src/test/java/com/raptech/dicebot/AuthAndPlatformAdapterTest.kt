package com.raptech.dicebot

import com.raptech.dicebot.data.adapter.BetfuryAdapter
import com.raptech.dicebot.data.adapter.PickIoAdapter
import com.raptech.dicebot.data.adapter.SimulatorAdapter
import com.raptech.dicebot.engine.LuaEngine
import com.raptech.dicebot.model.BetRecord
import com.raptech.dicebot.model.CasinoPlatform
import com.raptech.dicebot.model.CoinBalance
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AuthAndPlatformAdapterTest {

    @Test
    fun testPickIoPlatformUrlsAndConfig() {
        assertEquals("https://tronpick.io", CasinoPlatform.TRONPICK.defaultLoginUrl)
        assertEquals("https://dogepick.io", CasinoPlatform.DOGEPICK.defaultLoginUrl)
        assertEquals("https://litepick.io", CasinoPlatform.LITEPICK.defaultLoginUrl)
        assertEquals("https://bnbpick.io", CasinoPlatform.BNBPICK.defaultLoginUrl)
        assertEquals("https://solpick.io", CasinoPlatform.SOLPICK.defaultLoginUrl)
        assertEquals("https://polpick.io", CasinoPlatform.POLPICK.defaultLoginUrl)
        assertEquals("https://btcpick.io", CasinoPlatform.BTCPICK.defaultLoginUrl)
        assertEquals("https://ethpick.io", CasinoPlatform.ETHPICK.defaultLoginUrl)
        assertEquals("https://usdtpick.io", CasinoPlatform.USDTPICK.defaultLoginUrl)
        assertEquals("https://bchpick.io", CasinoPlatform.BCHPICK.defaultLoginUrl)
        assertEquals("https://tonpick.io", CasinoPlatform.TONPICK.defaultLoginUrl)
        assertEquals("", CasinoPlatform.SIMULATOR.defaultLoginUrl)

        assertFalse(CasinoPlatform.SIMULATOR.isDirectApi)
        assertTrue(CasinoPlatform.TRONPICK.isDirectApi)
        assertTrue(CasinoPlatform.DOGEPICK.isDirectApi)
        assertTrue(CasinoPlatform.LITEPICK.isDirectApi)
    }

    @Test
    fun testPickIoDivisorsAndPrecision() {
        assertEquals(1_000_000.0, CasinoPlatform.TRONPICK.unitDivisor, 0.001)
        assertEquals(6, CasinoPlatform.TRONPICK.decimalPrecision)

        assertEquals(1_000_000.0, CasinoPlatform.USDTPICK.unitDivisor, 0.001)
        assertEquals(6, CasinoPlatform.USDTPICK.decimalPrecision)

        assertEquals(100_000_000.0, CasinoPlatform.DOGEPICK.unitDivisor, 0.001)
        assertEquals(8, CasinoPlatform.DOGEPICK.decimalPrecision)

        assertEquals(100_000_000.0, CasinoPlatform.LITEPICK.unitDivisor, 0.001)
        assertEquals(8, CasinoPlatform.LITEPICK.decimalPrecision)

        assertEquals(100_000_000.0, CasinoPlatform.BTCPICK.unitDivisor, 0.001)
        assertEquals(8, CasinoPlatform.BTCPICK.decimalPrecision)
    }

    @Test
    fun testSupportedCoinsList() {
        assertTrue(CasinoPlatform.TRONPICK.supportedCoins.contains("TRX"))
        assertTrue(CasinoPlatform.DOGEPICK.supportedCoins.contains("DOGE"))
        assertTrue(CasinoPlatform.LITEPICK.supportedCoins.contains("LTC"))
        assertTrue(CasinoPlatform.BNBPICK.supportedCoins.contains("BNB"))
        assertTrue(CasinoPlatform.SOLPICK.supportedCoins.contains("SOL"))
        assertTrue(CasinoPlatform.POLPICK.supportedCoins.contains("POL"))
        assertTrue(CasinoPlatform.BTCPICK.supportedCoins.contains("BTC"))
        assertTrue(CasinoPlatform.ETHPICK.supportedCoins.contains("ETH"))
        assertTrue(CasinoPlatform.USDTPICK.supportedCoins.contains("USDT"))
        assertTrue(CasinoPlatform.BCHPICK.supportedCoins.contains("BCH"))
        assertTrue(CasinoPlatform.TONPICK.supportedCoins.contains("TON"))

        assertTrue(CasinoPlatform.SIMULATOR.supportedCoins.contains("TRX"))
        assertTrue(CasinoPlatform.SIMULATOR.supportedCoins.contains("DOGE"))
    }

    @Test
    fun testCoinBalanceFormatting() {
        val coin1 = CoinBalance("TRX", 1730.1152)
        assertEquals("1,730.1152", coin1.formattedBalance)

        val coin2 = CoinBalance("USDT", 25.50)
        assertEquals("25.500000", coin2.formattedBalance)

        val coin3 = CoinBalance("BTC", 0.00012345)
        assertEquals("0.00012345", coin3.formattedBalance)

        val coin4 = CoinBalance("ETH", 0.0)
        assertEquals("0.0000", coin4.formattedBalance)
    }

    @Test
    fun testTokenSanitizationLogic() {
        // Test cookie extraction
        val rawCookiePaste = "user_session=abc12345; csrf_cookie_name=token999; remember_token=xyz"
        val clean1 = rawCookiePaste.removePrefix("Bearer ").removePrefix("\"").removeSuffix("\"").trim()
        assertTrue(clean1.contains("user_session=abc12345"))

        // PickIoAdapter cookie & CSRF extraction
        val adapter = PickIoAdapter(CasinoPlatform.TRONPICK, rawCookiePaste)
        assertEquals("Tronpick.io", adapter.getPlatformName())
        assertEquals(rawCookiePaste, adapter.getCookie())
    }

    @Test
    fun testSimulatorAdapterExecutionAndCoinBalances() = runBlocking {
        val simulator = SimulatorAdapter(initialTrxBalance = 5000.0)
        val balRes = simulator.fetchBalance("TRX")
        assertTrue(balRes.isSuccess)
        assertEquals(5000.0, balRes.getOrThrow(), 0.0001)

        val coinsRes = simulator.fetchAvailableBalances()
        assertTrue(coinsRes.isSuccess)
        val coins = coinsRes.getOrThrow()
        assertTrue(coins.isNotEmpty())
        assertTrue(coins.any { it.currency == "TRX" && it.balance > 0 })
        assertTrue(coins.any { it.currency == "DOGE" && it.balance > 0 })

        val betRes = simulator.placeDiceBet(
            amount = 1.0,
            target = 49.5,
            isHigh = false,
            currency = "TRX"
        )
        assertTrue(betRes.isSuccess)
        val betData = betRes.getOrThrow()
        assertTrue(betData.rollResult in 0.0..100.0)
        assertTrue(betData.nonce > 0)
        assertNotNull(betData.newBalance)

        val seedRes = simulator.resetSeed()
        assertTrue(seedRes.isSuccess)
        assertTrue(seedRes.getOrThrow().contains("Client seed reset"))
    }

    @Test
    fun testPickIoAdapterResetSeed() = runBlocking {
        val adapter = PickIoAdapter(CasinoPlatform.TRONPICK)
        val res = adapter.resetSeed()
        assertTrue(res.isSuccess)
        assertTrue(res.getOrThrow().contains("Tronpick.io"))
    }

    @Test
    fun testLuaEngineWorkflowWithResets() {
        val logs = mutableListOf<String>()
        var statsResetCount = 0
        var allResetCount = 0
        var seedResetCount = 0
        var stopCount = 0

        val engine = LuaEngine(
            onLog = { logs.add(it) },
            onStopRequested = { stopCount++ },
            onResetRequested = { statsResetCount++ },
            onResetStatsRequested = { statsResetCount++ },
            onResetAllRequested = { allResetCount++ },
            onResetSeedRequested = { seedResetCount++ }
        )

        val script = """
            chance = 49.5
            nextbet = 0.0001
            bethigh = true
            function dobet()
                if win then
                    nextbet = 0.0001
                else
                    nextbet = previousbet * 2
                    if math.abs(currentstreak) >= 2 then
                        resetseed()
                        resetstats()
                    end
                end
            end
        """.trimIndent()

        val initRes = engine.initScript(script, 100.0, "TRX")
        assertTrue(initRes.isSuccess)

        // Simulate 1st Loss
        val lossRecord1 = BetRecord(
            executionNumber = 1,
            amount = 0.0001,
            targetChance = 49.5,
            isHigh = true,
            rollResult = 30.0,
            isWin = false,
            netResult = -0.0001,
            nonce = 1
        )

        engine.onRollCompleted(
            lastRecord = lossRecord1,
            currentBalance = 99.9999,
            totalProfit = -0.0001,
            totalBets = 1,
            totalWins = 0,
            totalLosses = 1,
            totalVolume = 0.0001,
            currency = "TRX"
        )

        assertEquals(0, seedResetCount)
        assertEquals(0, statsResetCount)

        // Simulate 2nd Loss -> streak reaches 2 -> resetseed() & resetstats() called!
        val lossRecord2 = BetRecord(
            executionNumber = 2,
            amount = 0.0002,
            targetChance = 49.5,
            isHigh = true,
            rollResult = 25.0,
            isWin = false,
            netResult = -0.0002,
            nonce = 2
        )

        engine.onRollCompleted(
            lastRecord = lossRecord2,
            currentBalance = 99.9997,
            totalProfit = -0.0003,
            totalBets = 2,
            totalWins = 0,
            totalLosses = 2,
            totalVolume = 0.0003,
            currency = "TRX"
        )

        assertEquals(1, seedResetCount)
        assertEquals(1, statsResetCount)
    }

    @Test
    fun testBetfuryPlatformConfig() {
        assertEquals("https://betfury.com", CasinoPlatform.BETFURY.defaultLoginUrl)
        assertEquals("Betfury.com", CasinoPlatform.BETFURY.displayName)
        assertEquals("BFG", CasinoPlatform.BETFURY.defaultCurrency)
        assertTrue(CasinoPlatform.BETFURY.isDirectApi)
        assertTrue(CasinoPlatform.BETFURY.supportedCoins.contains("BFG"))
        assertTrue(CasinoPlatform.BETFURY.supportedCoins.contains("USDT"))
        assertTrue(CasinoPlatform.BETFURY.supportedCoins.contains("BTC"))
        assertTrue(CasinoPlatform.BETFURY.supportedCoins.contains("TRX"))
    }

    @Test
    fun testBetfuryCredentialsParsing() {
        val raw1 = "eyJhbGciOiJIUzI1NiJ9.test;uid=123456_abcdef"
        val (token1, uid1, fp1) = BetfuryAdapter.parseCredentials(raw1)
        assertEquals("eyJhbGciOiJIUzI1NiJ9.test", token1)
        assertEquals("123456_abcdef", uid1)
        assertEquals("123456", fp1)

        val rawJson = """{"token": "jwt_token_999", "uid": "user_777_xyz"}"""
        val (token2, uid2, fp2) = BetfuryAdapter.parseCredentials(rawJson)
        assertEquals("jwt_token_999", token2)
        assertEquals("user_777_xyz", uid2)
        assertEquals("user", fp2)

        val rawDirect = "my_custom_pure_token_xyz"
        val (token3, uid3, fp3) = BetfuryAdapter.parseCredentials(rawDirect)
        assertEquals("my_custom_pure_token_xyz", token3)
        assertEquals("", uid3)
        assertEquals("", fp3)

        // Test cookie string with multiple cookies where JWT is embedded
        val rawCookies = "_ga=GA1.1.123456789; cf_clearance=abcdef; token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJ1c2VyXzk5OV9iZXQifQ.sig123; uid=user_999_bet"
        val (token4, uid4, fp4) = BetfuryAdapter.parseCredentials(rawCookies)
        assertEquals("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJ1c2VyXzk5OV9iZXQifQ.sig123", token4)
        assertEquals("user_999_bet", uid4)
        assertEquals("user", fp4)

        // Test session token with cookies suffix and bal parameter
        val rawWithCookiesSuffix = "eyJhbGciOiJIUzI1NiJ9.payload.signature;uid=555_session;bal=24.5006732;cookies=_ga=123; session=abc"
        val (token5, uid5, fp5) = BetfuryAdapter.parseCredentials(rawWithCookiesSuffix)
        assertEquals("eyJhbGciOiJIUzI1NiJ9.payload.signature", token5)
        assertEquals("555_session", uid5)
        assertEquals("555", fp5)

        val adapter = BetfuryAdapter(rawWithCookiesSuffix)
        runBlocking {
            val balRes = adapter.fetchBalance("BFG")
            assertTrue(balRes.isSuccess)
            assertEquals(24.5006732, balRes.getOrNull() ?: 0.0, 0.0000001)
        }
    }
}
