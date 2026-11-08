import uuid
from app.db import connection
from app.config import settings


def history(tenant: str, conversation_id: uuid.UUID):
    """Load recent chat turns for one tenant and conversation.

    Messages are selected newest first to enforce the memory limit, then
    reversed so the returned history is chronological for prompt construction.
    """
    with connection() as conn:
        rows = conn.execute(
            """SELECT role,content FROM (
            SELECT id,role,content,created_at FROM chat_messages
            WHERE tenant_id=%s AND conversation_id=%s ORDER BY id DESC LIMIT %s
        ) recent ORDER BY id ASC""",
            (tenant, conversation_id, settings().memory_turns * 2),
        ).fetchall()
    return rows


def save_turn(tenant: str, conversation_id: uuid.UUID, question: str, response: str):
    """Persist one user question and its assistant response as a conversation turn."""
    with connection() as conn:
        conn.execute(
            """INSERT INTO chat_messages(tenant_id,conversation_id,role,content)
                        VALUES (%s,%s,'user',%s),(%s,%s,'assistant',%s)""",
            (tenant, conversation_id, question, tenant, conversation_id, response),
        )


def list_messages(tenant: str, conversation_id: uuid.UUID):
    """Return up to 100 oldest-first messages for an existing conversation."""
    with connection() as conn:
        return conn.execute(
            """SELECT role,content,created_at FROM chat_messages
          WHERE tenant_id=%s AND conversation_id=%s ORDER BY id ASC LIMIT 100""",
            (tenant, conversation_id),
        ).fetchall()
