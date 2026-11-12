import base64
import json
import os
import urllib.error
import urllib.request


def executar_tesseract(imagem_processada, largura_original, altura_original):
    try:
        import pytesseract
    except ImportError as erro:
        raise RuntimeError(
            "Instale a dependência Python 'pytesseract' para usar o Tesseract."
        ) from erro

    dados = pytesseract.image_to_data(
        imagem_processada,
        lang="eng",
        output_type=pytesseract.Output.DICT,
    )
    escala_x = imagem_processada.shape[1] / largura_original
    escala_y = imagem_processada.shape[0] / altura_original
    resultados = []

    for indice, texto in enumerate(dados["text"]):
        texto = texto.strip()
        confianca = float(dados["conf"][indice])
        if not texto or confianca < 0:
            continue

        x1 = int(float(dados["left"][indice]) / escala_x)
        y1 = int(float(dados["top"][indice]) / escala_y)
        x2 = int(
            (float(dados["left"][indice]) + float(dados["width"][indice]))
            / escala_x
        )
        y2 = int(
            (float(dados["top"][indice]) + float(dados["height"][indice]))
            / escala_y
        )
        resultados.append((
            [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
            texto,
            confianca / 100,
        ))

    return "\n".join(resultado[1] for resultado in resultados), resultados


def executar_gemini(imagem_original, cv2_module):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Defina GEMINI_API_KEY para habilitar a comparação com a API Gemini."
        )

    sucesso, imagem_codificada = cv2_module.imencode(".jpg", imagem_original)
    if not sucesso:
        raise RuntimeError("Não foi possível codificar a imagem para a API Gemini.")

    altura, largura = imagem_original.shape[:2]
    modelo = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{modelo}:generateContent"
    )
    payload = {
        "contents": [{
            "parts": [
                {
                    "text": (
                        "Leia todo o texto visível nesta placa industrial. "
                        "Retorne somente JSON no formato "
                        '{"detections":[{"text":"...","box":[x_min,y_min,'
                        'x_max,y_max],"confidence":0.0}]}. As coordenadas da '
                        "caixa devem ser normalizadas entre 0 e 1 em relação "
                        "à imagem inteira. confidence deve estar entre 0 e 1. "
                        "Inclua uma detecção por trecho legível."
                    )
                },
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": base64.b64encode(imagem_codificada).decode("ascii"),
                    }
                },
            ]
        }],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    requisicao = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(requisicao, timeout=90) as resposta:
            resposta_api = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        raise RuntimeError(
            f"API Gemini respondeu HTTP {erro.code}: "
            f"{erro.read().decode('utf-8', errors='replace')[:500]}"
        ) from None
    except urllib.error.URLError as erro:
        raise RuntimeError(f"Falha de comunicação com a API Gemini: {erro.reason}") from erro

    try:
        texto_json = resposta_api["candidates"][0]["content"]["parts"][0]["text"]
        deteccoes = json.loads(texto_json)["detections"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as erro:
        raise RuntimeError("A API Gemini retornou uma resposta sem detecções válidas.") from erro

    if not isinstance(deteccoes, list):
        raise RuntimeError("O campo 'detections' retornado pelo Gemini não é uma lista.")

    resultados = []
    for deteccao in deteccoes:
        try:
            texto = deteccao["text"].strip()
            caixa = deteccao["box"]
            x1, y1, x2, y2 = (float(valor) for valor in caixa)
            confianca = float(deteccao["confidence"])
        except (KeyError, TypeError, ValueError) as erro:
            raise RuntimeError("O Gemini retornou uma detecção malformada.") from erro

        if (
            not texto
            or not all(0 <= valor <= 1 for valor in (x1, y1, x2, y2, confianca))
            or x2 <= x1
            or y2 <= y1
        ):
            raise RuntimeError("O Gemini retornou texto, confiança ou caixa inválidos.")

        resultados.append((
            [
                [int(x1 * largura), int(y1 * altura)],
                [int(x2 * largura), int(y1 * altura)],
                [int(x2 * largura), int(y2 * altura)],
                [int(x1 * largura), int(y2 * altura)],
            ],
            texto,
            confianca,
        ))

    return "\n".join(resultado[1] for resultado in resultados), resultados
