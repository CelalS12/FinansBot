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

bot = telebot.TeleBot(TOKEN)
print("V26.1 GROQ (GPT-OSS ÜCRETSİZ) JSON HAFIZALI TERMİNAL: Sistem başlatılıyor...")

if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    groq_client = None

GROQ_MODEL = "openai/gpt-oss-20b"

# =========================================================================
# 🔴 JSON VERİTABANI SİSTEMİ 🔴
# =========================================================================
VERITABANI_DOSYASI = "cuzdan_hafizasi.json"
veritabani_kilidi = threading.Lock() 

kullanici_portfoy = {}

if os.path.exists(VERITABANI_DOSYASI):
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
    markup.row(InlineKeyboardButton("💼 Cüzdanım (Portföy)", callback_data="islem_portfoy"),
               InlineKeyboardButton("⚙️ Risk Profili", callback_data="islem_risk"))
    markup.row(InlineKeyboardButton("🌍 Küresel Radar", callback_data="islem_radar"),
               InlineKeyboardButton("🔔 Bülten Test", callback_data="test_bulten"))
    markup.row(InlineKeyboardButton("📄 Gün Sonu Kurumsal PDF Raporu", callback_data="pdf_rapor"))
    
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
        "**Ana menüden yapabileceklerin:**\n"
        "📊 Kapsamlı Analiz — Tek bir hisse/kripto için teknik analiz, AI haber yorumu ve fiyat tahmini\n"
        "⚖️ Düello — İki varlığı yan yana karşılaştırır\n"
        "💼 Cüzdanım — Sahip olduğun varlıkları takip eder, kâr/zarar gösterir\n"
        "⚙️ Risk Profili — Defansif / Dengeli / Agresif seçimi\n"
        "🌍 Küresel Radar — Dolar, altın, bitcoin ve S&P500 özeti\n"
        "📄 PDF Raporu — Portföyünün kurumsal formatta PDF raporu\n\n"
        "💡 **İpucu:** Hisse kodunu yazarken BIST için sadece kodu (örn. THYAO), "
        "ABD borsası için sembolü (örn. AAPL), kripto için de USD çiftini (örn. BTC-USD) "
        "yazman yeterli — gerisini bot otomatik tamamlıyor."
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

    if veri in ["islem_analiz", "islem_duello", "portfoy_ekle"]:
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
            bot.send_message(chat_id, "⚠️ Sistem yeniden başlatıldığı için önceki işleminiz silindi. Lütfen ana menüden baştan başlayın.", reply_markup=ana_menu_olustur())
            return
            
        kullanici_durumu[chat_id]['piyasa'] = veri.split("_")[1]
        mod = kullanici_durumu[chat_id]['mod']
        if mod == 'analiz':
            msg = bot.send_message(chat_id, f"Lütfen hisse/varlık kodunu yazın:")
            bot.register_next_step_handler(msg, hisse_kaydet_analiz)
        elif mod == 'duello':
            msg = bot.send_message(chat_id, f"1. varlık kodunu yazın:")
            bot.register_next_step_handler(msg, hisse1_kaydet_duello)
        elif mod == 'ekle':
            msg = bot.send_message(chat_id, f"Cüzdana eklenecek varlık kodunu yazın:")
            bot.register_next_step_handler(msg, p_hisse_al)
        return

    elif veri == "islem_radar":
        bot.send_message(chat_id, "🌍 Küresel piyasalar taranıyor, makro analiz yapılıyor...")
        try:
            usd = yf.Ticker("TRY=X").history(period="1mo")
            gold = yf.Ticker("GC=F").history(period="1mo")
            btc = yf.Ticker("BTC-USD").history(period="1mo")
            sp500 = yf.Ticker("^GSPC").history(period="1mo")
            
            if usd.empty or gold.empty or btc.empty or sp500.empty:
                bot.send_message(chat_id, "⚠️ Yahoo Finance makro verileri anlık olarak çekemedi. Lütfen birazdan tekrar deneyin.", reply_markup=ana_menu_olustur())
                return

            usd_fiyat = usd['Close'].iloc[-1]
            gold_fiyat = gold['Close'].iloc[-1]
            btc_fiyat = btc['Close'].iloc[-1]
            sp500_fiyat = sp500['Close'].iloc[-1]

            gold_degisim = (gold_fiyat / gold['Close'].iloc[0] - 1) * 100
            btc_degisim = (btc_fiyat / btc['Close'].iloc[0] - 1) * 100
            sp500_degisim = (sp500_fiyat / sp500['Close'].iloc[0] - 1) * 100

            if gold_degisim > 2: gold_yorum = "Altın son 1 ayda yükselişte. Dünyada enflasyon veya jeopolitik kriz endişesi artıyor. Güvenli limana kaçış var."
            elif gold_degisim < -2: gold_yorum = "Altın son 1 ayda düşüşte. Kriz endişeleri azalmış, para riskli varlıklara kayıyor."
            else: gold_yorum = "Altın yatay seyrediyor. Piyasalar belirleyici bir makro veri bekliyor."

            if btc_degisim > 5: btc_yorum = "Bitcoin güçlü yükselişte. Risk İştahı tavan yapmış, piyasada coşku hakim."
            elif btc_degisim < -5: btc_yorum = "Bitcoin sert düşüşte. Riskten Kaçış hakim, nakde geçiş var."
            else: btc_yorum = "Bitcoin durağan bir bölgede."

            sp500_yorum = "ABD Borsaları yükselişte. Küresel piyasa havası iyimser." if sp500_degisim > 2 else "ABD Borsaları zorlanıyor. Büyüme endişeleri baskın."

            rapor = (
                f"🌍 **KÜRESEL PİYASA RADARI VE MAKRO ANALİZ** 🌍\n━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 **Dolar/TL:** {usd_fiyat:.2f} ₺\n\n"
                f"🪙 **Ons Altın:** {gold_fiyat:.2f} $\n"
                f"🔍 **Analiz:** {gold_yorum}\n\n"
                f"🚀 **Bitcoin:** {btc_fiyat:,.2f} $\n"
                f"🔍 **Analiz:** {btc_yorum}\n\n"
                f"🇺🇸 **ABD S&P500:** {sp500_fiyat:,.2f} Puan\n"
                f"🔍 **Analiz:** {sp500_yorum}\n━━━━━━━━━━━━━━━━━━━━━━\n"
            )
            bot.send_message(chat_id, rapor, reply_markup=ana_menu_olustur())
        except Exception as e:
            bot.send_message(chat_id, f"❌ Makro veriler işlenirken hata oluştu: {str(e)}", reply_markup=ana_menu_olustur())
        return

    elif veri == "test_bulten":
        bot.send_message(chat_id, "⏳ Otonom sabah bülteni ve alarm sistemi tetikleniyor...")
        otomatik_sabah_bulteni()
        otomatik_alarm_kontrolu()
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
                   InlineKeyboardButton("📈 Kâr/Zarar Durumu", callback_data="portfoy_izle"))
        markup.row(InlineKeyboardButton("🏠 Ana Menüye Dön", callback_data="ana_menu"))
        bot.send_message(chat_id, "💼 Cüzdanına hoş geldin. Ne yapmak istersin?", reply_markup=markup)
        return
        
    elif veri == "portfoy_izle":
        portfoy_raporu_ver(chat_id)
        return

    if veri in ["butce_yok", "butce_var"] or veri.startswith("vade_"):
        if chat_id not in kullanici_durumu or 'mod' not in kullanici_durumu[chat_id]:
            bot.send_message(chat_id, "⚠️ Bot yeniden başlatıldığı için işlem hafızası silindi. Lütfen ana menüden tekrar başlayın.", reply_markup=ana_menu_olustur())
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

