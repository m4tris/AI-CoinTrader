import requests
import pandas as pd
import ta
from datetime import datetime
import os
import time
from dotenv import load_dotenv
from openai import OpenAI

# Ortam değişkenlerini yükle (.env içinde OPENAI_API_KEY olmalı)
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)


def get_usdt_pairs():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    data = requests.get(url).json()
    return [
        s["symbol"] for s in data["symbols"]
        if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
    ]


def get_klines_df(symbol, interval="1h", limit=200):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    data = requests.get(url, params=params).json()
    df = pd.DataFrame(data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    # Sayısal sütunları float'a dönüştür
    df[["close", "high", "low", "volume"]] = df[["close", "high", "low", "volume"]].apply(pd.to_numeric)
    return df


def calculate_fib_levels(df):
    high = df["high"].tail(100).max()
    low = df["low"].tail(100).min()
    diff = high - low
    return {
        "fib_0": round(low, 4),
        "fib_23_6": round(high - 0.236 * diff, 4),
        "fib_38_2": round(high - 0.382 * diff, 4),
        "fib_50": round(high - 0.5 * diff, 4),
        "fib_61_8": round(high - 0.618 * diff, 4),
        "fib_100": round(high, 4),
    }


def calculate_support_resistance(df, window=20):
    support = df['low'].rolling(window=window).min().iloc[-1]
    resistance = df['high'].rolling(window=window).max().iloc[-1]
    return round(support, 4), round(resistance, 4)


def analyze_single_timeframe(df):
    df = df.dropna()
    if len(df) < 200:
        return None

    df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()
    df["stoch_rsi"] = ta.momentum.StochRSIIndicator(df["close"]).stochrsi_k()
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["ema50"] = ta.trend.EMAIndicator(df["close"], 50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(df["close"], 200).ema_indicator()
    df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"]).average_true_range()
    bb = ta.volatility.BollingerBands(df["close"])
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["momentum"] = df["close"] - df["close"].shift(10)
    df["vol_avg"] = df["volume"].rolling(50).mean()
    df["obv"] = ta.volume.OnBalanceVolumeIndicator(df["close"], df["volume"]).on_balance_volume()
    df["adx"] = ta.trend.ADXIndicator(df["high"], df["low"], df["close"]).adx()
    df["cci"] = ta.trend.CCIIndicator(df["high"], df["low"], df["close"]).cci()
    df["williams_r"] = ta.momentum.WilliamsRIndicator(df["high"], df["low"], df["close"]).williams_r()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    fib = calculate_fib_levels(df)
    support, resistance = calculate_support_resistance(df)

    score = 0
    if last["rsi"] < 30: score += 3
    elif last["rsi"] < 50: score += 1
    if last["stoch_rsi"] < 0.2: score += 2
    if last["macd"] > last["macd_signal"]: score += 2
    if last["ema50"] > last["ema200"]: score += 2
    if last["volume"] > last["vol_avg"]: score += 1
    if last["rsi"] > prev["rsi"]: score += 1
    if last["macd"] > prev["macd"]: score += 1
    if last["adx"] > 25: score += 2
    if last["cci"] < -100: score += 1
    if last["williams_r"] < -80: score += 1

    return {
        "score": score,
        "rsi": round(last["rsi"], 2),
        "stoch_rsi": round(last["stoch_rsi"], 4),
        "macd": round(last["macd"], 4),
        "macd_signal": round(last["macd_signal"], 4),
        "ema50": round(last["ema50"], 2),
        "ema200": round(last["ema200"], 2),
        "atr": round(last["atr"], 4),
        "bb_upper": round(last["bb_upper"], 2),
        "bb_lower": round(last["bb_lower"], 2),
        "momentum": round(last["momentum"], 4),
        "volume": round(last["volume"], 2),
        "vol_avg": round(last["vol_avg"], 2),
        "obv": round(last["obv"], 2),
        "fib_0": fib["fib_0"],
        "fib_23_6": fib["fib_23_6"],
        "fib_38_2": fib["fib_38_2"],
        "fib_50": fib["fib_50"],
        "fib_61_8": fib["fib_61_8"],
        "fib_100": fib["fib_100"],
        "support": support,
        "resistance": resistance,
    }


def analyze_coin(symbol):
    intervals = ["1h", "4h", "1d"]
    scores = []
    datas = []

    for interval in intervals:
        df = get_klines_df(symbol, interval=interval)
        result = analyze_single_timeframe(df)
        if result is None:
            return None
        scores.append(result["score"])
        datas.append(result)
        time.sleep(0.15)  # API limit için bekleme

    avg_score = sum(scores) / len(scores)
    main_data = datas[-1]  # 1d timeframe verisi
    main_data["symbol"] = symbol
    main_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    main_data["score"] = avg_score

    return main_data


def ask_gpt(coin_data):
    prompt = (
        f"Bir kripto paranın teknik göstergeleri aşağıda verilmiştir. "
        f"Lütfen sadece 'AL' veya 'ALMA' kararı ver. Kısa ve net ol.\n\n"
        f"Coin: {coin_data['symbol']}\n"
        f"RSI: {coin_data['rsi']}\n"
        f"MACD: {coin_data['macd']} (Signal: {coin_data['macd_signal']})\n"
        f"EMA50: {coin_data['ema50']} vs EMA200: {coin_data['ema200']}\n"
        f"Destek: {coin_data['support']}\n"
        f"Direnç: {coin_data['resistance']}\n"
        f"ATR (Volatilite): {coin_data['atr']}\n"
        f"Puan: {round(coin_data['score'], 2)}\n\n"
        f"Lütfen karar ver."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Sen profesyonel bir kripto para teknik analiz uzmanısın."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"GPT Hatası: {e}"


def scan_market(min_score=8, max_coins=100):
    symbols = get_usdt_pairs()[:max_coins]
    analyzed = []

    for sym in symbols:
        try:
            result = analyze_coin(sym)
            if result and result["score"] >= min_score:
                analyzed.append(result)
        except Exception as e:
            print(f"{sym} analiz hatası: {e}")

    return analyzed


if __name__ == "__main__":
    high_score_coins = scan_market(min_score=8, max_coins=100)

    if high_score_coins:
        best = max(high_score_coins, key=lambda x: x["score"])
        print(f"\n🔝 En iyi coin: {best['symbol']} (Score: {round(best['score'], 2)})")
        print("Detaylı veriler:", best)
    else:
        print("Yüksek puanlı coin bulunamadı.")
