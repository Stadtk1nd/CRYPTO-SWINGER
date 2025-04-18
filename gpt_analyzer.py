# gpt_analyzer.py

import os
import openai

# Récupération de la clé API OpenAI depuis les variables d’environnement
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("❌ Clé API OpenAI manquante. Définissez OPENAI_API_KEY dans les variables d'environnement.")

openai.api_key = OPENAI_API_KEY

def generate_gpt_analysis(symbol, interval,
                          technical_score, technical_details,
                          fundamental_score, fundamental_details,
                          macro_score, macro_details,
                          signal, confidence, buy_price, sell_price):
    """
    Génère une analyse synthétique rédigée en français à partir des scores et signaux d’analyse.
    """
    system_prompt = (
        "Tu es un assistant expert en trading crypto. "
        "Tu sais interpréter les indicateurs techniques, fondamentaux et macroéconomiques pour produire "
        "des synthèses concises et argumentées, utiles aux traders expérimentés."
    )

    user_prompt = f"""
Crypto analysée : {symbol}
Intervalle de temps : {interval}

📊 Analyse technique (score : {technical_score}) :
{chr(10).join(f"- {detail}" for detail in technical_details)}

📈 Analyse fondamentale (score : {fundamental_score}) :
{chr(10).join(f"- {detail}" for detail in fundamental_details)}

🌍 Analyse macroéconomique (score : {macro_score}) :
{chr(10).join(f"- {detail}" for detail in macro_details)}

🎯 Recommandation algorithmique : {signal.upper()} (confiance : {confidence:.0%})
Prix d’achat estimé : ${buy_price:.2f}
Prix de vente estimé : ${sell_price:.2f}

À partir de ces informations, rédige une analyse synthétique (5 à 10 lignes) en français,
structurée, professionnelle et orientée décision. Termine par une recommandation claire.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=600,
        )
        return response["choices"][0]["message"]["content"]

    except Exception as e:
        return f"❌ Erreur lors de la génération de l'analyse GPT : {e}"
