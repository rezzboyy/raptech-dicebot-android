package com.raptech.dicebot.engine

import com.raptech.dicebot.model.SyntaxValidationResult

/**
 * Result of the AutoFix operation on a LUA script.
 */
data class AutoFixResult(
    val isModified: Boolean,
    val fixedScript: String,
    val changes: List<String>,
    val isValid: Boolean,
    val errorMessage: String? = null,
    val errorLine: Int? = null
) {
    val summaryMessage: String
        get() {
            if (!isModified && isValid) return "Skrip sudah valid & optimal ✓"
            if (!isModified && !isValid) return "Tidak ada pola error otomatis yang cocok (Error baris ${errorLine ?: "?"})"
            val count = changes.size
            return if (isValid) {
                "AutoFix ($count perbaikan): Sintaks 100% Valid ✓"
            } else {
                "AutoFix ($count perbaikan), cek baris ${errorLine ?: "?"}: ${errorMessage ?: "error"}"
            }
        }
}

/**
 * Intelligent AutoFix Engine for Raptech Dicebot LUA scripts.
 * Automatically analyzes and fixes syntax mistakes (JS/C typos, missing then/do,
 * unbalanced ends, missing dobet(), missing standard variables).
 */
object LuaScriptAutoFixer {

    private const val DEFAULT_WORKING_SCRIPT = """-- Raptech Dicebot Standard Martingale LUA Script
basebet = 0.0001
nextbet = basebet
chance = 49.5
bethigh = true

function dobet()
    if win then
        print("WIN! Reset bet ke basebet.")
        nextbet = basebet
    else
        print("LOSE! Gandakan bet (Martingale).")
        nextbet = previousbet * 2
    end
end
"""

