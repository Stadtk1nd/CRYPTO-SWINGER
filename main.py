VERSION = "7.2.6"  # Incrémenté pour correction du bouton de copie dans le presse-papier avec échappement correct

import streamlit as st
import pandas as pd
import plotly.express as px
import os
import logging
import html
from datetime import datetime, timezone
from data_fetcher import fetch_all_data, VERSION as DATA_FETCHER_VERSION, COINCAP_ID_MAP
from indicators import calculate_indicators, validate_data, VERSION as INDICATORS_VERSION
from analyzer import analyze_technical, analyze_fundamental, analyze_macro, generate_recommendation, VERSION as ANALYZER_VERSION

# Fonction pour formater les détails de l'analyse
def format_analysis_details(symbol, signal, technical_score, technical_details, fundamental_score, fundamental_details, macro_score, macro_details):
    """Formate les détails de l'analyse pour le presse-papier."""
    details = [
        f"Synthétise ces données en un commentaire structuré pour un trader averti, avec une préconisation de trading à court, moyen et long terme sur la cryptomonnaie {symbol}",
        f"Préconisation actuelle : {signal}",
        f"Score technique : {technical_score}",
        *[f"- {detail}" for detail in technical_details],
        f"Score fondamental : {fundamental_score}",
        *[f"- {detail}" for detail in fundamental_details],
        f"Score macro : {macro_score}",
        *[f"- {detail}" for detail in macro_details]
    ]
    return "\n".join(details)

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

# Vérification des clés API
if not all([FRED_API_KEY, ALPHA_VANTAGE_API_KEY]):
    st.error("❌ Clés API manquantes. Configurez FRED_API_KEY et ALPHA_VANTAGE_API_KEY.")
    st.stop()

# Interface Streamlit
st.title("Assistant de Trading Crypto")
st.write("Entrez les paramètres pour générer un plan de trading.")

# Formulaire
with st.form("trading_form"):
    symbol_input = st.text_input("🔍 Entrez la crypto (ex: BTC ou BTCUSDT)", "BTC").upper()
    interval_input = st.selectbox("⏳ Choisissez l’intervalle", ["1H", "4H", "1D", "1W"], index=0)
    submit_button = st.form_submit_button("Lancer l’analyse")

