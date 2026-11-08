"""FastAPI application entry point for the Enterprise Knowledge Assistant.

This module configures web routes for document ingestion, chat, feedback,
approvals, health checks, and tenant-aware administration.
"""

import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.aws import client
from app.config import settings
from app.db import audit, connection
from app.demo_context import Principal, principal
from app.guardrails import classify_input
from app.memory import history, list_messages, save_turn
from app.observability import initialize
from app.rag import chat
from worker.ingest import process_s3_key

# Start tracing and application observability before serving requests.
initialize()

# Resolve project paths from this file so static and template locations work
# consistently when the application is started from any working directory.
BASE = Path(__file__).resolve().parent

# Create the FastAPI application and name it for API documentation.
app = FastAPI(title="Atlas Enterprise RAG", docs_url="/api/docs")

# Serve browser assets from the static directory at the /static URL prefix.
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

# Load HTML templates used by browser-facing FastAPI routes.
templates = Jinja2Templates(directory=BASE / "templates")


class Upload(BaseModel):
    """Request fields required to begin a document upload."""

    filename: str = Field(min_length=1, max_length=180)


class Ask(BaseModel):
    """Request fields for a tenant-scoped chat question."""

    question: str = Field(min_length=3, max_length=2000)
    conversation_id: uuid.UUID | None = None