def kod_formatla(kod, piyasa):
    return kod.upper().strip() + ".IS" if piyasa == "tr" else kod.upper().strip()

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
    except Exception as e:
        print(f"⚠️ Öneri araması başarısız oldu: {e}")
        return []

def haber_ve_duygu_analizi(ticker_obj, hisse_kodu):
    try:
        if not groq_client:
            return "🗞️ *YAPAY ZEKA ANALİZİ:* Lütfen Render ortam değişkenlerine GROQ_API_KEY ekleyin."

        haberler = ticker_obj.news
        if not haberler: 
            return "🗞️ *YAPAY ZEKA ANALİZİ:* Şirketle ilgili güncel bir haber akışı bulunamadı."
        
        haber_basliklari = ""
        for h in haberler[:5]: 
            baslik = ""
            if isinstance(h, dict):
                if 'content' in h and isinstance(h['content'], dict):
                    baslik = h['content'].get('title', '')
                if not baslik:
                    baslik = h.get('title', '')
            if baslik:
                haber_basliklari += f"- {baslik}\n"
            
        if not haber_basliklari:
            return "🗞️ *YAPAY ZEKA ANALİZİ:* Haber başlıkları alınamadı."

        prompt = (
            f"Sen Wall Street'te çalışan profesyonel bir fon yöneticisisin. "
            f"Aşağıda {hisse_kodu} varlığına ait en güncel haber başlıkları var:\n\n"
            f"{haber_basliklari}\n\n"
            f"Lütfen bu haberlerin varlık değerini ve geleceğini nasıl etkileyebileceğini "
            f"kısa, profesyonel ve net bir şekilde 3 cümleyle tamamen Türkçe olarak yorumla. Başına emoji koy."
        )
        
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Sen kıdemli bir finansal analistsin. Sadece Türkçe dilinde cevap vermelisin."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=GROQ_MODEL,
            temperature=0.5,
        )
        
        ai_cevap = chat_completion.choices[0].message.content
        return f"🧠 **GROQ AI HABER ÖZETİ VE YORUMU** 🧠\n\n*{ai_cevap.strip()}*\n\n*İncelenen Son Başlıklar:*\n{haber_basliklari}"
        
    except Exception as e:
        return f"🗞️ *YAPAY ZEKA ANALİZİ:* Yapay zeka modülü şu an cevap veremiyor. (Detay: {str(e)})"

