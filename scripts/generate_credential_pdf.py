# -*- coding: utf-8 -*-
import os
import unicodedata
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate

# ── FONTS ────────────────────────────────────────────────────────────────────
FONTS_DIR = r"C:\Windows\Fonts"
pdfmetrics.registerFont(TTFont("Arial",     os.path.join(FONTS_DIR, "arial.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Bold",os.path.join(FONTS_DIR, "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Italic",os.path.join(FONTS_DIR, "ariali.ttf")))
pdfmetrics.registerFont(TTFont("CourierNew",os.path.join(FONTS_DIR, "cour.ttf")))
pdfmetrics.registerFont(TTFont("CourierNew-Bold",os.path.join(FONTS_DIR, "courbd.ttf")))

# ── COLORS ───────────────────────────────────────────────────────────────────
C_BLUE_DARK  = colors.HexColor("#1E3A5F")
C_BLUE       = colors.HexColor("#2B6CB0")
C_BLUE_LIGHT = colors.HexColor("#EBF4FF")
C_GREEN_LIGHT= colors.HexColor("#F0FFF4")
C_GREEN      = colors.HexColor("#276749")
C_GRAY_BG    = colors.HexColor("#F7FAFC")
C_GRAY_BORDER= colors.HexColor("#CBD5E0")
C_GRAY_TEXT  = colors.HexColor("#4A5568")
C_DARK_TEXT  = colors.HexColor("#1A202C")
C_WHITE      = colors.white
C_ROW_ALT    = colors.HexColor("#EDF2F7")
C_AMBER_LIGHT= colors.HexColor("#FFFBEB")
C_AMBER      = colors.HexColor("#B7791F")

PAGE_W, PAGE_H = A4
MARGIN = 2.2 * cm
BODY_W = PAGE_W - 2 * MARGIN

def nfc(s):
    return unicodedata.normalize("NFC", s)

# ── STYLES ───────────────────────────────────────────────────────────────────
def styles():
    return {
        "cover_title": ParagraphStyle("cover_title",
            fontName="Arial-Bold", fontSize=36, textColor=C_BLUE_DARK,
            spaceAfter=8, leading=44, alignment=1),
        "cover_sub": ParagraphStyle("cover_sub",
            fontName="Arial", fontSize=15, textColor=C_GRAY_TEXT,
            spaceAfter=6, leading=22, alignment=1),
        "cover_tag": ParagraphStyle("cover_tag",
            fontName="Arial-Bold", fontSize=18, textColor=C_BLUE,
            spaceAfter=4, leading=26, alignment=1),
        "cover_ver": ParagraphStyle("cover_ver",
            fontName="Arial", fontSize=11, textColor=C_GRAY_TEXT,
            spaceAfter=0, leading=16, alignment=1),
        "h1": ParagraphStyle("h1",
            fontName="Arial-Bold", fontSize=18, textColor=C_BLUE_DARK,
            spaceBefore=18, spaceAfter=6, leading=24),
        "h2": ParagraphStyle("h2",
            fontName="Arial-Bold", fontSize=14, textColor=C_BLUE,
            spaceBefore=14, spaceAfter=5, leading=20),
        "h3": ParagraphStyle("h3",
            fontName="Arial-Bold", fontSize=12, textColor=C_DARK_TEXT,
            spaceBefore=10, spaceAfter=4, leading=17),
        "body": ParagraphStyle("body",
            fontName="Arial", fontSize=11, textColor=C_DARK_TEXT,
            spaceBefore=3, spaceAfter=4, leading=17),
        "bullet": ParagraphStyle("bullet",
            fontName="Arial", fontSize=11, textColor=C_DARK_TEXT,
            spaceBefore=2, spaceAfter=2, leading=16,
            leftIndent=18, bulletIndent=6),
        "step": ParagraphStyle("step",
            fontName="Arial", fontSize=11, textColor=C_DARK_TEXT,
            spaceBefore=3, spaceAfter=3, leading=16,
            leftIndent=24),
        "code": ParagraphStyle("code",
            fontName="CourierNew", fontSize=9.5, textColor=C_DARK_TEXT,
            spaceBefore=1, spaceAfter=1, leading=14),
        "info_text": ParagraphStyle("info_text",
            fontName="Arial", fontSize=10.5, textColor=colors.HexColor("#2B4B7E"),
            spaceBefore=2, spaceAfter=2, leading=15),
        "warn_text": ParagraphStyle("warn_text",
            fontName="Arial-Bold", fontSize=10.5, textColor=C_AMBER,
            spaceBefore=2, spaceAfter=2, leading=15),
        "table_hdr": ParagraphStyle("table_hdr",
            fontName="Arial-Bold", fontSize=10, textColor=C_WHITE,
            spaceBefore=0, spaceAfter=0, leading=14),
        "table_cell": ParagraphStyle("table_cell",
            fontName="Arial", fontSize=10, textColor=C_DARK_TEXT,
            spaceBefore=0, spaceAfter=0, leading=14),
        "table_mono": ParagraphStyle("table_mono",
            fontName="CourierNew", fontSize=9, textColor=C_DARK_TEXT,
            spaceBefore=0, spaceAfter=0, leading=13),
        "footer": ParagraphStyle("footer",
            fontName="Arial", fontSize=9, textColor=C_GRAY_TEXT,
            alignment=1, leading=12),
    }

S = styles()

# ── HELPERS ──────────────────────────────────────────────────────────────────
def sp(h=0.3):
    return Spacer(1, h * cm)

def hr():
    return HRFlowable(width="100%", thickness=0.5, color=C_GRAY_BORDER, spaceAfter=4, spaceBefore=4)

def h1(text):
    return Paragraph(nfc(text), S["h1"])

def h2(text):
    return Paragraph(nfc(text), S["h2"])

def h3(text):
    return Paragraph(nfc(text), S["h3"])

def body(text):
    return Paragraph(nfc(text), S["body"])

def bullet_item(text):
    return Paragraph(nfc(f"\u2022  {text}"), S["bullet"])

def step_item(num, text):
    return Paragraph(nfc(f"<b>{num}.</b>  {text}"), S["step"])

def info_box(text, bg=C_BLUE_LIGHT, border_color=C_BLUE, style_key="info_text"):
    data = [[Paragraph(nfc(text), S[style_key])]]
    t = Table(data, colWidths=[BODY_W - 0.4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("BOX",        (0,0), (-1,-1), 1.2, border_color),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING",   (0,0), (-1,-1), 14),
        ("RIGHTPADDING",  (0,0), (-1,-1), 14),
    ]))
    return t

def warn_box(text):
    return info_box(
        f"\u26a0\ufe0f  {text}",
        bg=C_AMBER_LIGHT, border_color=C_AMBER, style_key="warn_text"
    )

def code_block(lines):
    cells = [[Paragraph(nfc(line), S["code"])] for line in lines]
    t = Table(cells, colWidths=[BODY_W - 0.4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_ROW_ALT),
        ("BOX",        (0,0), (-1,-1), 0.8, C_GRAY_BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("RIGHTPADDING",  (0,0), (-1,-1), 12),
    ]))
    return t

