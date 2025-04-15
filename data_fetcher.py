import requests
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

# Configuration de la journalisation
logging.basicConfig(level=logging.INFO, filename="trading.log", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fetch_klines(symbol, interval, limit=200, timeout=10):
    """Récupère les données de prix via Binance proxy."""
    try:
        start_time = datetime.now()
        url = "https://crypto-swing-proxy.fly.dev/proxy/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        klines = response.json()
        if not klines or not isinstance(klines, list):
            raise ValueError("Réponse API invalide : aucune donnée ou format incorrect")
        price_data = [
            {
                "date": datetime.fromtimestamp(k[0] / 1000).strftime('%Y-%m-%d %H:%M'),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            }
            for k in klines
        ]
        df = pd.DataFrame(price_data)
        logger.info(f"fetch_klines réussi pour {symbol} en {(datetime.now() - start_time).total_seconds():.2f}s")
        return df
    except Exception as e:
        logger.error(f"Erreur fetch_klines pour {symbol} : {e}")
        raise

def fetch_fundamental_data(coin_id, timeout=5):
    """Récupère les données fondamentales via CoinGecko avec fallback."""
    try:
        start_time = datetime.now()
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if "market_cap" not in data or "market_data" not in data:
            raise ValueError("Structure JSON inattendue")
        result = {
            "market_cap": data["market_cap"].get("usd", 0),
            "volume_24h": data["market_data"]["total_volume"].get("usd", 0),
            "developer_score": data.get("developer_score", 0),
            "community_score": data.get("community_score", 0)
        }
        logger.info(f"fetch_fundamental_data réussi pour {coin_id} en {(datetime.now() - start_time).total_seconds():.2f}s")
        return result
    except Exception as e:
        logger.warning(f"Erreur CoinGecko pour {coin_id} : {e}, tentative avec fallback")
        # Fallback : données minimales
        return {
            "market_cap": 0,
            "volume_24h": 0,
            "developer_score": 0,
            "community_score": 0
        }

def fetch_macro_data(fred_api_key, timeout=5):
    """Récupère les données macroéconomiques avec parallélisation."""
    def fetch_fear_greed():
        try:
            url = "https://api.alternative.me/fng/?limit=7"
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if not data.get("data"):
                raise ValueError("Données Fear & Greed absentes")
            return {
                "fear_greed_index": int(data["data"][0]["value"]),
                "fng_trend": [int(day["value"]) for day in data["data"]]
            }
        except Exception as e:
            logger.error(f"Erreur Fear & Greed : {e}")
            return None

    def fetch_fed_rate():
        try:
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&api_key={fred_api_key}&file_type=json&limit=1&sort_order=desc"
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            return {
                "fed_rate": float(data["observations"][0]["value"]),
                "fed_rate_date": data["observations"][0]["date"]
            }
        except Exception as e:
            logger.error(f"Erreur FED rate : {e}")
            return None

    start_time = datetime.now()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda f: f(), [fetch_fear_greed, fetch_fed_rate]))
    
    macro_data = {}
    if results[0]:
        macro_data.update(results[0])
    if results[1]:
        macro_data.update(results[1])
    logger.info(f"fetch_macro_data terminé en {(datetime.now() - start_time).total_seconds():.2f}s")
    return macro_data

def fetch_all_data(symbol, interval, coin_id, fred_api_key):
    """Récupère toutes les données en parallèle."""
    start_time = datetime.now()
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(fetch_klines, symbol, interval),
            executor.submit(fetch_fundamental_data, coin_id),
            executor.submit(fetch_macro_data, fred_api_key)
        ]
        price_data, fundamental_data, macro_data = [f.result() for f in futures]
    logger.info(f"fetch_all_data terminé en {(datetime.now() - start_time).total_seconds():.2f}s")
    return price_data, fundamental_data, macro_data