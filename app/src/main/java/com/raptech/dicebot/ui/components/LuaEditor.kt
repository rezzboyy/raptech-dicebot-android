package com.raptech.dicebot.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Error
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raptech.dicebot.engine.LuaEngine
import com.raptech.dicebot.model.StrategyPreset
import com.raptech.dicebot.model.StrategyPresets
import com.raptech.dicebot.model.SyntaxValidationResult
import com.raptech.dicebot.ui.theme.RaptechColors

@Composable
fun LuaEditor(
    script: String,
    onScriptChange: (String) -> Unit,
    onPresetSelected: (StrategyPreset) -> Unit,
    syntaxResult: SyntaxValidationResult?,
    modifier: Modifier = Modifier
) {
    var draftStatus by remember { mutableStateOf("Draft autosaved") }
    var presetMenuExpanded by remember { mutableStateOf(false) }
    var showVariablesDialog by remember { mutableStateOf(false) }
    val lineCount = script.lines().size
    val charCount = script.length

    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(RaptechColors.SurfaceWhite)
            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(8.dp))
            .padding(8.dp)
    ) {
        // Row 1: Presets Dropdown, Dedicated Variables Menu Button & Action Buttons
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                // Presets Dropdown
                Box {
                    Row(
                        modifier = Modifier
                            .clip(RoundedCornerShape(5.dp))
                            .background(RaptechColors.OrangePrimary)
                            .clickable { presetMenuExpanded = true }
                            .padding(horizontal = 9.dp, vertical = 5.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(3.dp)
                    ) {
                        Text(
                            text = "Presets",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        Icon(
                            imageVector = Icons.Default.ArrowDropDown,
                            contentDescription = null,
                            tint = Color.White,
                            modifier = Modifier.size(16.dp)
                        )
                    }

                    DropdownMenu(
                        expanded = presetMenuExpanded,
                        onDismissRequest = { presetMenuExpanded = false },
                        modifier = Modifier
                            .background(RaptechColors.SurfaceWhite)
                            .border(1.dp, RaptechColors.BorderSubtle)
                    ) {
                        StrategyPresets.ALL_PRESETS.forEach { preset ->
                            DropdownMenuItem(
                                text = {
                                    Column {
                                        Text(
                                            text = preset.name,
                                            color = RaptechColors.OrangePrimary,
                                            fontSize = 13.sp,
                                            fontWeight = FontWeight.Bold
                                        )
                                        Text(
                                            text = "${preset.category} • ${preset.description}",
                                            color = RaptechColors.TextSecondary,
                                            fontSize = 10.sp
                                        )
                                    }
                                },
                                onClick = {
                                    onPresetSelected(preset)
                                    presetMenuExpanded = false
                                    draftStatus = "Preset '${preset.name}' dimuat"
                                }
                            )
                        }
                    }
                }

                // Dedicated Function & Variable Reference Menu Button
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(5.dp))
                        .background(RaptechColors.OrangeSoft)
                        .border(1.dp, RaptechColors.OrangeBorder, RoundedCornerShape(5.dp))
                        .clickable { showVariablesDialog = true }
                        .padding(horizontal = 8.dp, vertical = 5.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "FX / Variabel",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = RaptechColors.OrangePrimary
                    )
                }
            }

            // Quick Actions: Check, Clear
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                EditorActionButton("Cek Sintaks", RaptechColors.SurfaceLight, RaptechColors.TextPrimary) {
                    val res = LuaEngine.validateSyntax(script)
                    draftStatus = if (res.isValid) "Sintaks LUA Valid ✓" else "Error baris ${res.errorLine ?: "?"}"
                }
                EditorActionButton("Clear", RaptechColors.LossBackground, RaptechColors.LossDanger) {
                    onScriptChange("")
                    draftStatus = "Editor dikosongkan"
                }
            }
        }

        Spacer(modifier = Modifier.height(6.dp))

        // Syntax Validation Banner (if error or checked)
        if (syntaxResult != null && !syntaxResult.isValid) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(5.dp))
                    .background(RaptechColors.LossBackground)
                    .border(1.dp, RaptechColors.LossBorder, RoundedCornerShape(5.dp))
                    .padding(horizontal = 8.dp, vertical = 5.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Error,
                    contentDescription = null,
                    tint = RaptechColors.LossDanger,
                    modifier = Modifier.size(14.dp)
                )
                Text(
                    text = "Sintaks Error${syntaxResult.errorLine?.let { " [Baris $it]" } ?: ""}: ${syntaxResult.errorMessage}",
                    fontSize = 10.sp,
                    color = RaptechColors.LossDanger,
                    fontFamily = FontFamily.Monospace,
                    maxLines = 2
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
        }

        // Code Editor Box with Line Numbers
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(290.dp)
                .clip(RoundedCornerShape(6.dp))
                .background(RaptechColors.SurfaceLight)
                .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                .padding(6.dp)
        ) {
            // Line Numbers Column
            val lineNumbersText = (1..lineCount).joinToString("\n")
            Text(
                text = lineNumbersText,
                color = RaptechColors.TextMuted,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                lineHeight = 16.sp,
                modifier = Modifier
                    .width(32.dp)
                    .padding(end = 4.dp)
            )

            // Text Area
            BasicTextField(
                value = script,
                onValueChange = {
                    onScriptChange(it)
                    draftStatus = "Draft autosaved"
                },
                modifier = Modifier.fillMaxWidth(),
                visualTransformation = remember { LuaSyntaxTransformation() },
                textStyle = androidx.compose.ui.text.TextStyle(
                    color = RaptechColors.TextCode,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    lineHeight = 16.sp
                ),
                cursorBrush = SolidColor(RaptechColors.OrangePrimary)
            )
        }

        Spacer(modifier = Modifier.height(4.dp))

        // Footer Status Bar
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = draftStatus,
                color = RaptechColors.OrangePrimary,
                fontSize = 10.sp,
                fontWeight = FontWeight.Medium
            )
            Text(
                text = "$lineCount lines | $charCount chars",
                color = RaptechColors.TextMuted,
                fontSize = 10.sp
            )
        }

        // Dedicated Modal Kamus Variabel & Fungsi LUA
        if (showVariablesDialog) {
            LuaVariablesDialog(
                onDismiss = { showVariablesDialog = false },
                onInsert = { snippet ->
                    onScriptChange(script + snippet)
                    draftStatus = "Snippet '${snippet.trim()}' disisipkan"
                }
            )
        }
    }
}

