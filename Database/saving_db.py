import sqlite3

def salvar_no_banco(df_ativos, db_path="forzy_gemeo_digital.db"):
    colunas_permitidas = ["planta", "area", "ativo_pai", "sub_ativo", "tag_identificacao", "potencia", "tensao", "corrente", "rotacao", "frequencia", "dados_adicionais_json"]  # Restringe o contrato da tabela.
    registros_validos = df_ativos[df_ativos["status_validacao"] == "APROVADO"].copy() if "status_validacao" in df_ativos.columns else df_ativos.copy()  # Evita persistir pendências.
    registros_validos = registros_validos.reindex(columns=colunas_permitidas, fill_value="Não localizado")  # Remove campos de controle.
    conn = sqlite3.connect(db_path)  # Abre conexão somente durante a gravação.
    registros_validos.to_sql("_ativos_staging", conn, if_exists="replace", index=False)  # Usa tabela temporária para executar upsert sem destruir o esquema principal.
    conn.execute("INSERT OR REPLACE INTO cadastro_ativos (planta, area, ativo_pai, sub_ativo, tag_identificacao, potencia, tensao, corrente, rotacao, frequencia, dados_adicionais_json) SELECT planta, area, ativo_pai, sub_ativo, tag_identificacao, potencia, tensao, corrente, rotacao, frequencia, dados_adicionais_json FROM _ativos_staging")  # Substitui somente a TAG correspondente e mantém o lote resiliente.
    conn.execute("DROP TABLE _ativos_staging")  # Remove a tabela temporária após o upsert.
    conn.commit()  # Confirma a transação explicitamente antes de fechar.
    conn.close()  # Libera o arquivo SQLite após a gravação.
    print(f"Registros aprovados salvos no banco de dados '{db_path}'.")  # Informa a política de persistência seletiva.