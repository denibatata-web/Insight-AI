# Insight AI — Sistema Multi-Agente para Análise de Apólices D&O

Projeto Final do **InsurMinds** voltado à leitura, estruturação, análise e comparação de apólices de seguro **D&O (Directors & Officers)** com apoio de Inteligência Artificial Generativa.

## Participantes

- **Deni de Souza Santos — Representante**
- **Tatiane Ivanof**

## Visão geral

O Insight AI recebe duas ou mais apólices, extrai seus principais dados, organiza as informações em estrutura padronizada e executa uma análise multiagente. Ao final, apresenta uma comparação consolidada, gera relatório em PDF e permite exportar os dados estruturados em JSON.

## Arquitetura multiagente

**Agente 1 — Extrator de Dados:** identifica campos como seguradora, número da apólice, tomador, segurados, LMG, prêmio, vigência, retroatividade, coberturas, limites, franquias/POS e exclusões.

**Agente 2 — Analista de Coberturas:** produz uma análise técnica individual de cada apólice, destacando coberturas, limites, franquias e pontos de atenção.

**Agente 3 — Auditor de Riscos:** compara as apólices analisadas, identifica diferenças, lacunas, exclusões e aspectos relevantes para apoio à decisão.

Fluxo resumido:

`Documento → Extração → Agente 1 → JSON/Pydantic → Agente 2 → Agente 3 → Interface → PDF/JSON`

## Tecnologias

- Python
- Streamlit
- Groq / modelo de linguagem
- Pydantic
- pandas
- pypdf
- ReportLab
- Pillow e pytesseract para OCR opcional de imagens

## Estrutura do projeto

```text
Insight-AI/
├── app.py
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── apolices_exemplo/
│   ├── Apolice_DO_01_Alpha_Ficticia.pdf
│   ├── Apolice_DO_02_Beta_Ficticia.pdf
│   └── Apolice_DO_03_Gama_Ficticia.pdf
└── documentacao/
    └── Relatorio_Tecnico_Final_Insight_AI.pdf
```

## Instalação

Recomenda-se Python 3.10 ou superior.

Crie e ative um ambiente virtual, se desejar, e instale as dependências:

```bash
pip install -r requirements.txt
```

### OCR opcional

A análise de PDFs com texto pesquisável não depende de OCR. Para analisar arquivos PNG/JPG/JPEG, o projeto utiliza `pytesseract`, que também requer a instalação do programa **Tesseract OCR** no sistema operacional.

## Chave da Groq

Nunca coloque uma chave real de API no GitHub.

O aplicativo permite informar a chave de forma protegida na interface e também consulta a variável de ambiente:

```text
GROQ_API_KEY
```

Exemplo no Windows PowerShell:

```powershell
$env:GROQ_API_KEY="SUA_CHAVE_AQUI"
streamlit run app.py
```

O arquivo `.env.example` contém apenas um exemplo e não deve receber uma chave real antes de ser publicado.

## Execução

Na pasta do projeto:

```bash
streamlit run app.py
```

O navegador deverá abrir a interface do Insight AI. Carregue pelo menos duas apólices e execute a análise multiagente.

## Cenário acadêmico de demonstração

A pasta `apolices_exemplo` contém três documentos D&O **fictícios e exclusivamente acadêmicos**, criados para demonstração do sistema. Eles não possuem validade contratual e não representam seguradoras ou contratos reais.

O conjunto permite demonstrar diferenças de LMG, prêmio, retroatividade, franquias/POS, coberturas e sublimites.

## Saídas

O Insight AI disponibiliza:

- visualização dos dados extraídos;
- análise individual das apólices;
- comparação consolidada;
- auditoria de riscos;
- relatório em PDF;
- exportação dos dados em JSON.

## Limitações

Resultados gerados por modelos de linguagem devem ser conferidos antes de uso operacional ou contratual. O teste acadêmico identificou que textos narrativos podem ocasionalmente interpretar incorretamente abreviações monetárias, mesmo quando o dado estruturado permanece correto. Uma evolução recomendada é adicionar verificadores determinísticos entre os dados validados e o texto final.

## Segurança

- Não publique chaves de API.
- Não inclua `.env` nem `secrets.toml` no repositório.
- Para uso real, documentos e resultados devem seguir políticas adequadas de acesso, retenção, privacidade e auditoria.
- A ferramenta é um protótipo acadêmico e não substitui análise técnica ou jurídica especializada.

## Licença

Este projeto é disponibilizado sob a **Licença MIT**. Consulte o arquivo `LICENSE`.

## 🎥 Demonstração em vídeo

A apresentação e demonstração do **Insight AI — Sistema Multiagente para Análise e Comparação de Apólices D&O** está disponível no YouTube.

▶️ [Assistir à demonstração do Insight AI](https://youtu.be/-DHnJMWrWp0)

O vídeo apresenta a proposta do projeto, a arquitetura multiagente, o funcionamento da aplicação, a análise comparativa das apólices D&O e os principais resultados obtidos.

## 📊 Apresentação do projeto

Os materiais utilizados na apresentação estão disponíveis na pasta `apresentação/`:

- `Pitch_Deck_Insight_AI_InsurMinds_2026.pdf`
- `Pitch_Deck_Insight_AI_InsurMinds_2026.pptx`

## 👥 Equipe

**Deni de Souza Santos — Representante**  
**Tatiane Ivanof**

Projeto Final — **InsurMinds 2026**
