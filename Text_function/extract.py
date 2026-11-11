import re

_SERIAL_TOKEN = re.compile(r"[A-Z0-9]+(?:[-/][A-Z0-9]+)*", re.IGNORECASE)
_SERIAL_LABEL = re.compile(
    r"(?:N[ÚU]MERO\s+DE\s+S[ÉE]RIE|SERIAL\s*(?:N[º°O]|NO|NUMBER)?|S\s*/\s*N|N[º°])"
    r"\s*[:#.-]?\s*([A-Z0-9]+(?:[-/]\s*[A-Z0-9]+)*)",
    re.IGNORECASE,
)
_SERIAL_STOPWORDS = {
    "SERIAL", "NUMBER", "NO", "TYPE", "MODEL", "MOTOR", "WEG", "SIEMENS",
    "CEMB", "NETZSCH", "MADE", "IN", "CLASS", "FRAME", "VOLT", "RPM",
}


def _limpar_serial(valor):
    return re.sub(r"\s+", "", str(valor)).strip(".:#-")


def _candidato_serial(valor):
    candidato = _limpar_serial(valor).upper()
    compacto = re.sub(r"[^A-Z0-9]", "", candidato)
    if candidato in _SERIAL_STOPWORDS or len(compacto) < 6:
        return None
    if not any(caractere.isdigit() for caractere in compacto):
        return None
    return candidato


def _extrair_serial(texto_placa, resultados_ocr=None):
    correspondencia = _SERIAL_LABEL.search(texto_placa)
    if correspondencia:
        candidato = _candidato_serial(correspondencia.group(1))
        if candidato:
            return candidato

    candidatos = []
    for resultado in resultados_ocr or []:
        if len(resultado) < 3:
            continue
        confianca = float(resultado[2])
        for token in _SERIAL_TOKEN.findall(resultado[1]):
            candidato = _candidato_serial(token)
            if candidato:
                compacto = re.sub(r"[^A-Z0-9]", "", candidato)
                pontuacao = (len(compacto), any(letra.isalpha() for letra in compacto), confianca)
                candidatos.append((pontuacao, candidato))

    if not candidatos:
        return "Não localizado"
    return max(candidatos, key=lambda item: item[0])[1]


def _normalizar_serial(valor):
    return re.sub(r"[^A-Z0-9]", "", str(valor).upper())


def calcular_confianca_serial(serial, resultados_ocr):
    serial_normalizado = _normalizar_serial(serial)
    if not serial_normalizado or serial_normalizado == "NAOLOCALIZADO":
        return 0.0

    confiancas = []
    for resultado in resultados_ocr or []:
        if len(resultado) < 3:
            continue
        texto_normalizado = _normalizar_serial(resultado[1])
        if serial_normalizado in texto_normalizado:
            confiancas.append(float(resultado[2]))

    return max(confiancas, default=0.0)


def extrair(texto_placa, dicionario_tags, dados_hierarquia, resultados_ocr=None):
    dados_extraidos = {
        "planta": dados_hierarquia.get("planta", "Planta Geral"),
        "area": dados_hierarquia.get("area", "Setor Não Especificado"),
        "ativo_pai": dados_hierarquia.get("ativo_pai", "Sistema Principal"),
        "sub_ativo": dados_hierarquia.get("sub_ativo", "Equipamento")
    }

    for tag, regex in dicionario_tags.items():
        match = re.search(regex, texto_placa, re.IGNORECASE)
        if match:
            # Captura a combinação do valor + unidade se houver grupos
            dados_extraidos[tag] = " ".join(match.groups()).strip()
        else:
            dados_extraidos[tag] = "Não localizado"

    if "tag_identificacao" in dicionario_tags:
        dados_extraidos["tag_identificacao"] = _extrair_serial(texto_placa, resultados_ocr)

    return dados_extraidos


def validar_metadados(dados_extraidos, resultados_ocr=None, confianca_minima=0.35):  # Valida os dados antes da persistência.
    motivos = []  # Acumula justificativas para revisão humana.
    tag = dados_extraidos.get("tag_identificacao", "Não localizado")
    if tag == "Não localizado" or len(re.sub(r"[^A-Z0-9]", "", str(tag).upper())) < 6:
        motivos.append("TAG de identificação não localizada")  # Registra a falha.
    if resultados_ocr:  # Calcula confiança quando há leituras.
        confianca_media = calcular_confianca_serial(tag, resultados_ocr)
        if confianca_media < confianca_minima:  # Bloqueia OCR abaixo do limite operacional.
            motivos.append(f"confiança OCR baixa: {confianca_media:.2f}")  # Preserva a métrica observada.
    else:  # Trata ausência de OCR como falha explícita.
        confianca_media = 0.0  # Representa ausência de evidência.
        motivos.append("nenhuma leitura OCR encontrada")  # Envia para revisão.
    limites = {"potencia": (0, 10000), "tensao": (0, 10000), "corrente": (0, 10000), "rotacao": (0, 100000), "frequencia": (0, 1000)}  # Define limites amplos para bloquear apenas absurdos evidentes.
    for campo in limites:  # Verifica campos numéricos e seus limites operacionais.
        valor = dados_extraidos.get(campo, "Não localizado")  # Obtém o campo sem quebrar se ausente.
        if valor != "Não localizado" and not any(caractere.isdigit() for caractere in valor):  # Bloqueia valor sem dígitos.
            motivos.append(f"valor inválido em {campo}")  # Registra inconsistência.
        if valor != "Não localizado":  # Avalia a faixa somente quando houve candidato.
            numero = re.search(r"\d+(?:[\.,]\d+)?", valor)  # Obtém o primeiro número normalizado do campo.
            if numero and not limites[campo][0] <= float(numero.group().replace(",", ".")) <= limites[campo][1]:  # Bloqueia valor fora da faixa.
                motivos.append(f"valor fora da faixa em {campo}")  # Envia o caso para revisão.
    return len(motivos) == 0, motivos, confianca_media  # Retorna decisão, motivos e confiança.