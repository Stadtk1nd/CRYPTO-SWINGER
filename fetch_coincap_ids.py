import requests
import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def fetch_coincap_ids():
    """Récupère les 100 plus grandes cryptos et leurs ID via l'API CoinCap v3."""
    url = "https://rest.coincap.io/v3/assets?limit=100"
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
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des ID CoinCap : {e}")
        return {}

if __name__ == "__main__":
    # Exécuter et sauvegarder les données dans un fichier JSON
    coincap_ids = fetch_coincap_ids()
    with open("coincap_ids.json", "w") as f:
        json.dump(coincap_ids, f, indent=4)
    print(f"Dictionnaire sauvegardé dans coincap_ids.json : {coincap_ids}")
