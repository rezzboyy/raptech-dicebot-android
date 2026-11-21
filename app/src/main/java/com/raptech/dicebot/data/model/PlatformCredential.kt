package com.raptech.dicebot.data.model

import kotlinx.serialization.Serializable

@Serializable
data class BetResponse(
    val success: Boolean,
    val nonce: Long,
    val rollResult: Double,
    val isWin: Boolean,
    val profit: Double,
    val newBalance: Double,
    val rawMessage: String? = null
)

data class PlatformCredential(
    val platformName: String,
    val apiToken: String = "",
    val sessionCookie: String = "",
    val customEndpoint: String = "",
    val isSimulationMode: Boolean = false
)