class Feedback(BaseModel):
    """Optional feedback submitted by a user for a document response."""

    document_id: str | None = None
    rating: int = Field(ge=-1, le=1)
    note: str = Field(default="", max_length=500)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Render the main browser interface with configured deployment details."""

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "region": settings().aws_region,
            "mode": "single-workspace demo",
        },
    )


@app.get("/health/live")
def live():
    """Report whether the web process is running."""

    return {"status": "alive"}


@app.get("/health/ready")
def ready():
    """Verify database availability before reporting the application as ready."""

    try:
        # A minimal query checks whether FastAPI can establish a usable database
        # connection without loading or changing application data.
        with connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ready"}
    except Exception as exc:
        # Convert infrastructure failures into an HTTP readiness error so
        # orchestrators do not send traffic to an unavailable instance.
        raise HTTPException(503, "Database unavailable") from exc


@app.post("/api/documents/uploads")
def create_upload(
    body: Upload,
    p: Principal = Depends(principal),
):
    """Create a pending document record and return an S3 upload URL.

    The browser uploads directly to S3 with the returned presigned URL. The
    database record is created first so subsequent ingestion requests can
    identify and authorize the document.
    """

    # Normalize the extension and accept only document formats this worker can parse.
    suffix = Path(body.filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(400, "Allowed types: PDF, DOCX, TXT, MD")

    # Generate a unique document ID and never expose a caller-controlled object path.
    doc_id = str(uuid.uuid4())
    key = f"tenants/{p.tenant}/incoming/{doc_id}/v1{suffix}"

    # Insert pending status and ownership metadata in the same database transaction.
    with connection() as conn:
        conn.execute(
            """INSERT INTO documents(
                id, tenant_id, title, owner_sub, allowed_groups, s3_key,
                status, current_version
            )
            VALUES (%s,%s,%s,%s,%s,%s,'pending',1)""",
            (
                doc_id,
                p.tenant,
                body.filename,
                p.subject,
                ["workspace"],
                key,
            ),
        )
        # Audit the request so document creation is traceable by tenant and actor.
        audit(
            conn,
            p.subject,
            p.tenant,
            "upload_requested",
            {"document_id": doc_id},
        )

    # Create a five-minute presigned PUT operation so the browser does not need
    # AWS credentials while uploading the document directly to S3.
    url = client("s3").generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings().s3_bucket,
            "Key": key,
            "ContentType": "application/octet-stream",
        },
        ExpiresIn=300,
    )
    return {
        "document_id": doc_id,
        "upload_url": url,
        "headers": {"Content-Type": "application/octet-stream"},
    }


class CompleteUpload(BaseModel):
    """Request identifying the uploaded document that should be ingested."""

    document_id: uuid.UUID


@app.post("/api/documents/complete")
def complete_upload(
    body: CompleteUpload,
    p: Principal = Depends(principal),
):
    """Trigger synchronous ingestion for an uploaded document.

    Existing ready and processing states are handled before invoking the
    ingestion worker, preventing duplicate work after a completion callback.
    """

    # Find the S3 key only for a document belonging to the caller's tenant.
    with connection() as conn:
        row = conn.execute(
            """SELECT s3_key,status FROM documents
            WHERE id=%s AND tenant_id=%s""",
            (body.document_id, p.tenant),
        ).fetchone()

    # Do not disclose documents that exist outside the caller's tenant.
    if not row:
        raise HTTPException(404, "Document not found")

    # Returning ready is idempotent if the browser retries the completion request.
    if row["status"] == "ready":
        return {"status": "ready"}

    # Concurrent callbacks should not enqueue the same document twice.
    if row["status"] == "processing":
        raise HTTPException(409, "Already processing")

    try:
        # Process immediately here; worker retries can still be added later.
        process_s3_key(row["s3_key"])
    except Exception as exc:
        # Hide internal parser and service details while retaining server logs.
        raise HTTPException(
            502,
            "Ingestion failed. Check server logs and document status.",
        ) from exc

    return {"status": "ready"}


@app.get("/api/documents")
def documents(
    p: Principal = Depends(principal),
):
    """List documents the caller owns or can access through workspace groups."""

    # Use tenant and authorization filters in SQL so unrelated records are never
    # selected by this endpoint.
    with connection() as conn:
        rows = conn.execute(
            """SELECT id,title,status,current_version,created_at,allowed_groups
            FROM documents
            WHERE tenant_id=%s
              AND (allowed_groups && %s::text[] OR owner_sub=%s)
            ORDER BY created_at DESC LIMIT 100""",
            (p.tenant, list(p.groups), p.subject),
        ).fetchall()

    return {"documents": rows}


@app.post("/api/chat")
def ask(
    body: Ask,
    p: Principal = Depends(principal),
):
    """Answer a chat question after input guardrails, approvals, and history checks."""

    # Classify dangerous input separately so the rejection reason can be audited.
    reason = classify_input(body.question)
    if reason:
        with connection() as conn:
            audit(
                conn,
                p.subject,
                p.tenant,
                "guardrail_input_blocked",
                {"reason": reason},
            )
        raise HTTPException(
            400,
            f"Input guardrail blocked this request ({reason}).",
        )

    # Certain administrative or destructive-looking requests require an approval.
    if settings().hitl_enabled and any(
        term in body.question.lower()
        for term in ("delete", "export", "send to", "update policy")
    ):
        with connection() as conn:
            row = conn.execute(
                """INSERT INTO approvals(
                    tenant_id, requester, question, status
                )
                VALUES (%s,%s,%s,%s)
                RETURNING id""",
                (
                    p.tenant,
                    p.subject,
                    body.question,
                    "pending",
                ),
            ).fetchone()
            audit(
                conn,
                p.subject,
                p.tenant,
                "approval_requested",
                {"id": str(row["id"])},
            )

        # Return an explanation rather than executing the requested action.
        return {
            "answer": (
                "This request requires administrator approval before any action. "
                "Open the Approvals tab to review it."
            ),
            "sources": [],
            "status": "pending_approval",
            "approval_id": str(row["id"]),
        }

    # Reuse an existing conversation ID or create a new conversation identifier.
    conversation_id = body.conversation_id or uuid.uuid4()

    # Load recent conversation context so follow-up questions can be resolved.
    prior = history(p.tenant, conversation_id)

    # Run retrieval, answer generation, and output validation through the RAG graph.
    result = chat(p, body.question, prior)

    # Persist both sides of the turn after successful response generation.
    save_turn(
        p.tenant,
        conversation_id,
        body.question,
        result["answer"],
    )

    # Convert output-guardrail refusals into a distinct status and remove citations.
    if (
        result.get("answer")
        == "The response was blocked by the sensitive-data output guardrail."
    ):
        with connection() as conn:
            audit(
                conn,
                p.subject,
                p.tenant,
                "guardrail_output_blocked",
                {"conversation_id": str(conversation_id)},
            )
        result["status"] = "guardrail_blocked"
        result["sources"] = []

    # Expose the conversation ID so later requests can continue this conversation.
    return {**result, "conversation_id": str(conversation_id)}


@app.get("/api/conversations/{conversation_id}/messages")
def conversation_messages(
    conversation_id: uuid.UUID,
    p: Principal = Depends(principal),
):
    """Return stored messages for a conversation within the caller's tenant."""

    return {
        "conversation_id": str(conversation_id),
        "messages": list_messages(p.tenant, conversation_id),
    }