@Composable
private fun EditorActionButton(
    text: String,
    bgColor: Color,
    textColor: Color,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(4.dp))
            .background(bgColor)
            .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(4.dp))
            .clickable { onClick() }
            .padding(horizontal = 8.dp, vertical = 4.dp)
    ) {
        Text(text = text, fontSize = 10.sp, color = textColor, fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Medium)
    }
}

/**
 * High-performance regex-based syntax highlighter for LUA in Jetpack Compose.
 * Tailored for high-contrast, comfortable viewing on solid white / light surfaces.
 */
private class LuaSyntaxTransformation : VisualTransformation {
    override fun filter(text: AnnotatedString): TransformedText {
        val raw = text.text
        val builder = AnnotatedString.Builder(raw)

        // 1. Strings: "..." or '...' -> Emerald 600
        val stringRegex = Regex("(\"[^\"]*\"|'[^']*')")
        for (match in stringRegex.findAll(raw)) {
            builder.addStyle(
                SpanStyle(color = Color(0xFF059669)),
                match.range.first, match.range.last + 1
            )
        }

        // 2. Comments: --.*$ -> Slate 500
        val commentRegex = Regex("--.*$", RegexOption.MULTILINE)
        for (match in commentRegex.findAll(raw)) {
            builder.addStyle(
                SpanStyle(color = Color(0xFF64748B)),
                match.range.first, match.range.last + 1
            )
        }

        // 3. Numbers: \b\d+(\.\d+)?\b -> Amber / Terracotta
        val numberRegex = Regex("\\b\\d+(\\.\\d+)?\\b")
        for (match in numberRegex.findAll(raw)) {
            builder.addStyle(
                SpanStyle(color = Color(0xFFD97706)),
                match.range.first, match.range.last + 1
            )
        }

        // 4. Lua Keywords -> Blue 700
        val keywords = listOf(
            "and", "break", "do", "else", "elseif", "end", "false", "for",
            "function", "if", "in", "local", "nil", "not", "or", "repeat",
            "return", "then", "true", "until", "while"
        )
        val keywordRegex = Regex("\\b(${keywords.joinToString("|")})\\b")
        for (match in keywordRegex.findAll(raw)) {
            builder.addStyle(
                SpanStyle(color = Color(0xFF1D4ED8), fontWeight = FontWeight.Bold),
                match.range.first, match.range.last + 1
            )
        }

        // 5. Bot Variables & Functions -> Warm Comfort Orange
        val botVars = listOf(
            "balance", "profit", "nextbet", "chance", "bethigh", "win",
            "currentstreak", "previousbet", "bets", "wins", "losses",
            "invested", "currency", "lastBet", "dobet", "stop", "reset", "print"
        )
        val botVarRegex = Regex("\\b(${botVars.joinToString("|")})\\b")
        for (match in botVarRegex.findAll(raw)) {
            builder.addStyle(
                SpanStyle(color = RaptechColors.OrangePrimary, fontWeight = FontWeight.Bold),
                match.range.first, match.range.last + 1
            )
        }

        return TransformedText(builder.toAnnotatedString(), OffsetMapping.Identity)
    }
}