def section_rule():
    return HRFlowable(width="100%", thickness=1.5, color=C_BLUE, spaceAfter=6, spaceBefore=2)

# ── HEADER / FOOTER ──────────────────────────────────────────────────────────
class DocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kw):
        BaseDocTemplate.__init__(self, filename, **kw)
        frame = Frame(MARGIN, MARGIN + 1*cm, BODY_W, PAGE_H - 2*MARGIN - 1.6*cm, id="main")
        template = PageTemplate(id="main", frames=[frame], onPage=self._on_page)
        self.addPageTemplates([template])

    def _on_page(self, canvas, doc):
        canvas.saveState()
        # Header
        canvas.setFont("Arial-Bold", 8.5)
        canvas.setFillColor(C_GRAY_TEXT)
        canvas.drawString(MARGIN, PAGE_H - MARGIN + 4, "AppTrack  —  Credential Yonetimi Rehberi")
        canvas.setStrokeColor(C_GRAY_BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, PAGE_H - MARGIN, PAGE_W - MARGIN, PAGE_H - MARGIN)
        # Footer
        canvas.line(MARGIN, MARGIN + 0.7*cm, PAGE_W - MARGIN, MARGIN + 0.7*cm)
        canvas.setFont("Arial", 8.5)
        canvas.drawCentredString(PAGE_W / 2, MARGIN + 0.2*cm, f"Sayfa {doc.page}")
        canvas.restoreState()

