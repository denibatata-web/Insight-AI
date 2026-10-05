import streamlit as st
import pandas as pd
import json
import re
import os
from io import BytesIO
from datetime import datetime

from pypdf import PdfReader
from groq import Groq
from pydantic import BaseModel, Field
from typing import List

# OCR opcional para imagens (JPG/PNG).
# Instale com: pip install pillow pytesseract
try:
    from PIL import Image
    import pytesseract
    OCR_DISPONIVEL = True
except ImportError:
    OCR_DISPONIVEL = False

# ============================================================================
# REPORTLAB - GERAÇÃO DE PDF
# ============================================================================

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

MODELO_PADRAO = "openai/gpt-oss-120b"

MODELOS_DISPONIVEIS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]

# =============================================================================
# IDENTIDADE DO PROJETO
# =============================================================================

NOME_APLICATIVO = "Insight AI"
SUBTITULO_APLICATIVO = "Sistema Multi-Agente D&O"
PARTICIPANTES_PROJETO = [
    "Deni de Souza Santos — Representante",
    "Tatiane Ivanof",
]
AUTOR_RELATORIO = "Deni de Souza Santos e Tatiane Ivanof"


# =============================================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================================

st.set_page_config(
    page_title=f"{NOME_APLICATIVO} - {SUBTITULO_APLICATIVO}",
    page_icon="🛡️",
    layout="wide"
)


# =============================================================================
# FONTES PARA PDF
# =============================================================================

def configurar_fontes_pdf():
    """
    Procura fontes Unicode disponíveis no Windows.
    Isso permite gerar PDF com caracteres como:
    ç, ã, õ, é, á, í etc.
    """

    fontes_possiveis = [
        (
            "Arial",
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\arialbd.ttf"
        ),
        (
            "DejaVu",
            r"C:\Windows\Fonts\DejaVuSans.ttf",
            r"C:\Windows\Fonts\DejaVuSans-Bold.ttf"
        ),
    ]

    for nome, regular, bold in fontes_possiveis:

        if os.path.exists(regular):

            try:

                pdfmetrics.registerFont(
                    TTFont(nome, regular)
                )

                if os.path.exists(bold):

                    pdfmetrics.registerFont(
                        TTFont(f"{nome}-Bold", bold)
                    )

                    return nome, f"{nome}-Bold"

                return nome, nome

            except Exception:
                pass

    # Fallback
    return "Helvetica", "Helvetica-Bold"


PDF_FONT, PDF_FONT_BOLD = configurar_fontes_pdf()


# =============================================================================
# MODELAGEM DOS DADOS - PYDANTIC
# =============================================================================

class Cobertura(BaseModel):

    nome: str = Field(
        default="Não identificado",
        description="Nome da cobertura ou garantia"
    )

    limite: str = Field(
        default="Não identificado",
        description="Limite de indenização"
    )

    franquia_pos: str = Field(
        default="Não identificado",
        description="Franquia ou POS aplicável"
    )


class ApoliceDO(BaseModel):

    numero_apolice: str = Field(
        default="Não identificado",
        description="Número da apólice ou proposta"
    )

    seguradora: str = Field(
        default="Não identificado",
        description="Nome da companhia seguradora"
    )

    tomador: str = Field(
        default="Não identificado",
        description="Razão social e CNPJ/NIF do Tomador"
    )

    segurados: str = Field(
        default="Não identificado",
        description="Descrição dos Segurados"
    )

    lmg_total: str = Field(
        default="Não identificado",
        description="Limite Máximo de Garantia"
    )

    premio_total: str = Field(
        default="Não identificado",
        description="Valor do prêmio total"
    )

    vigencia_inicio: str = Field(
        default="Não identificado",
        description="Data início da vigência"
    )

    vigencia_fim: str = Field(
        default="Não identificado",
        description="Data fim da vigência"
    )

    data_retroatividade: str = Field(
        default="Não identificado",
        description="Data de retroatividade"
    )

    coberturas: List[Cobertura] = Field(
        default_factory=list,
        description="Lista de coberturas"
    )

    exclusoes_relevantes: List[str] = Field(
        default_factory=list,
        description="Principais exclusões"
    )


# =============================================================================
# FUNÇÕES AUXILIARES PYDANTIC
# =============================================================================

def pydantic_to_dict(model_obj: BaseModel) -> dict:

    if hasattr(model_obj, "model_dump"):
        return model_obj.model_dump()

    return model_obj.dict()


def pydantic_to_json(model_obj: BaseModel) -> str:

    if hasattr(model_obj, "model_dump_json"):
        return model_obj.model_dump_json(indent=2)

    return model_obj.json(indent=2)


# =============================================================================
# EXTRAÇÃO DO PDF
# =============================================================================

def extrair_texto_pdf(uploaded_file) -> str:

    try:

        reader = PdfReader(uploaded_file)

        texto = ""

        for page in reader.pages:

            texto_pagina = page.extract_text()

            if texto_pagina:
                texto += texto_pagina + "\n"

        if not texto.strip():

            raise ValueError(
                "O PDF está vazio ou não possui texto pesquisável. "
                "Pode ser necessário utilizar OCR."
            )

        return texto

    except Exception as e:

        raise Exception(
            f"Falha ao ler o arquivo PDF: {str(e)}"
        )



