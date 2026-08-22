# -*- coding: utf-8 -*-
import requests
import time
import os
import io
import traceback
from urllib.parse import quote
import yfinance as yf
import pandas as pd
import mplfinance as mpf

# ============================
# تنظیمات اصلی
# ============================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

EMA_PERIOD = 5
DIFF_THRESHOLD = -5          # درصد افت از EMA برای صدورر هشدار
REQUIRE_RED_CANDLES = True   # شرط ۳ کندل قرمز روزانه قبل از کندل فعلی
CYCLE_SECONDS = 300          # فاصله بین هر چرخه‌ی کامل اسکن (۵ دقیقه)
REQUEST_TIMEOUT = 15
CRYPTO_RANK_LIMIT = 300      # فقط ۳۰۰ ارز برتر بر اساس حجم معاملات ۲۴ ساعته (رنک نقدشوندگی)
TSE_RANK_LIMIT = 200         # فقط ۲۰۰ نماد برتر بورس تهران بر اساس حجم معاملات امروز
FROZEN_TOLERANCE = 0.0001    # اگه فاصله قیمت-EMA به این میزان یا کمتر تغییر کنه، نماد "مرده" حساب میشه
IRAN_BROKER_CHECK_TIMEOUT = 8

# ============================
# دیکشنری نام فارسی/انگلیسی نمادهای پرکاربرد
# (برای نمادهایی که اینجا نباشن، فقط خود نماد نمایش داده میشه)
# ============================
CRYPTO_NAMES = {
    "BTCUSDT": ("Bitcoin", "بیت کوین"), "ETHUSDT": ("Ethereum", "اتریوم"),
    "BNBUSDT": ("BNB", "بایننس کوین"), "SOLUSDT": ("Solana", "سولانا"),
    "XRPUSDT": ("XRP", "ریپل"), "ADAUSDT": ("Cardano", "کاردانو"),
    "DOGEUSDT": ("Dogecoin", "دوج کوین"), "TRXUSDT": ("TRON", "ترون"),
    "TONUSDT": ("Toncoin", "تون کوین"), "AVAXUSDT": ("Avalanche", "آوالانچ"),
    "SHIBUSDT": ("Shiba Inu", "شیبا اینو"), "DOTUSDT": ("Polkadot", "پولکادات"),
    "LINKUSDT": ("Chainlink", "چین لینک"), "MATICUSDT": ("Polygon", "پالیگان"),
    "LTCUSDT": ("Litecoin", "لایت کوین"), "BCHUSDT": ("Bitcoin Cash", "بیت کوین کش"),
    "ICPUSDT": ("Internet Computer", "اینترنت کامپیوتر"), "NEARUSDT": ("NEAR Protocol", "نی یر پروتکل"),
    "UNIUSDT": ("Uniswap", "یونی سواپ"), "APTUSDT": ("Aptos", "اپتوس"),
    "XLMUSDT": ("Stellar", "استلار"), "ETCUSDT": ("Ethereum Classic", "اتریوم کلاسیک"),
    "FILUSDT": ("Filecoin", "فایل کوین"), "ATOMUSDT": ("Cosmos", "کازماس"),
    "IMXUSDT": ("Immutable", "ایموتبل"), "OPUSDT": ("Optimism", "اپتیمیزم"),
    "ARBUSDT": ("Arbitrum", "آربیتروم"), "HBARUSDT": ("Hedera", "هدرا"),
    "VETUSDT": ("VeChain", "وی چین"), "MKRUSDT": ("Maker", "میکر"),
    "INJUSDT": ("Injective", "اینجکتیو"), "GRTUSDT": ("The Graph", "د گراف"),
    "RUNEUSDT": ("THORChain", "تورچین"), "AAVEUSDT": ("Aave", "آوه"),
    "ALGOUSDT": ("Algorand", "الگورند"), "SANDUSDT": ("The Sandbox", "سندباکس"),
    "MANAUSDT": ("Decentraland", "دیسنترالند"), "EOSUSDT": ("EOS", "ایاواس"),
    "XTZUSDT": ("Tezos", "تزوس"), "THETAUSDT": ("Theta Network", "تتا نتورک"),
    "FTMUSDT": ("Fantom", "فانتوم"), "PEPEUSDT": ("Pepe", "په په"),
    "WIFUSDT": ("dogwifhat", "داگ ویف هت"), "SUIUSDT": ("Sui", "سویی"),
    "SEIUSDT": ("Sei", "سی ای"), "TIAUSDT": ("Celestia", "سلستیا"),
    "PYTHUSDT": ("Pyth Network", "پیث نتورک"), "JUPUSDT": ("Jupiter", "جوپیتر"),
    "RNDRUSDT": ("Render", "رندر"), "STXUSDT": ("Stacks", "استکس"),
}

