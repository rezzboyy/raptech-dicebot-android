package com.raptech.dicebot.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Raptech Design System Tokens: Solid White & Comfort Warm Orange.
 * Crafted for maximum clarity, eye comfort during extended sessions,
 * and ultra-lightweight GPU rendering.
 */
object RaptechColors {
    // ==========================================
    // 1. SOLID WHITE & CLEAN SURFACES
    // ==========================================
    val Background = Color(0xFFFFFFFF)          // Pure Solid White
    val SurfaceWhite = Color(0xFFFFFFFF)        // Main card container
    val SurfaceDark = Color(0xFFFFFFFF)         // Clean white card surface
    val SurfaceLight = Color(0xFFF8FAFC)        // Elevated tab & panel (Slate 50)
    val SurfaceBorder = Color(0xFFE2E8F0)       // Thin divider & border (Slate 200)
    val SurfaceSelected = Color(0xFFFFF7ED)     // Active item background (Warm Cream / Orange 50)
    val SurfaceHover = Color(0xFFF1F5F9)        // Slate 100 for subtle hover/pressed
    val BorderSubtle = Color(0xFFE2E8F0)        // Slate 200 hairline border
    val BorderStrong = Color(0xFFCBD5E1)        // Slate 300 active input border
    val Divider = Color(0xFFF1F5F9)             // Slate 100 row divider

    // ==========================================
    // 2. COMFORT WARM ORANGE PALETTE (SIGNATURE)
    // ==========================================
    val OrangePrimary = Color(0xFFEA580C)       // Warm Tangerine: Main brand & primary CTA
    val OrangeDark = Color(0xFFC2410C)          // Deep Terracotta: Button pressed state
    val OrangeVibrant = Color(0xFFF97316)       // Vibrant Apricot: Interactive highlights & chips
    val OrangeSoft = Color(0xFFFFF7ED)          // Soft Warm Tint: Pill & badge backgrounds
    val OrangeBorder = Color(0xFFFED7AA)        // Soft Peach: Warm accent border
    val OrangeGlow = Color(0x1AEA580C)          // 10% Opacity subtle elevation glow

    // Compatibility aliases
    val AmberPrimary = OrangePrimary
    val AmberDark = OrangeDark
    val AmberLight = OrangeVibrant
    val AmberGlow = OrangeGlow
    val WarningOrange = OrangePrimary

    // ==========================================
    // 3. STATUS & FINANCIAL INDICATORS (HARMONIZED)
    // ==========================================
    val WinSuccess = Color(0xFF059669)          // Emerald 600: Win profit & positive streak
    val WinBackground = Color(0xFFECFDF5)       // Emerald 50: Soft green badge
    val WinBorder = Color(0xFFA7F3D0)           // Emerald 200: Soft green border

    val LossDanger = Color(0xFFDC2626)          // Red 600: Loss, drawdown & emergency stop
    val LossBackground = Color(0xFFFEF2F2)      // Red 50: Soft red badge
    val LossBorder = Color(0xFFFECACA)          // Red 200: Soft red border

    val InfoBlue = Color(0xFF0284C7)            // Sky 600: Connection status, sniffer & mirrors
    val InfoBackground = Color(0xFFF0F9FF)      // Sky 50: Soft blue badge
    val NeutralCyan = InfoBlue                  // Compatibility alias

    // ==========================================
    // 4. TYPOGRAPHY & READABILITY (SLATE HIGH CONTRAST)
    // ==========================================
    val TextPrimary = Color(0xFF0F172A)         // Slate 900: High-contrast crisp black
    val TextSecondary = Color(0xFF475569)       // Slate 600: Secondary labels & sub-metrics
    val TextMuted = Color(0xFF94A3B8)           // Slate 400: Placeholders & currency units
    val TextCode = Color(0xFF1E293B)            // Slate 800: LUA code editor syntax base
}
