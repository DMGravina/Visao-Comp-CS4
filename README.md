# Forzy Digital Twin: Plataforma Integrada de Gestão de Ativos Industriais

Olá! Este repositório contém a prova de conceito do **Forzy Challenge**, desenvolvido pelo **Grupo Dota** em parceria com a **Forzy / Promon Engenharia** e a **FIAP**. A entrega implementada concentra-se na ingestão de dados estáticos de placas industriais por OCR, sua revisão humana e o cadastro aprovado em SQLite. Telemetria, manutenção preditiva e assistência RAG permanecem como arquitetura proposta, não como funcionalidades executáveis neste repositório.

O objetivo maior é uma solução de **Gêmeo Digital** focada em monitoramento, visibilidade operacional e manutenção preditiva. Embora a prova de conceito utilize motores elétricos, a arquitetura pretendida é generalista e pode se adaptar à topologia de outras plantas industriais.

---

## Como Raciocinamos a Solução

O protótipo implementa o fluxo de ingestão de metadados estáticos. Os demais pilares abaixo descrevem a arquitetura planejada:

### 1. Visão Computacional
Diga adeus ao cadastro manual demorado e suscetível a erros. Desenvolvemos um pipeline robusto para ler as placas metálicas dos ativos de fábrica:
*   **Pré-processamento:** Usamos `OpenCV` (Filtro Bilateral, CLAHE e Threshold Adaptativo) para limpar reflexos de flash, arranhões e sujeira do metal.
*   **Comparação de OCR:** O benchmark avalia EasyOCR, Tesseract OCR e, quando explicitamente habilitado, Gemini multimodal. Registra acertos exatos de TAG normalizada, falhas de execução e resultado por imagem em relação ao gabarito.
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
*   Binário do Tesseract OCR e dados de idioma `eng` instalados e disponíveis no `PATH` (opcional para executar somente EasyOCR).
*   Para usar Gemini no benchmark ou no cadastro: variável `GEMINI_API_KEY` preenchida com uma chave válida da API e autorização explícita para enviar as imagens ao serviço do Google. Sem chave, o Gemini não funciona; no benchmark, também é necessário `--enable-gemini` para permitir o envio do lote.
*   (Opcional) Suporte a GPU CUDA para acelerar o EasyOCR.

#### Instalação do Tesseract

No Ubuntu/Debian:
```bash
sudo apt update
sudo apt install -y tesseract-ocr
tesseract --version
tesseract --list-langs
```

No Windows, instale o Tesseract OCR com os dados de idioma inglês e adicione a pasta de instalação ao `PATH`; depois, confirme com `tesseract --version` e `tesseract --list-langs` em um novo terminal.