STOCK_NAMES = {
    "AAPL": ("Apple Inc.", "اپل"), "MSFT": ("Microsoft Corporation", "مایکروسافت"),
    "NVDA": ("NVIDIA Corporation", "انویدیا"), "GOOGL": ("Alphabet Inc. (Class A)", "آلفابت - گوگل"),
    "GOOG": ("Alphabet Inc. (Class C)", "آلفابت - گوگل"), "AMZN": ("Amazon.com Inc.", "آمازون"),
    "META": ("Meta Platforms Inc.", "متا - فیسبوک"), "AVGO": ("Broadcom Inc.", "برادکام"),
    "TSLA": ("Tesla Inc.", "تسلا"), "BRK-B": ("Berkshire Hathaway Inc.", "برکشایر هاتاوی"),
    "JPM": ("JPMorgan Chase & Co.", "جی پی مورگان چیس"), "LLY": ("Eli Lilly and Company", "ایلای لیلی"),
    "V": ("Visa Inc.", "ویزا"), "UNH": ("UnitedHealth Group Inc.", "یونایتد هلث گروپ"),
    "XOM": ("Exxon Mobil Corporation", "اکسون موبیل"), "MA": ("Mastercard Inc.", "مسترکارت"),
    "COST": ("Costco Wholesale Corporation", "کاستکو"), "HD": ("The Home Depot Inc.", "هوم دیپو"),
    "PG": ("Procter & Gamble Co.", "پراکتر اند گمبل"), "NFLX": ("Netflix Inc.", "نتفلیکس"),
    "JNJ": ("Johnson & Johnson", "جانسون اند جانسون"), "WMT": ("Walmart Inc.", "والمارت"),
    "BAC": ("Bank of America Corporation", "بانک آو امریکا"), "CRM": ("Salesforce Inc.", "سیلزفورس"),
    "ABBV": ("AbbVie Inc.", "ابوی"), "CVX": ("Chevron Corporation", "شورون"),
    "KO": ("The Coca-Cola Company", "کوکاکولا"), "MRK": ("Merck & Co. Inc.", "مرک"),
    "AMD": ("Advanced Micro Devices Inc.", "ای ام دی"), "PEP": ("PepsiCo Inc.", "پپسی کو"),
    "ORCL": ("Oracle Corporation", "اوراکل"), "ADBE": ("Adobe Inc.", "ادوبی"),
    "TMO": ("Thermo Fisher Scientific Inc.", "ترمو فیشر"), "LIN": ("Linde plc", "لیندی"),
    "MCD": ("McDonald's Corporation", "مک دونالد"), "CSCO": ("Cisco Systems Inc.", "سیسکو"),
    "ACN": ("Accenture plc", "اکسنچر"), "ABT": ("Abbott Laboratories", "ابوت"),
    "WFC": ("Wells Fargo & Company", "ولز فارگو"), "DIS": ("The Walt Disney Company", "والت دیزنی"),
    "IBM": ("International Business Machines Corp.", "آی بی ام"), "GE": ("General Electric Company", "جنرال الکتریک"),
    "PM": ("Philip Morris International Inc.", "فیلیپ موریس"), "CAT": ("Caterpillar Inc.", "کاترپیلار"),
    "TXN": ("Texas Instruments Inc.", "تگزاس اینسترومنتس"), "NOW": ("ServiceNow Inc.", "سرویس ناو"),
    "INTU": ("Intuit Inc.", "اینتویت"), "ISRG": ("Intuitive Surgical Inc.", "اینتوییتیو سرجیکال"),
    "VZ": ("Verizon Communications Inc.", "وریزون"), "QCOM": ("Qualcomm Inc.", "کوالکام"),
    "AMGN": ("Amgen Inc.", "امجن"), "CMCSA": ("Comcast Corporation", "کامکست"),
    "SPGI": ("S&P Global Inc.", "اس اند پی گلوبال"), "UBER": ("Uber Technologies Inc.", "اوبر"),
    "BKNG": ("Booking Holdings Inc.", "بوکینگ"), "NEE": ("NextEra Energy Inc.", "نکست ارا انرژی"),
    "PFE": ("Pfizer Inc.", "فایزر"), "AMAT": ("Applied Materials Inc.", "اپلاید متریالز"),
    "RTX": ("RTX Corporation", "آر تی ایکس"), "LOW": ("Lowe's Companies Inc.", "لوز"),
    "UNP": ("Union Pacific Corporation", "یونیون پسیفیک"), "T": ("AT&T Inc.", "ای تی اند تی"),
    "HON": ("Honeywell International Inc.", "هانیول"), "COP": ("ConocoPhillips", "کونوکوفیلیپس"),
    "DE": ("Deere & Company", "دیر - جان دیر"), "PGR": ("Progressive Corporation", "پروگرسیو"),
    "GS": ("The Goldman Sachs Group Inc.", "گلدمن ساکس"), "ETN": ("Eaton Corporation plc", "ایتون"),
    "MS": ("Morgan Stanley", "مورگان استنلی"), "SYK": ("Stryker Corporation", "استرایکر"),
    "LMT": ("Lockheed Martin Corporation", "لاکهید مارتین"), "BLK": ("BlackRock Inc.", "بلک راک"),
    "AXP": ("American Express Company", "امریکن اکسپرس"), "SCHW": ("The Charles Schwab Corporation", "چارلز شواب"),
    "TJX": ("The TJX Companies Inc.", "تی جی ایکس"), "BSX": ("Boston Scientific Corporation", "بوستون ساینتیفیک"),
    "MU": ("Micron Technology Inc.", "میکرون تکنولوژی"), "MDT": ("Medtronic plc", "مدترونیک"),
    "ADP": ("Automatic Data Processing Inc.", "ای دی پی"), "VRTX": ("Vertex Pharmaceuticals Inc.", "ورتکس فارماسیوتیکالز"),
    "GILD": ("Gilead Sciences Inc.", "گیلیاد ساینسز"), "PLD": ("Prologis Inc.", "پرولوجیس"),
    "C": ("Citigroup Inc.", "سیتی گروپ"), "ADI": ("Analog Devices Inc.", "آنالوگ دیوایسز"),
    "SBUX": ("Starbucks Corporation", "استارباکس"), "MMC": ("Marsh & McLennan Companies Inc.", "مارش اند مک لنان"),
    "CB": ("Chubb Limited", "چاب"), "REGN": ("Regeneron Pharmaceuticals Inc.", "ریجنرون فارماسیوتیکالز"),
    "PANW": ("Palo Alto Networks Inc.", "پالو آلتو نتورکس"), "ANET": ("Arista Networks Inc.", "آریستا نتورکس"),
    "AMT": ("American Tower Corporation", "امریکن تاور"), "KLAC": ("KLA Corporation", "کی ال ای"),
    "SO": ("The Southern Company", "ساترن کمپانی"), "ELV": ("Elevance Health Inc.", "الوانس هلث"),
    "APH": ("Amphenol Corporation", "امفنول"), "CI": ("The Cigna Group", "سیگنا"),
    "CME": ("CME Group Inc.", "سی ام ای گروپ"), "MO": ("Altria Group Inc.", "آلتریا گروپ"),
    "DUK": ("Duke Energy Corporation", "دیوک انرژی"), "ZTS": ("Zoetis Inc.", "زوئتیس"),
}

