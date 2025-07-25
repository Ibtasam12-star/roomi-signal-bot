import requests
import pandas as pd
import time
import asyncio
from datetime import datetime
from ta.trend import MACD
from telegram import Bot

# ========== CONFIG ==========
TELEGRAM_TOKEN = "7633446060:AAGukJWGgruXfdFeV17jaN17uq2qCOCQQME"
CHAT_ID = "-1002693490642"
SYMBOL = "BTC_USDT"
INTERVAL = "1h"
LIMIT = 100
SIGNAL_INTERVAL = 60  # seconds

last_signal_type = None  # buy/sell
last_signal_time = None
bot = Bot(token=TELEGRAM_TOKEN)

# ========== FETCH KLINES ==========
def fetch_klines(symbol, interval, limit=100):
    try:
        url = f"https://api.mexc.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        raw_data = response.json()

        # Only use 6 columns
        cleaned_data = [row[:6] for row in raw_data]
        df = pd.DataFrame(cleaned_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df
    except Exception as e:
        print(f"[ERROR] Failed to fetch {symbol} data: {e}")
        return pd.DataFrame()

# ========== INDICATOR + SIGNAL ==========
def check_macd_signal(df):
    macd = MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    if df["macd"].iloc[-2] < df["macd_signal"].iloc[-2] and df["macd"].iloc[-1] > df["macd_signal"].iloc[-1]:
        return "BUY"
    elif df["macd"].iloc[-2] > df["macd_signal"].iloc[-2] and df["macd"].iloc[-1] < df["macd_signal"].iloc[-1]:
        return "SELL"
    else:
        return None

# ========== SEND TO TELEGRAM ==========
def send_signal(symbol, signal_type, price):
    if signal_type == "BUY":
        tp = round(price * 1.015, 2)
        sl = round(price * 0.985, 2)
    else:
        tp = round(price * 0.985, 2)
        sl = round(price * 1.015, 2)

    message = (
        f"🔔 *{signal_type} Signal* for `{symbol}`\n\n"
        f"💰 Entry: `{price}`\n"
        f"🎯 Take Profit: `{tp}`\n"
        f"🛑 Stop Loss: `{sl}`\n"
        f"🕐 Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
    )
    bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")

# ========== MAIN LOOP ==========
async def main():
    global last_signal_type, last_signal_time

    while True:
        df = fetch_klines(SYMBOL, INTERVAL, LIMIT)
        if df.empty:
            print("[WARNING] No data. Skipping this round.")
            await asyncio.sleep(SIGNAL_INTERVAL)
            continue

        signal = check_macd_signal(df)
        last_close = df["close"].iloc[-1]

        if signal and signal != last_signal_type:
            print(f"[INFO] New signal: {signal} at {last_close}")
            send_signal(SYMBOL, signal, last_close)
            last_signal_type = signal
            last_signal_time = datetime.now()
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No new valid signal.")

        await asyncio.sleep(SIGNAL_INTERVAL)

# ========== AUTO START ==========
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped manually.")