# =============================================================================
# EXTRAÇÃO DE IMAGEM / DESPACHANTE DE DOCUMENTOS
# =============================================================================

def extrair_texto_imagem(uploaded_file) -> str:
    """
    Extrai texto de JPG/JPEG/PNG via OCR local (Tesseract).
    A funcionalidade é opcional e não altera o fluxo existente de PDFs.
    """
    if not OCR_DISPONIVEL:
        raise RuntimeError(
            "Para analisar imagens, instale as dependências de OCR: "
            "'pip install pillow pytesseract' e o Tesseract OCR no Windows. "
            "A análise de PDFs continua funcionando normalmente."
        )

    try:
        imagem = Image.open(uploaded_file).convert("RGB")
        texto = pytesseract.image_to_string(imagem, lang="por")
    except Exception as e:
        raise RuntimeError(
            "Não foi possível executar o OCR da imagem. "
            "Verifique se o Tesseract OCR está instalado e configurado. "
            f"Detalhes: {str(e)}"
        )

    if not texto.strip():
        raise ValueError(
            "Nenhum texto foi identificado na imagem. "
            "Use uma imagem mais nítida ou um PDF com texto pesquisável."
        )

    return texto


def extrair_texto_documento(uploaded_file) -> str:
    """
    Encaminha o arquivo para o extrator apropriado sem alterar
    o processamento multiagente posterior.
    """
    nome = uploaded_file.name.lower()

    if nome.endswith(".pdf"):
        return extrair_texto_pdf(uploaded_file)

    if nome.endswith((".png", ".jpg", ".jpeg")):
        return extrair_texto_imagem(uploaded_file)

    raise ValueError("Formato não suportado. Utilize PDF, PNG, JPG ou JPEG.")


# =============================================================================
# LIMPEZA DO JSON
# =============================================================================

def limpar_e_extrair_json(texto: str) -> dict:

    if not texto:

        raise ValueError(
            "A IA retornou uma resposta vazia."
        )

    texto = texto.strip()

    match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        texto,
        re.DOTALL
    )

    if match:

        json_str = match.group(1)

    else:

        inicio = texto.find("{")
        fim = texto.rfind("}")

        if inicio != -1 and fim != -1 and fim > inicio:

            json_str = texto[inicio:fim + 1]

        else:

            json_str = texto

    try:

        return json.loads(json_str)

    except json.JSONDecodeError as e:

        raise ValueError(
            "Não foi possível interpretar a resposta da IA como JSON.\n\n"
            f"Erro: {str(e)}\n\n"
            f"Resposta recebida:\n{texto[:5000]}"
        )


# =============================================================================
# AGENTE 1 - EXTRATOR
# =============================================================================

def agente_1_extrator(
    texto_pdf: str,
    client: Groq,
    model_name: str
) -> ApoliceDO:

    prompt_sistema = """
Você é um especialista em extração de dados de seguros corporativos D&O
(Directors and Officers).

Sua tarefa é analisar o texto de uma apólice de seguro e extrair
as informações relevantes.

RETORNE SOMENTE UM OBJETO JSON VÁLIDO.

A estrutura obrigatória é:

{
  "numero_apolice": "string",
  "seguradora": "string",
  "tomador": "string",
  "segurados": "string",
  "lmg_total": "string",
  "premio_total": "string",
  "vigencia_inicio": "DD/MM/AAAA",
  "vigencia_fim": "DD/MM/AAAA",
  "data_retroatividade": "string",
  "coberturas": [
    {
      "nome": "string",
      "limite": "string",
      "franquia_pos": "string"
    }
  ],
  "exclusoes_relevantes": [
    "string"
  ]
}

REGRAS:

1. Retorne SOMENTE JSON válido.
2. Não escreva introdução.
3. Não escreva explicações.
4. Não escreva comentários.
5. Não use Markdown.
6. Não utilize ```json.
7. Não invente informações.
8. Se uma informação não estiver presente, utilize "Não identificado".
9. Preserve valores monetários.
10. Preserve números de apólice.
11. Para datas, utilize DD/MM/AAAA.
12. Liste todas as coberturas relevantes.
13. Liste as principais exclusões.
14. Não confunda LMG com limite de cobertura.
15. Não confunda prêmio com limite de indenização.
"""

    texto_enviado = texto_pdf[:15000]

    try:

        response = client.chat.completions.create(

            model=model_name,

            messages=[
                {
                    "role": "system",
                    "content": prompt_sistema
                },
                {
                    "role": "user",
                    "content": (
                        "Analise o seguinte documento de seguro "
                        "e extraia os dados solicitados.\n\n"
                        "DOCUMENTO:\n\n"
                        f"{texto_enviado}"
                    )
                }
            ],

            temperature=0.0,

            reasoning_effort="low",

            include_reasoning=False,

            response_format={
                "type": "json_object"
            }
        )

    except Exception as e:

        raise Exception(
            f"Erro na chamada do Agente 1 / Groq:\n\n{str(e)}"
        )

    conteudo = response.choices[0].message.content

    if not conteudo:

        raise ValueError(
            "O Agente 1 retornou uma resposta vazia."
        )

    dados_dict = limpar_e_extrair_json(conteudo)

    try:

        return ApoliceDO(**dados_dict)

    except Exception as e:

        raise ValueError(
            "O JSON retornado pela IA não corresponde "
            f"ao modelo esperado.\n\n{str(e)}"
        )


