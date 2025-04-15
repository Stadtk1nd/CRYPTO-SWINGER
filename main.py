import streamlit as st
import pandas as pd
import plotly.express as px
import os
import logging
from datetime import datetime, timezone
from data_fetcher import fetch_all_data
from indicators import calculate_indicators, validate_data
from analyzer import analyze_technical, analyze_fundamental, analyze_macro, generate_recommendation

# Configuration de la journalisation vers stdout avec un handler en mémoire
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# Handler en mémoire pour capturer les logs
from io import StringIO
log_stream = StringIO()
stream_handler = logging.StreamHandler(log_stream)
stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(stream_handler)

# Clés API depuis variables d’environnement
FRED_API_KEY = os.environ.get("FRED_API_KEY")
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY")
LUNARCRUSH_API_KEY = os.environ.get("LUNARCRUSH_API_KEY")

# Interface Streamlit
st.title("Assistant de Trading Crypto v3")
st.write("Entrez les paramètres pour générer un plan de trading.")

# Formulaire dynamique
with st.form("trading_form"):
    symbol_input = st.text_input("🔍 Entrez la crypto (ex: BTC ou BTCUSDT)", "BTC").upper()
    interval_input = st.selectbox("⏳ Choisissez l’intervalle", ["1H", "4H", "1D", "1W"], index=0)
    submit_button = st.form_submit_button("Lancer l’analyse")

if submit_button:
    with st.spinner("Analyse en cours..."):
        try:
            # Réinitialiser le buffer de logs
            log_stream.seek(0)
            log_stream.truncate(0)

            # Préparation des paramètres
            symbol = symbol_input if symbol_input.endswith("USDT") else symbol_input + "USDT"
            coin_id_map = {"BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin", "ADA": "cardano"}
            coin_id = coin_id_map.get(symbol_input.lower().replace("usdt", ""), symbol_input.lower().replace("usdt", ""))
            interval = interval_input.lower()

            # Récupération des données
            price_data, fundamental_data, macro_data = fetch_all_data(symbol, interval, coin_id, FRED_API_KEY, ALPHA_VANTAGE_API_KEY)

            # Affichage des logs capturés
            with st.expander("Logs de débogage (avant validation)"):
                log_content = log_stream.getvalue().splitlines()
                st.text("\n".join(log_content[-10:]) if log_content else "Aucun log disponible.")

            # Validation des données
            is_valid, validation_message = validate_data(price_data)
            if not is_valid:
                st.error(f"❌ Erreur : {validation_message}")
                st.markdown("**Détails supplémentaires** : Vérifiez les logs ci-dessus pour plus d’informations. Cela peut être dû à une erreur réseau ou à une limitation de l’API Binance.")
                st.stop()

            # Calcul des indicateurs
            price_data = calculate_indicators(price_data, interval_input)

            # Analyse
            technical_score, technical_details = analyze_technical(price_data, interval_input)
            fundamental_score, fundamental_details = analyze_fundamental(fundamental_data)
            macro_score, macro_details = analyze_macro(macro_data, interval_input)

            # Recommandation
            signal, confidence, buy_price, sell_price = generate_recommendation(
                price_data, technical_score, fundamental_score, macro_score, interval_input
            )

            # Affichage des résultats
            st.markdown("### Recommandation de trading")
            st.markdown(f"**Préconisation** : {signal}")
            st.markdown(f"**Prix d'achat recommandé** : ${buy_price:.2f}")
            st.markdown(f"**Prix de vente recommandé** : ${sell_price:.2f}")
            st.markdown(f"**Confiance** : {confidence:.2%}")

            with st.expander("Détails de l’analyse"):
                st.markdown(f"**Score technique** : {technical_score}")
                for detail in technical_details:
                    st.markdown(f"- {detail}")
                st.markdown(f"**Score fondamental** : {fundamental_score}")
                for detail in fundamental_details:
                    st.markdown(f"- {detail}")
                st.markdown(f"**Score macroéconomique** : {macro_score}")
                for detail in macro_details:
                    st.markdown(f"- {detail}")

            # Affichage des logs après analyse
            with st.expander("Logs de débogage (après analyse)"):
                log_content = log_stream.getvalue().splitlines()
                st.text("\n".join(log_content[-10:]) if log_content else "Aucun log disponible.")

            # Visualisation
            fig = px.line(price_data, x="date", y="close", title=f"Prix de {symbol}")
            fig.add_scatter(x=price_data["date"], y=price_data["SUPPORT"], name="Support", line=dict(dash="dash"))
            fig.add_scatter(x=price_data["date"], y=price_data["RESISTANCE"], name="Résistance", line=dict(dash="dash"))
            st.plotly_chart(fig)

        except Exception as e:
            logger.error(f"Erreur générale : {e}")
            st.error(f"❌ Une erreur est survenue : {e}")
            with st.expander("Logs de débogage (en cas d’erreur)"):
                log_content = log_stream.getvalue().splitlines()
                st.text("\n".join(log_content[-10:]) if log_content else "Aucun log disponible.")
