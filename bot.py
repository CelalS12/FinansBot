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
print("V28.2 GROQ AI DESTEKLİ GELİŞMİŞ FİNANS TERMİNALİ: Sistem başlatılıyor...")

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
    markup.row(InlineKeyboardButton("📈 Grafik & Trend Analizi", callback_data="islem_grafik"),
               InlineKeyboardButton("💼 Cüzdanım (Portföy)", callback_data="islem_portfoy"))
    markup.row(InlineKeyboardButton("⚙️ Risk Profili", callback_data="islem_risk"),
               InlineKeyboardButton("🌍 Küresel Radar", callback_data="islem_radar"))
    markup.row(InlineKeyboardButton("📄 Kurumsal PDF Raporu", callback_data="pdf_rapor"))
    
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
        "📊 Kapsamlı Analiz — Teknik, derin AI haber yorumu ve fiyat tahmini\n"
        "⚖️ Düello — İki varlığı mantıksal projeksiyonlarla karşılaştırır\n"
        "📈 Grafik Analizi — Hareketli ortalamalar, destek/direnç ve hacim yorumu\n"
        "💼 Cüzdanım — Varlıklarını takip eder, kâr/zarar gösterir\n"
        "⚙️ Risk Profili — Defansif / Dengeli / Agresif seçimi\n"
        "🌍 Küresel Radar — Makroekonomik veriler ve Groq AI piyasa yorumu\n"
        "📄 PDF Raporu — AI analizleriyle zenginleştirilmiş kurumsal rapor\n\n"
        "💡 **İpucu:** 'pegasus', 'thy' veya şirket adı yazman yeterli — bot kodu otomatik çözer!"
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
            bot.send_message(chat_id, "⚠️ Sistem yeniden başlatıldığı için önceki işleminiz silindi. Lütfen ana menüden baştan başlayın.", reply_markup=ana_menu_olustur())
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
        bot.send_message(chat_id, "🌍 Küresel piyasalar taranıyor, Groq AI makro analiz raporu hazırlanıyor...")
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

            makro_prompt = (
                f"Küresel finans verileri:\n"
                f"- Dolar/TL: {usd_fiyat:.2f}\n"
                f"- Ons Altın: {gold_fiyat:.2f} USD\n"
                f"- Bitcoin: {btc_fiyat:,.2f} USD\n"
                f"- ABD S&P500: {sp500_fiyat:,.2f}\n\n"
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
                    ai_makro_yorum = res.choices[0].message.content.strip()
                except Exception:
                    pass

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
        bot.send_message(chat_id, "💼 Cüzdana hoş geldin. Ne yapmak istersin?", reply_markup=markup)
        return
        
    elif veri == "portfoy_izle":
        portfoy_raporu_ver(chat_id)
        return

    if veri in ["butce_yok", "butce_var"] or veri.startswith("vade_"):
        if chat_id not in kullanici_durumu or 'mod' not in kullanici_durumu[chat_id]:
            bot.send_message(chat_id, "⚠️ Bot yeniden başlatıldığı için işlem hafızası silindi. Lütfen ana menüden baştan başlayın.", reply_markup=ana_menu_olustur())
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

def akilli_kod_cozucu(metin, piyasa):
    temiz = metin.upper().strip()
    if piyasa == "tr":
        if not temiz.endswith(".IS"):
            aday = temiz + ".IS"
            try:
                if not yf.Ticker(aday).history(period="3d").empty:
                    return aday
            except:
                pass
    
    try:
        arama_sonuclari = yf.Search(temiz, max_results=3).quotes
        if arama_sonuclari:
            en_iyi = arama_sonuclari[0].get('symbol')
            if en_iyi:
                if piyasa == "tr" and not en_iyi.endswith(".IS") and "." not in en_iyi:
                    return en_iyi + ".IS"
                return en_iyi
    except Exception as e:
        print(f"⚠️ Akıllı kod çözme hatası: {e}")
        
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
            f"Şirket/Varlık: {hisse_kodu}\n"
            f"Haberler:\n{haber_basliklari}\n\n"
            f"Bu haberlerin hisse üzerindeki etkisini profesyonel ve net bir dille 2 cümleyle özetle."
        )
        
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": "Sen kıdemli bir Türk finans analistisin. Gelen haberler hangi dilde olursa olsun, cevabını KESİNLİKTE ve SADECE akıcı bir Türkçe ile yazmalısın. Asla İngilizce kelime veya cümle kullanma."
                },
                {"role": "user", "content": prompt}
            ],
            model=GROQ_MODEL,
            temperature=0.3,
        )
        
        ai_cevap = chat_completion.choices[0].message.content
        return f"🧠 **GROQ AI HABER ÖZETİ VE YORUMU** 🧠\n\n*{ai_cevap.strip()}*\n\n*İncelenen Son Başlıklar:*\n{haber_basliklari}"
        
    except Exception as e:
        return f"🗞️ *YAPAY ZEKA ANALİZİ:* Yapay zeka modülü şu an cevap veremiyor. (Detay: {str(e)})"

