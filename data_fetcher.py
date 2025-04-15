import pandas as pd
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import logging

logging.basicConfig(level=logging.INFO, filename="trading.log", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fetch_klines(symbol, interval):
    """Récupère les données de prix via Binance."""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=100"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume", "close_time",
            "quote_asset_volume", "number_of_trades", "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        logger.info(f"fetch_klines: {len(df)} lignes récupérées en {(datetime.now() - start_time).total_seconds():.2f}s")
        return df
    except Exception as e:
        logger.error(f"Erreur fetch_klines ({symbol}, {interval}) : {e}")
        return pd.DataFrame()

def fetch_fundamental_data(coin_id):
    """Récupère les données fondamentales via CoinGecko."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        fundamental_data = {
            "market_cap": data.get("market_cap", {}).get("usd", 0),
            "volume_24h": data.get("total_volume", {}).get("usd", 0),
            "developer_score": data.get("developer_score", 0)
        }
        logger.info(f"fetch_fundamental_data: Données récupérées en {(datetime.now() - start_time).total_seconds():.2f}s")
        return fundamental_data
    except Exception as e:
        logger.error(f"Erreur fetch_fundamental_data ({coin_id}) : {e}")
        return {"market_cap": 0, "volume_24h": 0, "developer_score": 0}

def fetch_fear_greed():
    """Récupère l’indice Fear & Greed."""
    url = "https://api.alternative.me/fng/?limit=7"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        fng_values = [int(entry["value"]) for entry in data["data"]]
        logger.info(f"fetch_fear_greed: Données récupérées en {(datetime.now() - start_time).total_seconds():.2f}s")
        return fng_values[-1], fng_values
    except Exception as e:
        logger.error(f"Erreur fetch_fear_greed : {e}")
        return 0, []

def fetch_fed_interest_rate(fred_api_key):
    """Récupère le taux d’intérêt de la FED via FRED."""
    series_id = "FEDFUNDS"
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_api_key}&file_type=json&limit=1"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        rate = float(data["observations"][-1]["value"])
        logger.info(f"fetch_fed_interest_rate: Taux récupéré ({rate}%) en {(datetime.now() - start_time).total_seconds():.2f}s")
        return rate
    except Exception as e:
        logger.error(f"Erreur fetch_fed_interest_rate : {e}")
        return 0

def fetch_cpi(fred_api_key):
    """Récupère l’Indice des prix à la consommation (CPI) via FRED."""
    series_id = "CPIAUCSL"
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_api_key}&file_type=json&limit=2"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        cpi_values = [float(obs["value"]) for obs in data["observations"]]
        logger.info(f"fetch_cpi: CPI récupéré en {(datetime.now() - start_time).total_seconds():.2f}s")
        return cpi_values[-1], cpi_values[-2]  # Dernière valeur et avant-dernière pour la tendance
    except Exception as e:
        logger.error(f"Erreur fetch_cpi : {e}")
        return 0, 0

def fetch_gdp(fred_api_key):
    """Récupère le PIB USA via FRED."""
    series_id = "GDP"
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_api_key}&file_type=json&limit=2"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        gdp_values = [float(obs["value"]) for obs in data["observations"]]
        logger.info(f"fetch_gdp: PIB récupéré en {(datetime.now() - start_time).total_seconds():.2f}s")
        return gdp_values[-1], gdp_values[-2]
    except Exception as e:
        logger.error(f"Erreur fetch_gdp : {e}")
        return 0, 0

def fetch_unemployment_rate(fred_api_key):
    """Récupère le taux de chômage USA via FRED."""
    series_id = "UNRATE"
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_api_key}&file_type=json&limit=1"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        rate = float(data["observations"][-1]["value"])
        logger.info(f"fetch_unemployment_rate: Taux récupéré ({rate}%) en {(datetime.now() - start_time).total_seconds():.2f}s")
        return rate
    except Exception as e:
        logger.error(f"Erreur fetch_unemployment_rate : {e}")
        return 0

def fetch_sp500(alpha_vantage_api_key):
    """Récupère les données du S&P 500 via Alpha Vantage."""
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=SPY&apikey={alpha_vantage_api_key}"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        daily_data = data.get("Time Series (Daily)", {})
        if not daily_data:
            logger.warning("fetch_sp500: Aucune donnée disponible")
            return 0, []
        dates = sorted(daily_data.keys())
        sp500_values = [float(daily_data[date]["4. close"]) for date in dates[-7:]]  # 7 derniers jours
        logger.info(f"fetch_sp500: Données récupérées en {(datetime.now() - start_time).total_seconds():.2f}s")
        return sp500_values[-1], sp500_values  # Dernière valeur et liste pour variation
    except Exception as e:
        logger.error(f"Erreur fetch_sp500 : {e}")
        return 0, []

def fetch_all_data(symbol, interval, coin_id, fred_api_key, alpha_vantage_api_key):
    """Récupère toutes les données en parallèle."""
    with ThreadPoolExecutor() as executor:
        future_klines = executor.submit(fetch_klines, symbol, interval)
        future_fundamental = executor.submit(fetch_fundamental_data, coin_id)
        future_fear_greed = executor.submit(fetch_fear_greed)
        future_fed_rate = executor.submit(fetch_fed_interest_rate, fred_api_key)
        future_cpi = executor.submit(fetch_cpi, fred_api_key)
        future_gdp = executor.submit(fetch_gdp, fred_api_key)
        future_unemployment = executor.submit(fetch_unemployment_rate, fred_api_key)
        future_sp500 = executor.submit(fetch_sp500, alpha_vantage_api_key)

        price_data = future_klines.result()
        fundamental_data = future_fundamental.result()
        fear_greed_index, fng_trend = future_fear_greed.result()
        fed_rate = future_fed_rate.result()
        cpi_current, cpi_previous = future_cpi.result()
        gdp_current, gdp_previous = future_gdp.result()
        unemployment_rate = future_unemployment.result()
        sp500_value, sp500_values = future_sp500.result()

        macro_data = {
            "fear_greed_index": fear_greed_index,
            "fng_trend": fng_trend,
            "fed_interest_rate": fed_rate,
            "cpi_current": cpi_current,
            "cpi_previous": cpi_previous,
            "gdp_current": gdp_current,
            "gdp_previous": gdp_previous,
            "unemployment_rate": unemployment_rate,
            "sp500_value": sp500_value,
            "sp500_values": sp500_values
        }

    return price_data, fundamental_data, macro_data
