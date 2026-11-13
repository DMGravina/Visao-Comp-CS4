import argparse
import json
import os
import re
import unicodedata
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from Database.init import iniciar_DB
from Governanca.fila_revisao import (
    aprovar_revisao,
    listar_pendencias,
    rejeitar_revisao,
    salvar_para_revisao,
)
from Governanca.revisao import decidir_validacao
from tags.dicionario import criar_ddt
from Text_function.extract import calcular_confianca_serial, extrair
from Text_function.ocr_methods import executar_gemini, executar_tesseract
from Text_function.tratar import detectar_texto, tratar_imagens


ABORDAGENS = ("EasyOCR", "Tesseract", "Gemini API")
QUANTIDADE_ESPERADA = 30


def _criar_leitor_easyocr():
    try:
        import easyocr
    except ImportError as erro:
        raise RuntimeError(
            "Instale a dependência Python 'easyocr' para usar esta abordagem."
        ) from erro
    return easyocr.Reader(["pt", "en"], gpu=False)


def normalizar_serie(valor):
    if pd.isna(valor):
        return ""
    sem_acentos = unicodedata.normalize("NFKD", str(valor))
    texto_ascii = sem_acentos.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Z0-9]", "", texto_ascii.upper())


def distancia_edicao(primeira, segunda):
    if len(primeira) < len(segunda):
        primeira, segunda = segunda, primeira
    linha_anterior = list(range(len(segunda) + 1))
    for indice, caractere in enumerate(primeira, start=1):
        linha_atual = [indice]
        for coluna, outro_caractere in enumerate(segunda, start=1):
            custo = 0 if caractere == outro_caractere else 1
            linha_atual.append(min(
                linha_atual[coluna - 1] + 1,
                linha_anterior[coluna] + 1,
                linha_anterior[coluna - 1] + custo,
            ))
        linha_anterior = linha_atual
    return linha_anterior[-1]


def calcular_similaridade(primeira, segunda):
    primeira_normalizada = normalizar_serie(primeira)
    segunda_normalizada = normalizar_serie(segunda)
    if "NAOLOCALIZADO" in (primeira_normalizada, segunda_normalizada):
        return 0.0
    maior_comprimento = max(len(primeira_normalizada), len(segunda_normalizada))
    if maior_comprimento == 0:
        return 0.0
    distancia = distancia_edicao(primeira_normalizada, segunda_normalizada)
    return round(100 * (1 - distancia / maior_comprimento), 2)


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


