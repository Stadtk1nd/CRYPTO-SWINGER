import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, filename="trading.log", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def analyze_technical(df, interval_input):
    """Analyse technique avec seuils dynamiques et conditions ajustées."""
    last = df.iloc[-1]
    price = last["close"]
    atr = last["ATR_14"]
    volatility = df["close"].pct_change().rolling(window=20).std().iloc[-1] * 100
    if pd.isna(volatility) or volatility == 0:
        logger.warning("Volatilité nulle ou non calculable, utilisation de valeur par défaut")
        volatility = 1.0

    technical_score = 0
    technical_details = []

    rsi_overbought = 65 + (volatility if volatility > 5 else 0)
    rsi_oversold = 35 - (volatility if volatility > 5 else 0)

    if last["RSI"] > rsi_overbought:
        technical_score -= 4
        technical_details.append(f"RSI > {rsi_overbought:.2f} : suracheté (-4)")
    elif last["RSI"] < rsi_oversold:
        technical_score += 4
        technical_details.append(f"RSI < {rsi_oversold:.2f} : survendu (+4)")

    if last["MACD"] > last["MACD_SIGNAL"]:
        technical_score += 4
        technical_details.append("MACD haussier (+4)")
    elif last["MACD"] < last["MACD_SIGNAL"]:
        technical_score -= 4
        technical_details.append("MACD baissier (-4)")

    if last["EMA_12"] > last["EMA_26"]:
        technical_score += 3
        technical_details.append("EMA 12 > EMA 26 : tendance haussière (+3)")
    elif last["EMA_12"] < last["EMA_26"]:
        technical_score -= 3
        technical_details.append("EMA 12 < EMA 26 : tendance baissière (-3)")

    if last["ADX"] > 25:
        if last["close"] > last["EMA_20"]:
            technical_score += 3
            technical_details.append("ADX > 25 et prix > EMA 20 : forte tendance haussière (+3)")
        else:
            technical_score -= 3
            technical_details.append("ADX > 25 et prix < EMA 20 : forte tendance baissière (-3)")

    avg_volume = df["volume"].rolling(window=20).mean().iloc[-1]
    if avg_volume != 0 and last["volume"] > 2 * avg_volume:
        if last["close"] > last["EMA_20"]:
            technical_score += 2
            technical_details.append("Volume élevé et prix > EMA 20 : signal haussier (+2)")
        else:
            technical_score -= 2
            technical_details.append("Volume élevé et prix < EMA 20 : signal baissier (-2)")

    logger.info(f"Score technique : {technical_score}, Détails : {technical_details}")
    return technical_score, technical_details

def analyze_fundamental(fundamental_data):
    """Analyse fondamentale avec seuils ajustés."""
    fundamental_score = 0
    fundamental_details = []
    if fundamental_data["market_cap"] > 10_000_000_000:
        fundamental_score += 4
        fundamental_details.append("Market cap élevé (> 10B USD) (+4)")
    if fundamental_data["market_cap"] != 0 and fundamental_data["volume_24h"] / fundamental_data["market_cap"] > 0.01:
        fundamental_score += 3
        fundamental_details.append("Volume élevé (> 1% market cap) (+3)")
    if fundamental_data["developer_score"] > 50:
        fundamental_score += 3
        fundamental_details.append("Score développeur élevé (> 50) (+3)")
    logger.info(f"Score fondamental : {fundamental_score}, Détails : {fundamental_details}")
    return fundamental_score, fundamental_details

