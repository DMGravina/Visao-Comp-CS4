# Relatório comparativo — Sprints 3 e 4

**Projeto:** Gêmeo Digital para Ativos Industriais (Forzy / Promon)  
**Grupo:** Dota  
**Data da análise:** 13 de novembro de 2026  
**Base da análise:** relatórios técnicos das Sprints 3 e 4 e código atualmente presente neste repositório.

## 1. Síntese executiva

A Sprint 3 concentrou-se na evolução do protótipo de OCR: reduzir os erros de leitura de placas industriais, investigar alternativas ao OCR clássico e estabelecer um conjunto de teste rotulado. A Sprint 4 deslocou o foco para a estabilização e a comparação de motores de OCR, com refinamentos no pré-processamento, extração mais estrita da tensão e proteção da chave da API Gemini.

O relatório da Sprint 4 registrou um resultado ainda inconclusivo: nos primeiros 15 dos 30 exemplos, EasyOCR e Tesseract tiveram zero correspondências exatas com as TAGs do gabarito; o Gemini não foi avaliado por falta de chave configurada. O documento também identificou como pendências a integração entre OCR, governança e SQLite e a execução integral do benchmark.

No código atualmente presente, essas pendências de integração foram parcialmente resolvidas depois do estado descrito no relatório da Sprint 4: há modos separados para benchmark, ingestão e revisão humana; o cadastro aprovado é gravado no SQLite, enquanto pendências e rejeições ficam fora da tabela de ativos. A prova de conceito continua, contudo, limitada à ingestão visual de metadados. O benchmark completo com Gemini e a integração de telemetria, predição e RAG não estão comprovados ou implementados neste repositório.

## 2. Comparação entre as sprints

| Tema | Sprint 3 | Sprint 4 e situação no código |
|---|---|---|
| **Objetivo** | Aumentar a capacidade de interpretar placas e estruturar uma avaliação comparativa. | Estabilizar o pipeline, comparar motores e documentar limitações e evidências. |
| **Estratégias de OCR** | O relatório apresenta ajuste do EasyOCR, ROI/template matching para layouts conhecidos e modelos multimodais como abordagens investigadas. | O código executa EasyOCR, Tesseract e Gemini via API. Não há implementação de ROI fixo nem de um Vision Transformer local; a alternativa multimodal presente é o serviço Gemini. |
| **Pré-processamento** | OpenCV com escala de cinza, filtro bilateral, CLAHE e binarização adaptativa já é descrito como base do pipeline. | O código mantém esses filtros e acrescenta redimensionamento limitado a 1800 pixels e conversão de coordenadas das caixas para a imagem original. |
| **Extração** | O relatório enfatiza Regex e a extração de grandezas, além da leitura de TAGs, em placas com formatos variados. | O tratamento de tensão exige um valor numérico seguido de `V` e corrige caracteres ambíguos como `O`/`0`. A TAG é localizada por rótulo ou por candidatos OCR. No dicionário padrão atual, os únicos campos extraídos por padrão são TAG e tensão; potência, corrente, rotação e frequência não têm regras padrão configuradas. |
| **Avaliação** | O relatório propõe um dataset de 30 imagens e avaliação integral de campos contra o *ground truth*. | O benchmark atual compara correspondência exata da TAG normalizada e registra resultados por motor. O relatório da Sprint 4 descreve apenas 15 imagens avaliadas com EasyOCR/Tesseract, sem Gemini. A métrica principal ainda não é acurácia de todos os campos. |
| **Governança e persistência** | A Sprint 3 descreve a automação do cadastro como objetivo e menciona persistência no contexto da evolução anterior. | O relatório da Sprint 4 reconhece que OCR, SQLite e governança estavam separados. No código atual, a ingestão encaminha os resultados à revisão humana e só a aprovação persiste o ativo. |
| **Segurança** | Não é o foco principal do relatório da Sprint 3. | A chave Gemini é obtida localmente via `.env`; `.env.example` contém apenas o modelo, sem segredo. O código envia a imagem à API Gemini quando esse motor é selecionado. |

## 3. Upgrades implementados no código atual

### 3.1 Pipeline de visão computacional

O fluxo de [tratar.py](./Text_function/tratar.py) redimensiona a imagem para controlar o custo de processamento, aplica filtro bilateral, CLAHE e limiarização adaptativa, e preserva a imagem original. As caixas retornadas pelo OCR são convertidas para coordenadas relativas à imagem original. O pipeline central, em [modelo_visaoc.py](./modelo_visaoc.py), compara os resultados dos três motores, produz CSVs detalhados e resumidos e salva evidências visuais com as caixas detectadas.

