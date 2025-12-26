"""Semantic search functionality for transcripts."""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from .models import Conversation, ConversationEmbedding, MessageEmbedding
from .embeddings import get_embedding_service


def search_transcripts(
    db_session: Session,
    query: str,
    limit: int = 20,
    model_name: str = "all-MiniLM-L6-v2",
) -> List[Dict[str, Any]]:
    """
    Search for transcripts using semantic similarity.

    Args:
        db_session: Database session
        query: Search query text
        limit: Maximum number of results to return
        model_name: Embedding model to use

    Returns:
        List of search results with metadata
    """
    # Generate query embedding
    embedding_service = get_embedding_service(model_name)
    query_embedding = embedding_service.encode_single(query)

    # Convert to PostgreSQL vector format
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

    results = []

    # Search conversation embeddings (summaries)
    conv_query = text(
        """
        SELECT
            ce.conversation_id,
            ce.summary_text,
            c.session_id,
            c.source,
            c.first_message,
            1 - (ce.embedding <=> :embedding) as similarity,
            'summary' as match_type,
            NULL as page_number,
            NULL as message_index
        FROM conversation_embeddings ce
        JOIN conversations c ON ce.conversation_id = c.id
        ORDER BY ce.embedding <=> :embedding
        LIMIT :limit
    """
    )

    conv_results = db_session.execute(
        conv_query, {"embedding": embedding_str, "limit": limit}
    ).fetchall()

    for row in conv_results:
        results.append(
            {
                "conversation_id": row[0],
                "text": row[1],
                "session_id": row[2],
                "source": row[3],
                "first_message": row[4],
                "similarity": float(row[5]),
                "match_type": row[6],
                "page_number": row[7],
                "message_index": row[8],
                "url": f"/transcript/{row[2]}",
            }
        )

    # Search message embeddings (individual queries)
    msg_query = text(
        """
        SELECT
            me.conversation_id,
            me.message_text,
            c.session_id,
            c.source,
            c.first_message,
            1 - (me.embedding <=> :embedding) as similarity,
            'message' as match_type,
            me.page_number,
            me.message_index
        FROM message_embeddings me
        JOIN conversations c ON me.conversation_id = c.id
        ORDER BY me.embedding <=> :embedding
        LIMIT :limit
    """
    )

    msg_results = db_session.execute(
        msg_query, {"embedding": embedding_str, "limit": limit}
    ).fetchall()

    for row in msg_results:
        results.append(
            {
                "conversation_id": row[0],
                "text": row[1],
                "session_id": row[2],
                "source": row[3],
                "first_message": row[4],
                "similarity": float(row[5]),
                "match_type": row[6],
                "page_number": row[7],
                "message_index": row[8],
                "url": (
                    f"/transcript/{row[2]}/page-{row[7]:03d}.html#msg-{row[8]}"
                    if row[7]
                    else f"/transcript/{row[2]}"
                ),
            }
        )

    # Sort all results by similarity and limit
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]