def p_hisse_al(message):
    chat_id = message.chat.id
    hisse_kodu = kod_formatla(message.text, kullanici_durumu[chat_id]['piyasa'])

    try:
        gecmis = yf.Ticker(hisse_kodu).history(period="5d")
        gecerli = not gecmis.empty
    except Exception:
        gecerli = False

    if not gecerli:
        oneriler = hisse_onerisi_bul(hisse_kodu)
        if oneriler:
            oneri_metni = "\n".join(f"• {o}" for o in oneriler)
            msg = bot.send_message(
                chat_id,
                f"⚠️ '{hisse_kodu}' bulunamadı. Bunlardan birini mi demek istedin?\n\n{oneri_metni}\n\n"
                f"Doğru kodu yazar mısın?",
            )
        else:
            msg = bot.send_message(chat_id, f"⚠️ '{hisse_kodu}' bulunamadı. Kodu kontrol edip tekrar yazar mısın?")
        bot.register_next_step_handler(msg, p_hisse_al)
        return

    kullanici_durumu[chat_id]['p_hisse'] = hisse_kodu
    msg = bot.send_message(chat_id, f"Maliyetin nedir? (Örn: 245.50):")
    bot.register_next_step_handler(msg, p_maliyet_al)

def p_maliyet_al(message):
    chat_id = message.chat.id
    try:
        kullanici_durumu[chat_id]['p_maliyet'] = float(message.text.replace(',', '.'))
        msg = bot.send_message(chat_id, "Kaç adet aldın?")
        bot.register_next_step_handler(msg, p_lot_al)
    except Exception:
        msg = bot.send_message(chat_id, "Rakam girmelisin. Maliyetin nedir?")
        bot.register_next_step_handler(msg, p_maliyet_al)

def p_lot_al(message):
    chat_id = message.chat.id
    chat_id_str = str(chat_id)
    try:
        lot = float(message.text)
        hisse = kullanici_durumu[chat_id]['p_hisse']
        maliyet = kullanici_durumu[chat_id]['p_maliyet']
        
        kullanici_portfoy[chat_id_str]['hisseler'][hisse] = {'maliyet': maliyet, 'lot': lot}
        veritabanina_kaydet()
        
        bot.send_message(chat_id, f"✅ {hisse} kalıcı hafızaya eklendi! Sunucu kapansa bile silinmeyecek.", reply_markup=ana_menu_olustur())
    except Exception:
        msg = bot.send_message(chat_id, "Sayı girmelisin. Kaç adet aldın?")
        bot.register_next_step_handler(msg, p_lot_al)