if submit_button:
    # Validation du symbole
    if not symbol_input or not symbol_input.isalnum():
        st.error("❌ Symbole invalide. Entrez un symbole comme BTC ou BTCUSDT.")
        st.stop()

    with st.spinner("Analyse en cours..."):
        try:
            # Réinitialiser les logs
            log_stream.seek(0)
            log_stream.truncate(0)

            # Préparation des paramètres
            symbol = symbol_input if symbol_input.endswith("USDT") else symbol_input + "USDT"
            symbol_key = symbol_input.upper().replace("USDT", "")
            coin_id = COINCAP_ID_MAP.get(symbol_key.lower(), symbol_key.lower())
            interval = interval_input.lower()

            # Vérifier si le symbole existe
            if symbol_key.lower() not in COINCAP_ID_MAP:
                st.warning(f"⚠️ Symbole {symbol_key} non trouvé dans CoinCap. Tentative avec ID générique.")

            # Purger cache si symbole change
            if "last_symbol" not in st.session_state or st.session_state.last_symbol != symbol:
                st.cache_data.clear()
                st.session_state.last_symbol = symbol

            # Récupération des données (cachée)
            @st.cache_data(show_spinner=False)
            def cached_fetch_all_data(_symbol, _interval, _coin_id, _fred_key, _alpha_key, _cache_key=None):
                return fetch_all_data(_symbol, _interval, _coin_id, _fred_key, _alpha_key, _cache_key=_cache_key)

            logger.info(f"Début de fetch_all_data pour {symbol} ({interval})")
            price_data, fundamental_data, macro_data, price_data_dict = cached_fetch_all_data(
                symbol, interval, coin_id, FRED_API_KEY, ALPHA_VANTAGE_API_KEY, _cache_key=symbol
            )

            # Validation des données
            is_valid, validation_message = validate_data(price_data)
            if not is_valid:
                st.error(f"❌ Erreur : {validation_message}")
                log_content = log_stream.getvalue()
                if "451 Client Error" in log_content:
                    st.markdown("**Détails** : Accès à l’API Binance bloqué (erreur 451). Restrictions géographiques ou IP possible.")
                elif "401 Client Error" in log_content:
                    st.markdown("**Détails** : Accès à l’API CoinCap échoué (erreur 401). Vérifiez COINCAP_API_KEY.")
                else:
                    st.markdown("**Détails** : Échec récupération données via APIs (Binance, CoinCap, Kraken, Binance Futures).")
                st.markdown("### Logs")
                st.text("\n".join(log_stream.getvalue().splitlines()[-10:]))
                st.stop()

            # Calcul des indicateurs
            price_data = calculate_indicators(price_data, interval_input)
            for key in price_data_dict:
                price_data_dict[key] = calculate_indicators(price_data_dict[key], key.upper())

            # Analyse MTFA
            technical_score, technical_details = analyze_technical(price_data, interval_input, price_data_dict)
            fundamental_score, fundamental_details = analyze_fundamental(fundamental_data)
            macro_score, macro_details = analyze_macro(macro_data, interval_input)

            # Recommandation
            signal, confidence, buy_price, sell_price = generate_recommendation(
                price_data, technical_score, fundamental_score, macro_score, interval_input, price_data_dict
            )

            # Résultats
            st.markdown("### Recommandation de trading")
            st.markdown(f"**Préconisation** : {signal}")
            st.markdown(f"**Prix d'achat** : ${buy_price:.2f}")
            st.markdown(f"**Prix de vente** : ${sell_price:.2f}")

            with st.expander("Détails de l’analyse"):
                st.markdown(f"**Score technique** : {technical_score}")
                for detail in technical_details:
                    st.markdown(f"- {detail}")
                st.markdown(f"**Score fondamental** : {fundamental_score}")
                for detail in fundamental_details:
                    st.markdown(f"- {detail}")
                st.markdown(f"**Score macro** : {macro_score}")
                for detail in macro_details:
                    st.markdown(f"- {detail}")

            # Logs
            with st.expander("Logs"):
                st.text("\n".join(log_stream.getvalue().splitlines()[-10:]))

            # Bouton pour copier les détails dans le presse-papier
            details_text = format_analysis_details(
                symbol, signal, technical_score, technical_details, fundamental_score, fundamental_details, macro_score, macro_details
            )
            escaped_text = html.escape(details_text)
            st.markdown(
                f"""
                <button onclick="copyToClipboard()">Copier les détails dans le presse-papier</button>
                <input type="hidden" id="details_text" value="{escaped_text}">
                <script>
                    function copyToClipboard() {{
                        var text = document.getElementById('details_text').value;
                        navigator.clipboard.writeText(text).then(function() {{
                            document.getElementById('copy_status').innerText = 'Texte copié dans le presse-papier !';
                        }}, function(err) {{
                            document.getElementById('copy_status').innerText = 'Erreur lors de la copie : ' + err;
                        }});
                    }}
                </script>
                <div id="copy_status"></div>
                """,
                unsafe_allow_html=True
            )

            # Visualisation
            fig = px.line(price_data, x="date", y="close", title=f"Prix de {symbol}")
            fig.add_scatter(x=price_data["date"], y=price_data["SUPPORT"], name="Support", line=dict(dash="dash"))
            fig.add_scatter(x=price_data["date"], y=price_data["RESISTANCE"], name="Résistance", line=dict(dash="dash"))
            st.plotly_chart(fig, key=f"chart_{symbol}_{interval}")

            # Versions
            st.write(f"Versions : Main v{VERSION}, Analyzer v{ANALYZER_VERSION}, Data Fetcher v{DATA_FETCHER_VERSION}, Indicators v{INDICATORS_VERSION}")

        except Exception as e:
            logger.error(f"Erreur générale : {e}")
            st.error(f"❌ Erreur : {e}")
            st.markdown("### Logs")
            st.text("\n".join(log_stream.getvalue().splitlines()[-10:]))
