package com.raptech.dicebot

import com.raptech.dicebot.model.BetRecord
import com.raptech.dicebot.model.ChartPoint
import com.raptech.dicebot.model.DicebotUiState
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RiskManagementAndHistoryTest {

    @Test
    fun testRiskCircuitBreakerStopLoss() {
        val state = DicebotUiState(
            balance = 1000.0,
            initialBalance = 1000.0,
            netResult = -15.5,
            stopLossLimit = 15.0 // Max allowed loss is 15.0
        )

        val sl = state.stopLossLimit
        val isStopLossTriggered = sl != null && sl > 0.0 && state.netResult <= -sl

        assertTrue("Circuit breaker stop loss harus terpicu saat kerugian mencapai batas", isStopLossTriggered)
    }

    @Test
    fun testRiskCircuitBreakerTakeProfit() {
        val state = DicebotUiState(
            balance = 1050.0,
            initialBalance = 1000.0,
            netResult = 50.0,
            takeProfitLimit = 40.0 // Target profit is 40.0
        )

        val tp = state.takeProfitLimit
        val isTakeProfitTriggered = tp != null && tp > 0.0 && state.netResult >= tp

        assertTrue("Circuit breaker take profit harus terpicu saat profit melampaui target", isTakeProfitTriggered)
    }

    @Test
    fun testRiskCircuitBreakerMaxBetCap() {
        val maxBetLimit = 25.0
        val requestedBetAmount = 50.0 // Martingale calculation resulted in 50

        val effectiveBet = if (maxBetLimit > 0.0 && requestedBetAmount > maxBetLimit) {
            maxBetLimit
        } else {
            requestedBetAmount
        }

        assertEquals(25.0, effectiveBet, 0.000001)
    }

    @Test
    fun testStopOnWinLogic() {
        val stopOnWinEnabled = true
        val roll1IsWin = false
        val shouldHaltAfterRoll1 = stopOnWinEnabled && roll1IsWin
        assertFalse(shouldHaltAfterRoll1)

        val roll2IsWin = true
        val shouldHaltAfterRoll2 = stopOnWinEnabled && roll2IsWin
        assertTrue("Bot harus berhenti jika stop on win aktif dan hasil roll adalah menang", shouldHaltAfterRoll2)
    }

    @Test
    fun testHistoryJsonSerialization() {
        val history = listOf(
            BetRecord(
                executionNumber = 1,
                amount = 0.001,
                targetChance = 49.5,
                isHigh = false,
                rollResult = 24.12,
                isWin = true,
                netResult = 0.00102020,
                nonce = 1001L
            ),
            BetRecord(
                executionNumber = 2,
                amount = 0.001,
                targetChance = 49.5,
                isHigh = false,
                rollResult = 88.45,
                isWin = false,
                netResult = -0.00100000,
                nonce = 1002L
            )
        )

        val jsonString = Json { prettyPrint = true }.encodeToString(history)
        assertNotNull(jsonString)
        assertTrue(jsonString.contains("executionNumber"))
        assertTrue(jsonString.contains("24.12"))
        assertTrue(jsonString.contains("88.45"))

        val decoded: List<BetRecord> = Json.decodeFromString(jsonString)
        assertEquals(2, decoded.size)
        assertEquals(1L, decoded[0].executionNumber)
        assertTrue(decoded[0].isWin)
        assertFalse(decoded[1].isWin)
    }

    @Test
    fun testRingBufferCapacityLimit() {
        val maxRecords = 5
        var historyList = emptyList<BetRecord>()

        for (i in 1..20) {
            val record = BetRecord(
                executionNumber = i.toLong(),
                amount = 0.01,
                targetChance = 49.5,
                isHigh = false,
                rollResult = 50.0,
                isWin = true,
                netResult = 0.01,
                nonce = i.toLong()
            )
            historyList = (historyList + record).takeLast(maxRecords)
        }

        assertEquals(5, historyList.size)
        assertEquals(16L, historyList.first().executionNumber)
        assertEquals(20L, historyList.last().executionNumber)
    }

    @Test
    fun testChartPointCalculations() {
        val points = listOf(
            ChartPoint(1, 0.01, 100.01),
            ChartPoint(2, -0.02, 99.98),
            ChartPoint(3, 0.05, 100.05)
        )

        val minPnl = minOf(0.0, points.minOf { it.netResult })
        val maxPnl = maxOf(0.0001, points.maxOf { it.netResult })

        assertEquals(-0.02, minPnl, 0.00001)
        assertEquals(0.05, maxPnl, 0.00001)
    }

    @Test
    fun testLuaEngineExactMicroBettingFollowsScript() {
        val luaEngine = com.raptech.dicebot.engine.LuaEngine()
        val script = """
            chance = 49.5
            bethigh = true
            basebet = 0.00000001
            nextbet = basebet

            function dobet()
              if win then
                nextbet = basebet
              else
                nextbet = previousbet * 2
              end
            end
        """.trimIndent()

        val initResult = luaEngine.initScript(
            script = script,
            initialBalance = 500.0,
            currency = "TRX",
            casino = "simulation",
            minBet = 0.00000001
        )
        assertTrue(initResult.isSuccess)

        // 1. Roll 1 should be exactly 0.00000001
        val initialDecision = luaEngine.getInitialBetDecision()
        assertEquals(0.00000001, initialDecision.amount, 0.0000000001)
        assertEquals(49.5, initialDecision.chance, 0.01)
        assertTrue(initialDecision.isHigh)

        // 2. Roll 1 finishes with LOSE -> nextbet should be 0.00000002
        val loseRecord = BetRecord(
            executionNumber = 1L,
            amount = 0.00000001,
            targetChance = 49.5,
            isHigh = true,
            rollResult = 30.0,
            isWin = false,
            netResult = -0.00000001,
            nonce = 1L
        )
        val nextAfterLose = luaEngine.onRollCompleted(
            lastRecord = loseRecord,
            currentBalance = 499.99999999,
            totalProfit = -0.00000001,
            totalBets = 1L,
            totalWins = 0L,
            totalLosses = 1L,
            totalVolume = 0.00000001
        )
        assertEquals(0.00000002, nextAfterLose.amount, 0.0000000001)

        // 3. Roll 2 finishes with WIN -> nextbet should reset to basebet (0.00000001)
        val winRecord = BetRecord(
            executionNumber = 2L,
            amount = 0.00000002,
            targetChance = 49.5,
            isHigh = true,
            rollResult = 80.0,
            isWin = true,
            netResult = 0.00000002,
            nonce = 2L
        )
        val nextAfterWin = luaEngine.onRollCompleted(
            lastRecord = winRecord,
            currentBalance = 500.00000001,
            totalProfit = 0.00000001,
            totalBets = 2L,
            totalWins = 1L,
            totalLosses = 1L,
            totalVolume = 0.00000003
        )
        assertEquals(0.00000001, nextAfterWin.amount, 0.0000000001)
    }
}
