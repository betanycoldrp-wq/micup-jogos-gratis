
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

WEBHOOK = os.environ["MICUP_WEBHOOK_URL"]
TESTE = os.getenv("TEST_MODE", "true").lower() == "true"
HISTORICO = Path("jogos_enviados.json")

LIMITE = 8
POR_LOJA = 2

LOJAS = {
    "1": "Steam",
    "25": "Epic Games",
    "7": "GOG"
}

SESSAO = requests.Session()
SESSAO.headers.update({
    "User-Agent": "BrasilGamers-OfertasBot/2.0 (GitHub Actions)"
})


def requisitar(url, params=None):
    r = SESSAO.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def moeda(valor, codigo):
    if codigo == "BRL":
        return "R$ " + f"{valor:,.2f}".replace(
            ",", "X"
        ).replace(".", ",").replace("X", ".")
    if codigo == "USD":
        return f"US$ {valor:.2f}"
    return f"{codigo} {valor:.2f}"


def preco_steam(appid):
    if not appid:
        return None

    try:
        dados = requisitar(
            "https://store.steampowered.com/api/appdetails",
            {"appids": appid, "cc": "BR",
             "filters": "price_overview"}
        )
        registro = dados.get(str(appid), {})
        if not registro.get("success"):
            return None

        preco = registro["data"]["price_overview"]
        if preco.get("currency") != "BRL":
            return None

        return {
            "normal": preco["initial"] / 100,
            "atual": preco["final"] / 100,
            "moeda": "BRL"
        }
    except (requests.RequestException, KeyError,
            TypeError, ValueError) as erro:
        print("Steam regional indisponivel:", erro)
        return None


def ofertas_cheapshark():
    resultado = []

    for codigo, loja in LOJAS.items():
        try:
            dados = requisitar(
                "https://www.cheapshark.com/api/1.0/deals",
                {
                    "storeID": codigo,
                    "onSale": 1,
                    "pageSize": 30
                }
            )
            print(f"{loja}: {len(dados)} ofertas")

            for j in dados:
                normal = float(j["normalPrice"])
                atual = float(j["salePrice"])

                if normal <= 0 or atual >= normal:
                    continue

                link = (
                    "https://www.cheapshark.com/redirect"
                    "?dealID=" + quote(j["dealID"], safe="")
                )

                if loja == "Steam" and j.get("steamAppID"):
                    link = (
                        "https://store.steampowered.com/app/"
                        + str(j["steamAppID"]) + "/"
                    )

                resultado.append({
                    "id": f"cheap:{codigo}:{j['gameID']}",
                    "titulo": j["title"],
                    "loja": loja,
                    "normal": normal,
                    "atual": atual,
                    "moeda": "USD",
                    "appid": j.get("steamAppID"),
                    "imagem": j.get("thumb", ""),
                    "link": link
                })

        except (requests.RequestException, ValueError,
                KeyError, TypeError) as erro:
            print(f"Erro em {loja}: {erro}")

    return resultado


def ofertas_gratis_epic():
    resultado = []

    try:
        dados = requisitar(
            "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",
            {
                "locale": "pt-BR",
                "country": "BR",
                "allowCountries": "BR"
            }
        )

        jogos = dados["data"]["Catalog"]["searchStore"]["elements"]
        agora = datetime.now(timezone.utc)

        for j in jogos:
            preco = (j.get("price") or {}).get("totalPrice") or {}
            original = preco.get("originalPrice", 0)

            if original <= 0:
                continue

            promocoes = j.get("promotions") or {}
            grupos = promocoes.get("promotionalOffers") or []

            for grupo in grupos:
                for oferta in grupo.get("promotionalOffers", []):
                    if (
                        oferta.get("discountSetting", {}).get(
                            "discountPercentage"
                        ) != 0
                    ):
                        continue

                    inicio = datetime.fromisoformat(
                        oferta["startDate"].replace("Z", "+00:00")
                    )
                    fim = datetime.fromisoformat(
                        oferta["endDate"].replace("Z", "+00:00")
                    )

                    if not inicio <= agora < fim:
                        continue

                    mapeamentos = (
                        (j.get("catalogNs") or {}).get("mappings") or []
                    )
                    slug = (
                        mapeamentos[0].get("pageSlug")
                        if mapeamentos else j.get("productSlug")
                    )

                    if not slug:
                        continue

                    imagens = j.get("keyImages") or []
                    imagem = next(
                        (
                            x.get("url", "")
                            for x in imagens
                            if x.get("type") in (
                                "OfferImageWide", "DieselStoreFrontWide",
                                "Thumbnail"
                            )
                        ),
                        ""
                    )

                    codigo_moeda = preco.get("currencyCode", "USD")
                    divisor = (
                        preco.get("currencyInfo") or {}
                    ).get("decimals", 2)

                    resultado.append({
                        "id": f"epic-gratis:{j['id']}:{oferta['endDate']}",
                        "titulo": j["title"],
                        "loja": "Epic Games",
                        "normal": original / (10 ** divisor),
                        "atual": 0,
                        "moeda": codigo_moeda,
                        "imagem": imagem,
                        "link": (
                            "https://store.epicgames.com/pt-BR/p/"
                            + slug.strip("/")
                        )
                    })
                    break

    except (requests.RequestException, KeyError,
            ValueError, TypeError) as erro:
        print("Epic gratuitos indisponiveis:", erro)

    return resultado


