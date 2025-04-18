VERSION = "1.0.7"  # Incrémenté de 1.0.6 pour ajout analyse Bollinger et divergences RSI

import pandas as pd
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constantes
MARKET_CAP_THRESHOLD = 10_000_000_000
TVL_THRESHOLD = 1_000_000_000
VOLUME_RATIO_THRESHOLD = 0.01
SPY_THRESHOLD = 400  # Ajusté pour ETF SPY

def _check_mtfa_trend(price_data_dict, interval_input, is_bullish):
    """Vérifie la tendance MTFA pour haussier ou baissier."""
    trend_confirmed = True
    for timeframe in ["4h", "1d", "1w"]:
        if timeframe in price_data_dict and not price_data_dict[timeframe].empty:
            tf_last = price_data_dict[timeframe].iloc[-1]
            if is_bullish and tf_last["EMA_12"] < tf_last["EMA_26"]:
                trend_confirmed = False
                break
            elif not is_bullish and tf_last["EMA_12"] > tf_last["EMA_26"]:
                trend_confirmed = False
                break
    return trend_confirmed

def analyze_technical(df, interval_input, price_data_dict):
    """Analyse technique avec seuils dynamiques et MTFA."""
    interval_input = interval_input.upper()
    last = df.iloc[-1]
    price = last["close"]
    atr = last["ATR_14"]
    volatility = df["close"].pct_change().rolling(window=20).std().iloc[-1] * 100
    if pd.isna(volatility) or volatility == 0:
        volatility = 1.0

    technical_score = 0
    technical_details = []

    # Seuils RSI
    rsi_weight = {"1H": 1.2, "4H": 1.0, "1D": 0.8, "1W": 0.6}.get(interval_input, 1.0)
    rsi_overbought = 65 + (volatility if volatility > 5 else 0)
    rsi_oversold = 35 - (volatility if volatility > 5 else 0)
    if last["RSI"] > rsi_overbought:
        technical_score -= int(4 * rsi_weight)
        technical_details.append(f"RSI > {rsi_overbought:.2f} : suracheté (-{int(4 * rsi_weight)})")
    elif last["RSI"] < rsi_oversold:
        technical_score += int(4 * rsi_weight)
        technical_details.append(f"RSI < {rsi_oversold:.2f} : survendu (+{int(4 * rsi_weight)})")

    # MACD
    macd_weight = {"1H": 1.2, "4H": 1.0, "1D": 0.8, "1W": 0.6}.get(interval_input, 1.0)
    if last["MACD"] > last["MACD_SIGNAL"]:
        technical_score += int(4 * macd_weight)
        technical_details.append(f"MACD haussier (+{int(4 * macd_weight)})")
    elif last["MACD"] < last["MACD_SIGNAL"]:
        technical_score -= int(4 * macd_weight)
        technical_details.append(f"MACD baissier (-{int(4 * macd_weight)})")

    # EMA avec MTFA
    ema_weight = {"1H": 1.2, "4H": 1.0, "1D": 0.8, "1W": 0.6}.get(interval_input, 1.0)
    if last["EMA_12"] > last["EMA_26"]:
        technical_score += int(3 * ema_weight)
        technical_details.append(f"EMA 12 > EMA 26 : haussier (+{int(3 * ema_weight)})")
        if _check_mtfa_trend(price_data_dict, interval_input, is_bullish=True):
            technical_score += 2
            technical_details.append("Tendance haussière confirmée par MTFA (+2)")
    elif last["EMA_12"] < last["EMA_26"]:
        technical_score -= int(3 * ema_weight)
        technical_details.append(f"EMA 12 < EMA 26 : baissier (-{int(3 * ema_weight)})")
        if _check_mtfa_trend(price_data_dict, interval_input, is_bullish=False):
            technical_score -= 2
            technical_details.append("Tendance baissière confirmée par MTFA (-2)")

    # ADX
    adx_weight = {"1H": 1.0, "4H": 1.0, "1D": 1.2, "1W": 1.2}.get(interval_input, 1.0)
    if last["ADX"] > 25:
        if last["close"] > last["EMA_20"]:
            technical_score += int(3 * adx_weight)
            technical_details.append(f"ADX > 25 et prix > EMA 20 : forte hausse (+{int(3 * adx_weight)})")
        else:
            technical_score -= int(3 * adx_weight)
            technical_details.append(f"ADX > 25 et prix < EMA 20 : forte baisse (-{int(3 * adx_weight)})")

    # Volume
    volume_weight = {"1H": 1.2, "4H": 1.0, "1D": 0.8, "1W": 0.6}.get(interval_input, 1.0)
    avg_volume = df["volume"].rolling(window=20).mean().iloc[-1]
    if avg_volume != 0 and last["volume"] > 2 * avg_volume:
        if last["close"] > last["EMA_20"]:
            technical_score += int(2 * volume_weight)
            technical_details.append(f"Volume élevé et prix > EMA 20 : haussier (+{int(2 * volume_weight)})")
        else:
            technical_score -= int(2 * volume_weight)
            technical_details.append(f"Volume élevé et prix < EMA 20 : baissier (-{int(2 * volume_weight)})")

    # Bandes de Bollinger
    bb_weight = {"1H": 1.2, "4H": 1.0, "1D": 0.8, "1W": 0.6}.get(interval_input, 1.0)
    if last["close"] <= last["BB_LOWER"]:
        technical_score += int(3 * bb_weight)
        technical_details.append(f"Prix <= BB_LOWER : survendu (+{int(3 * bb_weight)})")
    elif last["close"] >= last["BB_UPPER"]:
        technical_score -= int(3 * bb_weight)
        technical_details.append(f"Prix >= BB_UPPER : suracheté (-{int(3 * bb_weight)})")

    # Divergences RSI
    div_weight = {"1H": 1.2, "4H": 1.0, "1D": 0.8, "1W": 0.6}.get(interval_input, 1.0)
    if last["RSI_DIVERGENCE"] == 1:
        technical_score += int(3 * div_weight)
        technical_details.append(f"Divergence haussière RSI (+{int(3 * div_weight)})")
    elif last["RSI_DIVERGENCE"] == -1:
        technical_score -= int(3 * div_weight)
        technical_details.append(f"Divergence baissière RSI (-{int(3 * div_weight)})")

    return technical_score, technical_details

