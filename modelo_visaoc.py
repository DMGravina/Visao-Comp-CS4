import argparse
import os
import re
from pathlib import Path

import cv2
import easyocr
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from tags.dicionario import criar_ddt
from Text_function.extract import extrair
from Text_function.ocr_methods import executar_gemini, executar_tesseract
from Text_function.tratar import detectar_texto, tratar_imagens


ABORDAGENS = ("EasyOCR", "Tesseract", "Gemini API")
QUANTIDADE_ESPERADA = 30


def normalizar_serie(valor):
    if pd.isna(valor):
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(valor).upper())


def salvar_evidencia(caminho, imagem, abordagem, resultados, cv2_module):
    marcada = imagem.copy()
    altura, largura = marcada.shape[:2]

    for caixa, texto, confianca in resultados:
        pontos = [
            [
                max(0, min(largura - 1, int(ponto[0]))),
                max(0, min(altura - 1, int(ponto[1]))),
            ]
            for ponto in caixa
        ]
        cv2_module.polylines(
            marcada,
            [np.array(pontos, dtype=np.int32)],
            True,
            (0, 200, 0),
            2,
        )
        x, y = pontos[0]
        cv2_module.putText(
            marcada,
            f"{texto} ({confianca:.2f})",
            (x, max(20, y - 6)),
            cv2_module.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 255),
            1,
            cv2_module.LINE_AA,
        )

    cv2_module.putText(
        marcada,
        abordagem,
        (8, 22),
        cv2_module.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 0, 0),
        2,
        cv2_module.LINE_AA,
    )
    if not cv2_module.imwrite(str(caminho), marcada):
        raise OSError(f"Não foi possível salvar a evidência em '{caminho}'.")


def carregar_gabarito(arquivo_gabarito):
    caminho = Path(arquivo_gabarito)
    if caminho.suffix.lower() == ".csv":
        df = pd.read_csv(
            caminho,
            sep=None,
            engine="python",
            encoding="utf-8-sig",
            dtype=str,
        )
        df = df.loc[
            :,
            ~df.columns.astype(str).str.match(r"^(Unnamed:|$)"),
        ]
        return df.dropna(axis=1, how="all")
    if caminho.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(
            caminho,
            sheet_name="Planilha1",
            dtype={"nome_arquivo": str, "tag": str},
        )
    raise ValueError("O gabarito deve estar em formato CSV ou Excel (.xlsx).")


