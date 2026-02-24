const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, LevelFormat, ExternalHyperlink,
} = require('docx');
const fs = require('fs');
const path = require('path');

// ── Helpers ────────────────────────────────────────────────────────────────
const BLUE   = '1E3A5F';
const LBLUE  = '2B6CB0';
const BGBLUE = 'EBF4FF';
const BGGREEN= 'F0FFF4';
const BGGRAY = 'F7FAFC';
const BORDER_GRAY = 'CBD5E0';
const WHITE  = 'FFFFFF';
const PAGE_W = 11906;
const PAGE_H = 16838;
const MARGIN = 1134; // ~2 cm
const BODY_W = PAGE_W - MARGIN * 2; // printable width

const border = (color = BORDER_GRAY) => ({
  top: { style: BorderStyle.SINGLE, size: 4, color },
  bottom: { style: BorderStyle.SINGLE, size: 4, color },
  left: { style: BorderStyle.SINGLE, size: 4, color },
  right: { style: BorderStyle.SINGLE, size: 4, color },
});

const noBorder = () => ({
  top: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  bottom: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
});

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 120 },
    children: [new TextRun({ text, bold: true, size: 36, color: BLUE, font: 'Calibri' })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 80 },
    children: [new TextRun({ text, bold: true, size: 28, color: LBLUE, font: 'Calibri' })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 200, after: 60 },
    children: [new TextRun({ text, bold: true, size: 24, color: '2D3748', font: 'Calibri' })],
  });
}

function para(runs, spacing = { before: 60, after: 60 }) {
  return new Paragraph({ children: runs, spacing });
}

function txt(text, opts = {}) {
  return new TextRun({ text, font: 'Calibri', size: 22, ...opts });
}

function mono(text, opts = {}) {
  return new TextRun({ text, font: 'Courier New', size: 20, ...opts });
}

function bullet(text, bold = false) {
  return new Paragraph({
    numbering: { reference: 'bullet', level: 0 },
    spacing: { before: 40, after: 40 },
    children: [txt(text, { bold })],
  });
}

function step(num, text) {
  return new Paragraph({
    numbering: { reference: 'steps', level: 0 },
    spacing: { before: 60, after: 60 },
    children: [txt(text)],
  });
}

function spacer(pts = 120) {
  return new Paragraph({ children: [new TextRun('')], spacing: { before: 0, after: pts } });
}

function codeBlock(lines) {
  const rows = lines.map(line =>
    new TableRow({
      children: [
        new TableCell({
          borders: noBorder(),
          width: { size: BODY_W - 240, type: WidthType.DXA },
          margins: { top: 40, bottom: 40, left: 160, right: 160 },
          children: [new Paragraph({ children: [mono(line, { color: '1A202C' })] })],
        }),
      ],
    })
  );
  return new Table({
    width: { size: BODY_W, type: WidthType.DXA },
    columnWidths: [BODY_W],
    rows,
    margins: { top: 80, bottom: 80, left: 0, right: 0 },
    borders: border('B2BFCC'),
    shading: { fill: 'EDF2F7', type: ShadingType.CLEAR },
  });
}

function infoBox(text, fillColor = BGBLUE) {
  return new Table({
    width: { size: BODY_W, type: WidthType.DXA },
    columnWidths: [BODY_W],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            borders: border(LBLUE),
            shading: { fill: fillColor, type: ShadingType.CLEAR },
            margins: { top: 100, bottom: 100, left: 160, right: 160 },
            children: [new Paragraph({ children: [txt(text, { color: '2B4B7E' })] })],
          }),
        ],
      }),
    ],
  });
}

function summaryTable(rows) {
  const COL = [2600, 2800, 5506];
  const headerRow = new TableRow({
    tableHeader: true,
    children: [
      ['Ayar Kartı', 'Alan Adı', 'Nereden Alınır'].map((h, i) =>
        new TableCell({
          borders: border(LBLUE),
          shading: { fill: BLUE, type: ShadingType.CLEAR },
          width: { size: COL[i], type: WidthType.DXA },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [txt(h, { bold: true, color: WHITE })] })],
        })
      ),
    ],
  });

  const dataRows = rows.map((r, idx) =>
    new TableRow({
      children: r.map((cell, i) =>
        new TableCell({
          borders: border(BORDER_GRAY),
          shading: { fill: idx % 2 === 0 ? BGGRAY : WHITE, type: ShadingType.CLEAR },
          width: { size: COL[i], type: WidthType.DXA },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [i === 1 ? mono(cell, { size: 18 }) : txt(cell, { size: 20 })] })],
        })
      ),
    })
  );

  return new Table({
    width: { size: BODY_W, type: WidthType.DXA },
    columnWidths: COL,
    rows: [headerRow, ...dataRows],
  });
}