def analyze_fundamental(fundamental_data):
    """Analyse fondamentale avec seuils constants."""
    fundamental_score = 0
    fundamental_details = []

    if fundamental_data["market_cap"] > MARKET_CAP_THRESHOLD:
        fundamental_score += 3
        fundamental_details.append(f"Market cap élevé (> {MARKET_CAP_THRESHOLD/1_000_000_000}B USD) (+3)")
    if fundamental_data["market_cap"] != 0 and fundamental_data["volume_24h"] / fundamental_data["market_cap"] > VOLUME_RATIO_THRESHOLD:
        fundamental_score += 2
        fundamental_details.append(f"Volume élevé (> {VOLUME_RATIO_THRESHOLD*100}% market cap) (+2)")
    if fundamental_data["tvl"] > TVL_THRESHOLD:
        fundamental_score += 3
        fundamental_details.append(f"TVL élevé (> {TVL_THRESHOLD/1_000_000_000}B USD) (+3)")

    return fundamental_score, fundamental_details

def analyze_macro(macro_data, interval_input):
    """Analyse macroéconomique avec VIX et Fear & Greed."""
    interval_input = interval_input.upper()
    macro_score = 0
    macro_details = []
    weight = {"1H": 0.2, "4H": 0.4, "1D": 0.6, "1W": 0.8}.get(interval_input, 1.0)

    fear_greed = macro_data.get("fear_greed_index", 0)
    fng_trend = macro_data.get("fng_trend", [])
    if fear_greed < 30:
        macro_score += int(2 * weight)
        macro_details.append(f"Fear & Greed < 30 : opportunité (+{int(2 * weight)})")
    elif fear_greed > 70:
        macro_score -= int(2 * weight)
        macro_details.append(f"Fear & Greed > 70 : prudence (-{int(2 * weight)})")
    if len(fng_trend) >= 2 and fng_trend[-1] > fng_trend[-2]:
        macro_score += int(1 * weight)
        macro_details.append(f"Fear & Greed en hausse (+{int(1 * weight)})")
    elif len(fng_trend) >= 2 and fng_trend[-1] < fng_trend[-2]:
        macro_score -= int(1 * weight)
        macro_details.append(f"Fear & Greed en baisse (-{int(1 * weight)})")

    vix_value = macro_data.get("vix_value", 0)
    vix_trend = macro_data.get("vix_trend", [])
    if vix_value > 30:
        macro_score -= int(3 * weight)
        macro_details.append(f"VIX > 30 : forte volatilité (-{int(3 * weight)})")
    elif vix_value < 15:
        macro_score += int(3 * weight)
        macro_details.append(f"VIX < 15 : marché stable (+{int(3 * weight)})")
    if len(vix_trend) >= 2 and vix_trend[-1] > vix_trend[-2]:
        macro_score -= int(2 * weight)
        macro_details.append(f"VIX en hausse : volatilité croissante (-{int(2 * weight)})")
    elif len(vix_trend) >= 2 and vix_trend[-1] < vix_trend[-2]:
        macro_score += int(2 * weight)
        macro_details.append(f"VIX en baisse : volatilité décroissante (+{int(2 * weight)})")

    fed_rate = macro_data.get("fed_interest_rate", 0)
    if fed_rate > 5:
        macro_score -= int(3 * weight)
        macro_details.append(f"Taux FED > 5% : pression baissière (-{int(3 * weight)})")
    elif fed_rate < 2:
        macro_score += int(3 * weight)
        macro_details.append(f"Taux FED < 2% : favorable (+{int(3 * weight)})")

    cpi_current = macro_data.get("cpi_current", 0)
    cpi_previous = macro_data.get("cpi_previous", 0)
    if cpi_current and cpi_previous and cpi_previous != 0:
        cpi_inflation = ((cpi_current - cpi_previous) / cpi_previous) * 100
        if cpi_inflation > 3:
            macro_score -= int(2 * weight)
            macro_details.append(f"Inflation CPI > 3% ({cpi_inflation:.2f}%) : pression baissière (-{int(2 * weight)})")
        elif cpi_inflation < 1:
            macro_score += int(2 * weight)
            macro_details.append(f"Inflation CPI < 1% ({cpi_inflation:.2f}%) : favorable (+{int(2 * weight)})")

    gdp_current = macro_data.get("gdp_current", 0)
    gdp_previous = macro_data.get("gdp_previous", 0)
    if gdp_current and gdp_previous and gdp_previous != 0:
        gdp_growth = ((gdp_current - gdp_previous) / gdp_previous) * 100
        if gdp_growth < 1:
            macro_score -= int(2 * weight)
            macro_details.append(f"PIB < 1% ({gdp_growth:.2f}%) : ralentissement (-{int(2 * weight)})")
        elif gdp_growth > 3:
            macro_score += int(2 * weight)
            macro_details.append(f"PIB > 3% ({gdp_growth:.2f}%) : expansion (+{int(2 * weight)})")

    unemployment_rate = macro_data.get("unemployment_rate", 0)
    if unemployment_rate > 5:
        macro_score -= int(2 * weight)
        macro_details.append(f"Chômage > 5% : faiblesse économique (-{int(2 * weight)})")
    elif unemployment_rate < 4:
        macro_score += int(2 * weight)
        macro_details.append(f"Chômage < 4% : économie robuste (+{int(2 * weight)})")

    sp500_value = macro_data.get("sp500_value", 0)
    if sp500_value:
        if sp500_value < SPY_THRESHOLD:
            macro_score -= int(3 * weight)
            macro_details.append(f"SPY < {SPY_THRESHOLD} : marché baissier (-{int(3 * weight)})")
        else:
            macro_score += int(3 * weight)
            macro_details.append(f"SPY > {SPY_THRESHOLD} : marché haussier (+{int(3 * weight)})")

    sp500_values = macro_data.get("sp500_values", [])
    if len(sp500_values) >= 2:
        sp500_current = sp500_values[-1]
        sp500_7days_ago = sp500_values[-2] if len(sp500_values) == 2 else sp500_values[-7]
        if sp500_7days_ago != 0:
            sp500_change = ((sp500_current - sp500_7days_ago) / sp500_7days_ago) * 100
            if sp500_change > 2:
                macro_score += int(1 * weight)
                macro_details.append(f"SPY +{sp500_change:.2f}% sur 7 jours : haussier (+{int(1 * weight)})")
            elif sp500_change < -2:
                macro_score -= int(1 * weight)
                macro_details.append(f"SPY {sp500_change:.2f}% sur 7 jours : baissier (-{int(1 * weight)})")

    return macro_score, macro_details

