package com.raptech.dicebot.model

enum class CasinoPlatform(
    val displayName: String,
    val defaultCurrency: String,
    val isDirectApi: Boolean,
    val defaultLoginUrl: String,
    val supportedCoins: List<String>,
    val unitDivisor: Double = 100_000_000.0,
    val decimalPrecision: Int = 8,
    val minBet: Double = 0.0001
) {
    TRONPICK(
        displayName = "Tronpick.io",
        defaultCurrency = "TRX",
        isDirectApi = true,
        defaultLoginUrl = "https://tronpick.io",
        supportedCoins = listOf("TRX"),
        unitDivisor = 1_000_000.0,
        decimalPrecision = 6,
        minBet = 0.0001
    ),
    DOGEPICK(
        displayName = "Dogepick.io",
        defaultCurrency = "DOGE",
        isDirectApi = true,
        defaultLoginUrl = "https://dogepick.io",
        supportedCoins = listOf("DOGE"),
        unitDivisor = 100_000_000.0,
        decimalPrecision = 8,
        minBet = 0.000001
    ),
    LITEPICK(
        displayName = "Litepick.io",
        defaultCurrency = "LTC",
        isDirectApi = true,
        defaultLoginUrl = "https://litepick.io",
        supportedCoins = listOf("LTC"),
        unitDivisor = 100_000_000.0,
        decimalPrecision = 8,
        minBet = 0.0000005
    ),
    BNBPICK(
        displayName = "Bnbpick.io",
        defaultCurrency = "BNB",
        isDirectApi = true,
        defaultLoginUrl = "https://bnbpick.io",
        supportedCoins = listOf("BNB"),
        unitDivisor = 100_000_000.0,
        decimalPrecision = 8,
        minBet = 0.0000001
    ),
    SOLPICK(
        displayName = "Solpick.io",
        defaultCurrency = "SOL",
        isDirectApi = true,
        defaultLoginUrl = "https://solpick.io",
        supportedCoins = listOf("SOL"),
        unitDivisor = 100_000_000.0,
        decimalPrecision = 8,
        minBet = 0.0000005
    ),
    POLPICK(
        displayName = "Polpick.io",
        defaultCurrency = "POL",
        isDirectApi = true,
        defaultLoginUrl = "https://polpick.io",
        supportedCoins = listOf("POL"),
        unitDivisor = 100_000_000.0,
        decimalPrecision = 8,
        minBet = 0.0001
    ),
    BTCPICK(
        displayName = "Btcpick.io",
        defaultCurrency = "BTC",
        isDirectApi = true,
        defaultLoginUrl = "https://btcpick.io",
        supportedCoins = listOf("BTC"),
        unitDivisor = 100_000_000.0,
        decimalPrecision = 8,
        minBet = 0.00000001
    ),
    ETHPICK(
        displayName = "Ethpick.io",
        defaultCurrency = "ETH",
        isDirectApi = true,
        defaultLoginUrl = "https://ethpick.io",
        supportedCoins = listOf("ETH"),
        unitDivisor = 100_000_000.0,
        decimalPrecision = 8,
        minBet = 0.00000005
    ),
    USDTPICK(
        displayName = "Usdtpick.io",
        defaultCurrency = "USDT",
        isDirectApi = true,
        defaultLoginUrl = "https://usdtpick.io",
        supportedCoins = listOf("USDT"),
        unitDivisor = 1_000_000.0,
        decimalPrecision = 6,
        minBet = 0.0001
    ),
    BCHPICK(
        displayName = "Bchpick.io",
        defaultCurrency = "BCH",
        isDirectApi = true,
        defaultLoginUrl = "https://bchpick.io",
        supportedCoins = listOf("BCH"),
        unitDivisor = 100_000_000.0,
        decimalPrecision = 8,
        minBet = 0.0000005
    ),
    TONPICK(
        displayName = "Tonpick.io",
        defaultCurrency = "TON",
        isDirectApi = true,
        defaultLoginUrl = "https://tonpick.io",
        supportedCoins = listOf("TON"),
        unitDivisor = 100_000_000.0,
        decimalPrecision = 8,
        minBet = 0.0001
    ),
    BETFURY(
        displayName = "Betfury.com",
        defaultCurrency = "BFG",
        isDirectApi = true,
        defaultLoginUrl = "https://betfury.com",
        supportedCoins = listOf(
            "BFG", "USDT", "TRX", "BTC", "ETH", "BNB", "DOGE", "LTC", "SOL", "XRP", "MATIC", "BCH", "SHIB"
        ),
        unitDivisor = 100_000_000.0,
        decimalPrecision = 8,
        minBet = 0.00000001
    ),
    SIMULATOR(
        displayName = "Simulation (Pick.io)",
        defaultCurrency = "TRX",
        isDirectApi = false,
        defaultLoginUrl = "",
        supportedCoins = listOf("TRX", "DOGE", "LTC", "BNB", "SOL", "POL", "BTC", "ETH", "USDT", "BCH", "TON"),
        unitDivisor = 100_000_000.0,
        decimalPrecision = 8,
        minBet = 0.00000001
    )
}

enum class ScriptLanguage(val displayName: String) {
    LUA("LUA Script"),
    JS("JavaScript")
}
