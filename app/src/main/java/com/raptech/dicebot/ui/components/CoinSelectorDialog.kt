package com.raptech.dicebot.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.BasicAlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raptech.dicebot.R
import com.raptech.dicebot.model.CasinoPlatform
import com.raptech.dicebot.model.CoinBalance
import com.raptech.dicebot.ui.theme.RaptechColors

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CoinSelectorDialog(
    platform: CasinoPlatform,
    selectedCurrency: String,
    availableCoins: List<CoinBalance>,
    isDetecting: Boolean,
    onDismiss: () -> Unit,
    onCoinSelected: (String) -> Unit,
    onRefreshCoins: () -> Unit
) {
    var searchQuery by remember { mutableStateOf("") }
    var selectedFilterIndex by remember { mutableIntStateOf(0) } // 0: Semua, 1: Hanya Saldo > 0

    // Filter coins based on search and filter tab
    val filteredCoins = remember(availableCoins, searchQuery, selectedFilterIndex) {
        availableCoins.filter { coin ->
            val matchSearch = searchQuery.isBlank() || coin.currency.contains(searchQuery.trim(), ignoreCase = true)
            val matchFilter = when (selectedFilterIndex) {
                1 -> coin.balance > 0.0
                else -> true
            }
            matchSearch && matchFilter
        }
    }

    val positiveBalancesCount = remember(availableCoins) {
        availableCoins.count { it.balance > 0.0 }
    }

    BasicAlertDialog(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.85f)
                .clip(RoundedCornerShape(12.dp))
                .background(RaptechColors.SurfaceWhite)
                .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(12.dp))
                .padding(16.dp)
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(
                        painter = painterResource(id = R.drawable.ic_wallet_coin),
                        contentDescription = null,
                        tint = RaptechColors.OrangePrimary,
                        modifier = Modifier.size(24.dp)
                    )
                    Column {
                        Text(
                            text = "Pilih Koin & Dompet",
                            color = RaptechColors.TextPrimary,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "${platform.displayName} • ${availableCoins.size} Koin Terdata",
                            color = RaptechColors.TextSecondary,
                            fontSize = 10.sp
                        )
                    }
                }

                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    // Tombol Deteksi Otomatis
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(5.dp))
                            .background(RaptechColors.OrangeSoft)
                            .border(1.dp, RaptechColors.OrangeBorder, RoundedCornerShape(5.dp))
                            .clickable(enabled = !isDetecting) { onRefreshCoins() }
                            .padding(horizontal = 8.dp, vertical = 5.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            if (isDetecting) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(12.dp),
                                    color = RaptechColors.OrangePrimary,
                                    strokeWidth = 2.dp
                                )
                            } else {
                                Icon(
                                    imageVector = Icons.Default.Refresh,
                                    contentDescription = "Deteksi Ulang",
                                    tint = RaptechColors.OrangePrimary,
                                    modifier = Modifier.size(13.dp)
                                )
                            }
                            Text(
                                text = if (isDetecting) "Mendeteksi..." else "Deteksi Koin",
                                color = RaptechColors.OrangePrimary,
                                fontSize = 10.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }

                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.size(28.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Tutup",
                            tint = RaptechColors.TextMuted,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Search Bar
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(6.dp))
                    .background(RaptechColors.SurfaceLight)
                    .border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(6.dp))
                    .padding(horizontal = 8.dp, vertical = 7.dp)
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Search,
                        contentDescription = null,
                        tint = RaptechColors.TextMuted,
                        modifier = Modifier.size(16.dp)
                    )
                    Box(modifier = Modifier.weight(1f)) {
                        if (searchQuery.isEmpty()) {
                            Text(
                                text = "Cari simbol koin (misal: BFG, USDT, BTC)...",
                                color = RaptechColors.TextMuted,
                                fontSize = 11.sp
                            )
                        }
                        BasicTextField(
                            value = searchQuery,
                            onValueChange = { searchQuery = it },
                            modifier = Modifier.fillMaxWidth(),
                            textStyle = androidx.compose.ui.text.TextStyle(
                                color = RaptechColors.TextPrimary,
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace
                            ),
                            cursorBrush = SolidColor(RaptechColors.OrangePrimary),
                            singleLine = true
                        )
                    }
                    if (searchQuery.isNotEmpty()) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Clear",
                            tint = RaptechColors.TextMuted,
                            modifier = Modifier
                                .size(14.dp)
                                .clickable { searchQuery = "" }
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Filter Tabs: Semua vs Hanya Saldo > 0
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(5.dp))
                        .background(if (selectedFilterIndex == 0) RaptechColors.OrangePrimary else RaptechColors.SurfaceLight)
                        .then(
                            if (selectedFilterIndex != 0) Modifier.border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(5.dp))
                            else Modifier
                        )
                        .clickable { selectedFilterIndex = 0 }
                        .padding(vertical = 5.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Semua Koin (${availableCoins.size})",
                        fontSize = 10.sp,
                        fontWeight = if (selectedFilterIndex == 0) FontWeight.Bold else FontWeight.Medium,
                        color = if (selectedFilterIndex == 0) Color.White else RaptechColors.TextSecondary
                    )
                }

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(5.dp))
                        .background(if (selectedFilterIndex == 1) RaptechColors.OrangePrimary else RaptechColors.SurfaceLight)
                        .then(
                            if (selectedFilterIndex != 1) Modifier.border(1.dp, RaptechColors.BorderSubtle, RoundedCornerShape(5.dp))
                            else Modifier
                        )
                        .clickable { selectedFilterIndex = 1 }
                        .padding(vertical = 5.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Hanya Saldo Aktif ($positiveBalancesCount)",
                        fontSize = 10.sp,
                        fontWeight = if (selectedFilterIndex == 1) FontWeight.Bold else FontWeight.Medium,
                        color = if (selectedFilterIndex == 1) Color.White else RaptechColors.TextSecondary
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Coins List
            if (filteredCoins.isEmpty()) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = if (selectedFilterIndex == 1 && positiveBalancesCount == 0)
                                "Tidak ada koin dengan saldo > 0.\nTekan tab 'Semua Koin' atau Deteksi Koin."
                            else
                                "Koin '${searchQuery}' tidak ditemukan.",
                            color = RaptechColors.TextMuted,
                            fontSize = 11.sp,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                            lineHeight = 16.sp
                        )
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    items(filteredCoins, key = { it.currency }) { coin ->
                        val isSelected = coin.currency.equals(selectedCurrency, ignoreCase = true)
                        val hasBalance = coin.balance > 0.0

                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(6.dp))
                                .background(
                                    if (isSelected) RaptechColors.OrangeSoft
                                    else RaptechColors.SurfaceLight
                                )
                                .border(
                                    1.dp,
                                    if (isSelected) RaptechColors.OrangeBorder
                                    else RaptechColors.BorderSubtle,
                                    RoundedCornerShape(6.dp)
                                )
                                .clickable {
                                    onCoinSelected(coin.currency)
                                    onDismiss()
                                }
                                .padding(horizontal = 10.dp, vertical = 8.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            // Left: Coin Symbol & Default Badge
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Box(
                                    modifier = Modifier
                                        .size(32.dp)
                                        .clip(CircleShape)
                                        .background(
                                            if (isSelected) RaptechColors.OrangePrimary
                                             else if (hasBalance) RaptechColors.WinBackground
                                            else RaptechColors.SurfaceHover
                                        ),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = coin.currency.take(3),
                                        fontSize = 9.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = if (isSelected) Color.White
                                        else if (hasBalance) RaptechColors.WinSuccess
                                        else RaptechColors.TextSecondary,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }

                                Column {
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                                    ) {
                                        Text(
                                            text = coin.currency,
                                            fontSize = 13.sp,
                                            fontWeight = FontWeight.Bold,
                                            fontFamily = FontFamily.Monospace,
                                            color = if (isSelected) RaptechColors.OrangePrimary else RaptechColors.TextPrimary
                                        )

                                        if (coin.currency.equals(platform.defaultCurrency, true)) {
                                            Box(
                                                modifier = Modifier
                                                    .clip(RoundedCornerShape(3.dp))
                                                    .background(RaptechColors.SurfaceHover)
                                                    .border(0.5.dp, RaptechColors.BorderSubtle, RoundedCornerShape(3.dp))
                                                    .padding(horizontal = 4.dp, vertical = 1.dp)
                                            ) {
                                                Text(
                                                    text = "Default",
                                                    fontSize = 8.sp,
                                                    color = RaptechColors.InfoBlue,
                                                    fontFamily = FontFamily.Monospace
                                                )
                                            }
                                        }
                                    }

                                    Text(
                                        text = if (hasBalance) "Saldo Aktif" else "Saldo Kosong",
                                        fontSize = 9.sp,
                                        color = if (hasBalance) RaptechColors.WinSuccess else RaptechColors.TextMuted
                                    )
                                }
                            }

                            // Right: Balance & Selected Indicator
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Column(horizontalAlignment = Alignment.End) {
                                    Text(
                                        text = coin.formattedBalance,
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.Bold,
                                        fontFamily = FontFamily.Monospace,
                                        color = if (hasBalance) RaptechColors.WinSuccess else RaptechColors.TextMuted
                                    )
                                    Text(
                                        text = coin.currency,
                                        fontSize = 9.sp,
                                        color = RaptechColors.TextMuted,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }

                                if (isSelected) {
                                    Icon(
                                        imageVector = Icons.Default.CheckCircle,
                                        contentDescription = "Aktif",
                                        tint = RaptechColors.OrangePrimary,
                                        modifier = Modifier.size(16.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
