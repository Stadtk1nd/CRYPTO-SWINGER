# gpt_analyzer.py

import os
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

# Initialisation du client OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("❌ Clé API OpenAI manquante. Définissez OPENAI_API_KEY dans les variables d'environnement.")

client = OpenAI(api_key=OPENAI_API_KEY)

def generate_gpt_analysis(symbol, interval,
                          technical_score, technical_details,
                          fundamental_score, fundamental_details,
                          macro_score, macro_details,
                          signal, confidence, buy_price, sell_price):
    """
    Génère une synthèse GPT à partir des résultats d'analyse.
    """
    system_message: ChatCompletionMessageParam = {
        "role": "system",
        "content": (
            "Tu es un assistant expert en trading crypto. "
            "Tu interprètes les analyses techniques, fondamentales et macroéconomiques pour rédiger une synthèse utile aux traders expérimentés."
        )
    }

    user_prompt = f"""
Crypto : {symbol}
Intervalle : {interval}

📊 Technique (score : {technical_score}) :
{chr(10).join(f"- {d}" for d in technical_details)}

📈 Fondamentale (score : {fundamental_score}) :
{chr(10).join(f"- {d}" for d in fundamental_details)}

🌍 Macroéco (score : {macro_score}) :
{chr(10).join(f"- {d}" for d in macro_details)}

📌 Signal brut : {signal} (confiance : {confidence:.0%})
🎯 Prix d’achat : ${buy_price:.2f}
🎯 Prix de vente : ${sell_price:.2f}

Rédige une synthèse en français, structurée et claire, pour aider un trader à prendre une décision.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                system_message,
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"❌ Erreur lors de la génération de l'analyse GPT : {e}"