# ── COVER PAGE ───────────────────────────────────────────────────────────────
def cover_page():
    items = []
    items.append(sp(3.5))
    # App name
    items.append(Paragraph("AppTrack", S["cover_title"]))
    items.append(sp(0.3))
    items.append(Paragraph(nfc("Mobil Uygulama Yayin Otomasyon Platformu"), S["cover_sub"]))
    items.append(sp(1.5))

    # Title box
    title_data = [[Paragraph(nfc("Credential Yonetimi — Kullanici Rehberi"), S["cover_tag"])]]
    title_tbl = Table(title_data, colWidths=[BODY_W])
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_BLUE_DARK),
        ("TOPPADDING",    (0,0), (-1,-1), 16),
        ("BOTTOMPADDING", (0,0), (-1,-1), 16),
        ("LEFTPADDING",   (0,0), (-1,-1), 20),
        ("RIGHTPADDING",  (0,0), (-1,-1), 20),
        ("BOX",           (0,0), (-1,-1), 0, C_BLUE_DARK),
        ("ROUNDEDCORNERS", [4]),
    ]))
    items.append(title_tbl)
    items.append(sp(1.5))

    desc_data = [[Paragraph(
        nfc("Bu dokuman, AppTrack platformunda build ve store deployment icin gerekli "
            "API anahtarlarinin Settings sayfasindan nasil girileceğini ve nereden "
            "alinacagini adim adim aciklar."),
        ParagraphStyle("cover_desc", fontName="Arial", fontSize=12, textColor=colors.HexColor("#2B4B7E"),
                       leading=19, alignment=1)
    )]]
    desc_tbl = Table(desc_data, colWidths=[BODY_W])
    desc_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_BLUE_LIGHT),
        ("BOX",        (0,0), (-1,-1), 1.2, C_BLUE),
        ("TOPPADDING",    (0,0), (-1,-1), 20),
        ("BOTTOMPADDING", (0,0), (-1,-1), 20),
        ("LEFTPADDING",   (0,0), (-1,-1), 24),
        ("RIGHTPADDING",  (0,0), (-1,-1), 24),
    ]))
    items.append(desc_tbl)
    items.append(sp(2))

    meta = [
        ["Surum",   "1.0"],
        ["Tarih",   "Subat 2026"],
        ["Proje",   "AppTrack Platform"],
        ["Konum",   "docs/credential-yonetimi-rehberi.pdf"],
    ]
    meta_tbl = Table(meta, colWidths=[3.5*cm, BODY_W - 3.5*cm])
    meta_tbl.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (0,-1), "Arial-Bold"),
        ("FONTNAME",  (1,0), (1,-1), "Arial"),
        ("FONTSIZE",  (0,0), (-1,-1), 10.5),
        ("TEXTCOLOR", (0,0), (-1,-1), C_GRAY_TEXT),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LINEBEFORE", (1,0), (1,-1), 1, C_GRAY_BORDER),
        ("LEFTPADDING", (1,0), (1,-1), 10),
    ]))
    items.append(meta_tbl)
    items.append(PageBreak())
    return items

# ── SECTION 1 — GENEL BAKIS ──────────────────────────────────────────────────
def section_genel_bakis():
    items = []
    items += [h1("1.  Genel Bakis"), section_rule(), sp(0.2)]
    items.append(body(
        "AppTrack platformu, mobil uygulamalarinizi GitHub reposundan alarak otomatik olarak derleme (build) yapar "
        "ve dogrudan uygulama magazalarina yukler. Bu islemin gerceklesebilmesi icin kullanicinin ilgili servis "
        "saglayicilarinа ait API anahtarlarini platformda tanimlamasi gerekir."
    ))
    items.append(sp(0.4))
    items += [h2("Settings Sayfasina Erisim"), sp(0.1)]
    items.append(body("Menudan Settings sayfasina gidin:"))
    items.append(code_block(["http://localhost:3000/settings"]))
    items.append(sp(0.3))
    items.append(body("Sayfada iki ana bolum bulunur:"))
    items.append(bullet_item("GitHub Connection  —  GitHub hesabi baglama"))
    items.append(bullet_item("Build Providers  —  Build ve store credential'lari"))
    items.append(sp(0.5))
    items.append(info_box(
        nfc("Guvenlik Notu:  Girdiginiz tum anahtarlar AES sifreleme (Fernet) ile veritabaninda saklanir. "
            "Anahtarlarin ham degerleri hicbir zaman goruntulenmez veya loglanmaz.")
    ))
    items.append(sp(0.4))
    return items

