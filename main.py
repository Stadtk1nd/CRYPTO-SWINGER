import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from data_fetcher import fetch_all_data, VERSION as DATA_FETCHER_VERSION
from indicators import calculate_indicators, VERSION as INDICATORS_VERSION
from analyzer import analyze_technical, analyze_fundamental, analyze_macro, generate_recommendation, VERSION as ANALYZER_VERSION
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

st.set_page_config(page_title="CryptoSwing Dashboard", layout="wide")

st.title("CryptoSwing Dashboard")

# Sidebar pour les inputs utilisateur
st.sidebar.header("Paramètres")
symbol = st.sidebar.selectbox("Sélectionnez une cryptomonnaie", ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT"])
interval = st.sidebar.selectbox("Intervalle de temps", ["1H", "4H", "1D", "1W"]).lower()
fred_api_key = st.sidebar.text_input("Clé API FRED", value=os.environ.get("FRED_API_KEY", ""))
alpha_vantage_api_key = st.sidebar.text_input("Clé API Alpha Vantage", value=os.environ.get("ALPHA_VANTAGE_API_KEY", ""))

if not fred_api_key or not alpha_vantage_api_key:
    st.error("Veuillez fournir les clés API FRED et Alpha Vantage.")
else:
    # Correspondance entre symbol et coin_id
    coin_id_map = {
        "BTCUSDT": "bitcoin",
        "ETHUSDT": "ethereum",
        "BNBUSDT": "binancecoin",
        "ADAUSDT": "cardano"
    }
    coin_id = coin_id_map.get(symbol, "bitcoin")

    # Récupérer les données
    try:
        with st.spinner("Récupération des données..."):
            price_data, fundamental_data, macro_data = fetch_all_data(
                symbol, interval, coin_id, fred_api_key, alpha_vantage_api_key
            )
        if price_data.empty:
            st.error("Aucune donnée de prix récupérée. Vérifiez les API ou les paramètres.")
        else:
            # Calculer les indicateurs
            price_data = calculate_indicators(price_data)

            # Analyses
            technical_score, technical_details = analyze_technical(price_data, interval.upper())
            fundamental_score, fundamental_details = analyze_fundamental(fundamental_data)
            macro_score, macro_details = analyze_macro(macro_data, interval.upper())

            # Générer la recommandation
            signal, confidence, buy_price, sell_price = generate_recommendation(
                price_data, technical_score, fundamental_score, macro_score, interval.upper()
            )

            # Afficher le graphique
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=price_data["date"],
                open=price_data["open"],
                high=price_data["high"],
                low=price_data["low"],
                close=price_data["close"],
                name="OHLC"
            ))
            fig.update_layout(
                title=f"{symbol} - {interval.upper()}",
                xaxis_title="Date",
                yaxis_title="Prix (USDT)",
                xaxis_rangeslider_visible=False
            )
            st.plotly_chart(fig, use_container_width=True)

            # Afficher les versions des fichiers sous le graphique
            st.write(f"Versions des fichiers utilisés : Analyzer v{ANALYZER_VERSION}, Data Fetcher v{DATA_FETCHER_VERSION}, Indicators v{INDICATORS_VERSION}")

            # Afficher la recommandation
            st.subheader("Recommandation")
            st.write(f"**Signal** : {signal}")
            st.write(f"**Confiance** : {confidence:.2%}")
            st.write(f"**Prix d'achat suggéré** : {buy_price:.2f} USDT")
            st.write(f"**Prix de vente suggéré** : {sell_price:.2f} USDT")

            # Afficher les détails des analyses
            with st.expander("Détails de l'analyse technique"):
                for detail in technical_details:
                    st.write(f"- {detail}")
            with st.expander("Détails de l'analyse fondamentale"):
                for detail in fundamental_details:
                    st.write(f"- {detail}")
            with st.expander("Détails de l'analyse macroéconomique"):
                for detail in macro_details:
                    st.write(f"- {detail}")
    except Exception as e:
        logger.error(f"Erreur dans l'exécution : {e}")
        st.error(f"Une erreur s'est produite : {e}")
