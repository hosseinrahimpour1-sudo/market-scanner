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
DIFF_THRESHOLD = -5          # درصد افت از EMA برای صدور هشدار
REQUIRE_RED_CANDLES = True   # شرط ۳ کندل قرمز روزانه قبل از کندل فعلی
CYCLE_SECONDS = 300          # فاصله بین هر چرخه‌ی کامل اسکن (۵ دقیقه)
REQUEST_TIMEOUT = 15
CRYPTO_RANK_LIMIT = 300      # فقط ۳۰۰ ارز برتر بر اساس حجم معاملات ۲۴ ساعته (رنک نقدشوندگی)


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

# نمادهای پرمعامله‌ی بورس تهران (کد L18 که در تسدمتسی استفاده میشه)
# چون بورس تهران داده‌ی درون‌روزی (۳۰ دقیقه‌ای) آزاد و رسمی نداره، این بخش صرفاً از داده‌ی روزانه استفاده می‌کنه
TSE_SYMBOLS = {
    "فولاد": "فولاد مبارکه اصفهان", "فملی": "ملی صنایع مس ایران", "خودرو": "ایران خودرو",
    "خساپا": "سایپا", "شپنا": "پالایش نفت اصفهان", "شبندر": "پالایش نفت بندرعباس",
    "فارس": "پتروشیمی فارس", "پارس": "پتروشیمی پارس", "وبملت": "بانک ملت",
    "وتجارت": "بانک تجارت", "وبصادر": "بانک صادرات ایران", "شستا": "سرمایه‌گذاری تامین اجتماعی",
    "کگل": "معدنی و صنعتی گل‌گهر", "کچاد": "معدنی و صنعتی چادرملو", "رمپنا": "گروه مپنا",
    "شتران": "پالایش نفت تهران", "همراه": "ارتباطات سیار ایران", "وغدیر": "سرمایه‌گذاری غدیر",
    "فخوز": "فولاد خوزستان", "کاوه": "فولاد کاوه جنوب کیش", "نوری": "پتروشیمی نوری",
    "شپدیس": "پتروشیمی پردیس", "جم": "پتروشیمی جم", "زاگرس": "پتروشیمی زاگرس",
    "فایرا": "آلومینیوم ایران", "وپاسار": "بانک پاسارگاد", "اخابر": "مخابرات ایران",
    "شفن": "پتروشیمی فناوران", "کیمیا": "معدنی کیمیای زنجان گستران",
}


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


def had_three_red_days_by_close(closes):
    """
    برای بورس تهران که 'باز شدن' رسمی هر روز مثل کریپتو معنی نداره،
    قرمز بودن روز رو بر اساس پایین‌تر بودن قیمت پایانی نسبت به روز قبل می‌سنجیم
    (همون منطقی که اکثر سکوهای بورس ایران برای رنگ کندل روزانه استفاده می‌کنن).
    """
    if len(closes) < 5:
        return False
    for i in (-4, -3, -2):
        if not (closes[i] < closes[i - 1]):
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
            caption = (
                f"🪙 ⚠️ [کریپتو] هشدار ریزش از EMA!\n"
                f"نماد: {display_name}\n"
                f"تایم‌فریم EMA: 30m | تایم‌فریم کندل قرمز: روزانه\n"
                f"قیمت: {current_price}\n"
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
# بخش بورس تهران (TSETMC) - آزمایشی
# ============================
# توجه: بورس تهران API رسمی و رایگان نداره. اینجا از کتابخانه‌ی غیررسمی «tsetmc» استفاده میشه
# که ممکنه به‌مرور با تغییرات سایت tsetmc.com از کار بیفته. اگه خطا بده، فقط همین بخش غیرفعال
# میشه و بقیه‌ی ربات (کریپتو و سهام آمریکا) عادی کار می‌کنه.
# چون داده‌ی درون‌روزی (۳۰ دقیقه‌ای) رسمی برای بورس تهران در دسترس نیست، همه‌چیز روی
# تایم‌فریم روزانه محاسبه میشه (هم EMA و هم شرط ۳ کندل قرمز).
def check_tehran_stocks_market():
    try:
        from tsetmc.instruments import Instrument
    except Exception as e:
        log(f"⚠️ کتابخانه‌ی tsetmc در دسترس نیست ({e})؛ اسکن بورس تهران رد شد.")
        return

    total = len(TSE_SYMBOLS)
    log(f"[بورس تهران] {total} نماد پیدا شد.")

    for index, (l18, fa_full_name) in enumerate(TSE_SYMBOLS.items(), 1):
        try:
            inst = Instrument.from_l18(l18)
            page = inst.page_data(trade_history=True)
            hist = page.get("trade_history")
            if hist is None or len(hist) < 5:
                continue
            hist = hist.sort_index()

            closes = hist["pc"].astype(float).tolist()
            current_price = closes[-1]
            ema_value = calculate_ema(closes, EMA_PERIOD)
            if not ema_value:
                continue

            diff_percent = ((current_price - ema_value) / ema_value) * 100
            if diff_percent > DIFF_THRESHOLD:
                continue

            if REQUIRE_RED_CANDLES:
                if not had_three_red_days_by_close(closes):
                    continue

            daily_df = pd.DataFrame({
                "Open": hist["py"].astype(float),   # تقریبی: چون «باز شدن» رسمی در این منبع نیست
                "High": hist["pmax"].astype(float),
                "Low": hist["pmin"].astype(float),
                "Close": hist["pc"].astype(float),
            })

            caption = (
                f"🇮🇷 ⚠️ [بورس تهران] هشدار ریزش از EMA!\n"
                f"نماد: {l18} ({fa_full_name})\n"
                f"تایم‌فریم: روزانه (داده درون‌روزی برای بورس تهران در دسترس نیست)\n"
                f"قیمت پایانی: {current_price}\n"
                f"EMA{EMA_PERIOD}: {ema_value:.4f}\n"
                f"فاصله: {diff_percent:.2f}%\n"
                f"⚠️ لینک تردینگ‌ویو برای بورس تهران پشتیبانی نمیشه."
            )
            log(caption)

            chart = make_candlestick_chart(daily_df, title=f"{l18} - Daily")
            if chart:
                send_telegram_photo(chart, caption)
            else:
                send_telegram_message(caption)
        except Exception as e:
            log(f"خطا در پردازش نماد بورس تهران {l18}: {e}")

        if index % 10 == 0:
            log(f"[بورس تهران] {index}/{total} اسکن شد...")
        time.sleep(0.3)


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