# ── SECTION 2.1 — EXPO EAS ───────────────────────────────────────────────────
def section_eas():
    items = []
    items += [h2("2.1   Expo EAS  —  React Native / Expo Projeleri"), sp(0.1)]
    items.append(body(
        "Bu kart doldurulmadığında, Expo/React Native projeleri icin build simule edilir "
        "(gercek binary uretilmez)."
    ))
    items.append(sp(0.3))

    # EAS Token
    items += [h3("EAS Access Token"), sp(0.1)]
    items.append(body("Expo API uzerinden dogrulama icin kullanilir. Her build isteğinde EAS API'ye bu token ile giris yapilir."))
    items.append(sp(0.2))
    for num, txt in [
        (1, "https://expo.dev adresine giris yapin."),
        (2, "Sag ust koseden profil fotografiniza tiklayin  >  Access Tokens."),
        (3, '"Create Token" butonuna tiklayin.'),
        (4, "Token'a bir isim verin (orn: apptrack-prod)  >  Create tiklayin."),
        (5, "Olusturulan token'i kopyalayin ve Settings sayfasina yapistirin."),
    ]:
        items.append(step_item(num, txt))
    items.append(sp(0.2))
    items.append(code_block(["Ornek format:  eas_AbCdEfGhIjKlMnOpQrStUvWxYz"]))
    items.append(sp(0.3))
    items.append(warn_box("Token yalnizca bir kez gosterilir. Kopyaladiktan sonra sayfayi kapatmadan once Settings'e kaydettiginizden emin olun."))
    items.append(sp(0.4))

    # Expo App ID
    items += [h3("Expo App ID"), sp(0.1)]
    items.append(body("EAS'a hangi projeye build tetiklenecegini bildiren benzersiz proje kimligidir."))
    items.append(sp(0.2))
    for num, txt in [
        (1, "https://expo.dev  >  sol menudan Projects sekmesine gidin."),
        (2, "Ilgili projenin uzerine tiklayin."),
        (3, "Tarayici URL'inde veya proje Ayarlari > Project ID alaninda goruntulenir:"),
    ]:
        items.append(step_item(num, txt))
    items.append(sp(0.2))
    items.append(code_block([
        "https://expo.dev/accounts/KULLANICI_ADI/projects/PROJE_ADI",
        "",
        "Ornek App ID:  a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    ]))
    items.append(sp(0.4))
    return items

# ── SECTION 2.2 — CODEMAGIC ──────────────────────────────────────────────────
def section_codemagic():
    items = []
    items += [h2("2.2   Codemagic  —  Flutter Projeleri"), sp(0.1)]
    items.append(body("Flutter projeleri icin Codemagic CI/CD platformunu kullanir. Her iki alan da doldurulmadan gercek build baslatilamamaz."))
    items.append(sp(0.3))

    items += [h3("API Access Token"), sp(0.1)]
    items.append(body("Codemagic REST API'ye kimlik dogrulama icin kullanilir."))
    items.append(sp(0.2))
    for num, txt in [
        (1, "https://codemagic.io adresine giris yapin."),
        (2, "Sag ust  >  Teams  >  Personal Account secin."),
        (3, "Integrations sekmesine gidin."),
        (4, '"Codemagic API" satirindaki "Show" butonuna tiklayin.'),
        (5, "Gorunen token'i kopyalayip Settings'e yapistirin."),
    ]:
        items.append(step_item(num, txt))
    items.append(sp(0.2))
    items.append(code_block(["Ornek format:  xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"]))
    items.append(sp(0.4))

    items += [h3("App ID"), sp(0.1)]
    items.append(body("Codemagic'te kayitli uygulamanin kimligidir."))
    items.append(sp(0.2))
    for num, txt in [
        (1, "Codemagic panelinde ilgili uygulamayi acin."),
        (2, "Tarayici URL'inden ID'yi kopyalayin:"),
    ]:
        items.append(step_item(num, txt))
    items.append(sp(0.2))
    items.append(code_block([
        "https://codemagic.io/app/64a1b2c3d4e5f6a7b8c9d0e1/...",
        "                         ^^^^^^^^^^^^^^^^^^^^^^^^",
        "                         Bu kisim App ID'dir",
    ]))
    items.append(sp(0.4))
    return items

# ── SECTION 2.3 — GOOGLE PLAY ────────────────────────────────────────────────
def section_google_play():
    items = []
    items += [PageBreak(), h2("2.3   Google Play  —  Android APK / AAB Yukleme"), sp(0.1)]
    items.append(body(
        "Android uygulamalarini Google Play Store'a yuklemek icin Google Cloud uzerinde bir service account "
        "olusturulmali ve JSON anahtari platforma tanimlanmalidir."
    ))
    items.append(sp(0.3))
    items += [h3("Service Account Key (JSON)"), sp(0.1)]
    items.append(body("Google Play Developer API'ye erisim icin service account kimlik bilgilerini iceren JSON dosyasidir."))
    items.append(sp(0.3))

    items.append(Paragraph("<b>ADIM 1 — Google Cloud'da Service Account olusturun:</b>", S["body"]))
    items.append(sp(0.1))
    for num, txt in [
        (1, "https://console.cloud.google.com adresine gidin."),
        (2, "Projenizi secin (veya yeni proje olusturun)."),
        (3, "Sol menu  >  IAM & Admin  >  Service Accounts."),
        (4, '"Create Service Account" tiklayin.'),
        (5, 'Isim girin (orn: apptrack-deploy)  >  Create and Continue.'),
        (6, 'Role secin: "Service Account Token Creator"  >  Done.'),
    ]:
        items.append(step_item(num, txt))
    items.append(sp(0.3))

    items.append(Paragraph("<b>ADIM 2 — JSON Key indirin:</b>", S["body"]))
    items.append(sp(0.1))
    for num, txt in [
        (1, "Olusturulan service account'a tiklayin."),
        (2, '"Keys" sekmesi  >  "Add Key"  >  "Create new key".'),
        (3, "Format: JSON  >  Create tiklayin."),
        (4, "Dosya otomatik indirilir. Bu dosya sadece bir kez indirilebilir."),
    ]:
        items.append(step_item(num, txt))
    items.append(sp(0.3))

    items.append(Paragraph("<b>ADIM 3 — Google Play Console'da izin verin:</b>", S["body"]))
    items.append(sp(0.1))
    for num, txt in [
        (1, "https://play.google.com/console adresine gidin."),
        (2, "Ayarlar  >  API erisimi sayfasina gidin."),
        (3, "Service account e-postasini bulun  >  Grant access."),
        (4, 'Yetki: "Release to production, exclude devices, and use Play App Signing" secin.'),
    ]:
        items.append(step_item(num, txt))
    items.append(sp(0.3))

    items.append(Paragraph("<b>ADIM 4 — JSON icerigini Settings'e yapistirin:</b>", S["body"]))
    items.append(sp(0.1))
    for num, txt in [
        (1, "Indirilen JSON dosyasini metin editoruyle acin."),
        (2, "Tum icerigi kopyalayin."),
        (3, "Settings sayfasinda Google Play kartindaki textarea'ya yapistirin."),
    ]:
        items.append(step_item(num, txt))
    items.append(sp(0.2))
    items.append(code_block([
        "{",
        '  "type": "service_account",',
        '  "project_id": "my-project-123",',
        '  "private_key_id": "abc123...",',
        '  "private_key": "-----BEGIN RSA PRIVATE KEY-----\\n...",',
        '  "client_email": "apptrack-deploy@my-project.iam.gserviceaccount.com",',
        '  ...',
        "}",
    ]))
    items.append(sp(0.4))
    return items

# ── SECTION 2.4 — APP STORE ──────────────────────────────────────────────────
def section_app_store():
    items = []
    items += [h2("2.4   App Store Connect  —  iOS IPA Yukleme"), sp(0.1)]
    items.append(body(
        "iOS uygulamalarini App Store'a yuklemek icin App Store Connect API uc ayri alan gerektirir: "
        "Key ID, Issuer ID ve Private Key."
    ))
    items.append(sp(0.3))
    items += [h3("API Key Olusturma (Tek Adimda 3 Deger)"), sp(0.1)]
    for num, txt in [
        (1, "https://appstoreconnect.apple.com/access/integrations/api adresine gidin."),
        (2, '"App Store Connect API"  >  "Team Keys" sekmesini secin.'),
        (3, '"+" butonuna tiklayin.'),
        (4, 'Bir isim girin (orn: apptrack-upload).'),
        (5, 'Access: "App Manager" secin  >  "Generate" tiklayin.'),
        (6, "Olusturulan key satirindan 3 degeri asagidaki tabloya gore toplayin."),
    ]:
        items.append(step_item(num, txt))
    items.append(sp(0.3))

    tbl_data = [
        [Paragraph("Settings Alani", S["table_hdr"]),
         Paragraph("App Store'da Nerede", S["table_hdr"]),
         Paragraph("Ornek Format", S["table_hdr"])],
        [Paragraph("APP_STORE_KEY_ID",       S["table_mono"]),
         Paragraph('"Key ID" sutunu (tabloda)', S["table_cell"]),
         Paragraph("AB12CD34EF", S["table_mono"])],
        [Paragraph("APP_STORE_ISSUER_ID",    S["table_mono"]),
         Paragraph("Tablonun ustundeki 'Issuer ID'", S["table_cell"]),
         Paragraph("xxxx-xxxx-xxxx-xxxx", S["table_mono"])],
        [Paragraph("APP_STORE_PRIVATE_KEY",  S["table_mono"]),
         Paragraph('"Download API Key"  >  .p8 dosyasi icerigi', S["table_cell"]),
         Paragraph("-----BEGIN PRIVATE KEY-----\\nMIGH...", S["table_mono"])],
    ]
    col_w = [5*cm, 6.5*cm, BODY_W - 11.5*cm]
    tbl = Table(tbl_data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  C_BLUE_DARK),
        ("TEXTCOLOR",     (0,0), (-1,0),  C_WHITE),
        ("BACKGROUND",    (0,1), (-1,1),  C_GRAY_BG),
        ("BACKGROUND",    (0,2), (-1,2),  C_WHITE),
        ("BACKGROUND",    (0,3), (-1,3),  C_GRAY_BG),
        ("BOX",           (0,0), (-1,-1), 0.8, C_GRAY_BORDER),
        ("INNERGRID",     (0,0), (-1,-1), 0.5, C_GRAY_BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    items.append(tbl)
    items.append(sp(0.3))
    items.append(warn_box(
        ".p8 dosyasi yalnizca bir kez indirilebilir. Kaybedilirse mevcut key iptal edilip yeniden olusturulmalidir. "
        "Private Key alanina dosyanin -----BEGIN PRIVATE KEY----- basligi dahil tum icerigi girilmelidir."
    ))
    items.append(sp(0.4))

    items += [h3("EAS Submit ile App Store Yukleme"), sp(0.1)]
    items.append(body(
        "Expo/React Native projeleri icin, App Store Connect bilgilerine ek olarak EAS Token ve Expo App ID "
        "girildiginde, platform EAS Submit API araciligiyla IPA dosyasini otomatik olarak App Store'a gonderir."
    ))
    items.append(sp(0.2))
    items.append(code_block([
        "Deploy akisi (Expo/RN + App Store):",
        "",
        "  EAS_TOKEN        --+",
        "  EXPO_APP_ID      --+--> EAS Submit API --> App Store Review",
        "  APP_STORE_KEY_ID --+          ^",
        "  APP_STORE_ISSUER--+      IPA artifact",
    ]))
    items.append(sp(0.4))
    return items

# ── SECTION 3 — GUVENLIK ─────────────────────────────────────────────────────
def section_guvenlik():
    items = []
    items += [PageBreak(), h1("3.  Guvenlik Mimarisi"), section_rule(), sp(0.2)]
    items.append(body("Credential'larin guvenli saklanmasi icin asagidaki katmanlar uygulanmaktadir:"))
    items.append(sp(0.3))

    rows = [
        [Paragraph("Katman",     S["table_hdr"]), Paragraph("Aciklama", S["table_hdr"])],
        [Paragraph("Sifreleme",  S["table_cell"]),
         Paragraph("Fernet (AES-128 CBC + HMAC-SHA256). SECRET_KEY'den turetilir.", S["table_cell"])],
        [Paragraph("Transport",  S["table_cell"]),
         Paragraph("HTTPS uzerinden iletilir. Plaintext hic loglanmaz.", S["table_cell"])],
        [Paragraph("DB Kaydi",   S["table_cell"]),
         Paragraph("Yalnizca sifrelenmis deger (encrypted_value) saklanir. Ham deger asla donmez.", S["table_cell"])],
        [Paragraph("Erisim",     S["table_cell"]),
         Paragraph("Yalnizca kendi kullanicisina ait credential'lar goruntulenir.", S["table_cell"])],
        [Paragraph("Kullanimda", S["table_cell"]),
         Paragraph("Build/Deploy aninda decrypt  >  servis  >  hemen yok edilir.", S["table_cell"])],
        [Paragraph("API Response",S["table_cell"]),
         Paragraph("GET /credentials yalnizca id, provider, key_name doner. Deger hic donmez.", S["table_cell"])],
    ]
    col_w = [3.2*cm, BODY_W - 3.2*cm]
    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  C_BLUE_DARK),
        ("TEXTCOLOR",     (0,0), (-1,0),  C_WHITE),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_GRAY_BG, C_WHITE]),
        ("BOX",           (0,0), (-1,-1), 0.8, C_GRAY_BORDER),
        ("INNERGRID",     (0,0), (-1,-1), 0.5, C_GRAY_BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING",   (0,0), (-1,-1), 9),
        ("RIGHTPADDING",  (0,0), (-1,-1), 9),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("FONTNAME",      (0,1), (0,-1),  "Arial-Bold"),
    ]))
    items.append(tbl)
    items.append(sp(0.4))
    return items