# نمادهای بورس تهران دیگه ثابت نیستن — هر چرخه با کتابخانه‌ی algotik-tse به‌صورت زنده
# ۲۰۰ نماد پرحجم‌تر روز از کل بازار استخراج میشن (تابع get_top_tse_symbols پایین‌تر).

# صرافی‌های ایرانی که برای بررسی «آیا این کریپتو در بروکر ایرانی لیست شده» چک میشن
IRAN_CRYPTO_BROKERS = ["نوبیتکس", "والکس"]

# ردیابی «فاصله‌ی قیمت-EMA» هر نماد بین چرخه‌ها، برای تشخیص نماد مرده (بدون تغییر)
LAST_DIFF_STATE = {}

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def get_display_name(symbol, names_dict):
    """برگردوندن رشته‌ی 'نماد (اسم انگلیسی | اسم فارسی)' یا فقط خود نماد اگه پیدا نشد"""
    info = names_dict.get(symbol)
    if info:
        en, fa = info
        return f"{symbol} ({en} | {fa})"
    return symbol


def get_tradingview_link(symbol, market):
    """لینک واقعی و تست‌شده‌ی صفحه‌ی نماد در تردینگ‌ویو"""
    if market == "crypto":
        return f"https://www.tradingview.com/symbols/{quote(symbol)}/?exchange=BINANCE"
    return f"https://www.tradingview.com/symbols/{quote(symbol)}/"


