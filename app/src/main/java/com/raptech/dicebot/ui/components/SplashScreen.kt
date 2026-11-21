package com.raptech.dicebot.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raptech.dicebot.R
import com.raptech.dicebot.ui.theme.RaptechColors
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Unique, memorable, and lightweight 2-second opening splash animation.
 * Features rotating and pulsing amber 3D dice, concentric cyber pulse rings,
 * and bold typography that transitions smoothly into the main application.
 */
@Composable
fun SplashScreen(
    onAnimationFinished: () -> Unit
) {
    val scaleAnim = remember { Animatable(0.4f) }
    val rotateAnim = remember { Animatable(0f) }
    val alphaAnim = remember { Animatable(0f) }
    val progressAnim = remember { Animatable(0f) }

    val infiniteTransition = rememberInfiniteTransition(label = "PulseTransition")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.45f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "PulseScale"
    )
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.35f,
        targetValue = 0.05f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "PulseAlpha"
    )

    LaunchedEffect(Unit) {
        // Fade in & Pop scale
        launch {
            alphaAnim.animateTo(1f, tween(400))
        }
        launch {
            scaleAnim.animateTo(
                targetValue = 1f,
                animationSpec = tween(700, easing = FastOutSlowInEasing)
            )
        }
        // Smooth 360 degree spin
        launch {
            rotateAnim.animateTo(
                targetValue = 360f,
                animationSpec = tween(1200, easing = FastOutSlowInEasing)
            )
        }
        // 2-second Progress Bar Fill
        launch {
            progressAnim.animateTo(
                targetValue = 1f,
                animationSpec = tween(1900, easing = LinearEasing)
            )
        }

        // Exact 2-second screen duration
        delay(2000L)
        onAnimationFinished()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(RaptechColors.SurfaceWhite),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
            modifier = Modifier
                .alpha(alphaAnim.value)
                .scale(scaleAnim.value)
        ) {
            // Dice Centerpiece with Cyber Pulse Rings
            Box(
                contentAlignment = Alignment.Center,
                modifier = Modifier.size(140.dp)
            ) {
                // Outer Pulse Ring 2
                Box(
                    modifier = Modifier
                        .size(130.dp)
                        .scale(pulseScale)
                        .alpha(pulseAlpha)
                        .clip(CircleShape)
                        .background(RaptechColors.OrangePrimary)
                )

                // Outer Pulse Ring 1
                Box(
                    modifier = Modifier
                        .size(105.dp)
                        .clip(CircleShape)
                        .background(RaptechColors.OrangeSoft)
                        .border(1.5.dp, RaptechColors.OrangeBorder, CircleShape)
                )

                // Central Rounded Amber Dice Container
                Box(
                    modifier = Modifier
                        .size(72.dp)
                        .rotate(rotateAnim.value)
                        .clip(RoundedCornerShape(18.dp))
                        .background(RaptechColors.OrangePrimary)
                        .border(2.dp, RaptechColors.OrangeBorder, RoundedCornerShape(18.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        painter = painterResource(id = R.drawable.ic_dice),
                        contentDescription = "Raptech Dice",
                        tint = Color.White,
                        modifier = Modifier.size(42.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Branding Typography
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Text(
                    text = "RAPTECH",
                    color = RaptechColors.TextPrimary,
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Black,
                    fontFamily = FontFamily.SansSerif,
                    letterSpacing = 2.sp
                )
                Text(
                    text = "DICE",
                    color = RaptechColors.OrangePrimary,
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Black,
                    fontFamily = FontFamily.SansSerif,
                    letterSpacing = 2.sp
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            // Subtitle Tag
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .background(RaptechColors.OrangeSoft)
                    .border(1.dp, RaptechColors.OrangeBorder, RoundedCornerShape(6.dp))
                    .padding(horizontal = 10.dp, vertical = 3.dp)
            ) {
                Text(
                    text = "CRYPTO AUTOMATION ENGINE",
                    color = RaptechColors.OrangePrimary,
                    fontSize = 9.5.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    letterSpacing = 1.sp
                )
            }

            Spacer(modifier = Modifier.height(32.dp))

            // 2-Second Linear Loading Bar
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.width(180.dp)
            ) {
                LinearProgressIndicator(
                    progress = { progressAnim.value },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(4.dp)
                        .clip(RoundedCornerShape(2.dp)),
                    color = RaptechColors.OrangePrimary,
                    trackColor = RaptechColors.OrangeSoft
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "INITIALIZING...",
                    color = RaptechColors.TextMuted,
                    fontSize = 9.sp,
                    fontWeight = FontWeight.SemiBold,
                    fontFamily = FontFamily.Monospace,
                    letterSpacing = 1.sp
                )
            }
        }
    }
}
