# Forzy Digital Twin: Plataforma Integrada de Gestão de Ativos Industriais

Olá! Bem-vindo ao repositório oficial do projeto **Forzy Challenge**, desenvolvido pelo **Grupo Dota** em parceria com a **Forzy / Promon Engenharia** e a **FIAP**.

Nós construímos uma solução de **Gêmeo Digital (Digital Twin)** focada em monitoramento, visibilidade operacional e manutenção preditiva. Embora nossa Prova de Conceito (PoC) utilize motores elétricos (como o WEG W22), o coração desta plataforma é **generalista**. Ela foi desenhada para se adaptar à topologia de qualquer planta industrial (bombas, compressores, válvulas, etc.), permitindo o rastreio do efeito cascata de falhas entre equipamentos interconectados.

---

## Como Raciocinamos a Solução (Os 4 Pilares)

Nossa arquitetura divide o fluxo de dados operacionais (dinâmicos) e metadados (estáticos) em quatro grandes pilares tecnológicos:

### 1. Visão Computacional (O Cadastro Inteligente)
Diga adeus ao cadastro manual demorado e suscetível a erros. Desenvolvemos um pipeline robusto para ler as placas metálicas dos ativos de fábrica:
*   **Pré-processamento:** Usamos `OpenCV` (Filtro Bilateral, CLAHE e Threshold Adaptativo) para limpar reflexos de flash, arranhões e sujeira do metal.
*   **OCR com GPU:** Implementamos o `EasyOCR` (DB para Bounding Boxes e CRNN para leitura) para transcrever a imagem.
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
*   (Opcional, mas recomendado) Suporte a GPU CUDA para acelerar o EasyOCR.

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
pip install -r requirements.txt
```

### 4. Executando o Pipeline
**Para testar a extração OCR (Visão Computacional):**
Basta executar o script principal passando o caminho da imagem de teste. O sistema aplicará os filtros, extrairá os dados via Regex e salvará no banco local `forzy_gemeo_digital.db`.
```bash
python src/cv_pipeline.py --image_path "data/images/placa_weg_teste.jpg"
```

*(O front-end e os serviços de telemetria podem requerer a subida de containers Docker para o TimescaleDB e Node-RED, documentados separadamente no diretório `/infra`)*.

---

## Equipe (Grupo Dota)
Nós nos orgulhamos do desenvolvimento ponta-a-ponta desta aplicação, evoluindo a Prova de Conceito e aplicando os preceitos de Governança para entregar uma solução escalável, confiável e inovadora para a Promon Engenharia.