def get_binance_link(symbol):
    """لینک مستقیم صفحه‌ی معامله‌ی نماد در خود بایننس"""
    if symbol.endswith("USDT"):
        base = symbol[:-4]
        return f"https://www.binance.com/en/trade/{quote(base)}_USDT"
    return f"https://www.binance.com/en/trade/{quote(symbol)}"


def is_symbol_frozen(state_key, diff_percent, tolerance=FROZEN_TOLERANCE):
    """
    اگه فاصله‌ی قیمت-EMA این نماد نسبت به چرخه‌ی قبلی عملاً تغییر نکرده باشه،
    یعنی نماد «مرده»/بدون معامله‌ی واقعیه؛ نباید هر چرخه دوباره هشدار بفرسته.
    """
    prev = LAST_DIFF_STATE.get(state_key)
    LAST_DIFF_STATE[state_key] = diff_percent
    if prev is None:
        return False
    return abs(diff_percent - prev) < tolerance


def get_iran_broker_listing(base_currency):
    """
    بررسی اینکه آیا این ارز در صرافی‌های معروف ایرانی (نوبیتکس، والکس) لیست شده.
    این بخش فقط برای نمادهایی که قراره هشدار براشون ارسال بشه صدا زده میشه (حجم کم درخواست).
    اگه هر صرافی در دسترس نبود، فقط از لیست نتیجه رد میشه (خطای کلی رو نمی‌شکنه).
    """
    listed_in = []
    base_lower = base_currency.lower()

# نوبیتکس
    try:
        r = requests.post(
            "https://api.nobitex.ir/market/stats",
            json={"srcCurrency": base_lower, "dstCurrency": "usdt"},
            timeout=IRAN_BROKER_CHECK_TIMEOUT,
        )
        data = r.json()
        if data.get("status") == "ok":
            stats = data.get("stats", {})
            key = f"{base_lower}-usdt"
            if key in stats and stats[key] and not stats[key].get("isClosed", True):
                listed_in.append("نوبیتکس")
    except Exception:
        pass

    # والکس
    try:
        r = requests.get("https://api.wallex.ir/hector/web/v1/markets", timeout=IRAN_BROKER_CHECK_TIMEOUT)
        data = r.json()
        result = data.get("result", data)
        symbols_dict = result.get("symbols", result) if isinstance(result, dict) else {}
        if isinstance(symbols_dict, dict):
            target = f"{base_currency.upper()}USDT"
            target_tmn = f"{base_currency.upper()}TMN"
            if target in symbols_dict or target_tmn in symbols_dict:
                listed_in.append("والکس")
    except Exception:
        pass

    return listed_in