@app.post("/api/feedback")
def feedback(
    body: Feedback,
    p: Principal = Depends(principal),
):
    """Store a numeric response rating and optional written feedback."""

    with connection() as conn:
        conn.execute(
            """INSERT INTO feedback(tenant_id,actor,rating,note)
            VALUES (%s,%s,%s,%s)""",
            (p.tenant, p.subject, body.rating, body.note),
        )
    return {"saved": True}


@app.get("/api/admin/metrics")
def metrics(
    p: Principal = Depends(principal),
):
    """Summarize document and feedback counts for the caller's tenant."""

    with connection() as conn:
        docs = conn.execute(
            """SELECT status,count(*) AS total FROM documents
            WHERE tenant_id=%s GROUP BY status""",
            (p.tenant,),
        ).fetchall()
        fb = conn.execute(
            """SELECT rating,count(*) AS total FROM feedback
            WHERE tenant_id=%s GROUP BY rating""",
            (p.tenant,),
        ).fetchall()

    return {"documents": docs, "feedback": fb}


class ApprovalDecision(BaseModel):
    """Request selecting whether a pending approval is accepted or rejected."""

    approve: bool


@app.get("/api/approvals")
def list_approvals(
    p: Principal = Depends(principal),
):
    """List pending and previous approval requests for tenant administrators."""

    # Administrative review data must not be visible to standard users.
    if not p.admin:
        raise HTTPException(403, "Admin only")

    with connection() as conn:
        rows = conn.execute(
            """SELECT id,requester,question,status,reviewer,created_at,reviewed_at
            FROM approvals
            WHERE tenant_id=%s
            ORDER BY created_at DESC LIMIT 100""",
            (p.tenant,),
        ).fetchall()

    return {"approvals": rows}


@app.post("/api/approvals/{approval_id}/decision")
def decide(
    approval_id: uuid.UUID,
    body: ApprovalDecision,
    p: Principal = Depends(principal),
):
    """Approve or reject a pending request without executing its proposed action.

    This endpoint intentionally records an authorization decision only. Any
    future destructive operation must still be implemented and audited separately.
    """

    # Verify administrator privileges before changing approval state.
    if not p.admin:
        raise HTTPException(403, "Admin only")

    with connection() as conn:
        # Atomically approve/reject only a pending request in this tenant.
        row = conn.execute(
            """UPDATE approvals
            SET status=%s, reviewer=%s, reviewed_at=now()
            WHERE id=%s AND tenant_id=%s AND status='pending'
            RETURNING id""",
            (
                "approved" if body.approve else "rejected",
                p.subject,
                approval_id,
                p.tenant,
            ),
        ).fetchone()

        # Avoid duplicate decisions or updates belonging to another tenant.
        if not row:
            raise HTTPException(404, "Pending approval not found")

        audit(
            conn,
            p.subject,
            p.tenant,
            "approval_decided",
            {
                "id": str(approval_id),
                "approved": body.approve,
            },
        )

    return {
        "status": "approved" if body.approve else "rejected",
        "executed": False,
    }


@app.get("/api/admin/guardrails")
def guardrail_metrics(
    p: Principal = Depends(principal),
):
    """Report tenant-level deterministic input and output guardrail counts."""

    # Limit guardrail operational data to administrators.
    if not p.admin:
        raise HTTPException(403, "Admin only")

    with connection() as conn:
        rows = conn.execute(
            """SELECT action,count(*) AS total FROM audit_events
            WHERE tenant_id=%s
              AND action IN (
                'guardrail_input_blocked',
                'guardrail_output_blocked'
              )
            GROUP BY action ORDER BY action""",
            (p.tenant,),
        ).fetchall()

    return {
        "events": rows,
        "mode": "deterministic_demo",
        "managed_bedrock_guardrails": False,
    }
