import sqlite3

def iniciar_DB(db_path="forzy_gemeo_digital.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cadastro_ativos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            planta TEXT,
            area TEXT,
            ativo_pai TEXT,
            sub_ativo TEXT,
            tag_identificacao TEXT UNIQUE,
            potencia TEXT,
            tensao TEXT,
            corrente TEXT,
            rotacao TEXT,
            frequencia TEXT,
            dados_adicionais_json TEXT,
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()