def send_telegram_message(text):
    """ارسال پیام متنی به تلگرام"""
    if not TOKEN or not CHAT_ID:
        log("⚠️ توکن یا چت‌آیدی تنظیم نشده! پیام ارسال نشد.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            log(f"خطای تلگرام (sendMessage): {r.status_code} - {r.text[:200]}")
    except Exception as e:
        log(f"خطا در ارسال پیام تلگرام: {e}")


def send_telegram_photo(image_bytes, caption):
    """ارسال عکس (نمودار شمعی) همراه با کپشن به تلگرام"""
    if not TOKEN or not CHAT_ID:
        log("⚠️ توکن یا چت‌آیدی تنظیم نشده! عکس ارسال نشد.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        files = {"photo": ("chart.png", image_bytes, "image/png")}
        data = {"chat_id": CHAT_ID, "caption": caption}
        r = requests.post(url, data=data, files=files, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            log(f"خطای تلگرام (sendPhoto): {r.status_code} - {r.text[:200]}")
            send_telegram_message(caption)
    except Exception as e:
        log(f"خطا در ارسال عکس: {e}")
        send_telegram_message(caption)


def calculate_ema(prices, period):
    """محاسبه ریاضی اندیکاتور EMA"""
    if len(prices) < period:
        return None
    ema = sum(prices[:period]) / period
    multiplier = 2 / (period + 1)
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


def had_three_red_candles_before_last(opens, closes):
    """
    شرط: سه کندل قبل از کندل آخر (کندل امروز/فعلی) باید همگی قرمز (کاهشی) باشن.
    ایندکس‌های -4، -3، -2 نسبت به آخرین کندل (کندل -1 = کندل فعلی، بررسی نمیشه).
    """
    if len(opens) < 4 or len(closes) < 4:
        return False
    for i in (-4, -3, -2):
        if not (closes[i] < opens[i]):
            return False
    return True


def had_zero_volume_recently(volumes):
    """بررسی اینکه آیا در ۳ کندل قبل از کندل فعلی حجم صفر بوده"""
    if len(volumes) < 4:
        return True  # داده کافی نیست، برای احتیاط رد میشه
    vols_before = volumes[-4:-1]
    return any(v == 0 for v in vols_before)


def make_candlestick_chart(df, title=""):
    """ساخت تصویر کوچیک نمودار شمعی از دیتافریم OHLC و برگردوندن به‌صورت بایت"""
    buf = io.BytesIO()
    try:
        mpf.plot(
            df,
            type="candle",
            style="charles",
            volume=False,
            title=title,
            figsize=(5, 3.2),
            savefig=dict(fname=buf, dpi=90, bbox_inches="tight"),
        )
        buf.seek(0)
        return buf
    except Exception as e:
        log(f"خطا در ساخت نمودار: {e}")
        return None


# ============================
# بخش کریپتو (بایننس)
# ============================
def get_top_ranked_usdt_symbols(limit=CRYPTO_RANK_LIMIT):
    """
    دریافت ارزهای تتر بایننس، رتبه‌بندی بر اساس حجم معاملات ۲۴ ساعته (به‌عنوان معیار نقدشوندگی/رنک)
    و برگردوندن N تای برتر. این کار باعث حذف نمادهای کم‌ارزش و کم‌نقدشوندگی میشه.
    """
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT).json()
        usdt_pairs = [
            item for item in response
            if isinstance(item, dict) and item.get("symbol", "").endswith("USDT")
        ]
        usdt_pairs.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
        return [item["symbol"] for item in usdt_pairs[:limit]]
    except Exception as e:
        log(f"خطا در دریافت و رتبه‌بندی لیست ارزها: {e}")
        return []


def get_crypto_daily_df(symbol, limit=180):
    """گرفتن دیتافریم OHLC روزانه (پیش‌فرض ۶ ماه گذشته) برای یک ارز"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT).json()
        if not isinstance(response, list) or len(response) == 0:
            return None
        df = pd.DataFrame(response, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"
        ])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df.set_index("open_time", inplace=True)
        df = df[["open", "high", "low", "close"]].astype(float)
        df.columns = ["Open", "High", "Low", "Close"]
        return df
    except Exception as e:
        log(f"خطا در دریافت دیتای روزانه {symbol}: {e}")
        return None


def check_crypto_market():
    """اسکن بازار کریپتو (بایننس) - کندل ۳۰ دقیقه‌ای برای EMA، کندل روزانه برای شرط ۳ کندل قرمز"""
    symbols = get_top_ranked_usdt_symbols()
    total = len(symbols)
    log(f"[کریپتو] {total} ارز برتر (بر اساس حجم ۲۴ ساعته) پیدا شد.")

    for index, symbol in enumerate(symbols, 1):
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=30m&limit=10"
            response = requests.get(url, timeout=REQUEST_TIMEOUT).json()
            if not isinstance(response, list) or len(response) < 4:
                continue

            closes = [float(c[4]) for c in response]
            volumes = [float(c[5]) for c in response]
            current_price = closes[-1]
            ema_value = calculate_ema(closes, EMA_PERIOD)
            if not ema_value:
                continue

            diff_percent = ((current_price - ema_value) / ema_value) * 100
            if diff_percent > DIFF_THRESHOLD:
                continue  # شرط افت از EMA برقرار نیست

            if had_zero_volume_recently(volumes):
                continue  # حجم صفر در ۳ کندل قبلی => نماد بی‌کیفیت/غیرفعال

            if is_symbol_frozen(f"crypto:{symbol}", diff_percent):
                continue  # نماد مرده: فاصله قیمت-EMA نسبت به چرخه قبل تغییر نکرده

            daily_df = get_crypto_daily_df(symbol)
            if daily_df is None or len(daily_df) < 4:
                continue

            if REQUIRE_RED_CANDLES:
                if not had_three_red_candles_before_last(
                    daily_df["Open"].tolist(), daily_df["Close"].tolist()
                ):
                    continue

            display_name = get_display_name(symbol, CRYPTO_NAMES)
            tv_link = get_tradingview_link(symbol, "crypto")
            binance_link = get_binance_link(symbol)
            base_currency = symbol[:-4] if symbol.endswith("USDT") else symbol
            brokers = get_iran_broker_listing(base_currency)
            broker_line = f"لیست‌شده در بروکر ایرانی: {', '.join(brokers)}\n" if brokers else ""

            caption = (
                f"🪙 ⚠️ [کریپتو] هشدار ریزش از EMA!\n"
                f"نماد: {display_name}\n"
                f"تایم‌فریم EMA: 30m | تایم‌فریم کندل قرمز: روزانه\n"
                f"قیمت: {current_price}\n"
                f"EMA{EMA_PERIOD}: {ema_value:.4f}\n"
                f"فاصله: {diff_percent:.2f}%\n"
                f"{broker_line}"
                f"نمودار تردینگ‌ویو: {tv_link}\n"
                f"نمودار بایننس: {binance_link}"
            )
            log(caption)

            chart = make_candlestick_chart(daily_df, title=f"{symbol} - 6M Daily")
            if chart:
                send_telegram_photo(chart, caption)
            else:
                send_telegram_message(caption)
        except Exception as e:
            log(f"خطا در پردازش {symbol}: {e}")

        if index % 50 == 0:
            log(f"[کریپتو] {index}/{total} اسکن شد...")
        time.sleep(0.15)


# ============================
# بخش سهام آمریکا (Yahoo Finance)
# ============================
def get_top100_us_symbols():
    return list(STOCK_NAMES.keys())


def check_us_stocks_market():
    """اسکن ۱۰۰ شرکت بزرگ آمریکا - کندل ۳۰ دقیقه‌ای برای EMA، کندل روزانه برای شرط ۳ کندل قرمز"""
    symbols = get_top100_us_symbols()
    total = len(symbols)
    log(f"[سهام] {total} نماد پیدا شد.")

    for index, symbol in enumerate(symbols, 1):
        try:
            data30 = yf.download(symbol, period="5d", interval="30m", progress=False)
            if data30.empty or len(data30) < EMA_PERIOD or len(data30) < 4:
                continue

            closes = data30["Close"].values.flatten().tolist()
            volumes = data30["Volume"].values.flatten().tolist()
            current_price = closes[-1]
            ema_value = calculate_ema(closes, EMA_PERIOD)
            if not ema_value:
                continue

            diff_percent = ((current_price - ema_value) / ema_value) * 100
            if diff_percent > DIFF_THRESHOLD:
                continue

            if had_zero_volume_recently(volumes):
                continue

            if is_symbol_frozen(f"stock:{symbol}", diff_percent):
                continue  # نماد مرده: فاصله قیمت-EMA نسبت به چرخه قبل تغییر نکرده

            daily_data = yf.download(symbol, period="6mo", interval="1d", progress=False)
            if daily_data.empty or len(daily_data) < 4:
                continue
            daily_df = daily_data[["Open", "High", "Low", "Close"]].copy()

            if REQUIRE_RED_CANDLES:
                if not had_three_red_candles_before_last(
                    daily_df["Open"].values.flatten().tolist(),
                    daily_df["Close"].values.flatten().tolist(),
                ):
                    continue

            display_name = get_display_name(symbol, STOCK_NAMES)
            tv_link = get_tradingview_link(symbol, "stock")
            caption = (
                f"📈 ⚠️ [سهام آمریکا] هشدار ریزش از EMA!\n"
                f"نماد: {display_name}\n"
                f"تایم‌فریم EMA: 30m | تایم‌فریم کندل قرمز: روزانه\n"
                f"قیمت: {current_price:.2f}\n"
                f"EMA{EMA_PERIOD}: {ema_value:.4f}\n"
                f"فاصله: {diff_percent:.2f}%\n"
                f"نمودار تردینگ‌ویو: {tv_link}"
            )
            log(caption)

            chart = make_candlestick_chart(daily_df, title=f"{symbol} - 6M Daily")
            if chart:
                send_telegram_photo(chart, caption)
            else:
                send_telegram_message(caption)
        except Exception as e:
            log(f"خطا در پردازش {symbol}: {e}")

        if index % 25 == 0:
            log(f"[سهام] {index}/{total} اسکن شد...")
        time.sleep(0.15)


# ============================
# بخش بورس تهران (TSETMC) - از کتابخانه‌ی مستندسازی‌شده‌ی algotik-tse استفاده میشه
# ============================
# توجه: بورس تهران API رسمی و رایگان نداره؛ algotik-tse داده رو از tsetmc.com می‌خونه و
# ممکنه به‌مرور با تغییرات اون سایت از کار بیفته. اگه خطا بده، فقط همین بخش غیرفعال میشه
# و بقیه‌ی ربات (کریپتو و سهام آمریکا) عادی کار می‌کنه.
# چون داده‌ی درون‌روزی رسمی و پایدار برای بورس تهران در دسترس نیست، هم EMA و هم شرط
# ۳ کندل قرمز روی تایم‌فریم روزانه محاسبه میشه. نمادها هر چرخه به‌صورت زنده بر اساس
# حجم معاملات امروز رتبه‌بندی میشن (نه یه لیست ثابت دستی).
TSE_STOCK_TYPES = [300, 303, 309]  # کد نوع ابزار برای سهام عادی (بورس/فرابورس)


def get_top_tse_symbols(limit=TSE_RANK_LIMIT):
    """گرفتن اسنپ‌شات لحظه‌ای کل بازار و برگردوندن N نماد پرحجم‌تر (فقط سهام عادی، نه صندوق/اختیار/اوراق)"""
    import algotik_tse as att
    data = att.get_market_snapshot()
    stocks_df = data["stocks"]
    real = stocks_df[stocks_df["InstrumentType"].isin(TSE_STOCK_TYPES)].copy()
    real = real.sort_values("Volume", ascending=False)
    names = dict(zip(real["Symbol"], real["Name"]))
    top_symbols = real["Symbol"].head(limit).tolist()
    return top_symbols, names


def check_tehran_stocks_market():
    try:
        import algotik_tse as att
    except Exception as e:
        log(f"⚠️ کتابخانه‌ی algotik-tse در دسترس نیست ({e})؛ اسکن بورس تهران رد شد.")
        return

    try:
        top_symbols, names = get_top_tse_symbols()
    except Exception as e:
        log(f"خطا در دریافت اسنپ‌شات بازار بورس تهران: {e}")
        return

    total = len(top_symbols)
    log(f"[بورس تهران] {total} نماد برتر (بر اساس حجم امروز) پیدا شد.")

    # دریافت دسته‌جمعی ۱۰ روز آخر برای همه‌ی نمادها در یک درخواست (به‌جای ۲۰۰ درخواست جدا)
    try:
        hist_all = att.get_history(top_symbols, limit=10, progress=False, dropna=False)
    except Exception as e:
        log(f"خطا در دریافت تاریخچه‌ی دسته‌جمعی بورس تهران: {e}")
        return

    for index, symbol in enumerate(top_symbols, 1):
        try:
            if symbol not in hist_all.columns.get_level_values(1):
                continue
            opens = hist_all[("Open", symbol)].dropna().tolist()
            closes = hist_all[("Close", symbol)].dropna().tolist()
            if len(closes) < 4:
                continue

            current_price = closes[-1]
            ema_value = calculate_ema(closes, EMA_PERIOD)
            if not ema_value:
                continue

            diff_percent = ((current_price - ema_value) / ema_value) * 100
            if diff_percent > DIFF_THRESHOLD:
                continue

            if is_symbol_frozen(f"tse:{symbol}", diff_percent):
                continue  # نماد مرده: فاصله قیمت-EMA نسبت به چرخه قبل تغییر نکرده

            if REQUIRE_RED_CANDLES:
                if not had_three_red_candles_before_last(opens, closes):
                    continue

            # نمودار ۶ ماهه‌ی جداگانه فقط برای نمادی که واجد شرایط شده
            daily_df = att.get_history(symbol, limit=180, progress=False)
            if daily_df is None or len(daily_df) < 4:
                continue

            fa_full_name = names.get(symbol, "")
            caption = (
                f"🇮🇷 ⚠️ [بورس تهران] هشدار ریزش از EMA!\n"
                f"نماد: {symbol} ({fa_full_name})\n"
                f"تایم‌فریم: روزانه (داده درون‌روزی رسمی برای بورس تهران در دسترس نیست)\n"
                f"قیمت پایانی: {current_price}\n"
                f"EMA{EMA_PERIOD}: {ema_value:.4f}\n"
                f"فاصله: {diff_percent:.2f}%\n"
                f"⚠️ لینک تردینگ‌ویو برای بورس تهران پشتیبانی نمیشه."
            )
            log(caption)

            chart = make_candlestick_chart(daily_df, title=f"{symbol} - 6M Daily")
            if chart:
                send_telegram_photo(chart, caption)
            else:
                send_telegram_message(caption)
        except Exception as e:
            log(f"خطا در پردازش نماد بورس تهران {symbol}: {e}")

        if index % 40 == 0:
            log(f"[بورس تهران] {index}/{total} اسکن شد...")


# ============================
# حلقه اصلی برنامه
# ============================
if __name__ == "__main__":
    log("ربات اسکنر چند-بازاره روشن شد...")

    if not TOKEN or not CHAT_ID:
        log("⚠️⚠️⚠️ هشدار: TELEGRAM_TOKEN یا TELEGRAM_CHAT_ID تنظیم نشده! لطفاً توی Railway Variables تنظیم کن.")

    send_telegram_message(
        f"✅ ربات اسکنر کریپتو + ۱۰۰ سهام برتر آمریکا + بورس تهران (EMA{EMA_PERIOD}) روشن شد!\n"
        f"چرخه هر {CYCLE_SECONDS} ثانیه اجرا میشه."
    )

    while True:
        start_time = time.time()

        try:
            check_crypto_market()
        except Exception as e:
            log(f"خطای کلی در اسکن کریپتو: {e}\n{traceback.format_exc()}")

        try:
            check_us_stocks_market()
        except Exception as e:
            log(f"خطای کلی در اسکن سهام: {e}\n{traceback.format_exc()}")

        try:
            check_tehran_stocks_market()
        except Exception as e:
            log(f"خطای کلی در اسکن بورس تهران: {e}\n{traceback.format_exc()}")

        elapsed = time.time() - start_time
        log(f"یک چرخه کامل در {elapsed:.1f} ثانیه تمام شد.")

        remaining = CYCLE_SECONDS - elapsed
        if remaining > 0:
            log(f"در حال استراحت به مدت {remaining:.1f} ثانیه...")
            time.sleep(remaining)