def generate_recommendation(df, technical_score, fundamental_score, macro_score, interval_input, price_data_dict):
    """Génère la recommandation avec MTFA."""
    interval_input = interval_input.upper()
    last = df.iloc[-1]
    price = last["close"]
    atr = last["ATR_14"]
    volatility = df["close"].pct_change().rolling(window=20).std().iloc[-1] * 100
    if pd.isna(volatility) or volatility == 0:
        volatility = 1.0
    capped_volatility = min(volatility, 10)  # Limiter l'impact

    # Calcul des scores techniques MTFA
    intervals = ["1h", "4h", "1d", "1w"]
    technical_scores = {interval_input.lower(): technical_score}
    for interval in intervals:
        if interval != interval_input.lower() and interval in price_data_dict and not price_data_dict[interval].empty:
            score, _ = analyze_technical(price_data_dict[interval], interval.upper(), price_data_dict)
            technical_scores[interval] = score

    # Poids MTFA
    weights = {
        "1H": (0.6, 0.2, 0.2),
        "4H": (0.5, 0.3, 0.2),
        "1D": (0.4, 0.3, 0.3),
        "1W": (0.3, 0.4, 0.3)
    }
    w_tech, w_fund, w_macro = weights[interval_input]

    # Ajustement score technique
    mtfa_weight = {"1h": 0.1, "4h": 0.2, "1d": 0.3, "1w": 0.4}
    adjusted_technical_score = technical_score
    for interval, score in technical_scores.items():
        if interval != interval_input.lower():
            weight = mtfa_weight.get(interval, 0)
            adjusted_technical_score += score * weight

    # Score total
    total_score = (adjusted_technical_score * w_tech + fundamental_score * w_fund + macro_score * w_macro) * (1 + capped_volatility / 200)
    score_threshold = 0.3 * (1 + capped_volatility / 100)

    if total_score > score_threshold:
        signal = "BUY"
        confidence = total_score / (total_score + 4)
    elif total_score < -score_threshold:
        signal = "SELL"
        confidence = abs(total_score) / (abs(total_score) + 4)
    else:
        signal = "HOLD"
        confidence = 0

    # Prix achat/vente
    volatility_factor = {"1H": 1.0, "4H": 1.5, "1D": 2.0, "1W": 3.0}.get(interval_input, 1.0)
    if signal == "BUY":
        buy_price = max(price - 0.5 * atr, last["SUPPORT"])
        sell_price = min(price + atr * volatility_factor, last["FIBO_0.618"])
    elif signal == "SELL":
        sell_price = min(price + 0.5 * atr, last["RESISTANCE"])
        buy_price = max(price - atr * volatility_factor, last["FIBO_0.382"])
    else:
        buy_price = price - 0.5 * atr
        sell_price = price + 0.5 * atr

    # Ajustement MTFA
    for timeframe in ["4h", "1d", "1w"]:
        if timeframe in price_data_dict and not price_data_dict[timeframe].empty:
            tf_last = price_data_dict[timeframe].iloc[-1]
            buy_price = max(buy_price, tf_last["SUPPORT"])
            sell_price = min(sell_price, tf_last["RESISTANCE"])

    # Validation déviation
    max_deviation = {"1H": 0.02, "4H": 0.03, "1D": 0.05, "1W": 0.10}.get(interval_input, 0.05)
    if price != 0:
        if buy_price < price * (1 - max_deviation):
            buy_price = price * (1 - max_deviation)
        if sell_price > price * (1 + max_deviation):
            sell_price = price * (1 + max_deviation)

    # Spread minimum
    min_spread = 0.5 + (capped_volatility / 100 if capped_volatility != 0 else 0.01)
    if price != 0 and (sell_price - buy_price) / price * 100 < min_spread:
        buy_price = price * (1 - (atr / price if price != 0 else 0.01))
        sell_price = price * (1 + (atr / price if price != 0 else 0.01))

    # Vérification signal BUY
    if signal == "BUY" and sell_price <= price * 1.02:
        signal = "HOLD"
        confidence = 0

    logger.info(f"Signal: {signal}, Confiance: {confidence:.2%}, Buy: {buy_price:.2f}, Sell: {sell_price:.2f}, Total score: {total_score:.2f}, Seuil: {score_threshold:.2f}")
    return signal, confidence, buy_price, sell_price