def executar_lote(pasta_imagens, arquivo_gabarito, pasta_saida, quantidade_esperada):
    load_dotenv()
    df_gabarito = carregar_gabarito(arquivo_gabarito)
    colunas_obrigatorias = {"nome_arquivo", "tag"}
    if not colunas_obrigatorias.issubset(df_gabarito.columns):
        raise ValueError(
            "A planilha deve conter as colunas 'nome_arquivo' e 'tag'. "
            f"Colunas encontradas: {list(df_gabarito.columns)}"
        )

    df_gabarito = df_gabarito[["nome_arquivo", "tag"]].copy()
    df_gabarito["nome_arquivo"] = df_gabarito["nome_arquivo"].map(os.path.basename)
    df_gabarito = df_gabarito.rename(columns={"tag": "numero_serie_real"})
    if df_gabarito.empty:
        raise ValueError("O gabarito não contém imagens para avaliar.")
    if df_gabarito["nome_arquivo"].duplicated().any():
        raise ValueError("O gabarito contém nomes de imagem duplicados.")
    if df_gabarito["numero_serie_real"].isna().any():
        raise ValueError("O gabarito contém TAGs vazias.")

    if len(df_gabarito) < quantidade_esperada:
        print(
            f"AVISO: benchmark incompleto: {len(df_gabarito)} imagens rotuladas "
            f"disponíveis; esperado {quantidade_esperada}. "
            "A acurácia será calculada sobre as imagens presentes no gabarito."
        )
    elif len(df_gabarito) > quantidade_esperada:
        print(
            f"AVISO: o gabarito contém {len(df_gabarito)} imagens; "
            f"o alvo informado é {quantidade_esperada}. Todas serão processadas."
        )

    arquivos = [
        Path(pasta_imagens) / nome_arquivo
        for nome_arquivo in df_gabarito["nome_arquivo"]
    ]
    ausentes = [str(caminho) for caminho in arquivos if not caminho.is_file()]
    if ausentes:
        raise FileNotFoundError(
            "Imagens do gabarito não encontradas: " + ", ".join(ausentes)
        )

    pasta_saida = Path(pasta_saida)
    pasta_marcacoes = pasta_saida / "marcacoes"
    pasta_marcacoes.mkdir(parents=True, exist_ok=True)
    dict_tags = criar_ddt()
    leitor_easyocr = easyocr.Reader(["pt", "en"], gpu=False)
    try:
        import pytesseract
    except ImportError as erro:
        erro_tesseract = (
            "Instale a dependência Python 'pytesseract' para usar o Tesseract. "
            f"Detalhe: {erro}"
        )
    else:
        try:
            pytesseract.get_tesseract_version()
            erro_tesseract = None
        except pytesseract.TesseractNotFoundError as erro:
            erro_tesseract = (
                "Instale o binário do Tesseract OCR para usar esta abordagem. "
                f"Detalhe: {erro}"
            )

    registros_avaliacao = []

    for caminho in arquivos:
        imagem_original = None
        imagem_processada = None
        try:
            imagem_processada, imagem_original = tratar_imagens(str(caminho))
            altura, largura = imagem_original.shape[:2]

            def executar_tesseract_local():
                if erro_tesseract:
                    raise RuntimeError(erro_tesseract)
                return executar_tesseract(imagem_processada, largura, altura)

            resultados_metodos = {
                "EasyOCR": lambda: detectar_texto(
                    str(caminho), leitor_easyocr, imagem_processada
                ),
                "Tesseract": executar_tesseract_local,
                "Gemini API": lambda: executar_gemini(imagem_original, cv2),
            }
        except Exception as erro:
            resultados_metodos = {
                abordagem: (None, None, f"Falha no pré-processamento: {erro}")
                for abordagem in ABORDAGENS
            }

        for abordagem in ABORDAGENS:
            resultado = resultados_metodos[abordagem]
            if isinstance(resultado, tuple) and len(resultado) == 3:
                texto, deteccoes, erro = resultado
            else:
                try:
                    texto, deteccoes = resultado()
                    erro = ""
                except Exception as excecao:
                    texto, deteccoes, erro = "", [], str(excecao)

            if erro:
                texto, deteccoes = "", []
                print(f"Erro em {abordagem} para {caminho.name}: {erro}")

            serie = extrair(texto or "", dict_tags, {}, deteccoes)["tag_identificacao"]
            serie_real = df_gabarito.loc[
                df_gabarito["nome_arquivo"] == caminho.name,
                "numero_serie_real",
            ].iloc[0]
            acertou = (
                bool(normalizar_serie(serie))
                and normalizar_serie(serie) == normalizar_serie(serie_real)
            )
            registros_avaliacao.append({
                "abordagem": abordagem,
                "nome_arquivo": caminho.name,
                "numero_serie_extraido": serie,
                "numero_serie_real": serie_real,
                "acertou": acertou,
                "status": "ERRO" if erro else "EXECUTADO",
                "erro": erro,
            })

            if imagem_original is not None:
                nome_abordagem = re.sub(r"[^A-Za-z0-9]+", "_", abordagem).strip("_")
                salvar_evidencia(
                    pasta_marcacoes / f"{nome_abordagem}_{caminho.stem}.jpg",
                    imagem_original,
                    abordagem,
                    deteccoes,
                    cv2,
                )

    df_avaliacao = pd.DataFrame(registros_avaliacao)
    df_resumo = pd.DataFrame([
        {
            "abordagem": abordagem,
            "imagens_no_gabarito": len(df_gabarito),
            "imagens_esperadas": quantidade_esperada,
            "dataset_completo": len(df_gabarito) >= quantidade_esperada,
            "acertos": int(
                df_avaliacao.loc[
                    df_avaliacao["abordagem"] == abordagem, "acertou"
                ].sum()
            ),
            "acuracia_percentual": round(
                100
                * df_avaliacao.loc[
                    df_avaliacao["abordagem"] == abordagem, "acertou"
                ].sum()
                / len(df_gabarito),
                2,
            ),
            "erros_execucao": int(
                (
                    df_avaliacao.loc[
                        df_avaliacao["abordagem"] == abordagem, "status"
                    ]
                    == "ERRO"
                ).sum()
            ),
        }
        for abordagem in ABORDAGENS
    ])

    df_avaliacao.to_csv(
        pasta_saida / "resultados_detalhados.csv",
        index=False,
        encoding="utf-8-sig",
    )
    df_resumo.to_csv(
        pasta_saida / "comparativo_acuracia.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print("\n--- Comparativo de OCR ---")
    print(df_resumo.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(
        description="Compara EasyOCR, Tesseract e Gemini em imagens industriais."
    )
    parser.add_argument("--images-dir", default="./placas")
    parser.add_argument("--ground-truth", default="./placas/Book.csv")
    parser.add_argument("--output-dir", default="./evidencias_ocr")
    parser.add_argument("--expected-images", type=int, default=QUANTIDADE_ESPERADA)
    argumentos = parser.parse_args()
    executar_lote(
        argumentos.images_dir,
        argumentos.ground_truth,
        argumentos.output_dir,
        argumentos.expected_images,
    )


if __name__ == "__main__":
    main()