    fun fix(rawScript: String): AutoFixResult {
        val changes = mutableListOf<String>()

        // 1. Handle Empty or Blank Script
        if (rawScript.isBlank()) {
            val valid = LuaEngine.validateSyntax(DEFAULT_WORKING_SCRIPT)
            return AutoFixResult(
                isModified = true,
                fixedScript = DEFAULT_WORKING_SCRIPT,
                changes = listOf("Memuat template skrip standar dicebot"),
                isValid = valid.isValid,
                errorMessage = valid.errorMessage,
                errorLine = valid.errorLine
            )
        }

        var code = rawScript

        // 2. Normalize line endings (CRLF -> LF)
        code = code.replace("\r\n", "\n").replace("\r", "\n")

        // 3. Convert C-style comments before masking literals
        // Multiline comment /* ... */ -> --[[ ... ]]
        val cMultiComment = Regex("/\\*([\\s\\S]*?)\\*/")
        if (cMultiComment.containsMatchIn(code)) {
            code = cMultiComment.replace(code) { "--[[${it.groupValues[1]}]]" }
            changes.add("Konversi komentar multiline '/* */' ke '--[[ ]]'")
        }

        // Single-line comment // ... (not preceded by :) -> -- ...
        val cSingleComment = Regex("(?<!:)//([^\n]*)")
        if (cSingleComment.containsMatchIn(code)) {
            code = cSingleComment.replace(code) { "--${it.groupValues[1]}" }
            changes.add("Konversi komentar '//' ke '--'")
        }

        // 4. Tokenize & Mask String Literals and Existing Lua Comments to prevent corruption
        val literalPlaceholders = mutableListOf<String>()
        val literalPattern = Regex("(--\\[\\[[\\s\\S]*?\\]\\]|--[^\n]*|\"(?:[^\"\\\\]|\\\\.)*\"|'(?:[^'\\\\]|\\\\.)*'|\\[\\[[\\s\\S]*?\\]\\])")

        var maskedCode = literalPattern.replace(code) { match ->
            val placeholder = "___RAPTECH_LITERAL_${literalPlaceholders.size}___"
            literalPlaceholders.add(match.value)
            placeholder
        }

        // 5. Replace C/JS Logical & Comparison Operators
        // !== or != -> ~=
        if (maskedCode.contains("!==") || maskedCode.contains("!=")) {
            maskedCode = maskedCode.replace("!==", "~=").replace("!=", "~=")
            changes.add("Ganti operator '!=' ke '~='")
        }

        // === -> ==
        if (maskedCode.contains("===")) {
            maskedCode = maskedCode.replace("===", "==")
            changes.add("Ganti operator '===' ke '=='")
        }

        // && -> and
        if (maskedCode.contains("&&")) {
            maskedCode = maskedCode.replace("&&", " and ")
            changes.add("Ganti operator '&&' ke 'and'")
        }

        // || -> or
        if (maskedCode.contains("||")) {
            maskedCode = maskedCode.replace("||", " or ")
            changes.add("Ganti operator '||' ke 'or'")
        }

        // ! followed by identifier or parenthesis -> not
        val notPattern = Regex("!(?!=)\\s*([a-zA-Z0-9_(])")
        if (notPattern.containsMatchIn(maskedCode)) {
            maskedCode = notPattern.replace(maskedCode) { "not ${it.groupValues[1]}" }
            changes.add("Ganti operator '!' ke 'not '")
        }

        // 6. Replace C/JS Literals & Keywords
        val boolTruePattern = Regex("\\bTrue\\b")
        if (boolTruePattern.containsMatchIn(maskedCode)) {
            maskedCode = boolTruePattern.replace(maskedCode, "true")
            changes.add("Ganti 'True' ke 'true'")
        }
        val boolFalsePattern = Regex("\\bFalse\\b")
        if (boolFalsePattern.containsMatchIn(maskedCode)) {
            maskedCode = boolFalsePattern.replace(maskedCode, "false")
            changes.add("Ganti 'False' ke 'false'")
        }
        val nullPattern = Regex("\\b(null|NULL|None)\\b")
        if (nullPattern.containsMatchIn(maskedCode)) {
            maskedCode = nullPattern.replace(maskedCode, "nil")
            changes.add("Ganti 'null/None' ke 'nil'")
        }
        val elseIfPattern = Regex("\\belse\\s+if\\b")
        if (elseIfPattern.containsMatchIn(maskedCode)) {
            maskedCode = elseIfPattern.replace(maskedCode, "elseif")
            changes.add("Ganti 'else if' ke 'elseif'")
        }

        // 7. Compound Assignments & Increment/Decrement (x++, x--, x += y, etc.)
        val incPattern = Regex("([a-zA-Z0-9_.]+)\\s*\\+\\+")
        if (incPattern.containsMatchIn(maskedCode)) {
            maskedCode = incPattern.replace(maskedCode) { "${it.groupValues[1]} = ${it.groupValues[1]} + 1" }
            changes.add("Konversi 'x++' ke 'x = x + 1'")
        }
        val plusEqPattern = Regex("([a-zA-Z0-9_.]+)\\s*\\+=\\s*([^;\n]+)")
        if (plusEqPattern.containsMatchIn(maskedCode)) {
            maskedCode = plusEqPattern.replace(maskedCode) { "${it.groupValues[1]} = ${it.groupValues[1]} + (${it.groupValues[2].trim()})" }
            changes.add("Konversi '+=' ke 'x = x + y'")
        }
        val minusEqPattern = Regex("([a-zA-Z0-9_.]+)\\s*-=\\s*([^;\n]+)")
        if (minusEqPattern.containsMatchIn(maskedCode)) {
            maskedCode = minusEqPattern.replace(maskedCode) { "${it.groupValues[1]} = ${it.groupValues[1]} - (${it.groupValues[2].trim()})" }
            changes.add("Konversi '-=' ke 'x = x - y'")
        }
        val mulEqPattern = Regex("([a-zA-Z0-9_.]+)\\s*\\*=\\s*([^;\n]+)")
        if (mulEqPattern.containsMatchIn(maskedCode)) {
            maskedCode = mulEqPattern.replace(maskedCode) { "${it.groupValues[1]} = ${it.groupValues[1]} * (${it.groupValues[2].trim()})" }
            changes.add("Konversi '*=' ke 'x = x * y'")
        }
        val divEqPattern = Regex("([a-zA-Z0-9_.]+)\\s*/=\\s*([^;\n]+)")
        if (divEqPattern.containsMatchIn(maskedCode)) {
            maskedCode = divEqPattern.replace(maskedCode) { "${it.groupValues[1]} = ${it.groupValues[1]} / (${it.groupValues[2].trim()})" }
            changes.add("Konversi '/=' ke 'x = x / y'")
        }

        // 8. C-style Braces for Control Blocks ({ ... })
        // First convert "} else if" and "} else {" so that '}' is not mistakenly turned into 'end else'
        val closeElseIfBracePattern = Regex("\\}\\s*else\\s*if\\s*\\((.*?)\\)\\s*\\{")
        if (closeElseIfBracePattern.containsMatchIn(maskedCode)) {
            maskedCode = closeElseIfBracePattern.replace(maskedCode) { "elseif ${it.groupValues[1]} then" }
            changes.add("Konversi '} else if' ke 'elseif ... then'")
        }
        val closeElseIfNoParenPattern = Regex("\\}\\s*else\\s*if\\s+([^{]+?)\\s*\\{")
        if (closeElseIfNoParenPattern.containsMatchIn(maskedCode)) {
            maskedCode = closeElseIfNoParenPattern.replace(maskedCode) { "elseif ${it.groupValues[1].trim()} then" }
            changes.add("Konversi '} else if' ke 'elseif ... then'")
        }
        val closeElseBracePattern = Regex("\\}\\s*else\\s*\\{")
        if (closeElseBracePattern.containsMatchIn(maskedCode)) {
            maskedCode = closeElseBracePattern.replace(maskedCode) { "else" }
            changes.add("Konversi '} else {' ke 'else'")
        }
        val closeElsePattern = Regex("\\}\\s*else\\b")
        if (closeElsePattern.containsMatchIn(maskedCode)) {
            maskedCode = closeElsePattern.replace(maskedCode) { "else" }
            changes.add("Konversi '} else' ke 'else'")
        }

        val ifBracePattern = Regex("\\bif\\s*\\((.*?)\\)\\s*\\{")
        if (ifBracePattern.containsMatchIn(maskedCode)) {
            maskedCode = ifBracePattern.replace(maskedCode) { "if ${it.groupValues[1]} then" }
            changes.add("Konversi 'if (...) {' ke 'if ... then'")
        }
        val ifBraceNoParen = Regex("\\bif\\s+([^{]+?)\\s*\\{")
        if (ifBraceNoParen.containsMatchIn(maskedCode)) {
            maskedCode = ifBraceNoParen.replace(maskedCode) { "if ${it.groupValues[1].trim()} then" }
            changes.add("Konversi 'if ... {' ke 'if ... then'")
        }
        val elseifBracePattern = Regex("\\belseif\\s*\\((.*?)\\)\\s*\\{")
        if (elseifBracePattern.containsMatchIn(maskedCode)) {
            maskedCode = elseifBracePattern.replace(maskedCode) { "elseif ${it.groupValues[1]} then" }
            changes.add("Konversi 'elseif (...) {' ke 'elseif ... then'")
        }
        val whileBracePattern = Regex("\\bwhile\\s*\\((.*?)\\)\\s*\\{")
        if (whileBracePattern.containsMatchIn(maskedCode)) {
            maskedCode = whileBracePattern.replace(maskedCode) { "while ${it.groupValues[1]} do" }
            changes.add("Konversi 'while (...) {' ke 'while ... do'")
        }
        val forBracePattern = Regex("\\bfor\\s*\\((.*?)\\)\\s*\\{")
        if (forBracePattern.containsMatchIn(maskedCode)) {
            maskedCode = forBracePattern.replace(maskedCode) { "for ${it.groupValues[1]} do" }
            changes.add("Konversi 'for (...) {' ke 'for ... do'")
        }
        val elseBracePattern = Regex("\\belse\\s*\\{")
        if (elseBracePattern.containsMatchIn(maskedCode)) {
            maskedCode = elseBracePattern.replace(maskedCode) { "else" }
            changes.add("Konversi 'else {' ke 'else'")
        }
        val funcBracePattern = Regex("\\bfunction\\s*([a-zA-Z0-9_.]+)\\s*\\((.*?)\\)\\s*\\{")
        if (funcBracePattern.containsMatchIn(maskedCode)) {
            maskedCode = funcBracePattern.replace(maskedCode) { "function ${it.groupValues[1]}(${it.groupValues[2]})" }
            changes.add("Konversi kurung kurawal fungsi ke LUA")
        }
        // Replace remaining closing curly brace '}' with 'end'
        if (maskedCode.contains("}")) {
            maskedCode = maskedCode.replace("}", "end")
            changes.add("Ganti '}' ke 'end'")
        }

        // 9. Unmask Literals & Comments
        literalPlaceholders.forEachIndexed { index, literal ->
            maskedCode = maskedCode.replace("___RAPTECH_LITERAL_${index}___", literal)
        }

        code = maskedCode

        // 10. Line-by-Line missing 'then' and 'do' check
        val lines = code.lines().toMutableList()
        var lineModified = false
        for (i in lines.indices) {
            val rawLine = lines[i]
            val trimmed = rawLine.trim()

            // Skip comments and empty lines
            if (trimmed.startsWith("--") || trimmed.isEmpty()) continue

            // If line starts with "if" or "elseif" and does not contain "then"
            if (Regex("^(if|elseif)\\b").containsMatchIn(trimmed) && !trimmed.contains(Regex("\\bthen\\b"))) {
                lines[i] = "$rawLine then"
                lineModified = true
                changes.add("Menambahkan 'then' pada baris ${i + 1}")
            }
            // If line starts with "while" or "for" and does not contain "do"
            else if (Regex("^(while|for)\\b").containsMatchIn(trimmed) && !trimmed.contains(Regex("\\bdo\\b"))) {
                lines[i] = "$rawLine do"
                lineModified = true
                changes.add("Menambahkan 'do' pada baris ${i + 1}")
            }
        }
        if (lineModified) {
            code = lines.joinToString("\n")
        }

        // 11. Balance Blocks & Fix Missing / Excess 'end'
        val stripped = stripCommentsAndStrings(code)
        val openTokens = Regex("\\b(function|if|while|for)\\b").findAll(stripped).count()
        val totalClosers = Regex("\\bend\\b").findAll(stripped).count()

        if (openTokens > totalClosers) {
            val missing = openTokens - totalClosers
            val endsToAppend = "\n" + (1..missing).joinToString("\n") { "end" }
            code = code.trimEnd() + endsToAppend + "\n"
            changes.add("Melengkapi $missing 'end' penutup yang hilang")
        } else if (totalClosers > openTokens) {
            val excess = totalClosers - openTokens
            var trimmedCode = code.trimEnd()
            var removed = 0
            while (removed < excess && trimmedCode.endsWith("end")) {
                trimmedCode = trimmedCode.substring(0, trimmedCode.length - 3).trimEnd()
                removed++
            }
            if (removed > 0) {
                code = trimmedCode + "\n"
                changes.add("Menghapus $removed kelebihan 'end'")
            }
        }

        // 12. Check if 'function dobet()' exists
        val hasDobet = Regex("\\b(function\\s+dobet\\s*\\(|dobet\\s*=\\s*function)").containsMatchIn(code)
        if (!hasDobet) {
            val hasBettingLogic = Regex("\\b(win|nextbet|basebet|previousbet|chance|bethigh|balance|currentstreak)\\b").containsMatchIn(code)
            if (hasBettingLogic) {
                val codeLines = code.lines()
                val configLines = mutableListOf<String>()
                val logicLines = mutableListOf<String>()

                for (l in codeLines) {
                    val t = l.trim()
                    if (t.matches(Regex("^(basebet|base|chance|bethigh|nextbet|local\\s+[a-zA-Z0-9_]+)\\s*=.*")) && !t.contains("function")) {
                        configLines.add(l)
                    } else if (t.isNotEmpty() && !t.startsWith("--")) {
                        logicLines.add(l)
                    } else if (logicLines.isEmpty()) {
                        configLines.add(l)
                    } else {
                        logicLines.add(l)
                    }
                }

                val sb = java.lang.StringBuilder()
                if (configLines.isNotEmpty()) {
                    sb.append(configLines.joinToString("\n")).append("\n\n")
                }
                sb.append("function dobet()\n")
                for (l in logicLines) {
                    sb.append("    ").append(l).append("\n")
                }
                sb.append("end\n")
                code = sb.toString()
                changes.add("Membungkus logika taruhan ke dalam 'function dobet() ... end'")
            }
        }

        // 13. Ensure Essential Variables Are Declared
        val strippedAfter = stripCommentsAndStrings(code)
        val hasBasebet = Regex("\\b(basebet|base)\\s*=").containsMatchIn(strippedAfter)
        val hasNextbet = Regex("\\bnextbet\\s*=").containsMatchIn(strippedAfter)
        val hasChance = Regex("\\bchance\\s*=").containsMatchIn(strippedAfter)
        val hasBethigh = Regex("\\bbethigh\\s*=").containsMatchIn(strippedAfter)

        val prependLines = mutableListOf<String>()
        if (!hasBasebet) {
            prependLines.add("basebet = 0.0001")
            changes.add("Mendeklarasikan 'basebet = 0.0001'")
        }
        if (!hasNextbet) {
            prependLines.add("nextbet = basebet")
            changes.add("Mendeklarasikan 'nextbet = basebet'")
        }
        if (!hasChance) {
            prependLines.add("chance = 49.5")
            changes.add("Mendeklarasikan 'chance = 49.5'")
        }
        if (!hasBethigh) {
            prependLines.add("bethigh = true")
            changes.add("Mendeklarasikan 'bethigh = true'")
        }

        if (prependLines.isNotEmpty()) {
            code = prependLines.joinToString("\n") + "\n\n" + code
        }

        // 14. Validate Syntax with LuaEngine
        var validation = LuaEngine.validateSyntax(code)

        // 15. If validation still failed with 'end' expected, try adding one more 'end'
        if (!validation.isValid && validation.errorMessage?.contains("'end' expected") == true) {
            val retryCode = code.trimEnd() + "\nend\n"
            val retryValidation = LuaEngine.validateSyntax(retryCode)
            if (retryValidation.isValid) {
                code = retryCode
                validation = retryValidation
                changes.add("Melengkapi 'end' penutup pada akhir file")
            }
        }

        val isModified = code != rawScript

        return AutoFixResult(
            isModified = isModified,
            fixedScript = code,
            changes = changes,
            isValid = validation.isValid,
            errorMessage = validation.errorMessage,
            errorLine = validation.errorLine
        )
    }

    private fun stripCommentsAndStrings(source: String): String {
        val pattern = Regex("(--\\[\\[[\\s\\S]*?\\]\\]|--[^\n]*|\"(?:[^\"\\\\]|\\\\.)*\"|'(?:[^'\\\\]|\\\\.)*'|\\[\\[[\\s\\S]*?\\]\\])")
        return pattern.replace(source, " ")
    }
}
