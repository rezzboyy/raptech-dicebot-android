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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.BasicAlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raptech.dicebot.R
import com.raptech.dicebot.ui.theme.RaptechColors
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RiskConfigDialog(
    currentStopLoss: Double?,
    currentTakeProfit: Double?,
    currentMaxBet: Double?,
    currency: String,
    onDismiss: () -> Unit,
    onSaveLimits: (stopLoss: Double?, takeProfit: Double?, maxBet: Double?) -> Unit
) {
    var stopLossText by remember { mutableStateOf(currentStopLoss?.let { String.format(Locale.US, "%.6f", it) } ?: "") }
    var takeProfitText by remember { mutableStateOf(currentTakeProfit?.let { String.format(Locale.US, "%.6f", it) } ?: "") }
    var maxBetText by remember { mutableStateOf(currentMaxBet?.let { String.format(Locale.US, "%.8f", it) } ?: "") }

    BasicAlertDialog(
        onDismissRequest = onDismiss
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(RaptechColors.SurfaceWhite)
                .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(12.dp))
                .padding(18.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Icon(
                    painter = painterResource(id = R.drawable.ic_shield_risk),
                    contentDescription = null,
                    tint = RaptechColors.OrangePrimary,
                    modifier = Modifier.size(24.dp)
                )
                Text(
                    text = "Risk Management Circuit Breakers",
                    color = RaptechColors.TextPrimary,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = "Proteksi modal otomatis. Bot akan berhenti otomatis seketika jika batas risiko tercapai.",
                color = RaptechColors.TextSecondary,
                fontSize = 11.sp
            )

            Spacer(modifier = Modifier.height(14.dp))

            // Stop Loss Input
            RiskInputField(
                label = "Stop-Loss Limit ($currency)",
                description = "Bot langsung berhenti jika rugi melebihi nilai ini (misal: 10.0)",
                value = stopLossText,
                onValueChange = { stopLossText = it },
                accentColor = RaptechColors.LossDanger
            )

            Spacer(modifier = Modifier.height(10.dp))

            // Take Profit Input
            RiskInputField(
                label = "Take-Profit Target ($currency)",
                description = "Bot langsung berhenti saat profit mencapai nilai ini (misal: 5.0)",
                value = takeProfitText,
                onValueChange = { takeProfitText = it },
                accentColor = RaptechColors.WinSuccess
            )

            Spacer(modifier = Modifier.height(10.dp))

            // Max Bet Cap Input
            RiskInputField(
                label = "Max Bet Limit ($currency)",
                description = "Batas maksimum taruhan per roll agar martingal tidak liar",
                value = maxBetText,
                onValueChange = { maxBetText = it },
                accentColor = RaptechColors.OrangePrimary
            )

            Spacer(modifier = Modifier.height(18.dp))

            // Action Buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(RaptechColors.SurfaceLight)
                        .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                        .clickable {
                            // Reset/disable all
                            onSaveLimits(null, null, null)
                            onDismiss()
                        }
                        .padding(horizontal = 12.dp, vertical = 7.dp)
                ) {
                    Text(
                        text = "Reset / Off",
                        color = RaptechColors.LossDanger,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium
                    )
                }

                Spacer(modifier = Modifier.width(8.dp))

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(RaptechColors.OrangePrimary)
                        .clickable {
                            val sl = stopLossText.toDoubleOrNull()?.takeIf { it > 0 }
                            val tp = takeProfitText.toDoubleOrNull()?.takeIf { it > 0 }
                            val mb = maxBetText.toDoubleOrNull()?.takeIf { it > 0 }
                            onSaveLimits(sl, tp, mb)
                            onDismiss()
                        }
                        .padding(horizontal = 16.dp, vertical = 7.dp)
                ) {
                    Text(
                        text = "Simpan Proteksi",
                        color = Color.White,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

@Composable
private fun RiskInputField(
    label: String,
    description: String,
    value: String,
    onValueChange: (String) -> Unit,
    accentColor: Color
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(text = label, color = accentColor, fontSize = 11.sp, fontWeight = FontWeight.Bold)
        }
        Text(text = description, color = RaptechColors.TextMuted, fontSize = 9.sp)
        Spacer(modifier = Modifier.height(3.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(6.dp))
                .background(RaptechColors.SurfaceLight)
                .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                .padding(horizontal = 10.dp, vertical = 7.dp)
        ) {
            if (value.isEmpty()) {
                Text(text = "Nonaktif (Kosong)", color = RaptechColors.TextMuted, fontSize = 12.sp)
            }
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                textStyle = androidx.compose.ui.text.TextStyle(
                    color = RaptechColors.TextPrimary,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.SemiBold
                ),
                cursorBrush = SolidColor(RaptechColors.OrangePrimary)
            )
        }
    }
}
