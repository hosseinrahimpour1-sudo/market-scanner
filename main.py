# -*- coding: utf-8 -*-
import os
import io
import json
import time
import hmac
import hashlib
import sqlite3
import threading
import traceback
from decimal import Decimal, ROUND_DOWN
from urllib.parse import quote

import requests
import pandas as pd
import mplfinance as mpf
import yfinance as yf

# ==================================================================
# بخش ۱: تنظیمات اصلی
# ==================================================================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

EMA_PERIOD = 5
DIFF_THRESHOLD = -7          # <-- خودتون عووض کنید (مثلاً -7 یعنی ۷٪ زیر EMA5)
REQUIRE_RED_CANDLES = True
RED_CANDLE_USE_DAILY = False
INTRADAY_DISPLAY_DAYS = 2
CYCLE_SECONDS = 300
REQUEST_TIMEOUT = 15
CRYPTO_RANK_LIMIT = 300
TSE_RANK_LIMIT = 200
ALERT_COOLDOWN_SECONDS = 6 * 3600
FROZEN_TOLERANCE = 1.0
IRAN_BROKER_CHECK_TIMEOUT = 8

# --- شرط پیوت (مبنای اصلی استراتژی: ورود در S2 یا S3) -----------------
REQUIRE_PIVOT_CONDITION = True
PIVOT_TYPE = "fibonacci"          # "fibonacci" یا "camarilla"
PIVOT_ENTRY_LEVELS = ["S2", "S3"]  # قیمت باید به یکی از این‌ها رسیده باشه

# --- معامله‌ی نیمه‌خودکار --------------------------------------------
DRY_RUN = True                     # تا مطمئن نشدید False نکنید!
TEST_TRADE_AMOUNT_USDT = 6
TAKE_PROFIT_PERCENT = 3.0          # <-- «مثلاً ۳ درصد بالای قیمت خرید»
STOP_LOSS_OPTIONS = [3, 5, 8, 10]  # درصدهای پیشنهادی حد ضرر که موقع خرید نشون داده میشن

BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET")
NOBITEX_TOKEN = os.environ.get("NOBITEX_TOKEN")

# فقط همین آیدی‌های عددی تلگرام اجازه‌ی زدن دکمه‌ی خرید/فروش رو دارن.
# در Railway Variables یه متغیر به اسم AUTHORIZED_TELEGRAM_USER_IDS بسازید
# و آیدی عددی خودتون رو (و هرکس دیگه‌ای که باید اجازه داشته باشه) با کاما جدا کنید.
# مثال: AUTHORIZED_TELEGRAM_USER_IDS=123456789,987654321
# اگه نمی‌دونید آیدی عددی‌تون چیه، به بات @userinfobot توی تلگرام پیام بدید.
def _parse_authorized_ids():
    raw = os.environ.get("AUTHORIZED_TELEGRAM_USER_IDS", "")
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


AUTHORIZED_TELEGRAM_USER_IDS = _parse_authorized_ids()

# مسیر پایگاه‌داده‌ی معاملات. روی هاست‌هایی مثل Railway که فایل‌سیستم موقتیه،
# این فایل با هر ریدیپلوی پاک میشه -- مگر اینکه یه Volume دائمی توی Railway
# وصل کنید و این مسیر رو به همون Volume اشاره بدید (با متغیر TRADES_DB_PATH).
TRADES_DB_FILE = os.environ.get("TRADES_DB_PATH", "trades.db")

# ==================================================================
# بخش ۲: دیکشنری اسامی فارسی/انگلیسی (نسخه‌ی کامل)
# ==================================================================
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

IRAN_CRYPTO_BROKERS = ["نوبیتکس", "والکس"]
LAST_ALERT_STATE = {}
TSE_STOCK_TYPES = [300, 303, 309]

# ردیابی پیام‌هایی که برای هر کدوم قبلاً یه دکمه پردازش شده (idempotency روی کلیک تکراری)
CONSUMED_MESSAGES = set()


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


# ==================================================================
# بخش ۳: توابع کمکی نمایش/لینک
# ==================================================================
def get_display_name(symbol, names_dict):
    info = names_dict.get(symbol)
    if info:
        en, fa = info
        return f"{symbol} ({en} | {fa})"
    return symbol


def get_tradingview_link(symbol, market):
    if market == "crypto":
        return f"https://www.tradingview.com/chart/?symbol=BINANCE:{quote(symbol)}"
    return f"https://www.tradingview.com/chart/?symbol={quote(symbol)}"


def get_binance_link(symbol):
    if symbol.endswith("USDT"):
        base = symbol[:-4]
        return f"https://www.binance.com/en/trade/{quote(base)}_USDT"
    return f"https://www.binance.com/en/trade/{quote(symbol)}"


def should_suppress_repeat_alert(state_key, diff_percent):
    now = time.time()
    prev = LAST_ALERT_STATE.get(state_key)
    if prev is None:
        LAST_ALERT_STATE[state_key] = {"diff": diff_percent, "time": now}
        return False
    time_since_last = now - prev["time"]
    diff_change = abs(diff_percent - prev["diff"])
    if time_since_last < ALERT_COOLDOWN_SECONDS and diff_change < FROZEN_TOLERANCE:
        return True
    LAST_ALERT_STATE[state_key] = {"diff": diff_percent, "time": now}
    return False


def get_iran_broker_links(base_currency):
    listed_in = []
    base_lower = base_currency.lower()
    base_upper = base_currency.upper()

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
                listed_in.append(("نوبیتکس", f"https://nobitex.ir/price/{base_lower}/"))
    except Exception as e:
        log(f"⚠️ خطا در چک نوبیتکس برای {base_currency}: {e}")

    try:
        r = requests.get("https://api.wallex.ir/hector/web/v1/markets", timeout=IRAN_BROKER_CHECK_TIMEOUT)
        data = r.json()
        result = data.get("result", data)
        symbols_dict = result.get("symbols", result) if isinstance(result, dict) else {}
        if isinstance(symbols_dict, dict):
            target = f"{base_upper}USDT"
            target_tmn = f"{base_upper}TMN"
            if target in symbols_dict:
                listed_in.append(("والکس", f"https://wallex.ir/app/trade/{target}"))
            elif target_tmn in symbols_dict:
                listed_in.append(("والکس", f"https://wallex.ir/app/trade/{target_tmn}"))
    except Exception as e:
        log(f"⚠️ خطا در چک والکس برای {base_currency}: {e}")

    return listed_in