// ── Document ───────────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      {
        reference: 'bullet',
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: '\u2022',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 560, hanging: 280 } } },
        }],
      },
      {
        reference: 'steps',
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: '%1.',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 640, hanging: 360 } } },
        }],
      },
    ],
  },
  styles: {
    default: { document: { run: { font: 'Calibri', size: 22 } } },
    paragraphStyles: [
      {
        id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, color: BLUE, font: 'Calibri' },
        paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 },
      },
      {
        id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, color: LBLUE, font: 'Calibri' },
        paragraph: { spacing: { before: 280, after: 80 }, outlineLevel: 1 },
      },
      {
        id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, color: '2D3748', font: 'Calibri' },
        paragraph: { spacing: { before: 200, after: 60 }, outlineLevel: 2 },
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: BORDER_GRAY } },
              alignment: AlignmentType.RIGHT,
              children: [txt('AppTrack — Credential Yönetimi Rehberi', { size: 18, color: '718096' })],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              border: { top: { style: BorderStyle.SINGLE, size: 4, color: BORDER_GRAY } },
              alignment: AlignmentType.CENTER,
              children: [
                txt('Sayfa ', { size: 18, color: '718096' }),
                new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '718096', font: 'Calibri' }),
                txt(' / ', { size: 18, color: '718096' }),
                new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: '718096', font: 'Calibri' }),
              ],
            }),
          ],
        }),
      },
      children: [

        // ── KAPAK ──────────────────────────────────────────────────────
        spacer(720),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 120 },
          children: [new TextRun({ text: 'AppTrack', bold: true, size: 72, color: BLUE, font: 'Calibri' })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 60 },
          children: [txt('Mobil Uygulama Yayın Otomasyon Platformu', { size: 28, color: '4A5568' })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 480 },
          children: [new TextRun({ text: 'Credential Yönetimi — Kullanıcı Rehberi', bold: true, size: 32, color: LBLUE, font: 'Calibri' })],
        }),
        new Table({
          width: { size: BODY_W, type: WidthType.DXA },
          columnWidths: [BODY_W],
          rows: [new TableRow({ children: [new TableCell({
            borders: border(LBLUE),
            shading: { fill: BGBLUE, type: ShadingType.CLEAR },
            margins: { top: 200, bottom: 200, left: 300, right: 300 },
            children: [
              new Paragraph({ alignment: AlignmentType.CENTER, children: [txt('Bu doküman, AppTrack platformunda build ve store deployment için gerekli API anahtarlarının Settings sayfasından nasıl girileceğini ve nereden alınacağını açıklar.', { size: 22, color: '2B4B7E' })] }),
            ],
          })]})]
        }),
        spacer(240),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [txt('Sürüm: 1.0  •  Şubat 2026', { size: 20, color: '718096' })],
        }),

        // ── SAYFA SONU ─────────────────────────────────────────────────
        new Paragraph({ children: [new PageBreak()] }),

        // ── 1. GENEL BAKIŞ ─────────────────────────────────────────────
        h1('1. Genel Bakış'),
        para([txt('AppTrack platformu, mobil uygulamalarınızı GitHub reposundan alarak otomatik olarak derleme (build) yapar ve doğrudan uygulama mağazalarına yükler. Bu işlemin gerçekleşebilmesi için kullanıcının ilgili servis sağlayıcılarına ait API anahtarlarını platformda tanımlaması gerekir.')]),
        spacer(80),
        h2('Settings Sayfasına Erişim'),
        para([txt('Menüden '), txt('Settings', { bold: true }), txt(' sayfasına gidin:')]),
        codeBlock(['http://localhost:3000/settings']),
        spacer(80),
        para([txt('Sayfada iki bölüm yer alır:')]),
        bullet('GitHub Connection — GitHub hesabı bağlama'),
        bullet('Build Providers — Build ve store credential\'ları'),
        spacer(120),
        infoBox('Güvenlik Notu: Girdiğiniz tüm anahtarlar AES şifrelemesi (Fernet) ile veritabanında saklanır. Anahtarların ham değerleri hiçbir zaman görüntülenmez veya loglanmaz.', BGGREEN),
        spacer(160),

        // ── 2. CREDENTIAL KARTLARI ─────────────────────────────────────
        h1('2. Credential Kartları'),

        // ── 2.1 Expo EAS ───────────────────────────────────────────────
        h2('2.1  Expo EAS — React Native / Expo Projeleri'),
        para([txt('Bu kart doldurul madığında, Expo/React Native projeleri için build '), txt('simüle', { bold: true }), txt(' edilir (gerçek binary üretilmez).')]),
        spacer(80),
        h3('EAS Access Token'),
        para([txt('Expo API üzerinden doğrulama için kullanılır. Her build isteğinde EAS API\'ye bu token ile giriş yapılır.')]),
        spacer(60),
        para([txt('Nasıl alınır:', { bold: true })]),
        step(1, 'https://expo.dev adresine giriş yapın.'),
        step(2, 'Sağ üst köşeden profil fotoğrafınıza tıklayın → Access Tokens.'),
        step(3, '"Create Token" butonuna tıklayın.'),
        step(4, 'Token\'a bir isim verin (ör: apptrack-prod) → "Create" tıklayın.'),
        step(5, 'Oluşturulan token\'ı kopyalayın ve Settings sayfasına yapıştırın.'),
        spacer(80),
        codeBlock(['Örnek format: eas_AbCdEfGhIjKlMnOpQrStUvWxYz']),
        spacer(120),
        infoBox('Token yalnızca bir kez gösterilir. Kopyaladıktan sonra sayfayı kapatmadan önce Settings\'e kaydettiğinizden emin olun.'),
        spacer(120),

        h3('Expo App ID'),
        para([txt('EAS\'a hangi projeye build tetikleneceğini bildiren benzersiz proje kimliğidir.')]),
        spacer(60),
        para([txt('Nasıl alınır:', { bold: true })]),
        step(1, 'https://expo.dev → sol menüden Projects sekmesine gidin.'),
        step(2, 'İlgili projenin üzerine tıklayın.'),
        step(3, 'Tarayıcı URL\'inde UUID formatında App ID görünür:'),
        spacer(40),
        codeBlock([
          'https://expo.dev/accounts/KULLANICI_ADI/projects/PROJE_ADI',
          '                                                  ↑',
          'Proje sayfası > Proje ayarları > Project ID alanından da alınabilir.',
          '',
          'Örnek: a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        ]),
        spacer(160),

        // ── 2.2 Codemagic ──────────────────────────────────────────────
        h2('2.2  Codemagic — Flutter Projeleri'),
        para([txt('Flutter projeleri için Codemagic CI/CD platformunu kullanır. Her iki alan da doldurulmadan gerçek build başlatılamaz.')]),
        spacer(80),

        h3('API Access Token'),
        para([txt('Codemagic REST API\'ye kimlik doğrulama için kullanılır.')]),
        spacer(60),
        para([txt('Nasıl alınır:', { bold: true })]),
        step(1, 'https://codemagic.io adresine giriş yapın.'),
        step(2, 'Sağ üst → Teams → Personal Account seçin.'),
        step(3, 'Integrations sekmesine gidin.'),
        step(4, '"Codemagic API" satırındaki "Show" butonuna tıklayın.'),
        step(5, 'Görünen token\'ı kopyalayıp Settings\'e yapıştırın.'),
        spacer(80),
        codeBlock(['Örnek format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx']),
        spacer(120),

        h3('App ID'),
        para([txt('Codemagic\'te kayıtlı uygulamanın kimliğidir. Build tetiklendiğinde hangi workflow\'un çalışacağını belirler.')]),
        spacer(60),
        para([txt('Nasıl alınır:', { bold: true })]),
        step(1, 'Codemagic panelinde ilgili uygulamayı açın.'),
        step(2, 'Tarayıcı URL\'inden ID\'yi kopyalayın:'),
        spacer(40),
        codeBlock([
          'https://codemagic.io/app/64a1b2c3d4e5f6a7b8c9d0e1/...',
          '                         ↑──────────────────────────',
          '                         Bu kısım App ID\'dir',
          '',
          'Örnek: 64a1b2c3d4e5f6a7b8c9d0e1',
        ]),
        spacer(160),

        // ── SAYFA SONU ─────────────────────────────────────────────────
        new Paragraph({ children: [new PageBreak()] }),

        // ── 2.3 Google Play ────────────────────────────────────────────
        h2('2.3  Google Play — Android APK / AAB Yükleme'),
        para([txt('Android uygulamalarını Google Play Store\'a yüklemek için Google Cloud üzerinde bir service account oluşturulmalı ve JSON anahtarı platforma tanımlanmalıdır.')]),
        spacer(80),

        h3('Service Account Key (JSON)'),
        para([txt('Google Play Developer API\'ye erişim için service account kimlik bilgilerini içeren JSON dosyasıdır.')]),
        spacer(80),

        para([txt('ADIM 1 — Google Cloud\'da Service Account oluşturun:', { bold: true })]),
        step(1, 'https://console.cloud.google.com adresine gidin.'),
        step(2, 'Projenizi seçin (veya yeni proje oluşturun).'),
        step(3, 'Sol menü → IAM & Admin → Service Accounts.'),
        step(4, '"Create Service Account" tıklayın.'),
        step(5, 'İsim girin (ör: apptrack-deploy) → Create and Continue.'),
        step(6, 'Role seçin: "Service Account Token Creator" → Done.'),
        spacer(100),

        para([txt('ADIM 2 — JSON Key indirin:', { bold: true })]),
        step(1, 'Oluşturulan service account\'a tıklayın.'),
        step(2, '"Keys" sekmesi → "Add Key" → "Create new key".'),
        step(3, 'Format: JSON → Create tıklayın.'),
        step(4, 'Dosya otomatik indirilir. Bu dosya sadece bir kez indirilebilir.'),
        spacer(100),

        para([txt('ADIM 3 — Google Play Console\'da izin verin:', { bold: true })]),
        step(1, 'https://play.google.com/console adresine gidin.'),
        step(2, 'Ayarlar → API erişimi sayfasına gidin.'),
        step(3, 'Service account e-postasını bulun → "Grant access".'),
        step(4, 'Yetki: "Release to production, exclude devices, and use Play App Signing" seçin.'),
        spacer(100),

        para([txt('ADIM 4 — JSON içeriğini Settings\'e yapıştırın:', { bold: true })]),
        step(1, 'İndirilen JSON dosyasını metin editörüyle açın.'),
        step(2, 'Tüm içeriği kopyalayın.'),
        step(3, 'Settings sayfasında Google Play kartındaki textarea\'ya yapıştırın.'),
        spacer(80),
        codeBlock([
          '{',
          '  "type": "service_account",',
          '  "project_id": "my-project-123",',
          '  "private_key_id": "abc123...",',
          '  "private_key": "-----BEGIN RSA PRIVATE KEY-----\\n...",',
          '  "client_email": "apptrack-deploy@my-project.iam.gserviceaccount.com",',
          '  ...',
          '}',
        ]),
        spacer(160),

        // ── 2.4 App Store Connect ──────────────────────────────────────
        h2('2.4  App Store Connect — iOS IPA Yükleme'),
        para([txt('iOS uygulamalarını App Store\'a yüklemek için App Store Connect API üç ayrı alan gerektirir: Key ID, Issuer ID ve Private Key.')]),
        spacer(80),

        h3('API Key Oluşturma (Tek Adımda 3 Değer)'),
        para([txt('Nasıl yapılır:', { bold: true })]),
        step(1, 'https://appstoreconnect.apple.com/access/integrations/api adresine gidin.'),
        step(2, '"App Store Connect API" → "Team Keys" sekmesini seçin.'),
        step(3, '"+" butonuna veya "Generate API Key"e tıklayın.'),
        step(4, 'Bir isim girin (ör: apptrack-upload).'),
        step(5, 'Access: "App Manager" seçin → "Generate" tıklayın.'),
        step(6, 'Oluşturulan key satırında 3 değeri toplayın (aşağıdaki tabloya bakın).'),
        spacer(120),

        new Table({
          width: { size: BODY_W, type: WidthType.DXA },
          columnWidths: [2800, 2800, 5306],
          rows: [
            new TableRow({
              tableHeader: true,
              children: [
                ['Settings Alanı', 'App Store\'da Nerede', 'Örnek Format'].map((h, i) =>
                  new TableCell({
                    borders: border(LBLUE),
                    shading: { fill: BLUE, type: ShadingType.CLEAR },
                    width: { size: [2800,2800,5306][i], type: WidthType.DXA },
                    margins: { top: 80, bottom: 80, left: 120, right: 120 },
                    children: [new Paragraph({ children: [txt(h, { bold: true, color: WHITE, size: 20 })] })],
                  })
                ),
              ],
            }),
            ...([
              ['APP_STORE_KEY_ID', '"Key ID" sütunu (tabloda)', 'AB12CD34EF'],
              ['APP_STORE_ISSUER_ID', 'Tablonun üstündeki "Issuer ID"', 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'],
              ['APP_STORE_PRIVATE_KEY', '"Download API Key" → .p8 dosyası içeriği', '-----BEGIN PRIVATE KEY-----\\nMIGH...\\n-----END PRIVATE KEY-----'],
            ].map((r, idx) =>
              new TableRow({
                children: r.map((cell, i) =>
                  new TableCell({
                    borders: border(BORDER_GRAY),
                    shading: { fill: idx % 2 === 0 ? BGGRAY : WHITE, type: ShadingType.CLEAR },
                    width: { size: [2800,2800,5306][i], type: WidthType.DXA },
                    margins: { top: 80, bottom: 80, left: 120, right: 120 },
                    children: [new Paragraph({ children: [i === 0 ? mono(cell, { size: 17 }) : txt(cell, { size: 19 })] })],
                  })
                ),
              })
            )),
          ],
        }),
        spacer(120),

        infoBox('.p8 dosyası yalnızca bir kez indirilebilir. Kaybedilirse mevcut key iptal edilip yeniden oluşturulmalıdır. Private Key alanına dosyanın -----BEGIN PRIVATE KEY----- başlığı dahil tüm içeriği girilmelidir.'),
        spacer(120),

        h3('EAS Submit ile App Store Yükleme'),
        para([txt('Expo/React Native projeleri için, App Store Connect bilgilerine ek olarak EAS Token ve Expo App ID girildiğinde, platform '), txt('EAS Submit API', { bold: true }), txt(' aracılığıyla IPA dosyasını otomatik olarak App Store\'a gönderir.')]),
        spacer(80),
        codeBlock([
          'Deploy akışı (Expo/RN + App Store):',
          '',
          '  EAS_TOKEN       ──┐',
          '  EXPO_APP_ID     ──┤──► EAS Submit API ──► App Store Review',
          '  APP_STORE_KEY_ID──┤        ↑',
          '  APP_STORE_ISSUER──┘   IPA artifact',
        ]),
        spacer(160),

        // ── SAYFA SONU ─────────────────────────────────────────────────
        new Paragraph({ children: [new PageBreak()] }),

        // ── 3. GÜVENLİK ───────────────────────────────────────────────
        h1('3. Güvenlik Mimarisi'),
        para([txt('Credential\'ların güvenli saklanması için aşağıdaki katmanlar uygulanmaktadır:')]),
        spacer(80),

        new Table({
          width: { size: BODY_W, type: WidthType.DXA },
          columnWidths: [3200, 7706],
          rows: [
            new TableRow({
              tableHeader: true,
              children: [
                ['Katman', 'Açıklama'].map((h, i) =>
                  new TableCell({
                    borders: border(LBLUE),
                    shading: { fill: BLUE, type: ShadingType.CLEAR },
                    width: { size: [3200, 7706][i], type: WidthType.DXA },
                    margins: { top: 80, bottom: 80, left: 120, right: 120 },
                    children: [new Paragraph({ children: [txt(h, { bold: true, color: WHITE })] })],
                  })
                ),
              ],
            }),
            ...([
              ['Şifreleme', 'Fernet (AES-128 CBC + HMAC-SHA256). SECRET_KEY\'den türetilir.'],
              ['Transport', 'HTTPS üzerinden iletilir. Plaintext hiç loglanmaz.'],
              ['DB Kaydı', 'Yalnızca şifreli değer (encrypted_value) saklanır. Ham değer asla dönmez.'],
              ['Erişim', 'Yalnızca kendi kullanıcısına ait credential\'lar görüntülenebilir.'],
              ['Kullanım Anı', 'Build/Deploy tetiklendiğinde anlık decrypt → servis → hemen yok edilir.'],
              ['API Response', 'GET /credentials yalnızca id, provider, key_name döner. Değer hiç dönmez.'],
            ].map((r, idx) =>
              new TableRow({
                children: r.map((cell, i) =>
                  new TableCell({
                    borders: border(BORDER_GRAY),
                    shading: { fill: idx % 2 === 0 ? BGGRAY : WHITE, type: ShadingType.CLEAR },
                    width: { size: [3200, 7706][i], type: WidthType.DXA },
                    margins: { top: 80, bottom: 80, left: 120, right: 120 },
                    children: [new Paragraph({ children: [txt(cell, { size: 20, bold: i === 0 })] })],
                  })
                ),
              })
            )),
          ],
        }),
        spacer(160),

        // ── 4. ÖZET TABLO ──────────────────────────────────────────────
        h1('4. Özet — Tüm Credential\'lar'),
        para([txt('Aşağıdaki tablo, Settings sayfasındaki tüm alanları ve nereden alınacağını özetler:')]),
        spacer(80),
        summaryTable([
          ['Expo EAS',       'EAS_TOKEN',                'expo.dev → Profil → Access Tokens'],
          ['Expo EAS',       'EXPO_APP_ID',              'expo.dev → Projects → Proje URL UUID'],
          ['Codemagic',      'CODEMAGIC_TOKEN',          'codemagic.io → Teams → Integrations → API → Show'],
          ['Codemagic',      'CODEMAGIC_APP_ID',         'codemagic.io → Uygulama URL\'indeki ID'],
          ['Google Play',    'GOOGLE_PLAY_KEY_JSON',     'Google Cloud Console → Service Account → JSON Key'],
          ['App Store',      'APP_STORE_KEY_ID',         'appstoreconnect.apple.com → Integrations → API'],
          ['App Store',      'APP_STORE_ISSUER_ID',      'Aynı sayfa → Tablonun üstündeki Issuer ID'],
          ['App Store',      'APP_STORE_PRIVATE_KEY',    'İndirilen .p8 dosyasının tam içeriği'],
        ]),
        spacer(160),

        // ── 5. SIKÇA SORULAN SORULAR ───────────────────────────────────
        h1('5. Sıkça Sorulan Sorular'),

        h3('Credential girmeden build çalışır mı?'),
        para([txt('Evet, '), txt('simülasyon', { bold: true }), txt(' modunda çalışır. Gerçek binary üretilmez; test akışını doğrulamak için kullanılabilir. Gerçek APK/IPA almak için ilgili provider\'ın credential\'ları girilmiş olmalıdır.')]),
        spacer(80),

        h3('Bir credential\'ı nasıl güncellerim?'),
        para([txt('Settings sayfasında ilgili alana yeni değeri girin ve "Save" butonuna tıklayın. Önceki şifreli değer üzerine yazılır.')]),
        spacer(80),

        h3('Credential\'ı nasıl silerim?'),
        para([txt('Kaydedilmiş alan yanındaki '), txt('çöp kutusu ikonuna', { bold: true }), txt(' tıklayın. Onay sonrası veritabanından kalıcı olarak silinir.')]),
        spacer(80),

        h3('.p8 dosyasını kaybettim, ne yapmalıyım?'),
        para([txt('App Store Connect\'te mevcut key\'i '), txt('Revoke', { bold: true }), txt(' edin, ardından yeni bir key oluşturun. Yeni Key ID, Issuer ID ve Private Key değerlerini tekrar Settings sayfasına girin.')]),
        spacer(80),

        h3('Google Play JSON key\'im çalışmıyor, neden?'),
        para([txt('En yaygın nedenler:')]),
        bullet('Google Play Console\'da service account\'a yeterli izin verilmemiş'),
        bullet('"Google Play Android Developer API" Google Cloud\'da enable edilmemiş'),
        bullet('JSON dosyasını yanlış yapıştırma (eksik süslü parantez vs.)'),
        bullet('Paket adı (package_name) deploy sırasında yanlış girilmiş'),
        spacer(160),

        // ── SON ────────────────────────────────────────────────────────
        new Table({
          width: { size: BODY_W, type: WidthType.DXA },
          columnWidths: [BODY_W],
          rows: [new TableRow({ children: [new TableCell({
            borders: border(LBLUE),
            shading: { fill: BGBLUE, type: ShadingType.CLEAR },
            margins: { top: 160, bottom: 160, left: 300, right: 300 },
            children: [
              new Paragraph({ alignment: AlignmentType.CENTER, children: [txt('AppTrack — Mobil Uygulama Yayın Otomasyon Platformu', { bold: true, color: BLUE, size: 24 })] }),
              spacer(40),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [txt('Bu doküman proje kaynak kodunun docs/ klasöründe saklanmaktadır.', { size: 20, color: '4A5568' })] }),
            ],
          })]})]
        }),
      ],
    },
  ],
});

const outPath = path.join(__dirname, '..', 'docs', 'credential-yonetimi-rehberi.docx');
const docsDir = path.join(__dirname, '..', 'docs');
if (!fs.existsSync(docsDir)) fs.mkdirSync(docsDir, { recursive: true });

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log('OK:' + outPath);
}).catch(err => {
  console.error('ERROR:', err.message);
  process.exit(1);
});
