# Kendi Mac'inle iOS Build — Self-Hosted Runner Rehberi

> Bu rehber, kendi Apple Silicon Mac'ini GitHub Actions **self-hosted runner** olarak
> repona bağlayıp AppTrack iOS build'lerini o makinede çalıştırmanı anlatır.
> Adım adım, komut bloklu.
>
> İleri düzey donanım/servis/keychain detayları için ayrıca bkz.
> [self-hosted-ios-runner.md](self-hosted-ios-runner.md).

## 1. Neden self-hosted?

- **Sınırsız build dakikası.** Kendi Mac'in senindir; GitHub-hosted macOS runner'larının
  dakika kotasına takılmazsın.
- **~1/10 maliyet.** GitHub-hosted `macos-26` runner'ları dakika başına en pahalı
  seçenektir. Kendi donanımın bir kez alınır, geri kalanı elektrik parasıdır.
- **AppTrack "compute senin" modeli.** AppTrack orkestrasyonu yapar (workflow, imza,
  artifact, store deploy); asıl derleme senin makinende koşabilir.
- **Opt-in.** Varsayılan hosted `macos-26` runner olarak kalır. Self-hosted'ı yalnızca
  sen açtığında devreye girer — hiçbir şeyi zorla değiştirmez.

## 2. Ön koşullar

- **Apple Silicon Mac** (arm64 — M1/M2/M3/M4). Intel Mac desteklenmez.
- **macOS güncel** olmalı.
- **Xcode 26+ kurulu olmalı.** ⚠️ App Store Connect **28 Nisan 2026'dan** beri
  yüklemeleri **iOS 26 SDK / Xcode 26** ile derlenmiş olarak ister; daha eski SDK ile
  derlenen build'lerin **upload'ı reddedilir**. Sürümü doğrula:

  ```bash
  xcodebuild -version
  # Xcode 26.x görmelisin
  ```

- Repoya **admin erişimi** (runner kaydı Settings → Actions altından yapılır).

## 3. Runner'ı GitHub'a kaydetme

1. GitHub'da repona git: **Settings → Actions → Runners → New self-hosted runner**.
2. İşletim sistemi olarak **macOS**, mimari olarak **ARM64** seç. GitHub sana indirme
   komutlarını ve tek kullanımlık bir kayıt token'ı verir. Kayıt komutu şu biçimdedir:

   ```bash
   ./config.sh --url https://github.com/OWNER/REPO --token <TOKEN>
   ```

3. **Otomatik label'lar.** Kayıt sırasında runner otomatik olarak `self-hosted`,
   `macOS` ve `ARM64` label'larını alır. **Büyük/küçük harf önemlidir** (`macOS`,
   `ARM64` — aynen böyle).

4. **Opsiyonel özel label.** Birden çok Mac'i veya projeyi ayırt etmek istersen kayıt
   sırasında kendi label'ını ekle:

   ```bash
   ./config.sh --url https://github.com/OWNER/REPO --token <TOKEN> --labels apptrack-ios
   ```

   > Bu özel label, AppTrack'teki **Build Runner** ayarına gireceğin label ile
   > **birebir aynı** olmalı. Aksi halde build seni bekleyen bir runner bulamaz.

5. Runner'ı başlat:

   ```bash
   ./run.sh
   ```

   Ya da kalıcı servis olarak (Mac açıldığında otomatik başlar):

   ```bash
   ./svc.sh install
   ./svc.sh start
   ```

## 4. AppTrack'te self-hosted'ı açma

1. AppTrack'te ilgili projenin sayfasını aç.
2. **Build Runner** kartında **"Self-hosted"** seçeneğini işaretle.
3. (Opsiyonel) Kayıtta özel label kullandıysan aynı label'ı buraya gir (ör.
   `apptrack-ios`).
4. **Kaydet.**

Sonraki build'ler senin Mac'inde çalışır. Workflow şu şekilde hedeflenir:

```yaml
runs-on: [self-hosted, macOS, ARM64, apptrack-ios]
```

> **Preflight kontrolü.** AppTrack build'i tetiklemeden önce **çevrimiçi bir runner
> var mı** diye kontrol eder. Yoksa build **hemen net bir hatayla** başarısız olur —
> 24 saat boyunca kuyrukta beklemez. Bu sayede Mac'in kapalıyken build'lerin
> takılıp kalmaz.

## 5. PAT izni notu

AppTrack'in runner'ları **listeleyip preflight** yapabilmesi için token'ın uygun izne
sahip olmalı:

- **Fine-grained PAT:** `Administration` → **read** izni.
- **Klasik PAT:** `repo` scope.

İzin yoksa AppTrack preflight adımını **atlar** (runner listelenemez), ancak build yine
de denenir — bu durumda runner offline'sa hatayı build sırasında görürsün.

## 6. Güvenlik ⚠️

> **Self-hosted runner'ı ASLA public repo'da kullanma.**
>
> GitHub'ın resmî uyarısı: public repo'ya gelen **fork PR'ları**, senin runner
> makinende **keyfi kod çalıştırabilir** ve makinedeki **secret'lara / dosyalara**
> erişebilir. Bu, kişisel Mac'in için ciddi bir risktir.

Kurallar:

- **Private repo kullan.** AppTrack açık kaynak paketi de zaten private repo akışına
  göre tasarlanmıştır.
- Public repo şart ise:
  - Fork PR'ları için **manuel onay** (workflow approval) zorunlu kıl.
  - **Ephemeral runner** kullan — her işten sonra kendini kayıttan düşürür, böylece
    bir iş bir sonrakine sızıntı yapamaz:

    ```bash
    ./config.sh --url https://github.com/OWNER/REPO --token <TOKEN> --ephemeral
    ```

## 7. Ücret notu

- Self-hosted runner **dakikaları şu an ücretsizdir** (GitHub Actions dakika kotasına
  saymaz).
- GitHub'ın **1 Mart 2026** için planladığı dakika-başı **"cloud platform charge"**
  denemesi **ERTELENDİ ama iptal edilmedi**. Gelecekte **private repo** self-hosted
  dakikaları için ücret gelebilir.
- **Public repo** self-hosted runner kullanımı ücretsiz kalmaya devam ediyor (ama
  yukarıdaki güvenlik uyarısı nedeniyle yine de önerilmez).

## 8. Sorun giderme

Runner **offline** görünüyorsa sırayla kontrol et:

- **Süreç çalışıyor mu?** `./run.sh` (veya `./svc.sh status`) aktif mi? Mac uyku
  modunda / kapalı olabilir.
- **Label'lar eşleşiyor mu?** GitHub'daki runner label'ları ile AppTrack Build Runner
  ayarındaki label birebir aynı mı? Büyük/küçük harfe dikkat (`macOS`, `ARM64`).
- **Xcode sürümü yeterli mi?**

  ```bash
  xcodebuild -version   # 26.x olmalı; değilse App Store Connect upload'ı reddeder
  ```

- Runner'ı GitHub API'den doğrula:

  ```bash
  gh api repos/OWNER/REPO/actions/runners \
    --jq '.runners[] | {name, status, labels: [.labels[].name]}'
  ```

## Kaynaklar

- Self-hosted runner'ı workflow'da kullanma —
  https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/use-in-a-workflow
- Self-hosted runner referansı —
  https://docs.github.com/en/actions/reference/runners/self-hosted-runners
- Güvenli kullanım (fork PR / secret riski) —
  https://docs.github.com/en/actions/reference/security/secure-use
- Apple — yaklaşan gereksinimler (iOS 26 SDK / Xcode 26 zorunluluğu) —
  https://developer.apple.com/news/upcoming-requirements/?id=02032026a
