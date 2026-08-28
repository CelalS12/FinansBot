import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yfinance as yf
import pandas as pd
import threading
import time
import schedule
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fpdf import FPDF
import io
import os
import json
from flask import Flask, request
from groq import Groq

# =========================================================================
# 🔴 AYARLAR (ORTAM DEĞİŞKENLERİNDEN OKUNUYOR) 🔴
# =========================================================================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST", "https://finansbot-1-kqdj.onrender.com")

if not TOKEN:
    raise RuntimeError(
        "TELEGRAM_TOKEN ortam değişkeni bulunamadı! "
        "Render'da Environment sekmesinden eklemen lazım."
    )

bot = telebot.TeleBot(TOKEN, num_threads=20)
print("V31.0 BIST 100 + US 50 + CRYPTO 30 RADAR MOTORU: Sistem başlatılıyor...")

if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    groq_client = None

GROQ_MODEL = "openai/gpt-oss-20b"

# =========================================================================
# 🔴 180 DEV VARLIK HAVUZU (BIST 100 + ABD 50 + KRIPTO 30) 🔴
# =========================================================================
HAVUZ_BIST_100 = [
    "THYAO.IS", "BIMAS.IS", "TUPRS.IS", "FROTO.IS", "KCHOL.IS", "AKBNK.IS", "YKBNK.IS", "ASELS.IS", "SISE.IS", "SAHOL.IS",
    "PGSUS.IS", "CCOLA.IS", "MGROS.IS", "ENKAI.IS", "EREGL.IS", "ASTOR.IS", "KONTR.IS", "ISCTR.IS", "GARAN.IS", "VAKBN.IS",
    "HALKB.IS", "TCELL.IS", "TTKOM.IS", "PETKM.IS", "KOZAL.IS", "KOZAA.IS", "IPEKE.IS", "TOASO.IS", "ARCLK.IS", "ALARK.IS",
    "HEKTS.IS", "SASA.IS", "GUBRF.IS", "EKGYO.IS", "OYAKC.IS", "SMRTG.IS", "ENJSA.IS", "KRDMD.IS", "CIMSA.IS", "DOHOL.IS",
    "TAVHL.IS", "TKFEN.IS", "SOKM.IS", "AGHOL.IS", "BUCIM.IS", "BRISA.IS", "OTKAR.IS", "DOAS.IS", "KORDS.IS", "ULKER.IS",
    "MAVI.IS", "VESBE.IS", "VESTL.IS", "MPARK.IS", "TSKB.IS", "ANSGR.IS", "AKSA.IS", "AKFGY.IS", "ECILC.IS", "EUPWR.IS",
    "ALFAS.IS", "CWENE.IS", "CANTE.IS", "ODAS.IS", "ZOREN.IS", "BIOEN.IS", "GESAN.IS", "YEOTK.IS", "QUAGR.IS", "ISGYO.IS",
    "TRGYO.IS", "KLGYO.IS", "KZBGY.IS", "SNGYO.IS", "ALGYO.IS", "PSGYO.IS", "SKBNK.IS", "TUKAS.IS", "KONYA.IS", "EGEEN.IS",
    "BFREN.IS", "BRYAT.IS", "TMSN.IS", "KCAER.IS", "GWIND.IS", "AEFES.IS", "ISMEN.IS", "OYAYO.IS", "GLYHO.IS", "BERA.IS",
    "IEYHO.IS", "IHLGM.IS", "GSDHO.IS", "POLHO.IS", "CEMTS.IS", "PARSN.IS", "LOGO.IS", "ARDYZ.IS", "MIATK.IS", "SDTTR.IS"
]

HAVUZ_ABD_50 = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B", "LLY", "AVGO",
    "JPM", "UNH", "V", "XOM", "MA", "JNJ", "PG", "HD", "COST", "ABBV",
    "MRK", "NFLX", "BAC", "AMD", "CRM", "KO", "PEP", "WMT", "CVX", "TMO",
    "LIN", "ORCL", "ACN", "MCD", "CSCO", "QCOM", "ABT", "TXN", "GE", "PM",
    "DHR", "INTU", "WFC", "IBM", "AMAT", "CAT", "NOW", "DIS", "MS", "UBER"
]

HAVUZ_KRIPTO_30 = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD", "TRX-USD", "AVAX-USD", "LINK-USD",
    "SHIB-USD", "DOT-USD", "BCH-USD", "NEAR-USD", "SUI-USD", "LTC-USD", "PEPE-USD", "UNI-USD", "APT-USD", "ICP-USD",
    "FET-USD", "XMR-USD", "XLM-USD", "RENDER-USD", "HBAR-USD", "ATOM-USD", "ARB-USD", "OP-USD", "FIL-USD", "INJ-USD"
]

# =========================================================================
# 🔴 JSON VERİTABANI VE KİLİT SİSTEMLERİ 🔴
# =========================================================================
veritabani_kilidi = threading.Lock() 
grafik_kilidi = threading.Lock()

kullanici_portfoy = {}

if os.path.exists(VERITABANI_DOSYASI := "cuzdan_hafizasi.json"):
    with open(VERITABANI_DOSYASI, "r", encoding="utf-8") as f:
        try:
            kullanici_portfoy = json.load(f)
            print(f"✅ JSON hafızası yüklendi: {len(kullanici_portfoy)} kullanıcı bulundu.")
        except Exception as e:
            print(f"⚠️ JSON dosyası okunamadı, boş başlatılıyor: {e}")
            kullanici_portfoy = {}
else:
    kullanici_portfoy = {}

def veritabanina_kaydet():
    with veritabani_kilidi:
        with open(VERITABANI_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(kullanici_portfoy, f, ensure_ascii=False, indent=4)

kullanici_durumu = {} 

def cuzdan_kontrol(chat_id):
    chat_id_str = str(chat_id)
    if chat_id_str not in kullanici_portfoy:
        kullanici_portfoy[chat_id_str] = {'risk_profili': 'dengeli', 'hisseler': {}}
        veritabanina_kaydet()

def ana_menu_olustur():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏠 Ana Menüye Dön", callback_data="ana_menu"))
    return markup

def ana_menuyu_gonder(chat_id):
    cuzdan_kontrol(chat_id)
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📊 Kapsamlı Analiz", callback_data="islem_analiz"),
               InlineKeyboardButton("⚖️ Düello (Kıyas)", callback_data="islem_duello"))
    markup.row(InlineKeyboardButton("💡 Stratejik Hisse Radarı", callback_data="islem_radar_oneri"),
               InlineKeyboardButton("📈 Grafik & Trend Analizi", callback_data="islem_grafik"))
    markup.row(InlineKeyboardButton("💼 Cüzdanım (Portföy)", callback_data="islem_portfoy"),
               InlineKeyboardButton("⚙️ Risk Profili", callback_data="islem_risk"))
    markup.row(InlineKeyboardButton("🌍 Küresel Radar", callback_data="islem_radar"),
               InlineKeyboardButton("📄 Kurumsal PDF Raporu", callback_data="pdf_rapor"))
    
    bot.send_message(chat_id, "🏠 **GLOBAL FİNANS TERMİNALİ**\nHangi işlemi seçiyoruz Patron?", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text.lower() in ['selam', 'merhaba', 'hi', 'start', '/start'])
def baslangic(message):
    bot.clear_step_handler_by_chat_id(message.chat.id) 
    ana_menuyu_gonder(message.chat.id)

@bot.message_handler(func=lambda message: message.text.lower() in ['/help', 'yardım', 'yardim', 'help'])
def yardim_komutu(message):
    yardim_metni = (
        "🤖 **FİNANS BOTU YARDIM** 🤖\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "**Komutlar:**\n"
        "🏠 /start — Ana menüyü açar\n"
        "❓ /help — Bu yardım mesajını gösterir\n\n"
        "**Özellikler:**\n"
        "💬 Serbest Mod — Herhangi bir finansal sorunu yaz, AI anında cevaplasın!\n"
        "📊 Kapsamlı Analiz — Teknik, AI haber, fiyat projeksiyonu ve temettü bilgisi\n"
        "⚖️ Düello — İki varlığı mantıksal projeksiyonlarla karşılaştırır\n"
        "💡 Hisse Radarı — BIST 100, ABD 50 ve Kripto 30 tarama motoru\n"
        "📈 Grafik Analizi — Hareketli ortalamalar ve trend analizi\n"
        "💼 Cüzdanım — Kâr/zarar, Dolar/TL hesabı ve Stop-Loss takibi\n"
        "🌍 Küresel Radar — Dolar, altın, BTC ve S&P500 özeti\n"
        "📄 PDF Raporu — Profesyonel kurumsal rapor oluşturur\n"
    )
    bot.send_message(message.chat.id, yardim_metni, parse_mode="Markdown", reply_markup=ana_menu_olustur())