def analyze_macro(macro_data, interval_input):
    """Analyse macroéconomique avec tous les facteurs demandés."""
    macro_score = 0
    macro_details = []
    weight = {"1H": 0.4, "4H": 0.6, "1D": 0.8, "1W": 1.0}.get(interval_input, 1.0)

    # Indice Fear & Greed
    fear_greed = macro_data.get("fear_greed_index", 0)
    fng_trend = macro_data.get("fng_trend", [])
    if fear_greed < 30:
        macro_score += int(4 * weight)
        macro_details.append("Fear & Greed < 30 : opportunité (+4)")
    elif fear_greed > 70:
        macro_score -= int(4 * weight)
        macro_details.append("Fear & Greed > 70 : prudence (-4)")
    if len(fng_trend) >= 2 and fng_trend[-1] > fng_trend[-2]:
        macro_score += int(3 * weight)
        macro_details.append("Fear & Greed en hausse (+3)")
    elif len(fng_trend) >= 2 and fng_trend[-1] < fng_trend[-2]:
        macro_score -= int(3 * weight)
        macro_details.append("Fear & Greed en baisse (-3)")

    # Taux d’intérêt FED
    fed_rate = macro_data.get("fed_interest_rate", 0)
    if fed_rate > 5:  # Seuil indicatif pour un taux élevé
        macro_score -= int(3 * weight)
        macro_details.append("Taux FED > 5% : pression baissière (-3)")
    elif fed_rate < 2:  # Seuil indicatif pour un taux bas
        macro_score += int(3 * weight)
        macro_details.append("Taux FED < 2% : environnement favorable (+3)")

    # Indice des prix à la consommation (CPI)
    cpi_current = macro_data.get("cpi_current", 0)
    cpi_previous = macro_data.get("cpi_previous", 0)
    if cpi_current and cpi_previous and cpi_previous != 0:
        cpi_inflation = ((cpi_current - cpi_previous) / cpi_previous) * 100  # Variation en %
        if cpi_inflation > 3:  # Inflation élevée
            macro_score -= int(2 * weight)
            macro_details.append(f"Inflation CPI > 3% ({cpi_inflation:.2f}%) : pression baissière (-2)")
        elif cpi_inflation < 1:  # Inflation faible
            macro_score += int(2 * weight)
            macro_details.append(f"Inflation CPI < 1% ({cpi_inflation:.2f}%) : environnement favorable (+2)")

    # PIB USA
    gdp_current = macro_data.get("gdp_current", 0)
    gdp_previous = macro_data.get("gdp_previous", 0)
    if gdp_current and gdp_previous and gdp_previous != 0:
        gdp_growth = ((gdp_current - gdp_previous) / gdp_previous) * 100  # Croissance en %
        if gdp_growth < 1:  # Croissance faible
            macro_score -= int(2 * weight)
            macro_details.append(f"Croissance PIB < 1% ({gdp_growth:.2f}%) : ralentissement économique (-2)")
        elif gdp_growth > 3:  # Croissance forte
            macro_score += int(2 * weight)
            macro_details.append(f"Croissance PIB > 3% ({gdp_growth:.2f}%) : expansion économique (+2)")

    # Taux de chômage USA
    unemployment_rate = macro_data.get("unemployment_rate", 0)
    if unemployment_rate > 5:  # Chômage élevé
        macro_score -= int(2 * weight)
        macro_details.append("Chômage > 5% : faiblesse économique (-2)")
    elif unemployment_rate < 4:  # Chômage bas
        macro_score += int(2 * weight)
        macro_details.append("Chômage < 4% : économie robuste (+2)")

    # S&P 500 : Seuil statique
    sp500_value = macro_data.get("sp500_value", 0)
    if sp500_value:
        if sp500_value < 4500:
            macro_score -= int(3 * weight)
            macro_details.append("S&P 500 < 4500 : marché baissier (-3)")
        else:
            macro_score += int(3 * weight)
            macro_details.append("S&P 500 > 4500 : marché haussier (+3)")

    # S&P 500 : Variation sur 7 jours
    sp500_values = macro_data.get("sp500_values", [])
    if len(sp500_values) >= 2:
        sp500_current = sp500_values[-1]
        sp500_7days_ago = sp500_values[-2] if len(sp500_values) == 2 else sp500_values[-7]  # Approximation
        if sp500_7days_ago != 0:
            sp500_change = ((sp500_current - sp500_7days_ago) / sp500_7days_ago) * 100
            if sp500_change > 2:  # Hausse significative
                macro_score += int(3 * weight)
                macro_details.append(f"S&P 500 +{sp500_change:.2f}% sur 7 jours : tendance haussière (+3)")
            elif sp500_change < -2:  # Baisse significative
                macro_score -= int(3 * weight)
                macro_details.append(f"S&P 500 {sp500_change:.2f}% sur 7 jours : tendance baissière (-3)")

    logger.info(f"Score macro : {macro_score}, Détails : {macro_details}")
    return macro_score, macro_details

def generate_recommendation(df, technical_score, fundamental_score, macro_score, interval_input):
    """Génère la recommandation avec seuil réduit et validation assouplie."""
    last = df.iloc[-1]
    price = last["close"]
    atr = last["ATR_14"]
    volatility = df["close"].pct_change().rolling(window=20).std().iloc[-1] * 100
    if pd.isna(volatility) or volatility == 0:
        logger.warning("Volatilité nulle, utilisation de valeur par défaut")
        volatility = 1.0

    weights = {"1H": (0.5, 0.3, 0.2), "4H": (0.4, 0.3, 0.3), "1D": (0.4, 0.3, 0.3), "1W": (0.3, 0.4, 0.3)}
    w_tech, w_fund, w_macro = weights[interval_input]
    total_score = technical_score * w_tech + fundamental_score * w_fund + macro_score * w_macro

    score_threshold = 0.3 * (1 + volatility / 100)
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

    if signal == "BUY" and sell_price <= price * 1.10:
        signal = "HOLD"
        confidence = 0
        logger.info("Signal BUY changé en HOLD : sell_price <= price * 1.10")

    logger.info(f"Signal final : {signal}, Confiance : {confidence:.2%}, Buy : {buy_price:.2f}, Sell : {sell_price:.2f}")
    return signal, confidence, buy_price, sell_price
