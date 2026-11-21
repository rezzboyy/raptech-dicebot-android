# Production Readiness & Release Guide (Raptech Dicebot Android)

Dokumen ini memuat panduan persiapan rilis produksi, optimasi performa binary, konfigurasi ProGuard/R8, deklarasi izin Android 15 (SDK 35), dan kepatuhan standar keamanan eksekusi taruhan untuk aplikasi **Raptech Dicebot Android** berbasis **Kotlin + Jetpack Compose**.

---

## 1. Konfigurasi Build & Spesifikasi SDK

### 1.1 Spesifikasi Versi SDK
- **`compileSdk`**: `35` (Android 15)
- **`minSdk`**: `24` (Android 7.0 Nougat) — mencakup >97% perangkat aktif global dengan dukungan Java 8+/17 dan hardware crypto.
- **`targetSdk`**: `35` (Kepatuhan penuh standar Google Play Store & Android 15 Edge-to-Edge).
- **`jvmTarget`**: `17` (Kompatibel dengan toolchain Java modern).

### 1.2 Skema Versi Aplikasi
- **`versionCode`**: Nilai integer berurutan (`1`, `2`, `3`, ...) untuk setiap rilis.
- **`versionName`**: Semantic Versioning `vMAJOR.MINOR.PATCH` (contoh: `v1.0.0-android`).

---

## 2. Keamanan & Penandatanganan Aplikasi (App Signing)

### 2.1 File `keystore.properties` (Lokal & Terlindungi)
Keystore produksi **dilarang keras** di-commit ke repositori Git. Buat file konfigurasi terpisah:

```properties
# keystore.properties (Wajib masuk ke .gitignore)
KEYSTORE_PATH=../keystore/raptech_dicebot_release.jks
KEYSTORE_PASSWORD=super_secure_keystore_password
KEY_ALIAS=raptech_dicebot
KEY_PASSWORD=super_secure_key_password
```

### 2.2 Konfigurasi Gradle (`app/build.gradle.kts`)
```kotlin
import java.util.Properties

val keystorePropertiesFile = rootProject.file("keystore.properties")
val keystoreProperties = Properties().apply {
    if (keystorePropertiesFile.exists()) {
        load(keystorePropertiesFile.inputStream())
    }
}

android {
    signingConfigs {
        create("release") {
            storeFile = file(keystoreProperties.getProperty("KEYSTORE_PATH") ?: "dummy.jks")
            storePassword = keystoreProperties.getProperty("KEYSTORE_PASSWORD")
            keyAlias = keystoreProperties.getProperty("KEY_ALIAS")
            keyPassword = keystoreProperties.getProperty("KEY_PASSWORD")
            enableV3Signing = true
            enableV4Signing = true
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            signingConfig = signingConfigs.getByName("release")
        }
    }
}
```

---

## 3. Konfigurasi ProGuard & R8 Optimization (`proguard-rules.pro`)

Penggunaan engine `LuaJ` membutuhkan aturan ProGuard khusus karena LuaJ banyak menggunakan refleksi Java internal saat memetakan fungsi skrip:

```proguard
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

# === Sanitasi Logcat Produksi ===
-assumenosideeffects class android.util.Log {
    public static boolean isLoggable(java.lang.String, int);
    public static int v(...);
    public static int d(...);
}
```

---

## 4. Konfigurasi Foreground Service & Izin Android 14/15

Mulai Android 14 (API 34) dan Android 15 (API 35), Foreground Service wajib mendeklarasikan tipe layanan spesifik di `AndroidManifest.xml`:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- Izin Jaringan -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <!-- Izin Eksekusi Latar Belakang & Notifikasi -->
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />
    <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />

    <application
        android:allowBackup="false"
        android:label="Raptech Dicebot"
        android:theme="@style/Theme.RaptechDicebot">

        <!-- Layanan Bot Latar Belakang -->
        <service
            android:name=".service.DicebotForegroundService"
            android:exported="false"
            android:foregroundServiceType="specialUse">
            <property
                android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"
                android:value="Automated Crypto Dicebot Strategy Runner" />
        </service>

    </application>
</manifest>
```

---

## 5. Tolok Ukur Kinerja Target (Performance Benchmarks)

| Metrik Kinerja | Target Produksi | Metode Pengukuran |
|---|---|---|
| **Ukuran File APK Release** | **< 8.0 MB** | Hasil build `./gradlew assembleRelease` dengan R8 aktif |
| **Waktu Cold Start** | **< 180 ms** | Android Profiler / Macrobenchmark `StartupTimingMetric` |
| **Konsumsi RAM (Idle)** | **< 35 MB** | Memory Profiler pada halaman dashboard sebelum bot aktif |
| **Konsumsi RAM (Active 5.000 Bets)** | **< 65 MB** | Memory Profiler setelah bot berjalan 1 jam dengan Ring Buffer |
| **Frame Rendering UI** | **60 / 120 FPS** | GPU Rendering Profile (tidak ada garis merah melompati 16ms) |
| **Latensi Siklus LUA per Bet** | **< 3 ms** | Stopwatch benchmarking evaluasi fungsi strategi `dobet()` |

---

## 6. Daftar Periksa Pra-Rilis (Pre-Release Checklist)

### 6.1 Fungsionalitas & Engine
- [ ] Script LUA default (Martingale dasar & Raptech snippet) berjalan lancar tanpa error sintaks.
- [ ] Ring Buffer membatasi data history maksimal sesuai konfigurasi pengguna (`Max Record`).
- [ ] Tombol kontrol `[START]`, `[PAUSE]`, `[STOP]`, dan `[REFRESH BAL]` merespons seketika.

### 6.2 Manajemen Risiko & Keamanan
- [ ] **Hard Stop-Loss**: Teruji mematikan bot 100% seketika saat saldo menyentuh batas bawah.
- [ ] **Take-Profit**: Teruji mematikan bot 100% saat target profit tercapai.
- [ ] **Max Bet Cap**: Menolak eksekusi bet jika nilai taruhan hasil kalkulasi LUA melebihi batas yang diizinkan.
- [ ] Kredensial akun (API Key / Cookie) tersimpan di EncryptedSharedPreferences (bukan plaintext).
- [ ] Tidak ada token rahasia yang tercetak di Logcat rilis.

### 6.3 Stabilitas Latar Belakang (Android Background Stability)
- [ ] Notifikasi status bar (`ForegroundService`) muncul dengan indikator saldo dan PnL terkini.
- [ ] Bot tetap berjalan tanpa putus saat layar HP dimatikan selama minimal 30 menit.
- [ ] Dialog edukasi optimasi baterai (*Ignore Battery Optimization*) tampil untuk memandu pengguna.