# =============================================================================
# AGENTE 2 - ANALISTA DE COBERTURAS
# =============================================================================

def agente_2_analista_coberturas(
    dados_apolice: ApoliceDO,
    client: Groq,
    model_name: str
) -> str:

    prompt_sistema = """
Você é um Subscritor Sênior especialista em seguros D&O.

Analise tecnicamente os dados estruturados da apólice.

Estruture sua resposta:

### 1. Avaliação do LMG

### 2. Coberturas

### 3. Franquias e POS

### 4. Pontos de Atenção

### 5. Garantias Identificadas

Baseie-se exclusivamente nos dados fornecidos.
Não invente informações.
Não considere informação ausente como inexistência de cobertura.
"""

    dados_json_str = pydantic_to_json(
        dados_apolice
    )

    try:

        response = client.chat.completions.create(

            model=model_name,

            messages=[
                {
                    "role": "system",
                    "content": prompt_sistema
                },
                {
                    "role": "user",
                    "content": (
                        "Dados estruturados da apólice:\n\n"
                        f"{dados_json_str}"
                    )
                }
            ],

            temperature=0.2,

            reasoning_effort="low",

            include_reasoning=False
        )

    except Exception as e:

        raise Exception(
            f"Erro na chamada do Agente 2 / Groq:\n\n{str(e)}"
        )

    return response.choices[0].message.content


# =============================================================================
# AGENTE 3 - AUDITOR
# =============================================================================

def agente_3_auditor_riscos(
    resultados_gerais: dict,
    client: Groq,
    model_name: str
) -> str:

    prompt_sistema = """
Você é um Auditor Independente de Riscos Corporativos
especialista em seguros D&O.

Compare duas ou mais apólices de D&O.

Estruture a resposta:

### 1. Resumo Executivo da Comparação

### 2. Principais Lacunas de Cobertura (Gaps)

### 3. Exclusões Severas ou Atípicas de Atenção

### 4. Diferenças de Limites, Franquias e Condições

### 5. Recomendação Técnica para Tomada de Decisão

Não invente dados.
Diferencie dados encontrados de interpretações.
"""

    contexto = json.dumps(
        {
            k: pydantic_to_dict(v["dados"])
            for k, v in resultados_gerais.items()
        },
        ensure_ascii=False,
        indent=2
    )

    try:

        response = client.chat.completions.create(

            model=model_name,

            messages=[
                {
                    "role": "system",
                    "content": prompt_sistema
                },
                {
                    "role": "user",
                    "content": (
                        "Dados das apólices para comparação:\n\n"
                        f"{contexto}"
                    )
                }
            ],

            temperature=0.2,

            reasoning_effort="low",

            include_reasoning=False
        )

    except Exception as e:

        raise Exception(
            f"Erro na chamada do Agente 3 / Groq:\n\n{str(e)}"
        )

    return response.choices[0].message.content


# =============================================================================
# FUNÇÕES PARA O PDF
# =============================================================================

