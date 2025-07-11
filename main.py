import os
import time
import pandas as pd
import ta
from datetime import datetime
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import *

print("✅ Le script a bien démarré")

# Charger les clés API
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
client = Client(API_KEY, SECRET_KEY)

# Paramètres du bot
SYMBOL = "XRPUSDC"
INTERVAL = Client.KLINE_INTERVAL_1MINUTE
CAPITAL_PERCENT = 0.95
EMA_FAST = 9
EMA_SLOW = 50
EMA_TREND = 200
TP_PCT = 0.02   # +2%
SL_PCT = 0.01   # -1%
in_position = False

def get_step_size(symbol):
    try:
        info = client.get_symbol_info(symbol)
        for f in info["filters"]:
            if f["filterType"] == "LOT_SIZE":
                return float(f["stepSize"])
    except Exception as e:
        print("❌ Erreur récupération stepSize :", e)
    return 0.01

def get_usdc_balance():
    try:
        balance = client.get_asset_balance(asset="USDC")
        return float(balance["free"])
    except Exception as e:
        print("❌ Erreur récupération solde USDC :", e)
        return 0

def calculate_quantity(symbol_price):
    usdc_balance = get_usdc_balance()
    if usdc_balance <= 0:
        print("❌ Solde USDC insuffisant")
        return 0

    equity_to_use = usdc_balance * CAPITAL_PERCENT
    quantity = equity_to_use / symbol_price
    step_size = get_step_size(SYMBOL)
    quantity = quantity - (quantity % step_size)
    quantity = round(quantity, 2)

    if quantity * symbol_price < 10:
        print(f"❌ Quantité trop faible : {quantity} XRP ≈ {quantity * symbol_price:.2f} USDC")
        return 0

    return quantity

def get_klines(symbol, interval, limit=100):
    try:
        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'qav', 'num_trades', 'tbbav', 'tbqav', 'ignore'
        ])
        df['close'] = pd.to_numeric(df['close'])
        return df
    except Exception as e:
        print("❌ Erreur récupération données :", e)
        return pd.DataFrame()

def add_indicators(df):
    df["ema_fast"] = ta.trend.ema_indicator(df["close"], window=EMA_FAST)
    df["ema_slow"] = ta.trend.ema_indicator(df["close"], window=EMA_SLOW)
    df["ema_trend"] = ta.trend.ema_indicator(df["close"], window=EMA_TREND)
    df["rsi"] = ta.momentum.rsi(df["close"], window=14)
    return df

def place_trade(side, quantity, entry_price):
    try:
        tp = round(entry_price * (1 + TP_PCT), 6)
        sl = round(entry_price * (1 - SL_PCT), 6)
        opposite = SIDE_SELL if side == SIDE_BUY else SIDE_BUY

        print(f"\n📈 {side} | Entrée : {entry_price} | TP : {tp} | SL : {sl}")

        client.create_order(
            symbol=SYMBOL,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )

        client.create_order(
            symbol=SYMBOL,
            side=opposite,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=quantity,
            price=str(tp)
        )

        client.create_order(
            symbol=SYMBOL,
            side=opposite,
            type=ORDER_TYPE_STOP_LOSS_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=quantity,
            stopPrice=str(sl),
            price=str(sl)
        )

        print("✅ Ordres TP et SL placés.")
    except Exception as e:
        print("❌ Erreur lors du trade :", e)

def run_bot():
    global in_position

    print("🚀 Bot EMA XRPUSDC M1 lancé...")
    while True:
        try:
            df = get_klines(SYMBOL, INTERVAL)
            if df.empty:
                time.sleep(60)
                continue

            df = add_indicators(df)

            last = df.iloc[-2]
            prev = df.iloc[-3]

            is_trend = last["close"] > last["ema_trend"]
            ema_cross = prev["ema_fast"] < prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
            rsi_ok = last["rsi"] > 50
            price = float(last["close"])

            if is_trend and ema_cross and rsi_ok and not in_position:
                qty = calculate_quantity(price)
                if qty > 0:
                    place_trade(SIDE_BUY, qty, price)
                    in_position = True
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] En attente de signal…")

            time.sleep(60)

        except Exception as e:
            print("⚠️ Erreur dans la boucle :", e)
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
