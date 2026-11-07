"""Pinecone index initialization and tenant-aware vector operations."""

import logging
import time
from functools import lru_cache
from typing import Iterable, Sequence

from pinecone import Pinecone, ServerlessSpec

from app.config import settings
from app.observability import trace


log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def index():
    """Initialize, validate, and return the configured Pinecone index.

    Existing indexes are reused. If the index does not exist, it is created with
    the configured embedding dimension and cosine similarity metric. The function
    waits until Pinecone reports that the index is ready.
    """
    app_settings = settings()

    if not app_settings.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is missing from .env")
    if not app_settings.pinecone_index_name:
        raise RuntimeError("PINECONE_INDEX_NAME is missing from .env")

    pinecone = Pinecone(api_key=app_settings.pinecone_api_key)
    index_name = app_settings.pinecone_index_name

    # Describe rather than list indexes: this is more targeted and works for
    # both existing indexes and the missing-index case.
    try:
        index_info = pinecone.describe_index(index_name)
    except Exception as exc:
        # Only create an index when the API reports that it does not exist.
        if getattr(exc, "status", None) != 404:
            raise

        log.info(
            "Creating Pinecone index %s (dimension=%d, metric=cosine)",
            index_name,
            app_settings.embed_dim,
        )
        try:
            pinecone.create_index(
                name=index_name,
                dimension=app_settings.embed_dim,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=app_settings.pinecone_cloud,
                    region=app_settings.pinecone_region,
                ),
            )
        except Exception as create_exc:
            # Another process may have created the index concurrently.
            if getattr(create_exc, "status", None) != 409:
                raise

        index_info = pinecone.describe_index(index_name)

    if int(index_info.dimension) != app_settings.embed_dim:
        raise ValueError(
            f"Pinecone index {index_name} dimension={index_info.dimension}, "
            f"expected {app_settings.embed_dim}. Use a different index name or "
            "matching EMBED_DIM."
        )

    if str(index_info.metric).lower() != "cosine":
        raise ValueError(
            f"Pinecone index {index_name} must use cosine metric, "
            f"got {index_info.metric}"
        )

    deadline = time.monotonic() + app_settings.pinecone_ready_timeout
    while not pinecone.describe_index(index_name).status["ready"]:
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Pinecone index {index_name} was not ready within "
                f"{app_settings.pinecone_ready_timeout}s"
            )
        time.sleep(3)

    log.info("Pinecone index %s ready", index_name)
    return pinecone.Index(index_name)


def namespace(tenant: str) -> str:
    """Return the Pinecone namespace isolated for one tenant."""
    return f"tenant-{tenant}"


@trace("upsert")
def upsert(tenant: str, records: Sequence[dict]):
    """Insert or update vectors in the namespace belonging to a tenant."""
    return index().upsert(
        vectors=records,
        namespace=namespace(tenant),
    )


@trace("search")
def search(
    tenant: str,
    vector: list[float],
    groups: Iterable[str],
    owner: str,
    limit: int = 5,
) -> list[dict]:
    """Search for vectors accessible to a user within a tenant namespace.

    Results must either belong to an allowed group or be owned by the requesting
    user. Returned matches are converted to simple dictionaries for callers.
    """
    access_filter = {
        "$or": [
            {"allowed_groups": {"$in": list(groups)}},
            {"owner_sub": {"$eq": owner}},
        ]
    }

    result = index().query(
        vector=vector,
        top_k=limit,
        include_metadata=True,
        namespace=namespace(tenant),
        filter=access_filter,
    )

    return [
        {
            "id": match.id,
            "score": match.score,
            "metadata": match.metadata or {},
        }
        for match in result.matches
    ]


def delete_document(tenant: str, ids: Iterable[str]) -> None:
    """Delete vector records for the supplied document IDs in one tenant."""
    document_ids = list(ids)
    if document_ids:
        index().delete(
            ids=document_ids,
            namespace=namespace(tenant),
        )