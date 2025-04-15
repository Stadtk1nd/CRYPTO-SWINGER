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
                logger.warning(f"Échec après {max_retries} tentatives via proxy, passage à l’API de secours (CoinGecko)")
                return fetch_klines_fallback(symbol, interval)

def fetch_klines_fallback(symbol, interval):
    """Récupère les données de prix via CoinGecko comme solution de secours."""
    interval_map = {"1h": "hourly", "4h": "hourly", "1d": "daily", "1w": "daily"}
    coingecko_interval = interval_map.get(interval.lower(), "hourly")
    symbol_map = {"BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "BNBUSDT": "binancecoin", "ADAUSDT": "cardano"}
    coin_id = symbol_map.get(symbol, symbol.lower().replace("usdt", ""))
    
    coingecko_api_key = os.environ.get("COINGECKO_API_KEY")
    if not coingecko_api_key:
        logger.error("Clé API CoinGecko manquante. Veuillez configurer la variable d’environnement COINGECKO_API_KEY.")
        return fetch_klines_fallback_kraken(symbol, interval)

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=7&interval={coingecko_interval}&x_cg_demo_api_key={coingecko_api_key}"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        prices = data.get("prices", [])
        if not prices:
            logger.error(f"fetch_klines_fallback: Aucune donnée renvoyée par CoinGecko pour {coin_id}")
            return fetch_klines_fallback_kraken(symbol, interval)
        df = pd.DataFrame(prices, columns=["timestamp", "close"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"] = df["close"]
        df["volume"] = 0.0
        df["close_time"] = df["timestamp"]
        df["quote_asset_volume"] = 0.0
        df["number_of_trades"] = 0
        df["taker_buy_base"] = 0.0
        df["taker_buy_quote"] = 0.0
        df["ignore"] = 0
        logger.info(f"fetch_klines_fallback: {len(df)} lignes récupérées pour {coin_id} ({coingecko_interval}) en {(datetime.now() - start_time).total_seconds():.2f}s")
        return df
    except Exception as e:
        logger.error(f"Erreur fetch_klines_fallback ({symbol}, {interval}) : {e}")
        return fetch_klines_fallback_kraken(symbol, interval)

def fetch_klines_fallback_kraken(symbol, interval):
    """Récupère les données de prix via Kraken comme solution de secours supplémentaire."""
    symbol_map = {"BTCUSDT": "XBTUSD", "ETHUSDT": "ETHUSD", "BNBUSDT": "BNBUSD", "ADAUSDT": "ADAUSD"}
    kraken_symbol = symbol_map.get(symbol, symbol.replace("USDT", "USD"))
    interval_map = {"1h": 60, "4h": 240, "1d": 1440, "1w": 10080}
    kraken_interval = interval_map.get(interval.lower(), 60)
    
    url = f"https://api.kraken.com/0/public/OHLC?pair={kraken_symbol}&interval={kraken_interval}"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data["error"] and len(data["error"]) > 0:
            logger.error(f"Erreur API Kraken : {data['error']}")
            return fetch_klines_fallback_binance_futures(symbol, interval)
        ohlc_data = data["result"].get(kraken_symbol, [])
        if not ohlc_data:
            logger.error(f"fetch_klines_fallback_kraken: Aucune donnée renvoyée par Kraken pour {kraken_symbol}")
            return fetch_klines_fallback_binance_futures(symbol, interval)
        df = pd.DataFrame(ohlc_data, columns=[
            "timestamp", "open", "high", "low", "close", "vwap", "volume", "count"
        ])
        df["date"] = pd.to_datetime(df["timestamp"], unit="s")
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        df["close_time"] = df["timestamp"] * 1000
        df["quote_asset_volume"] = 0.0
        df["number_of_trades"] = df["count"]
        df["taker_buy_base"] = 0.0
        df["taker_buy_quote"] = 0.0
        df["ignore"] = 0
        logger.info(f"fetch_klines_fallback_kraken: {len(df)} lignes récupérées pour {kraken_symbol} ({interval}) en {(datetime.now() - start_time).total_seconds():.2f}s")
        return df
    except Exception as e:
        logger.error(f"Erreur fetch_klines_fallback_kraken ({symbol}, {interval}) : {e}")
        return fetch_klines_fallback_binance_futures(symbol, interval)

def fetch_klines_fallback_binance_futures(symbol, interval):
    """Récupère les données de prix via Binance Futures comme dernier recours."""
    interval_map = {"1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w"}
    binance_interval = interval_map.get(interval.lower(), "1h")
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={binance_interval}&limit=200"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        if response.status_code == 451:
            logger.error(f"Erreur API Binance Futures : Accès bloqué pour des raisons légales (451 Client Error)")
            return pd.DataFrame()
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "code" in data:
            logger.error(f"Erreur API Binance Futures : {data['msg']} (code: {data['code']})")
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume", "close_time",
            "quote_asset_volume", "number_of_trades", "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        logger.info(f"fetch_klines_fallback_binance_futures: {len(df)} lignes récupérées pour {symbol} ({interval}) en {(datetime.now() - start_time).total_seconds():.2f}s")
        return df
    except Exception as e:
        logger.error(f"Erreur fetch_klines_fallback_binance_futures ({symbol}, {interval}) : {e}")
        return pd.DataFrame()

def fetch_fundamental_data(coin_id):
    """Récupère les données fondamentales via CoinGecko."""
    coingecko_api_key = os.environ.get("COINGECKO_API_KEY")
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    if coingecko_api_key:
        url += f"?x_cg_demo_api_key={coingecko_api_key}"
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
        return cpi_values[-1], cpi_values[-2]
    except Exception as e:
        logger.error(f"Erreur fetch_cpi : {e}")
        return 0, 0

def fetch_gdp(fred_api_key):
    """Récupère le PIB USA via FRED avec gestion des valeurs non numériques."""
    series_id = "GDP"
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_api_key}&file_type=json&limit=2"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Réponse brute FRED pour GDP : {data}")
        
        if "observations" not in data or len(data["observations"]) < 2:
            logger.warning("fetch_gdp: Moins de 2 observations disponibles")
            return 0, 0

        gdp_values = []
        for obs in data["observations"]:
            value = obs.get("value", "0")
            try:
                # Vérifier si la valeur est convertible en float
                gdp_value = float(value)
                gdp_values.append(gdp_value)
            except ValueError as e:
                logger.warning(f"fetch_gdp: Valeur non numérique rencontrée : '{value}', remplacée par 0")
                gdp_values.append(0)

        # S’assurer d’avoir au moins 2 valeurs
        while len(gdp_values) < 2:
            gdp_values.insert(0, 0)

        logger.info(f"fetch_gdp: PIB récupéré ({gdp_values[-1]}, {gdp_values[-2]}) en {(datetime.now() - start_time).total_seconds():.2f}s")
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
        sp500_values = [float(daily_data[date]["4. close"]) for date in dates[-7:]]
        logger.info(f"fetch_sp500: Données récupérées en {(datetime.now() - start_time).total_seconds():.2f}s")
        return sp500_values[-1], sp500_values
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
