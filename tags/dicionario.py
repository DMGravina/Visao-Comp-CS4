def criar_ddt():
  dicionario_tags = {
      "tag_identificacao": (
      r'(?:N[ÚU]MERO\s+DE\s+S[ÉE]RIE|SERIAL\s*'
      r'(?:N[º°O]|NO|NUMBER)?|S\s*/\s*N|N[º°])'
      r'\s*[:#\.]?\s*([A-Z0-9]+(?:[-/]\s*[A-Z0-9]+)*)'
      ),
  }

  return dicionario_tags

def insercao(dicionario_tags):
  print("CONFIGURAÇÃO DINÂMICA DE TAGS DO ATIVO")
  while True:
        opcao = input("Deseja adicionar um novo campo/TAG de medição para extração? (s/n): ").strip().lower()
        if opcao != 's':
            break
        nome_tag = input("Nome do campo (ex: Vazao, Pressao, Modelo): ").strip()
        padrao_regex = input(f"Expressão Regular (Regex) para {nome_tag}: ").strip()
        dicionario_tags[nome_tag] = padrao_regex
        print(f"✓ TAG '{nome_tag}' adicionada ao extrator!")
  return dicionario_tags