package com.raptech.dicebot.model

import kotlinx.serialization.Serializable

@Serializable
data class BetRecord(
    val executionNumber: Long,
    val amount: Double,
    val targetChance: Double,
    val isHigh: Boolean,
    val rollResult: Double,
    val isWin: Boolean,
    val netResult: Double,
    val nonce: Long = 0L,
    val timestamp: Long = System.currentTimeMillis()
)

data class ChartPoint(
    val executionIndex: Long,
    val netResult: Double,
    val balance: Double,
    val isWin: Boolean = true
)
