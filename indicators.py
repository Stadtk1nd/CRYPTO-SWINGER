import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator, SMAIndicator, ADXIndicator, IchimokuIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import OnBalanceVolumeIndicator
from ta.trend import CCIIndicator
import logging

logging.basicConfig(level=logging.INFO, filename="trading.log", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def calculate_indicators(df, interval_input):
    """Calcule tous les indicateurs techniques en une seule passe."""
    try:
        window_map = {"1H": 10, "4H": 15, "1D": 20, "1W": 50}
        ema_window = window_map[interval_input]
        sma_window = window_map[interval_input]
        atr_window = 14 if interval_input in ["1H", "4H"] else 7
        adx_window = 14 if interval_input in ["1H", "4H"] else 7
        rsi_base = {"1H": 9, "4H": 10, "1D": 14, "1W": 21}.get(interval_input, 14)

        # Calcul de la volatilité pour ajuster dynamiquement RSI
        volatility = (df["high"] - df["low"]).mean() / df["close"].mean() * 100
        rsi_window = max(5, min(50, rsi_base + (-3 if volatility > 5 else 3 if volatility < 2 else 0)))

        indicators = {
            "ATR_14": AverageTrueRange(df["high"], df["low"], df["close"], window=atr_window).average_true_range(),
            "RSI": RSIIndicator(df["close"], window=rsi_window).rsi(),
            "MACD": MACD(df["close"]).macd(),
            "MACD_SIGNAL": MACD(df["close"]).macd_signal(),
            "EMA_20": EMAIndicator(df["close"], window=ema_window).ema_indicator(),
            "SMA_20": SMAIndicator(df["close"], window=sma_window).sma_indicator(),
            "EMA_50": EMAIndicator(df["close"], window=50).ema_indicator(),
            "EMA_12": EMAIndicator(df["close"], window=12).ema_indicator(),
            "EMA_26": EMAIndicator(df["close"], window=26).ema_indicator(),
            "ADX": ADXIndicator(df["high"], df["low"], df["close"], window=adx_window).adx(),
            "STOCH_K": StochasticOscillator(df["high"], df["low"], df["close"]).stoch(),
            "TENKAN": IchimokuIndicator(df["high"], df["low"]).ichimoku_conversion_line(),
            "KIJUN": IchimokuIndicator(df["high"], df["low"]).ichimoku_base_line(),
            "FIBO_0.382": df["close"].rolling(window=100).max() - 0.382 * (df["close"].rolling(window=100).max() - df["close"].rolling(window=100).min()),
            "FIBO_0.618": df["close"].rolling(window=100).max() - 0.618 * (df["close"].rolling(window=100).max() - df["close"].rolling(window=100).min()),
            "SUPPORT": df["low"].rolling(window=20).min(),
            "RESISTANCE": df["high"].rolling(window=20).max(),
            "BB_High": BollingerBands(df["close"], window=20, window_dev=2).bollinger_hband(),
            "BB_Low": BollingerBands(df["close"], window=20, window_dev=2).bollinger_lband(),
            "OBV": OnBalanceVolumeIndicator(df["close"], df["volume"]).on_balance_volume(),
            "CCI": CCIIndicator(df["high"], df["low"], df["close"], window=20).cci(),
            "VOLUME_AVG": df["volume"].rolling(window=20).mean(),
            "VOLUME_SPIKE": df["volume"] > 2 * df["volume"].rolling(window=20).mean()
        }

        for name, series in indicators.items():
            df[name] = series

        # Calculs supplémentaires
        volatility_factor = volatility / 5
        volume_spike_factor = 1.5 if df["VOLUME_SPIKE"].iloc[-5:].any() else 1.0
        liquidation_margin = 0.1 * (1 + volatility_factor) * volume_spike_factor
        df["LIQUIDATION_LONG"] = df[["SUPPORT", "FIBO_0.382"]].min(axis=1) - liquidation_margin * df["ATR_14"]
        df["LIQUIDATION_SHORT"] = df[["RESISTANCE", "FIBO_0.618"]].max(axis=1) + liquidation_margin * df["ATR_14"]

        # Suppression unique des NaN
        critical_columns = ["close", "high", "low", "ATR_14", "RSI", "MACD"]
        df.dropna(subset=critical_columns, inplace=True)

        if df.empty:
            raise ValueError("DataFrame vide après calcul des indicateurs")

        logger.info(f"Indicateurs calculés pour intervalle {interval_input}")
        return df
    except Exception as e:
        logger.error(f"Erreur calcul indicateurs : {e}")
        raise

def validate_data(df):
    """Valide les données pour détecter les anomalies."""
    if df["close"].pct_change().abs().max() > 0.5:
        logger.warning("Variation de prix anormale (> 50%)")
        return False, "Variation de prix anormale détectée (> 50%)"
    if df["volume"].mean() < 1000:
        logger.warning("Volume moyen faible")
        return False, "Volume moyen faible détecté (< 1000)"
    return True, ""