# =========================================================================
# 🔴 GRAFİK & TREND ANALİZİ MODÜLÜ 🔴
# =========================================================================
def grafik_analiz_calistir(message):
    chat_id = message.chat.id
    ham_metin = message.text
    piyasa = kullanici_durumu[chat_id].get('piyasa', 'tr')
    hisse_kodu = akilli_kod_cozucu(ham_metin, piyasa)

    bot.send_message(chat_id, f"📈 **{hisse_kodu}** için gelişmiş teknik grafik ve hareketli ortalamalar çiziliyor...")
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

        grafik_dosya = f"gelismis_grafik_{chat_id}.png"
        try:
            plt.figure(figsize=(10, 5))
            plt.plot(df.index, df['Close'], label='Kapanis Fiyati', color='#1f77b4', linewidth=2)
            plt.plot(df.index, df['SMA20'], label='20 Gunluk SMA (Kisa Trend)', color='#2ca02c', linestyle='--')
            plt.plot(df.index, df['SMA50'], label='50 Gunluk SMA (Orta Trend)', color='#d62728', linestyle='--')
            plt.title(f"{hisse_kodu} - Son 6 Aylik Teknik Trend ve Hareketli Ortalamalar")
            plt.xlabel("Tarih")
            plt.ylabel("Fiyat")
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.savefig(grafik_dosya, bbox_inches='tight')
        finally:
            plt.close()

        grafik_prompt = (
            f"Varlık: {hisse_kodu}\n"
            f"Güncel Fiyat: {guncel_fiyat:.2f}\n"
            f"20 Günlük SMA: {sma20_son:.2f}\n"
            f"50 Günlük SMA: {sma50_son:.2f}\n"
            f"Teknik durum: Fiyat 20 günlük ortalamanın {'üzerinde' if guncel_fiyat > sma20_son else 'altında'}.\n"
            f"Bu teknik görünüme dayanarak yatırımcıya kısa ve orta vadeli trend yönünü, olası destek/direnç mantığını "
            f"profesyonel bir borsa analisti gibi 3 cümleyle tamamen Türkçe olarak açıkla."
        )

        ai_grafik_yorum = "Fiyat hareketli ortalamalar çevresinde denge arıyor."
        if groq_client:
            try:
                res = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "Sen kıdemli bir teknik analiz uzmanısın. Yalnızca Türkçe yazmalısın."},
                        {"role": "user", "content": grafik_prompt}
                    ],
                    model=GROQ_MODEL, temperature=0.3
                )
                ai_grafik_yorum = res.choices[0].message.content.strip()
            except Exception:
                pass

        rapor = (
            f"📈 **{hisse_kodu} GELİŞMİŞ GRAFİK & TREND ANALİZİ** 📈\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 **Anlık Fiyat:** {guncel_fiyat:.2f}\n"
            f"🟢 **20 Günlük SMA (Kısa Vade):** {sma20_son:.2f}\n"
            f"🔴 **50 Günlük SMA (Orta Vade):** {sma50_son:.2f}\n\n"
            f"🧠 **AI Teknik Grafik Yorumu:**\n*{ai_grafik_yorum}*\n━━━━━━━━━━━━━━━━━━━━━━\n"
        )

        with open(grafik_dosya, "rb") as f:
            bot.send_photo(chat_id, photo=f, caption=rapor, parse_mode="Markdown", reply_markup=ana_menu_olustur())

    except Exception as e:
        bot.send_message(chat_id, f"❌ Grafik analizi yapılırken hata oluştu: {str(e)}", reply_markup=ana_menu_olustur())
    finally:
        if os.path.exists(grafik_dosya):
            try:
                os.remove(grafik_dosya)
            except:
                pass

