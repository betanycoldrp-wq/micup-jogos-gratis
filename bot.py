
import json
import os
import time
from pathlib import Path

import requests

WEBHOOK = os.environ["MICUP_WEBHOOK_URL"]
ARQUIVO = Path("jogos_enviados.json")
API = "https://www.cheapshark.com/api/1.0/deals"

LOJAS = {
    "1": "Steam",
    "7": "GOG",
    "25": "Epic Games"
}

LIMITE = 8


def consultar():
    ofertas = []

    for codigo, loja in LOJAS.items():
        resposta = requests.get(
            API,
            params={
                "storeID": codigo,
                "onSale": 1,
                "pageSize": 60,
            },
            timeout=30
        )
        resposta.raise_for_status()

        for item in resposta.json():
            item["loja"] = loja
            ofertas.append(item)

    return ofertas


def executar():
    historico = {}

    if ARQUIVO.exists():
        historico = json.loads(
            ARQUIVO.read_text(encoding="utf-8")
        )

    ofertas = consultar()
    enviados = 0

    for jogo in ofertas:
        preco = float(jogo["salePrice"])
        normal = float(jogo["normalPrice"])

        if normal <= preco:
            continue

        desconto = round((1 - preco / normal) * 100)
        if desconto <= 0:
            continue

        identificador = (
            str(jogo["storeID"]) + ":"
            + str(jogo["gameID"])
        )

        assinatura = str(jogo["salePrice"])

        if historico.get(identificador) == assinatura:
            continue

        gratuito = preco == 0

        titulo = (
            "🎁 JOGO GRÁTIS!"
            if gratuito
            else "🔥 PROMOÇÃO DE JOGO!"
        )

        preco_texto = (
            "GRÁTIS"
            if gratuito
            else f"US$ {preco:.2f}"
        )

        link = (
            "https://www.cheapshark.com/redirect"
            "?dealID=" + requests.utils.quote(
                jogo["dealID"], safe=""
            )
        )

        mensagem = (
            f"**{titulo}**\n\n"
            f"🎮 **{jogo['title']}**\n"
            f"🛒 Loja: {jogo['loja']}\n"
            f"💰 De US$ {normal:.2f} "
            f"por **{preco_texto}**\n"
            f"🏷️ Desconto: {desconto}%\n\n"
            f"🔗 {link}\n\n"
            "🇧🇷 Brasil Gamers | Ofertas"
        )

        resposta = requests.post(
            WEBHOOK,
            json={"content": mensagem},
            timeout=30
        )
        resposta.raise_for_status()

        historico[identificador] = assinatura

        ARQUIVO.write_text(
            json.dumps(
                historico,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        enviados += 1
        time.sleep(2)

        if enviados >= LIMITE:
            break

    print(f"Ofertas publicadas: {enviados}")


if __name__ == "__main__":
    executar()
