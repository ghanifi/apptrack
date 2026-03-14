# App Store & Google Play Store Yayinlama Rehberi - 2026

> Son guncelleme: Mart 2026
> Bu dokuman, 2026 yili itibariyle Apple App Store ve Google Play Store'da uygulama yayinlama sureclerini, guncel gereksinimleri ve red (rejection) riskini minimize etmek icin yapilmasi gerekenleri kapsar.

---

## 1. Apple App Store 2026 Gereksinimleri

### 1.1 SDK ve Xcode Gereksinimleri

| Gereksinim | Detay | Tarih |
|---|---|---|
| **iOS/iPadOS SDK** | iOS 26 & iPadOS 26 SDK veya uzeri | 28 Nisan 2026 |
| **tvOS SDK** | tvOS 26 SDK veya uzeri | 28 Nisan 2026 |
| **watchOS SDK** | watchOS 26 SDK veya uzeri | 28 Nisan 2026 |
| **visionOS SDK** | visionOS 26 SDK veya uzeri | 28 Nisan 2026 |
| **Xcode** | Xcode 26 veya uzeri | 28 Nisan 2026 |

**Onemli:** SDK gereksinimi, uygulamanin hangi SDK ile **derlendigi** ile ilgilidir. Minimum deployment target farkli olabilir. iOS 16/17 destegi devam ettirilebilir, ancak derleme iOS 26 SDK ile yapilmalidir.

**Onceki gereksinim (Nisan 2025):** Xcode 16, iOS 18 SDK.

### 1.2 Privacy Manifest (PrivacyInfo.xcprivacy)

**Zorunlu:** Mayis 2024'ten itibaren tum yeni ve guncellenen uygulamalar icin.

**Dosya adi:** `PrivacyInfo.xcprivacy` (degistirilemez)

**Icerik gereksinimleri:**
- Toplanan veri turlerinin beyan edilmesi
- Required Reason API kullaniminin belirtilmesi
- Ucuncu taraf SDK'larin privacy manifest'leri ve imzalari

### 1.3 Required Reason APIs

Asagidaki API kategorileri icin kullanim nedeni belirtilmelidir:

| API Kategorisi | NSPrivacyAccessedAPIType | Ornek Neden Kodu |
|---|---|---|
| **UserDefaults** | `NSPrivacyAccessedAPICategoryUserDefaults` | CA92.1 |
| **File Timestamp** | `NSPrivacyAccessedAPICategoryFileTimestamp` | 3B52.1 |
| **Disk Space** | `NSPrivacyAccessedAPICategoryDiskSpace` | 7D9E.1 |
| **System Boot Time** | `NSPrivacyAccessedAPICategorySystemBootTime` | 35F9.1 |
| **Active Keyboard** | `NSPrivacyAccessedAPICategoryActiveKeyboards` | - |

> UserDefaults tahminen uygulamalarin %90'i tarafindan kullanilmaktadir. Bu API'yi kullaniyorsaniz mutlaka beyan edin.

### 1.4 App Tracking Transparency (ATT)

- iOS 14.5+ icin zorunlu
- Kullanici takibi veya IDFA erisimi icin `AppTrackingTransparency` framework kullanilmali
- Kullanici izni ALINMADAN tracking yapilamaz
- ATT prompt metni acik ve anlasilir olmali
- Ucuncu taraf SDK'larin tracking davranislari da beyan edilmeli

### 1.5 Privacy Nutrition Labels

- Tum App Store uygulamalari icin **zorunlu**
- Gizlilik politikasi URL'si (publicaccess erisilebilir) zorunlu
- Toplanan tum veri turleri beyan edilmeli
- Veri kullanim amaci (analytics, tracking, vs.) belirtilmeli
- Ucuncu taraf ortaklarin topladigi veriler de dahil
- Guncel tutulmali - uyumsuzluk red sebebi

### 1.6 Yas Derecelendirme Sistemi (Guncellendi)

Yeni yas derecelendirme sistemi:
- **4+**, **9+**, **13+** (yeni), **16+** (yeni), **18+** (yeni)
- **Son tarih:** 31 Ocak 2026'ya kadar guncellenmeli
- Guncellenmezse yeni gonderimler engellenebilir

