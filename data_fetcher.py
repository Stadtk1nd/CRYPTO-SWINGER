VERSION = "1.0.13"  # Incrémenté de 1.0.12 à 1.0.13 pour gérer la clé API CoinCap

import pandas as pd
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import logging
import time
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Récupérer dynamiquement les ID CoinCap au démarrage
def fetch_coincap_ids():
    """Récupère les 100 plus grandes cryptos et leurs ID via l'API CoinCap v3."""
    coincap_api_key = os.environ.get("COINCAP_API_KEY")
    if not coincap_api_key:
        logger.error("Clé API CoinCap manquante. Veuillez configurer la variable d’environnement COINCAP_API_KEY.")
        return {
            "btc": "bitcoin",
            "eth": "ethereum",
            "bnb": "binance-coin",
            "ada": "cardano",
            "tao": "bittensor",
        }  # Fallback avec quelques cryptos principales

    url = f"https://rest.coincap.io/v3/assets?limit=100&apiKey={coincap_api_key}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        coincap_id_map = {}
        for asset in data["data"]:
            symbol = asset["symbol"].lower()  # Normaliser en minuscules
            coincap_id = asset["id"]
            coincap_id_map[symbol] = coincap_id
        logger.info(f"Récupéré {len(coincap_id_map)} cryptos depuis CoinCap")
        return coincap_id_map
    except requests.exceptions.HTTPError as e:
        logger.error(f"Erreur lors de la récupération des ID CoinCap : {e} - Code HTTP : {e.response.status_code}")
        return {
            "btc": "bitcoin",
            "eth": "ethereum",
            "bnb": "binance-coin",
            "ada": "cardano",
            "tao": "bittensor",
        }  # Fallback en cas d'erreur
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des ID CoinCap : {e}")
        return {
            "btc": "bitcoin",
            "eth": "ethereum",
            "bnb": "binance-coin",
            "ada": "cardano",
            "tao": "bittensor",
        }

# Charger les ID au démarrage du module
COINCAP_ID_MAP = fetch_coincap_ids()

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

    url = f"https://rest.coincap.io/v3/candles?exchange=binance_timestamps&interval={coincap_interval}&baseId={coin_id}&apiKey={coincap_api_key}"
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
    """Récupère les données fondamentales via CoinCap v3 et DeFiLlama pour TVL."""
    coincap_api_key = os.environ.get("COINCAP_API_KEY")
    if not coincap_api_key:
        logger.error("Clé API CoinCap manquante. Veuillez configurer la variable d’environnement COINCAP_API_KEY.")
        return {"market_cap": 0, "volume_24h": 0, "tvl": 0}

    coincap_id = COINCAP_ID_MAP.get(coin_id, coin_id)

    url = f"https://rest.coincap.io/v3/assets/{coincap_id}?apiKey={coincap_api_key}"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Réponse brute CoinCap v3 pour {coincap_id} : {data}")

        asset_data = data.get("data", {})
        fundamental_data = {
            "market_cap": float(asset_data.get("marketCapUsd", 0)),
            "volume_24h": float(asset_data.get("volumeUsd24Hr", 0)),
            "tvl": 0
        }

        if all(value == 0 for value in fundamental_data.values()):
            logger.warning(f"fetch_fundamental_data: Toutes les données fondamentales pour {coincap_id} sont à 0. Vérifiez la réponse de l’API.")
    except requests.exceptions.HTTPError as e:
        logger.error(f"Erreur HTTP fetch_fundamental_data ({coincap_id}) : {e} - Code HTTP : {e.response.status_code}")
        if e.response.status_code == 429:
            logger.warning("Limite de taux atteinte pour CoinCap. Essayez de réduire la fréquence des requêtes.")
        return {"market_cap": 0, "volume_24h": 0, "tvl": 0}
    except Exception as e:
        logger.error(f"Erreur fetch_fundamental_data ({coincap_id}) : {e}")
        return {"market_cap": 0, "volume_24h": 0, "tvl": 0}

    # Vérification du volume par rapport à la capitalisation boursière
    market_cap_threshold = 10_000_000_000
    volume_ratio_threshold = 0.01
    if fundamental_data["market_cap"] > market_cap_threshold:
        logger.info(f"Market cap élevé pour {coincap_id} : {fundamental_data['market_cap']}")
    if fundamental_data["market_cap"] != 0 and fundamental_data["volume_24h"] / fundamental_data["market_cap"] > volume_ratio_threshold:
        logger.info(f"Volume élevé pour {coincap_id} : {fundamental_data['volume_24h'] / fundamental_data['market_cap'] * 100:.2f}% de la market cap")

    defillama_id_map = {
        "bitcoin": "bitcoin",
        "ethereum": "ethereum",
        "binancecoin": "binance-smart-chain",
        "cardano": "cardano",
        "tao": "bittensor",
        "solana": "solana",
        "xrp": "xrp",
        # À compléter pour correspondre à COINCAP_ID_MAP
    }
    defillama_id = defillama_id_map.get(coin_id, coin_id)
    defillama_url = f"https://api.llama.fi/v2/chains"
    try:
        response = requests.get(defillama_url, timeout=10)
        response.raise_for_status()
        chains = response.json()
        for chain in chains:
            if chain.get("gecko_id") == defillama_id:
                fundamental_data["tvl"] = float(chain.get("tvl", 0))
                break
        logger.info(f"fetch_fundamental_data: TVL récupéré pour {defillama_id} : {fundamental_data['tvl']}")
    except Exception as e:
        logger.error(f"Erreur fetch TVL via DeFiLlama ({defillama_id}) : {e}")
        fundamental_data["tvl"] = 0

    logger.info(f"fetch_fundamental_data: Données récupérées pour {coincap_id} en {(datetime.now() - start_time).total_seconds():.2f}s")
    return fundamental_data

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

