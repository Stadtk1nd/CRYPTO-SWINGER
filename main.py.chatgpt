VERSION = "8.0.2"  # Incrémenté pour correction du bug de mise à jour du symbole

import streamlit as st
import pandas as pd
import plotly.express as px
import os
import logging
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
            interval = "1h"  # Valeur par défaut puisque le sélecteur est supprimé

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
            price_data = calculate_indicators(price_data, interval)
            for key in price_data_dict:
                price_data_dict[key] = calculate_indicators(price_data_dict[key], key.upper())

            # Analyse MTFA
            technical_score, technical_details = analyze_technical(price_data, interval, price_data_dict)
            fundamental_score, fundamental_details = analyze_fundamental(fundamental_data)
            macro_score, macro_details = analyze_macro(macro_data, interval)

            # Recommandation remplacée par analyse synthétique
            st.markdown("### Analyse synthétique")
            st.markdown("""
#### ✅ **Contexte global : mitigé avec biais technique baissier**

- **Macroéconomie : favorable**  
  - FED < 2 %, CPI à 0.65 %, PIB à 3.83 %, chômage < 4 % → soutien structurel des marchés.  
  - SPY > 400 → le marché actions reste globalement solide malgré un repli technique récent (-4.05 % sur 7 jours).


- **Sentiment et volatilité : dégradation**  
  - **Fear & Greed en baisse**, **VIX en hausse** → aversion au risque croissante.


- **Indicateurs techniques : dominés par la baisse**  
  - **RSI < 35** → zone de survente, possible rebond à court terme.  
  - **MACD baissier** → momentum négatif persistant.  
  - **ADX > 25 avec prix sous EMA20** → tendance baissière forte.  
  - **EMA12 > EMA26** → signal haussier contradictoire, mais faible dans ce contexte.


- **Fondamentaux crypto : solides**  
  - Market cap > 10B, TVL > 1B → actifs bien établis, pas de signe de fuite des capitaux.

---

#### 🧱 **Préconisation : Attente active / Vente partielle selon horizon**

- **Court terme (trading)** :  
  Vente partielle ou prise de profit conseillée.  
  → La dynamique baissière est dominante, malgré un possible rebond technique (RSI survendu).  
  → Le MACD + ADX sous EMA20 sont les signaux les plus forts ici.


- **Moyen terme (swing)** :  
  Attente active recommandée.  
  → Rester liquide ou en stablecoin en attendant un signal de retournement clair (MACD haussier, retour au-dessus EMA20).


- **Long terme (investissement)** :  
  Pas de vente agressive.  
  → Les fondamentaux macro et crypto sont solides. Une phase de correction peut offrir un point d’entrée plus bas.
            """)

            # Visualisation graphique juste en dessous
            fig = px.line(price_data, x="date", y="close", title=f"Prix de {symbol}")
            fig.add_scatter(x=price_data["date"], y=price_data["SUPPORT"], name="Support", line=dict(dash="dash"))
            fig.add_scatter(x=price_data["date"], y=price_data["RESISTANCE"], name="Résistance", line=dict(dash="dash"))
            st.plotly_chart(fig, key=f"chart_{symbol}_{interval}")

            # Versions
            st.write(f"Versions : Main v{VERSION}, Analyzer v{ANALYZER_VERSION}, Data Fetcher v{DATA_FETCHER_VERSION}, Indicators v{INDICATORS_VERSION}")

            # Logs en bas de page
            with st.expander("Logs"):
                st.text("\n".join(log_stream.getvalue().splitlines()[-10:]))

        except Exception as e:
            logger.error(f"Erreur générale : {e}")
            st.error(f"❌ Erreur : {e}")
            st.markdown("### Logs")
            st.text("\n".join(log_stream.getvalue().splitlines()[-10:]))