### 1.7 IPv6 Destegi

- 1 Haziran 2016'dan beri zorunlu
- Uygulama IPv6-only aglarda tam islevsel olmali
- Hardcoded IPv4 adresleri kullanilmamali

### 1.8 Bitcode

- Xcode 14'te deprecated edildi
- Xcode 15'te tamamen kaldirildi
- Xcode 16+ ile bitcode iceren uygulamalar **reddedilir**
- Ucuncu taraf kutuphane/framework'lerde bitcode varsa kaldirilmali
- `ENABLE_BITCODE = NO` olmali

### 1.9 Notarization (Alternatif Dagitim)

- AB ve Japonya icin alternatif dagitim mekanizmasi
- iOS uygulamalari icin notarization gereksinimleri mevcut
- Standart App Store dagitimi icin mevcut review sureci gecerli

### 1.10 SwiftUI vs UIKit

- Apple'dan zorunlu SwiftUI mandati **YOKTUR**
- UIKit ile gelistirilen uygulamalar kabul edilmeye devam ediyor
- SwiftUI tercih edilir ancak zorunlu degil

---

## 2. Google Play Store 2026 Gereksinimleri

### 2.1 Target API Level

| Uygulama Turu | Minimum targetSdkVersion | Son Tarih |
|---|---|---|
| **Yeni uygulamalar** | API 35 (Android 15) | 31 Agustos 2025 (GECTI) |
| **Mevcut uygulama guncellemeleri** | API 35 (Android 15) | 31 Agustos 2025 (GECTI) |
| **Mevcut uygulamalar (guncelleme yok)** | API 34 (Android 14) | 31 Agustos 2025 |
| **Wear OS** | API 33 (Android 13) | 31 Agustos 2025 |
| **Android TV** | API 33 (Android 13) | 31 Agustos 2025 |

> **Not:** API 36 (Android 16) icin resmi zorunlu tarih henuz duyurulmadi (Mart 2026 itibariyle). Ancak gelecek Agustos 2026'da yukseltilmesi bekleniyor.

### 2.2 Android App Bundle (AAB)

- Yeni uygulamalar icin **AAB zorunlu** (APK kabul edilmez)
- AAB, optimize edilmis dagitim saglar
- Play App Signing ile birlikte calisir

### 2.3 Play App Signing

- Tum yeni uygulamalar icin **zorunlu**
- Google, uygulama imzalama anahtarini yonetir
- Upload key ile AAB yuklenir, Google distribution APK'lari imzalar
- Anahtar kaybina karsi koruma saglar

### 2.4 Data Safety Section

