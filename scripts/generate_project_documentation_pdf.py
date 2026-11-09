from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = HexColor('#0F172A')
BLUE = HexColor('#2563EB')
TEAL = HexColor('#0F766E')
LIGHT = HexColor('#F8FAFC')
ACCENT = HexColor('#E0F2FE')
BORDER = HexColor('#CBD5E1')
TEXT = HexColor('#1F2937')


def stylesheet():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            'TitleDoc',
            parent=styles['Title'],
            fontName='Helvetica-Bold',
            fontSize=24,
            textColor=NAVY,
            leading=28,
            alignment=1,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            'SubtitleDoc',
            parent=styles['Title'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=BLUE,
            leading=18,
            alignment=1,
            spaceAfter=16,
        )
    )
    styles.add(
        ParagraphStyle(
            'SectionDoc',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=15,
            textColor=TEAL,
            leading=18,
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            'BodyDoc',
            parent=styles['BodyText'],
            fontName='Helvetica',
            fontSize=10.5,
            textColor=TEXT,
            leading=15,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            'TagDoc',
            parent=styles['BodyText'],
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=BLUE,
            leading=12,
            alignment=1,
            borderPadding=6,
            borderWidth=1,
            borderColor=BORDER,
            backColor=ACCENT,
        )
    )
    return styles


def title_page(story, styles):
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph('Enterprise Knowledge Assistant', styles['TitleDoc']))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph('Project Documentation', styles['SubtitleDoc']))
    story.append(Spacer(1, 0.6 * inch))

    badge_data = [[
        Paragraph('AI Knowledge Copilot', styles['TagDoc']),
        Paragraph('Document-grounded RAG', styles['TagDoc']),
        Paragraph('Enterprise Ready', styles['TagDoc']),
    ]]

    table = Table(badge_data, colWidths=[2.1 * inch, 2.3 * inch, 2.1 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(table)


def add_section(story, title, paragraphs, styles):
    story.append(Paragraph(title, styles['SectionDoc']))
    story.append(Spacer(1, 0.08 * inch))
    for para in paragraphs:
        story.append(Paragraph(para, styles['BodyDoc']))
        story.append(Spacer(1, 0.06 * inch))


def add_bullets(story, items, styles):
    bullet_style = ParagraphStyle(
        'BulletDoc',
        parent=styles['BodyDoc'],
        leftIndent=18,
        bulletIndent=0,
        firstLineIndent=0,
        spaceAfter=6,
    )
    for item in items:
        story.append(Paragraph(f'• {item}', bullet_style))


def build_tech_table():
    data = [
        ['Technology', 'Purpose'],
        ['Python + FastAPI', 'Backend APIs for chat, uploads, ingestion, approvals, and metrics.'],
        ['HTML, CSS, JavaScript', 'Browser dashboard with chat, upload, approvals, and history.'],
        ['LangGraph', 'Orchestrates retrieval, memory, guardrails, model calls, and HITL routing.'],
        ['Amazon S3', 'Durable document storage; browser uploads via presigned URLs.'],
        ['Amazon Bedrock Titan Embeddings V2', 'Converts document chunks and queries into semantic vectors.'],
        ['Amazon Bedrock Nova Lite', 'Generates responses using retrieved enterprise context.'],
        ['Pinecone', 'Stores embeddings and retrieves semantically similar chunks.'],
        ['Render PostgreSQL', 'Persists document metadata, conversations, approvals, feedback, and audit events.'],
        ['GlassFlow Rius', 'Traces instrumented agent, ingestion, model, and retrieval operations.'],
        ['Deterministic Python guardrails', 'Screens selected input/output patterns and risky prompts.'],
        ['Ingestion worker', 'Extracts text, chunks documents, creates embeddings, and updates indexes/status.'],
    ]

    table = Table(data, colWidths=[2.3 * inch, 4.0 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [LIGHT, colors.white]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    return table


def build_story():
    styles = stylesheet()
    story = []
    title_page(story, styles)

    add_section(story, '1. Project Goal', [
        'Build an enterprise-ready AI knowledge copilot that allows employees to ask natural-language questions about organizational documents and receive grounded, trusted answers instead of searching across scattered files.'
    ], styles)

    add_section(story, '2. Problem Statement', [
        'Organizational knowledge is scattered across policies, handbooks, procedures, and internal documents. Employees waste time searching for answers, and teams cannot reliably rely on a single source of truth.'
    ], styles)

    add_section(story, '3. Proposed Solution', [
        'Enterprise Knowledge Assistant provides a single chat interface over approved enterprise documents. Files are uploaded to Amazon S3, processed into searchable chunks, embedded into vector space, and retrieved through a RAG pipeline that grounds answers in source documents.'
    ], styles)

    add_section(story, '4. Real-World Use Cases', [], styles)
    add_bullets(story, [
        'HR and employee policies: leave, working hours, remote work, and onboarding rules.',
        'IT and operations: setup guides, troubleshooting steps, and deployment practices.',
        'Customer support: product, policy, and escalation information in one place.',
        'Internal knowledge discovery: search approved documentation without manual browsing.',
    ], styles)

    story.append(Spacer(1, 0.2 * inch))
    add_section(story, '5. Technology Stack & Responsibilities', [
        'Each component in the system has a clear role in the end-to-end flow. The design keeps the stack understandable while still supporting a realistic enterprise-style knowledge assistant.'
    ], styles)
    story.append(build_tech_table())

    story.append(Spacer(1, 0.2 * inch))
    add_section(story, '6. System Architecture', [
        'The application includes two primary paths: document ingestion and conversational question answering. Ingestion captures files, extracts chunks, generates embeddings, and stores vector indexes. Chat retrieves context and converts it into grounded responses.'
    ], styles)

    add_section(story, '7. Application Functionalities', [], styles)
    add_bullets(story, [
        'Document upload and ingestion',
        'Enterprise RAG chat',
        'Persistent conversation memory',
        'Input and output guardrails',
        'Human-in-the-loop approvals',
        'Audit trail and feedback',
    ], styles)

    add_section(story, '8. Design Notes', [
        'This version uses cleaner spacing, better typography, and a more polished color palette to improve readability compared with the original raw PDF export. It keeps the structure and content intact while making the document easier to scan and present.'
    ], styles)

    return story


def generate_pdf(output_path: str = 'docs/Enterprise-Knowledge-Assistant_Project_Documentation.pdf'):
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )
    doc.build(build_story())

    print(f'Generated {target}')


if __name__ == '__main__':
    generate_pdf()