def escapar_pdf(texto):
    """
    Escapa caracteres que podem interferir no Paragraph do ReportLab.
    """

    if texto is None:
        return ""

    texto = str(texto)

    texto = (
        texto
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    return texto


# =============================================================================
# CONVERSÃO DO TEXTO DO AGENTE PARA ELEMENTOS PDF
# =============================================================================

def texto_agente_para_pdf(
    texto,
    styles
):

    elementos = []

    if not texto:
        return elementos

    linhas = texto.split("\n")

    for linha in linhas:

        linha = linha.strip()

        if not linha:
            elementos.append(
                Spacer(1, 0.15 * cm)
            )
            continue

        # ---------------------------------------------------------------
        # Títulos Markdown
        # ---------------------------------------------------------------

        if linha.startswith("### "):

            titulo = linha[4:].strip()

            elementos.append(
                Paragraph(
                    escapar_pdf(titulo),
                    styles["SubSection"]
                )
            )

            elementos.append(
                Spacer(1, 0.10 * cm)
            )

        elif linha.startswith("## "):

            titulo = linha[3:].strip()

            elementos.append(
                Paragraph(
                    escapar_pdf(titulo),
                    styles["Section"]
                )
            )

        elif linha.startswith("# "):

            titulo = linha[2:].strip()

            elementos.append(
                Paragraph(
                    escapar_pdf(titulo),
                    styles["Section"]
                )
            )

        # ---------------------------------------------------------------
        # Bullets
        # ---------------------------------------------------------------

        elif linha.startswith("- "):

            texto = linha[2:].strip()

            elementos.append(
                Paragraph(
                    "• " + escapar_pdf(texto),
                    styles["Body"]
                )
            )

        # ---------------------------------------------------------------
        # Texto normal
        # ---------------------------------------------------------------

        else:

            elementos.append(
                Paragraph(
                    escapar_pdf(linha),
                    styles["Body"]
                )
            )

    return elementos


# =============================================================================
# CABEÇALHO E RODAPÉ DO PDF
# =============================================================================

def adicionar_cabecalho_rodape(
    canvas,
    doc
):

    canvas.saveState()

    largura, altura = A4

    # ---------------------------------------------------------------
    # Cabeçalho
    # ---------------------------------------------------------------

    canvas.setStrokeColor(
        colors.HexColor("#D9E2F3")
    )

    canvas.line(
        1.5 * cm,
        altura - 1.5 * cm,
        largura - 1.5 * cm,
        altura - 1.5 * cm
    )

    canvas.setFont(
        PDF_FONT,
        8
    )

    canvas.setFillColor(
        colors.HexColor("#666666")
    )

    canvas.drawString(
        1.5 * cm,
        altura - 1.2 * cm,
        f"{NOME_APLICATIVO} - {SUBTITULO_APLICATIVO}"
    )

    # ---------------------------------------------------------------
    # Rodapé
    # ---------------------------------------------------------------

    canvas.line(
        1.5 * cm,
        1.3 * cm,
        largura - 1.5 * cm,
        1.3 * cm
    )

    canvas.setFont(
        PDF_FONT,
        8
    )

    canvas.drawString(
        1.5 * cm,
        0.8 * cm,
        f"{NOME_APLICATIVO} | Relatório gerado automaticamente"
    )

    canvas.drawRightString(
        largura - 1.5 * cm,
        0.8 * cm,
        f"Página {doc.page}"
    )

    canvas.restoreState()


# =============================================================================
# GERAÇÃO DO RELATÓRIO PDF
# =============================================================================

def gerar_relatorio_pdf(
    resultados,
    relatorio_auditoria,
    modelo_utilizado
):

    buffer = BytesIO()

    doc = SimpleDocTemplate(

        buffer,

        pagesize=A4,

        rightMargin=1.5 * cm,

        leftMargin=1.5 * cm,

        topMargin=2.0 * cm,

        bottomMargin=1.8 * cm,

        title=f"{NOME_APLICATIVO} - Relatório de Análise e Auditoria de Apólices D&O",

        author=AUTOR_RELATORIO
    )


    # =========================================================================
    # ESTILOS
    # =========================================================================

    styles = getSampleStyleSheet()


    styles.add(
        ParagraphStyle(
            name="CapaTitulo",
            fontName=PDF_FONT_BOLD,
            fontSize=24,
            leading=29,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17365D"),
            spaceAfter=20
        )
    )


    styles.add(
        ParagraphStyle(
            name="CapaSubtitulo",
            fontName=PDF_FONT,
            fontSize=13,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#555555"),
            spaceAfter=15
        )
    )


    styles.add(
        ParagraphStyle(
            name="Section",
            fontName=PDF_FONT_BOLD,
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#17365D"),
            spaceBefore=14,
            spaceAfter=10
        )
    )


    styles.add(
        ParagraphStyle(
            name="SubSection",
            fontName=PDF_FONT_BOLD,
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1F4E79"),
            spaceBefore=10,
            spaceAfter=6
        )
    )


    styles.add(
        ParagraphStyle(
            name="Body",
            fontName=PDF_FONT,
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#222222"),
            alignment=TA_LEFT,
            spaceAfter=5
        )
    )


    styles.add(
        ParagraphStyle(
            name="Small",
            fontName=PDF_FONT,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#555555")
        )
    )


    styles.add(
        ParagraphStyle(
            name="Tabela",
            fontName=PDF_FONT,
            fontSize=7.5,
            leading=10,
            textColor=colors.black
        )
    )


    styles.add(
        ParagraphStyle(
            name="TabelaCabecalho",
            fontName=PDF_FONT_BOLD,
            fontSize=7.5,
            leading=10,
            textColor=colors.white
        )
    )


    # =========================================================================
    # ELEMENTOS
    # =========================================================================

    story = []


    # =========================================================================
    # CAPA
    # =========================================================================

    story.append(
        Spacer(1, 3 * cm)
    )


    story.append(
        Paragraph(
            f"🛡️ {NOME_APLICATIVO.upper()}",
            styles["CapaTitulo"]
        )
    )


    story.append(
        Paragraph(
            "Relatório de Análise e Auditoria de Apólices D&O",
            styles["CapaSubtitulo"]
        )
    )


    story.append(
        Spacer(1, 1 * cm)
    )


    story.append(
        Paragraph(
            f"<b>Data de geração:</b> "
            f"{datetime.now().strftime('%d/%m/%Y %H:%M')}",
            styles["Body"]
        )
    )


    story.append(
        Paragraph(
            f"<b>Modelo de IA:</b> "
            f"{escapar_pdf(modelo_utilizado)}",
            styles["Body"]
        )
    )


    story.append(
        Paragraph(
            f"<b>Apólices analisadas:</b> "
            f"{len(resultados)}",
            styles["Body"]
        )
    )


    # -------------------------------------------------------------------------
    # IDENTIFICAÇÃO DO PROJETO E PARTICIPANTES
    # Mantém a estrutura original da capa e acrescenta a identificação da equipe.
    # -------------------------------------------------------------------------

    story.append(Spacer(1, 0.5 * cm))

    capa_projeto = Table(
        [
            [Paragraph("<b>PROJETO</b>", styles["TabelaCabecalho"])],
            [Paragraph(escapar_pdf(NOME_APLICATIVO), styles["Body"])],
            [Paragraph("<b>PARTICIPANTES</b>", styles["TabelaCabecalho"])],
            [Paragraph(escapar_pdf(PARTICIPANTES_PROJETO[0]), styles["Body"])],
            [Paragraph(escapar_pdf(PARTICIPANTES_PROJETO[1]), styles["Body"])],
        ],
        colWidths=[15.8 * cm]
    )

    capa_projeto.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("TEXTCOLOR", (0, 2), (-1, 2), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#B7C9E2")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2F3")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    story.append(capa_projeto)


    story.append(
        Spacer(1, 1.0 * cm)
    )


    story.append(
        Paragraph(
            "Este relatório foi produzido automaticamente a partir "
            f"dos documentos carregados no sistema {NOME_APLICATIVO}. "
            "As informações apresentadas devem ser verificadas "
            "contra os documentos originais antes de qualquer utilização "
            "operacional ou contratual.",
            styles["Small"]
        )
    )


    story.append(
        PageBreak()
    )


    # =========================================================================
    # 1. RESUMO DAS APÓLICES
    # =========================================================================

    story.append(
        Paragraph(
            "1. Resumo das Apólices Analisadas",
            styles["Section"]
        )
    )


    resumo_data = [

        [
            Paragraph("Apólice / Arquivo", styles["TabelaCabecalho"]),
            Paragraph("Seguradora", styles["TabelaCabecalho"]),
            Paragraph("Tomador", styles["TabelaCabecalho"]),
            Paragraph("LMG", styles["TabelaCabecalho"]),
            Paragraph("Prêmio", styles["TabelaCabecalho"]),
        ]
    ]


    for filename, info in resultados.items():

        dados = info["dados"]

        resumo_data.append(
            [
                Paragraph(
                    escapar_pdf(filename),
                    styles["Tabela"]
                ),

                Paragraph(
                    escapar_pdf(dados.seguradora),
                    styles["Tabela"]
                ),

                Paragraph(
                    escapar_pdf(dados.tomador),
                    styles["Tabela"]
                ),

                Paragraph(
                    escapar_pdf(dados.lmg_total),
                    styles["Tabela"]
                ),

                Paragraph(
                    escapar_pdf(dados.premio_total),
                    styles["Tabela"]
                )
            ]
        )


    tabela_resumo = Table(
        resumo_data,
        colWidths=[
            4.0 * cm,
            3.3 * cm,
            4.0 * cm,
            2.8 * cm,
            2.5 * cm
        ],
        repeatRows=1
    )


    tabela_resumo.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#17365D")
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#BBBBBB")
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP"
                ),

                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor("#F3F6FA")
                    ]
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),
            ]
        )
    )


    story.append(
        tabela_resumo
    )


    story.append(
        Spacer(1, 0.5 * cm)
    )


    # =========================================================================
    # 2. DETALHAMENTO DE CADA APÓLICE
    # =========================================================================

    story.append(
        Paragraph(
            "2. Detalhamento das Apólices",
            styles["Section"]
        )
    )


    for numero, (filename, info) in enumerate(
        resultados.items(),
        start=1
    ):

        dados = info["dados"]


        story.append(
            Paragraph(
                f"2.{numero}. {escapar_pdf(filename)}",
                styles["SubSection"]
            )
        )


        # ---------------------------------------------------------------------
        # Dados gerais
        # ---------------------------------------------------------------------

        dados_tabela = [

            [
                Paragraph("Campo", styles["TabelaCabecalho"]),
                Paragraph("Informação", styles["TabelaCabecalho"])
            ],

            [
                Paragraph(
                    "Número da Apólice / Proposta",
                    styles["Tabela"]
                ),
                Paragraph(
                    escapar_pdf(dados.numero_apolice),
                    styles["Tabela"]
                )
            ],

            [
                Paragraph(
                    "Seguradora",
                    styles["Tabela"]
                ),
                Paragraph(
                    escapar_pdf(dados.seguradora),
                    styles["Tabela"]
                )
            ],

            [
                Paragraph(
                    "Tomador / Estipulante",
                    styles["Tabela"]
                ),
                Paragraph(
                    escapar_pdf(dados.tomador),
                    styles["Tabela"]
                )
            ],

            [
                Paragraph(
                    "Segurados",
                    styles["Tabela"]
                ),
                Paragraph(
                    escapar_pdf(dados.segurados),
                    styles["Tabela"]
                )
            ],

            [
                Paragraph(
                    "LMG",
                    styles["Tabela"]
                ),
                Paragraph(
                    escapar_pdf(dados.lmg_total),
                    styles["Tabela"]
                )
            ],

            [
                Paragraph(
                    "Prêmio Total",
                    styles["Tabela"]
                ),
                Paragraph(
                    escapar_pdf(dados.premio_total),
                    styles["Tabela"]
                )
            ],

            [
                Paragraph(
                    "Início da Vigência",
                    styles["Tabela"]
                ),
                Paragraph(
                    escapar_pdf(dados.vigencia_inicio),
                    styles["Tabela"]
                )
            ],

            [
                Paragraph(
                    "Fim da Vigência",
                    styles["Tabela"]
                ),
                Paragraph(
                    escapar_pdf(dados.vigencia_fim),
                    styles["Tabela"]
                )
            ],

            [
                Paragraph(
                    "Retroatividade",
                    styles["Tabela"]
                ),
                Paragraph(
                    escapar_pdf(dados.data_retroatividade),
                    styles["Tabela"]
                )
            ],
        ]


        tabela_dados = Table(
            dados_tabela,
            colWidths=[
                5.5 * cm,
                11.0 * cm
            ],
            repeatRows=1
        )


        tabela_dados.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#1F4E79")
                    ),

                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.4,
                        colors.HexColor("#CCCCCC")
                    ),

                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP"
                    ),

                    (
                        "BACKGROUND",
                        (0, 1),
                        (0, -1),
                        colors.HexColor("#EAF0F7")
                    ),

                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        5
                    ),

                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        5
                    ),

                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        5
                    ),

                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        5
                    ),
                ]
            )
        )


        story.append(
            tabela_dados
        )


        story.append(
            Spacer(1, 0.4 * cm)
        )


        # ---------------------------------------------------------------------
        # COBERTURAS
        # ---------------------------------------------------------------------

        story.append(
            Paragraph(
                "Coberturas e Garantias",
                styles["SubSection"]
            )
        )


        if dados.coberturas:

            cobertura_data = [

                [
                    Paragraph(
                        "Cobertura",
                        styles["TabelaCabecalho"]
                    ),

                    Paragraph(
                        "Limite",
                        styles["TabelaCabecalho"]
                    ),

                    Paragraph(
                        "Franquia / POS",
                        styles["TabelaCabecalho"]
                    )
                ]
            ]


            for cobertura in dados.coberturas:

                cobertura_data.append(
                    [
                        Paragraph(
                            escapar_pdf(
                                cobertura.nome
                            ),
                            styles["Tabela"]
                        ),

                        Paragraph(
                            escapar_pdf(
                                cobertura.limite
                            ),
                            styles["Tabela"]
                        ),

                        Paragraph(
                            escapar_pdf(
                                cobertura.franquia_pos
                            ),
                            styles["Tabela"]
                        )
                    ]
                )


            tabela_coberturas = Table(
                cobertura_data,
                colWidths=[
                    7.0 * cm,
                    4.5 * cm,
                    5.0 * cm
                ],
                repeatRows=1
            )


            tabela_coberturas.setStyle(
                TableStyle(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, 0),
                            colors.HexColor("#17365D")
                        ),

                        (
                            "GRID",
                            (0, 0),
                            (-1, -1),
                            0.4,
                            colors.HexColor("#BBBBBB")
                        ),

                        (
                            "VALIGN",
                            (0, 0),
                            (-1, -1),
                            "TOP"
                        ),

                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [
                                colors.white,
                                colors.HexColor("#F5F7FA")
                            ]
                        ),

                        (
                            "LEFTPADDING",
                            (0, 0),
                            (-1, -1),
                            5
                        ),

                        (
                            "RIGHTPADDING",
                            (0, 0),
                            (-1, -1),
                            5
                        ),

                        (
                            "TOPPADDING",
                            (0, 0),
                            (-1, -1),
                            5
                        ),

                        (
                            "BOTTOMPADDING",
                            (0, 0),
                            (-1, -1),
                            5
                        ),
                    ]
                )
            )


            story.append(
                tabela_coberturas
            )

        else:

            story.append(
                Paragraph(
                    "Nenhuma cobertura foi identificada.",
                    styles["Body"]
                )
            )


        # ---------------------------------------------------------------------
        # EXCLUSÕES
        # ---------------------------------------------------------------------

        story.append(
            Paragraph(
                "Exclusões Relevantes",
                styles["SubSection"]
            )
        )


        if dados.exclusoes_relevantes:

            for exclusao in dados.exclusoes_relevantes:

                story.append(
                    Paragraph(
                        "• " + escapar_pdf(exclusao),
                        styles["Body"]
                    )
                )

        else:

            story.append(
                Paragraph(
                    "Nenhuma exclusão relevante foi identificada "
                    "nos dados extraídos.",
                    styles["Body"]
                )
            )


        # ---------------------------------------------------------------------
        # PARECER DO AGENTE 2
        # ---------------------------------------------------------------------

        story.append(
            Paragraph(
                "Parecer Técnico - Agente Subscritor",
                styles["SubSection"]
            )
        )


        elementos_agente2 = texto_agente_para_pdf(
            info["parecer_coberturas"],
            styles
        )


        story.extend(
            elementos_agente2
        )


        story.append(
            Spacer(1, 0.4 * cm)
        )


        if numero < len(resultados):

            story.append(
                PageBreak()
            )


    # =========================================================================
    # 3. AUDITORIA GERAL
    # =========================================================================

    story.append(
        PageBreak()
    )


    story.append(
        Paragraph(
            "3. Auditoria de Riscos e Análise Comparativa",
            styles["Section"]
        )
    )


    if relatorio_auditoria:

        elementos_auditoria = texto_agente_para_pdf(
            relatorio_auditoria,
            styles
        )

        story.extend(
            elementos_auditoria
        )

    else:

        story.append(
            Paragraph(
                "O relatório de auditoria não foi gerado.",
                styles["Body"]
            )
        )


    # =========================================================================
    # 4. OBSERVAÇÕES
    # =========================================================================

    story.append(
        Spacer(1, 0.8 * cm)
    )


    story.append(
        Paragraph(
            "4. Observações e Limitações",
            styles["Section"]
        )
    )


    observacoes = [
        "As informações foram extraídas automaticamente dos documentos fornecidos.",

        "A ausência de determinada informação na extração não significa necessariamente que ela não exista na apólice.",

        "As análises dos agentes de IA têm caráter auxiliar e devem ser confrontadas com os documentos originais.",

        "O relatório não substitui a análise jurídica, atuarial, técnica ou de subscrição realizada por profissional habilitado.",

        "Recomenda-se verificar valores, datas, limites, franquias, exclusões e condições especiais diretamente na documentação original."
    ]


    for observacao in observacoes:

        story.append(
            Paragraph(
                "• " + escapar_pdf(observacao),
                styles["Body"]
            )
        )


    # =========================================================================
    # GERAÇÃO
    # =========================================================================

    doc.build(
        story,
        onFirstPage=adicionar_cabecalho_rodape,
        onLaterPages=adicionar_cabecalho_rodape
    )


    buffer.seek(0)

    return buffer.getvalue()


