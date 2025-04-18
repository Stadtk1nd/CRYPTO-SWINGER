# main.py corrigé

VERSION = "8.0.3"  # Correction des doublons de formulaire

import streamlit as st
import pandas as pd
import plotly.express as px
import os
import logging
import openai
from datetime import datetime, timezone
from data_fetcher import fetch_all_data, VERSION as DATA_FETCHER_VERSION, COINCAP_ID_MAP
from indicators import calculate_indicators, validate_data, VERSION as INDICATORS_VERSION
from analyzer import analyze_technical, analyze_fundamental, analyze_macro, generate_recommendation, VERSION as ANALYZER_VERSION

# Configurer le logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Capturer les logs pour Streamlit
from io import StringIO
log_stream = StringIO()
stream_handler = logging.StreamHandler(log_stream)
stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger('').addHandler(stream_handler)

# Clés API
FRED_API_KEY = os.environ.get("FRED_API_KEY")
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not all([FRED_API_KEY, ALPHA_VANTAGE_API_KEY, OPENAI_API_KEY]):
    st.error("❌ Clés API manquantes. Configurez FRED_API_KEY, ALPHA_VANTAGE_API_KEY et OPENAI_API_KEY.")
    st.stop()

openai.api_key = OPENAI_API_KEY

# Interface Streamlit
st.title("Assistant de Trading Crypto")
st.write("Entrez les paramètres pour générer un plan de trading.")

# Formulaire
with st.form("trading_form"):
    symbol_input = st.text_input("🔍 Entrez la crypto (ex: BTC ou BTCUSDT)", "BTC").upper()
    submit_button = st.form_submit_button("Lancer l’analyse")

# Fonction d'appel à GPT

def get_gpt_analysis(data_dict):
    system_prompt = """
Tu es un analyste de marché crypto professionnel. Ton rôle est de fournir une analyse synthétique et structurée du marché à partir des données suivantes, sans citer directement les chiffres. Organise ta réponse selon ces sections :
- Contexte macroéconomique
- Sentiment et volatilité
- Indicateurs techniques
- Fondamentaux crypto
- Préconisation (court, moyen et long terme)

Adopte un ton professionnel, concis et argumenté. Tu peux signaler quand certains indicateurs sont contradictoires. Ne donne aucune recommandation d’achat ou de vente directe.
"""

    user_prompt = f"""
Voici les données du marché pour l'actif {data_dict['symbol']} :

RSI : {data_dict['rsi']}
MACD : {data_dict['macd']}
EMA12 > EMA26 : {data_dict['ema12_above_ema26']}
ADX : {data_dict['adx']}
Prix < EMA20 : {data_dict['price_below_ema20']}
Market Cap : {data_dict['market_cap']}
TVL : {data_dict['tvl']}
Fear & Greed : {data_dict['fear_greed_index']}
VIX : {data_dict['vix']}
Taux FED : {data_dict['fed_rate']}
CPI : {data_dict['cpi']}
PIB : {data_dict['gdp']}
Chômage : {data_dict['unemployment']}
SPY : {data_dict['spy_price']}
SPY variation 7j : {data_dict['spy_7d_change']}%
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

if submit_button:
    if not symbol_input or not symbol_input.isalnum():
        st.error("❌ Symbole invalide. Entrez un symbole comme BTC ou BTCUSDT.")
        st.stop()

    with st.spinner("Analyse en cours..."):
        try:
            log_stream.seek(0)
            log_stream.truncate(0)

            symbol = symbol_input if symbol_input.endswith("USDT") else symbol_input + "USDT"
            symbol_key = symbol_input.upper().replace("USDT", "")
            coin_id = COINCAP_ID_MAP.get(symbol_key.lower(), symbol_key.lower())
            interval = "1h"

            if symbol_key.lower() not in COINCAP_ID_MAP:
                st.warning(f"⚠️ Symbole {symbol_key} non trouvé dans CoinCap. Tentative avec ID générique.")

            if "last_symbol" not in st.session_state or st.session_state.last_symbol != symbol:
                st.cache_data.clear()
                st.session_state.last_symbol = symbol

            @st.cache_data(show_spinner=False)
            def cached_fetch_all_data(_symbol, _interval, _coin_id, _fred_key, _alpha_key, _cache_key=None):
                return fetch_all_data(_symbol, _interval, _coin_id, _fred_key, _alpha_key, _cache_key=_cache_key)

            price_data, fundamental_data, macro_data, price_data_dict = cached_fetch_all_data(
                symbol, interval, coin_id, FRED_API_KEY, ALPHA_VANTAGE_API_KEY, _cache_key=symbol
            )

            is_valid, validation_message = validate_data(price_data)
            if not is_valid:
                st.error(f"❌ Erreur : {validation_message}")
                st.markdown("### Logs")
                st.text("\n".join(log_stream.getvalue().splitlines()[-10:]))
                st.stop()

            price_data = calculate_indicators(price_data, interval)
            for key in price_data_dict:
                price_data_dict[key] = calculate_indicators(price_data_dict[key], key.upper())

            technical_score, technical_details = analyze_technical(price_data, interval, price_data_dict)
            fundamental_score, fundamental_details = analyze_fundamental(fundamental_data)
            macro_score, macro_details = analyze_macro(macro_data, interval)

            data_input = {
                "symbol": symbol_key,
                "rsi": price_data["RSI"].iloc[-1],
                "macd": "bearish" if price_data["MACD_Hist"].iloc[-1] < 0 else "bullish",
                "ema12_above_ema26": bool(price_data["EMA12"].iloc[-1] > price_data["EMA26"].iloc[-1]),
                "adx": price_data["ADX"].iloc[-1],
                "price_below_ema20": bool(price_data["close"].iloc[-1] < price_data["EMA20"].iloc[-1]),
                "market_cap": fundamental_data.get("market_cap", 0),
                "tvl": fundamental_data.get("tvl", 0),
                "fear_greed_index": macro_data.get("fear_greed", 50),
                "vix": macro_data.get("vix", 20),
                "fed_rate": macro_data.get("fed_rate", 2.0),
                "cpi": macro_data.get("cpi", 2.0),
                "gdp": macro_data.get("gdp", 3.0),
                "unemployment": macro_data.get("unemployment", 4.0),
                "spy_price": macro_data.get("spy_price", 400),
                "spy_7d_change": macro_data.get("spy_change_7d", 0.0)
            }

            st.markdown("### Analyse synthétique (GPT)")
            st.markdown(get_gpt_analysis(data_input))

            fig = px.line(price_data, x="date", y="close", title=f"Prix de {symbol}")
            fig.add_scatter(x=price_data["date"], y=price_data["SUPPORT"], name="Support", line=dict(dash="dash"))
            fig.add_scatter(x=price_data["date"], y=price_data["RESISTANCE"], name="Résistance", line=dict(dash="dash"))
            st.plotly_chart(fig, key=f"chart_{symbol}_{interval}")

            st.write(f"Versions : Main v{VERSION}, Analyzer v{ANALYZER_VERSION}, Data Fetcher v{DATA_FETCHER_VERSION}, Indicators v{INDICATORS_VERSION}")

            with st.expander("Logs"):
                st.text("\n".join(log_stream.getvalue().splitlines()[-10:]))

        except Exception as e:
            logger.error(f"Erreur générale : {e}")
            st.error(f"❌ Erreur : {e}")
            st.markdown("### Logs")
            st.text("\n".join(log_stream.getvalue().splitlines()[-10:]))
