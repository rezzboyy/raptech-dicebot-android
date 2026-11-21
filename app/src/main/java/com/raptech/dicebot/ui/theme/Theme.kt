package com.raptech.dicebot.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val RaptechLightColorScheme = lightColorScheme(
    primary = RaptechColors.OrangePrimary,
    onPrimary = Color.White,
    primaryContainer = RaptechColors.OrangeSoft,
    onPrimaryContainer = RaptechColors.OrangePrimary,
    secondary = RaptechColors.InfoBlue,
    onSecondary = Color.White,
    background = RaptechColors.Background,
    onBackground = RaptechColors.TextPrimary,
    surface = RaptechColors.SurfaceWhite,
    onSurface = RaptechColors.TextPrimary,
    surfaceVariant = RaptechColors.SurfaceLight,
    onSurfaceVariant = RaptechColors.TextSecondary,
    outline = RaptechColors.BorderSubtle,
    error = RaptechColors.LossDanger,
    onError = Color.White
)

@Composable
fun RaptechDicebotTheme(
    content: @Composable () -> Unit
) {
    val colorScheme = RaptechLightColorScheme
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as? Activity)?.window
            if (window != null) {
                window.statusBarColor = RaptechColors.Background.toArgb()
                window.navigationBarColor = RaptechColors.Background.toArgb()
                WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = true
                WindowCompat.getInsetsController(window, view).isAppearanceLightNavigationBars = true
            }
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = RaptechTypography,
        content = content
    )
}
