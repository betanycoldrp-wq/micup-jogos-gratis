
import requests

URL = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"

def buscar_jogos_gratis():
    resposta = requests.get(
        URL,
        params={"locale": "pt-BR", "country": "BR"},
        timeout=20
    )
    resposta.raise_for_status()

    jogos = resposta.json()["data"]["Catalog"]["searchStore"]["elements"]

    for jogo in jogos:
        print(jogo["title"])

if __name__ == "__main__":
    buscar_jogos_gratis()
