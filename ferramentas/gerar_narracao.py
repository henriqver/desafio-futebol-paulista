#!/usr/bin/env python3
"""
Gera os áudios de narração do Desafio Futebol Paulista (pasta narracao/).

Os áudios gerados aqui são tocados pelo próprio jogo e, por isso, entram no vídeo gravado.
(A voz do navegador não pode ser gravada: é uma limitação de todos os navegadores.)

O que o script faz:
  1. Lê dados/jogadores.csv, dados/quiz.csv e dados/escudos.csv e monta a lista de falas
     (perguntas fixas, nomes de clubes, nomes de jogadores e perguntas do quiz).
  2. Grava narracao/roteiro.csv com todas as falas e o nome de arquivo de cada uma
     (serve também para gravar com um locutor, se a FPF preferir).
  3. Gera os MP3 que ainda não existem, com o serviço configurado:
       - ElevenLabs: variáveis ELEVENLABS_API_KEY e ELEVENLABS_VOICE_ID (opcional: ELEVENLABS_MODEL)
       - ou Azure:   variáveis AZURE_TTS_KEY e AZURE_TTS_REGION
  4. Atualiza narracao/indice.json com os áudios disponíveis.

Uso:  python ferramentas/gerar_narracao.py
Sem dependências além do Python 3.
"""
import csv, json, os, re, sys, time, unicodedata, urllib.request, urllib.error
from pathlib import Path
from xml.sax.saxutils import escape

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "narracao"
VOZ = os.environ.get("AZURE_TTS_VOZ", "pt-BR-AntonioNeural")
VELOCIDADE = os.environ.get("AZURE_TTS_VELOCIDADE", "+5%")

FIXAS = ["Quem é o jogador?", "Quem jogou em", "e", "Quem nunca jogou no", "Quem nunca jogou na",
         "De qual clube é este escudo?", "Quem falta no", "Quem falta na", "Fim de jogo!",
         # nomes dos jogos (narrados na 1ª rodada quando a câmera está ligada)
         "Adivinhe pela carreira", "Jogou em todos", "Quem é o intruso?", "Adivinhe o escudo", "Escalação campeã", "Quiz do futebol paulista"]
# mesma lista de js/dados.js
PRONUNCIA = {"Botafogo-SP": "Botafogo de Ribeirão Preto", "Juventus-SP": "Juventus da Mooca", "Nacional-SP": "Nacional",
             "Comercial-SP": "Comercial", "River Plate (URU)": "River Plate", "Universidad Católica (EQU)": "Universidad Católica",
             "PSV": "P S V", "CSKA Moscou": "CSKA de Moscou",
             "Barcelona-SP": "Barcelona", "Flamengo-SP": "Flamengo de Guarulhos", "América-SP": "América de Rio Preto", "Rio Branco-SP": "Rio Branco de Americana", "Independente-SP": "Independente de Limeira", "ECUS": "E C U S", "USAC": "U S A C"}
ALIAS = {"S. Caetano": "São Caetano", "Sao Paulo": "São Paulo", "Bragantino": "Red Bull Bragantino"}


def slug(t):
    """Igual ao slug() de js/dados.js — define o nome do arquivo de cada fala."""
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if not ("\u0300" <= c <= "\u036f")).lower()
    return "-".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


def ler(nome):
    f = RAIZ / "dados" / nome
    if not f.exists():
        return []
    texto = f.read_text(encoding="utf-8-sig")
    sep = ";" if texto.split("\n")[0].count(";") > texto.split("\n")[0].count(",") else ","
    return list(csv.DictReader(texto.splitlines(), delimiter=sep))


def campo(linha, *nomes):
    for k, v in linha.items():
        if k and slug(k) in [slug(n) for n in nomes]:
            return (v or "").strip()
    return ""


def lista_colchetes(s):
    """Separa por vírgula, ignorando vírgulas dentro de [colchetes]."""
    out, atual, nivel = [], "", 0
    for ch in (s or ""):
        nivel += ch == "["; nivel -= ch == "]"
        if ch == "," and nivel == 0:
            out.append(atual.strip()); atual = ""
        else:
            atual += ch
    if atual.strip(): out.append(atual.strip())
    return [ALIAS.get(x, x) for x in out if x]


def lista(s):
    return [ALIAS.get(x.strip(), x.strip()) for x in (s or "").split(",") if x.strip()]


