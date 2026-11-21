package com.raptech.dicebot.model

import java.util.Locale

/**
 * Model data saldo koin/kripto untuk multi-currency kasino.
 */
data class CoinBalance(
    val currency: String,
    val balance: Double = 0.0,
    val isAvailable: Boolean = true
) {
    val formattedBalance: String
        get() = when {
            balance >= 1000.0 -> String.format(Locale.US, "%,.4f", balance)
            balance >= 1.0 -> String.format(Locale.US, "%.6f", balance)
            balance > 0.0 -> String.format(Locale.US, "%.8f", balance)
            else -> "0.0000"
        }
}
