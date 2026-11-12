from Governanca.revisao import decidir_validacao
from Text_function.extract import extrair, validar_metadados
from tags.dicionario import criar_ddt


def test_decisao_rejeita_ocr_baixo_e_tag_faltante():
    dados = {
        "tag_identificacao": "Não localizado",
        "potencia": "2200 W",
        "tensao": "220 V",
        "corrente": "10 A",
        "rotacao": "Não localizado",
        "frequencia": "Não localizado",
    }

    status, motivos, aprovacao = decidir_validacao(dados, confianca_media=0.20)

    assert status == "PENDENTE"
    assert aprovacao is False
    assert "tag_identificacao" in " ".join(motivos).lower()
    assert "ocr" in " ".join(motivos).lower()


def test_decisao_aprova_dados_consistentes():
    dados = {
        "tag_identificacao": "MB-004",
        "potencia": "7.5 kW",
        "tensao": "220 V",
        "corrente": "32 A",
        "rotacao": "1450 rpm",
        "frequencia": "60 Hz",
    }

    status, motivos, aprovacao = decidir_validacao(dados, confianca_media=0.85)

    assert status == "APROVADO"
    assert aprovacao is True
    assert motivos == []


def test_extrai_serial_rotulado_com_barras():
    resultados_ocr = [([], "Serial No. C132394/8020035999/0010", 0.91)]

    dados = extrair(
        "Serial No. C132394/8020035999/0010",
        criar_ddt(),
        {},
        resultados_ocr,
    )

    assert dados["tag_identificacao"] == "C132394/8020035999/0010"
    aprovado, motivos, confianca = validar_metadados(dados, resultados_ocr)
    assert aprovado is True
    assert motivos == []
    assert confianca == 0.91


def test_nao_aceita_letra_isolada_como_serial():
    resultados_ocr = [([], "SIEMENS", 0.95), ([], "S", 0.95)]

    dados = extrair("SIEMENS\nS", criar_ddt(), {}, resultados_ocr)

    assert dados["tag_identificacao"] == "Não localizado"


def test_extrai_tensao_com_formato_numerico_e_corrige_caracteres_ambiguos():
    dados = extrair("SERIAL C132394 22OV", criar_ddt(), {})

    assert dados["tensao"] == "220 V"


def test_nao_extrai_grandezas_sem_unidade_volt():
    dados = extrair("220 Hz\n2.2 kW", criar_ddt(), {})

    assert dados["tensao"] == "Não localizado"