def portfoy_raporu_ver(chat_id):
    chat_id_str = str(chat_id)
    cuzdan = kullanici_portfoy[chat_id_str]['hisseler']
    if not cuzdan:
        bot.send_message(chat_id, "💼 Cüzdanın boş.", reply_markup=ana_menu_olustur())
        return
    bot.send_message(chat_id, "🔄 Veriler çekiliyor...")
    toplam_yatirim, toplam_guncel_deger = 0, 0
    rapor = "💼 KİŞİSEL PORTFÖYÜN\n━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for hisse, veriler in cuzdan.items():
        try:
            guncel_fiyat = yf.Ticker(hisse).fast_info['last_price']
            yat_para = veriler['maliyet'] * veriler['lot']
            gun_para = guncel_fiyat * veriler['lot']
            kar_zarar = gun_para - yat_para
            yuzde = ((guncel_fiyat - veriler['maliyet']) / veriler['maliyet']) * 100
            toplam_yatirim += yat_para
            toplam_guncel_deger += gun_para
            ikon = "🟩" if kar_zarar > 0 else "🟥"
            rapor += (f"🔹 **{hisse}** ({veriler['lot']:.2f} Adet)\n• Maliyet: {veriler['maliyet']:.2f} | Güncel: {guncel_fiyat:.2f}\n"
                      f"• Durum: {ikon} {kar_zarar:+.2f} (%{yuzde:+.1f})\n\n")
        except Exception as e:
            print(f"⚠️ {hisse} için veri çekilemedi: {e}")
            
    fark = toplam_guncel_deger - toplam_yatirim
    genel_yuzde = (fark / toplam_yatirim) * 100 if toplam_yatirim > 0 else 0
    rapor += (f"━━━━━━━━━━━━━━━━━━━━━━\n💵 Toplam Maliyet: {toplam_yatirim:.2f}\n💰 Güncel Bakiye: {toplam_guncel_deger:.2f}\n"
              f"🎯 GENEL DURUM: {'🟩' if fark > 0 else '🟥'} {fark:+.2f} (%{genel_yuzde:+.2f})\n")
    bot.send_message(chat_id, rapor, reply_markup=ana_menu_olustur())

def hisse_kaydet_analiz(message):
    kullanici_durumu[message.chat.id]['hisse1'] = kod_formatla(message.text, kullanici_durumu[message.chat.id]['piyasa'])
    butce_sorusu_sun(message.chat.id)
def hisse1_kaydet_duello(message):
    kullanici_durumu[message.chat.id]['hisse1'] = kod_formatla(message.text, kullanici_durumu[message.chat.id]['piyasa'])
    msg = bot.send_message(message.chat.id, "İkinci varlığın kodunu yazın:")
    bot.register_next_step_handler(msg, hisse2_kaydet_duello)
def hisse2_kaydet_duello(message):
    kullanici_durumu[message.chat.id]['hisse2'] = kod_formatla(message.text, kullanici_durumu[message.chat.id]['piyasa'])
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

