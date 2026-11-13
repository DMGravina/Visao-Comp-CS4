import csv
import sqlite3
import sys
from types import SimpleNamespace

import pytest

import modelo_visaoc
from Database.init import iniciar_DB
from Database.saving_db import salvar_no_banco
from Governanca.fila_revisao import (
    aprovar_revisao,
    listar_pendencias,
    rejeitar_revisao,
    salvar_para_revisao,
)


def _metadados(tag="C132394/8020035999/0010"):
    return {
        "planta": "Planta Geral",
        "area": "Setor Não Especificado",
        "ativo_pai": "Sistema Principal",
        "sub_ativo": "Equipamento",
        "tag_identificacao": tag,
        "tensao": "220 V",
        "arquivo_origem": "placa.jpg",
        "texto_bruto": f"Serial No. {tag}",
        "confianca_ocr": 0.91,
    }


def test_ingestao_encaminha_para_revisao_sem_gravar_ativo(tmp_path, monkeypatch):
    imagem = tmp_path / "placa.jpg"
    imagem.touch()
    banco = tmp_path / "ativos.db"
    leitura = "Serial No. C132394/8020035999/0010"

    monkeypatch.setattr(modelo_visaoc, "_preparar_ocr", lambda abordagem: object())
    monkeypatch.setattr(
        modelo_visaoc,
        "tratar_imagens",
        lambda caminho: (object(), object()),
    )
    monkeypatch.setattr(
        modelo_visaoc,
        "detectar_texto",
        lambda caminho, leitor, processada: (
            leitura,
            [([], leitura, 0.91)],
        ),
    )

    ids = modelo_visaoc.executar_ingestao(
        [str(imagem)], "EasyOCR", str(banco)
    )

    assert len(ids) == 1
    pendencias = listar_pendencias(str(banco))
    assert pendencias[0]["id"] == ids[0]
    assert "Aprovação humana obrigatória" in pendencias[0]["motivos"]

    conn = sqlite3.connect(banco)
    try:
        assert conn.execute("SELECT COUNT(*) FROM cadastro_ativos").fetchone()[0] == 0
    finally:
        conn.close()