def p_hisse_al(message):
    chat_id = message.chat.id
    ham_metin = message.text
    piyasa = kullanici_durumu[chat_id]['piyasa']
    hisse_kodu = akilli_kod_cozucu(ham_metin, piyasa)

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
                f"⚠️ '{ham_metin}' tam olarak bulunamadı. Bunlardan birini mi demek istedin?\n\n{oneri_metni}\n\n"
                f"Doğru kodu yazar mısın?",
            )
        else:
            msg = bot.send_message(chat_id, f"⚠️ '{ham_metin}' bulunamadı. Kodu kontrol edip tekrar yazar mısın?")
        bot.register_next_step_handler(msg, p_hisse_al)
        return

    kullanici_durumu[chat_id]['p_hisse'] = hisse_kodu
    msg = bot.send_message(chat_id, f"✅ Algılanan varlık: **{hisse_kodu}**\nMaliyetin nedir? (Örn: 245.50):", parse_mode="Markdown")
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
        
        kullanici_portfoy[chat_id_str]['hisseler'][hisse] = {
            'maliyet': maliyet, 
            'lot': lot,
            'son_alarm_fiyati': maliyet # Yeni eklenen hisse için referans fiyat maliyettir
        }
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
    hisse = akilli_kod_cozucu(message.text, kullanici_durumu[message.chat.id]['piyasa'])
    kullanici_durumu[message.chat.id]['hisse1'] = hisse
    butce_sorusu_sun(message.chat.id)

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
    bot.send_message(chat_id, "⚖️ İki varlık ringe çıkarılıyor, Groq AI düello senaryosu oluşturuluyor...")
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
                ai_duello_yorum = res.choices[0].message.content.strip()
            except Exception:
                pass
        
        chat_id_str = str(chat_id)
        cuzdan = kullanici_portfoy[chat_id_str]['hisseler']
        cuzdan_metni = ""
        if h1 in cuzdan: cuzdan_metni += f"• **{h1}** cüzdanında mevcut.\n"
        if h2 in cuzdan: cuzdan_metni += f"• **{h2}** cüzdanında mevcut.\n"

        rapor = (f"⚖️ KAPSAMLI DÜELLO PROJEKSİYONU: {h1} vs {h2}\n━━━━━━━━━━━━━━━━━━━━━━\n")
        if cuzdan_metni: rapor += f"💼 CÜZDAN EŞLEŞMESİ:\n{cuzdan_metni}\n"
            
        rapor += (
            f"🧠 **GROQ AI DÜELLO YORUMU:**\n*{ai_duello_yorum}*\n\n"
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
        bot.send_message(chat_id, f"❌ Düello yapılırken hata oluştu. (Detay: {str(e)})", reply_markup=ana_menu_olustur())


# =========================================================================
# 🔴 KURUMSAL TASARIMLI VE AI DESTEKLİ PDF RAPORU SİSTEMİ 🔴
# =========================================================================

def tr_to_eng(metin):
    metin = str(metin)
    degisimler = {
        "ğ": "g", "ş": "s", "ı": "i", "ç": "c", "ö": "o", "ü": "u",
        "Ğ": "G", "Ş": "S", "İ": "I", "Ç": "C", "Ö": "O", "Ü": "U",
        "₺": "TL", "—": "-", "–": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "…": "..."
    }
    for eski, yeni in degisimler.items():
        metin = metin.replace(eski, yeni)
    return metin.encode('latin-1', 'replace').decode('latin-1')

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
        cuzdan = kullanici_portfoy[chat_id_str]['hisseler']
        
        odak_hisse = list(cuzdan.keys())[0] if cuzdan else "XU100.IS"
        veri = yf.Ticker(odak_hisse).history(period="6mo")
        
        if veri.empty or len(veri) < 5:
            bot.send_message(chat_id, "⚠️ Grafik çizimi için yeterli veri alınamadı. Lütfen birazdan tekrar deneyin.", reply_markup=ana_menu_olustur())
            return
            
        try:
            plt.figure(figsize=(9, 3.8))
            plt.plot(veri.index, veri['Close'], color='#1f77b4', linewidth=2, label='Fiyat')
            plt.plot(veri.index, veri['Close'].rolling(window=50).mean(), color='#ff7f0e', linestyle='--', label='50 Gun SMA')
            plt.title(f"{odak_hisse} Fiyat Hareketleri ve Trend Analizi")
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.savefig(grafik_dosya, bbox_inches='tight')
        finally:
            plt.close()

        usd = yf.Ticker("TRY=X").fast_info['last_price']
        gold = yf.Ticker("GC=F").fast_info['last_price']
        btc = yf.Ticker("BTC-USD").fast_info['last_price']

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
        
        pdf.cell(0, 6, txt=f"Guncel Risk Profiliniz: {tr_to_eng(kullanici_portfoy[chat_id_str]['risk_profili']).upper()}", ln=True)
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
                    top_yat += v['maliyet'] * v['lot']
                    top_gun += g_fiyat * v['lot']
                    durum = "KAR" if kar > 0 else "ZARAR"
                    satir = f"-> Varlik: {h} | Adet: {v['lot']} | Maliyet: {v['maliyet']:.2f} | Guncel: {g_fiyat:.2f} | Durum: {kar:+.2f} ({durum})"
                    pdf.cell(0, 6, txt=tr_to_eng(satir), ln=True)
                except Exception as e:
                    print(f"⚠️ PDF varlık satırı hatası: {e}")
            
            pdf.ln(2)
            fark = top_gun - top_yat
            genel = "POZITIF" if fark > 0 else "NEGATIF"
            ozet_metin = f"TOPLAM YATIRIM: {top_yat:.2f} TL   |   GUNCEL DEGER: {top_gun:.2f} TL\nNET DURUM: {fark:+.2f} TL ({genel})"
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
        except Exception as e:
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
                try:
                    os.remove(dosya)
                except Exception as e:
                    print(f"⚠️ Geçici dosya silinemedi ({dosya}): {e}")

# =========================================================================
# 🔴 AKILLI ALARM VE HABER SİSTEMİ (2 SAATTE BİR) 🔴
# =========================================================================

gonderilen_haberler = set()

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
                    if len(gonderilen_haberler) > 1000:
                        gonderilen_haberler.clear()
                        
                    # Groq AI'ye haberin kritik olup olmadığını sor
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
                        except Exception as e:
                            print(f"⚠️ Groq haber analizi hatası: {e}")
                            
            hisse_verileri[hisse] = {'fiyat': fiyat, 'haber': kritik_haber}
        except Exception as e:
            print(f"⚠️ {hisse} alarm kontrolünde hata: {e}")
            
    # Kullanıcılara akıllı bildirimleri gönder (Sadece yeni %2.5'lik hareketlerde spam yapmadan)
    for chat_id_str, portfoy in kullanici_portfoy.items():
        chat_id = int(chat_id_str)
        cuzdan = portfoy.get('hisseler', {})
        degisiklik_oldu_mu = False
        
        for hisse, veriler in cuzdan.items():
            if hisse not in hisse_verileri:
                continue
                
            guncel_fiyat = hisse_verileri[hisse]['fiyat']
            maliyet = veriler['maliyet']
            referans_fiyat = veriler.get('son_alarm_fiyati', maliyet)
            
            anlik_degisim_yuzdesi = ((guncel_fiyat - referans_fiyat) / referans_fiyat) * 100
            toplam_degisim_yuzdesi = ((guncel_fiyat - maliyet) / maliyet) * 100
            
            if anlik_degisim_yuzdesi >= 2.5:
                try:
                    bot.send_message(chat_id, f"🚨 **HAREKETLİLİK ALARMI (YÜKSELİŞ)** 🚨\nCüzdanındaki **{hisse}** hareketlendi!\n• Maliyetin: {maliyet:.2f}\n• Anlık Fiyat: {guncel_fiyat:.2f} (Toplam Kâr/Zarar: %{toplam_degisim_yuzdesi:+.2f})")
                    kullanici_portfoy[chat_id_str]['hisseler'][hisse]['son_alarm_fiyati'] = guncel_fiyat
                    degisiklik_oldu_mu = True
                except: pass
            elif anlik_degisim_yuzdesi <= -2.5:
                try:
                    bot.send_message(chat_id, f"🚨 **HAREKETLİLİK ALARMI (DÜŞÜŞ)** 🚨\nCüzdanındaki **{hisse}** sert düştü!\n• Maliyetin: {maliyet:.2f}\n• Anlık Fiyat: {guncel_fiyat:.2f} (Toplam Kâr/Zarar: %{toplam_degisim_yuzdesi:+.2f})")
                    kullanici_portfoy[chat_id_str]['hisseler'][hisse]['son_alarm_fiyati'] = guncel_fiyat
                    degisiklik_oldu_mu = True
                except: pass
                
            kritik_haber = hisse_verileri[hisse]['haber']
            if kritik_haber:
                try:
                    bot.send_message(chat_id, f"📰 **KRİTİK HABER ALARMI!** 📰\nPortföyündeki **{hisse}** için piyasayı sarsabilecek yeni bir gelişme var:\n\n📌 *{kritik_haber}*")
                except: pass

        if degisiklik_oldu_mu:
            veritabanina_kaydet()

schedule.every().day.at("08:30").do(otomatik_sabah_bulteni)
schedule.every(2).hours.do(otomatik_alarm_kontrolu) # Döngü 2 saate çıkarıldı

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
    return "Finans Botu 7/24 Webhook ve AI Destekli Gelişmiş Finans Terminali ile Çalışıyor!"

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
