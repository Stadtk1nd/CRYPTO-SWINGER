import pandas as pd
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import logging
import time
import os

logger = logging.getLogger(__name__)

def fetch_klines(symbol, interval, max_retries=3, retry_delay=10):
    """Récupère les données de prix via un proxy pour contourner les restrictions de Binance."""
    url = f"https://crypto-swing-proxy.fly.dev/proxy/api/v3/klines?symbol={symbol}&interval={interval}&limit=200"
    for attempt in range(max_retries):
        try:
            start_time = datetime.now()
            response = requests.get(url, timeout=10)
            if response.status_code == 451:
                logger.error(f"Erreur API via proxy : Accès bloqué pour des raisons légales (451 Client Error)")
                return fetch_klines_fallback(symbol, interval)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "code" in data:
                logger.error(f"Erreur API via proxy : {data['msg']} (code: {data['code']})")
                return pd.DataFrame()
            df = pd.DataFrame(data, columns=[
                "timestamp", "open", "high", "low", "close", "volume", "close_time",
                "quote_asset_volume", "number_of_trades", "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            numeric_columns = ["open", "high", "low", "close", "volume", "quote_asset_volume", "taker_buy_base", "taker_buy_quote"]
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)
                if df[col].isnull().any():
                    logger.warning(f"Des valeurs non numériques ont été trouvées dans la colonne {col}, remplacées par NaN")
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
            logger.info(f"fetch_klines: {len(df)} lignes récupérées pour {symbol} ({interval}) en {(datetime.now() - start_time).total_seconds():.2f}s")
            return df
        except Exception as e:
            logger.error(f"Erreur fetch_klines via proxy ({symbol}, {interval}) - Tentative {attempt + 1}/{max_retries} : {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logger.warning(f"Échec après {max_retries} tentatives via proxy, passage à l’API de secours (CoinCap)")
                return fetch_klines_fallback(symbol, interval)

def fetch_klines_fallback(symbol, interval):
    """Récupère les données de prix via CoinCap v3 comme solution de secours."""
    interval_map = {"1h": "h1", "4h": "h4", "1d": "d1", "1w": "d7"}
    coincap_interval = interval_map.get(interval.lower(), "h1")
    symbol_map = {"BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "BNBUSDT": "binance-coin", "ADAUSDT": "cardano"}
    coin_id = symbol_map.get(symbol, symbol.lower().replace("usdt", ""))
    
    coincap_api_key = os.environ.get("COINCAP_API_KEY")
    if not coincap_api_key:
        logger.error("Clé API CoinCap manquante. Veuillez configurer la variable d’environnement COINCAP_API_KEY.")
        return fetch_klines_fallback_kraken(symbol, interval)

    # URL corrigée avec quoteId=tether
    url = f"https://rest.coincap.io/v3/candles?exchange=binance&interval={coincap_interval}&baseId={coin_id}&quoteId=tether&apiKey={coincap_api_key}"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        candles = data.get("data", [])
        if not candles:
            logger.error(f"fetch_klines_fallback: Aucune donnée renvoyée par CoinCap pour {coin_id}")
            return fetch_klines_fallback_kraken(symbol, interval)
        df = pd.DataFrame(candles)
        df["timestamp"] = pd.to_datetime(df["period"], unit="ms")
        df["date"] = df["timestamp"]
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        df["close_time"] = df["period"]
        df["quote_asset_volume"] = 0.0
        df["number_of_trades"] = 0
        df["taker_buy_base"] = 0.0
        df["taker_buy_quote"] = 0.0
        df["ignore"] = 0
        logger.info(f"fetch_klines_fallback: {len(df)} lignes récupérées pour {coin_id} ({coincap_interval}) en {(datetime.now() - start_time).total_seconds():.2f}s")
        return df
    except Exception as e:
        logger.error(f"Erreur fetch_klines_fallback ({symbol}, {interval}) : {e}")
        return fetch_klines_fallback_kraken(symbol, interval)

def fetch_klines_fallback_kraken(symbol, interval):
    """Récupère les données de prix via Kraken comme solution de secours supplémentaire."""
    symbol_map = {"BTCUSDT": "XBTUSD", "ETHUSDT": "ETHUSD", "BNBUSDT": "BNBUSD", "ADAUSDT": "ADAUSD"}
    kraken_symbol = symbol_map.get(symbol, symbol.replace("USDT", "USD"))
    interval_map = {"1h": 60