def final_rapor_analiz(chat_id):
    bot.send_message(chat_id, "🏛️ Analizler hesaplanıyor, haberler AI ile yorumlanıyor ve GRAFİKLER çiziliyor...")
    try:
        tercih = kullanici_durumu[chat_id]
        hisse_kodu = tercih['hisse1']
        ticker = yf.Ticker(hisse_kodu)
        gecmis_veri = ticker.history(period="1y")

        if gecmis_veri.empty or len(gecmis_veri) < 5:
            oneriler = hisse_onerisi_bul(hisse_kodu)
            if oneriler:
                oneri_metni = "\n".join(f"• {o}" for o in oneriler)
                bot.send_message(
                    chat_id,
                    f"⚠️ '{hisse_kodu}' bulunamadı. Bunlardan birini mi demek istedin?\n\n{oneri_metni}\n\n"
                    f"Doğru kodu öğrenip ana menüden tekrar dener misin?",
                    reply_markup=ana_menu_olustur(),
                )
            else:
                bot.send_message(chat_id, f"⚠️ Yahoo Finance API anlık olarak {hisse_kodu} verisini boş döndürdü. Lütfen kodu kontrol edip birazdan tekrar deneyin.", reply_markup=ana_menu_olustur())
            return

        info = ticker.info
        guncel_fiyat = gecmis_veri['Close'].iloc[-1]
        fk_orani = info.get('trailingPE', 0) or 0
        
        sma_50 = gecmis_veri['Close'].rolling(window=50).mean()
        sma_200 = gecmis_veri['Close'].rolling(window=200).mean()
        sma_50_son = sma_50.iloc[-1] if len(sma_50.dropna()) > 0 else 0
        sma_200_son = sma_200.iloc[-1] if len(sma_200.dropna()) > 0 else 0
        
        try:
            plt.figure(figsize=(10, 5))
            plt.plot(gecmis_veri.index, gecmis_veri['Close'], label='Kapanis Fiyati', color='#1f77b4', linewidth=2)
            plt.plot(gecmis_veri.index, sma_50, label='50 Gun SMA', color='#ff7f0e', linestyle='--')
            plt.title(f"{hisse_kodu} Son 1 Yillik Performans")
            plt.xlabel("Tarih")
            plt.ylabel("Fiyat")
            plt.legend()
            plt.grid(True, alpha=0.3)
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            bot.send_photo(chat_id, photo=buf, caption=f"📈 {hisse_kodu} Teknik Analiz Grafiği")
        finally:
            plt.close()

        rs = gecmis_veri['Close'].diff().clip(lower=0).ewm(com=13, adjust=False).mean() / (-1 * gecmis_veri['Close'].diff().clip(upper=0)).ewm(com=13, adjust=False).mean()
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        aylik_carpan = (guncel_fiyat / gecmis_veri['Close'].iloc[0]) ** (1/12)
        t1, t12 = guncel_fiyat * (aylik_carpan ** 1), guncel_fiyat * (aylik_carpan ** 12)

        chat_id_str = str(chat_id)
        risk_profili = kullanici_portfoy[chat_id_str]['risk_profili']
        
        rapor = f"📑 {hisse_kodu} BİRLEŞİK DETAYLI ANALİZ\n━━━━━━━━━━━━━━━━━━━━━━\n"
        rapor += f"💵 GÜNCEL FİYAT: {guncel_fiyat:.2f}\n• F/K: {fk_orani:.1f} | RSI: {rsi:.1f}\n\n"
        
        if hisse_kodu in kullanici_portfoy[chat_id_str]['hisseler']:
            lot = kullanici_portfoy[chat_id_str]['hisseler'][hisse_kodu]['lot']
            maliyet = kullanici_portfoy[chat_id_str]['hisseler'][hisse_kodu]['maliyet']
            kar = (guncel_fiyat - maliyet) * lot
            rapor += f"💼 **CÜZDANINDA VAR:** {lot:.2f} adet. Kâr/Zararın: {'🟩' if kar>0 else '🟥'} {kar:+.2f}\n\n"

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
            
        bot.send_message(chat_id, rapor, reply_markup=ana_menu_olustur())
    except Exception as e:
        bot.send_message(chat_id, f"❌ Hata oluştu. (Detay: {str(e)})", reply_markup=ana_menu_olustur())

