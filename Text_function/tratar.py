import cv2
import numpy as np


def tratar_imagens(caminho_imagem):
    img = cv2.imread(caminho_imagem)
    if img is None:
        raise FileNotFoundError(f"ERRO: A imagem '{caminho_imagem}' não foi encontrada.")
    altura, largura = img.shape[:2]
    img_redimensionada = cv2.resize(
        img,
        (largura * 2, altura * 2),
        interpolation=cv2.INTER_CUBIC,
    )
    cinza = cv2.cvtColor(img_redimensionada, cv2.COLOR_BGR2GRAY)
    suave = cv2.bilateralFilter(cinza, d=9, sigmaColor=75, sigmaSpace=75)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    contraste = clahe.apply(suave)
    thresh = cv2.adaptiveThreshold(
        contraste,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        2,
    )
    kernel = np.ones((2, 2), np.uint8)
    processada = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    return processada, img
  

  
def detectar_texto(caminho_imagem, reader, imagem_processada=None):  # Aceita imagem já tratada para tornar a ordem explícita.
    if imagem_processada is None:  # Mantém compatibilidade com chamadas antigas que fornecem apenas o caminho.
        imagem_processada, _ = tratar_imagens(caminho_imagem)  # Garante o pré-processamento antes do OCR.

    imagem_original = cv2.imread(caminho_imagem)
    leituras = [(reader.readtext(imagem_processada, detail=1), 0.5)]
    if imagem_original is not None:
        leituras.append((reader.readtext(imagem_original, detail=1), 1.0))

    melhores_resultados = {}
    for leitura, escala in leituras:
        for resultado in leitura:
            caixa, texto, confianca = resultado
            caixa_original = [
                [coordenada * escala for coordenada in ponto]
                for ponto in caixa
            ]
            normalizado = (caixa_original, texto, confianca)
            chave = texto.strip().upper()
            if chave not in melhores_resultados or confianca > melhores_resultados[chave][2]:
                melhores_resultados[chave] = normalizado

    resultados = sorted(
        melhores_resultados.values(),
        key=lambda resultado: (
            min(ponto[1] for ponto in resultado[0]),
            min(ponto[0] for ponto in resultado[0]),
        ),
    )

    txt_consolidado = "\n".join(res[1] for res in resultados)  # Preserva separação de linhas no texto consolidado.

    return txt_consolidado, resultados  # Devolve caixas e confiança para validação posterior.