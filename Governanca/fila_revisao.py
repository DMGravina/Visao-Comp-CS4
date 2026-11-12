import ast
import json
import sqlite3

from Database.init import iniciar_DB
from Database.saving_db import persistir_ativo


def _carregar_dados_extraidos(valor, revisao_id):
    try:
        dados_extraidos = json.loads(valor)
    except (json.JSONDecodeError, TypeError):
        try:
            dados_extraidos = ast.literal_eval(valor)
        except (ValueError, SyntaxError, TypeError) as erro:
            raise ValueError(
                f"Os dados da revisão {revisao_id} não estão em formato válido."
            ) from erro
    if not isinstance(dados_extraidos, dict):
        raise ValueError(
            f"Os dados da revisão {revisao_id} não estão em formato válido."
        )
    return dados_extraidos


def criar_tabela_revisao(db_path="forzy_gemeo_digital.db"):
    iniciar_DB(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
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
    finally:
        conn.close()


def salvar_para_revisao(metadados, motivo, db_path="forzy_gemeo_digital.db"):
    criar_tabela_revisao(db_path)
    motivos = [motivo] if isinstance(motivo, str) else list(motivo)
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO revisao_ativos (
                    arquivo_origem,
                    tag_identificacao,
                    status,
                    motivos,
                    confianca_ocr,
                    dados_brutos,
                    dados_extraidos
                ) VALUES (?, ?, 'PENDENTE', ?, ?, ?, ?)
                """,
                (
                    metadados.get("arquivo_origem", ""),
                    metadados.get("tag_identificacao", "Não localizado"),
                    "; ".join(str(item) for item in motivos),
                    metadados.get("confianca_ocr", 0.0),
                    metadados.get("texto_bruto", ""),
                    json.dumps(metadados, ensure_ascii=False),
                ),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def listar_pendencias(db_path="forzy_gemeo_digital.db"):
    criar_tabela_revisao(db_path)
    conn = sqlite3.connect(db_path)
    try:
        linhas = conn.execute(
            """
            SELECT id, arquivo_origem, tag_identificacao, motivos,
                   confianca_ocr, dados_brutos, dados_extraidos
            FROM revisao_ativos
            WHERE status = 'PENDENTE'
            ORDER BY id
            """
        ).fetchall()
    finally:
        conn.close()

    pendencias = []
    for linha in linhas:
        dados_extraidos = _carregar_dados_extraidos(linha[6], linha[0])
        pendencias.append({
            "id": linha[0],
            "arquivo_origem": linha[1],
            "tag_identificacao": linha[2],
            "motivos": linha[3],
            "confianca_ocr": linha[4],
            "dados_brutos": linha[5],
            "dados_extraidos": dados_extraidos,
        })
    return pendencias


def aprovar_revisao(revisao_id, db_path="forzy_gemeo_digital.db"):
    criar_tabela_revisao(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        linha = conn.execute(
            """
            SELECT status, dados_extraidos
            FROM revisao_ativos
            WHERE id = ?
            """,
            (revisao_id,),
        ).fetchone()
        if linha is None:
            raise ValueError(f"Revisão {revisao_id} não encontrada.")
        if linha[0] != "PENDENTE":
            raise ValueError(
                f"A revisão {revisao_id} não está pendente (status: {linha[0]})."
            )

        dados_extraidos = _carregar_dados_extraidos(linha[1], revisao_id)

        persistir_ativo(conn, dados_extraidos)
        conn.execute(
            "UPDATE revisao_ativos SET status = 'APROVADO' WHERE id = ?",
            (revisao_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rejeitar_revisao(revisao_id, db_path="forzy_gemeo_digital.db"):
    criar_tabela_revisao(db_path)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE revisao_ativos
            SET status = 'REJEITADO'
            WHERE id = ? AND status = 'PENDENTE'
            """,
            (revisao_id,),
        )
        if cursor.rowcount == 0:
            existe = conn.execute(
                "SELECT status FROM revisao_ativos WHERE id = ?",
                (revisao_id,),
            ).fetchone()
            if existe is None:
                raise ValueError(f"Revisão {revisao_id} não encontrada.")
            raise ValueError(
                f"A revisão {revisao_id} não está pendente (status: {existe[0]})."
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
