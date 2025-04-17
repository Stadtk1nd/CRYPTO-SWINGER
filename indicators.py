VERSION = "1.0.1"

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
    # Ajout : Vérifier la volatilité soudaine (variation de prix > 10% sur 5 périodes)
    recent_volatility = df["close"].pct_change(periods=5).abs().iloc[-1] if len(df) >= 5 else 0
    if recent_volatility > 0.10:
        return False, "Volatilité soudaine détectée (>10% sur 5 périodes)"
    # Ajout : Vérifier les volumes anormaux (volume > 3x la moyenne sur 20 périodes)
    avg_volume = df["volume"].rolling(window=20).mean().iloc[-1] if len(df) >= 20 else 0
    if avg_volume != 0 and df["volume"].iloc[-1] > 3 * avg_volume:
        return False, "Volume anormal détecté (>3x la moyenne sur 20 périodes)"
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

        # Calcul du RSI (Relative Strength Index) avec ajustement basé sur la volatilité
        volatility = df["close"].pct_change().rolling(window=20).std().iloc[-1] * 100 if len(df) >= 20 else 1.0
        rsi_window = 14 if volatility < 2 else 10  # Raccourcir la fenêtre si forte volatilité
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_window).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # Calcul de l’ADX (Average Directional Index) avec fenêtre ajustée
        adx_window = 14 if interval in ["1D", "1W"] else 10  # Plus court pour les petits intervalles
        plus_dm = df["high"].diff()
        minus_dm = df["low"].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        tr = df["TR"]
        plus_di = 100 * plus_dm.rolling(window=adx_window).sum() / tr.rolling(window=adx_window).sum()
        minus_di = 100 * (-minus_dm).rolling(window=adx_window).sum() / tr.rolling(window=adx_window).sum()
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        df["ADX"] = dx.rolling(window=adx_window).mean()

        # Calcul des niveaux de support et résistance dynamiques
        window = 10 if interval in ["1H", "4H"] else 20  # Fenêtre plus courte pour les petits intervalles
        df["SUPPORT"] = df["low"].rolling(window=window).min().ewm(span=window, adjust=False).mean()  # Ajout d'une EMA pour pondérer les données récentes
        df["RESISTANCE"] = df["high"].rolling(window=window).max().ewm(span=window, adjust=False).mean()

        # Calcul des niveaux de Fibonacci
        price_range = df["RESISTANCE"] - df["SUPPORT"]
        df["FIBO_0.382"] = df["SUPPORT"] + price_range * 0.382
        df["FIBO_0.618"] = df["SUPPORT"] + price_range * 0.618

        logger.info("Indicateurs calculés avec succès")
        return df

    except Exception as e:
        logger.error(f"Erreur calcul indicateurs : {e}")
        raise
