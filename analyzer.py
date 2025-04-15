import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, filename="trading.log", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def analyze_technical(df, interval_input):
    """Analyse technique avec seuils dynamiques."""
    last = df.iloc[-1]
    price = last["close"]
    atr = last["ATR_14"]
    volatility = df["close"].pct_change().rolling(window=20).std().iloc[-1] * 100

    technical_score = 0
    technical_details = []

    # Seuils dynamiques pour RSI
    rsi_overbought = 70 + (volatility if volatility > 5 else 0)
    rsi_oversold = 30 - (volatility if volatility > 5 else 0)

    if last["RSI"] > rsi_overbought:
        technical_score -= 1
        technical_details.append(f"RSI > {rsi_overbought:.2f} : suracheté (-1)")
    elif last["RSI"] < rsi_oversold:
        technical_score += 1
        technical_details.append(f"RSI < {rsi_oversold:.2f} : survendu (+1)")

    if last["MACD"] > last["MACD_SIGNAL"]:
        technical_score += 2
        technical_details.append("MACD haussier (+2)")
    elif last["MACD"] < last["MACD_SIGNAL"]:
        technical_score -= 2
        technical_details.append("MACD baissier (-2)")

    # Ajouter d'autres indicateurs (simplifié pour l'exemple)
    return technical_score, technical_details

def analyze_fundamental(fundamental_data):
    """Analyse fondamentale."""
    fundamental_score = 0
    fundamental_details = []
    if fundamental_data["market_cap"] > 100_000_000_000:
        fundamental_score += 2
        fundamental_details.append("Market cap élevé (> 100B USD) (+2)")
    if fundamental_data["volume_24h"] / fundamental_data["market_cap"] > 0.05:
        fundamental_score += 1
        fundamental_details.append("Volume élevé (+1)")
    return fundamental_score, fundamental_details

def analyze_macro(macro_data, interval_input):
    """Analyse macroéconomique avec pondération."""
    macro_score = 0
    macro_details = []
    weight = {"1H": 0.5, "4H": 0.7, "1D": 1.0, "1W": 1.5}.get(interval_input, 1.0)
    
    if macro_data.get("fear_greed_index", 0) < 25:
        macro_score += int(2 * weight)
        macro_details.append("Fear & Greed < 25 : opportunité (+2)")
    return macro_score, macro_details

def generate_recommendation(df, technical_score, fundamental_score, macro_score, interval_input):
    """Génère la recommandation avec validation des prix."""
    last = df.iloc[-1]
    price = last["close"]
    atr = last["ATR_14"]
    volatility = df["close"].pct_change().rolling(window=20).std().iloc[-1] * 100

    # Pondération des scores
    weights = {"1H": (0.6, 0.2, 0.2), "4H": (0.5, 0.3, 0.2), "1D": (0.4, 0.3, 0.3), "1W": (0.3, 0.3, 0.4)}
    w_tech, w_fund, w_macro = weights[interval_input]
    total_score = technical_score * w_tech + fundamental_score * w_fund + macro_score * w_macro

    # Seuil dynamique
    score_threshold = 4 * (1 + volatility / 100)
    if total_score > score_threshold:
        signal = "BUY"
        confidence = total_score / (total_score + 4)
    elif total_score < -score_threshold:
        signal = "SELL"
        confidence = abs(total_score) / (abs(total_score) + 4)
    else:
        signal = "HOLD"
        confidence = 0

    # Calcul et validation des prix cibles
    buy_price = min(last["SUPPORT"], last["FIBO_0.382"]) + 0.5 * atr
    sell_price = max(last["RESISTANCE"], last["FIBO_0.618"]) - 0.5 * atr
    min_spread = 0.5 + volatility / 100  # Spread minimum ajusté
    if (sell_price - buy_price) / price * 100 < min_spread:
        buy_price = price * (1 - atr / price)
        sell_price = price * (1 + atr / price)

    if signal == "BUY" and sell_price <= price:
        signal = "HOLD"
        confidence = 0

    return signal, confidence, buy_price, sell_price