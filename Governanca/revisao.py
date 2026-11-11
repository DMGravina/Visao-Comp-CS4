def decidir_validacao(dados_extraidos, confianca_media=0.0, confianca_minima=0.65):
    """Decide se um registro pode prosseguir para o banco final.

    Regra de governança: evitar persistência automática de dados duvidosos.
    Não implementa validação semântica avançada; apenas validações de
    integridade, qualidade de OCR e consistência mínima de campos críticos.
    """
    motivos = []

    tag = dados_extraidos.get("tag_identificacao", "Não localizado")
    if tag in (None, "", "Não localizado"):
        motivos.append("tag_identificacao ausente ou inválida")

    if confianca_media < confianca_minima:
        motivos.append(f"confiança OCR baixa: {confianca_media:.2f}")

    campos_criticos = ["potencia", "tensao", "corrente", "rotacao", "frequencia"]
    for campo in campos_criticos:
        valor = dados_extraidos.get(campo, "Não localizado")
        if valor in (None, "", "Não localizado"):
            continue

        if not any(caractere.isdigit() for caractere in str(valor)):
            motivos.append(f"valor inválido em {campo}")
            continue

        numero = __extrair_numero(valor)
        if numero is None:
            motivos.append(f"valor não numérico em {campo}")
            continue

        if campo == "potencia" and numero <= 0:
            motivos.append("potencia fora do limite físico")
        elif campo == "tensao" and numero <= 0:
            motivos.append("tensao fora do limite físico")
        elif campo == "corrente" and numero <= 0:
            motivos.append("corrente fora do limite físico")

    status = "APROVADO" if not motivos else "PENDENTE"
    aprovado = status == "APROVADO"
    return status, motivos, aprovado


def __extrair_numero(valor):
    if valor is None:
        return None

    match = __import__("re").search(r"\d+(?:[.,]\d+)?", str(valor))
    if not match:
        return None

    return float(match.group().replace(",", "."))