@bot.callback_query_handler(func=lambda call: True)
def buton_tepkisi(call):
    chat_id = call.message.chat.id
    chat_id_str = str(chat_id)
    veri = call.data
    cuzdan_kontrol(chat_id)
    
    if veri == "ana_menu":
        bot.clear_step_handler_by_chat_id(chat_id)
        ana_menuyu_gonder(chat_id)
        return

    if veri == "pdf_rapor":
        pdf_rapor_olustur_ve_gonder(chat_id)
        return

    # 1. RADAR PROFİL SEÇİMİ
    if veri == "islem_radar_oneri":
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🛡️ Defansif Portföy", callback_data="oneri_risk_defansif"),
                   InlineKeyboardButton("⚖️ Dengeli Portföy", callback_data="oneri_risk_dengeli"))
        markup.row(InlineKeyboardButton("⚔️ Agresif / Büyüme", callback_data="oneri_risk_agresif"))
        markup.row(InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu"))
        bot.send_message(chat_id, "🎯 **STRATEJİK HİSSE RADARI**\nHangi risk profiline uygun tarama yapılsın?", reply_markup=markup, parse_mode="Markdown")
        return

    # 2. RADAR VADE SEÇİMİ
    elif veri.startswith("oneri_risk_"):
        secilen_risk = veri.split("_")[2]
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("⏱️ Kısa Vade (1-3 Ay)", callback_data=f"oneri_vade_{secilen_risk}_kisa"),
                   InlineKeyboardButton("📅 Uzun Vade (6-12 Ay+)", callback_data=f"oneri_vade_{secilen_risk}_uzun"))
        markup.row(InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu"))
        bot.send_message(chat_id, f"Seçilen Profil: **{secilen_risk.upper()}**\nVade tercihin nedir?", reply_markup=markup, parse_mode="Markdown")
        return

    # 3. RADAR PİYASA SEÇİMİ (BIST 100 / ABD 50 / KRİPTO 30)
    elif veri.startswith("oneri_vade_"):
        parcalar = veri.split("_")
        risk_tipi = parcalar[2]
        vade_tipi = parcalar[3]
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🇹🇷 BIST 100 (100 Hisse)", callback_data=f"oneri_run_{risk_tipi}_{vade_tipi}_bist"),
                   InlineKeyboardButton("🇺🇸 ABD Top 50 (50 Dev)", callback_data=f"oneri_run_{risk_tipi}_{vade_tipi}_us"))
        markup.row(InlineKeyboardButton("🪙 Kripto Top 30 (30 Coin)", callback_data=f"oneri_run_{risk_tipi}_{vade_tipi}_crypto"),
                   InlineKeyboardButton("🌐 Global Karma (Tümü)", callback_data=f"oneri_run_{risk_tipi}_{vade_tipi}_all"))
        markup.row(InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu"))
        bot.send_message(chat_id, f"🎯 **Hangi Piyasa Taranacak?**\n(Profil: {risk_tipi.upper()} | Vade: {vade_tipi.upper()})", reply_markup=markup, parse_mode="Markdown")
        return

    # 4. RADAR ÇALIŞTIRMA
    elif veri.startswith("oneri_run_"):
        parcalar = veri.split("_")
        risk_tipi = parcalar[2]
        vade_tipi = parcalar[3]
        piyasa_secimi = parcalar[4]
        threading.Thread(target=hisse_tarama_ve_oneri_uret, args=(chat_id, risk_tipi, vade_tipi, piyasa_secimi)).start()
        return

    if veri in ["islem_analiz", "islem_duello", "islem_grafik", "portfoy_ekle"]:
        kullanici_durumu[chat_id] = {'mod': veri.split("_")[1]} 
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🇹🇷 BIST", callback_data="piyasa_tr"),
                   InlineKeyboardButton("🇺🇸 ABD Borsası", callback_data="piyasa_us"),
                   InlineKeyboardButton("🪙 Kripto", callback_data="piyasa_crypto"))
        markup.row(InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu"))
        bot.send_message(chat_id, "Hangi piyasada işlem yapacağız?", reply_markup=markup)
        return

    elif veri.startswith("piyasa_"):
        if chat_id not in kullanici_durumu or 'mod' not in kullanici_durumu[chat_id]:
            bot.send_message(chat_id, "⚠️ Sistem sıfırlandı. Ana menüden baştan başlayın.", reply_markup=ana_menu_olustur())
            return
            
        kullanici_durumu[chat_id]['piyasa'] = veri.split("_")[1]
        mod = kullanici_durumu[chat_id]['mod']
        if mod == 'analiz':
            msg = bot.send_message(chat_id, f"Lütfen hisse veya şirket adını yazın (örn: pegasus, THYAO):")
            bot.register_next_step_handler(msg, hisse_kaydet_analiz)
        elif mod == 'duello':
            msg = bot.send_message(chat_id, f"1. varlık adını veya kodunu yazın:")
            bot.register_next_step_handler(msg, hisse1_kaydet_duello)
        elif mod == 'grafik':
            msg = bot.send_message(chat_id, f"Grafik analizi yapılacak varlığın adını veya kodunu yazın:")
            bot.register_next_step_handler(msg, grafik_analiz_calistir)
        elif mod == 'ekle':
            msg = bot.send_message(chat_id, f"Cüzdana eklenecek varlık adını veya kodunu yazın:")
            bot.register_next_step_handler(msg, p_hisse_al)
        return

    elif veri == "islem_radar":
        threading.Thread(target=kuresel_radar_islet, args=(chat_id,)).start()
        return

    elif veri == "islem_risk":
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🛡️ Defansif", callback_data="risk_defansif"),
                   InlineKeyboardButton("⚖️ Dengeli", callback_data="risk_dengeli"),
                   InlineKeyboardButton("⚔️ Agresif", callback_data="risk_agresif"))
        bot.send_message(chat_id, "Nasıl bir yatırımcısın Patron?", reply_markup=markup)
        return
        
    elif veri.startswith("risk_"):
        kullanici_portfoy[chat_id_str]['risk_profili'] = veri.split("_")[1]
        veritabanina_kaydet()
        bot.send_message(chat_id, f"✅ Risk profilin **{veri.split('_')[1].upper()}** olarak güncellenip KALICI OLARAK KAYDEDİLDİ.", reply_markup=ana_menu_olustur())
        return

    elif veri == "islem_portfoy":
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("➕ Hisse/Kripto Ekle", callback_data="portfoy_ekle"),
                   InlineKeyboardButton("➖ Hisse Sat/Çıkar", callback_data="portfoy_cikar"))
        markup.row(InlineKeyboardButton("📈 Kâr/Zarar Durumu", callback_data="portfoy_izle"),
                   InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu"))
        bot.send_message(chat_id, "💼 Cüzdana hoş geldin. Ne yapmak istersin?", reply_markup=markup)
        return

    elif veri == "portfoy_cikar":
        if not kullanici_portfoy[chat_id_str].get('hisseler'):
            bot.send_message(chat_id, "💼 Cüzdanın zaten boş.", reply_markup=ana_menu_olustur())
            return
        msg = bot.send_message(chat_id, "Çıkarmak istediğin hissenin tam kodunu veya adını yaz:")
        bot.register_next_step_handler(msg, p_hisse_cikar)
        return
        
    elif veri == "portfoy_izle":
        portfoy_raporu_ver(chat_id)
        return

    if veri in ["butce_yok", "butce_var"] or veri.startswith("vade_"):
        if chat_id not in kullanici_durumu or 'mod' not in kullanici_durumu[chat_id]:
            bot.send_message(chat_id, "⚠️ Bot hafızası silindi. Menüden baştan başlayın.", reply_markup=ana_menu_olustur())
            return

        if veri == "butce_yok":
            kullanici_durumu[chat_id]['butce'] = None
            if kullanici_durumu[chat_id]['mod'] == 'analiz': vade_secimi_sun(chat_id)
            else: final_rapor_duello(chat_id)
        elif veri == "butce_var":
            msg = bot.send_message(chat_id, "Lütfen bütçenizi RAKAM olarak yazın:")
            bot.register_next_step_handler(msg, butce_kaydet)
        elif veri.startswith("vade_"):
            kullanici_durumu[chat_id]['vade'] = veri.split("_")[1]
            final_rapor_analiz(chat_id)

def kuresel_radar_islet(chat_id):
    bot.send_message(chat_id, "🌍 Küresel piyasalar taranıyor, Groq AI makro analiz raporu hazırlanıyor...")
    try:
        data = yf.download(["TRY=X", "GC=F", "BTC-USD", "^GSPC"], period="1mo", threads=True, progress=False)['Close']
        usd_fiyat = data["TRY=X"].dropna().iloc[-1]
        gold_fiyat = data["GC=F"].dropna().iloc[-1]
        btc_fiyat = data["BTC-USD"].dropna().iloc[-1]
        sp500_fiyat = data["^GSPC"].dropna().iloc[-1]

        makro_prompt = (
            f"Küresel finans verileri:\n- Dolar/TL: {usd_fiyat:.2f}\n- Ons Altın: {gold_fiyat:.2f} USD\n"
            f"- Bitcoin: {btc_fiyat:,.2f} USD\n- ABD S&P500: {sp500_fiyat:,.2f}\n\n"
            f"Bu verileri kullanarak piyasanın genel yönünü ekonomik bir dille 2 cümleyle özetle."
        )
        
        ai_makro_yorum = "Küresel piyasalar dengeli seyrediyor."
        if groq_client:
            try:
                res = groq_client.chat.completions.create(
                    messages=[{"role": "system", "content": "Sen kıdemli bir Türk ekonomistsin. Sadece Türkçe yazmalısın."},
                              {"role": "user", "content": makro_prompt}],
                    model=GROQ_MODEL, temperature=0.3
                )
                ai_makro_yorum = res.choices[0].message.content.strip().replace("*", "")
            except: pass

        rapor = (
            f"🌍 **KÜRESEL PİYASA RADARI VE GROQ AI MAKRO ANALİZ** 🌍\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 **Dolar/TL:** {usd_fiyat:.2f} ₺\n"
            f"🪙 **Ons Altın:** {gold_fiyat:.2f} $\n"
            f"🚀 **Bitcoin:** {btc_fiyat:,.2f} $\n"
            f"🇺🇸 **ABD S&P500:** {sp500_fiyat:,.2f} Puan\n\n"
            f"🧠 **AI Makro Değerlendirme:**\n*{ai_makro_yorum}*\n━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        bot.send_message(chat_id, rapor, reply_markup=ana_menu_olustur())
    except Exception as e:
        bot.send_message(chat_id, f"❌ Makro veriler işlenirken hata oluştu: {str(e)}", reply_markup=ana_menu_olustur())

def akilli_kod_cozucu(metin, piyasa):
    temiz = metin.upper().strip()
    if piyasa == "tr":
        if not temiz.endswith(".IS"):
            aday = temiz + ".IS"
            try:
                if not yf.Ticker(aday).history(period="3d").empty:
                    return aday
            except: pass
    try:
        arama_sonuclari = yf.Search(temiz, max_results=3).quotes
        if arama_sonuclari:
            en_iyi = arama_sonuclari[0].get('symbol')
            if en_iyi:
                if piyasa == "tr" and not en_iyi.endswith(".IS") and "." not in en_iyi:
                    return en_iyi + ".IS"
                return en_iyi
    except: pass
    return temiz + ".IS" if piyasa == "tr" else temiz

def hisse_onerisi_bul(kod):
    try:
        arama_terimi = kod.replace(".IS", "")
        sonuclar = yf.Search(arama_terimi, max_results=5).quotes
        oneriler = []
        for s in sonuclar:
            sembol = s.get('symbol', '')
            isim = s.get('shortname') or s.get('longname') or ''
            if sembol and sembol != kod:
                oneriler.append(f"{sembol}" + (f" — {isim}" if isim else ""))
        return oneriler[:3]
    except: return []

def haber_ve_duygu_analizi(ticker_obj, hisse_kodu):
    try:
        if not groq_client: return "🗞️ *YAPAY ZEKA ANALİZİ:* API anahtarı eksik."
        haberler = ticker_obj.news
        if not haberler: return "🗞️ *YAPAY ZEKA ANALİZİ:* Şirketle ilgili güncel haber bulunamadı."
        
        haber_basliklari = ""
        for h in haberler[:5]: 
            baslik = ""
            if isinstance(h, dict):
                if 'content' in h and isinstance(h['content'], dict):
                    baslik = h['content'].get('title', '')
                if not baslik:
                    baslik = h.get('title', '')
            if baslik: haber_basliklari += f"- {baslik}\n"
            
        if not haber_basliklari: return "🗞️ *YAPAY ZEKA ANALİZİ:* Haber başlıkları alınamadı."

        prompt = (f"Şirket/Varlık: {hisse_kodu}\nHaberler:\n{haber_basliklari}\n\n"
                  f"Bu haberlerin hisse üzerindeki etkisini profesyonel ve net bir dille 2 cümleyle özetle.")
        
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Sen kıdemli bir Türk finans analistisin. Gelen haberler İngilizce olsa dahi KESİNLİKLE sadece Türkçe özetle."},
                {"role": "user", "content": prompt}
            ],
            model=GROQ_MODEL, temperature=0.3,
        )
        ai_cevap = chat_completion.choices[0].message.content.strip().replace("*", "")
        return f"🧠 **GROQ AI HABER ÖZETİ VE YORUMU** 🧠\n\n{ai_cevap}\n\n*İncelenen Son Başlıklar:*\n{haber_basliklari}"
    except Exception as e:
        return f"🗞️ *YAPAY ZEKA ANALİZİ:* Yapay zeka modülü cevap veremiyor. ({str(e)})"