def final_rapor_duello(chat_id):
    bot.send_message(chat_id, "⚖️ İki varlık ringe çıkarılıyor, cüzdan ve makro verilerle kapıştırılıyor...")
    try:
        tercih = kullanici_durumu[chat_id]
        h1, h2 = tercih['hisse1'], tercih['hisse2']
        t1, t2 = yf.Ticker(h1), yf.Ticker(h2)
        
        v1, v2 = t1.history(period="1y"), t2.history(period="1y")

        if v1.empty or v2.empty or len(v1) < 5 or len(v2) < 5:
            hatali_kod = h1 if (v1.empty or len(v1) < 5) else h2
            oneriler = hisse_onerisi_bul(hatali_kod)
            if oneriler:
                oneri_metni = "\n".join(f"• {o}" for o in oneriler)
                bot.send_message(
                    chat_id,
                    f"⚠️ '{hatali_kod}' bulunamadı. Bunlardan birini mi demek istedin?\n\n{oneri_metni}",
                    reply_markup=ana_menu_olustur(),
                )
            else:
                bot.send_message(chat_id, "⚠️ Yahoo Finance API varlıklardan birinin verisini anlık olarak boş döndürdü. Lütfen kodu kontrol edip birazdan tekrar deneyin.", reply_markup=ana_menu_olustur())
            return
            
        f1, f2 = t1.fast_info['last_price'], t2.fast_info['last_price']
        fk1, fk2 = t1.info.get('trailingPE', 0) or 0, t2.info.get('trailingPE', 0) or 0
        
        rs1 = v1['Close'].diff().clip(lower=0).ewm(com=13, adjust=False).mean() / (-1 * v1['Close'].diff().clip(upper=0)).ewm(com=13, adjust=False).mean()
        rsi1 = (100 - (100 / (1 + rs1))).iloc[-1]
        rs2 = v2['Close'].diff().clip(lower=0).ewm(com=13, adjust=False).mean() / (-1 * v2['Close'].diff().clip(upper=0)).ewm(com=13, adjust=False).mean()
        rsi2 = (100 - (100 / (1 + rs2))).iloc[-1]

        c1 = (f1 / v1['Close'].iloc[0]) ** (1/12)
        c2 = (f2 / v2['Close'].iloc[0]) ** (1/12)

        h1_1, h1_12 = f1*c1, f1*(c1**12)
        h2_1, h2_12 = f2*c2, f2*(c2**12)

        kisa_kazanan = h1 if rsi1 < rsi2 else h2
        uzun_kazanan = h1 if (0 < fk1 < fk2) else h2
        
        chat_id_str = str(chat_id)
        cuzdan = kullanici_portfoy[chat_id_str]['hisseler']
        cuzdan_metni = ""
        if h1 in cuzdan: cuzdan_metni += f"• **{h1}** cüzdanında mevcut.\n"
        if h2 in cuzdan: cuzdan_metni += f"• **{h2}** cüzdanında mevcut.\n"

        rapor = (f"⚖️ KAPSAMLI DÜELLO PROJEKSİYONU: {h1} vs {h2}\n━━━━━━━━━━━━━━━━━━━━━━\n")
        if cuzdan_metni: rapor += f"💼 CÜZDAN EŞLEŞMESİ:\n{cuzdan_metni}\n"
            
        rapor += (
            f"⏱️ HANGİSİNİ ALMAK DAHA MANTIKLI?\n\n"
            f"• **Kısa Vade (1-3 Ay):** {kisa_kazanan} daha avantajlı. *(Çünkü RSI momentumuna göre kısa vadede daha ucuz/sakin bölgede, tepki ihtimali yüksek.)*\n\n"
            f"• **Uzun Vade (6-12 Ay+):** {uzun_kazanan} daha avantajlı. *(Çünkü temel F/K çarpanına göre şirket daha iskontolu ve kârlılığını daha iyi fiyatlıyor.)*\n\n"
            f"🔮 GELECEK FİYAT TAHMİNLERİ:\n\n"
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
                f"🔹 **{h1} Alırsan:** {lot1:.2f} adet.\n• 1 Ay Sonra: {p1_1:.2f} | 12 Ay Sonra: {p1_12:.2f}\n\n"
                f"🔹 **{h2} Alırsan:** {lot2:.2f} adet.\n• 1 Ay Sonra: {p2_1:.2f} | 12 Ay Sonra: {p2_12:.2f}\n"
            )
            
        bot.send_message(chat_id, rapor, reply_markup=ana_menu_olustur())
    except Exception as e:
        bot.send_message(chat_id, f"❌ Düello yapılırken hata oluştu. (Detay: {str(e)})", reply_markup=ana_menu_olustur())


# =========================================================================
# 🔴 KURUMSAL PDF RAPORU SİSTEMİ 🔴
# =========================================================================

def tr_to_eng(metin):
    return str(metin).replace("ğ","g").replace("ş","s").replace("ı","i").replace("ç","c").replace("ö","o").replace("ü","u").replace("Ğ","G").replace("Ş","S").replace("İ","I").replace("Ç","C").replace("Ö","O").replace("Ü","U").replace("₺","TL")

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18)
        self.set_text_color(20, 50, 90)
        self.cell(0, 15, 'STRATEJIK FINANS VE PORTFOY RAPORU', 0, 1, 'C')
        self.set_draw_color(20, 50, 90)
        self.line(10, 25, 200, 25)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