### 1. Clonando o Repositório
```bash
git clone https://github.com/DMGravina/Visao-Comp-CS4.git
cd Visao-Comp-CS4
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

### 4. Configurando a chave Gemini (opcional)
EasyOCR e Tesseract não exigem chave de API. Para executar Gemini, é obrigatório configurar `GEMINI_API_KEY` com uma chave válida. O benchmark padrão não habilita Gemini e não envia imagens externamente. Só configure/ use a chave se o envio das imagens à API estiver autorizado. Copie o modelo local e edite `.env`:
```bash
cp .env.example .env
```
No Windows PowerShell:
```powershell
Copy-Item .env.example .env
```
Abra `.env` e preencha `GEMINI_API_KEY=sua-chave`. O `.env` é ignorado pelo Git; nunca compartilhe nem versione esse arquivo ou a chave. No benchmark, a chave sozinha não habilita o envio: use `--enable-gemini` apenas depois de confirmar a autorização para usar o dataset nesse serviço. Se o Gemini não for habilitado ou não houver chave, os resultados indicam `NAO_EXECUTADO`, sem contar isso como falha de OCR.

### 5. Executando o Pipeline
**Para executar o benchmark local do lote rotulado (Gemini é opcional):**
```bash
python modelo_visaoc.py --output-dir evidencias_ocr
```
O comando processa as 30 imagens listadas em `placas/Book.csv` e gera `evidencias_ocr/comparativo_acuracia.csv`, `evidencias_ocr/resultados_detalhados.csv` e imagens com bounding boxes em `evidencias_ocr/marcacoes/` para os métodos executados. O CSV detalhado tem uma linha por imagem e método; `status` distingue `EXECUTADO`, `ERRO_EXECUCAO` e `NAO_EXECUTADO`, enquanto `classificacao_resultado` distingue falha de execução de `ERRO_OCR` (TAG executada mas sem correspondência exata). Esta execução gera apenas evidências e não grava dados no banco relacional.

Para a TAG normalizada, o benchmark ignora caixa e acentos e compara apenas letras ASCII e dígitos, removendo pontuação e espaços. `acuracia_percentual` conta acertos exatos sobre todas as imagens do lote (uma falha ou método não executado não conta como acerto); `acuracia_sobre_processadas_percentual` e `similaridade_media_percentual` usam somente as execuções concluídas. Distância de edição e similaridade percentual são informativas e nunca contam como acerto. Para executar em lotes menores (por exemplo, para limitar o uso de memória), use `--batch-offset` e `--batch-size` e escolha um `--output-dir` diferente para cada lote. Também é possível passar `--images-dir`, `--ground-truth`, `--output-dir` e `--expected-images`.

#### Resultado medido neste repositório

Execução local do benchmark em 2026-11-13, com o gabarito atual (30 imagens), EasyOCR e Tesseract habilitados e Gemini desabilitado:

| Método | Processadas | Acertos exatos de TAG | Erros de execução | Não executadas | Similaridade média |
|---|---:|---:|---:|---:|---:|
| EasyOCR | 30/30 | 0/30 (0%) | 0 | 0 | 11,92% |
| Tesseract | 30/30 | 0/30 (0%) | 0 | 0 | 3,22% |
| Gemini API | 0/30 | Não avaliado | 0 | 30 | Não avaliada |

As 30 imagens do `Book.csv` existem e foram processadas pelos dois motores locais. Em ambos, todas as saídas foram classificadas como `ERRO_OCR` (TAG extraída diferente da TAG normalizada do gabarito); não houve falhas de execução. Gemini foi deliberadamente `NAO_EXECUTADO` para não enviar imagens sem autorização explícita. Portanto, estes resultados não demonstram ganho de acurácia. Os CSVs detalhados contêm 90 linhas (uma por imagem e método) e foram gerados junto com 60 marcações dos motores locais em `evidencias_ocr/`; esse diretório é ignorado pelo Git.

**Gemini, somente com autorização para esse dataset:**
```bash
python modelo_visaoc.py --enable-gemini
```
Esse comando requer `GEMINI_API_KEY` e conectividade com a API. Uma chave configurada sem a opção `--enable-gemini` não causa transmissão. Uma chamada recusada, erro de conexão ou resposta inválida aparecerá como `ERRO_EXECUCAO`, separado de um resultado OCR incorreto.

**Para enviar imagens ao fluxo de cadastro e revisão humana:**
```bash
python modelo_visaoc.py --mode ingest --images placas/Placa_Ind10.jpg --ocr-method "EasyOCR"
```

O modo `ingest` aceita uma ou mais imagens e os motores `EasyOCR`, `Tesseract` ou `Gemini API`. Para selecionar Gemini, configure `GEMINI_API_KEY` e execute, por exemplo:
```bash
python modelo_visaoc.py --mode ingest --images placas/Placa_Ind10.jpg --ocr-method "Gemini API"
```
Esse comando envia a imagem à API Gemini; use-o somente com chave válida e autorização para esse uso. As imagens são encaminhadas à fila SQLite como pendentes; não há gravação automática de ativos. Para revisar os dados apresentados e aprovar ou rejeitar cada registro:
```bash
python modelo_visaoc.py --mode review
```

Use `--db-path caminho/para/banco.db` em ambos os modos para selecionar outro banco. A aprovação grava o registro na tabela de ativos e atualiza o status da revisão na mesma transação. O benchmark completo com Gemini exige uma chave válida configurada localmente e conectividade com a API; essa execução não é feita automaticamente.

---

## Equipe (Grupo Dota)
O Grupo Dota desenvolveu esta prova de conceito em parceria com a Forzy / Promon Engenharia e a FIAP.