# =============================================================================
# INTERFACE
# =============================================================================

st.title(
    f"🛡️ {NOME_APLICATIVO} - {SUBTITULO_APLICATIVO}"
)


st.markdown(
    """
    Plataforma de análise e auditoria de apólices D&O do projeto **Insight AI**,
    impulsionada por agentes especialistas de IA via
    **Groq Cloud**.
    """
)


# =============================================================================
# BARRA LATERAL
# =============================================================================

st.sidebar.header(
    "🔑 Configuração da API"
)


api_key_input = st.sidebar.text_input(
    "Groq API Key",
    value=os.getenv("GROQ_API_KEY", ""),
    type="password",
    help=(
        "Preferencialmente defina GROQ_API_KEY como variável de ambiente. "
        "A chave não é incluída no relatório nem nos arquivos exportados."
    )
)


modelo_selecionado = st.sidebar.selectbox(
    "Modelo Groq",
    options=MODELOS_DISPONIVEIS,
    index=0
)


st.sidebar.markdown("---")


st.sidebar.markdown(
    "### 🤖 Agentes Ativos:"
)

st.sidebar.markdown(
    "- **Agente 1:** Extrator & Normalizador"
)

st.sidebar.markdown(
    "- **Agente 2:** Analista de Coberturas"
)

