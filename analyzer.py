import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, filename="trading.log", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def analyze_technical(df, interval_input):
    """Analyse technique avec seuils dynamiques et plus de conditions."""
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
        technical_score -= 2
        technical_details.append(f"RSI > {rsi_overbought:.2f} : suracheté (-2)")
    elif last["RSI"] < rsi_oversold:
        technical_score += 2
        technical_details.append(f"RSI < {rsi_oversold:.2f} : survendu (+2)")

    if last["MACD"] > last["MACD_SIGNAL"]:
        technical_score += 2
        technical_details.append("MACD haussier (+2)")
    elif last["MACD"] < last["MACD_SIGNAL"]:
        technical_score -= 2
        technical_details.append("MACD baissier (-2)")

    # Ajout de conditions sur EMA et ADX
    if last["EMA_12"] > last["EMA_26"]:
        technical_score += 1
        technical_details.append("EMA 12 > EMA 26 : tendance haussière (+1)")
    elif last["EMA_12"] < last["EMA_26"]:
        technical_score -= 1
        technical_details.append("EMA 12 < EMA 26 : tendance baissière (-1)")

    if last["ADX"] > 25:
        if last["close"] > last["EMA_20"]:
            technical_score += 1
            technical_details.append("ADX > 25 et prix > EMA 20 : forte tendance haussière (+1)")
        else:
            technical_score -= 1
            technical_details.append("ADX > 25 et prix < EMA 20 : forte tendance baissière (-1)")

    logger.info(f"Score technique : {technical_score}, Détails : {technical_details}")
    return technical_score, technical_details

def analyze_fundamental(fundamental_data):
    """Analyse fondamentale avec seuils ajustés."""
    fundamental_score = 0
    fundamental_details = []
    if fundamental_data["market_cap"] > 50_000_000_000:  # Réduit de 100B à 50B
        fundamental_score += 2
        fundamental_details.append("Market cap élevé (> 50B USD) (+2)")
    if fundamental_data["market_cap"] != 0 and fundamental_data["volume_24h"] / fundamental_data["market_cap"] > 0.03:  # Réduit de 0.05 à 0.03
        fundamental_score += 2
        fundamental_details.append("Volume élevé (> 3% market cap) (+2)")
    if fundamental_data["developer_score"] > 70:
        fundamental_score += 1
        fundamental_details.append("Score développeur élevé (> 70) (+1)")
    logger.info(f"Score fondamental : {fundamental_score}, Détails : {fundamental_details}")
    return fundamental_score, fundamental_details

def analyze_macro(macro_data, interval_input):
    """Analyse macroéconomique avec pondération et conditions ajustées."""
    macro_score = 0
    macro_details = []
    weight = {"1H": 0.5, "4H": 0.7, "1D": 1.0, "1W": 1.5}.get(interval_input, 1.0)
    
    # Fear & Greed avec tendance
    fear_greed = macro_data.get("fear_greed_index", 0)
    fng_trend = macro_data.get("fng_trend", [])
    if fear_greed < 30:  # Réduit de 25 à 30
        macro_score += int(2 * weight)
        macro_details.append("Fear & Greed < 30 : opportunité (+2)")
    elif fear_greed > 70:
        macro_score -= int(2 * weight)
        macro_details.append("Fear & Greed > 70 : prudence (-2)")
    if len(fng_trend) >= 2 and fng_trend[-1] > fng_trend[-2]:
        macro_score += int(1 * weight)
        macro_details.append("Fear & Greed en hausse (+1)")

    # S&P 500
    sp500_value = macro_data.get("sp500_value")
    if sp500_value:
        if sp500_value < 4500:  # Ajusté de 4000 à 4500
            macro_score -= int(1 * weight)
            macro_details.append("S&P 500 < 4500 : marché baissier (-1)")
        else:
            macro_score += int(1 * weight)
            macro_details.append("S&P 500 > 4500 : marché haussier (+1)")

    logger.info(f"Score macro : {macro_score}, Détails : {macro_details}")
    return macro_score, macro_details

def generate_recommendation(df, technical_score, fundamental_score, macro_score, interval_input):
    """Génère la recommandation avec validation des prix et seuil ajusté."""
    last = df.iloc[-1]
    price = last["close"]
    atr = last["ATR_14"]
    volatility = df["close"].pct_change().rolling(window=20).std().iloc[-1] * 100
    if pd.isna(volatility) or volatility == 0:
        logger.warning("Volatilité nulle, utilisation de valeur par défaut")
        volatility = 1.0

    # Pondération des scores
    weights = {"1H": (0.6, 0.2, 0.2), "4H": (0.5, 0.3, 0.2), "1D": (0.4, 0.3, 0.3), "1W": (0.3, 0.3, 0.4)}
    w_tech, w_fund, w_macro = weights[interval_input]
    total_score = technical_score * w_tech + fundamental_score * w_fund + macro_score * w_macro

    # Seuil dynamique ajusté
    score_threshold = 2 * (1 + volatility / 100)  # Réduit de 4 à 2
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

    # Calcul et validation des prix cibles
    buy_price = min(last["SUPPORT"], last["FIBO_0.382"]) + 0.5 * atr
    sell_price = max(last["RESISTANCE"], last["FIBO_0.618"]) - 0.5 * atr
    min_spread = 0.5 + (volatility / 100 if volatility != 0 else 0.01)
    if price != 0 and (sell_price - buy_price) / price * 100 < min_spread:
        buy_price = price * (1 - (atr / price if price != 0 else 0.01))
        sell_price = price * (1 + (atr / price if price != 0 else 0.01))

    # Assouplir la condition pour éviter un HOLD forcé
    if signal == "BUY" and sell_price <= price * 1.01:  # Tolérance de 1%
        signal = "HOLD"
        confidence = 0
        logger.info("Signal BUY changé en HOLD : sell_price <= price * 1.01")

    logger.info(f"Signal final : {signal}, Confiance : {confidence:.2%}, Buy : {buy_price:.2f}, Sell : {sell_price:.2f}")
    return signal, confidence, buy_price, sell_price
