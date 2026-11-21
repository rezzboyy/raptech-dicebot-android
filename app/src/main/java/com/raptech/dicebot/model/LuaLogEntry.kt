package com.raptech.dicebot.model

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class LuaLogEntry(
    val timestamp: Long = System.currentTimeMillis(),
    val message: String,
    val isError: Boolean = false
) {
    val formattedTime: String
        get() = SimpleDateFormat("HH:mm:ss.SSS", Locale.US).format(Date(timestamp))
}

data class SyntaxValidationResult(
    val isValid: Boolean,
    val errorMessage: String? = null,
    val errorLine: Int? = null
)