def executar_lote(
    pasta_imagens,
    arquivo_gabarito,
    pasta_saida,
    quantidade_esperada,
    deslocamento_lote=0,
    tamanho_lote=None,
    habilitar_gemini=False,
):
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
            f"o alvo informado é {quantidade_esperada}."
        )

    if deslocamento_lote < 0:
        raise ValueError("O deslocamento do lote não pode ser negativo.")
    if tamanho_lote is not None and tamanho_lote <= 0:
        raise ValueError("O tamanho do lote deve ser maior que zero.")
    if deslocamento_lote >= len(df_gabarito):
        raise ValueError("O deslocamento do lote está além do gabarito.")

    df_lote = df_gabarito.iloc[deslocamento_lote:]
    if tamanho_lote is not None:
        df_lote = df_lote.iloc[:tamanho_lote]

    arquivos = [
        Path(pasta_imagens) / nome_arquivo
        for nome_arquivo in df_lote["nome_arquivo"]
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
    try:
        leitor_easyocr = _criar_leitor_easyocr()
        erro_easyocr = None
    except Exception as erro:
        leitor_easyocr = None
        erro_easyocr = f"EasyOCR indisponível: {erro}"

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

    if not habilitar_gemini:
        erro_gemini = (
            "Execução desabilitada; use --enable-gemini somente após confirmar "
            "a autorização para enviar este dataset à API."
        )
    elif not os.environ.get("GEMINI_API_KEY"):
        erro_gemini = (
            "GEMINI_API_KEY não configurada; nenhuma imagem foi enviada."
        )
    else:
        erro_gemini = None

    registros_avaliacao = []

    for caminho, (_, linha_gabarito) in zip(arquivos, df_lote.iterrows()):
        imagem_original = None
        imagem_processada = None
        try:
            imagem_processada, imagem_original = tratar_imagens(str(caminho))
            altura, largura = imagem_original.shape[:2]
        except Exception as erro:
            imagem_processada = None
            imagem_original = None
            erro_preprocessamento = f"Falha no pré-processamento: {erro}"
        else:
            erro_preprocessamento = None

        metodos = {
            "EasyOCR": (
                lambda: detectar_texto(
                    str(caminho), leitor_easyocr, imagem_processada
                )
            ),
            "Tesseract": (
                lambda: executar_tesseract(
                    imagem_processada, largura, altura
                )
            ),
            "Gemini API": lambda: executar_gemini(imagem_original, cv2),
        }
        erros_configuracao = {
            "EasyOCR": erro_easyocr,
            "Tesseract": erro_tesseract,
            "Gemini API": erro_gemini,
        }

        for abordagem in ABORDAGENS:
            texto = ""
            deteccoes = []
            erro = ""
            status = "EXECUTADO"

            if abordagem == "Gemini API" and erro_gemini:
                status = "NAO_EXECUTADO"
                erro = erro_gemini
            elif erro_preprocessamento:
                status = "ERRO_EXECUCAO"
                erro = erro_preprocessamento
            elif erros_configuracao[abordagem]:
                status = "ERRO_EXECUCAO"
                erro = erros_configuracao[abordagem]
            else:
                try:
                    texto, deteccoes = metodos[abordagem]()
                except Exception as excecao:
                    status = "ERRO_EXECUCAO"
                    erro = str(excecao)

            serie = extrair(
                texto or "", dict_tags, {}, deteccoes
            )["tag_identificacao"] if status == "EXECUTADO" else "Não localizado"
            serie_real = linha_gabarito["numero_serie_real"]
            serie_normalizada = normalizar_serie(serie)
            serie_real_normalizada = normalizar_serie(serie_real)
            acertou = (
                status == "EXECUTADO"
                and serie_normalizada not in ("", "NAOLOCALIZADO")
                and serie_real_normalizada not in ("", "NAOLOCALIZADO")
                and serie_normalizada == serie_real_normalizada
            )
            if status == "ERRO_EXECUCAO":
                print(f"Erro em {abordagem} para {caminho.name}: {erro}")
            similaridade = calcular_similaridade(serie, serie_real)
            distancia = None
            if (
                serie_normalizada not in ("", "NAOLOCALIZADO")
                and serie_real_normalizada not in ("", "NAOLOCALIZADO")
            ):
                distancia = distancia_edicao(
                    serie_normalizada, serie_real_normalizada
                )
            registros_avaliacao.append({
                "abordagem": abordagem,
                "nome_arquivo": caminho.name,
                "numero_serie_extraido": serie,
                "numero_serie_real": serie_real,
                "acertou": acertou,
                "classificacao_resultado": (
                    "ERRO_EXECUCAO"
                    if status == "ERRO_EXECUCAO"
                    else "NAO_EXECUTADO"
                    if status == "NAO_EXECUTADO"
                    else "ACERTO_EXATO"
                    if acertou
                    else "ERRO_OCR"
                ),
                "distancia_edicao": distancia,
                "similaridade_percentual": similaridade,
                "status": status,
                "erro": erro,
            })

            if status == "EXECUTADO":
                nome_abordagem = re.sub(r"[^A-Za-z0-9]+", "_", abordagem).strip("_")
                salvar_evidencia(
                    pasta_marcacoes / f"{nome_abordagem}_{caminho.stem}.jpg",
                    imagem_original,
                    abordagem,
                    deteccoes,
                    cv2,
                )

    df_avaliacao = pd.DataFrame(registros_avaliacao)
    resumos = []
    for abordagem in ABORDAGENS:
        avaliacao_abordagem = df_avaliacao[
            df_avaliacao["abordagem"] == abordagem
        ]
        executadas = avaliacao_abordagem[
            avaliacao_abordagem["status"] == "EXECUTADO"
        ]
        acertos = int(avaliacao_abordagem["acertou"].sum())
        resumos.append({
            "abordagem": abordagem,
            "imagens_no_gabarito": len(df_gabarito),
            "imagens_no_lote": len(df_lote),
            "imagens_processadas": len(executadas),
            "imagens_esperadas": quantidade_esperada,
            "dataset_completo": len(df_gabarito) >= quantidade_esperada,
            "inicio_lote": deslocamento_lote,
            "acertos_exatos": acertos,
            "similaridade_media_percentual": (
                round(executadas["similaridade_percentual"].mean(), 2)
                if not executadas.empty
                else None
            ),
            "acuracia_percentual": round(100 * acertos / len(df_lote), 2),
            "acuracia_sobre_processadas_percentual": (
                round(100 * acertos / len(executadas), 2)
                if not executadas.empty
                else None
            ),
            "erros_execucao": int(
                (avaliacao_abordagem["status"] == "ERRO_EXECUCAO").sum()
            ),
            "nao_executadas": int(
                (avaliacao_abordagem["status"] == "NAO_EXECUTADO").sum()
            ),
        })
    df_resumo = pd.DataFrame(resumos)

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


def _preparar_ocr(abordagem):
    if abordagem == "EasyOCR":
        return _criar_leitor_easyocr()
    if abordagem == "Tesseract":
        try:
            import pytesseract
        except ImportError as erro:
            raise RuntimeError(
                "Instale a dependência Python 'pytesseract' para usar o Tesseract."
            ) from erro
        try:
            pytesseract.get_tesseract_version()
        except pytesseract.TesseractNotFoundError as erro:
            raise RuntimeError(
                "Instale o binário do Tesseract OCR e adicione-o ao PATH."
            ) from erro
    return None


def executar_ingestao(imagens, abordagem, db_path="forzy_gemeo_digital.db"):
    load_dotenv()
    caminhos = [Path(imagem) for imagem in imagens]
    if not caminhos:
        raise ValueError("Informe ao menos uma imagem para cadastrar.")
    ausentes = [str(caminho) for caminho in caminhos if not caminho.is_file()]
    if ausentes:
        raise FileNotFoundError(
            "Imagens não encontradas: " + ", ".join(ausentes)
        )

    leitor_ocr = _preparar_ocr(abordagem)
    iniciar_DB(db_path)
    registros_criados = []
    dicionario_tags = criar_ddt()

    for caminho in caminhos:
        try:
            imagem_processada, imagem_original = tratar_imagens(str(caminho))
            if abordagem == "EasyOCR":
                texto, deteccoes = detectar_texto(
                    str(caminho), leitor_ocr, imagem_processada
                )
            elif abordagem == "Tesseract":
                altura, largura = imagem_original.shape[:2]
                texto, deteccoes = executar_tesseract(
                    imagem_processada, largura, altura
                )
            else:
                texto, deteccoes = executar_gemini(imagem_original, cv2)
            erro_processamento = ""
        except Exception as erro:
            texto = ""
            deteccoes = []
            erro_processamento = str(erro)
            print(f"Erro em {abordagem} para {caminho.name}: {erro_processamento}")

        dados_extraidos = extrair(
            texto, dicionario_tags, {}, deteccoes
        )
        confianca = calcular_confianca_serial(
            dados_extraidos["tag_identificacao"], deteccoes
        )
        _, motivos, _ = decidir_validacao(dados_extraidos, confianca)
        if erro_processamento:
            motivos.append(f"Falha no processamento OCR: {erro_processamento}")
        motivos.append("Aprovação humana obrigatória antes do cadastro")
        metadados = {
            **dados_extraidos,
            "arquivo_origem": str(caminho),
            "texto_bruto": texto,
            "confianca_ocr": confianca,
            "metodo_ocr": abordagem,
            "status_validacao": "PENDENTE",
            "motivos_validacao": motivos,
        }
        revisao_id = salvar_para_revisao(metadados, motivos, db_path)
        registros_criados.append(revisao_id)
        print(
            f"Imagem '{caminho.name}' enviada para revisão humana "
            f"(ID {revisao_id}; TAG: {dados_extraidos['tag_identificacao']})."
        )

    return registros_criados


def executar_revisao(db_path="forzy_gemeo_digital.db"):
    pendencias = listar_pendencias(db_path)
    if not pendencias:
        print("Não há registros pendentes de revisão.")
        return

    for pendencia in pendencias:
        print(f"\nRevisão {pendencia['id']} — {pendencia['arquivo_origem']}")
        print(f"TAG detectada: {pendencia['tag_identificacao']}")
        print(f"Confiança OCR: {pendencia['confianca_ocr']:.2f}")
        print(f"Motivos: {pendencia['motivos']}")
        print("Dados extraídos:")
        print(json.dumps(
            pendencia["dados_extraidos"],
            ensure_ascii=False,
            indent=2,
        ))
        decisao = input("[a]provar, [r]ejeitar ou [s]altar? ").strip().lower()
        if decisao == "a":
            aprovar_revisao(pendencia["id"], db_path)
            print("Registro aprovado e salvo no cadastro de ativos.")
        elif decisao == "r":
            rejeitar_revisao(pendencia["id"], db_path)
            print("Registro rejeitado.")
        elif decisao != "s":
            print("Opção inválida; o registro permanece pendente.")


def main():
    parser = argparse.ArgumentParser(
        description="Avalia OCR e gerencia o cadastro de placas industriais."
    )
    parser.add_argument(
        "--mode",
        choices=("benchmark", "ingest", "review"),
        default="benchmark",
        help="benchmark compara OCR; ingest encaminha imagens à revisão; "
        "review processa a fila humana.",
    )
    parser.add_argument("--images-dir", default="./placas")
    parser.add_argument("--ground-truth", default="./placas/Book.csv")
    parser.add_argument("--output-dir", default="./evidencias_ocr")
    parser.add_argument("--expected-images", type=int, default=QUANTIDADE_ESPERADA)
    parser.add_argument(
        "--batch-offset",
        type=int,
        default=0,
        help="Índice inicial do lote no gabarito (modo benchmark).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Quantidade de imagens no lote (modo benchmark).",
    )
    parser.add_argument(
        "--enable-gemini",
        action="store_true",
        help="Autoriza explicitamente o envio do dataset à API Gemini "
        "(exige GEMINI_API_KEY).",
    )
    parser.add_argument(
        "--images",
        nargs="+",
        help="Caminhos das imagens (obrigatório no modo ingest).",
    )
    parser.add_argument(
        "--ocr-method",
        choices=ABORDAGENS,
        default="EasyOCR",
        help="Motor usado no modo ingest.",
    )
    parser.add_argument("--db-path", default="forzy_gemeo_digital.db")
    argumentos = parser.parse_args()
    if argumentos.mode == "benchmark":
        executar_lote(
            argumentos.images_dir,
            argumentos.ground_truth,
            argumentos.output_dir,
            argumentos.expected_images,
            argumentos.batch_offset,
            argumentos.batch_size,
            argumentos.enable_gemini,
        )
    elif argumentos.mode == "ingest":
        if not argumentos.images:
            parser.error("--images é obrigatório no modo ingest.")
        executar_ingestao(
            argumentos.images,
            argumentos.ocr_method,
            argumentos.db_path,
        )
    else:
        executar_revisao(argumentos.db_path)


if __name__ == "__main__":
    main()
