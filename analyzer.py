import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, filename="trading.log", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def analyze_technical(df, interval_input):
    """Analyse technique avec seuils dynamiques et scores augmentés."""
    last = df.iloc[-1]
    price = last["close"]
    atr = last["ATR_14"]
    volatility = df["close"].pct_change().rolling(window=20).std().iloc[-1] * 100
    if pd.isna(volatility) or volatility == 0:
        logger.warning("Volatilité nulle ou non calculable, utilisation de valeur par défaut")
        volatility = 1.0

    technical_score = 0
    technical_details = []

    # Seuils dynamiques pour RSI
    rsi_overbought = 70 + (volatility if volatility > 5 else 0)
    rsi_oversold = 30 - (volatility if volatility > 5 else 0)

    if last["RSI"] > rsi_overbought:
        technical_score -= 4  # Augmenté de -3 à -4
        technical_details.append(f"RSI > {rsi_overbought:.2f} : suracheté (-4)")
    elif last["RSI"] < rsi_oversold:
        technical_score += 4  # Augmenté de +3 à +4
        technical_details.append(f"RSI < {rsi_oversold:.2f} : survendu (+4)")

    if last["MACD"] > last["MACD_SIGNAL"]:
        technical_score += 4  # Augmenté de +3 à +4
        technical_details.append("MACD haussier (+4)")
    elif last["MACD"] < last["MACD_SIGNAL"]:
        technical_score -= 4  # Augmenté de -3 à -4
        technical_details.append("MACD baissier (-4)")

    if last["EMA_12"] > last["EMA_26"]:
        technical_score += 3  # Augmenté de +2 à +3
        technical_details.append("EMA 12 > EMA 26 : tendance haussière (+3)")
    elif last["EMA_12"] < last["EMA_26"]:
        technical_score -= 3  # Augmenté de -2 à -3
        technical_details.append("EMA 12 < EMA 26 : tendance baissière (-3)")

    if last["ADX"] > 25:
        if last["close"] > last["EMA_20"]:
            technical_score += 3  # Augmenté de +2 à +3
            technical_details.append("ADX > 25 et prix > EMA 20 : forte tendance haussière (+3)")
        else:
            technical_score -= 3  # Augmenté de -2 à -3
            technical_details.append("ADX > 25 et prix < EMA 20 : forte tendance baissière (-3)")

    logger.info(f"Score technique : {technical_score}, Détails : {technical_details}")
    return technical_score, technical_details

def analyze_fundamental(fundamental_data):
    """Analyse fondamentale avec seuils ajustés."""
    fundamental_score = 0
    fundamental_details = []
    if fundamental_data["market_cap"] > 10_000_000_000:  # Réduit de 20B à 10B
        fundamental_score += 4  # Augmenté de +3 à +4
        fundamental_details.append("Market cap élevé (> 10B USD) (+4)")
    if fundamental_data["market_cap"] != 0 and fundamental_data["volume_24h"] / fundamental_data["market_cap"] > 0.01:  # Réduit de 0.02 à 0.01
        fundamental_score += 3  # Augmenté de +2 à +3
        fundamental_details.append("Volume élevé (> 1% market cap) (+3)")
    if fundamental_data["developer_score"] > 50:  # Réduit de 60 à 50
        fundamental_score += 3  # Augmenté de +2 à +3
        fundamental_details.append("Score développeur élevé (> 50) (+3)")
    logger.info(f"Score fondamental : {fundamental_score}, Détails : {fundamental_details}")
    return fundamental_score, fundamental_details

def analyze_macro(macro_data, interval_input):
    """Analyse macroéconomique avec pondération et conditions ajustées."""
    macro_score = 0
    macro_details = []
    weight = {"1H": 0.5, "4H": 0.7, "1D": 1.0, "1W": 1.5}.get(interval_input, 1.0)
    
    fear_greed = macro_data.get("fear_greed_index", 0)
    fng_trend = macro_data.get("fng_trend", [])
    if fear_greed < 30:
        macro_score += int(4 * weight)  # Augmenté de +3 à +4
        macro_details.append("Fear & Greed < 30 : opportunité (+4)")
    elif fear_greed > 70:
        macro_score -= int(4 * weight)  # Augmenté de -3 à -4
        macro_details.append("Fear & Greed > 70 : prudence (-4)")
    if len(fng_trend) >= 2 and fng_trend[-1] > fng_trend[-2]:
        macro_score += int(3 * weight)  # Augmenté de +2 à +3
        macro_details.append("Fear & Greed en hausse (+3)")

    sp500_value = macro_data.get("sp500_value")
    if sp500_value:
        if sp500_value < 4500:
            macro_score -= int(3 * weight)  # Augmenté de -2 à -3
            macro_details.append("S&P 500 < 4500 : marché baissier (-3)")
        else:
            macro_score += int(3 * weight)  # Augmenté de +2 à +3
            macro_details.append("S&P 500 > 4500 : marché haussier (+3)")

    logger.info(f"Score macro : {macro_score}, Détails : {macro_details}")
    return macro_score, macro_details

def generate_recommendation(df, technical_score, fundamental_score, macro_score, interval_input):
    """Génère la recommandation avec validation des prix et seuil réduit."""
    last = df.iloc[-1]
    price = last["close"]
    atr = last["ATR_14"]
    volatility = df["close"].pct_change().rolling(window=20).std().iloc[-1] * 100
    if pd.isna(volatility) or volatility == 0:
        logger.warning("Volatilité nulle, utilisation de valeur par défaut")
        volatility = 1.0

    weights = {"1H": (0.6, 0.2, 0.2), "4H": (0.5, 0.3, 0.2), "1D": (0.4, 0.3, 0.3), "1W": (0.3, 0.3, 0.4)}
    w_tech, w_fund, w_macro = weights[interval_input]
    total_score = technical_score * w_tech + fundamental_score * w_fund + macro_score * w_macro

    score_threshold = 0.5 * (1 + volatility / 100)  # Réduit de 1 à 0.5
    logger.info(f"Total score : {total_score:.2f}, Seuil : {score_threshold:.2f}")

    if total_score > score_threshold:
        signal = "BUY"
        confidence = total_score / (total_score + 4)
    elif total_score < -score_threshold:
        signal = "SELL"
        confidence = abs(total_score) / (abs(total_score) + 4)
    else:
        signal = "HOLD"
        confidence = 0

    buy_price = min(last["SUPPORT"], last["FIBO_0.382"]) + 0.5 * atr
    sell_price = max(last["RESISTANCE"], last["FIBO_0.618"]) - 0.5 * atr
    min_spread = 0.5 + (volatility / 100 if volatility != 0 else 0.01)
    if price != 0 and (sell_price - buy_price) / price * 100 < min_spread:
        buy_price = price * (1 - (atr / price if price != 0 else 0.01))
        sell_price = price * (1 + (atr / price if price != 0 else 0.01))

    if signal == "BUY" and sell_price <= price * 1.05:  # Tolérance augmentée de 1.01 à 1.05
        signal = "HOLD"
        confidence = 0
        logger.info("Signal BUY changé en HOLD : sell_price <= price * 1.05")

    logger.info(f"Signal final : {signal}, Confiance : {confidence:.2%}, Buy : {buy_price:.2f}, Sell : {sell_price:.2f}")
    return signal, confidence, buy_price, sell_price
