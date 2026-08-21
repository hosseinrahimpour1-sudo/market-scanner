import requests
import time
import os
import io
import yfinance as yf
import pandas as pd
import mplfinance as mpf

# ============================
# تنظیمات اصلی
# ============================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

EMA_PERIOD = 5
DIFF_THRESHOLD = -5  # درصد افت از EMA برای صدور هشدار


def send_telegram_message(text):
    """ارسال پیام متنی به تلگرام"""
    if not TOKEN or not CHAT_ID:
        print("⚠️ توکن یا چت‌آیدی تنظیم نشده! پیام ارسال نشد.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text})
    except:
        pass


def send_telegram_photo(image_bytes, caption):
    """ارسال عکس (نمودار شمعی) همراه با کپشن به تلگرام"""
    if not TOKEN or not CHAT_ID:
        print("⚠️ توکن یا چت‌آیدی تنظیم نشده! عکس ارسال نشد.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        files = {"photo": ("chart.png", image_bytes, "image/png")}
        data = {"chat_id": CHAT_ID, "caption": caption}
        requests.post(url, data=data, files=files)
    except Exception as e:
        print("خطا در ارسال عکس:", e)
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


def make_candlestick_chart(df):
    """ساخت تصویر نمودار شمعی از دیتافریم OHLC و برگردوندن به‌صورت بایت"""
    buf = io.BytesIO()
    try:
        mpf.plot(
            df,
            type="candle",
            style="charles",
            volume=False,
            savefig=dict(fname=buf, dpi=100, bbox_inches="tight"),
        )
        buf.seek(0)
        return buf
    except Exception as e:
        print("خطا در ساخت نمودار:", e)
        return None


# ============================
# بخش کریپتو (بایننس)
# ============================
def get_all_usdt_symbols():
    """دریافت تمام ارزهای تتر از بایننس"""
    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        response = requests.get(url).json()
        symbols = [item['symbol'] for item in response if item['symbol'].endswith('USDT')]
        return symbols
    except:
        print("خطا در دریافت لیست ارزها")
        return []


def check_crypto_market():
    """اسکن بازار کریپتو (بایننس) - کندل ۳۰ دقیقه‌ای"""
    symbols = get_all_usdt_symbols()
    total = len(symbols)
    print(f"[کریپتو] {total} ارز پیدا شد.")

    for index, symbol in enumerate(symbols, 1):
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=30m&limit=10"
            response = requests.get(url).json()
            close_prices = [float(candle[4]) for candle in response]
            current_price = close_prices[-1]
            ema_value = calculate_ema(close_prices, EMA_PERIOD)

            if ema_value:
                diff_percent = ((current_price - ema_value) / ema_value) * 100
                if diff_percent <= DIFF_THRESHOLD:
                    tv_link = f"https://www.tradingview.com/symbols/{symbol}/"
                    caption = (
                        f"🪙 ⚠️ [کریپتو] هشدار ریزش از EMA!\n"
                        f"نماد: {symbol}\n"
                        f"تایم‌فریم: 30m\n"
                        f"قیمت: {current_price}\n"
                        f"EMA{EMA_PERIOD}: {ema_value:.4f}\n"
                        f"فاصله: {diff_percent:.2f}%\n"
                        f"نمودار تردینگ‌ویو: {tv_link}"
                    )
                    print(caption)

                    df = pd.DataFrame(response, columns=[
                        "open_time", "open", "high", "low", "close", "volume",
                        "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"
                    ])
                    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
                    df.set_index("open_time", inplace=True)
                    df = df[["open", "high", "low", "close"]].astype(float)
                    df.columns = ["Open", "High", "Low", "Close"]

                    chart = make_candlestick_chart(df)
                    if chart:
                        send_telegram_photo(chart, caption)
                    else:
                        send_telegram_message(caption)
        except:
            pass

        if index % 50 == 0:
            print(f"[کریپتو] {index}/{total} اسکن شد...")
        time.sleep(0.2)


# ============================
# بخش سهام آمریکا (Yahoo Finance)
# ============================
def get_top100_us_symbols():
    """لیست ۱۰۰ شرکت بزرگ و مهم آمریکا"""
    symbols = [
        "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "AVGO", "TSLA", "BRK-B",
        "JPM", "LLY", "V", "UNH", "XOM", "MA", "COST", "HD", "PG", "NFLX",
        "JNJ", "WMT", "BAC", "CRM", "ABBV", "CVX", "KO", "MRK", "AMD", "PEP",
        "ORCL", "ADBE", "TMO", "LIN", "MCD", "CSCO", "ACN", "ABT", "WFC", "DIS",
        "IBM", "GE", "PM", "CAT", "TXN", "NOW", "INTU", "ISRG", "VZ", "QCOM",
        "AMGN", "CMCSA", "SPGI", "UBER", "BKNG", "NEE", "PFE", "AMAT", "RTX", "LOW",
        "UNP", "T", "HON", "COP", "DE", "PGR", "GS", "ETN", "MS", "SYK",
        "LMT", "BLK", "AXP", "SCHW", "TJX", "BSX", "MU", "MDT", "ADP", "VRTX",
        "GILD", "PLD", "C", "ADI", "SBUX", "MMC", "CB", "REGN", "PANW", "ANET",
        "AMT", "KLAC", "SO", "ELV", "APH", "CI", "CME", "MO", "DUK", "ZTS"
    ]
    return symbols


def check_us_stocks_market():
    """اسکن ۱۰۰ شرکت بزرگ آمریکا (Yahoo Finance) - کندل ۳۰ دقیقه‌ای"""
    symbols = get_top100_us_symbols()
    total = len(symbols)
    print(f"[سهام] {total} نماد پیدا شد.")

    for index, symbol in enumerate(symbols, 1):
        try:
            data = yf.download(symbol, period="5d", interval="30m", progress=False)
            if data.empty or len(data) < EMA_PERIOD:
                continue

            close_prices = data['Close'].values.flatten().tolist()
            current_price = close_prices[-1]
            ema_value = calculate_ema(close_prices, EMA_PERIOD)

            if ema_value:
                diff_percent = ((current_price - ema_value) / ema_value) * 100
                if diff_percent <= DIFF_THRESHOLD:
                    tv_link = f"https://www.tradingview.com/symbols/{symbol}/"
                    caption = (
                        f"📈 ⚠️ [سهام آمریکا] هشدار ریزش از EMA!\n"
                        f"نماد: {symbol}\n"
                        f"تایم‌فریم: 30m\n"
                        f"قیمت: {current_price:.2f}\n"
                        f"EMA{EMA_PERIOD}: {ema_value:.4f}\n"
                        f"فاصله: {diff_percent:.2f}%\n"
                        f"نمودار تردینگ‌ویو: {tv_link}"
                    )
                    print(caption)

                    df = data[["Open", "High", "Low", "Close"]].tail(10).copy()
                    chart = make_candlestick_chart(df)
                    if chart:
                        send_telegram_photo(chart, caption)
                    else:
                        send_telegram_message(caption)
        except:
            pass

        if index % 25 == 0:
            print(f"[سهام] {index}/{total} اسکن شد...")
        time.sleep(0.2)


# ============================
# حلقه اصلی برنامه
# ============================
if __name__ == "__main__":
    print("ربات اسکنر چند-بازاره روشن شد...")

    if not TOKEN or not CHAT_ID:
        print("⚠️⚠️⚠️ هشدار: TELEGRAM_TOKEN یا TELEGRAM_CHAT_ID تنظیم نشده! لطفاً توی Railway Variables تنظیم کن.")

    send_telegram_message(f"✅ ربات اسکنر کریپتو + ۱۰۰ سهام برتر آمریکا (EMA{EMA_PERIOD} - تایم‌فریم 30m) روشن شد!")

    while True:
        start_time = time.time()

        check_crypto_market()
        check_us_stocks_market()

        elapsed = time.time() - start_time
        print(f"یک چرخه کامل در {elapsed:.1f} ثانیه تمام شد.")

        remaining = 180 - elapsed
        if remaining > 0:
            print(f"در حال استراحت به مدت {remaining:.1f} ثانیه...")
            time.sleep(remaining)