# ==================================================================
# بخش ۴: ارسال پیام/عکس تلگرام (با پشتیبانی از دکمه)
# ==================================================================
def _telegram_post(method, data=None, files=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    return requests.post(url, data=data, files=files, timeout=REQUEST_TIMEOUT)


def send_telegram_message(text, reply_markup=None, _retry=True):
    if not TOKEN or not CHAT_ID:
        log("⚠️ توکن یا چت‌آیدی تنظیم نشده! پیام ارسال نشد.")
        return None
    data = {"chat_id": CHAT_ID, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        r = _telegram_post("sendMessage", data=data)
        if r.status_code == 429 and _retry:
            retry_after = r.json().get("parameters", {}).get("retry_after", 3)
            time.sleep(retry_after + 1)
            return send_telegram_message(text, reply_markup, _retry=False)
        elif r.status_code != 200:
            log(f"خطای تلگرام (sendMessage): {r.status_code} - {r.text[:200]}")
        return r.json()
    except Exception as e:
        log(f"خطا در ارسال پیام تلگرام: {e}")
        return None


def send_telegram_message_with_buttons(text, buttons):
    return send_telegram_message(text, reply_markup={"inline_keyboard": buttons})


def send_telegram_photo(image_bytes, caption, _retry=True):
    if not TOKEN or not CHAT_ID:
        log("⚠️ توکن یا چت‌آیدی تنظیم نشده! عکس ارسال نشد.")
        return
    files = {"photo": ("chart.png", image_bytes, "image/png")}
    data = {"chat_id": CHAT_ID, "caption": caption}
    try:
        r = _telegram_post("sendPhoto", data=data, files=files)
        if r.status_code == 429 and _retry:
            retry_after = r.json().get("parameters", {}).get("retry_after", 3)
            time.sleep(retry_after + 1)
            image_bytes.seek(0)
            send_telegram_photo(image_bytes, caption, _retry=False)
        elif r.status_code != 200:
            log(f"خطای تلگرام (sendPhoto): {r.status_code} - {r.text[:200]}")
            send_telegram_message(caption)
    except Exception as e:
        log(f"خطا در ارسال عکس: {e}")
        send_telegram_message(caption)

def answer_callback_query(callback_id, text, show_alert=False):
    try:
        _telegram_post("answerCallbackQuery", data={
            "callback_query_id": callback_id, "text": text, "show_alert": show_alert,
        })
    except Exception as e:
        log(f"خطا در answerCallbackQuery: {e}")


def remove_message_buttons(chat_id, message_id):
    """دکمه‌های زیر یه پیام رو حذف می‌کنه تا کاربر نتونه دوباره روشون کلیک کنه (جلوگیری از سفارش تکراری)."""
    if chat_id is None or message_id is None:
        return
    try:
        _telegram_post("editMessageReplyMarkup", data={
            "chat_id": chat_id, "message_id": message_id,
            "reply_markup": json.dumps({"inline_keyboard": []}),
        })
    except Exception as e:
        log(f"خطا در حذف دکمه‌های پیام: {e}")


def is_authorized(user_id):
    """فقط آیدی‌های عددی تلگرام توی AUTHORIZED_TELEGRAM_USER_IDS اجازه‌ی خرید/فروش دارن."""
    return user_id is not None and user_id in AUTHORIZED_TELEGRAM_USER_IDS


def mark_consumed_and_check(chat_id, message_id):
    """
    اگه این پیام قبلاً پردازش شده True برمی‌گردونه (یعنی رد کن، دوباره اجرا نکن)،
    وگرنه اون رو به‌عنوان پردازش‌شده ثبت می‌کنه و False برمی‌گردونه.
    """
    key = (chat_id, message_id)
    if key in CONSUMED_MESSAGES:
        return True
    CONSUMED_MESSAGES.add(key)
    return False


# ==================================================================
# بخش ۵: اندیکاتورها (EMA + پیوت fibonacci/camarilla)
# ==================================================================
def calculate_ema(prices, period):
    if len(prices) < period:
        return None
    ema = sum(prices[:period]) / period
    multiplier = 2 / (period + 1)
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


def calculate_ema_series(close_series, period=EMA_PERIOD):
    return close_series.ewm(span=period, adjust=False).mean()


def had_three_red_candles_before_last(opens, closes):
    if len(opens) < 4 or len(closes) < 4:
        return False
    for i in (-4, -3, -2):
        if not (closes[i] < opens[i]):
            return False
    return True


def had_zero_volume_recently(volumes):
    if len(volumes) < 4:
        return True
    return any(v == 0 for v in volumes[-4:-1])


def calculate_fibonacci_pivots(prev_high, prev_low, prev_close):
    pp = (prev_high + prev_low + prev_close) / 3
    diff = prev_high - prev_low
    return {
        "PP": pp,
        "R1": pp + 0.382 * diff, "R2": pp + 0.618 * diff, "R3": pp + 1.000 * diff,
        "S1": pp - 0.382 * diff, "S2": pp - 0.618 * diff, "S3": pp - 1.000 * diff,
    }


def calculate_camarilla_pivots(prev_high, prev_low, prev_close):
    diff = prev_high - prev_low
    return {
        "PP": prev_close,
        "R1": prev_close + diff * 1.1 / 12, "R2": prev_close + diff * 1.1 / 6, "R3": prev_close + diff * 1.1 / 4,
        "S1": prev_close - diff * 1.1 / 12, "S2": prev_close - diff * 1.1 / 6, "S3": prev_close - diff * 1.1 / 4,
    }


def calculate_pivots(prev_high, prev_low, prev_close, pivot_type=PIVOT_TYPE):
    if pivot_type == "camarilla":
        return calculate_camarilla_pivots(prev_high, prev_low, prev_close)
    return calculate_fibonacci_pivots(prev_high, prev_low, prev_close)


def price_reached_pivot_support(current_price, prev_high, prev_low, prev_close):
    """آیا قیمت به یکی از سطوح PIVOT_ENTRY_LEVELS (پیش‌فرض S2/S3) رسیده؟"""
    pivots = calculate_pivots(prev_high, prev_low, prev_close, PIVOT_TYPE)
    for level in PIVOT_ENTRY_LEVELS:
        if level in pivots and current_price <= pivots[level]:
            return True, level, pivots[level]
    return False, None, None


def compute_pivot_series(intraday_index, daily_df):
    daily_df = daily_df.sort_index()
    daily_dates = daily_df.index.normalize()
    unique_dates = intraday_index.normalize().unique()
    pivot_by_date = {}
    for d in unique_dates:
        prev_days = daily_df[daily_dates < d]
        pivot_by_date[d] = calculate_pivots(
            prev_days["High"].iloc[-1], prev_days["Low"].iloc[-1], prev_days["Close"].iloc[-1], PIVOT_TYPE
        ) if len(prev_days) > 0 else None
    levels = {k: [] for k in ("PP", "R1", "R2", "R3", "S1", "S2", "S3")}
    for ts in intraday_index:
        p = pivot_by_date.get(ts.normalize())
        for k in levels:
            levels[k].append(p[k] if p else float("nan"))
    return {k: pd.Series(v, index=intraday_index) for k, v in levels.items()}


PIVOT_COLORS = {
    "PP": "#800080",
    "R1": "#ff6666", "R2": "#ff0000", "R3": "#990000",
    "S1": "#66cc66", "S2": "#00aa00", "S3": "#006600",
}

# سطوحی که مبنای استراتژی ورودن (S2/S3) پررنگ‌تر و با برچسب عددی روی نمودار رسم میشن
KEY_PIVOT_LEVELS = ("S2", "S3")


def build_indicator_chart(df_full, display_bars, title, daily_df=None, show_pivots=False):
    """
    نمودار شمعی «فقط با EMA5 + پیوت» -- هیچ اندیکاتور اضافه‌ای (حجم و غیره) رسم نمیشه.
    خطوط S2 و S3 (مبنای ورود به معامله طبق استراتژی) پررنگ‌تر و با برچسب عددی دقیق
    کنار نمودار نمایش داده میشن تا کاملاً واضح و خوانا باشن.
    """
    buf = io.BytesIO()
    try:
        ema_series = calculate_ema_series(df_full["Close"], EMA_PERIOD)
        df_display = df_full.tail(display_bars)
        addplots = [mpf.make_addplot(ema_series.tail(display_bars), color="blue", width=1.3)]

        pivots_display = None
        if show_pivots and daily_df is not None and len(daily_df) > 0:
            pivots = compute_pivot_series(df_full.index, daily_df)
            pivots_display = {k: v.tail(display_bars) for k, v in pivots.items()}
            for level, series in pivots_display.items():
                is_key = level in KEY_PIVOT_LEVELS
                addplots.append(mpf.make_addplot(
                    series,
                    color=PIVOT_COLORS[level],
                    width=2.4 if is_key else 1.0,
                    linestyle="-" if is_key else "--",
                ))

        fig, axes = mpf.plot(
            df_display, type="candle", style="charles", volume=False, title=title,
            figsize=(11, 6), addplot=addplots, returnfig=True,
        )
        ax = axes[0]

        # برچسب عددی واضح کنار خطوط S2/S3 -- چون مبنای تصمیم خرید همینه
        if pivots_display:
            for level in KEY_PIVOT_LEVELS:
                series = pivots_display.get(level)
                if series is None or series.dropna().empty:
                    continue
                last_value = float(series.dropna().iloc[-1])
                ax.annotate(
                    f"{level}: {last_value:.4f}",
                    xy=(1, last_value), xycoords=("axes fraction", "data"),
                    xytext=(6, 0), textcoords="offset points",
                    color=PIVOT_COLORS[level], fontsize=10, fontweight="bold",
                    va="center", ha="left",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=PIVOT_COLORS[level], alpha=0.85),
                )

        fig.savefig(buf, dpi=140, bbox_inches="tight")
        buf.seek(0)
        return buf
    except Exception as e:
        log(f"خطا در ساخت نمودار اندیکاتور ({title}): {e}")
        return None


def make_candlestick_chart(df, title=""):
    buf = io.BytesIO()
    try:
        mpf.plot(df, type="candle", style="charles", volume=False, title=title,
                  figsize=(11, 6), savefig=dict(fname=buf, dpi=140, bbox_inches="tight"))
        buf.seek(0)
        return buf
    except Exception as e:
        log(f"خطا در ساخت نمودار: {e}")
        return None

# ==================================================================
# بخش ۶: دقت اعشار بایننس (LOT_SIZE / PRICE_FILTER / tickSize)
# ==================================================================
_EXCHANGE_INFO_CACHE = {"data": None, "ts": 0}
EXCHANGE_INFO_TTL_SECONDS = 3600  # هر ۱ ساعت یه بار دوباره از بایننس گرفته میشه


def get_binance_symbol_filters(symbol):
    """
    فیلترهای دقیق هر نماد (حداقل/گام مقدار = LOT_SIZE، حداقل/گام قیمت = PRICE_FILTER)
    رو از exchangeInfo بایننس می‌گیره و کش می‌کنه، تا سفارش‌ها با خطای دقت اعشار رد نشن.
    """
    global _EXCHANGE_INFO_CACHE
    now = time.time()
    if not _EXCHANGE_INFO_CACHE["data"] or now - _EXCHANGE_INFO_CACHE["ts"] > EXCHANGE_INFO_TTL_SECONDS:
        try:
            r = requests.get("https://api.binance.com/api/v3/exchangeInfo", timeout=REQUEST_TIMEOUT)
            data = r.json()
            info_map = {s["symbol"]: s for s in data.get("symbols", [])}
            _EXCHANGE_INFO_CACHE = {"data": info_map, "ts": now}
        except Exception as e:
            log(f"⚠️ خطا در دریافت exchangeInfo بایننس: {e}")
            if not _EXCHANGE_INFO_CACHE["data"]:
                return None

    info = _EXCHANGE_INFO_CACHE["data"].get(symbol) if _EXCHANGE_INFO_CACHE["data"] else None
    if not info:
        return None
    return {f["filterType"]: f for f in info.get("filters", [])}


def _round_to_step(value, step_str):
    """مقدار رو به پایین، به نزدیک‌ترین مضرب step گرد می‌کنه (برای رعایت دقیق stepSize/tickSize)."""
    step = Decimal(step_str)
    if step == 0:
        return float(value)
    value_dec = Decimal(str(value))
    steps = (value_dec / step).to_integral_value(rounding=ROUND_DOWN)
    return float(steps * step)


def format_binance_quantity(symbol, quantity):
    """مقدار سفارش رو طبق LOT_SIZE همون نماد گرد می‌کنه (نه یه عدد ثابت ۶ رقمی برای همه)."""
    filters = get_binance_symbol_filters(symbol)
    if not filters or "LOT_SIZE" not in filters:
        return round(quantity, 6)
    lot = filters["LOT_SIZE"]
    quantity = _round_to_step(quantity, lot["stepSize"])
    min_qty = float(lot["minQty"])
    if quantity < min_qty:
        quantity = min_qty
    return quantity


def format_binance_price(symbol, price):
    """قیمت سفارش رو طبق PRICE_FILTER (tickSize) همون نماد گرد می‌کنه."""
    filters = get_binance_symbol_filters(symbol)
    if not filters or "PRICE_FILTER" not in filters:
        return round(price, 6)
    pf = filters["PRICE_FILTER"]
    return _round_to_step(price, pf["tickSize"])


# ==================================================================
# بخش ۷: تفسیر خطاهای بایننس/نوبیتکس به پیام قابل‌فهم
# ==================================================================
BINANCE_ERROR_MESSAGES = {
    -1013: "مقدار یا قیمت سفارش با قوانین حداقل/گام اعشار این نماد (LOT_SIZE/PRICE_FILTER) جور در نمیاد.",
    -1021: "زمان سرور بایننس با ساعت سیستم اجراکننده‌ی ربات هماهنگ نیست.",
    -1121: "این نماد در بایننس نامعتبره یا لیست نشده.",
    -2010: "سفارش رد شد - معمولاً یعنی موجودی کافی نیست یا شرایط سفارش برقرار نیست.",
    -2011: "سفارش توسط بایننس لغو یا رد شد.",
    -1102: "یکی از پارامترهای اجباری سفارش خالی یا نامعتبره.",
}


def interpret_binance_error(result):
    if isinstance(result, dict) and "code" in result and "msg" in result:
        code = result["code"]
        friendly = BINANCE_ERROR_MESSAGES.get(code, "خطای ناشناخته از بایننس -- برای جزئیات به پیام اصلی نگاه کنید.")
        return f"⚠️ خطای بایننس (کد {code}): {friendly}\nپیام اصلی: {result['msg']}"
    return None


NOBITEX_ERROR_MESSAGES = {
    "InsufficientBalance": "موجودی کیف‌پول نوبیتکس برای این سفارش کافی نیست.",
    "Invalid": "پارامترهای سفارش نامعتبره -- مقدار یا قیمت رو بررسی کنید.",
    "SmallOrder": "حجم سفارش کمتر از حداقل مجاز نوبیتکسه.",
    "PriceInvalid": "قیمت وارد شده برای این سفارش قابل قبول نیست.",
}


def interpret_nobitex_error(result):
    if isinstance(result, dict) and result.get("status") not in ("ok", None):
        code = result.get("code", result.get("status", ""))
        friendly = NOBITEX_ERROR_MESSAGES.get(code, "خطای ناشناخته از نوبیتکس -- برای جزئیات به پیام اصلی نگاه کنید.")
        return f"⚠️ خطای نوبیتکس ({code}): {friendly}\nپیام اصلی: {result.get('message', '')}"
    return None


# ==================================================================
# بخش ۸: توابع معامله (بایننس / نوبیتکس)
# ==================================================================
def binance_place_order(symbol, side, quote_amount_usdt):
    if DRY_RUN:
        log(f"[DRY_RUN] بایننس مارکت: {side} {quote_amount_usdt} USDT از {symbol}")
        return {"dry_run": True, "symbol": symbol, "side": side, "amount": quote_amount_usdt}
    params = {"symbol": symbol, "side": side, "type": "MARKET",
              "quoteOrderQty": quote_amount_usdt, "timestamp": int(time.time() * 1000)}
    query = "&".join(f"{k}={v}" for k, v in params.items())
    signature = hmac.new(BINANCE_API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.binance.com/api/v3/order?{query}&signature={signature}"
    r = requests.post(url, headers={"X-MBX-APIKEY": BINANCE_API_KEY}, timeout=REQUEST_TIMEOUT)
    return r.json()


def binance_place_limit_order(symbol, side, quantity, price):
    if DRY_RUN:
        log(f"[DRY_RUN] بایننس لیمیت: {side} {quantity} {symbol} @ {price}")
        return {"dry_run": True, "symbol": symbol, "side": side, "quantity": quantity, "price": price}
    params = {"symbol": symbol, "side": side, "type": "LIMIT", "timeInForce": "GTC",
              "quantity": quantity, "price": price, "timestamp": int(time.time() * 1000)}
    query = "&".join(f"{k}={v}" for k, v in params.items())
    signature = hmac.new(BINANCE_API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.binance.com/api/v3/order?{query}&signature={signature}"
    r = requests.post(url, headers={"X-MBX-APIKEY": BINANCE_API_KEY}, timeout=REQUEST_TIMEOUT)
    return r.json()


def binance_place_stop_loss_order(symbol, quantity, stop_price, limit_price):
    """سفارش STOP_LOSS_LIMIT فروش -- وقتی قیمت به stop_price برسه، سفارش لیمیت فروش در limit_price فعال میشه."""
    if DRY_RUN:
        log(f"[DRY_RUN] بایننس استاپ‌لاس: SELL {quantity} {symbol} @ stop={stop_price} limit={limit_price}")
        return {"dry_run": True, "symbol": symbol, "quantity": quantity,
                "stop_price": stop_price, "limit_price": limit_price}
    params = {"symbol": symbol, "side": "SELL", "type": "STOP_LOSS_LIMIT", "timeInForce": "GTC",
              "quantity": quantity, "price": limit_price, "stopPrice": stop_price,
              "timestamp": int(time.time() * 1000)}
    query = "&".join(f"{k}={v}" for k, v in params.items())
    signature = hmac.new(BINANCE_API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.binance.com/api/v3/order?{query}&signature={signature}"
    r = requests.post(url, headers={"X-MBX-APIKEY": BINANCE_API_KEY}, timeout=REQUEST_TIMEOUT)
    return r.json()


def get_nobitex_price(base_currency):
    try:
        r = requests.post("https://api.nobitex.ir/market/stats",
                           json={"srcCurrency": base_currency.lower(), "dstCurrency": "usdt"},
                           timeout=IRAN_BROKER_CHECK_TIMEOUT)
        data = r.json()
        if data.get("status") == "ok":
            key = f"{base_currency.lower()}-usdt"
            stats = data.get("stats", {})
            if key in stats:
                return float(stats[key].get("latest", 0))
    except Exception as e:
        log(f"خطا در گرفتن قیمت نوبیتکس: {e}")
    return None


def get_current_price(exchange, symbol_or_base):
    if exchange == "binance":
        try:
            r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol_or_base}",
                              timeout=REQUEST_TIMEOUT)
            return float(r.json()["price"])
        except Exception as e:
            log(f"خطا در گرفتن قیمت بایننس: {e}")
            return None
    return get_nobitex_price(symbol_or_base)


def nobitex_place_order(base_currency, order_type, quote_amount_usdt):
    price = get_nobitex_price(base_currency)
    if not price:
        return {"status": "failed", "code": "PriceInvalid", "message": "نتونستم قیمت لحظه‌ای رو از نوبیتکس بگیرم."}
    amount = round(quote_amount_usdt / price, 6)
    if DRY_RUN:
        log(f"[DRY_RUN] نوبیتکس مارکت: {order_type} {amount} {base_currency}")
        return {"dry_run": True, "currency": base_currency, "type": order_type, "amount": amount}
    payload = {"type": order_type, "srcCurrency": base_currency.lower(), "dstCurrency": "usdt",
               "amount": amount, "execution": "market"}
    headers = {"Authorization": f"Token {NOBITEX_TOKEN}"}
    r = requests.post("https://api.nobitex.ir/market/orders/add", json=payload, headers=headers,
                       timeout=REQUEST_TIMEOUT)
    return r.json()


def nobitex_place_limit_order(base_currency, order_type, amount, price):
    if DRY_RUN:
        log(f"[DRY_RUN] نوبیتکس لیمیت: {order_type} {amount} {base_currency} @ {price}")
        return {"dry_run": True, "currency": base_currency, "type": order_type, "amount": amount, "price": price}
    payload = {"type": order_type, "srcCurrency": base_currency.lower(), "dstCurrency": "usdt",
               "amount": amount, "price": price, "execution": "limit"}
    headers = {"Authorization": f"Token {NOBITEX_TOKEN}"}
    r = requests.post("https://api.nobitex.ir/market/orders/add", json=payload, headers=headers,
                       timeout=REQUEST_TIMEOUT)
    return r.json()

def nobitex_place_stop_loss_order(base_currency, amount, stop_price):
    """
    نکته: ساختار API سفارش استاپ نوبیتکس ممکنه در طول زمان تغییر کنه. این پیاده‌سازی
    بر پایه‌ی execution=stopMarket نوشته شده؛ اگه با خطا مواجه شدید، مستندات فعلی
    نوبیتکس (https://apidocs.nobitex.ir) رو برای فیلد دقیق چک کنید.
    """
    if DRY_RUN:
        log(f"[DRY_RUN] نوبیتکس استاپ‌لاس: SELL {amount} {base_currency} @ stop={stop_price}")
        return {"dry_run": True, "currency": base_currency, "amount": amount, "stop_price": stop_price}
    payload = {"type": "sell", "srcCurrency": base_currency.lower(), "dstCurrency": "usdt",
               "amount": amount, "stopPrice": stop_price, "execution": "stopMarket"}
    headers = {"Authorization": f"Token {NOBITEX_TOKEN}"}
    r = requests.post("https://api.nobitex.ir/market/orders/add", json=payload, headers=headers,
                       timeout=REQUEST_TIMEOUT)
    return r.json()


# ==================================================================
# بخش ۹: ذخیره‌سازی معاملات (SQLite به‌جای JSON خام)
# ==================================================================
def _get_db_connection():
    conn = sqlite3.connect(TRADES_DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            exchange TEXT,
            symbol TEXT,
            entry_price REAL,
            amount_usdt REAL,
            take_profit_price REAL,
            stop_loss_price REAL,
            timestamp REAL
        )
    """)
    return conn


def load_trades():
    try:
        conn = _get_db_connection()
        cur = conn.execute(
            "SELECT id, exchange, symbol, entry_price, amount_usdt, take_profit_price, stop_loss_price, timestamp "
            "FROM trades"
        )
        rows = cur.fetchall()
        conn.close()
        cols = ["id", "exchange", "symbol", "entry_price", "amount_usdt",
                "take_profit_price", "stop_loss_price", "timestamp"]
        return [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        log(f"خطا در خواندن پایگاه‌داده‌ی معاملات: {e}")
        return []


def record_trade(exchange, symbol, entry_price, amount_usdt, take_profit_price, stop_loss_price):
    trade = {
        "id": f"{exchange}-{symbol}-{int(time.time())}",
        "exchange": exchange, "symbol": symbol,
        "entry_price": entry_price, "amount_usdt": amount_usdt,
        "take_profit_price": take_profit_price, "stop_loss_price": stop_loss_price,
        "timestamp": time.time(),
    }
    try:
        conn = _get_db_connection()
        conn.execute(
            "INSERT INTO trades (id, exchange, symbol, entry_price, amount_usdt, "
            "take_profit_price, stop_loss_price, timestamp) VALUES (?,?,?,?,?,?,?,?)",
            (trade["id"], trade["exchange"], trade["symbol"], trade["entry_price"], trade["amount_usdt"],
             trade["take_profit_price"], trade["stop_loss_price"], trade["timestamp"]),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"خطا در ذخیره‌ی معامله: {e}")
    return trade


def compute_trade_pnl(trade):
    current_price = get_current_price(trade["exchange"], trade["symbol"])
    if not current_price:
        return None
    return ((current_price - trade["entry_price"]) / trade["entry_price"]) * 100


def compute_monthly_pnl():
    trades = load_trades()
    now = time.localtime()
    month_trades = [t for t in trades if time.localtime(t["timestamp"]).tm_mon == now.tm_mon
                     and time.localtime(t["timestamp"]).tm_year == now.tm_year]
    total, count = 0.0, 0
    for t in month_trades:
        pnl = compute_trade_pnl(t)
        if pnl is not None:
            total += pnl
            count += 1
    return (total / count if count else 0.0), count


# ==================================================================
# بخش ۱۰: هندل کردن دکمه‌های تلگرام
#   جریان خرید حالا دو مرحله‌ایه:
#   ۱) کلیک روی «خرید» -> ربات درصد حد ضرر رو با چند دکمه می‌پرسه (نه خرید فوری)
#   ۲) کلیک روی یکی از درصدهای حد ضرر -> خرید واقعاً انجام میشه + حد سود و حد ضرر
#      هر دو به‌صورت خودکار ثبت میشن.
#   هر دو مرحله: چک هویت (فقط آیدی‌های مجاز) + idempotency (هر پیام فقط یک‌بار قابل کلیکه).
# ==================================================================
def execute_buy_with_protection(exchange, symbol_or_base, sl_percent):
    try:
        if exchange == "binance":
            buy_result = binance_place_order(symbol_or_base, "BUY", TEST_TRADE_AMOUNT_USDT)
        elif exchange == "nobitex":
            buy_result = nobitex_place_order(symbol_or_base, "buy", TEST_TRADE_AMOUNT_USDT)
        else:
            send_telegram_message("صرافی ناشناخته.")
            return

        buy_error = (interpret_binance_error(buy_result) if exchange == "binance"
                     else interpret_nobitex_error(buy_result))
        if buy_error:
            send_telegram_message(f"❌ خرید {symbol_or_base} در {exchange} ناموفق بود.\n{buy_error}")
            return

        entry_price = get_current_price(exchange, symbol_or_base)
        if not entry_price:
            send_telegram_message(
                f"❌ سفارش خرید ارسال شد ولی قیمت ورود برای محاسبه‌ی حد سود/ضرر پیدا نشد.\nنتیجه: {buy_result}"
            )
            return

        raw_quantity = TEST_TRADE_AMOUNT_USDT / entry_price
        take_profit_price = entry_price * (1 + TAKE_PROFIT_PERCENT / 100)
        stop_loss_price = entry_price * (1 - sl_percent / 100)

        if exchange == "binance":
            quantity = format_binance_quantity(symbol_or_base, raw_quantity)
            tp_price = format_binance_price(symbol_or_base, take_profit_price)
            sl_stop_price = format_binance_price(symbol_or_base, stop_loss_price)
            # قیمت لیمیت سفارش استاپ رو یه‌کم پایین‌تر از stopPrice می‌ذاریم تا مطمئن‌تر پر بشه
            sl_limit_price = format_binance_price(symbol_or_base, stop_loss_price * 0.995)
            tp_result = binance_place_limit_order(symbol_or_base, "SELL", quantity, tp_price)
            sl_result = binance_place_stop_loss_order(symbol_or_base, quantity, sl_stop_price, sl_limit_price)
        else:
            quantity = round(raw_quantity, 6)
            tp_result = nobitex_place_limit_order(symbol_or_base, "sell", quantity, take_profit_price)
            sl_result = nobitex_place_stop_loss_order(symbol_or_base, quantity, stop_loss_price)

        tp_error = (interpret_binance_error(tp_result) if exchange == "binance"
                    else interpret_nobitex_error(tp_result))
        sl_error = (interpret_binance_error(sl_result) if exchange == "binance"
                    else interpret_nobitex_error(sl_result))

        trade = record_trade(exchange, symbol_or_base, entry_price, TEST_TRADE_AMOUNT_USDT,
                              take_profit_price, stop_loss_price)

        mode_label = "🧪 حالت آزمایشی (DRY_RUN)" if DRY_RUN else "✅ سفارش واقعی ارسال شد"
        caption = (
            f"{mode_label}\n"
            f"صرافی: {exchange} | نماد: {symbol_or_base}\n"
            f"قیمت خرید: {entry_price}\n"
            f"حد سود ({TAKE_PROFIT_PERCENT}%): {take_profit_price:.6f}\n"
            f"حد ضرر ({sl_percent}%): {stop_loss_price:.6f}\n"
            f"نتیجه‌ی خرید: {buy_result}\n"
            f"نتیجه‌ی سفارش حد سود: {tp_result}" + (f"\n{tp_error}" if tp_error else "") + "\n"
            f"نتیجه‌ی سفارش حد ضرر: {sl_result}" + (f"\n{sl_error}" if sl_error else "")
        )
        pnl_buttons = [[{"text": "📊 نمایش سود/زیان", "callback_data": f"pnl:{trade['id']}"}]]
        send_telegram_message_with_buttons(caption, pnl_buttons)
    except Exception as e:
        send_telegram_message(f"❌ خطا در معامله‌ی {exchange} برای {symbol_or_base}: {e}")


def handle_callback_query(callback_query):
    callback_id = callback_query["id"]
    data = callback_query.get("data", "")
    parts = data.split(":")

    from_user = callback_query.get("from", {}) or {}
    user_id = from_user.get("id")
    message = callback_query.get("message", {}) or {}
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")

    # --- چک هویت: فقط آیدی‌های مجاز اجازه‌ی خرید/فروش دارن ---
    if parts and parts[0] in ("buy", "slbuy") and not is_authorized(user_id):
        username = from_user.get("username", "?")
        log(f"⛔ تلاش برای معامله توسط کاربر غیرمجاز: user_id={user_id} username=@{username}")
        answer_callback_query(callback_id, "⛔ شما اجازه‌ی استفاده از این دکمه رو ندارید.", show_alert=True)
        return

    if parts and parts[0] == "buy" and len(parts) == 3:
        if mark_consumed_and_check(chat_id, message_id):
            answer_callback_query(callback_id, "این هشدار قبلاً پردازش شده.", show_alert=True)
            return
        remove_message_buttons(chat_id, message_id)
        _, exchange, symbol_or_base = parts
        answer_callback_query(callback_id, "لطفاً درصد حد ضرر رو انتخاب کنید.")
        sl_buttons = [
            [{"text": f"🛑 حد ضرر {p}%", "callback_data": f"slbuy:{exchange}:{symbol_or_base}:{p}"}]
            for p in STOP_LOSS_OPTIONS
        ]
        send_telegram_message_with_buttons(
            f"برای خرید {symbol_or_base} در {exchange}، درصد مجاز ضرر (حد ضرر) رو انتخاب کنید:",
            sl_buttons,
        )

    elif parts and parts[0] == "slbuy" and len(parts) == 4:
        if mark_consumed_and_check(chat_id, message_id):
            answer_callback_query(callback_id, "این سفارش قبلاً پردازش شده.", show_alert=True)
            return
        remove_message_buttons(chat_id, message_id)
        _, exchange, symbol_or_base, sl_percent_str = parts
        try:
            sl_percent = float(sl_percent_str)
        except ValueError:
            answer_callback_query(callback_id, "درصد حد ضرر نامعتبره.", show_alert=True)
            return
        answer_callback_query(callback_id, f"⏳ در حال خرید {symbol_or_base} در {exchange} (حد ضرر {sl_percent}%)...")
        execute_buy_with_protection(exchange, symbol_or_base, sl_percent)

    elif parts and parts[0] == "pnl" and len(parts) == 2:
        trade_id = parts[1]
        trades = load_trades()
        trade = next((t for t in trades if t["id"] == trade_id), None)
        if not trade:
            answer_callback_query(callback_id, "این معامله پیدا نشد.")
            return
        pnl = compute_trade_pnl(trade)
        if pnl is None:
            answer_callback_query(callback_id, "قیمت لحظه‌ای پیدا نشد.")
            return
        monthly_avg, monthly_count = compute_monthly_pnl()
        emoji_trade = "🟢" if pnl >= 0 else "🔴"
        emoji_month = "🟢" if monthly_avg >= 0 else "🔴"
        text = (
            f"{emoji_trade} این معامله ({trade['symbol']}): {pnl:+.2f}%\n"
            f"{emoji_month} میانگین این ماه ({monthly_count} معامله): {monthly_avg:+.2f}%"
        )
        answer_callback_query(callback_id, text, show_alert=True)
    else:
        answer_callback_query(callback_id, "دستور ناشناخته.")


def poll_telegram_updates():
    offset = None
    while True:
        try:
            params = {"timeout": 25}
            if offset:
                params["offset"] = offset
            r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params=params, timeout=30)
            for update in r.json().get("result", []):
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    handle_callback_query(update["callback_query"])
        except Exception as e:
            log(f"خطا در دریافت آپدیت‌های تلگرام: {e}")
            time.sleep(3)


# ==================================================================
# بخش ۱۱: اسکن بازار کریپتو (بایننس) -- با رتبه + شرط پیوت + دکمه خرید
# ==================================================================
def get_top_ranked_usdt_symbols(limit=CRYPTO_RANK_LIMIT):
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT).json()
        usdt_pairs = [i for i in response if isinstance(i, dict) and i.get("symbol", "").endswith("USDT")]
        usdt_pairs.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
        return [i["symbol"] for i in usdt_pairs[:limit]]
    except Exception as e:
        log(f"خطا در دریافت و رتبه‌بندی لیست ارزها: {e}")
        return []


def get_crypto_daily_df(symbol, limit=180):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT).json()
        if not isinstance(response, list) or len(response) == 0:
            return None
        df = pd.DataFrame(response, columns=["open_time", "open", "high", "low", "close", "volume",
                                              "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df.set_index("open_time", inplace=True)
        df = df[["open", "high", "low", "close"]].astype(float)
        df.columns = ["Open", "High", "Low", "Close"]
        return df
    except Exception as e:
        log(f"خطا در دریافت دیتای روزانه {symbol}: {e}")
        return None


def get_crypto_intraday_df(symbol, interval, limit):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT).json()
        if not isinstance(response, list) or len(response) == 0:
            return None
        df = pd.DataFrame(response, columns=["open_time", "open", "high", "low", "close", "volume",
                                                      "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df.set_index("open_time", inplace=True)
        df = df[["open", "high", "low", "close"]].astype(float)
        df.columns = ["Open", "High", "Low", "Close"]
        return df
    except Exception as e:
        log(f"خطا در دریافت دیتای {interval} برای {symbol}: {e}")
        return None


def check_crypto_market():
    symbols = get_top_ranked_usdt_symbols()
    total = len(symbols)
    log(f"[کریپتو] {total} ارز برتر (بر اساس حجم ۲۴ ساعته) پیدا شد.")

    for index, symbol in enumerate(symbols, 1):
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=30m&limit=10"
            response = requests.get(url, timeout=REQUEST_TIMEOUT).json()
            if not isinstance(response, list) or len(response) < 4:
                continue

            opens30 = [float(c[1]) for c in response]
            closes = [float(c[4]) for c in response]
            volumes = [float(c[5]) for c in response]
            quote_values = [float(c[7]) for c in response]
            current_price = closes[-1]

            ema_value = calculate_ema(closes, EMA_PERIOD)
            if not ema_value:
                continue
            diff_percent = ((current_price - ema_value) / ema_value) * 100
            if diff_percent > DIFF_THRESHOLD:
                continue

            if had_zero_volume_recently(volumes):
                continue

            daily_df = get_crypto_daily_df(symbol)
            if daily_df is None or len(daily_df) < 4:
                continue

            if REQUIRE_RED_CANDLES:
                red_check_ok = had_three_red_candles_before_last(
                    daily_df["Open"].tolist(), daily_df["Close"].tolist()
                ) if RED_CANDLE_USE_DAILY else had_three_red_candles_before_last(opens30, closes)
                if not red_check_ok:
                    continue

            pivot_level = pivot_value = None
            if REQUIRE_PIVOT_CONDITION:
                prev_day = daily_df.iloc[-2]
                pivot_ok, pivot_level, pivot_value = price_reached_pivot_support(
                    current_price, prev_day["High"], prev_day["Low"], prev_day["Close"]
                )
                if not pivot_ok:
                    continue

            if should_suppress_repeat_alert(f"crypto:{symbol}", diff_percent):
                continue

            display_name = get_display_name(symbol, CRYPTO_NAMES)
            tv_link = get_tradingview_link(symbol, "crypto")
            binance_link = get_binance_link(symbol)
            base_currency = symbol[:-4] if symbol.endswith("USDT") else symbol
            broker_links = get_iran_broker_links(base_currency)
            broker_lines = "".join(f"🟢 {name}: {link}\n" for name, link in broker_links)

            pivot_line = f"شرط پیوت ({PIVOT_TYPE}): قیمت به {pivot_level} رسید ({pivot_value:.6f})\n" if pivot_level else ""
            red_tf_label = "روزانه" if RED_CANDLE_USE_DAILY else "30m"

            caption = (
                f"⚠️ [کریپتو] هشدار ریزش از EMA!\n"
                f"رتبه (بر اساس حجم ۲۴ساعته): {index} از {total}\n"
                f"نماد: {display_name}\n"
                f"تایم‌فریم EMA: 30m | تایم‌فریم کندل قرمز: {red_tf_label}\n"
                f"{pivot_line}"
                f"قیمت: {current_price}\n"
                f"EMA{EMA_PERIOD}: {ema_value:.4f}\n"
                f"فاصله: {diff_percent:.2f}%\n"
                f"حجم کندل آخر (30m): {volumes[-1]:,.0f} {base_currency}\n"
                f"ارزش کندل آخر (30m): {quote_values[-1]:,.0f} USDT\n"
                f"نمودار تردینگ‌ویو: {tv_link}\n"
                f"نمودار بایننس: {binance_link}\n"
                f"{broker_lines}"
            )
            log(caption)

            chart_6m = make_candlestick_chart(daily_df, title=f"{symbol} - 6M Daily")
            if chart_6m:
                send_telegram_photo(chart_6m, f"📊 نمودار ۶ ماهه (روزانه) - {symbol}")
                time.sleep(0.4)

            buf_30m = get_crypto_intraday_df(symbol, "30m", 48 * INTRADAY_DISPLAY_DAYS + 30)
            if buf_30m is not None:
                chart_30m = build_indicator_chart(buf_30m, 48 * INTRADAY_DISPLAY_DAYS,
                                                   title=f"{symbol} - {INTRADAY_DISPLAY_DAYS}D 30m",
                                                   daily_df=daily_df, show_pivots=True)
                if chart_30m:
                    send_telegram_photo(chart_30m, f"⏱ {symbol} - {INTRADAY_DISPLAY_DAYS} روز اخیر، تایم‌فریم ۳۰ دقیقه")
                    time.sleep(0.4)

            buf_15m = get_crypto_intraday_df(symbol, "15m", 96 * INTRADAY_DISPLAY_DAYS + 30)
            if buf_15m is not None:
                chart_15m = build_indicator_chart(buf_15m, 96 * INTRADAY_DISPLAY_DAYS,
                                                   title=f"{symbol} - {INTRADAY_DISPLAY_DAYS}D 15m",
                                                   daily_df=daily_df, show_pivots=True)
                if chart_15m:
                    send_telegram_photo(chart_15m, f"⏱ {symbol} - {INTRADAY_DISPLAY_DAYS} روز اخیر، تایم‌فریم ۱۵ دقیقه")
                    time.sleep(0.4)

            buy_buttons = [[{"text": "🟢 خرید آزمایشی در بایننس", "callback_data": f"buy:binance:{symbol}"}]]
            for broker_name, _ in broker_links:
                if broker_name == "نوبیتکس":
                    buy_buttons.append([{"text": "🟢 خرید آزمایشی در نوبیتکس",
                                          "callback_data": f"buy:nobitex:{base_currency}"}])
            send_telegram_message_with_buttons(caption, buy_buttons)

        except Exception as e:
            log(f"خطا در پردازش {symbol}: {e}")
        if index % 50 == 0:
            log(f"[کریپتو] {index}/{total} اسکن شد...")
        time.sleep(0.15)


# ==================================================================
# بخش ۱۲: سهام آمریکا (Yahoo Finance) -- تکمیل‌شده، فعال
# ==================================================================
def get_top100_us_symbols():
    return list(STOCK_NAMES.keys())


def check_us_stocks_market():
    """اسکن سهام برتر آمریکا - کندل ۳۰ دقیقه‌ای برای EMA، شرط ۳ کندل قرمز طبق RED_CANDLE_USE_DAILY"""
    symbols = get_top100_us_symbols()
    total = len(symbols)
    log(f"[سهام] {total} نماد پیدا شد.")

    for index, symbol in enumerate(symbols, 1):
        try:
            data30 = yf.download(symbol, period="5d", interval="30m", progress=False)
            if data30.empty or len(data30) < EMA_PERIOD or len(data30) < 4:
                continue
            data30 = data30[["Open", "High", "Low", "Close", "Volume"]].copy()

            opens30 = data30["Open"].values.flatten().tolist()
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
                if RED_CANDLE_USE_DAILY:
                    red_check_ok = had_three_red_candles_before_last(
                        daily_df["Open"].values.flatten().tolist(),
                        daily_df["Close"].values.flatten().tolist(),
                    )
                else:
                    red_check_ok = had_three_red_candles_before_last(opens30, closes)
                if not red_check_ok:
                    continue

            pivot_level = pivot_value = None
            if REQUIRE_PIVOT_CONDITION:
                prev_day = daily_df.iloc[-2]
                pivot_ok, pivot_level, pivot_value = price_reached_pivot_support(
                    current_price, prev_day["High"], prev_day["Low"], prev_day["Close"]
                )
                if not pivot_ok:
                    continue

            if should_suppress_repeat_alert(f"stock:{symbol}", diff_percent):
                continue

            display_name = get_display_name(symbol, STOCK_NAMES)
            tv_link = get_tradingview_link(symbol, "stock")

            last_volume = volumes[-1]
            last_value = last_volume * current_price
            red_tf_label = "روزانه" if RED_CANDLE_USE_DAILY else "30m"
            pivot_line = f"شرط پیوت ({PIVOT_TYPE}): قیمت به {pivot_level} رسید ({pivot_value:.6f})\n" if pivot_level else ""

            caption = (
                f"📈 ⚠️ [سهام آمریکا] هشدار ریزش از EMA!\n"
                f"رتبه (بر اساس حجم): {index} از {total}\n"
                f"نماد: {display_name}\n"
                f"تایم‌فریم EMA: 30m | تایم‌فریم کندل قرمز: {red_tf_label}\n"
                f"{pivot_line}"
                f"قیمت: {current_price:.2f}\n"
                f"EMA{EMA_PERIOD}: {ema_value:.4f}\n"
                f"فاصله: {diff_percent:.2f}%\n"
                f"حجم کندل آخر (30m): {last_volume:,.0f} سهم\n"
                f"ارزش تقریبی کندل آخر (30m): {last_value:,.0f} $\n"
                f"نمودار تردینگ‌ویو: {tv_link}\n"
                f"⚠️ خرید مستقیم برای این بازار پشتیبانی نمیشه (فقط اطلاع‌رسانی)."
            )
            log(caption)

            chart_6m = make_candlestick_chart(daily_df, title=f"{symbol} - 6M Daily")
            if chart_6m:
                send_telegram_photo(chart_6m, f"📊 {symbol} - نمودار ۶ ماهه (روزانه)")
                time.sleep(0.4)

            try:
                display_bars_30m = min(13 * INTRADAY_DISPLAY_DAYS, len(data30))
                chart_30m = build_indicator_chart(
                    data30[["Open", "High", "Low", "Close"]], display_bars_30m,
                    title=f"{symbol} - {INTRADAY_DISPLAY_DAYS}D 30m",
                    daily_df=daily_df, show_pivots=True,
                )
                if chart_30m:
                    send_telegram_photo(chart_30m, f"⏱ {symbol} - {INTRADAY_DISPLAY_DAYS} روز معاملاتی اخیر، تایم‌فریم ۳۰ دقیقه")
                    time.sleep(0.4)
            except Exception as e:
                log(f"خطا در ساخت نمودار ۳۰ دقیقه {symbol}: {e}")

            try:
                data15 = yf.download(symbol, period="5d", interval="15m", progress=False)
                if not data15.empty:
                    data15 = data15[["Open", "High", "Low", "Close"]].copy()
                    display_bars_15m = min(26 * INTRADAY_DISPLAY_DAYS, len(data15))
                    chart_15m = build_indicator_chart(
                        data15, display_bars_15m,
                        title=f"{symbol} - {INTRADAY_DISPLAY_DAYS}D 15m",
                        daily_df=daily_df, show_pivots=True,
                    )
                    if chart_15m:
                        send_telegram_photo(chart_15m, f"⏱ {symbol} - {INTRADAY_DISPLAY_DAYS} روز معاملاتی اخیر، تایم‌فریم ۱۵ دقیقه")
                        time.sleep(0.4)
            except Exception as e:
                log(f"خطا در ساخت نمودار ۱۵ دقیقه {symbol}: {e}")

            send_telegram_message(caption)
        except Exception as e:
            log(f"خطا در پردازش {symbol}: {e}")

        if index % 25 == 0:
            log(f"[سهام] {index}/{total} اسکن شد...")
        time.sleep(0.15)


# ==================================================================
# بخش ۱۳: بورس تهران (TSETMC) -- تکمیل‌شده، فعال
# منبع اول: algotik-tse | منبع دوم: pytse-client (فقط برای جبران)
# چون داده‌ی درون‌روزی رسمی برای بورس تهران در دسترس نیست، EMA و شرط
# ۳ کندل قرمز همیشه روی تایم‌فریم روزانه محاسبه میشه.
# ==================================================================
def get_tse_daily_df_fallback(symbol, limit=180):
    try:
        import pytse_client as tse
        ticker = tse.Ticker(symbol)
        hist = ticker.history
        if hist is not None and len(hist) > 0:
            hist = hist.sort_values("date").tail(limit)
            return pd.DataFrame({
                "Open": hist["open"].astype(float).values,
                "High": hist["high"].astype(float).values,
                "Low": hist["low"].astype(float).values,
                "Close": hist["close"].astype(float).values,
            }, index=pd.to_datetime(hist["date"].values))
    except Exception as e:
        log(f"خطا در منبع دوم (pytse-client) برای {symbol}: {e}")
    return None


def get_top_tse_symbols(limit=TSE_RANK_LIMIT):
    import algotik_tse as att
    names = {}
    top_symbols = []
    try:
        data = att.get_market_snapshot()
        stocks_df = data["stocks"]
        real = stocks_df[stocks_df["InstrumentType"].isin(TSE_STOCK_TYPES)].copy()
        real = real.sort_values("Volume", ascending=False)
        names = dict(zip(real["Symbol"], real["Name"]))
        top_symbols = real["Symbol"].head(limit).tolist()
    except Exception as e:
        log(f"⚠️ منبع اول (algotik-tse) برای رتبه‌بندی بازار جواب نداد: {e}")

    if len(top_symbols) < limit:
        log(f"⚠️ فقط {len(top_symbols)} نماد از منبع اول اومد؛ تلاش برای تکمیل تا {limit} از منبع دوم (pytse-client)...")
        try:
            import pytse_client as tse
            all_syms = tse.all_symbols()
            existing = set(top_symbols)
            for s in all_syms:
                if len(top_symbols) >= limit:
                    break
                if s not in existing:
                    top_symbols.append(s)
                    existing.add(s)
        except Exception as e:
            log(f"⚠️ منبع دوم (pytse-client) هم برای تکمیل لیست جواب نداد: {e}")

    log(f"[بورس تهران] در مجموع {len(top_symbols)} از {limit} نماد هدف آماده شد.")
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

    if len(top_symbols) < TSE_RANK_LIMIT:
        log(f"⚠️⚠️ هشدار: در نهایت فقط {len(top_symbols)} نماد بورس تهران (از {TSE_RANK_LIMIT} هدف) در دسترس بود.")

    total = len(top_symbols)

    hist_all = None
    try:
        hist_all = att.get_history(top_symbols, limit=10, progress=False, dropna=False)
    except Exception as e:
        log(f"⚠️ خطا در دریافت تاریخچه‌ی دسته‌جمعی از منبع اول: {e}")

    for index, symbol in enumerate(top_symbols, 1):
        try:
            opens, closes = [], []
            got_from_batch = (
                hist_all is not None and symbol in hist_all.columns.get_level_values(1)
            )
            if got_from_batch:
                opens = hist_all[("Open", symbol)].dropna().tolist()
                closes = hist_all[("Close", symbol)].dropna().tolist()

            if len(closes) < 4:
                fallback_df = get_tse_daily_df_fallback(symbol, limit=10)
                if fallback_df is None or len(fallback_df) < 4:
                    continue
                opens = fallback_df["Open"].tolist()
                closes = fallback_df["Close"].tolist()

            current_price = closes[-1]
            ema_value = calculate_ema(closes, EMA_PERIOD)
            if not ema_value:
                continue

            diff_percent = ((current_price - ema_value) / ema_value) * 100
            if diff_percent > DIFF_THRESHOLD:
                continue

            if REQUIRE_RED_CANDLES:
                if not had_three_red_candles_before_last(opens, closes):
                    continue

            if should_suppress_repeat_alert(f"tse:{symbol}", diff_percent):
                continue

            daily_df = None
            try:
                daily_df = att.get_history(symbol, limit=180, progress=False)
            except Exception as e:
                log(f"منبع اول برای نمودار ۶ ماهه‌ی {symbol} جواب نداد: {e}")
            if daily_df is None or len(daily_df) < 4:
                daily_df = get_tse_daily_df_fallback(symbol, limit=180)
            if daily_df is None or len(daily_df) < 4:
                continue

            pivot_level = pivot_value = None
            if REQUIRE_PIVOT_CONDITION and len(daily_df) >= 2:
                prev_day = daily_df.iloc[-2]
                pivot_ok, pivot_level, pivot_value = price_reached_pivot_support(
                    current_price, prev_day["High"], prev_day["Low"], prev_day["Close"]
                )
                if not pivot_ok:
                    continue

            fa_full_name = names.get(symbol, "")
            pivot_line = f"شرط پیوت ({PIVOT_TYPE}): قیمت به {pivot_level} رسید ({pivot_value:.2f})\n" if pivot_level else ""
            caption = (
                f"🇮🇷 ⚠️ [بورس تهران] هشدار ریزش از EMA!\n"
                f"رتبه (بر اساس حجم امروز): {index} از {total}\n"
                f"نماد: {symbol} ({fa_full_name})\n"
                f"تایم‌فریم: روزانه (داده درون‌روزی رسمی برای بورس تهران در دسترس نیست)\n"
                f"{pivot_line}"
                f"قیمت پایانی: {current_price}\n"
                f"EMA{EMA_PERIOD}: {ema_value:.4f}\n"
                f"فاصله: {diff_percent:.2f}%\n"
                f"⚠️ لینک تردینگ‌ویو و خرید خودکار برای بورس تهران پشتیبانی نمیشه."
            )
            log(caption)

            chart = make_candlestick_chart(daily_df, title=f"{symbol} - 6M Daily")
            if chart:
                send_telegram_photo(chart, f"📊 {symbol} - نمودار ۶ ماهه (روزانه)")
                time.sleep(0.4)

            send_telegram_message(caption)
        except Exception as e:
            log(f"خطا در پردازش نماد بورس تهران {symbol}: {e}")

        if index % 40 == 0:
            log(f"[بورس تهران] {index}/{total} اسکن شد...")


# ==================================================================
# بخش ۱۴: حلقه اصلی برنامه
# ==================================================================
if __name__ == "__main__":
    log("ربات اسکنر چند-بازاره روشن شد...")
    if not TOKEN or not CHAT_ID:
        log("⚠️⚠️⚠️ هشدار: TELEGRAM_TOKEN یا TELEGRAM_CHAT_ID تنظیم نشده!")
    if not AUTHORIZED_TELEGRAM_USER_IDS:
        log("⚠️⚠️⚠️ هشدار: AUTHORIZED_TELEGRAM_USER_IDS تنظیم نشده! فعلاً هیچ‌کس اجازه‌ی خرید نداره.")

    threading.Thread(target=poll_telegram_updates, daemon=True).start()
    log("👂 گوش‌دادن به دکمه‌های تلگرام (خرید/فروش نیمه‌خودکار) شروع شد.")

    send_telegram_message(
        f"✅ ربات اسکنر کریپتو + سهام آمریکا + بورس تهران (EMA{EMA_PERIOD}) روشن شد!\n"
        f"حالت معامله: {'🧪 آزمایشی (DRY_RUN)' if DRY_RUN else '⚠️ واقعی'}\n"
        f"چرخه هر {CYCLE_SECONDS} ثانیه اجرا می‌شه."
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

