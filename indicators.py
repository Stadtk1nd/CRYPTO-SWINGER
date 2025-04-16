VERSION = "1.0.0"

import pandas as pd
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def calculate_indicators(df):
    """Calcule les indicateurs techniques de base."""
    try:
        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = df["close"].ewm(span=12, adjust=False).mean()
        exp2 = df["close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = exp1 - exp2
        df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

        # EMA
        df["EMA_12"] = df["close"].ewm(span=12, adjust=False).mean()
        df["EMA_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["EMA_26"] = df["close"].ewm(span=26, adjust=False).mean()

        # ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["ATR_14"] = tr.rolling(window=14).mean()

        # ADX (simplifié)
        df["ADX"] = tr.rolling(window=14).mean()  # Approximation basique

        # Support/Résistance (simplifié)
        df["SUPPORT"] = df["low"].rolling(window=20).min()
        df["RESISTANCE"] = df["high"].rolling(window=20).max()

        # Fibonacci (simplifié)
        range_high = df["high"].rolling(window=20).max()
        range_low = df["low"].rolling(window=20).min()
        range_diff = range_high - range_low
        df["FIBO_0.382"] = range_low + 0.382 * range_diff
        df["FIBO_0.618"] = range_low + 0.618 * range_diff

        logger.info("Indicateurs calculés avec succès")
        return df
    except Exception as e:
        logger.error(f"Erreur lors du calcul des indicateurs : {e}")
        return df
