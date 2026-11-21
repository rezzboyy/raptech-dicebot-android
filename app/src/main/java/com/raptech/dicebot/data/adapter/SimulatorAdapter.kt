package com.raptech.dicebot.data.adapter

import com.raptech.dicebot.data.model.BetResponse
import com.raptech.dicebot.model.CasinoPlatform
import com.raptech.dicebot.model.CoinBalance
import kotlinx.coroutines.delay
import java.util.Locale
import kotlin.random.Random

class SimulatorAdapter(
    initialTrxBalance: Double = 5000.0
) : CasinoPlatformAdapter {

    private var currentNonce = 0L

    private val simulatedBalances = mutableMapOf(
        "TRX" to initialTrxBalance,
        "DOGE" to 10000.0,
        "LTC" to 10.0,
        "BNB" to 2.5,
        "SOL" to 25.0,
        "POL" to 500.0,
        "BTC" to 0.05,
        "ETH" to 0.5,
        "USDT" to 1000.0,
        "BCH" to 5.0,
        "TON" to 100.0
    )

    override fun getPlatformName(): String = "Simulation (Pick.io)"

    override suspend fun fetchBalance(currency: String): Result<Double> {
        delay(30)
        val curr = currency.uppercase(Locale.US)
        val bal = simulatedBalances[curr] ?: 1000.0
        return Result.success(bal)
    }

    override suspend fun fetchAvailableBalances(): Result<List<CoinBalance>> {
        delay(40)
        val coins = CasinoPlatform.SIMULATOR.supportedCoins.map { coin ->
            CoinBalance(
                currency = coin,
                balance = simulatedBalances[coin] ?: 1000.0
            )
        }
        return Result.success(coins)
    }

    override suspend fun placeDiceBet(
        amount: Double,
        target: Double,
        isHigh: Boolean,
        currency: String
    ): Result<BetResponse> {
        delay(35) // Simulate fast network latency

        currentNonce++
        val roll = Random.nextDouble(0.0, 100.0)
        val chance = target.coerceIn(0.01, 98.0)

        val isWin = if (isHigh) {
            roll > (100.0 - chance)
        } else {
            roll < chance
        }

        val multiplier = 99.0 / chance
        val profit = if (isWin) {
            (amount * multiplier) - amount
        } else {
            -amount
        }

        val curr = currency.uppercase(Locale.US)
        val prevBal = simulatedBalances[curr] ?: 1000.0
        val newBal = (prevBal + profit).coerceAtLeast(0.0)
        simulatedBalances[curr] = newBal

        val response = BetResponse(
            success = true,
            nonce = currentNonce,
            rollResult = String.format(Locale.US, "%.2f", roll).toDouble(),
            isWin = isWin,
            profit = profit,
            newBalance = newBal
        )

        return Result.success(response)
    }

    override suspend fun resetSeed(): Result<String> {
        delay(30)
        val newSeed = "pick_sim_${System.currentTimeMillis()}"
        return Result.success("Client seed reset: $newSeed")
    }

    fun setBalance(currency: String, newBalance: Double) {
        simulatedBalances[currency.uppercase(Locale.US)] = newBalance
    }
}
