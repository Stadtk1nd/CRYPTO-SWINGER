VERSION = "1.0.4"  # Incrémenté de 1.0.3 pour corriger assignations pandas dans detect_rsi_divergence

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def validate_data(df):
    """Valide les données de prix avant l’analyse."""
    if df.empty:
        return False, "Données manquantes ou invalides"
    if len(df) < 20:
        return False, "Pas assez de données (minimum 20 périodes)"
    if df["close"].isnull().any() or (df["close"] == 0).any():
        return False, "Valeurs de clôture manquantes ou nulles"
    if df["volume"].isnull().any() or (df["volume"] == 0).all():
        return False, "Valeurs de volume manquantes ou toutes nulles"
    
    # Vérifier la volatilité soudaine (>10% sur 5 périodes)
    if len(df) >= 5:
        recent_volatility = df["close"].pct_change(periods=5).abs().iloc[-1]
        if recent_volatility > 0.10:
            return False, "Volatilité soudaine (>10% sur 5 périodes)"
    
    # Vérifier les volumes anormaux (>3x la moyenne sur 20 périodes)
    avg_volume = df["volume"].rolling(window=20).mean().iloc[-1]
    if avg_volume != 0 and df["volume"].iloc[-1] > 3 * avg_volume:
        return False, "Volume anormal (>3x la moyenne sur 20 périodes)"
    
    return True, "Données valides"

def detect_rsi_divergence(df, window=5):
    """Détecte les divergences RSI/prix (haussière ou baissière)."""
    df["RSI_DIVERGENCE"] = 0
    for i in range(window, len(df)):
        price_change = df["close"].iloc[i] - df["close"].iloc[i-window]
        rsi_change = df["RSI"].iloc[i] - df["RSI"].iloc[i-window]
        if price_change < 0 and rsi_change > 0:  # Divergence haussière
            df.loc[df.index[i], "RSI_DIVERGENCE"] = 1
        elif price_change > 0 and rsi_change < 0:  # Divergence baissière
            df.loc[df.index[i], "RSI_DIVERGENCE"] = -1
    return df

def calculate_indicators(df, interval):
    """Calcule les indicateurs techniques pour l’analyse."""
    try:
        # Normaliser l’intervalle
        interval = interval.upper()
        
        # Vérifier les colonnes nécessaires
        required_columns = ["open", "high", "low", "close", "volume"]
        for col in required_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if df[col].isnull().any():
                logger.error(f"Données non numériques ou manquantes dans {col}")
                raise ValueError(f"Données non numériques ou manquantes dans {col}")

        # Calcul de l’ATR
        df["TR"] = np.maximum.reduce([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs()
        ])
        df["ATR_14"] = df["TR"].rolling(window=14).mean()

        # Calcul des EMA
        df["EMA_12"] = df["close"].ewm(span=12, adjust=False).mean()
        df["EMA_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["EMA_26"] = df["close"].ewm(span=26, adjust=False).mean()

        # Calcul du MACD
        df["MACD"] = df["EMA_12"] - df["EMA_26"]
        df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

        # Calcul du RSI avec gestion de division par zéro
        volatility = df["close"].pct_change().rolling(window=20).std().iloc[-1] * 100 if len(df) >= 20 else 1.0
        rsi_window = 14 if volatility < 2 else 10
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_window).mean()
        rs = gain / loss.where(loss != 0, np.inf)  # Éviter division par zéro
        df["RSI"] = 100 - (100 / (1 + rs)).where(rs != np.inf, 100)  # RSI = 100 si loss = 0

        # Calcul de l’ADX
        adx_window = 14 if interval in ["1D", "1W"] else 10
        plus_dm = df["high"].diff()
        minus_dm = df["low"].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        tr = df["TR"]
        plus_di = 100 * plus_dm.rolling(window=adx_window).sum() / tr.rolling(window=adx_window).sum()
        minus_di = 100 * (-minus_dm).rolling(window=adx_window).sum() / tr.rolling(window=adx_window).sum()
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        df["ADX"] = dx.rolling(window=adx_window).mean()

        # Calcul des niveaux de support/résistance
        window = 10 if interval in ["1H", "4H"] else 20
        df["SUPPORT"] = df["low"].rolling(window=window).min().ewm(span=window, adjust=False).mean()
        df["RESISTANCE"] = df["high"].rolling(window=window).max().ewm(span=window, adjust=False).mean()

        # Calcul des niveaux de Fibonacci
        price_range = df["RESISTANCE"] - df["SUPPORT"]
        df["FIBO_0.382"] = df["SUPPORT"] + price_range * 0.382
        df["FIBO_0.618"] = df["SUPPORT"] + price_range * 0.618

        # Calcul des bandes de Bollinger
        bb_window = 20
        df["BB_MID"] = df["close"].rolling(window=bb_window).mean()
        df["BB_STD"] = df["close"].rolling(window=bb_window).std()
        df["BB_UPPER"] = df["BB_MID"] + 2 * df["BB_STD"]
        df["BB_LOWER"] = df["BB_MID"] - 2 * df["BB_STD"]

        # Détection des divergences RSI
        df = detect_rsi_divergence(df, window=5)

        return df

    except Exception as e:
        logger.error(f"Erreur calcul indicateurs : {e}")
        raise