def fetch_vix(fred_api_key):
    """Récupère l’indice VIX (volatilité implicite) via FRED."""
    series_id = "VIXCLS"
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_api_key}&file_type=json&limit=7"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        vix_values = [float(obs["value"]) for obs in data["observations"]]
        logger.info(f"fetch_vix: VIX récupéré en {(datetime.now() - start_time).total_seconds():.2f}s")
        return vix_values[-1], vix_values
    except Exception as e:
        logger.error(f"Erreur fetch_vix : {e}")
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
    """Récupère le PIB USA via FRED avec gestion des séparateurs décimaux."""
    series_id = "GDP"
    # Limiter aux données à partir de 2000 pour éviter les données anciennes non fiables
    start_date = "2000-01-01"
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_api_key}&file_type=json&limit=20&start_date={start_date}"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Réponse brute FRED pour GDP : {data}")
        
        if "observations" not in data or not data["observations"]:
            logger.warning("fetch_gdp: Aucune observation disponible")
            return 0, 0

        gdp_values = []
        invalid_count = 0
        for obs in data["observations"]:
            value = obs.get("value", "0")
            date = obs.get("date", "inconnue")
            # Ignorer les valeurs vides ou non exploitables
            if not value or value.strip() in [".", ""]:
                invalid_count += 1
                continue
            # Nettoyer la valeur : gérer les séparateurs de milliers et points
            try:
                cleaned_value = value.replace(",", "").strip()
                if cleaned_value.count(".") > 1:
                    logger.warning(f"fetch_gdp: Valeur avec plusieurs points pour la date {date} : '{value}', ignorée")
                    invalid_count += 1
                    continue
                gdp_value = float(cleaned_value)
                if gdp_value <= 0:
                    logger.warning(f"fetch_gdp: Valeur non positive rencontrée pour la date {date} : {gdp_value}, ignorée")
                    invalid_count += 1
                    continue
                gdp_values.append(gdp_value)
            except ValueError as e:
                logger.warning(f"fetch_gdp: Valeur non numérique rencontrée pour la date {date} : '{value}', ignorée")
                invalid_count += 1
                continue

        if invalid_count > 0:
            logger.warning(f"fetch_gdp: {invalid_count} valeurs invalides ignorées")

        if len(gdp_values) < 2:
            logger.warning(f"fetch_gdp: Moins de 2 valeurs valides trouvées ({len(gdp_values)})")
            return 0, 0

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
    """Récupère les données de SPY (ETF suivant le S&P 500) via Alpha Vantage, en tenant compte des jours ouvrés."""
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=SPY&apikey={alpha_vantage_api_key}&outputsize=compact"
    try:
        start_time = datetime.now()
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()
        daily_data = data.get("Time Series (Daily)", {})
        if not daily_data:
            logger.warning("fetch_sp500: Aucune donnée disponible")
            return 0, []

        # Convertir les données en DataFrame pour faciliter la manipulation
        dates = sorted(daily_data.keys())
        df = pd.DataFrame([
            {"date": date, "close": float(daily_data[date]["4. close"])}
            for date in dates
        ])
        df["date"] = pd.to_datetime(df["date"])
        
        # Filtrer les jours ouvrés (lundi à vendredi, exclure week-ends)
        df["day_of_week"] = df["date"].dt.dayofweek  # 0 = lundi, 6 = dimanche
        df = df[df["day_of_week"] < 5]  # Exclure samedi (5) et dimanche (6)

        # Prendre les 7 derniers jours ouvrés
        if len(df) < 7:
            logger.warning(f"fetch_sp500: Moins de 7 jours ouvrés disponibles ({len(df)})")
            return 0, []
        
        sp500_values = df["close"].tail(7).tolist()  # 7 derniers jours ouvrés
        sp500_value = sp500_values[-1]  # Dernière valeur (plus récente)

        logger.info(f"fetch_sp500: {len(sp500_values)} jours ouvrés de données SPY récupérés en {(datetime.now() - start_time).total_seconds():.2f}s")
        return sp500_value, sp500_values
    except requests.exceptions.Timeout:
        logger.error("fetch_sp500: Délai d’attente dépassé lors de la connexion à Alpha Vantage")
        return 0, []
    except Exception as e:
        logger.error(f"Erreur fetch_sp500 : {e}")
        return 0, []