st.sidebar.markdown(
    "- **Agente 3:** Auditor de Riscos"
)


st.sidebar.markdown("---")


st.sidebar.info(
    f"Modelo ativo:\n\n`{modelo_selecionado}`"
)


# =============================================================================
# UPLOAD
# =============================================================================

uploaded_files = st.file_uploader(
    "Selecione duas ou mais apólices em PDF ou imagem (PNG/JPG/JPEG)",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=True,
    help="Para comparação, carregue pelo menos duas apólices."
)


# =============================================================================
# EXECUÇÃO
# =============================================================================

if uploaded_files:

    st.info(
        f"📁 **{len(uploaded_files)}** ficheiro(s) carregado(s)."
    )


    if st.button(
        "🚀 Executar Análise Multi-Agente",
        type="primary"
    ):

        if len(uploaded_files) < 2:
            st.error(
                "⚠️ O Projeto Final exige comparação entre pelo menos duas apólices. "
                "Carregue 2 ou mais documentos."
            )
            st.stop()

        if not api_key_input:

            st.error(
                "⚠️ Informe a Groq API Key."
            )

            st.stop()


        try:

            client = Groq(
                api_key=api_key_input
            )

        except Exception as e:

            st.error(
                f"Erro ao inicializar Groq:\n\n{str(e)}"
            )

            st.stop()


        resultados = {}


        progress_bar = st.progress(0)

        status_text = st.empty()


        total_passos = (
            len(uploaded_files) * 2 + 1
        )

        passo_atual = 0


        # =====================================================================
        # PROCESSAMENTO DOS DOCUMENTOS
        # =====================================================================

        for file in uploaded_files:

            try:

                # -------------------------------------------------------------
                # AGENTE 1
                # -------------------------------------------------------------

                status_text.text(
                    f"🤖 Agente 1 - Extraindo dados: "
                    f"{file.name}"
                )


                texto = extrair_texto_documento(
                    file
                )


                dados_apolice = agente_1_extrator(
                    texto,
                    client,
                    modelo_selecionado
                )


                passo_atual += 1


                progress_bar.progress(
                    min(
                        passo_atual / total_passos,
                        1.0
                    )
                )


                # -------------------------------------------------------------
                # AGENTE 2
                # -------------------------------------------------------------

                status_text.text(
                    f"🤖 Agente 2 - Analisando coberturas: "
                    f"{file.name}"
                )


                parecer_coberturas = (
                    agente_2_analista_coberturas(
                        dados_apolice,
                        client,
                        modelo_selecionado
                    )
                )


                passo_atual += 1


                progress_bar.progress(
                    min(
                        passo_atual / total_passos,
                        1.0
                    )
                )


                # -------------------------------------------------------------
                # SALVA RESULTADO
                # -------------------------------------------------------------

                resultados[file.name] = {

                    "dados": dados_apolice,

                    "parecer_coberturas": (
                        parecer_coberturas
                    )
                }


            except Exception as e:

                st.error(
                    f"""
❌ Erro no ficheiro **{file.name}**

{str(e)}
"""
                )


        # =====================================================================
        # AGENTE 3
        # =====================================================================

        if resultados:

            try:

                status_text.text(
                    "🤖 Agente 3 - Auditoria comparativa..."
                )


                relatorio_auditoria = (
                    agente_3_auditor_riscos(
                        resultados,
                        client,
                        modelo_selecionado
                    )
                )


                progress_bar.progress(1.0)


                st.session_state["resultados"] = (
                    resultados
                )


                st.session_state["relatorio_auditoria"] = (
                    relatorio_auditoria
                )


                status_text.text(
                    "✅ Análise concluída com sucesso!"
                )


            except Exception as e:

                st.error(
                    f"""
❌ Erro no Agente 3:

{str(e)}
"""
                )