# ── SECTION 4 — OZET TABLO ───────────────────────────────────────────────────
def section_ozet():
    items = []
    items += [h1("4.  Ozet  —  Tum Credential'lar"), section_rule(), sp(0.2)]
    items.append(body("Settings sayfasindaki tum alanlar ve nereden alinacagi:"))
    items.append(sp(0.3))

    data = [
        [Paragraph("Ayar Karti",    S["table_hdr"]),
         Paragraph("Alan Adi",      S["table_hdr"]),
         Paragraph("Nereden Alinir",S["table_hdr"])],
        ["Expo EAS",        "EAS_TOKEN",               "expo.dev  >  Profil  >  Access Tokens"],
        ["Expo EAS",        "EXPO_APP_ID",             "expo.dev  >  Projects  >  Proje URL UUID"],
        ["Codemagic",       "CODEMAGIC_TOKEN",         "codemagic.io  >  Teams  >  Integrations  >  API"],
        ["Codemagic",       "CODEMAGIC_APP_ID",        "codemagic.io  >  Uygulama URL'indeki ID"],
        ["Google Play",     "GOOGLE_PLAY_KEY_JSON",    "Google Cloud Console  >  Service Account  >  JSON Key"],
        ["App Store",       "APP_STORE_KEY_ID",        "appstoreconnect.apple.com  >  Integrations  >  API"],
        ["App Store",       "APP_STORE_ISSUER_ID",     "Ayni sayfa  >  Tablonun ustundeki Issuer ID"],
        ["App Store",       "APP_STORE_PRIVATE_KEY",   "Indirilen .p8 dosyasinin tam icerigi"],
    ]
    col_w = [3*cm, 5.2*cm, BODY_W - 8.2*cm]
    rows_fmt = [data[0]]
    for i, row in enumerate(data[1:]):
        bg = C_GRAY_BG if i % 2 == 0 else C_WHITE
        rows_fmt.append([
            Paragraph(row[0], S["table_cell"]),
            Paragraph(row[1], S["table_mono"]),
            Paragraph(row[2], ParagraphStyle("sm", fontName="Arial", fontSize=9.5, leading=13)),
        ])
    tbl = Table(rows_fmt, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  C_BLUE_DARK),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_GRAY_BG, C_WHITE]),
        ("BOX",           (0,0), (-1,-1), 0.8, C_GRAY_BORDER),
        ("INNERGRID",     (0,0), (-1,-1), 0.5, C_GRAY_BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    items.append(tbl)
    items.append(sp(0.4))
    return items

# ── SECTION 5 — SSS ──────────────────────────────────────────────────────────
def section_sss():
    items = []
    items += [h1("5.  Sikca Sorulan Sorular"), section_rule(), sp(0.2)]

    faqs = [
        ("Credential girmeden build calisir mi?",
         "Evet, simulasyon modunda calisir. Gercek binary uretilmez; test akisini dogrulamak icin kullanilabilir. "
         "Gercek APK/IPA almak icin ilgili provider'in credential'lari girilmis olmalidir."),
        ("Bir credential'i nasil guncellerim?",
         "Settings sayfasinda ilgili alana yeni degeri girin ve Save butonuna tiklayin. Onceki sifrelenmis deger uzerine yazilir."),
        ("Credential'i nasil silerim?",
         "Kaydedilmis alan yanindaki cop kutusuna tiklayin. Onay sonrasi veritabanindan kalici olarak silinir."),
        (".p8 dosyasini kaybettim, ne yapmali?",
         "App Store Connect'te mevcut key'i Revoke edin, ardindan yeni bir key olusturun. "
         "Yeni Key ID, Issuer ID ve Private Key degerlerini tekrar Settings sayfasina girin."),
        ("Google Play JSON key'm calismiyor, neden?",
         "En yaygin nedenler: (1) Google Play Console'da service account'a yeterli izin verilmemis, "
         "(2) 'Google Play Android Developer API' Cloud'da enable edilmemis, "
         "(3) JSON dosyasini yanlis yapistirma, "
         "(4) Paket adi (package_name) deploy sirasinda yanlis girilmis."),
        ("EAS Token ne kadar surede dolar?",
         "EAS Access Token'larin varsayilan suresi yoktur (kalicidir). Ancak hesap guvenliginiz tehlikeye girerse "
         "expo.dev > Access Tokens sayfasindan eski token'i iptal edip yeni bir tane olusturabilirsiniz."),
    ]
    for q, a in faqs:
        items.append(KeepTogether([
            h3(q),
            body(a),
            sp(0.3),
        ]))
    return items

# ── SECTION 6 — PIPELINE OZETI ───────────────────────────────────────────────
def section_pipeline():
    items = []
    items += [PageBreak(), h1("6.  Tam Pipeline Ozeti"), section_rule(), sp(0.2)]
    items.append(body("Credential'lar girildikten sonra gerceklesen tam otomasyon akisi:"))
    items.append(sp(0.3))
    items.append(code_block([
        " 1. Kullanici giriş yapar (email / GitHub OAuth)",
        " 2. GitHub hesabini baglar  >  Repo listesini goruntuler",
        " 3. Proje olusturur  >  Repo klonlanir",
        " 4. Framework otomatik tespit edilir (flutter / expo / swift / kotlin)",
        " 5. Canli Preview baslatilir (Expo/Flutter web / Appetize.io)",
        " 6. Build tetikler  >  EAS / Codemagic API'ye gonderilir",
        " 7. Webhook ile build tamamlaninca bildirim gelir",
        " 8. Artifact (APK/AAB/IPA) kaydedilir",
        " 9. Deploy tetikler:",
        "     Android: Google Play API  >  Internal Test  >  Production",
        "     iOS    : EAS Submit API   >  App Store Review",
        "10. Deploy durumu gercek zamanli guncellenir",
    ]))
    items.append(sp(0.4))

    items.append(info_box(
        nfc("Tum bu adimlar tek bir panel uzerinden, sifir sunucu kurulumu gerektirmeden, "
            "ucuncu parti build servislerini kullanarak gerceklestirilir.")
    ))
    items.append(sp(0.5))

    # Footer box
    footer_data = [[
        Paragraph("AppTrack  —  Mobil Uygulama Yayin Otomasyon Platformu", S["footer"]),
    ]]
    f_tbl = Table(footer_data, colWidths=[BODY_W])
    f_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C_BLUE_DARK),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("TEXTCOLOR",     (0,0), (-1,-1), C_WHITE),
    ]))
    items.append(f_tbl)
    return items

# ── BUILD ─────────────────────────────────────────────────────────────────────
def build_pdf(out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc = DocTemplate(
        out_path,
        pagesize=A4,
        topMargin=MARGIN + 0.5*cm,
        bottomMargin=MARGIN + 0.8*cm,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
    )

    story = []
    story += cover_page()
    story += section_genel_bakis()
    story += [h1("2.  Credential Kartlari"), section_rule(), sp(0.2)]
    story += section_eas()
    story += section_codemagic()
    story += section_google_play()
    story += section_app_store()
    story += section_guvenlik()
    story += section_ozet()
    story += section_sss()
    story += section_pipeline()

    doc.build(story)
    size = os.path.getsize(out_path)
    print(f"OK: {out_path}  ({size:,} bytes)")

if __name__ == "__main__":
    build_pdf(r"C:\Users\bilgi_islem\Desktop\apptrack\docs\credential-yonetimi-rehberi.pdf")
