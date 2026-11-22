package com.raptech.dicebot.data.repository

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.raptech.dicebot.data.adapter.BetfuryAdapter
import com.raptech.dicebot.data.adapter.CasinoPlatformAdapter
import com.raptech.dicebot.data.adapter.PickIoAdapter
import com.raptech.dicebot.data.adapter.SimulatorAdapter
import com.raptech.dicebot.data.model.BetResponse
import com.raptech.dicebot.model.CasinoPlatform
import com.raptech.dicebot.model.CoinBalance
import java.util.concurrent.ConcurrentHashMap

class CasinoRepository(context: Context) {

    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val securePrefs: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        "raptech_secure_credentials",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    val simulatorAdapter = SimulatorAdapter()
    private val pickAdapters = ConcurrentHashMap<CasinoPlatform, PickIoAdapter>()
    val betfuryAdapter = BetfuryAdapter()

    init {
        // Initialize Pick.io and Betfury adapters with saved credentials
        CasinoPlatform.values().forEach { platform ->
            if (platform == CasinoPlatform.BETFURY) {
                val token = securePrefs.getString("token_BETFURY", "") ?: ""
                val uid = securePrefs.getString("uid_BETFURY", "") ?: ""
                val cred = if (uid.isNotBlank()) "$token;uid=$uid" else token
                betfuryAdapter.setCredentials(cred)
            } else if (platform != CasinoPlatform.SIMULATOR) {
                val savedCookie = securePrefs.getString("token_${platform.name}", "") ?: ""
                pickAdapters[platform] = PickIoAdapter(platform, savedCookie)
            }
        }
    }

    fun getAdapter(platform: CasinoPlatform): CasinoPlatformAdapter {
        return when (platform) {
            CasinoPlatform.SIMULATOR -> simulatorAdapter
            CasinoPlatform.BETFURY -> betfuryAdapter
            else -> pickAdapters.computeIfAbsent(platform) {
                val savedCookie = securePrefs.getString("token_${it.name}", "") ?: ""
                PickIoAdapter(it, savedCookie)
            }
        }
    }

    fun saveToken(platform: CasinoPlatform, token: String, uid: String = "") {
        securePrefs.edit()
            .putString("token_${platform.name}", token.trim())
            .putString("uid_${platform.name}", uid.trim())
            .apply()

        if (platform == CasinoPlatform.BETFURY) {
            val cred = if (uid.isNotBlank()) "${token.trim()};uid=${uid.trim()}" else token.trim()
            betfuryAdapter.setCredentials(cred)
        } else if (platform != CasinoPlatform.SIMULATOR) {
            pickAdapters[platform]?.setCookie(token)
        }
    }

    fun getToken(platform: CasinoPlatform): String {
        return securePrefs.getString("token_${platform.name}", "") ?: ""
    }

    fun getUid(platform: CasinoPlatform): String {
        return securePrefs.getString("uid_${platform.name}", "") ?: ""
    }

    fun hasCredentials(platform: CasinoPlatform): Boolean {
        if (!platform.isDirectApi) return true
        return getToken(platform).isNotBlank()
    }

    fun clearToken(platform: CasinoPlatform) {
        securePrefs.edit()
            .remove("token_${platform.name}")
            .remove("uid_${platform.name}")
            .apply()

        if (platform == CasinoPlatform.BETFURY) {
            betfuryAdapter.setCredentials("")
        } else if (platform != CasinoPlatform.SIMULATOR) {
            pickAdapters[platform]?.setCookie("")
        }
    }

    suspend fun fetchBalance(platform: CasinoPlatform, currency: String): Result<Double> {
        return getAdapter(platform).fetchBalance(currency)
    }

    suspend fun fetchAvailableBalances(platform: CasinoPlatform): Result<List<CoinBalance>> {
        return getAdapter(platform).fetchAvailableBalances()
    }

    suspend fun placeDiceBet(
        platform: CasinoPlatform,
        amount: Double,
        target: Double,
        isHigh: Boolean,
        currency: String
    ): Result<BetResponse> {
        return getAdapter(platform).placeDiceBet(amount, target, isHigh, currency)
    }

    suspend fun resetSeed(platform: CasinoPlatform): Result<String> {
        return getAdapter(platform).resetSeed()
    }
}
