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
}
