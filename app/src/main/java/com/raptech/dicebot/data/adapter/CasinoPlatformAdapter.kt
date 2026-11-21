package com.raptech.dicebot.data.adapter

import com.raptech.dicebot.data.model.BetResponse
import com.raptech.dicebot.model.CoinBalance

interface CasinoPlatformAdapter {
    fun getPlatformName(): String
    suspend fun fetchBalance(currency: String): Result<Double>
    suspend fun fetchAvailableBalances(): Result<List<CoinBalance>>
    suspend fun placeDiceBet(
        amount: Double,
        target: Double,
        isHigh: Boolean,
        currency: String
    ): Result<BetResponse>
    suspend fun resetSeed(): Result<String>
}