def fetch_all_data(symbol, interval, coin_id, fred_api_key, alpha_vantage_api_key):
    """Récupère toutes les données en parallèle, incluant plusieurs intervalles pour MTFA."""
    intervals = ["1h", "4h", "1d", "1w"]  # Récupérer plusieurs intervalles pour MTFA
    price_data_dict = {}

    with ThreadPoolExecutor() as executor:
        # Récupérer les données de prix pour tous les intervalles (point 1 et 5)
        futures_klines = {intv: executor.submit(fetch_klines, symbol, intv) for intv in intervals}
        future_fundamental = executor.submit(fetch_fundamental_data, coin_id)
        future_fear_greed = executor.submit(fetch_fear_greed)
        future_vix = executor.submit(fetch_vix, fred_api_key)
        future_fed_rate = executor.submit(fetch_fed_interest_rate, fred_api_key)
        future_cpi = executor.submit(fetch_cpi, fred_api_key)
        future_gdp = executor.submit(fetch_gdp, fred_api_key)
        future_unemployment = executor.submit(fetch_unemployment_rate, fred_api_key)
        future_sp500 = executor.submit(fetch_sp500, alpha_vantage_api_key)

        # Récupérer les données de prix pour l’intervalle demandé et les autres
        for intv in intervals:
            price_data_dict[intv] = futures_klines[intv].result()
        fundamental_data = future_fundamental.result()
        fear_greed_index, fng_trend = future_fear_greed.result()
        vix_value, vix_trend = future_vix.result()
        fed_rate = future_fed_rate.result()
        cpi_current, cpi_previous = future_cpi.result()
        gdp_current, gdp_previous = future_gdp.result()
        unemployment_rate = future_unemployment.result()
        sp500_value, sp500_values = future_sp500.result()

        macro_data = {
            "fear_greed_index": fear_greed_index,
            "fng_trend": fng_trend,
            "vix_value": vix_value,
            "vix_trend": vix_trend,
            "fed_interest_rate": fed_rate,
            "cpi_current": cpi_current,
            "cpi_previous": cpi_previous,
            "gdp_current": gdp_current,
            "gdp_previous": gdp_previous,
            "unemployment_rate": unemployment_rate,
            "sp500_value": sp500_value,
            "sp500_values": sp500_values
        }

    # Retourner les données de prix pour l’intervalle demandé et les données MTFA
    price_data = price_data_dict.get(interval.lower(), pd.DataFrame())
    return price_data, fundamental_data, macro_data, price_data_dict
