import easyocr
import pandas as pd
import os
import re
from Database.init import iniciar_DB
from Database.saving_db import salvar_no_banco
from Governanca.revisao import decidir_validacao
from Governanca.fila_revisao import criar_tabela_revisao, salvar_para_revisao
from tags.dicionario import criar_ddt
from Text_function.extract import extrair, validar_metadados
from Text_function.tratar import tratar_imagens
from Text_function.tratar import detectar_texto


reader = easyocr.Reader(['pt', 'en'], gpu=True)  # Inicializa o OCR uma vez para reutilização.


iniciar_DB()
criar_tabela_revisao()

# Configurar Dicionário de TAGs
dict_tags = criar_ddt()

# hierarquia padrão
hierarquia_sessao = {
    "planta": "Fábrica São Paulo - Unidade 1",
    "area": "Linha de Envasamento 02",
    "ativo_pai": "Conjunto Motobomba MB-04",
    "sub_ativo": "Motor Principal"
}

# Diretório
# A validação da Sprint usa somente as imagens acompanhadas do gabarito.
pasta_imagens = "./placas"
arquivo_gabarito = "./placas/Book.xlsx"

df_gabarito = pd.read_excel(
    arquivo_gabarito,
    sheet_name="Planilha1",
    dtype={"nome_arquivo": str, "tag": str},
)
colunas_obrigatorias = {"nome_arquivo", "tag"}
if not colunas_obrigatorias.issubset(df_gabarito.columns):
    raise ValueError(
        "A planilha deve conter as colunas 'nome_arquivo' e 'tag'. "
        f"Colunas encontradas: {list(df_gabarito.columns)}"
    )

df_gabarito = df_gabarito.rename(columns={"tag": "numero_serie_real"})
df_gabarito["nome_arquivo"] = df_gabarito["nome_arquivo"].map(os.path.basename)
arquivos = [
    os.path.join(pasta_imagens, nome_arquivo)
    for nome_arquivo in df_gabarito["nome_arquivo"]
]
arquivos_ausentes = [caminho for caminho in arquivos if not os.path.isfile(caminho)]
if arquivos_ausentes:
    nomes_ausentes = ", ".join(os.path.basename(caminho) for caminho in arquivos_ausentes)
    raise FileNotFoundError(
        "As imagens do gabarito não foram encontradas em "
        f"'{pasta_imagens}': {nomes_ausentes}"
    )

registros = []  # Armazena resultados de todas as imagens para validação.
registros_aprovados = []  # Mantém o comportamento de persistir apenas registros aprovados.

for caminho in arquivos:  # Processa cada imagem sem alterar o dataset de origem.
    try:  # Isola falha individual e permite continuar o lote.
        imagem_processada, _ = tratar_imagens(caminho)  # Trata a imagem explicitamente antes do OCR.
        texto_bruto, resultados_ocr = detectar_texto(caminho, reader, imagem_processada)  # Envia somente a imagem tratada.
        metadados = extrair(
            texto_bruto,
            dict_tags,
            hierarquia_sessao,
            resultados_ocr,
        )  # Extrai campos do texto ordenado.

        metadados["texto_bruto"] = texto_bruto
        metadados["arquivo_origem"] = caminho

        aprovado_ocr, motivos_ocr, confianca_media = validar_metadados(metadados, resultados_ocr)
        status_gov, motivos_gov, aprovado_gov = decidir_validacao(metadados, confianca_media=confianca_media)

        motivos = list(dict.fromkeys(motivos_ocr + motivos_gov))
        aprovado = aprovado_ocr and aprovado_gov

        metadados["status_validacao"] = "APROVADO" if aprovado else "PENDENTE"
        metadados["motivos_validacao"] = "; ".join(motivos) if motivos else "Nenhum"
        metadados["confianca_ocr"] = confianca_media
        metadados["governanca"] = status_gov

        if not aprovado:
            salvar_para_revisao(metadados, motivos, db_path="forzy_gemeo_digital.db")
            print(f"Registro em revisão: {caminho} | Motivos: {metadados['motivos_validacao']}")
        else:
            registros_aprovados.append(metadados)

        registros.append(metadados)

    except Exception as erro:  # Captura falha operacional com identificação da imagem.
        print(f"Erro ao processar a imagem {caminho}: {erro}")  # Exibe erro sem interromper o lote.

# DataFrame e salvamento
df_resultado = pd.DataFrame(registros)
print("\n--- Amostra dos Dados Extraídos ---")
print(df_resultado.head())

df_extraido = df_resultado[["arquivo_origem", "tag_identificacao"]].rename(
    columns={
        "arquivo_origem": "nome_arquivo",
        "tag_identificacao": "numero_serie_extraido",
    }
)
df_extraido["nome_arquivo"] = df_extraido["nome_arquivo"].map(os.path.basename)

df_validacao = pd.merge(
    df_extraido,
    df_gabarito[["nome_arquivo", "numero_serie_real"]],
    on="nome_arquivo",
    how="left",
    validate="one_to_one",
)

def normalizar_serie(valor):
    if pd.isna(valor):
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(valor).upper())


df_validacao["numero_serie_extraido_normalizado"] = df_validacao["numero_serie_extraido"].map(normalizar_serie)
df_validacao["numero_serie_real_normalizado"] = df_validacao["numero_serie_real"].map(normalizar_serie)
df_validacao["acertou"] = (
    df_validacao["numero_serie_extraido_normalizado"] != ""
) & (
    df_validacao["numero_serie_extraido_normalizado"]
    == df_validacao["numero_serie_real_normalizado"]
)

total_imagens = len(df_validacao)
quantidade_acertos = int(df_validacao["acertou"].sum())
taxa_acertos = (quantidade_acertos / total_imagens * 100) if total_imagens else 0.0
print(
    f"\nAcurácia da TAG: {taxa_acertos:.2f}% "
    f"({quantidade_acertos}/{total_imagens} imagens)"
)

df_validacao.loc[~df_validacao["acertou"]].to_csv(
    "relatorio_de_erros.csv",
    index=False,
    encoding="utf-8-sig",
)

# SQLite
salvar_no_banco(pd.DataFrame(registros_aprovados))