# =========================================================================
# 🔴 HIZLI & GÜVENLİ STRATEJİK HİSSE RADARI (180 VARLIK HAVUZU) 🔴
# =========================================================================
def hisse_tarama_ve_oneri_uret(chat_id, risk_tipi, vade_tipi, piyasa_secimi):
    if piyasa_secimi == "bist":
        secili_havuz = HAVUZ_BIST_100
        havuz_adi = "🇹🇷 BIST 100"
    elif piyasa_secimi == "us":
        secili_havuz = HAVUZ_ABD_50
        havuz_adi = "🇺🇸 ABD Top 50"
    elif piyasa_secimi == "crypto":
        secili_havuz = HAVUZ_KRIPTO_30
        havuz_adi = "🪙 Kripto Top 30"
    else:
        secili_havuz = HAVUZ_BIST_100[:25] + HAVUZ_ABD_50[:15] + HAVUZ_KRIPTO_30[:10]
        havuz_adi = "🌐 Global Karma"

    bot.send_message(chat_id, f"🔍 **{havuz_adi}** taranıyor... ({risk_tipi.upper()} - {vade_tipi.upper()})\nLütfen bekleyin, grafikler çiziliyor...")
    
    sonuclar = []
    gecmis_veriler = {}
    
    try:
        # Toplu indirme ile maksimum hız
        veri_bulk = yf.download(secili_havuz, period="3mo", threads=True, progress=False)
        df_close = veri_bulk['Close'] if 'Close' in veri_bulk else veri_bulk
        
        for sembol in secili_havuz:
            try:
                if sembol not in df_close.columns: continue
                s_close = df_close[sembol].dropna()
                if len(s_close) < 15: continue
                    
                fiyat = float(s_close.iloc[-1])
                sma20 = float(s_close.rolling(20).mean().iloc[-1])
                sma50 = float(s_close.rolling(min(len(s_close), 50)).mean().iloc[-1])
                
                diff = s_close.diff()
                gain = diff.clip(lower=0).rolling(14).mean().iloc[-1]
                loss = (-1 * diff.clip(upper=0)).rolling(14).mean().iloc[-1]
                rsi = 50.0 if loss == 0 else float(100 - (100 / (1 + (gain / loss))))
                
                aylik_oran = (fiyat / float(s_close.iloc[0])) ** (1/3)
                projeksiyon = fiyat * (aylik_oran ** 12)
                
                puan = 50
                if risk_tipi == "defansif":
                    if fiyat > sma50: puan += 20
                    if 35 <= rsi <= 55: puan += 25
                    if sembol in ["BIMAS.IS", "TUPRS.IS", "FROTO.IS", "AAPL", "BTC-USD", "KO", "PG", "SISE.IS"]: puan += 15
                elif risk_tipi == "dengeli":
                    if sma20 > sma50: puan += 20
                    if 45 <= rsi <= 62: puan += 20
                    if projeksiyon > fiyat: puan += 15
                elif risk_tipi == "agresif":
                    if rsi > 55 or rsi < 35: puan += 20
                    if sembol in ["NVDA", "PGSUS.IS", "SOL-USD", "ASTOR.IS", "TSLA"]: puan += 20
                    if sma20 > sma50: puan += 15

                trend = "Yukarı 🟢" if fiyat > sma20 else "Dirençte 🟡"
                sonuclar.append({
                    'sembol': sembol, 'fiyat': fiyat, 'rsi': rsi,
                    'sma20': sma20, 'sma50': sma50, 'trend': trend,
                    'puan': puan, 'projeksiyon': projeksiyon
                })
                gecmis_veriler[sembol] = s_close
            except: continue

        sonuclar.sort(key=lambda x: x['puan'], reverse=True)
        secilenler = sonuclar[:8] # En yüksek puanlı 8 hisse/coin
        
        if not secilenler:
            bot.send_message(chat_id, "⚠️ Piyasa verilerine ulaşılamadı. Tekrar deneyin.", reply_markup=ana_menu_olustur())
            return

        grafik_dosya = f"radar_grafik_{chat_id}.png"
        
        with grafik_kilidi:
            try:
                plt.figure(figsize=(9, 4.5))
                for item in secilenler[:4]:
                    s = item['sembol']
                    s_series = gecmis_veriler[s]
                    norm = (s_series / s_series.iloc[0] - 1) * 100
                    plt.plot(s_series.index, norm, label=s, linewidth=2)
                    
                plt.title(f"{havuz_adi} - Öne Çıkanların 3 Aylık Göreceli Değişimi (%)")
                plt.xlabel("Tarih")
                plt.ylabel("Değişim (%)")
                plt.legend()
                plt.grid(True, alpha=0.3)
                plt.axhline(0, color='black', linewidth=1, linestyle='--')
                plt.savefig(grafik_dosya, bbox_inches='tight')
            except Exception as e:
                print(f"Grafik çizim hatası: {e}")
            finally:
                plt.close('all')

        hisse_listesi_metni = ""
        ai_detay_metni = ""
        for idx, item in enumerate(secilenler, 1):
            para = "$" if ("-USD" in item['sembol'] or not "." in item['sembol']) else "₺"
            hisse_listesi_metni += (
                f"{idx}. {item['sembol']} — Fiyat: {item['fiyat']:.2f}{para}\n"
                f"• RSI: {item['rsi']:.1f} | Trend: {item['trend']} | 12A Hedef: {item['projeksiyon']:.2f}{para}\n\n"
            )
            if idx <= 3:
                ai_detay_metni += f"- {item['sembol']}: Fiyat={item['fiyat']:.2f}, RSI={item['rsi']:.1f}\n"
                
        ai_prompt = (
            f"Kullanıcı {havuz_adi} piyasasında {risk_tipi.upper()} profil ve {vade_tipi.upper()} vade için tarama yaptı.\n"
            f"Algoritma sonucu öne çıkanlar:\n{ai_detay_metni}\n"
            f"Bu verilere dayanarak en gerçekçi, net piyasa stratejisini 2 cümleyle tamamen Türkçe olarak yaz. Özel karakterler ve yıldız işareti kullanma."
        )
        
        ai_ozet = "Hareketli ortalamalar ve teknik momentum göstergeleri dikkate alındığında dengeli bir portföy dağılımı önerilmektedir."
        if groq_client:
            try:
                res = groq_client.chat.completions.create(
                    messages=[{"role": "system", "content": "Sen kıdemli teknik analistsin. Sadece Türkçe yanıtla."},
                              {"role": "user", "content": ai_prompt}],
                    model=GROQ_MODEL, temperature=0.2
                )
                ai_ozet = res.choices[0].message.content.strip().replace("*", "").replace("_", "")
            except: pass

        mesaj = (
            f"🎯 {havuz_adi.upper()} STRATEJİK RADAR SONUÇLARI 🎯\n"
            f"📌 Profil: {risk_tipi.upper()} | ⏱️ Vade: {vade_tipi.upper()}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 AI Strateji Notu:\n{ai_ozet}\n\n"
            f"📊 Öne Çıkan En İyi Varlıklar:\n\n{hisse_listesi_metni}"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        if os.path.exists(grafik_dosya):
            with open(grafik_dosya, "rb") as f:
                bot.send_photo(chat_id, photo=f, caption=mesaj, reply_markup=ana_menu_olustur())
            try: os.remove(grafik_dosya)
            except: pass
        else:
            bot.send_message(chat_id, mesaj, reply_markup=ana_menu_olustur())

    except Exception as e:
        print(f"Genel radar hatası: {e}")
        bot.send_message(chat_id, f"❌ Radar analizi sırasında bir hata oluştu: {str(e)}", reply_markup=ana_menu_olustur())

# =========================================================================
# 🔴 TEKLİ GRAFİK & TREND ANALİZİ MODÜLÜ 🔴
# =========================================================================
def grafik_analiz_calistir(message):
    chat_id = message.chat.id
    ham_metin = message.text
    piyasa = kullanici_durumu[chat_id].get('piyasa', 'tr')
    hisse_kodu = akilli_kod_cozucu(ham_metin, piyasa)

    bot.send_message(chat_id, f"📈 **{hisse_kodu}** için teknik grafik ve hareketli ortalamalar çiziliyor...")
    grafik_dosya = f"gelismis_grafik_{chat_id}.png"
    try:
        ticker = yf.Ticker(hisse_kodu)
        df = ticker.history(period="6mo")
        
        if df.empty or len(df) < 10:
            bot.send_message(chat_id, f"⚠️ '{hisse_kodu}' için yeterli grafik verisi alınamadı.", reply_markup=ana_menu_olustur())
            return

        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        guncel_fiyat = df['Close'].iloc[-1]
        sma20_son = df['SMA20'].iloc[-1]
        sma50_son = df['SMA50'].iloc[-1]

        with grafik_kilidi:
            try:
                plt.figure(figsize=(10, 5))
                plt.plot(df.index, df['Close'], label='Kapanis Fiyati', color='#1f77b4', linewidth=2)
                plt.plot(df.index, df['SMA20'], label='20 Gunluk SMA (Kisa Trend)', color='#2ca02c', linestyle='--')
                plt.plot(df.index, df['SMA50'], label='50 Gunluk SMA (Orta Trend)', color='#d62728', linestyle='--')
                plt.title(f"{hisse_kodu} - Son 6 Aylik Teknik Trend")
                plt.xlabel("Tarih")
                plt.ylabel("Fiyat")
                plt.legend()
                plt.grid(True, alpha=0.3)
                plt.savefig(grafik_dosya, bbox_inches='tight')
            except: pass
            finally: plt.close('all')

        grafik_prompt = (
            f"Varlık: {hisse_kodu}\n"
            f"Güncel Fiyat: {guncel_fiyat:.2f}\n"
            f"20 Günlük SMA: {sma20_son:.2f}\n"
            f"50 Günlük SMA: {sma50_son:.2f}\n"
            f"Fiyat 20 günlük ortalamanın {'üzerinde' if guncel_fiyat > sma20_son else 'altında'}.\n"
            f"Bu görünüme dayanarak analist gibi 3 cümleyle Türkçe olarak trend yönünü açıkla."
        )

        ai_grafik_yorum = "Fiyat hareketli ortalamalar çevresinde denge arıyor."
        if groq_client:
            try:
                res = groq_client.chat.completions.create(
                    messages=[{"role": "system", "content": "Sen kıdemli teknik analistsin. Sadece Türkçe yanıtla."},
                              {"role": "user", "content": grafik_prompt}],
                    model=GROQ_MODEL, temperature=0.3
                )
                ai_grafik_yorum = res.choices[0].message.content.strip().replace("*", "")
            except: pass

        rapor = (
            f"📈 {hisse_kodu} GELİŞMİŞ GRAFİK ANALİZİ 📈\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Anlık Fiyat: {guncel_fiyat:.2f}\n"
            f"🟢 20 Günlük SMA: {sma20_son:.2f}\n"
            f"🔴 50 Günlük SMA: {sma50_son:.2f}\n\n"
            f"🧠 AI Grafik Yorumu:\n{ai_grafik_yorum}\n━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        
        if os.path.exists(grafik_dosya):
            with open(grafik_dosya, "rb") as f:
                bot.send_photo(chat_id, photo=f, caption=rapor, reply_markup=ana_menu_olustur())
            try: os.remove(grafik_dosya)
            except: pass
        else:
            bot.send_message(chat_id, rapor, reply_markup=ana_menu_olustur())

    except Exception as e:
        bot.send_message(chat_id, f"❌ Hata: {str(e)}", reply_markup=ana_menu_olustur())

# =========================================================================
# 🔴 PORTFÖY YÖNETİMİ VE ANALİZ 🔴
# =========================================================================
def p_hisse_al(message):
    chat_id = message.chat.id
    ham_metin = message.text
    piyasa = kullanici_durumu[chat_id]['piyasa']
    hisse_kodu = akilli_kod_cozucu(ham_metin, piyasa)

    try:
        gecmis = yf.Ticker(hisse_kodu).history(period="5d")
        gecerli = not gecmis.empty
    except: gecerli = False

    if not gecerli:
        oneriler = hisse_onerisi_bul(hisse_kodu)
        if oneriler:
            msg = bot.send_message(chat_id, f"⚠️ '{ham_metin}' bulunamadı. Şunlardan biri mi?\n\n{chr(10).join(['• '+o for o in oneriler])}\n\nDoğru kodu yaz:")
        else:
            msg = bot.send_message(chat_id, f"⚠️ '{ham_metin}' bulunamadı. Kodu tekrar yaz:")
        bot.register_next_step_handler(msg, p_hisse_al)
        return

    kullanici_durumu[chat_id]['p_hisse'] = hisse_kodu
    msg = bot.send_message(chat_id, f"✅ Varlık: **{hisse_kodu}**\nMaliyetin nedir? (Örn: 245.50):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, p_maliyet_al)

def p_maliyet_al(message):
    chat_id = message.chat.id
    try:
        kullanici_durumu[chat_id]['p_maliyet'] = float(message.text.replace(',', '.'))
        msg = bot.send_message(chat_id, "Kaç adet aldın?")
        bot.register_next_step_handler(msg, p_lot_al)
    except:
        msg = bot.send_message(chat_id, "Rakam girmelisin. Maliyetin nedir?")
        bot.register_next_step_handler(msg, p_maliyet_al)

def p_lot_al(message):
    chat_id = message.chat.id
    chat_id_str = str(chat_id)
    try:
        lot = float(message.text)
        hisse = kullanici_durumu[chat_id]['p_hisse']
        maliyet = kullanici_durumu[chat_id]['p_maliyet']
        
        kullanici_portfoy[chat_id_str]['hisseler'][hisse] = {
            'maliyet': maliyet, 
            'lot': lot,
            'son_alarm_fiyati': maliyet,
            'stop_loss': 0.0
        }
        veritabanina_kaydet()
        
        msg = bot.send_message(chat_id, f"✅ {hisse} kalıcı hafızaya eklendi!\n\n🛡️ İsteğe bağlı: **Zarar Kes (Stop-Loss)** seviyesi belirlemek ister misin? (Rakam yaz. İstemiyorsan '0' veya 'Yok' yaz):")
        bot.register_next_step_handler(msg, p_stop_loss_al, hisse)
    except:
        msg = bot.send_message(chat_id, "Sayı girmelisin. Kaç adet aldın?")
        bot.register_next_step_handler(msg, p_lot_al)

def p_stop_loss_al(message, hisse):
    chat_id = message.chat.id
    chat_id_str = str(chat_id)
    metin = message.text.replace(',', '.')
    
    if metin.lower() in ["0", "yok", "hayır", "hayir", "istemiyorum"]:
        bot.send_message(chat_id, "✅ Stop-Loss ayarlanmadı.", reply_markup=ana_menu_olustur())
        return
        
    try:
        sl = float(metin)
        if sl > 0:
            kullanici_portfoy[chat_id_str]['hisseler'][hisse]['stop_loss'] = sl
            veritabanina_kaydet()
            bot.send_message(chat_id, f"🛡️ Harika! **{hisse}** fiyatı **{sl}** seviyesinin altına inerse sana acil alarm göndereceğim.", parse_mode="Markdown", reply_markup=ana_menu_olustur())
        else:
            bot.send_message(chat_id, "✅ Stop-Loss ayarlanmadı.", reply_markup=ana_menu_olustur())
    except:
        bot.send_message(chat_id, "⚠️ Geçersiz rakam. Stop-Loss ayarlanmadı.", reply_markup=ana_menu_olustur())

def p_hisse_cikar(message):
    chat_id = message.chat.id
    chat_id_str = str(chat_id)
    kod = message.text.upper().strip()
    
    hisseler = kullanici_portfoy[chat_id_str].get('hisseler', {})
    bulunan = None
    for h in hisseler.keys():
        if kod in h:
            bulunan = h
            break
            
    if bulunan:
        del kullanici_portfoy[chat_id_str]['hisseler'][bulunan]
        veritabanina_kaydet()
        bot.send_message(chat_id, f"🗑️ **{bulunan}** portföyünden başarıyla silindi.", parse_mode="Markdown", reply_markup=ana_menu_olustur())
    else:
        bot.send_message(chat_id, f"⚠️ Cüzdanında '{kod}' ile eşleşen bir varlık bulunamadı.", reply_markup=ana_menu_olustur())

def portfoy_raporu_ver(chat_id):
    chat_id_str = str(chat_id)
    cuzdan = kullanici_portfoy[chat_id_str]['hisseler']
    if not cuzdan:
        bot.send_message(chat_id, "💼 Cüzdanın boş.", reply_markup=ana_menu_olustur())
        return
        
    bot.send_message(chat_id, "🔄 Veriler ve kurlar (Dolar/TL) çekiliyor...")
    
    try: usd_kur = yf.Ticker("TRY=X").fast_info['last_price']
    except: usd_kur = 34.0
    
    toplam_yatirim_tl, toplam_guncel_tl = 0, 0
    rapor = "💼 KİŞİSEL PORTFÖYÜN\n━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for hisse, veriler in cuzdan.items():
        try:
            guncel_fiyat = yf.Ticker(hisse).fast_info['last_price']
            yat_para = veriler['maliyet'] * veriler['lot']
            gun_para = guncel_fiyat * veriler['lot']
            kar_zarar = gun_para - yat_para
            yuzde = ((guncel_fiyat - veriler['maliyet']) / veriler['maliyet']) * 100
            
            is_usd = not hisse.endswith(".IS")
            carpan = usd_kur if is_usd else 1.0
            
            toplam_yatirim_tl += (yat_para * carpan)
            toplam_guncel_tl += (gun_para * carpan)
            
            ikon = "🟩" if kar_zarar > 0 else "🟥"
            para_birimi = "$" if is_usd else "₺"
            sl_metni = f" | Stop: {veriler.get('stop_loss', 0)}" if veriler.get('stop_loss', 0) > 0 else ""
            
            rapor += (f"🔹 **{hisse}** ({veriler['lot']:.2f} Adet)\n"
                      f"• Mal: {veriler['maliyet']:.2f}{para_birimi} | Gün: {guncel_fiyat:.2f}{para_birimi}{sl_metni}\n"
                      f"• Durum: {ikon} {kar_zarar:+.2f}{para_birimi} (%{yuzde:+.1f})\n\n")
        except: pass
            
    fark_tl = toplam_guncel_tl - toplam_yatirim_tl
    genel_yuzde = (fark_tl / toplam_yatirim_tl) * 100 if toplam_yatirim_tl > 0 else 0
    
    rapor += (f"━━━━━━━━━━━━━━━━━━━━━━\n💵 Toplam Maliyet: {toplam_yatirim_tl:,.2f} ₺\n"
              f"💰 Güncel Bakiye: {toplam_guncel_tl:,.2f} ₺\n"
              f"🎯 NET DURUM (TL): {'🟩' if fark_tl > 0 else '🟥'} {fark_tl:+,.2f} ₺ (%{genel_yuzde:+.2f})\n")
    bot.send_message(chat_id, rapor, reply_markup=ana_menu_olustur())

def hisse_kaydet_analiz(message):
    hisse = akilli_kod_cozucu(message.text, kullanici_durumu[message.chat.id]['piyasa'])
    kullanici_durumu[message.chat.id]['hisse1'] = hisse
    butce_sorusu_sun(message.chat.id)

def final_rapor_analiz(chat_id):
    bot.send_message(chat_id, "🏛️ Analizler hesaplanıyor, haberler AI ile yorumlanıyor...")
    try:
        tercih = kullanici_durumu[chat_id]
        hisse_kodu = tercih['hisse1']
        ticker = yf.Ticker(hisse_kodu)
        gecmis_veri = ticker.history(period="1y")

        if gecmis_veri.empty or len(gecmis_veri) < 5:
            bot.send_message(chat_id, "⚠️ API veriyi anlık çekemedi.", reply_markup=ana_menu_olustur())
            return

        info = ticker.info
        guncel_fiyat = gecmis_veri['Close'].iloc[-1]
        fk_orani = info.get('trailingPE', 0) or 0
        temettu_verimi = info.get('dividendYield', 0)
        temettu_metni = f"%{temettu_verimi*100:.1f}" if temettu_verimi else "Yok"
        
        sma_50 = gecmis_veri['Close'].rolling(window=50).mean()
        sma_200 = gecmis_veri['Close'].rolling(window=200).mean()
        sma_50_son = sma_50.iloc[-1] if len(sma_50.dropna()) > 0 else 0
        sma_200_son = sma_200.iloc[-1] if len(sma_200.dropna()) > 0 else 0
        
        rs = gecmis_veri['Close'].diff().clip(lower=0).ewm(com=13, adjust=False).mean() / (-1 * gecmis_veri['Close'].diff().clip(upper=0)).ewm(com=13, adjust=False).mean()
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        aylik_carpan = (guncel_fiyat / gecmis_veri['Close'].iloc[0]) ** (1/12)
        t1, t12 = guncel_fiyat * (aylik_carpan ** 1), guncel_fiyat * (aylik_carpan ** 12)

        chat_id_str = str(chat_id)
        
        grafik_dosya = f"analiz_grafik_{chat_id}.png"
        with grafik_kilidi:
            try:
                plt.figure(figsize=(10, 5))
                plt.plot(gecmis_veri.index, gecmis_veri['Close'], label='Kapanis Fiyati', color='#1f77b4', linewidth=2)
                plt.plot(gecmis_veri.index, sma_50, label='50 Gun SMA', color='#ff7f0e', linestyle='--')
                plt.title(f"{hisse_kodu} Son 1 Yillik Performans")
                plt.xlabel("Tarih")
                plt.ylabel("Fiyat")
                plt.legend()
                plt.grid(True, alpha=0.3)
                plt.savefig(grafik_dosya, bbox_inches='tight')
            except: pass
            finally: plt.close('all')

        rapor = f"📑 {hisse_kodu} BİRLEŞİK DETAYLI ANALİZ\n━━━━━━━━━━━━━━━━━━━━━━\n"
        rapor += f"💵 GÜNCEL FİYAT: {guncel_fiyat:.2f}\n• F/K: {fk_orani:.1f} | RSI: {rsi:.1f} | Temettü: {temettu_metni}\n\n"
        
        if hisse_kodu in kullanici_portfoy[chat_id_str].get('hisseler', {}):
            lot = kullanici_portfoy[chat_id_str]['hisseler'][hisse_kodu]['lot']
            maliyet = kullanici_portfoy[chat_id_str]['hisseler'][hisse_kodu]['maliyet']
            kar = (guncel_fiyat - maliyet) * lot
            rapor += f"💼 **CÜZDANINDA VAR:** {lot:.2f} adet. Kâr/Zarar: {'🟩' if kar>0 else '🟥'} {kar:+.2f}\n\n"

        rapor += f"{haber_ve_duygu_analizi(ticker, hisse_kodu)}\n\n"
        rapor += f"🧠 STRATEJİ VE AÇIKLAMALAR:\n\n"
        
        if tercih['vade'] in ['kisa', 'ikisi']: 
            rapor += f"⏱️ KISA VADE (RSI: {rsi:.1f}): {'Alım Fırsatı' if rsi <= 35 else ('Riskli/Şişmiş' if rsi >= 65 else 'Nötr')}\n"
        if tercih['vade'] in ['uzun', 'ikisi']:
            rapor += f"📅 UZUN VADE YÖN (SMA): {'Trend Yukarı' if sma_50_son > sma_200_son else 'Trend Aşağı'}\n"
            rapor += f"📅 UZUN VADE DEĞER (F/K: {fk_orani:.1f}): {'Ucuz/İskontolu' if 0 < fk_orani <= 10 else ('Pahalı/Primli' if fk_orani > 25 else 'Adil Fiyat')}\n\n"
            
        rapor += f"🔮 GELECEK TAHMİNLERİ:\n• 1 Ay Sonra: {t1:.2f}\n• 12 Ay Sonra: {t12:.2f}\n\n"

        if tercih['butce']:
            b = tercih['butce']
            rapor += f"💰 {b} İLE BÜTÇE PROJEKSİYONU:\n• {b/guncel_fiyat:.2f} adet alınabilir.\n• 1 Ay: {b*(aylik_carpan**1):.2f} | 12 Ay: {b*(aylik_carpan**12):.2f}"
            
        if os.path.exists(grafik_dosya):
            with open(grafik_dosya, "rb") as f:
                bot.send_photo(chat_id, photo=f, caption=rapor, reply_markup=ana_menu_olustur())
            try: os.remove(grafik_dosya)
            except: pass
        else:
            bot.send_message(chat_id, rapor, reply_markup=ana_menu_olustur())
    except Exception as e:
        bot.send_message(chat_id, f"❌ Hata oluştu. (Detay: {str(e)})", reply_markup=ana_menu_olustur())

def hisse1_kaydet_duello(message):
    hisse = akilli_kod_cozucu(message.text, kullanici_durumu[message.chat.id]['piyasa'])
    kullanici_durumu[message.chat.id]['hisse1'] = hisse
    msg = bot.send_message(message.chat.id, "2. varlık adını veya kodunu yazın:")
    bot.register_next_step_handler(msg, hisse2_kaydet_duello)

def hisse2_kaydet_duello(message):
    hisse = akilli_kod_cozucu(message.text, kullanici_durumu[message.chat.id]['piyasa'])
    kullanici_durumu[message.chat.id]['hisse2'] = hisse
    butce_sorusu_sun(message.chat.id)

def butce_sorusu_sun(chat_id):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("💰 Belirli bir bütçem var", callback_data="butce_var"),
               InlineKeyboardButton("❌ Sadece Verileri Göster", callback_data="butce_yok"))
    bot.send_message(chat_id, "Bütçe hesabı yapalım mı?", reply_markup=markup)

def butce_kaydet(message):
    chat_id = message.chat.id
    try:
        kullanici_durumu[chat_id]['butce'] = float(message.text.replace(',', '.'))
        if kullanici_durumu[chat_id]['mod'] == 'analiz': vade_secimi_sun(chat_id)
        else: final_rapor_duello(chat_id)
    except Exception:
        msg = bot.send_message(chat_id, "Rakam girin:")
        bot.register_next_step_handler(msg, butce_kaydet)

def vade_secimi_sun(chat_id):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("⏱️ Kısa Vade", callback_data="vade_kisa"),
               InlineKeyboardButton("📅 Uzun Vade", callback_data="vade_uzun"),
               InlineKeyboardButton("🧠 Her İkisi de", callback_data="vade_ikisi"))
    bot.send_message(chat_id, "Vade tercihiniz?", reply_markup=markup)

def final_rapor_duello(chat_id):
    bot.send_message(chat_id, "⚖️ İki varlık ringe çıkarılıyor, Groq AI düello senaryosu oluşturuluyor...")
    try:
        tercih = kullanici_durumu[chat_id]
        h1, h2 = tercih['hisse1'], tercih['hisse2']
        t1, t2 = yf.Ticker(h1), yf.Ticker(h2)
        
        v1, v2 = t1.history(period="1y"), t2.history(period="1y")

        if v1.empty or v2.empty or len(v1) < 5 or len(v2) < 5:
            bot.send_message(chat_id, f"⚠️ Veri alınamadı.", reply_markup=ana_menu_olustur())
            return
            
        f1, f2 = t1.fast_info['last_price'], t2.fast_info['last_price']
        
        rs1 = v1['Close'].diff().clip(lower=0).ewm(com=13, adjust=False).mean() / (-1 * v1['Close'].diff().clip(upper=0)).ewm(com=13, adjust=False).mean()
        rsi1 = (100 - (100 / (1 + rs1))).iloc[-1]
        rs2 = v2['Close'].diff().clip(lower=0).ewm(com=13, adjust=False).mean() / (-1 * v2['Close'].diff().clip(upper=0)).ewm(com=13, adjust=False).mean()
        rsi2 = (100 - (100 / (1 + rs2))).iloc[-1]

        c1 = (f1 / v1['Close'].iloc[0]) ** (1/12)
        c2 = (f2 / v2['Close'].iloc[0]) ** (1/12)

        h1_1, h1_12 = f1*c1, f1*(c1**12)
        h2_1, h2_12 = f2*c2, f2*(c2**12)

        uzun_kazanan = h1 if h1_12 > h2_12 else h2
        kisa_kazanan = h1 if abs(rsi1 - 50) < abs(rsi2 - 50) else h2

        duello_prompt = (
            f"Kısa vade teknik göstergelere göre kazanan: {kisa_kazanan}\n"
            f"Uzun vade fiyat projeksiyonuna göre kazanan: {uzun_kazanan}\n"
            f"Fiyat Projeksiyonları -> {h1} (12 Ay: {h1_12:.2f}) | {h2} (12 Ay: {h2_12:.2f})\n\n"
            f"Bu matematiksel verileri dikkate alarak fon yöneticisi edasıyla 2 cümlelik profesyonel Türkçe bir analiz yaz."
        )
        
        ai_duello_yorum = f"Kısa vadede {kisa_kazanan}, uzun vadede ise {uzun_kazanan} öne çıkmaktadır."
        if groq_client:
            try:
                res = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "Sen kıdemli bir Türk borsa uzmanısın. Yalnızca akıcı ve net Türkçe ile cevap vermelisin."},
                        {"role": "user", "content": duello_prompt}
                    ],
                    model=GROQ_MODEL, temperature=0.3
                )
                ai_duello_yorum = res.choices[0].message.content.strip().replace("*", "")
            except: pass
        
        chat_id_str = str(chat_id)
        cuzdan = kullanici_portfoy[chat_id_str].get('hisseler', {})
        cuzdan_metni = ""
        if h1 in cuzdan: cuzdan_metni += f"• **{h1}** cüzdanında mevcut.\n"
        if h2 in cuzdan: cuzdan_metni += f"• **{h2}** cüzdanında mevcut.\n"

        rapor = (f"⚖️ KAPSAMLI DÜELLO PROJEKSİYONU: {h1} vs {h2}\n━━━━━━━━━━━━━━━━━━━━━━\n")
        if cuzdan_metni: rapor += f"💼 CÜZDAN EŞLEŞMESİ:\n{cuzdan_metni}\n"
            
        rapor += (
            f"🧠 **GROQ AI DÜELLO YORUMU:**\n{ai_duello_yorum}\n\n"
            f"⏱️ TEKNİK ÖZET:\n"
            f"• **Kısa Vade:** {kisa_kazanan} avantajlı.\n"
            f"• **Uzun Vade (Projeksiyon):** {uzun_kazanan} avantajlı.\n\n"
            f"🔮 GELECEK FİYAT TAHMİNLERİ:\n"
            f"📈 **{h1}:** 1 Ay: {h1_1:.2f} | 12 Ay: {h1_12:.2f}\n"
            f"📈 **{h2}:** 1 Ay: {h2_1:.2f} | 12 Ay: {h2_12:.2f}\n"
        )

        if tercih['butce']:
            b = tercih['butce']
            lot1, lot2 = b / f1, b / f2
            p1_1, p1_12 = b*(c1**1), b*(c1**12)
            p2_1, p2_12 = b*(c2**1), b*(c2**12)
            rapor += (
                f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 BÜTÇE SİMÜLASYONU ({b} İLE):\n\n"
                f"🔹 **{h1} Alırsan:** {lot1:.2f} adet.\n• 1 Ay: {p1_1:.2f} | 12 Ay: {p1_12:.2f}\n\n"
                f"🔹 **{h2} Alırsan:** {lot2:.2f} adet.\n• 1 Ay: {p2_1:.2f} | 12 Ay: {p2_12:.2f}\n"
            )
            
        bot.send_message(chat_id, rapor, reply_markup=ana_menu_olustur())
    except Exception as e:
        bot.send_message(chat_id, f"❌ Düello yapılırken hata oluştu: {str(e)}", reply_markup=ana_menu_olustur())

