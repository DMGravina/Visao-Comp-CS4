import sqlite3


def criar_tabela_revisao(db_path="forzy_gemeo_digital.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS revisao_ativos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arquivo_origem TEXT,
            tag_identificacao TEXT,
            status TEXT,
            motivos TEXT,
            confianca_ocr REAL,
            dados_brutos TEXT,
            dados_extraidos TEXT,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def salvar_para_revisao(metadados, motivo, db_path="forzy_gemeo_digital.db"):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO revisao_ativos (
            arquivo_origem,
            tag_identificacao,
            status,
            motivos,
            confianca_ocr,
            dados_brutos,
            dados_extraidos
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metadados.get("arquivo_origem", ""),
            metadados.get("tag_identificacao", "Não localizado"),
            "PENDENTE",
            "; ".join(motivo),
            metadados.get("confianca_ocr", 0.0),
            str(metadados.get("texto_bruto", "")),
            str(metadados),
        ),
    )
    conn.commit()
    conn.close()


def aprovar_revisao(revisao_id, db_path="forzy_gemeo_digital.db"):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE revisao_ativos SET status = 'APROVADO' WHERE id = ?",
        (revisao_id,),
    )
    conn.commit()
    conn.close()


def rejeitar_revisao(revisao_id, db_path="forzy_gemeo_digital.db"):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE revisao_ativos SET status = 'REJEITADO' WHERE id = ?",
        (revisao_id,),
    )
    conn.commit()
    conn.close()
