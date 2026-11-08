"""S3 document ingestion worker for text extraction, embedding, and indexing."""

import io
import logging
from collections.abc import Iterator
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from app.aws import client, embed
from app.config import settings
from app.db import audit, connection
from app.observability import initialize, trace
from app.vector import upsert

initialize()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("atlas.worker")


def parse(blob: bytes, suffix: str) -> list[tuple[int, str]]:
    """Extract readable text and preserve its source page or document section.

    The returned `(page_number, text)` pairs let the search UI identify where a
    result came from. PDFs retain their real page numbers, DOCX files do not
    have reliable physical pages, and plain text is treated as one document page.
    Unknown file types are also decoded as UTF-8 so that simple text formats can
    use the same ingestion pipeline.
    """
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(blob))
        return [
            (page_number, page.extract_text() or "")
            for page_number, page in enumerate(reader.pages, start=1)
        ]

    if suffix == ".docx":
        document = Document(io.BytesIO(blob))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return [(1, text)]

    return [(1, blob.decode("utf-8"))]


def chunks(
    text: str,
    size: int = 1200,
    overlap: int = 180,
) -> Iterator[str]:
    """Split text into overlapping chunks suitable for embedding.

    Normalizing whitespace produces cleaner, smaller chunks without line-break
    artifacts. Overlap is intentional: it preserves context from words near a
    chunk boundary, making retrieval less dependent on where the text was split.
    """
    text = " ".join(text.split())
    position = 0

    while position < len(text):
        yield text[position : position + size]
        if position + size >= len(text):
            break

        position += size - overlap


@trace("process_s3_key")
def process_s3_key(key: str) -> None:
    """Download, validate, embed, index, and audit one document from S3.

    This function is safe to retry: a database row lock is used to claim the
    document, documents that are already ready are ignored, and an unsupported
    status is left unchanged. Processing status transitions provide visibility
    into ingestion progress and allow failed documents to be retried.
    """
    app_settings = settings()

    # Claim the document under a row lock so concurrent workers do not process
    # or embed the same S3 object at the same time. The status check makes the
    # operation naturally idempotent for completed, unknown, and already-running jobs.
    with connection() as conn:
        doc = conn.execute(
            "SELECT * FROM documents WHERE s3_key=%s FOR UPDATE",
            (key,),
        ).fetchone()

        if not doc or doc["status"] == "ready":
            return
        if doc["status"] not in ("pending", "failed"):
            return

        conn.execute(
            "UPDATE documents SET status='processing' WHERE id=%s",
            (doc["id"],),
        )

    try:
        # The size checks run before parsing and after reading so an oversized
        # object is rejected without consuming memory for the complete file.
        obj = client("s3").get_object(
            Bucket=app_settings.s3_bucket,
            Key=key,
        )
        if obj["ContentLength"] > app_settings.max_upload_bytes:
            raise ValueError("Upload too large")

        blob = obj["Body"].read(app_settings.max_upload_bytes + 1)
        if len(blob) > app_settings.max_upload_bytes:
            raise ValueError("Upload too large")

        # A PDF extension alone does not prove the file is valid. Checking the
        # signature catches mislabeled or corrupted files before text extraction.
        suffix = Path(key).suffix.lower()
        if suffix == ".pdf" and not blob.startswith(b"%PDF"):
            raise ValueError("Invalid PDF")

        # Convert the source format into page-text pairs, then divide every page
        # into searchable chunks while retaining the original page number.
        pages = parse(blob, suffix)
        parts: list[tuple[int, str]] = [
            (page_number, chunk)
            for page_number, page_text in pages
            for chunk in chunks(page_text)
        ]
        if not parts:
            raise ValueError("No extractable text; scanned PDFs need Textract OCR")

        # Each vector ID includes document ID, version, and chunk position. That
        # makes repeated ingestion replace the same vector records instead of
        # creating duplicates when a version is reprocessed.
        vectors: list[dict] = []
        for index, (page_number, chunk_text) in enumerate(parts):
            vectors.append(
                {
                    "id": (f'{doc["id"]}:' f'{doc["current_version"]}:' f"{index}"),
                    "values": embed(chunk_text),
                    "metadata": {
                        "document_id": str(doc["id"]),
                        "title": doc["title"],
                        "page": page_number,
                        "text": chunk_text,
                        "owner_sub": doc["owner_sub"],
                        "allowed_groups": doc["allowed_groups"],
                    },
                }
            )

        # Batching limits request size and metadata memory. It also makes failed
        # writes less likely to affect the entire document at once.
        for batch_start in range(0, len(vectors), 50):
            upsert(
                doc["tenant_id"],
                vectors[batch_start : batch_start + 50],
            )

        with connection() as conn:
            conn.execute(
                "UPDATE documents SET status='ready' WHERE id=%s",
                (doc["id"],),
            )
            audit(
                conn,
                doc["owner_sub"],
                doc["tenant_id"],
                "ingest_ready",
                {
                    "document_id": str(doc["id"]),
                    "chunks": len(parts),
                },
            )

        log.info(
            "Ingested document %s chunks=%d",
            doc["id"],
            len(parts),
        )

    except Exception:
        # Keep processing failures visible in the database while logging the full
        # exception for diagnostics. Raising afterward permits the worker platform
        # to retry or route the failed job according to its own policy.
        log.exception("Ingestion failed for key %s", key)
        with connection() as conn:
            conn.execute(
                "UPDATE documents SET status='failed' WHERE id=%s",
                (doc["id"],),
            )
        raise