O benchmark aceita lotes por deslocamento e tamanho, o que permite trabalhar em grupos menores diante das limitações de memória relatadas na Sprint 4. Cada lote deve usar um diretório de saída próprio para não sobrescrever as evidências de outra execução.

### 3.2 Comparação de TAGs mais informativa

Além da correspondência exata, o código calcula distância de edição e similaridade percentual entre TAG extraída e TAG de referência. A normalização ignora caixa, pontuação e acentos. Uma leitura ausente não é tratada como acerto nem recebe similaridade artificialmente favorável.

Essas métricas são diagnósticas: uma TAG parecida não é corrigida nem aprovada automaticamente. A comparação aproximada atende à recomendação do relatório da Sprint 4 de tornar visível o efeito de pequenos ruídos de OCR, mas não substitui validação humana ou validação de campo.

### 3.3 Ingestão, revisão humana e SQLite

O estado atual inclui um fluxo operacional além do benchmark:

1. `--mode ingest` processa uma ou mais imagens com um motor selecionado e grava os metadados como pendentes de revisão.
2. `--mode review` apresenta os resultados e permite aprovar, rejeitar ou deixar cada registro pendente.
3. A aprovação grava o ativo e atualiza o status da revisão na mesma transação SQLite. TAG ausente ou inválida impede a gravação.
4. A rejeição não grava o ativo. A função de persistência também exige um status de validação explícito, evitando gravação implícita de registros sem aprovação.

Assim, o loop de revisão apontado como pendência no relatório da Sprint 4 está conectado na versão atual do código. A revisão disponível é uma interface de terminal para aprovar ou rejeitar; ela ainda não permite editar os campos extraídos antes da aprovação.

### 3.4 Governança, documentação e testes

O código preserva motivos e confiança OCR na fila de revisão, e encaminha todos os resultados para aprovação humana, inclusive os que não acionaram as regras automáticas. As dependências, configuração local do Gemini e modos de execução estão documentados em [README.md](./README.md). Os testes cobrem OCR, extração, métricas, processamento em lotes e o ciclo de aprovação/rejeição.

Na validação realizada para esta análise, **15 testes passaram**. Esses testes verificam principalmente contratos e fluxo de dados com dependências externas simuladas; não constituem medição da acurácia dos motores nas 30 imagens reais.

## 4. Situação do projeto e limites das evidências

O código entregue é uma prova de conceito utilizável para ingestão visual de metadados estáticos, avaliação de TAGs e revisão humana. Ele não corresponde ainda à plataforma completa de Gêmeo Digital descrita como visão de produto.

As evidências devem ser interpretadas com cuidado:

- O resultado de **zero correspondências exatas em 15 imagens** é o que o relatório da Sprint 4 documenta para EasyOCR e Tesseract; não representa uma nova execução realizada nesta análise.
- A execução integral das 30 imagens com Gemini depende de chave local válida e conectividade com a API. Não foi realizada nesta análise.
- O benchmark atual mede a TAG, não a acurácia integral de TAG, potência, tensão, corrente, rotação e frequência descrita no plano da Sprint 3.
- As regras padrão de extração não cobrem todos os campos estruturados existentes no SQLite. A ausência desses campos deve continuar visível para revisão, em vez de ser apresentada como extração concluída.
- O README distingue corretamente a arquitetura planejada dos componentes presentes no repositório. OPC-UA, Node-RED, TimescaleDB, Grafana, modelos preditivos, topologia hierárquica completa e assistente RAG continuam fora do código executável.

## 5. Próximos passos recomendados para a entrega

1. Executar e arquivar o benchmark completo de 30 imagens para cada motor disponível, incluindo Gemini quando autorizado, com os CSVs e as evidências por lote.
2. Ampliar e avaliar a extração de campos além de TAG e tensão; incluir métricas por campo e casos de erro no *ground truth*.
3. Permitir correção manual dos metadados na revisão antes da aprovação e persistir claramente os valores corrigidos.
4. Documentar os resultados reais do benchmark e as limitações observadas, sem inferir superioridade do Gemini antes da execução comparável.
5. Tratar telemetria, predição, interface gráfica e RAG como etapas separadas de escopo, com requisitos e validação próprios, caso façam parte da entrega final.

## 6. Conclusão

A transição da Sprint 3 para a Sprint 4 foi principalmente uma passagem de exploração de abordagens para estabilização, comparação e análise de gargalos. O ganho central da Sprint 4 foi tornar o pipeline de OCR mais avaliável e seguro, não demonstrar acurácia suficiente para cadastro automático. As atualizações presentes no código atual fecham o fluxo OCR–revisão–SQLite e adicionam métricas aproximadas sem retirar a exigência de aprovação humana. Para concluir a entrega com evidência, ainda falta executar o benchmark integral e ampliar a extração e validação dos campos do ativo.