class PDF(FPDF):
    def header(self):
        self.set_fill_color(24, 43, 73)
        self.rect(0, 0, 210, 22, 'F')
        self.set_font('Arial', 'B', 15)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 5)
        self.cell(190, 12, 'GLOBAL FINANS & YATIRIM BANKACILIGI RAPORU', 0, 0, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Sayfa {self.page_no()} - Otonom Finans Terminali', 0, 0, 'C')

def pdf_rapor_olustur_ve_gonder(chat_id):
    bot.send_message(chat_id, "📄 Derin AI analizleriyle zenginleştirilmiş kurumsal PDF raporu hazırlanıyor...")
    grafik_dosya = f"rapor_grafik_{chat_id}.png"
    pdf_dosya = f"Kurumsal_Finans_Raporu_{chat_id}.pdf"
    try:
        chat_id_str = str(chat_id)
        cuzdan = kullanici_portfoy[chat_id_str].get('hisseler', {})
        odak_hisse = list(cuzdan.keys())[0] if cuzdan else "XU100.IS"
        veri = yf.Ticker(odak_hisse).history(period="6mo")
        
        if veri.empty or len(veri) < 5:
            bot.send_message(chat_id, "⚠️ Grafik çizimi için yeterli veri alınamadı.", reply_markup=ana_menu_olustur())
            return
            
        with grafik_kilidi:
            try:
                plt.figure(figsize=(9, 3.8))
                plt.plot(veri.index, veri['Close'], color='#1f77b4', linewidth=2, label='Fiyat')
                plt.plot(veri.index, veri['Close'].rolling(window=50).mean(), color='#ff7f0e', linestyle='--', label='50 Gun SMA')
                plt.title(f"{odak_hisse} Fiyat Hareketleri ve Trend Analizi")
                plt.legend()
                plt.grid(True, alpha=0.3)
                plt.savefig(grafik_dosya, bbox_inches='tight')
            except: pass
            finally: plt.close('all')

        try: usd = yf.Ticker("TRY=X").fast_info['last_price']
        except: usd = 34.0
        try: gold = yf.Ticker("GC=F").fast_info['last_price']
        except: gold = 0.0
        try: btc = yf.Ticker("BTC-USD").fast_info['last_price']
        except: btc = 0.0

        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(230, 235, 245)
        pdf.set_text_color(24, 43, 73)
        pdf.cell(0, 8, txt="  1. KURESEL PIYASA VE MAKRO DEGERLENDIRMESI", ln=True, fill=True)
        pdf.set_font("Arial", size=10)
        pdf.set_text_color(50, 50, 50)
        pdf.ln(2)

        makro_metin = (
            f"Dolar/TL kuru {usd:.2f} TL, Ons Altin {gold:.2f} USD ve Bitcoin {btc:,.2f} USD seviyelerinde fiyatlanmaktadir. "
            f"Piyasalardaki genel likidite ve enflasyon baskilari merkez bankalarinin kararlarini dogrudan etkilemektedir."
        )
        pdf.multi_cell(0, 6, txt=tr_to_eng(makro_metin))
        pdf.ln(2)

        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(230, 235, 245)
        pdf.set_text_color(24, 43, 73)
        pdf.cell(0, 8, txt="  2. KISISEL PORTFOY VE RISK ANALIZI", ln=True, fill=True)
        pdf.set_font("Arial", size=10)
        pdf.set_text_color(50, 50, 50)
        pdf.ln(2)
        
        pdf.cell(0, 6, txt=f"Guncel Risk Profiliniz: {tr_to_eng(kullanici_portfoy[chat_id_str].get('risk_profili', 'DENGELI')).upper()}", ln=True)
        pdf.ln(1)

        if not cuzdan:
            pdf.cell(0, 6, txt="Portfoyunuzde henuz kaydedilmis varlik bulunmamaktadir.", ln=True)
        else:
            top_yat = 0
            top_gun = 0
            for h, v in cuzdan.items():
                try:
                    g_fiyat = yf.Ticker(h).fast_info['last_price']
                    kar = (g_fiyat - v['maliyet']) * v['lot']
                    is_usd = not h.endswith(".IS")
                    carpan = usd if is_usd else 1.0
                    
                    top_yat += (v['maliyet'] * v['lot'] * carpan)
                    top_gun += (g_fiyat * v['lot'] * carpan)
                    
                    durum = "KAR" if kar > 0 else "ZARAR"
                    satir = f"-> Varlik: {h} | Adet: {v['lot']} | Maliyet: {v['maliyet']:.2f} | Guncel: {g_fiyat:.2f} | Durum: {kar:+.2f} ({durum})"
                    pdf.cell(0, 6, txt=tr_to_eng(satir), ln=True)
                except: pass
            
            pdf.ln(2)
            fark = top_gun - top_yat
            genel = "POZITIF" if fark > 0 else "NEGATIF"
            ozet_metin = f"TOPLAM YATIRIM (TL Cinsi): {top_yat:,.2f} TL   |   GUNCEL DEGER: {top_gun:,.2f} TL\nNET DURUM: {fark:+,.2f} TL ({genel})"
            pdf.set_font("Arial", 'B', 10)
            pdf.multi_cell(0, 6, txt=tr_to_eng(ozet_metin))
            pdf.set_font("Arial", size=10)

        pdf.ln(2)
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(230, 235, 245)
        pdf.set_text_color(24, 43, 73)
        pdf.cell(0, 8, txt=f"  3. ODAK VARLIK TEKNIK ANALIZI: {odak_hisse}", ln=True, fill=True)
        pdf.set_font("Arial", size=10)
        pdf.set_text_color(50, 50, 50)
        pdf.ln(2)

        try:
            odak_info = yf.Ticker(odak_hisse).info
            fk = odak_info.get('trailingPE', 0) or 0
            
            rs = veri['Close'].diff().clip(lower=0).ewm(com=13, adjust=False).mean() / (-1 * veri['Close'].diff().clip(upper=0)).ewm(com=13, adjust=False).mean()
            rsi = (100 - (100 / (1 + rs))).iloc[-1]
            
            aylik_carpan = (veri['Close'].iloc[-1] / veri['Close'].iloc[0]) ** (1/6)
            fiyat_12_ay = veri['Close'].iloc[-1] * (aylik_carpan ** 12)

            teknik_metin = (
                f"Degerleme & Momentum: Varligin F/K orani {fk:.1f}, anlik RSI degeri ise {rsi:.1f} seviyesindedir. "
                f"Matematiksel CAGR modeline gore 12 aylik fiyat projeksiyonu {fiyat_12_ay:.2f} seviyesindedir."
            )
            pdf.multi_cell(0, 6, txt=tr_to_eng(teknik_metin))
        except:
            pdf.cell(0, 6, txt="Teknik veriler su an saglanamiyor.", ln=True)

        pdf.ln(2)
        pdf.image(grafik_dosya, x=15, w=180)
        
        pdf.output(pdf_dosya)
        with open(pdf_dosya, "rb") as f:
            bot.send_document(chat_id, f, caption="Kurumsal yatırım raporunuz hazır! 📄", reply_markup=ana_menu_olustur())
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ PDF oluşturulurken hata: {str(e)}", reply_markup=ana_menu_olustur())
    finally:
        for dosya in (grafik_dosya, pdf_dosya):
            if os.path.exists(dosya):
                try: os.remove(dosya)
                except: pass

# =========================================================================
# 🔴 AKILLI ALARM VE HABER SİSTEMİ (2 SAATTE BİR) 🔴
# =========================================================================
gonderilen_haberler = set()

def otomatik_sabah_bulteni():
    try:
        usd = yf.Ticker("TRY=X").fast_info['last_price']
        btc = yf.Ticker("BTC-USD").fast_info['last_price']
        
        mesaj = (
            f"🌅 GÜNAYDIN PATRON! İŞTE SABAH BÜLTENİ 🌅\n"
            f"Piyasalar açılıyor. Güne başlarken küresel durum:\n"
            f"💵 Dolar/TL: {usd:.2f} ₺\n"
            f"🚀 Bitcoin: {btc:,.2f} $\n\n"
            f"İşlem yapmak veya portföyüne bakmak için menüyü kullanabilirsin. Bol kazançlar!"
        )
        for chat_id in kullanici_portfoy.keys():
            bot.send_message(int(chat_id), mesaj)
    except: pass

def otomatik_alarm_kontrolu():
    global gonderilen_haberler
    unique_stocks = set()
    for portfoy in kullanici_portfoy.values():
        for hisse in portfoy.get('hisseler', {}).keys():
            unique_stocks.add(hisse)
            
    hisse_verileri = {}
    for hisse in unique_stocks:
        try:
            ticker = yf.Ticker(hisse)
            fiyat = ticker.fast_info['last_price']
            kritik_haber = None
            
            haberler = ticker.news
            if haberler:
                son_haber = haberler[0]
                baslik = ""
                if isinstance(son_haber, dict):
                    if 'content' in son_haber and isinstance(son_haber['content'], dict):
                        baslik = son_haber['content'].get('title', '')
                    if not baslik:
                        baslik = son_haber.get('title', '')
                
                haber_id = son_haber.get('uuid') or son_haber.get('link') or baslik
                
                if baslik and haber_id and haber_id not in gonderilen_haberler:
                    gonderilen_haberler.add(haber_id)
                    if len(gonderilen_haberler) > 1000: gonderilen_haberler.clear()
                        
                    if groq_client:
                        prompt = f"Hisse: {hisse}\nHaber: {baslik}\nBu haber hissenin fiyatını sert etkileyecek (bilanço, ihale, iflas vb.) KRİTİK bir gelişme mi? Yorum yapmadan sadece 'EVET' veya 'HAYIR' yaz."
                        try:
                            res = groq_client.chat.completions.create(
                                messages=[{"role": "user", "content": prompt}],
                                model=GROQ_MODEL, temperature=0.1, max_tokens=10
                            )
                            cevap = res.choices[0].message.content.strip().upper()
                            if "EVET" in cevap:
                                kritik_haber = baslik
                        except: pass
                            
            hisse_verileri[hisse] = {'fiyat': fiyat, 'haber': kritik_haber}
        except: pass
            
    for chat_id_str, portfoy in kullanici_portfoy.items():
        chat_id = int(chat_id_str)
        cuzdan = portfoy.get('hisseler', {})
        degisiklik_oldu_mu = False
        
        for hisse, veriler in cuzdan.items():
            if hisse not in hisse_verileri: continue
                
            guncel_fiyat = hisse_verileri[hisse]['fiyat']
            maliyet = veriler['maliyet']
            referans_fiyat = veriler.get('son_alarm_fiyati', maliyet)
            stop_loss = veriler.get('stop_loss', 0)
            
            if stop_loss > 0 and guncel_fiyat <= stop_loss:
                try:
                    bot.send_message(chat_id, f"🚨 ACİL STOP-LOSS (ZARAR KES) TETİKLENDİ! 🚨\nKoruma altına aldığın {hisse} fiyatı {stop_loss} seviyesinin altına inerek {guncel_fiyat:.2f} oldu!")
                    kullanici_portfoy[chat_id_str]['hisseler'][hisse]['stop_loss'] = 0
                    degisiklik_oldu_mu = True
                except: pass

            anlik_degisim_yuzdesi = ((guncel_fiyat - referans_fiyat) / referans_fiyat) * 100
            toplam_degisim_yuzdesi = ((guncel_fiyat - maliyet) / maliyet) * 100
            
            if anlik_degisim_yuzdesi >= 2.5:
                try:
                    bot.send_message(chat_id, f"🚨 HAREKETLİLİK ALARMI (YÜKSELİŞ) 🚨\nCüzdanındaki {hisse} hareketlendi!\n• Maliyetin: {maliyet:.2f}\n• Anlık Fiyat: {guncel_fiyat:.2f} (Toplam Kâr/Zarar: %{toplam_degisim_yuzdesi:+.2f})")
                    kullanici_portfoy[chat_id_str]['hisseler'][hisse]['son_alarm_fiyati'] = guncel_fiyat
                    degisiklik_oldu_mu = True
                except: pass
            elif anlik_degisim_yuzdesi <= -2.5:
                try:
                    bot.send_message(chat_id, f"🚨 HAREKETLİLİK ALARMI (DÜŞÜŞ) 🚨\nCüzdanındaki {hisse} sert düştü!\n• Maliyetin: {maliyet:.2f}\n• Anlık Fiyat: {guncel_fiyat:.2f} (Toplam Kâr/Zarar: %{toplam_degisim_yuzdesi:+.2f})")
                    kullanici_portfoy[chat_id_str]['hisseler'][hisse]['son_alarm_fiyati'] = guncel_fiyat
                    degisiklik_oldu_mu = True
                except: pass
                
            kritik_haber = hisse_verileri[hisse]['haber']
            if kritik_haber:
                try:
                    bot.send_message(chat_id, f"📰 KRİTİK HABER ALARMI! 📰\nPortföyündeki {hisse} için piyasayı sarsabilecek yeni bir gelişme var:\n\n📌 {kritik_haber}")
                except: pass

        if degisiklik_oldu_mu:
            veritabanina_kaydet()

schedule.every().day.at("08:30").do(otomatik_sabah_bulteni)
schedule.every(2).hours.do(otomatik_alarm_kontrolu)

def arka_plan_zamanlayicisi():
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=arka_plan_zamanlayicisi, daemon=True).start()