# =============================================================================
# EXIBIÇÃO DOS RESULTADOS
# =============================================================================

if (
    "resultados" in st.session_state
    and st.session_state["resultados"]
):

    resultados = st.session_state["resultados"]


    # =========================================================================
    # TABELA COMPARATIVA
    # =========================================================================

    st.markdown("---")


    st.header(
        "📊 Tabela Comparativa Estruturada"
    )


    dados_gerais = {

        "Campo / Informação": [

            "Nº da Apólice / Proposta",

            "Seguradora",

            "Tomador / Estipulante",

            "Segurados",

            "Limite Máximo de Garantia (LMG)",

            "Prémio Total",

            "Vigência",

            "Data de Retroatividade"
        ]
    }


    for filename, info in resultados.items():

        dados = info["dados"]


        dados_gerais[filename] = [

            dados.numero_apolice,

            dados.seguradora,

            dados.tomador,

            dados.segurados,

            dados.lmg_total,

            dados.premio_total,

            (
                f"{dados.vigencia_inicio} "
                f"até "
                f"{dados.vigencia_fim}"
            ),

            dados.data_retroatividade
        ]


    st.dataframe(
        pd.DataFrame(dados_gerais),
        use_container_width=True,
        hide_index=True
    )


    # =========================================================================
    # ANÁLISE POR APÓLICE
    # =========================================================================

    st.markdown("---")


    st.header(
        "🔍 Análise Técnica de Coberturas "
        "(Agente Subscritor)"
    )


    tabs = st.tabs(
        list(resultados.keys())
    )


    for tab, (filename, info) in zip(
        tabs,
        resultados.items()
    ):

        with tab:

            dados = info["dados"]


            col1, col2 = st.columns(
                [1, 1]
            )


            # -----------------------------------------------------------------
            # COBERTURAS
            # -----------------------------------------------------------------

            with col1:

                st.markdown(
                    "#### Coberturas & Garantias"
                )


                if dados.coberturas:

                    cob_list = [

                        {
                            "Cobertura": cobertura.nome,

                            "Limite": cobertura.limite,

                            "POS/Franquia": (
                                cobertura.franquia_pos
                            )
                        }

                        for cobertura in dados.coberturas
                    ]


                    st.dataframe(
                        pd.DataFrame(cob_list),
                        use_container_width=True,
                        hide_index=True
                    )

                else:

                    st.write(
                        "Sem coberturas listadas."
                    )


            # -----------------------------------------------------------------
            # AGENTE 2
            # -----------------------------------------------------------------

            with col2:

                st.markdown(
                    "#### Parecer do Agente Subscritor"
                )


                st.info(
                    info["parecer_coberturas"]
                )


    # =========================================================================
    # AGENTE 3
    # =========================================================================

    if "relatorio_auditoria" in st.session_state:

        st.markdown("---")


        st.header(
            "⚖️ Auditoria de Riscos e Análise de Gaps"
        )


        st.markdown(
            st.session_state[
                "relatorio_auditoria"
            ]
        )


    # =========================================================================
    # GERAÇÃO DO PDF
    # =========================================================================

    st.markdown("---")


    st.header(
        "📄 Relatório Profissional"
    )


    st.markdown(
        """
        O relatório PDF reúne os dados estruturados das apólices,
        as coberturas identificadas, os pareceres dos agentes e
        a auditoria comparativa.
        """
    )


    if st.button(
        "📄 Gerar Relatório PDF",
        type="primary"
    ):

        try:

            with st.spinner(
                "Gerando relatório PDF..."
            ):

                pdf_bytes = gerar_relatorio_pdf(

                    resultados=resultados,

                    relatorio_auditoria=(
                        st.session_state.get(
                            "relatorio_auditoria",
                            ""
                        )
                    ),

                    modelo_utilizado=(
                        modelo_selecionado
                    )
                )


            st.success(
                "✅ Relatório PDF gerado com sucesso!"
            )


            nome_pdf = (
                "Relatorio_Insight_AI_DO_"
                + datetime.now().strftime(
                    "%Y%m%d_%H%M"
                )
                + ".pdf"
            )


            st.download_button(

                label="⬇️ Baixar Relatório PDF",

                data=pdf_bytes,

                file_name=nome_pdf,

                mime="application/pdf",

                type="primary"
            )


        except Exception as e:

            st.error(
                f"""
❌ Erro ao gerar o PDF:

{str(e)}
"""
            )


    # =========================================================================
    # EXPORTAÇÃO JSON
    # =========================================================================

    st.markdown("---")


    st.header(
        "📥 Exportação dos Dados"
    )


    json_export = {

        filename: pydantic_to_dict(
            info["dados"]
        )

        for filename, info in resultados.items()
    }


    st.download_button(

        label="📥 Baixar Dados Estruturados (JSON)",

        data=json.dumps(
            json_export,
            ensure_ascii=False,
            indent=4
        ),

        file_name="analise_multiagente_do.json",

        mime="application/json"
    )