def pdf_rapor_olustur_ve_gonder(chat_id):
    bot.send_message(chat_id, "📄 Kurumsal PDF Raporu hazırlanıyor. Lütfen bekleyin...")
    grafik_dosya = f"rapor_grafik_{chat_id}.png"
    pdf_dosya = f"Gun_Sonu_Raporu_{chat_id}.pdf"
    try:
        chat_id_str = str(chat_id)
        cuzdan = kullanici_portfoy[chat_id_str]['hisseler']
        
        odak_hisse = list(cuzdan.keys())[0] if cuzdan else "XU100.IS"
        veri = yf.Ticker(odak_hisse).history(period="6mo")
        
        if veri.empty or len(veri) < 5:
            bot.send_message(chat_id, "⚠️ Grafik çizimi için yeterli veri alınamadı. Lütfen birazdan tekrar deneyin.", reply_markup=ana_menu_olustur())
            return
            
        try:
            plt.figure(figsize=(9, 4))
            plt.plot(veri.index, veri['Close'], color='#2ca02c', linewidth=2, label='Fiyat')
            plt.plot(veri.index, veri['Close'].rolling(window=50).mean(), color='#d62728', linestyle='--', label='50 Gun SMA')
            plt.title(f"{odak_hisse} Fiyat Hareketleri (Son 6 Ay)")
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.savefig(grafik_dosya, bbox_inches='tight')
        finally:
            plt.close()

        pdf = PDF()
        pdf.add_page()
        
        pdf.set_font("Arial", 'B', 14)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 10, txt=" 1. KURESEL PIYASA VE MAKRO GORUNUM", ln=True, fill=True)
        pdf.set_font("Arial", size=11)
        pdf.set_text_color(0)
        pdf.ln(3)

        usd = yf.Ticker("TRY=X").fast_info['last_price']
        gold = yf.Ticker("GC=F").fast_info['last_price']
        btc = yf.Ticker("BTC-USD").fast_info['last_price']
        
        makro_metin = (
            f"Kuresel piyasalarda Dolar/TL kuru {usd:.2f} TL seviyelerinde islem gormektedir. "
            f"Guvenli liman olan Ons Altin {gold:.2f} USD fiyatlanmasiyla kuresel enflasyon ve risk algisi hakkinda ipuclari verirken, "
            f"risk istahinin en onemli gostergelerinden olan Bitcoin {btc:,.2f} USD seviyesinden islem gormektedir. "
            f"Uluslararasi iliskilerdeki jeopolitik gerilimler ve merkez bankalarinin faiz kararlari bu uc ana veriyi sekillendirmektedir."
        )
        pdf.multi_cell(0, 7, txt=tr_to_eng(makro_metin))
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, txt=" 2. PORTFOY VE RISK ANALIZI", ln=True, fill=True)
        pdf.set_font("Arial", size=11)
        pdf.ln(3)
        
        pdf.cell(0, 8, txt=f"Guncel Risk Profiliniz: {tr_to_eng(kullanici_portfoy[chat_id_str]['risk_profili']).upper()}", ln=True)
        pdf.ln(2)

        if not cuzdan:
            pdf.cell(0, 8, txt="Cuzdaninizda henuz varlik bulunmuyor.", ln=True)
        else:
            top_yat = 0
            top_gun = 0
            for h, v in cuzdan.items():
                try:
                    g_fiyat = yf.Ticker(h).fast_info['last_price']
                    kar = (g_fiyat - v['maliyet']) * v['lot']
                    top_yat += v['maliyet'] * v['lot']
                    top_gun += g_fiyat * v['lot']
                    durum = "KAR" if kar > 0 else "ZARAR"
                    satir = f"-> {h} | Adet: {v['lot']} | Maliyet: {v['maliyet']:.2f} | Guncel: {g_fiyat:.2f} | Durum: {kar:+.2f} ({durum})"
                    pdf.cell(0, 8, txt=tr_to_eng(satir), ln=True)
                except Exception as e:
                    print(f"⚠️ PDF için {h} verisi alınamadı: {e}")
            
            pdf.ln(3)
            fark = top_gun - top_yat
            genel = "POZITIF" if fark > 0 else "NEGATIF"
            ozet_metin = f"TOPLAM YATIRIM: {top_yat:.2f} TL   |   GUNCEL DEGER: {top_gun:.2f} TL\nNET FARK: {fark:+.2f} TL ({genel})"
            pdf.set_font("Arial", 'B', 11)
            pdf.multi_cell(0, 7, txt=tr_to_eng(ozet_metin))
            pdf.set_font("Arial", size=11)

        pdf.ln(5)
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, txt=f" 3. ODAK VARLIK TEKNIK ANALIZI: {odak_hisse}", ln=True, fill=True)
        pdf.set_font("Arial", size=11)
        pdf.ln(5)

        try:
            odak_info = yf.Ticker(odak_hisse).info
            fk = odak_info.get('trailingPE', 0) or 0
            
            rs = veri['Close'].diff().clip(lower=0).ewm(com=13, adjust=False).mean() / (-1 * veri['Close'].diff().clip(upper=0)).ewm(com=13, adjust=False).mean()
            rsi = (100 - (100 / (1 + rs))).iloc[-1]
            
            aylik_carpan = (veri['Close'].iloc[-1] / veri['Close'].iloc[0]) ** (1/6)
            fiyat_12_ay = veri['Close'].iloc[-1] * (aylik_carpan ** 12)

            teknik_metin = (
                f"Degerleme & Momentum: Varligin F/K orani {fk:.1f}, anlik RSI momentum degeri ise {rsi:.1f} seviyesindedir. "
                f"(RSI 30 alti asiri satim, 70 uzeri asiri alim bolgesini ifade eder). Son 6 aylik ivme ayni sekilde devam ederse, "
                f"matematiksel (CAGR) buyume modeline gore varligin 12 ay sonraki projeskiyon fiyati {fiyat_12_ay:.2f} seviyesinde hesaplanmistir."
            )
            pdf.multi_cell(0, 7, txt=tr_to_eng(teknik_metin))
        except Exception as e:
            pdf.cell(0, 8, txt="Teknik veriler su an saglanamiyor.", ln=True)
            print(f"⚠️ PDF teknik analiz hatası: {e}")

        pdf.ln(5)
        pdf.image(grafik_dosya, x=15, w=180)
        
        pdf.output(pdf_dosya)
        with open(pdf_dosya, "rb") as f:
            bot.send_document(chat_id, f, caption="Belgeniz hazır! İşte profesyonel gün sonu raporunuz 📄", reply_markup=ana_menu_olustur())
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ PDF oluşturulurken hata: {str(e)}", reply_markup=ana_menu_olustur())
    finally:
        for dosya in (grafik_dosya, pdf_dosya):
            if os.path.exists(dosya):
                try:
                    os.remove(dosya)
                except Exception as e:
                    print(f"⚠️ Geçici dosya silinemedi ({dosya}): {e}")

