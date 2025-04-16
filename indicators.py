import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Réduit le niveau de logging à INFO

def validate_data(df):
    """Valide les données de prix avant l’analyse."""
    if df.empty:
        return False, "Données manquantes ou invalides"
    if len(df) < 20:
        return False, "Pas assez de données pour l’analyse (minimum 20 périodes)"
    if df["close"].isnull().any() or (df["close"] == 0).any():
        return False, "Valeurs de clôture manquantes ou nulles"
    return True, "Données valides"

def calculate_indicators(df, interval):
    """Calcule les indicateurs techniques pour l’analyse."""
    try:
        # S’assurer que les colonnes nécessaires sont numériques
        required_columns = ["open", "high", "low", "close"]
        for col in required_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if df[col].isnull().any():
                logger.error(f"Données non numériques ou manquantes dans la colonne {col}")
                raise ValueError(f"Données non numériques ou manquantes dans la colonne {col}")

        # Calcul de l’ATR (Average True Range)
        df["TR"] = np.maximum.reduce([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs()
        ])
        df["ATR_14"] = df["TR"].rolling(window=14).mean()

        # Calcul des EMA (Exponential Moving Average)
        df["EMA_12"] = df["close"].ewm(span=12, adjust=False).mean()
        df["EMA_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["EMA_26"] = df["close"].ewm(span=26, adjust=False).mean()

        # Calcul du MACD
        df["MACD"] = df["EMA_12"] - df["EMA_26"]
        df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

        # Calcul du RSI (Relative Strength Index)
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # Calcul de l’ADX (Average Directional Index)
        plus_dm = df["high"].diff()
        minus_dm = df["low"].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        tr = df["TR"]
        plus_di = 100 * plus_dm.rolling(window=14).sum() / tr.rolling(window=14).sum()
        minus_di = 100 * (-minus_dm).rolling(window=14).sum() / tr.rolling(window=14).sum()
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        df["ADX"] = dx.rolling(window=14).mean()

        # Calcul des niveaux de support et résistance
        df["SUPPORT"] = df["low"].rolling(window=20).min()
        df["RESISTANCE"] = df["high"].rolling(window=20).max()

        # Calcul des niveaux de Fibonacci
        price_range = df["RESISTANCE"] - df["SUPPORT"]
        df["FIBO_0.382"] = df["SUPPORT"] + price_range * 0.382
        df["FIBO_0.618"] = df["SUPPORT"] + price_range * 0.618

        logger.info("Indicateurs calculés avec succès")
        return df

    except Exception as e:
        logger.error(f"Erreur calcul indicateurs : {e}")
        raise