**Zorunlu** (Temmuz 2022'den beri):
- Toplanan veri turlerinin beyani
- Veri paylasimi beyani
- Veri guvenlik uygulamalari
- Veri silme mekanizmasi
- Gizlilik politikasi URL'si
- Kapalyi, acik ve production test track'leri dahil tum uygulamalar icin gecerli

### 2.5 Play Integrity API

- Uygulama butunlugunu dogrulama
- Cihaz guvenlik durumunu kontrol etme
- Google Cloud projesi gerektirir
- Play Console veya SDK Console'da baglanti yapilmali
- Safetynet'in yerini aldi

### 2.6 Foto/Video Izinleri Politikasi

- `READ_MEDIA_IMAGES` ve `READ_MEDIA_VIDEO` icin **ozel beyar** gerekiyor
- Tek seferlik kullanim icin sistem picker kullanilmali (ornek: profil foto yukleme)
- Genis erisim icin Play Console'dan beyar formu doldurulmali
- **Son tarih:** 28 Mayis 2025 (GECTI) - uyumsuz uygulamalar kaldirilabilir

### 2.7 Foreground Service Kisitlamalari

- Android 12+ ile arka plandan foreground service baslatma kisitlanddi
- WorkManager veya exact alarm kullanilmali
- Foreground service tipi belirtilmeli
- Gereksiz foreground service kullanimi red sebebi

### 2.8 Yas Derecelendirme ve Icerik

- Yeni Age-Restricted Content and Functionality politikasi
- Matchmaking, dating, gercek para kumari icin minoru engelleme zorunlulugu
- Age Signals API kullanimi (1 Ocak 2026'dan itibaren yalnizca yas uygun deneyimler icin)
- ABD'de bazi eyaletlerde (Utah, Louisiana) yas dogrulama yasalari: Mayis ve Temmuz 2026

### 2.9 Gelistirici Dogrulamasi (Yeni - 2026)

- Eylul 2026'dan itibaren (Brezilya, Endonezya, Singapur, Tayland)
- 2027'de global genisleme
- Tum Android uygulama gelistiricileri icin dogrulama zorunlulugu
- Play Store disinda dagitilan uygulamalar da dahil

### 2.10 SDK Politikasi Degisiklikleri

- Ucuncu taraf SDK'lar (ornek: reklam SDK'lari) da politika uyumlulugundan sorumlu
- SDK davranisi, uygulamanin uyumluluegunu etkiler
- SDK veri toplama beyani Data Safety'de belirtilmeli

---

## 3. Yaygin Red (Rejection) Nedenleri

### 3.1 Apple App Store - En Yaygin Red Nedenleri

Apple, 2024'te yaklasik **7.77 milyon** uygulama gonderimini inceledi ve bunlarin yaklasik **%25'ini** reddetti.

| Sira | Neden | Guideline | Aciklama |
|---|---|---|---|
| 1 | **App Completeness** | 2.1 | Tamamlanmamis ozellikler, placeholder icerik (~%40 cozulmeyen vakalar) |
| 2 | **Privacy Violations** | 5.1 | Eksik gizlilik beyanlari, ATT uyumsuzlugu |
| 3 | **Crashes / Bugs** | 2.1 | Lansman sirasinda cokme, ciddi hatalar |
| 4 | **Yaniltici Metadata** | 2.3 | Ekran goruntuleri, baslik, aciklama uyumsuzlugu |
| 5 | **Eksik/Belirsiz Izinler** | 5.1.1 | Kamera, konum vb. icin aciklama eksikligi |
| 6 | **In-App Purchase** | 3.1 | Restore purchases eksikligi, test edememe |
| 7 | **SDK Uyumsuzlugu** | - | Privacy manifest eksik, imzasiz SDK'lar |
| 8 | **AI/Otomasyon Aciklamasi** | - | AI kullanan uygulamalarda yetersiz aciklama |
| 9 | **Performans** | 4.0 | Yavas yukleme, asiri bellek kullanimi |
| 10 | **Yasal Gereksinimler** | 5.0 | Gizlilik politikasi linki eksik, yerel yasa uyumsuzlugu |

### 3.2 Google Play Store - En Yaygin Red Nedenleri

Google, 2025'te **1.75 milyon+** uygulamanin yayinlanmasini engelledi ve **80.000+** gelistirici hesabini kapatti.

| Sira | Neden | Aciklama |
|---|---|---|
| 1 | **Crashes / ANR** | Cokme, Application Not Responding hatalari |
| 2 | **Izin Suistimali** | Gereksiz izin talepleri, gizli veri toplama |
| 3 | **Data Safety Uyumsuzlugu** | Eksik veya yanlis beyar |
| 4 | **Ince Icerik (Thin Content)** | Yetersiz islevsellik, deger katmayan uygulama |
| 5 | **Faturalama Politikasi** | Google Play billing kullanmama |
| 6 | **Gizlilik Politikasi** | Eksik veya bozuk gizlilik politikasi linki |
| 7 | **Kapali Test Basarisizligi** | Pre-launch report'ta ciddi sorunlar |
| 8 | **Veri Toplama Uygulamalari** | Asiri veri toplama, yetersiz kullanici rizasi |
| 9 | **Target SDK Uyumsuzlugu** | Eski targetSdkVersion |
| 10 | **Aldatici Davranis** | Yaniltici uygulama adi, ikon veya aciklama |

### 3.3 Metadata Red Nedenleri (Her Iki Store)

- Ekran goruntuleri uygulamayi yansitmiyor
- Baslik/aciklamada yaniltici ifadeler
- Keywords spam
- Uygunsuz icerik yas derecesiyle uyumsuz
- Telif hakki ihlali (ikon, isim)
- Gizlilik politikasi linki calismiyor veya eksik

### 3.4 Izin Kullani Aciklamalari

**Apple (Info.plist):**
```xml
<key>NSCameraUsageDescription</key>
<string>Profil fotosu cekmek icin kamera erisimine ihtiyacimiz var</string>
<key>NSPhotoLibraryUsageDescription</key>
<string>Profil fotosu secmek icin galeri erisimine ihtiyacimiz var</string>
<key>NSLocationWhenInUseUsageDescription</key>
<string>Yakininizdaki isletmeleri gostermek icin konum bilgisi gereklidir</string>
```

**Android (AndroidManifest.xml):**
```xml
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<!-- Runtime permission aciklamalari kod icerisinde gosterilmeli -->
```

---

## 4. Otomatik Uyumluluk Kontrolleri

### 4.1 Google Checks (CI/CD Entegrasyonu)

Google'in resmi uyumluluk tarama araci:

**Entegrasyon secenekleri:**
- GitHub Actions plugin
- Jenkins plugin
- Fastlane plugin
- CLI binary (tum CI/CD platformlari)
- REST API (ozel entegrasyonlar)

**Tarama kapsami:**
- Data Safety beyan dogrulamasi
- Izin kullanim analizi
- Families politikasi uyumlulugu
- API kullanim kontrolu
- Statik ve dinamik analiz

**CI/CD kullanimi:**
```yaml
# GitHub Actions ornegi
- name: Run Google Checks
  uses: google-checks/checks-app-scan-action@v1
  with:
    account_id: ${{ secrets.CHECKS_ACCOUNT_ID }}
    app_id: ${{ secrets.CHECKS_APP_ID }}
    binary_path: app/build/outputs/bundle/release/app-release.aab
```

### 4.2 Apple Tarafli Otomatik Kontroller

- **Xcode Analyzer:** Statik kod analizi
- **Privacy Manifest Validator:** Xcode 15+ icinde yerlesik
- **App Store Connect API:** Otomasyon onaylari
- **xcrun altool:** Komut satiri dogrulama araci
- **Transporter:** App Store'a yukleme ve dogrulama

### 4.3 Google Play Pre-Launch Report

**Otomatik ozellikler:**
- AAB/APK yuklendiginde otomatik tetiklenir
- Robo test ile otomatik kesfedici test
- Crash ve ANR tespiti
- Yavas baslangic ve bellek sorunlari uyarisi
- Erisilebilirlik kontrolleri (eksik content label vb.)
- Birden fazla cihaz ve ekran boyutunda test
- Dil-spesifik testler
- Login ekrani arkasi test destegi

### 4.4 CI/CD Pipeline Kontrol Listesi

```yaml
# Ornek CI/CD kontrol adimlari
steps:
  # 1. Statik Analiz
  - lint_check          # Android Lint / SwiftLint
  - privacy_manifest    # PrivacyInfo.xcprivacy dogrulama
  - permission_audit    # Gereksiz izin kontrolu

  # 2. Build Dogrulama
  - build_release       # Release build
  - signing_check       # Imza dogrulama
  - bitcode_check       # Bitcode kaldirildi mi (iOS)

  # 3. Uyumluluk Tarama
  - google_checks       # Google Checks taramasi
  - metadata_validate   # Metadata dogrulama
  - privacy_policy_url  # Gizlilik politikasi URL kontrolu

  # 4. Test
  - unit_tests
  - ui_tests
  - pre_launch_report   # Google Play pre-launch
```

---

## 5. Build Konfigurasyonu En Iyi Uygulamalar

### 5.1 iOS - Imzalama Konfigurasyonu

**Sertifika Turleri:**
| Tur | Kullanim |
|---|---|
| Apple Development | Gelistirme ve test |
| Apple Distribution | App Store ve Ad Hoc dagitim |

**ExportOptions.plist Ornegi (App Store):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>app-store</string>
    <key>teamID</key>
    <string>YOUR_TEAM_ID</string>
    <key>uploadBitcode</key>
    <false/>
    <key>uploadSymbols</key>
    <true/>
    <key>signingStyle</key>
    <string>manual</string>
    <key>provisioningProfiles</key>
    <dict>
        <key>com.yourcompany.yourapp</key>
        <string>Your App Store Profile Name</string>
    </dict>
    <key>signingCertificate</key>
    <string>Apple Distribution</string>
</dict>
</plist>
```

**En iyi uygulamalar:**
- Uretim dagitimlari icin **manual signing** kullanin
- Team ID'nin Apple Developer hesabinizla eslestiyini dogrulayin
- Her bundle identifier icin provisioning profile girisi ekleyin
- Extension'lar dahil tum target'lar icin profil tanimlannin
- ExportOptions.plist dosyasini version control'de tutun
- `uploadBitcode` her zaman `false` olmali (Xcode 16+)

### 5.2 Android - Build Konfigurasyonu

**build.gradle (app):**
```groovy
android {
    compileSdk 35  // veya 36

    defaultConfig {
        applicationId "com.yourcompany.yourapp"
        minSdk 24        // Minimum desteklenen Android
        targetSdk 35     // Google Play gereksinimi
        versionCode 1
        versionName "1.0.0"
    }

    signingConfigs {
        release {
            storeFile file("upload-keystore.jks")
            storePassword System.getenv("KEYSTORE_PASSWORD")
            keyAlias System.getenv("KEY_ALIAS")
            keyPassword System.getenv("KEY_PASSWORD")
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
            signingConfig = signingConfigs.release
        }
    }

    bundle {
        // AAB ayarlari
        language { enableSplit = true }
        density { enableSplit = true }
        abi { enableSplit = true }
    }
}
```

### 5.3 ProGuard/R8 Konfigurasyonu

**proguard-rules.pro temel kurallar:**
```proguard
# Data modelleri - obfuscate etmeyin
-keep class com.yourcompany.yourapp.model.** { *; }

# Retrofit interfaces
-keep interface com.yourcompany.yourapp.api.** { *; }

# Reflection kullanan siniflar
-keep class * implements java.io.Serializable { *; }

# Gson/Moshi
-keepattributes Signature
-keepattributes *Annotation*

# Enum'lar
-keepclassmembers enum * {
    public static **[] values();
    public static ** valueOf(java.lang.String);
}

# Crash raporlama icin satir numaralari
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
```

**R8 Durumu (2026):**
- R8, ProGuard'in yerini almistir (AGP 3.4.0+)
- Tek adimda shrinking + obfuscation + optimization
- ProGuard kural dosyalari R8 ile uyumludur
- `isMinifyEnabled = true` ve `isShrinkResources = true` kullanin

### 5.4 Play App Signing Akisi

```
Gelistirici -> Upload Key ile imzala -> AAB yukle -> Google Play
                                                        |
                                                   Play App Signing
                                                        |
                                               Distribution APK olustur
                                                        |
                                                  Kullaniciya dagit
```

---

## 6. Gonderim Akisi Otomasyonu

### 6.1 App Store Connect API - Otomatik Gonderim

**Authentication:**
```ruby
# Fastlane - API Key Setup
api_key = app_store_connect_api_key(
  key_id: "YOUR_KEY_ID",
  issuer_id: "YOUR_ISSUER_ID",
  key_filepath: "./AuthKey_XXXXXXXX.p8",
  duration: 1200,           # opsiyonel
  in_house: false           # Enterprise icin true
)
```

**Tam Otomasyon Akisi (Fastlane):**
```ruby
# Fastfile
default_platform(:ios)

platform :ios do
  desc "App Store'a otomatik gonderim"
  lane :release do
    # 1. Sertifika ve profil senkronizasyonu
    match(
      type: "appstore",
      api_key: api_key,
      readonly: true
    )

    # 2. Build numarasi artir
    increment_build_number(
      build_number: latest_testflight_build_number + 1
    )

    # 3. Archive
    build_app(
      scheme: "YourApp",
      export_method: "app-store",
      export_options: {
        uploadBitcode: false,
        uploadSymbols: true
      }
    )

    # 4. TestFlight'a yukle
    upload_to_testflight(
      api_key: api_key,
      skip_waiting_for_build_processing: false
    )

    # 5. App Store Review'a gonder (opsiyonel)
    deliver(
      api_key: api_key,
      submit_for_review: true,
      automatic_release: true,
      force: true,
      submission_information: {
        add_id_info_uses_idfa: false
      }
    )
  end
end
```

### 6.2 Google Play Developer API - Otomatik Gonderim

**Fastlane Supply ile:**
```ruby
# Fastfile
default_platform(:android)

platform :android do
  desc "Google Play Store'a otomatik gonderim"
  lane :release do
    # 1. Build
    gradle(
      task: "bundle",
      build_type: "Release"
    )

    # 2. Play Store'a yukle
    supply(
      track: "production",           # veya "internal", "alpha", "beta"
      aab: "app/build/outputs/bundle/release/app-release.aab",
      json_key: "play-store-key.json",
      release_status: "completed",   # veya "draft", "halted"
      rollout: "1.0",               # %100 rollout
      skip_upload_metadata: false,
      skip_upload_images: false,
      skip_upload_screenshots: false
    )
  end
end
```

**API Kurulum Adimlari:**
1. Google Cloud Console'da yeni service account olusturun
2. Google Play Android Developer API'yi etkinlestirin
3. Service account icin private key (.json) indirin
4. Google Play Console'da service account'u davet edin
5. Gerekli izinleri atayin (Release management, Store listing editing)

**Onemli:** Ilk uygulama yuklemeniz **manuel** yapilmali. API, ilk gonderim icin kullanilamaz.

### 6.3 TestFlight Otomatik Dagitim

```ruby
# TestFlight dagitim
upload_to_testflight(
  api_key: api_key,
  changelog: "Bug fixes and performance improvements",
  distribute_external: true,
  groups: ["Beta Testers"],
  notify_external_testers: true
)
```

### 6.4 Tam CI/CD Pipeline (GitHub Actions Ornegi)

```yaml
# .github/workflows/release.yml
name: Release to Stores

on:
  push:
    tags:
      - 'v*'

jobs:
  ios-release:
    runs-on: macos-latest  # veya self-hosted macOS runner
    steps:
      - uses: actions/checkout@v4

      - name: Setup Ruby
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.2'
          bundler-cache: true

      - name: Install dependencies
        run: bundle install

      - name: Build and Upload to TestFlight
        env:
          APP_STORE_CONNECT_API_KEY_ID: ${{ secrets.ASC_KEY_ID }}
          APP_STORE_CONNECT_API_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
          APP_STORE_CONNECT_API_KEY: ${{ secrets.ASC_API_KEY }}
          MATCH_PASSWORD: ${{ secrets.MATCH_PASSWORD }}
        run: bundle exec fastlane ios release

  android-release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'

      - name: Setup Ruby
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.2'
          bundler-cache: true

      - name: Decode Keystore
        run: echo "${{ secrets.KEYSTORE_BASE64 }}" | base64 -d > upload-keystore.jks

      - name: Build AAB
        env:
          KEYSTORE_PASSWORD: ${{ secrets.KEYSTORE_PASSWORD }}
          KEY_ALIAS: ${{ secrets.KEY_ALIAS }}
          KEY_PASSWORD: ${{ secrets.KEY_PASSWORD }}
        run: ./gradlew bundleRelease

      - name: Upload to Play Store
        env:
          SUPPLY_JSON_KEY_DATA: ${{ secrets.PLAY_STORE_JSON_KEY }}
        run: bundle exec fastlane android release
```

### 6.5 Uctan Uca Otomasyon - Mumkun mu?

| Adim | Apple | Google | Otomasyonmmu? |
|---|---|---|---|
| Build | Xcode CLI / Fastlane | Gradle / Fastlane | Evet |
| Signing | Fastlane Match | Play App Signing | Evet |
| Upload | Fastlane Deliver/Pilot | Fastlane Supply | Evet |
| Metadata | Fastlane Deliver | Fastlane Supply | Evet |
| Screenshots | Fastlane Snapshot | Fastlane Screengrab | Evet |
| Review Submit | App Store Connect API | Otomatik | Evet |
| Review Sureci | Apple Review (~24-48 saat) | Google Review (~saatler-gunler) | HAYIR |
| Release | Otomatik release mumkun | Otomatik rollout mumkun | Evet |

**Sonuc:** Review sureci haric, tum asamalar uctan uca otomatiklestirilebilir.

---

## 7. Hizli Kontrol Listesi

### App Store Gonderim Oncesi

- [ ] Xcode 26 ile derleme (Nisan 2026 sonrasi)
- [ ] PrivacyInfo.xcprivacy dosyasi eklenmiis ve dogru
- [ ] Required Reason API'lar beyan edilmis
- [ ] ATT framework entegre (tracking varsa)
- [ ] Privacy Nutrition Labels guncellenmis
- [ ] Yas derecelendirme sorulari cevaplandmis
- [ ] Gizlilik politikasi URL'si calisiyor
- [ ] IPv6-only network destegi
- [ ] Bitcode devre disi (ENABLE_BITCODE = NO)
- [ ] Tum ekran goruntuleri guncel
- [ ] In-App Purchase restore fonksiyonu mevcut
- [ ] Crash-free lansman dogrulanmis
- [ ] Tum izin aciklamalari (Info.plist) eklenmis
- [ ] Apple Distribution sertifikasi ile imzalanmis
- [ ] ExportOptions.plist dogru yapilandirilmis
- [ ] SDK'larin privacy manifest ve imzalari mevcut

### Google Play Gonderim Oncesi

- [ ] targetSdkVersion >= 35
- [ ] AAB formati (APK degil)
- [ ] Play App Signing etkin
- [ ] Data Safety section tamamlanmis
- [ ] Gizlilik politikasi URL'si calisiyor
- [ ] Yas derecelendirme tamamlanmis
- [ ] Gereksiz izinler kaldirilmis
- [ ] Foto/video izinleri politikasina uygun
- [ ] Foreground service tipleri belirtilmis
- [ ] ProGuard/R8 etkin ve yapilandirilmis
- [ ] Upload keystore ile imzalanmis
- [ ] Pre-launch report kontrol edilmis
- [ ] SDK veri toplama beyani Data Safety'de
- [ ] Tum ekran goruntuleri guncel
- [ ] Release notes eklenmis

---

## Kaynaklar

### Apple
- [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- [Upcoming Requirements](https://developer.apple.com/news/upcoming-requirements/)
- [Privacy Manifest Files](https://developer.apple.com/documentation/bundleresources/privacy-manifest-files)
- [Required Reason API](https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api)
- [App Tracking Transparency](https://developer.apple.com/documentation/apptrackingtransparency)
- [App Privacy Details](https://developer.apple.com/app-store/app-privacy-details/)
- [Submitting to App Store](https://developer.apple.com/app-store/submitting/)

### Google
- [Target API Level Requirements](https://developer.android.com/google/play/requirements/target-sdk)
- [Data Safety Section](https://support.google.com/googleplay/android-developer/answer/10787469)
- [Play App Signing](https://support.google.com/googleplay/android-developer/answer/9842756)
- [Play Integrity API](https://developer.android.com/google/play/integrity/overview)
- [Pre-Launch Reports](https://support.google.com/googleplay/android-developer/answer/9842757)
- [Google Checks](https://checks.google.com/)
- [Developer Program Policy](https://support.google.com/googleplay/android-developer/answer/16810878)

### Araclar
- [Fastlane](https://fastlane.tools/)
- [Fastlane Deliver](https://docs.fastlane.tools/actions/deliver/)
- [Fastlane Supply](https://docs.fastlane.tools/actions/supply/)
- [Google Checks CI/CD](https://developers.google.com/checks/guide/app-compliance/integrate/ci-cd/overview)

### Ek Kaynaklar
- [iOS App Store Review Guidelines 2026 - TheAppLaunchpad](https://theapplaunchpad.com/blog/app-store-review-guidelines)
- [Google Play Developer Policy Changes 2026 - OpenForge](https://openforge.io/google-play-developer-policy-changes-that-matter-in-2026/)
- [Apple App Store Submission Changes April 2026 - Medium](https://medium.com/@thakurneeshu280/apple-app-store-submission-changes-april-2026-5fa8bc265bbe)
- [Google Play App Rejection Rate 2026 - PrimeTestLab](https://primetestlab.com/blog/google-play-app-rejection-rate-2026)
- [R8 Code Shrinking - Android Developers](https://developer.android.com/build/shrink-code)