# =========================================================================
# 🔴 OTONOM ZAMANLAYICI VE ALARM SİSTEMİ 🔴
# =========================================================================

def otomatik_sabah_bulteni():
    try:
        usd = yf.Ticker("TRY=X").fast_info['last_price']
        btc = yf.Ticker("BTC-USD").fast_info['last_price']
        
        mesaj = (
            f"🌅 **GÜNAYDIN PATRON! İŞTE SABAH BÜLTENİ** 🌅\n"
            f"Piyasalar açılıyor. Güne başlarken küresel durum:\n"
            f"💵 Dolar/TL: {usd:.2f} ₺\n"
            f"🚀 Bitcoin: {btc:,.2f} $\n\n"
            f"İşlem yapmak veya portföyüne bakmak için menüyü kullanabilirsin. Bol kazançlar!"
        )
        for chat_id in kullanici_portfoy.keys():
            bot.send_message(int(chat_id), mesaj)
    except Exception as e:
        print(f"⚠️ Sabah bülteni gönderilemedi: {e}")

def otomatik_alarm_kontrolu():
    for chat_id, portfoy in kullanici_portfoy.items():
        cuzdan = portfoy['hisseler']
        if not cuzdan: continue
            
        for hisse, veriler in cuzdan.items():
            try:
                guncel_fiyat = yf.Ticker(hisse).fast_info['last_price']
                maliyet = veriler['maliyet']
                degisim_yuzdesi = ((guncel_fiyat - maliyet) / maliyet) * 100
                
                if degisim_yuzdesi >= 5.0:
                    bot.send_message(int(chat_id), f"🚨 **FIRSAT ALARMI!** 🚨\nCüzdanındaki **{hisse}** yükselişe geçti!\n• Maliyetin: {maliyet}\n• Anlık Fiyat: {guncel_fiyat:.2f} (+%{degisim_yuzdesi:.2f})")
                elif degisim_yuzdesi <= -5.0:
                    bot.send_message(int(chat_id), f"🚨 **DÜŞÜŞ ALARMI!** 🚨\nCüzdanındaki **{hisse}** sert düştü!\n• Maliyetin: {maliyet}\n• Anlık Fiyat: {guncel_fiyat:.2f} (%{degisim_yuzdesi:.2f})")
            except Exception as e:
                print(f"⚠️ Alarm kontrolü sırasında {hisse} hatası: {e}")
                continue

schedule.every().day.at("08:30").do(otomatik_sabah_bulteni)
schedule.every(15).minutes.do(otomatik_alarm_kontrolu)

def arka_plan_zamanlayicisi():
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=arka_plan_zamanlayicisi, daemon=True).start()

# =========================================================================
# 🔴 WEBHOOK SİSTEMİ VE FLASK SUNUCUSU 🔴
# =========================================================================
app = Flask(__name__)

WEBHOOK_PATH = f"/{TOKEN}/"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

@app.route('/', methods=['GET', 'HEAD'])
def ping():
    return "Finans Botu 7/24 Webhook ve Açık Kaynaklı Groq (GPT-OSS) Zekası ile Çalışıyor!"

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
