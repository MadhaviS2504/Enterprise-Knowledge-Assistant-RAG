# Enterprise Knowledge Assistant

## Project Documentation

### 1. Project Goal

Build an enterprise-ready AI knowledge copilot that allows employees to ask natural-language questions about organizational documents and receive grounded, trusted answers instead of searching across scattered files.

### 2. Problem Statement

Organizational knowledge is scattered across policies, handbooks, procedures, and internal documents. Employees waste time searching for answers, and teams cannot reliably rely on a single source of truth.

### 3. Proposed Solution

Enterprise Knowledge Assistant provides a single chat interface over approved enterprise documents. Files are uploaded to Amazon S3, processed into searchable chunks, embedded into vector space, and retrieved through a RAG pipeline that grounds answers in source documents.

### 4. Real-World Use Cases

- HR and employee policies: Ask about leave entitlement, working hours, remote work, and onboarding rules.
- IT and operations: Query setup guides, troubleshooting steps, and deployment practices.
- Customer support knowledge: Retrieve product, policy, and escalation information in one place.
- Internal knowledge discovery: Search approved documentation without manually browsing many files.

### 5. Technology Stack & Responsibilities

| Technology | Purpose |
| --- | --- |
| Python + FastAPI | Backend APIs for chat, uploads, ingestion triggers, approvals, and metrics. |
| HTML, CSS, JavaScript | Browser dashboard with chat, upload, approvals, and scrollable history. |
| LangGraph | Orchestrates retrieval, memory, guardrails, model calls, and HITL routing. |
| Amazon S3 | Durable document storage; browser uploads via presigned URLs. |
| Amazon Bedrock Titan Embeddings V2 | Converts document chunks and queries into semantic vectors (1,024 dimensions). |
| Amazon Bedrock Nova Lite | Generates responses using retrieved enterprise context. |
| Pinecone | Stores embeddings and retrieves semantically similar chunks. |
| Render PostgreSQL | Persists document metadata, conversations, approvals, feedback, and audit events. |
| GlassFlow Rius | Traces instrumented agent, ingestion, model, and retrieval operations. |
| Deterministic Python guardrails | Screens selected input/output patterns; not a substitute for full security controls. |
| Ingestion worker | Extracts text, chunks documents, creates embeddings, and updates indexes/status. |

### 6. System Architecture

Two primary paths drive the system: document ingestion and conversational question answering.

#### Ingestion flow

1. A user uploads a document to Amazon S3.
2. The ingestion worker extracts text and chunks it.
3. Embeddings are generated and stored in Pinecone.
4. Metadata and status are persisted in PostgreSQL.

#### Chat flow

1. A user asks a question in the browser.
2. FastAPI forwards the request to LangGraph.
3. The workflow checks memory, retrieves relevant context, and calls the LLM.
4. A grounded answer is returned with source context and audit data.

### 7. Application Functionalities

- Document upload and ingestion
- Enterprise RAG chat
- Persistent conversation memory
- Input and output guardrails
- Human-in-the-loop approvals
- Audit trail and feedback

### 8. Design Notes

This version uses cleaner spacing, better typography, and a more polished color palette to improve readability versus the original raw PDF export. The structure remains faithful to the project, while making the document easier to scan and present.

---

## Visual PDF Generation

The project now includes a dedicated generator that creates a cleaner, professionally styled PDF version of this document using ReportLab.

To generate the PDF:

```bash
python scripts/generate_project_documentation_pdf.py
```

This writes the output to:

```text
docs/Enterprise-Knowledge-Assistant_Project_Documentation.pdf
```