# =========================================================================
# 🔴 SERBEST AI SOHBET MODU 🔴
# =========================================================================
@bot.message_handler(func=lambda message: True)
def serbest_soru_cevap(message):
    chat_id = message.chat.id
    soru = message.text
    
    bot.send_message(chat_id, "⏳ Analiz ediliyor...")
    
    if groq_client:
        try:
            res = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Sen kıdemli, esprili ve zeki bir Türk finans analisti ve portföy yöneticisisin. Kullanıcının sorularına sadece Türkçe, piyasa dinamikleriyle açıklayan, akıcı, net ve çok uzun olmayan bir yanıt ver. Paragrafları ayırarak oku."},
                    {"role": "user", "content": soru}
                ],
                model=GROQ_MODEL, temperature=0.5
            )
            cevap = res.choices[0].message.content.strip()
            bot.send_message(chat_id, f"🧠 **GROQ AI YANITI:**\n\n{cevap}", parse_mode="Markdown")
        except Exception as e:
            bot.send_message(chat_id, "⚠️ Yapay zeka şu an yoğun, birazdan tekrar dene.")
    else:
        bot.send_message(chat_id, "⚠️ Yapay zeka bağlantısı kurulamadı.")

# =========================================================================
# 🔴 WEBHOOK SİSTEMİ VE FLASK SUNUCUSU 🔴
# =========================================================================
app = Flask(__name__)

WEBHOOK_PATH = f"/{TOKEN}/"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

@app.route('/', methods=['GET', 'HEAD'])
def ping():
    return "Finans Botu V31.0 7/24 Webhook ve AI Destekli Gelişmiş Finans Terminali ile Çalışıyor!"

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return "403 - Yetkisiz Erişim", 403

bot.remove_webhook()
time.sleep(1)
bot.set_webhook(url=WEBHOOK_URL)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
