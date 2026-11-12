# Forzy Digital Twin: Plataforma Integrada de Gestão de Ativos Industriais

Olá! Bem-vindo ao repositório oficial do projeto **Forzy Challenge**, desenvolvido pelo **Grupo Dota** em parceria com a **Forzy / Promon Engenharia** e a **FIAP**.

Nós construímos uma solução de **Gêmeo Digital (Digital Twin)** focada em monitoramento, visibilidade operacional e manutenção preditiva. Embora nossa Prova de Conceito (PoC) utilize motores elétricos (como o WEG W22), o coração desta plataforma é **generalista**. Ela foi desenhada para se adaptar à topologia de qualquer planta industrial (bombas, compressores, válvulas, etc.), permitindo o rastreio do efeito cascata de falhas entre equipamentos interconectados.

---

## Como Raciocinamos a Solução (Os 4 Pilares)

Nossa arquitetura divide o fluxo de dados operacionais (dinâmicos) e metadados (estáticos) em quatro grandes pilares tecnológicos:

### 1. Visão Computacional (O Cadastro Inteligente)
Diga adeus ao cadastro manual demorado e suscetível a erros. Desenvolvemos um pipeline robusto para ler as placas metálicas dos ativos de fábrica:
*   **Pré-processamento:** Usamos `OpenCV` (Filtro Bilateral, CLAHE e Threshold Adaptativo) para limpar reflexos de flash, arranhões e sujeira do metal.
*   **Comparação de OCR:** A rotina de avaliação compara EasyOCR, Tesseract OCR e Gemini multimodal, registrando as caixas detectadas e a acurácia em relação ao gabarito.
*   **Inteligência de Extração (Regex):** Como placas industriais não seguem um padrão fixo, usamos Expressões Regulares para buscar grandezas (ex: `[Número] + kW` = Potência). Esses dados formam a "identidade" do ativo e são injetados diretamente em nosso banco relacional (`SQLite`).

### 2. IoT e Telemetria (O Pulso da Máquina)
*   Coletamos os sinais vitais reais do equipamento (vibração, temperatura, corrente) via protocolo **OPC-UA**.
*   Processamos esses sinais no **Node-RED** e os armazenamos de forma otimizada em um banco de dados temporal (**TimescaleDB**).
*   A visualização em tempo real acontece através de dashboards integrados no **Grafana**.

### 3. Machine Learning e Inteligência Preditiva (O Cérebro)
Não mostramos apenas o que está quebrado; prevemos quando vai quebrar. Consumindo os dados do TimescaleDB, nossos modelos estabelecem o *baseline* (comportamento normal) do ativo e disparam alertas caso detectem anomalias que fujam desse padrão, recomendando o momento exato para a manutenção.

### 4. IA Generativa e Troubleshooting (O Especialista RAG)
Integramos um assistente multimodal baseado em arquitetura **RAG (Retrieval-Augmented Generation)**. Ele cruza os alertas do sistema com os manuais técnicos em PDF (Datasheets) do equipamento, oferecendo um chat conversacional para ajudar o técnico no chão de fábrica a resolver o problema rapidamente.

---

## A Estrutura em "Escada"

Para garantir que a plataforma sirva para qualquer indústria, modelamos a navegação de forma hierárquica e interconectada:
1. **Planta/Fábrica** (Visão Macro)
2. **Área/Setor** 
3. **Ativo Principal** (ex: Linha de Bombeamento)
4. **Sub-Ativos** (ex: Motor Elétrico Acoplado)
5. **Ponto de Telemetria** (Sensores individuais)

---

## Governança de IA (Gov.IA) e Segurança

A autonomia da máquina tem limites. Implementamos um rigoroso protocolo de **Governança de IA**:
*   **Metric Contracts (Limiares):** Contratos matemáticos que definem o que é um comportamento anômalo seguro para a IA atuar sozinha (Informação Explícita).
*   **Protocolo de Handoff Humano:** Critérios claros para quando o modelo deve passar a decisão para a intuição e experiência do engenheiro (Informação Tácita).
*   **Human-in-the-loop (A "Falha de Ouro"):** Descobrimos nos testes que o OCR pode ler, por proximidade geométrica, "1 HP 60 Hz" como "1 Hz". Por ser um ambiente crítico, a extração visual preenche o formulário, mas **exige validação humana** antes do cadastro definitivo (Circuit Breaker).

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

É possível passar `--images-dir`, `--ground-truth`, `--output-dir` e `--expected-images` para selecionar outro lote. O dataset atual contém 30 imagens rotuladas no CSV. O script sinaliza se a quantidade de imagens rotuladas for inferior à esperada.

*(O front-end e os serviços de telemetria podem requerer a subida de containers Docker para o TimescaleDB e Node-RED, documentados separadamente no diretório `/infra`)*.

---

## Equipe (Grupo Dota)
Nós nos orgulhamos do desenvolvimento ponta-a-ponta desta aplicação, evoluindo a Prova de Conceito e aplicando os preceitos de Governança para entregar uma solução escalável, confiável e inovadora para a Promon Engenharia.