def falas():
    out = list(FIXAS)
    for r in ler("jogadores.csv"):
        out.append(campo(r, "Jogador"))
        out += lista(campo(r, "Times Paulistas que Passou")) + lista(campo(r, "Todos os Times da Carreira"))
    for r in ler("escudos.csv"):
        out.append(ALIAS.get(campo(r, "Clube"), campo(r, "Clube")))
    for r in ler("escalacoes.csv"):
        out.append(ALIAS.get(campo(r, "Time"), campo(r, "Time")))
        out.append(f"campeão de {campo(r, 'Ano')}")
        out += [re.sub(r"^[A-Za-z]{2,4}\s*:\s*", "", re.sub(r"\s*\[.*\]\s*$", "", x)) for x in lista_colchetes(campo(r, "Escalação", "Titulares")) + lista_colchetes(campo(r, "Substitutos", "Reservas"))]
    for r in ler("quiz.csv"):
        out.append(campo(r, "Pergunta"))
    vistos, unicas = set(), []
    for t in out:
        if t and slug(t) and slug(t) not in vistos:
            vistos.add(slug(t)); unicas.append(t)
    return unicas


def sintetizar(texto, chave, regiao):
    ssml = (f"<speak version='1.0' xml:lang='pt-BR'><voice name='{VOZ}'>"
            f"<prosody rate='{VELOCIDADE}'>{escape(PRONUNCIA.get(texto, texto))}</prosody></voice></speak>")
    req = urllib.request.Request(
        f"https://{regiao}.tts.speech.microsoft.com/cognitiveservices/v1", data=ssml.encode("utf-8"), method="POST",
        headers={"Ocp-Apim-Subscription-Key": chave, "Content-Type": "application/ssml+xml",
                 "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3", "User-Agent": "desafio-futebol-paulista"})
    for tentativa in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and tentativa < 3:
                time.sleep(2 * (tentativa + 1)); continue
            raise


def sintetizar_elevenlabs(texto, chave, voz):
    modelo = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    corpo = json.dumps({"text": PRONUNCIA.get(texto, texto), "model_id": modelo,
                        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.3, "use_speaker_boost": True}}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voz}?output_format=mp3_44100_128", data=corpo, method="POST",
        headers={"xi-api-key": chave, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    for tentativa in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and tentativa < 4:
                time.sleep(3 * (tentativa + 1)); continue
            raise RuntimeError(f"ElevenLabs respondeu {e.code}: {e.read()[:300]!r}")


def main():
    PASTA.mkdir(exist_ok=True)
    todas = falas()
    with open(PASTA / "roteiro.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["Texto", "Como falar", "Arquivo", "Status"])
        for t in todas:
            arq = f"{slug(t)}.mp3"
            w.writerow([t, PRONUNCIA.get(t, ""), f"narracao/{arq}", "ok" if (PASTA / arq).exists() else "faltando"])
    el_chave, el_voz = os.environ.get("ELEVENLABS_API_KEY"), os.environ.get("ELEVENLABS_VOICE_ID")
    chave, regiao = os.environ.get("AZURE_TTS_KEY"), os.environ.get("AZURE_TTS_REGION")
    if el_chave and el_voz:
        gerar, servico = (lambda t: sintetizar_elevenlabs(t, el_chave, el_voz)), "ElevenLabs"
    elif chave and regiao:
        gerar, servico = (lambda t: sintetizar(t, chave, regiao)), "Azure"
    else:
        gerar, servico = None, None
    faltando = [t for t in todas if not (PASTA / f"{slug(t)}.mp3").exists()]
    print(f"{len(todas)} falas; {len(faltando)} sem áudio; {sum(len(t) for t in faltando)} caracteres a gerar.")
    if faltando and not gerar:
        print("Nenhum serviço de voz configurado: nenhum áudio novo gerado (o roteiro foi atualizado).")
    elif faltando:
        print(f"Gerando com {servico}…")
        limite = int(os.environ.get("NARRACAO_LIMITE_CARACTERES", "0") or 0)
        usados = 0
        try:
            for n, t in enumerate(faltando, 1):
                if limite and usados + len(t) > limite:
                    print(f"Limite de {limite} caracteres atingido; o restante fica para a próxima execução.")
                    break
                (PASTA / f"{slug(t)}.mp3").write_bytes(gerar(t))
                usados += len(t)
                print(f"[{n}/{len(faltando)}] {t}")
        except Exception as e:
            # cota esgotada ou falha de rede: guarda o que já foi gerado e continua na próxima execução
            print(f"Interrompido: {e}")
    disponiveis = sorted(p.stem for p in PASTA.glob("*.mp3"))
    (PASTA / "indice.json").write_text(json.dumps(disponiveis, ensure_ascii=False), encoding="utf-8")
    print(f"indice.json: {len(disponiveis)} áudios.")


if __name__ == "__main__":
    main()
