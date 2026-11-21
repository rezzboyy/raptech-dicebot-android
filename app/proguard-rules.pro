# === LuaJ Rules (Kritis: Mencegah Crash Refleksi Runtime) ===
-keep class org.luaj.vm2.** { *; }
-keep interface org.luaj.vm2.** { *; }
-dontwarn org.luaj.vm2.**

# === Kotlinx Serialization ===
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.SerializationKt
-keepclassmembers class * {
    *** Companion;
}
-keepclasseswithmembers class * {
    kotlinx.serialization.KSerializer serializer(...);
}

# === OkHttp3 & WebSocket ===
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }
-keep interface okhttp3.** { *; }

# === Compose Runtime ===
-keep class androidx.compose.runtime.** { *; }

# === Google Crypto / Tink (Security-Crypto) ===
-dontwarn com.google.errorprone.annotations.**
-dontwarn javax.script.**