def publicar(jogo):
    normal = jogo["normal"]
    atual = jogo["atual"]
    codigo = jogo["moeda"]
    gratis = atual == 0

    desconto = round((1 - atual / normal) * 100)

    embed = {
        "title": (
            "🎁 JOGO GRÁTIS!"
            if gratis else "🔥 OFERTA DE JOGO!"
        ),
        "description": (
            f"🎮 **{jogo['titulo']}**\n\n"
            f"🛒 **Loja:** {jogo['loja']}\n"
            f"💰 **De:** {moeda(normal, codigo)}\n"
            f"💵 **Por:** "
            f"{'GRÁTIS' if gratis else moeda(atual, codigo)}\n"
            f"🏷️ **Desconto:** {desconto}% OFF\n\n"
            f"🔗 [Ver na loja]({jogo['link']})"
        ),
        "color": 5763719 if gratis else 3447003,
        "footer": {"text": "Brasil Gamers | Ofertas"}
    }

    if jogo.get("imagem"):
        imagem = jogo["imagem"]
        if imagem.startswith("//"):
            imagem = "https:" + imagem
        if imagem.startswith("https://"):
            embed["image"] = {"url": imagem}

    if TESTE:
        print(
            "[TESTE]",
            jogo["loja"],
            jogo["titulo"],
            moeda(atual, codigo)
        )
        return

    resposta = requests.post(
        WEBHOOK,
        json={"embeds": [embed]},
        timeout=30
    )
    resposta.raise_for_status()
    time.sleep(2)

def chave_jogo(jogo):
    import re
    import unicodedata

    titulo = unicodedata.normalize(
        "NFKD", jogo["titulo"]
    )

    titulo = "".join(
        c for c in titulo
        if not unicodedata.combining(c)
    )

    titulo = re.sub(
        r"[^a-z0-9]+", "",
        titulo.casefold()
    )

    loja = jogo["loja"].casefold()

    return f"v2:{loja}:{titulo}"

def executar():
    historico = {}
    if HISTORICO.exists():
        historico = json.loads(
            HISTORICO.read_text(encoding="utf-8")
        )

    candidatos = ofertas_gratis_epic() + ofertas_cheapshark()
    # Evitar duplicações entre fontes diferentes
    # Prioriza jogos gratuitos da Epic Games Brasil.
    import re
    import unicodedata

    def normalizar_titulo(titulo):
        titulo = unicodedata.normalize("NFKD", titulo)
        titulo = "".join(
            c for c in titulo
            if not unicodedata.combining(c)
        )
        titulo = titulo.casefold()
        return re.sub(r"[^a-z0-9]+", "", titulo)

    unicos = {}

    for jogo in candidatos:
        chave = (
            jogo["loja"].casefold(),
            normalizar_titulo(jogo["titulo"])
        )

        anterior = unicos.get(chave)

        if anterior is None:
            unicos[chave] = jogo
            continue

        # Preferir a oferta gratuita e regional
        def prioridade(item):
            return (
                item["atual"] == 0,
                item["moeda"] == "BRL"
            )

        if prioridade(jogo) > prioridade(anterior):
            unicos[chave] = jogo

    candidatos = list(unicos.values())

    print(
        f"Ofertas após remover duplicações: "
        f"{len(candidatos)}"
    )


    # Consultar preços brasileiros dos candidatos Steam
    consultas = 0
    for jogo in candidatos:
        if jogo["loja"] != "Steam":
            continue
        if consultas >= 30:
            break

        consultas += 1
        regional = preco_steam(jogo.get("appid"))

        if regional:
            jogo.update(regional)
        else:
            # Não anunciar preço americano como brasileiro
            continue

    # Não divulgar ofertas Steam sem preço BR confirmado
    candidatos = [
        j for j in candidatos
        if j["loja"] != "Steam" or j["moeda"] == "BRL"
    ]

    # Apenas ofertas com desconto real
    candidatos = [
        j for j in candidatos
        if j["normal"] > 0 and 0 <= j["atual"] < j["normal"]
    ]

    candidatos.sort(
        key=lambda j: (
            j["atual"] == 0,
            (j["normal"] - j["atual"]) / j["normal"]
        ),
        reverse=True
    )

    selecionados = []
    ids = set()
    contagem = {loja: 0 for loja in LOJAS.values()}

    def pendente(j):
        chave = f"{j['moeda']}:{j['atual']:.2f}"
        return historico.get(chave_jogo(j)) != chave

    def adicionar(j):
        if j["id"] in ids or not pendente(j):
            return
        selecionados.append(j)
        ids.add(j["id"])
        contagem[j["loja"]] += 1

    # Gratuitos primeiro
    for j in candidatos:
        if len(selecionados) >= LIMITE:
            break
        if j["atual"] == 0:
            adicionar(j)

    # Distribuir as demais ofertas
    for j in candidatos:
        if len(selecionados) >= LIMITE:
            break
        if contagem[j["loja"]] < POR_LOJA:
            adicionar(j)

    # Completar as vagas
    for j in candidatos:
        if len(selecionados) >= LIMITE:
            break
        adicionar(j)

    for j in selecionados:
        publicar(j)

        if not TESTE:
            historico[chave_jogo(j)] = (
                f"{j['moeda']}:{j['atual']:.2f}"
            )

            HISTORICO.write_text(
                json.dumps(
                    historico,
                    ensure_ascii=False,
                    indent=2
                ),
                encoding="utf-8"
            ) 
    print("Ofertas selecionadas:", len(selecionados))
    print("Distribuicao:", contagem)
    print("Modo teste:", TESTE)


if __name__ == "__main__":
    executar()
