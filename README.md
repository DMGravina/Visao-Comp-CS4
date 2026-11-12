# Forzy Digital Twin: Plataforma Integrada de Gestão de Ativos Industriais

Olá! Este repositório contém a prova de conceito do **Forzy Challenge**, desenvolvido pelo **Grupo Dota** em parceria com a **Forzy / Promon Engenharia** e a **FIAP**. A entrega implementada concentra-se na ingestão de dados estáticos de placas industriais por OCR, sua revisão humana e o cadastro aprovado em SQLite. Telemetria, manutenção preditiva e assistência RAG permanecem como arquitetura proposta, não como funcionalidades executáveis neste repositório.

O objetivo maior é uma solução de **Gêmeo Digital** focada em monitoramento, visibilidade operacional e manutenção preditiva. Embora a prova de conceito utilize motores elétricos, a arquitetura pretendida é generalista e pode se adaptar à topologia de outras plantas industriais.

---

## Como Raciocinamos a Solução

O protótipo implementa o fluxo de ingestão de metadados estáticos. Os demais pilares abaixo descrevem a arquitetura planejada:

### 1. Visão Computacional
Diga adeus ao cadastro manual demorado e suscetível a erros. Desenvolvemos um pipeline robusto para ler as placas metálicas dos ativos de fábrica:
*   **Pré-processamento:** Usamos `OpenCV` (Filtro Bilateral, CLAHE e Threshold Adaptativo) para limpar reflexos de flash, arranhões e sujeira do metal.
*   **Comparação de OCR:** A rotina de avaliação compara EasyOCR, Tesseract OCR e Gemini multimodal, registrando as caixas detectadas e a acurácia em relação ao gabarito.
*   **Inteligência de Extração (Regex):** Expressões Regulares identificam campos disponíveis no texto reconhecido. No modo de cadastro, os resultados seguem para revisão humana e só são gravados no SQLite após aprovação.

### 2. IoT e Telemetria (arquitetura proposta)
OPC-UA, Node-RED, TimescaleDB e Grafana fazem parte do desenho futuro. A coleta, o armazenamento temporal e os dashboards ainda não estão implementados neste repositório.

### 3. Machine Learning e Inteligência Preditiva (arquitetura proposta)
Os modelos de anomalia, o *baseline* e os alertas de manutenção dependem da futura integração com os dados de telemetria e ainda não fazem parte do código entregue.

### 4. IA Generativa e Troubleshooting (arquitetura proposta)
O assistente **RAG** para consultar manuais e alertas permanece como etapa futura. A integração Gemini disponível neste código é usada para OCR multimodal de placas, não para troubleshooting conversacional.

---

## A Estrutura em "Escada"

Para a plataforma futura, a navegação está planejada de forma hierárquica e interconectada:
1. **Planta/Fábrica** (Visão Macro)
2. **Área/Setor** 
3. **Ativo Principal** (ex: Linha de Bombeamento)
4. **Sub-Ativos** (ex: Motor Elétrico Acoplado)
5. **Ponto de Telemetria** (Sensores individuais)

---

## Governança de IA e Segurança

A autonomia da máquina tem limites. No fluxo de cadastro implementado:
*   Os resultados do OCR são encaminhados à fila de revisão, mesmo quando as regras automáticas não apontam inconsistências.
*   A aprovação humana grava o ativo no SQLite; a rejeição mantém o registro fora da tabela de ativos.
*   O benchmark mede correspondência exata e similaridade das TAGs, mas similaridade não aprova nem corrige automaticamente um cadastro.

Os contratos de métrica para telemetria e o handoff associado a modelos preditivos permanecem fora do escopo de código atual.

---

## Guia de Instalação e Execução

Quer rodar o projeto localmente? Siga os passos abaixo:

### Pré-requisitos
*   [Python 3.9+](https://www.python.org/downloads/)
*   [Git](https://git-scm.com/)
*   Binário do Tesseract OCR instalado e disponível no `PATH`.
*   Chave própria da API Gemini para habilitar a abordagem multimodal. As imagens serão enviadas à API Gemini do Google; não configure a chave se isso não for permitido para o seu dataset.
*   (Opcional) Suporte a GPU CUDA para acelerar o EasyOCR.

#### Instalação do Tesseract

No Ubuntu/Debian:
```bash
sudo apt update
sudo apt install -y tesseract-ocr
tesseract --version
```

No Windows, instale o Tesseract OCR para Windows e adicione a pasta de instalação ao `PATH`; depois, confirme com `tesseract --version` em um novo terminal.

### 1. Clonando o Repositório
```bash
git clone https://github.com/SeuUsuario/forzy-digital-twin.git
cd forzy-digital-twin
```

### 2. Configurando o Ambiente Virtual
Recomendamos o uso de um ambiente virtual para isolar as dependências.
```bash
python -m venv venv
# No Windows:
venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate
```

### 3. Instalando as Dependências
Instale as bibliotecas necessárias de Visão Computacional, OCR, Pandas, etc.
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configurando a chave Gemini
Copie o modelo local e edite `.env` para inserir sua própria chave:
```bash
cp .env.example .env
```
No Windows PowerShell:
```powershell
Copy-Item .env.example .env
```
Abra `.env` e preencha `GEMINI_API_KEY=sua-chave`. O `.env` é ignorado pelo Git; nunca compartilhe nem versione esse arquivo ou a chave. O script carrega a chave localmente ao iniciar. Sem a chave, EasyOCR e Tesseract ainda podem ser avaliados, mas o comparativo identificará o Gemini como erro de execução.

### 5. Executando o Pipeline
**Para comparar as três abordagens no lote rotulado:**
```bash
python modelo_visaoc.py
```
O pipeline processa as imagens listadas em `placas/Book.csv` e gera `evidencias_ocr/comparativo_acuracia.csv`, `evidencias_ocr/resultados_detalhados.csv` e uma imagem com bounding boxes por abordagem e amostra em `evidencias_ocr/marcacoes/`. A acurácia é de correspondência exata da TAG normalizada (ignorando pontuação e caixa), e erros de execução são identificados no comparativo. Esta execução de benchmark gera apenas evidências e não grava dados no banco relacional.

O relatório de benchmark também inclui distância de edição e similaridade percentual. Esses indicadores são informativos: somente a correspondência exata conta como acerto. Para executar em lotes menores (por exemplo, para limitar o uso de memória), use `--batch-offset` e `--batch-size` e escolha um `--output-dir` diferente para cada lote. Também é possível passar `--images-dir`, `--ground-truth`, `--output-dir` e `--expected-images`. O dataset atual contém 30 imagens rotuladas no CSV.

**Para enviar imagens ao fluxo de cadastro e revisão humana:**
```bash
python modelo_visaoc.py --mode ingest --images placas/Placa_Ind10.jpg --ocr-method "EasyOCR"
```

O modo `ingest` aceita uma ou mais imagens e os motores `EasyOCR`, `Tesseract` ou `Gemini API`. As imagens são encaminhadas à fila SQLite como pendentes; não há gravação automática de ativos. Para revisar os dados apresentados e aprovar ou rejeitar cada registro:
```bash
python modelo_visaoc.py --mode review
```

Use `--db-path caminho/para/banco.db` em ambos os modos para selecionar outro banco. A aprovação grava o registro na tabela de ativos e atualiza o status da revisão na mesma transação. O benchmark completo com Gemini exige uma chave válida configurada localmente e conectividade com a API; essa execução não é feita automaticamente.

---

## Equipe (Grupo Dota)
O Grupo Dota desenvolveu esta prova de conceito em parceria com a Forzy / Promon Engenharia e a FIAP.
