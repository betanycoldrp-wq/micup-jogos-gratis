
import os
import requests

webhook = os.environ.get("MICUP_WEBHOOK_URL")

if not webhook:
    raise RuntimeError("Webhook nao configurado")

mensagem = {
    "content": (
        "🎮 TESTE BRASIL GAMERS\n\n"
        "O sistema de avisos de jogos gratis "
        "esta sendo configurado!\n\n"
        "Em breve, novidades da Epic Games."
    )
}

resposta = requests.post(
    webhook,
    json=mensagem,
    timeout=20
)

print("Status HTTP:", resposta.status_code)
print("Resposta:", resposta.text[:500])

resposta.raise_for_status()
