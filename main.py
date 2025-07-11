import os
import time
from datetime import datetime
import pandas as pd
import ta
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import *

print("\n✅ Bot lancé")

# Charger les clés API
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
client = Client(API_KEY, SECRET_KEY)

# Configuration
ticker = "XRPUSDT"
interval = Client.KLINE_INTERVAL_1MINUTE
capital_percent = 0.95
EMA_FAST = 9
EMA_SLOW = 50
EMA_TREND = 200
TP_PCT = 0.02  # +2 %
SL_PCT = 0.01  # -1 %
in_position = False

# Récupérer les données de marché
def get_klines(symbol, interval, limit=200):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'qav', 'num_trades', 'tbbav', 'tbqav', 'ignore'
    ])
    df['close'] = pd.to_numeric(df['close'])
    return df

# Ajouter les indicateurs EMA + RSI
def add_indicators(df):
    df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=EMA_FAST)
    df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=EMA_SLOW)
    df['ema_trend'] = ta.trend.ema_indicator(df['close'], window=EMA_TREND)
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    return df

# Obtenir le stepSize pour XRPUSDT
def get_step_size(symbol):
    try:
        info = client.get_symbol_info(symbol)
        for f in info["filters"]:
            if f["filterType"] == "LOT_SIZE":
                return float(f["stepSize"])
    except:
        return 1.0
    return 1.0

# Obtenir le solde USDT
def get_usdt_balance():
    try:
        balance = client.get_asset_balance(asset='USDT')
        return float(balance['free'])
    except:
        return 0

# Calculer la quantité de XRP à acheter
def calculate_quantity(price):
    usdt = get_usdt_balance()
    usdt_to_use = usdt * capital_percent
    quantity = usdt_to_use / price
    step_size = get_step_size(ticker)
    quantity = quantity - (quantity % step_size)
    return round(quantity, 1)

# Placer les ordres
def place_order(side, quantity, price):
    try:
        client.create_order(
            symbol=ticker,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )

        tp_price = round(price * (1 + TP_PCT), 4)
        sl_price = round(price * (1 - SL_PCT), 4)

        client.create_order(
            symbol=ticker,
            side=SIDE_SELL,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=quantity,
            price=str(tp_price)
        )

        client.create_order(
            symbol=ticker,
            side=SIDE_SELL,
            type=ORDER_TYPE_STOP_LOSS_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=quantity,
            stopPrice=str(sl_price),
            price=str(sl_price)
        )

        print(f"\n✅ Ordres TP/SL placés pour {quantity} XRP à {price} USDT")
    except Exception as e:
        print(f"❌ Erreur lors des ordres : {e}")

# Boucle principale
def run():
    global in_position
    print("\n🚀 Bot XRPUSDT - M1 - EMA Cross actif")
    while True:
        try:
            df = get_klines(ticker, interval)
            df = add_indicators(df)
            if len(df) < 201:
                print("⏳ Pas assez de données...")
                time.sleep(60)
                continue

            last = df.iloc[-2]
            prev = df.iloc[-3]

            tendance = last['close'] > last['ema_trend']
            croisement = prev['ema_fast'] < prev['ema_slow'] and last['ema_fast'] > last['ema_slow']
            rsi_haut = last['rsi'] > 50
            price = float(last['close'])

            if tendance and croisement and rsi_haut and not in_position:
                qty = calculate_quantity(price)
                if qty > 0:
                    print(f"\n📈 Signal LONG → {qty} XRP à {price}")
                    place_order(SIDE_BUY, qty, price)
                    in_position = True

            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] En attente de signal...")

            time.sleep(60)
        except Exception as e:
            print(f"⚠️ Erreur dans la boucle : {e}")
            time.sleep(60)

if __name__ == "__main__":
    run()
