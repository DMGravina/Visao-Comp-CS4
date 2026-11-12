import sqlite3

from Database.init import iniciar_DB


COLUNAS_ATIVO = (
    "planta",
    "area",
    "ativo_pai",
    "sub_ativo",
    "tag_identificacao",
    "potencia",
    "tensao",
    "corrente",
    "rotacao",
    "frequencia",
    "dados_adicionais_json",
)


def persistir_ativo(conn, ativo):
    valores = {
        coluna: ativo.get(coluna, "Não localizado")
        for coluna in COLUNAS_ATIVO
    }
    tag = valores["tag_identificacao"]
    if tag in (None, "", "Não localizado"):
        raise ValueError("Não é possível cadastrar um ativo sem TAG identificável.")

    colunas = ", ".join(COLUNAS_ATIVO)
    placeholders = ", ".join("?" for _ in COLUNAS_ATIVO)
    atualizacoes = ", ".join(
        f"{coluna} = excluded.{coluna}"
        for coluna in COLUNAS_ATIVO
        if coluna != "tag_identificacao"
    )
    conn.execute(
        f"""
        INSERT INTO cadastro_ativos ({colunas})
        VALUES ({placeholders})
        ON CONFLICT(tag_identificacao) DO UPDATE SET {atualizacoes}
        """,
        tuple(valores[coluna] for coluna in COLUNAS_ATIVO),
    )


def salvar_no_banco(df_ativos, db_path="forzy_gemeo_digital.db"):
    if "status_validacao" not in df_ativos.columns:
        raise ValueError(
            "Os registros precisam de status_validacao explícito; "
            "somente registros aprovados podem ser persistidos."
        )

    iniciar_DB(db_path)
    registros_aprovados = df_ativos.loc[
        df_ativos["status_validacao"] == "APROVADO"
    ]
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            for ativo in registros_aprovados.to_dict(orient="records"):
                persistir_ativo(conn, ativo)
    finally:
        conn.close()

    print(
        f"{len(registros_aprovados)} registro(s) aprovado(s) salvo(s) "
        f"no banco de dados '{db_path}'."
    )