package com.raptech.dicebot.data.network

import android.content.Context
import android.webkit.WebSettings
import okhttp3.ConnectionPool
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import java.io.IOException
import java.util.concurrent.TimeUnit

object CasinoHttpClient {

    const val DEFAULT_USER_AGENT = "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"

    @Volatile
    var currentUserAgent: String = DEFAULT_USER_AGENT

    /**
     * Synchronize OkHttp User-Agent with the device's native Chromium WebView engine
     * to ensure 100% Cloudflare WAF and cf_clearance consistency.
     */
    fun syncUserAgent(context: Context) {
        try {
            val systemUa = WebSettings.getDefaultUserAgent(context.applicationContext)
            if (!systemUa.isNullOrBlank()) {
                currentUserAgent = systemUa
            }
        } catch (_: Exception) {
            // Keep default fallback if WebView package is unavailable
        }
    }

    private val rateLimitInterceptor = Interceptor { chain ->
        val original = chain.request()
        val requestBuilder = original.newBuilder()
        if (original.header("User-Agent") == null) {
            requestBuilder.header("User-Agent", currentUserAgent)
        }

        var response = chain.proceed(requestBuilder.build())
        var tryCount = 0

        // Handle HTTP 429 Rate Limit with exponential backoff
        while (response.code == 429 && tryCount < 3) {
            response.close()
            tryCount++
            try {
                Thread.sleep(1000L * tryCount)
            } catch (e: InterruptedException) {
                Thread.currentThread().interrupt()
                throw IOException("Rate limit sleep interrupted", e)
            }
            response = chain.proceed(requestBuilder.build())
        }

        response
    }

    val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectionPool(ConnectionPool(10, 5, TimeUnit.MINUTES))
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .addInterceptor(rateLimitInterceptor)
            .build()
    }
}