def test_aprovacao_persiste_ativo_e_rejeicao_nao(tmp_path):
    banco = str(tmp_path / "ativos.db")
    iniciar_DB(banco)
    aprovado_id = salvar_para_revisao(
        _metadados(), ["Aprovação humana obrigatória"], banco
    )
    rejeitado_id = salvar_para_revisao(
        _metadados("SERIAL-REJEITADO-001"),
        ["Aprovação humana obrigatória"],
        banco,
    )

    aprovar_revisao(aprovado_id, banco)
    rejeitar_revisao(rejeitado_id, banco)

    conn = sqlite3.connect(banco)
    try:
        ativos = conn.execute(
            "SELECT tag_identificacao FROM cadastro_ativos"
        ).fetchall()
        estados = conn.execute(
            "SELECT status FROM revisao_ativos ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    assert ativos == [("C132394/8020035999/0010",)]
    assert estados == [("APROVADO",), ("REJEITADO",)]


def test_aprovacao_sem_tag_nao_muda_status_da_revisao(tmp_path):
    banco = str(tmp_path / "ativos.db")
    revisar_id = salvar_para_revisao(
        _metadados("Não localizado"), ["TAG inválida"], banco
    )

    with pytest.raises(ValueError, match="sem TAG"):
        aprovar_revisao(revisar_id, banco)

    pendencias = listar_pendencias(banco)
    assert [item["id"] for item in pendencias] == [revisar_id]


def test_fila_le_dados_json_e_formato_legacy(tmp_path):
    banco = str(tmp_path / "ativos.db")
    revisar_id = salvar_para_revisao(_metadados(), ["revisar"], banco)
    conn = sqlite3.connect(banco)
    try:
        conn.execute(
            "UPDATE revisao_ativos SET dados_extraidos = ? WHERE id = ?",
            (str(_metadados()), revisar_id),
        )
        conn.commit()
    finally:
        conn.close()

    pendencias = listar_pendencias(banco)

    assert pendencias[0]["dados_extraidos"]["tag_identificacao"] == (
        "C132394/8020035999/0010"
    )


def test_salvar_no_banco_exige_status_de_aprovacao(tmp_path):
    import pandas as pd

    with pytest.raises(ValueError, match="status_validacao explícito"):
        salvar_no_banco(
            pd.DataFrame([_metadados()]),
            str(tmp_path / "ativos.db"),
        )


def test_metricas_de_tag_medem_erros_sem_chamar_erro_de_acerto():
    assert modelo_visaoc.distancia_edicao("ABC123", "ABC124") == 1
    assert modelo_visaoc.calcular_similaridade("ABC-123", "ABC-124") == 83.33
    assert modelo_visaoc.calcular_similaridade("Não localizado", "ABC123") == 0


def test_benchmark_processa_lote_e_exporta_metricas_aproximadas(
    tmp_path, monkeypatch
):
    imagens = tmp_path / "imagens"
    imagens.mkdir()
    (imagens / "a.jpg").touch()
    (imagens / "b.jpg").touch()
    gabarito = tmp_path / "gabarito.csv"
    with gabarito.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow(["nome_arquivo", "tag"])
        escritor.writerow(["a.jpg", "ABC123"])
        escritor.writerow(["b.jpg", "ABC124"])

    imagem_original = SimpleNamespace(shape=(100, 200, 3))
    imagem_processada = SimpleNamespace(shape=(50, 100))
    monkeypatch.setattr(
        modelo_visaoc, "_criar_leitor_easyocr", lambda: object()
    )
    monkeypatch.setitem(
        sys.modules,
        "pytesseract",
        SimpleNamespace(
            get_tesseract_version=lambda: "5.3",
            TesseractNotFoundError=RuntimeError,
        ),
    )
    monkeypatch.setattr(
        modelo_visaoc,
        "tratar_imagens",
        lambda caminho: (imagem_processada, imagem_original),
    )
    monkeypatch.setattr(
        modelo_visaoc,
        "detectar_texto",
        lambda caminho, leitor, processada: (
            "Serial No. ABC124",
            [],
        ),
    )
    monkeypatch.setattr(
        modelo_visaoc,
        "executar_tesseract",
        lambda processada, largura, altura: ("Serial No. ABC124", []),
    )
    monkeypatch.setattr(
        modelo_visaoc,
        "executar_gemini",
        lambda original, cv2_module: ("Serial No. ABC124", []),
    )
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key")
    monkeypatch.setattr(modelo_visaoc, "salvar_evidencia", lambda *args: None)
    saida = tmp_path / "saida"

    modelo_visaoc.executar_lote(
        str(imagens),
        str(gabarito),
        str(saida),
        quantidade_esperada=2,
        deslocamento_lote=0,
        tamanho_lote=2,
        habilitar_gemini=True,
    )

    with (saida / "resultados_detalhados.csv").open(
        encoding="utf-8-sig", newline=""
    ) as arquivo:
        resultados = list(csv.DictReader(arquivo))
    with (saida / "comparativo_acuracia.csv").open(
        encoding="utf-8-sig", newline=""
    ) as arquivo:
        resumo = list(csv.DictReader(arquivo))

    assert len(resultados) == 6
    assert {linha["nome_arquivo"] for linha in resultados} == {"a.jpg", "b.jpg"}
    assert {
        linha["distancia_edicao"]
        for linha in resultados
        if linha["status"] == "EXECUTADO"
    } == {"0", "1"}
    assert {
        linha["classificacao_resultado"]
        for linha in resultados
        if linha["nome_arquivo"] == "a.jpg"
    } == {"ERRO_OCR"}
    assert {
        linha["similaridade_percentual"] for linha in resultados
    } == {"83.33", "100.0"}
    assert {linha["imagens_processadas"] for linha in resumo} == {"2"}
    assert {linha["acertos_exatos"] for linha in resumo} == {"1"}
    assert {linha["acuracia_percentual"] for linha in resumo} == {"50.0"}


def test_benchmark_isola_falha_de_motor_e_nao_envia_gemini_sem_opt_in(
    tmp_path, monkeypatch
):
    imagens = tmp_path / "imagens"
    imagens.mkdir()
    (imagens / "placa.jpg").touch()
    gabarito = tmp_path / "gabarito.csv"
    gabarito.write_text(
        "nome_arquivo;tag\nplaca.jpg;ABC123\n", encoding="utf-8"
    )
    imagem_original = SimpleNamespace(shape=(100, 200, 3))
    imagem_processada = SimpleNamespace(shape=(50, 100))

    def falhar_easyocr():
        raise RuntimeError("dependência indisponível")

    monkeypatch.setattr(modelo_visaoc, "_criar_leitor_easyocr", falhar_easyocr)
    monkeypatch.setitem(
        sys.modules,
        "pytesseract",
        SimpleNamespace(
            get_tesseract_version=lambda: "5.3",
            TesseractNotFoundError=RuntimeError,
        ),
    )
    monkeypatch.setattr(
        modelo_visaoc,
        "tratar_imagens",
        lambda caminho: (imagem_processada, imagem_original),
    )
    monkeypatch.setattr(
        modelo_visaoc,
        "executar_tesseract",
        lambda processada, largura, altura: ("Serial No. ABC123", []),
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(
        modelo_visaoc,
        "executar_gemini",
        lambda *args: _falha_gemini_nao_autorizado(),
    )
    monkeypatch.setattr(modelo_visaoc, "salvar_evidencia", lambda *args: None)
    saida = tmp_path / "saida"

    modelo_visaoc.executar_lote(
        str(imagens),
        str(gabarito),
        str(saida),
        quantidade_esperada=1,
    )

    with (saida / "resultados_detalhados.csv").open(
        encoding="utf-8-sig", newline=""
    ) as arquivo:
        resultados = {
            linha["abordagem"]: linha for linha in csv.DictReader(arquivo)
        }
    with (saida / "comparativo_acuracia.csv").open(
        encoding="utf-8-sig", newline=""
    ) as arquivo:
        resumo = {
            linha["abordagem"]: linha for linha in csv.DictReader(arquivo)
        }

    assert resultados["EasyOCR"]["status"] == "ERRO_EXECUCAO"
    assert resultados["EasyOCR"]["classificacao_resultado"] == "ERRO_EXECUCAO"
    assert resultados["Tesseract"]["status"] == "EXECUTADO"
    assert resultados["Tesseract"]["classificacao_resultado"] == "ACERTO_EXATO"
    assert resultados["Gemini API"]["status"] == "NAO_EXECUTADO"
    assert resumo["EasyOCR"]["erros_execucao"] == "1"
    assert resumo["Tesseract"]["imagens_processadas"] == "1"
    assert resumo["Gemini API"]["nao_executadas"] == "1"


def _falha_gemini_nao_autorizado():
    raise AssertionError("Gemini não deve ser chamado sem opt-in")
