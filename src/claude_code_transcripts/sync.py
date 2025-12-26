"""Synchronization service for fetching and updating transcripts."""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from . import (
    find_local_sessions,
    parse_session_file,
    generate_html,
    fetch_sessions,
    fetch_session,
    resolve_credentials,
    generate_html_from_session_data,
)
from .models import Conversation, ConversationEmbedding, MessageEmbedding
from .embeddings import get_embedding_service


def needs_update(existing: Optional[Conversation], session_data: dict) -> bool:
    """
    Determine if a session needs to be updated.

    Args:
        existing: Existing conversation record from database (or None if new)
        session_data: Current session data from API or file

    Returns:
        True if the session should be updated, False otherwise
    """
    # New session always needs update
    if existing is None:
        return True

    # Check if message count has changed
    current_message_count = len(session_data.get("loglines", []))
    return current_message_count != existing.message_count


def extract_user_queries(session_data: dict, prompts_per_page: int = 5) -> list:
    """
    Extract user queries from session data with page number information.

    Args:
        session_data: Parsed session data
        prompts_per_page: Number of prompts per HTML page

    Returns:
        List of tuples: (message_index, message_text, page_number)
    """
    user_queries = []
    message_index = 0
    prompt_count = 0

    for logline in session_data.get("loglines", []):
        content = logline.get("content")
        # User messages have string content
        if isinstance(content, str) and content.strip():
            page_number = (prompt_count // prompts_per_page) + 1
            user_queries.append(
                (message_index, content[:1000], page_number)
            )  # Limit to 1000 chars
            prompt_count += 1
        message_index += 1

    return user_queries


def store_embeddings(
    db_session: Session,
    conversation_id: int,
    summary_text: str,
    user_queries: list,
    model_name: str = "all-MiniLM-L6-v2",
):
    """
    Generate and store embeddings for conversation and messages.

    Args:
        db_session: Database session
        conversation_id: ID of the conversation
        summary_text: Summary text for the conversation
        user_queries: List of (message_index, message_text, page_number) tuples
        model_name: Embedding model to use
    """
    embedding_service = get_embedding_service(model_name)

    # Delete existing embeddings
    db_session.query(ConversationEmbedding).filter_by(
        conversation_id=conversation_id
    ).delete()
    db_session.query(MessageEmbedding).filter_by(
        conversation_id=conversation_id
    ).delete()

    # Generate and store conversation embedding
    if summary_text:
        summary_embedding = embedding_service.encode_single(summary_text)
        conv_embedding = ConversationEmbedding(
            conversation_id=conversation_id,
            summary_text=summary_text[:500],  # Limit stored text
            embedding=summary_embedding,
        )
        db_session.add(conv_embedding)

    # Generate and store message embeddings in batch
    if user_queries:
        messages = [text for _, text, _ in user_queries]
        embeddings = embedding_service.encode_batch(messages)

        for (msg_idx, msg_text, page_num), embedding in zip(user_queries, embeddings):
            msg_embedding = MessageEmbedding(
                conversation_id=conversation_id,
                message_index=msg_idx,
                message_text=msg_text[:500],  # Limit stored text
                embedding=embedding,
                page_number=page_num,
            )
            db_session.add(msg_embedding)

    db_session.commit()


def sync_local_sessions(
    db_session: Session,
    storage_path: str,
    claude_projects_dir: Optional[str] = None,
    limit: int = 100,
    github_repo: Optional[str] = None,
) -> int:
    """
    Sync local Claude Code sessions.

    Args:
        db_session: Database session
        storage_path: Base path for storing HTML files
        claude_projects_dir: Path to ~/.claude/projects (or None to use default)
        limit: Maximum number of sessions to sync
        github_repo: GitHub repo for commit links

    Returns:
        Number of sessions updated
    """
    # Find local sessions
    if claude_projects_dir is None:
        claude_projects_dir = os.path.expanduser("~/.claude/projects")

    try:
        sessions = find_local_sessions(claude_projects_dir, limit=limit)
    except Exception as e:
        print(f"Error finding local sessions: {e}")
        return 0

    updated_count = 0

    for session_path, summary in sessions:
        try:
            # Parse session file
            session_data = parse_session_file(session_path)

            # Extract session ID from filename
            session_id = Path(session_path).stem

            # Check if update needed
            existing = (
                db_session.query(Conversation).filter_by(session_id=session_id).first()
            )

            if not needs_update(existing, session_data):
                continue

            # Generate HTML
            output_dir = os.path.join(storage_path, session_id)
            os.makedirs(output_dir, exist_ok=True)

            generate_html(session_path, output_dir, github_repo=github_repo)

            # Extract metadata
            message_count = len(session_data.get("loglines", []))
            first_message = summary[:200] if summary else None

            # Update or create database record
            if existing:
                existing.last_updated = datetime.utcnow()
                existing.message_count = message_count
                existing.html_path = output_dir
                existing.first_message = first_message
                conversation_id = existing.id
            else:
                conversation = Conversation(
                    session_id=session_id,
                    source="local",
                    last_updated=datetime.utcnow(),
                    message_count=message_count,
                    html_path=output_dir,
                    first_message=first_message,
                )
                db_session.add(conversation)
                db_session.flush()  # Get the ID
                conversation_id = conversation.id

            db_session.commit()

            # Generate and store embeddings
            try:
                user_queries = extract_user_queries(session_data)
                store_embeddings(
                    db_session,
                    conversation_id,
                    first_message or "",
                    user_queries,
                )
            except Exception as e:
                print(f"Error generating embeddings for {session_id}: {e}")

            updated_count += 1

        except Exception as e:
            print(f"Error syncing session {session_path}: {e}")
            db_session.rollback()
            continue

    return updated_count


def sync_web_sessions(
    db_session: Session,
    storage_path: str,
    token: Optional[str] = None,
    org_uuid: Optional[str] = None,
    limit: int = 100,
    github_repo: Optional[str] = None,
) -> int:
    """
    Sync web sessions from Claude API.

    Args:
        db_session: Database session
        storage_path: Base path for storing HTML files
        token: Claude API token (or None to auto-detect)
        org_uuid: Organization UUID (or None to auto-detect)
        limit: Maximum number of sessions to sync
        github_repo: GitHub repo for commit links

    Returns:
        Number of sessions updated
    """
    try:
        # Resolve credentials
        token, org_uuid = resolve_credentials(token, org_uuid)

        # Fetch session list
        sessions = fetch_sessions(token, org_uuid)

        # Limit number of sessions
        sessions = sessions[:limit]

    except Exception as e:
        print(f"Error fetching web sessions: {e}")
        return 0

    updated_count = 0

    for session_info in sessions:
        session_id = session_info.get("session_id")
        if not session_id:
            continue

        try:
            # Fetch full session data
            session_data = fetch_session(token, org_uuid, session_id)

            # Check if update needed
            existing = (
                db_session.query(Conversation).filter_by(session_id=session_id).first()
            )

            if not needs_update(existing, session_data):
                continue

            # Generate HTML
            output_dir = os.path.join(storage_path, session_id)
            os.makedirs(output_dir, exist_ok=True)

            generate_html_from_session_data(
                session_data, output_dir, github_repo=github_repo
            )

            # Extract metadata
            message_count = len(session_data.get("loglines", []))
            first_message = None
            if session_data.get("loglines"):
                for line in session_data["loglines"]:
                    if isinstance(line.get("content"), str) and line.get("content"):
                        first_message = line["content"][:200]
                        break

            # Update or create database record
            if existing:
                existing.last_updated = datetime.utcnow()
                existing.message_count = message_count
                existing.html_path = output_dir
                existing.first_message = first_message
                conversation_id = existing.id
            else:
                conversation = Conversation(
                    session_id=session_id,
                    source="web",
                    last_updated=datetime.utcnow(),
                    message_count=message_count,
                    html_path=output_dir,
                    first_message=first_message,
                )
                db_session.add(conversation)
                db_session.flush()  # Get the ID
                conversation_id = conversation.id

            db_session.commit()

            # Generate and store embeddings
            try:
                user_queries = extract_user_queries(session_data)
                store_embeddings(
                    db_session,
                    conversation_id,
                    first_message or "",
                    user_queries,
                )
            except Exception as e:
                print(f"Error generating embeddings for {session_id}: {e}")

            updated_count += 1

        except Exception as e:
            print(f"Error syncing web session {session_id}: {e}")
            db_session.rollback()
            continue

    return updated_count


def sync_all(
    db_session: Session,
    storage_path: str,
    token: Optional[str] = None,
    org_uuid: Optional[str] = None,
    github_repo: Optional[str] = None,
) -> dict:
    """
    Sync both local and web sessions.

    Args:
        db_session: Database session
        storage_path: Base path for storing HTML files
        token: Claude API token (or None to auto-detect)
        org_uuid: Organization UUID (or None to auto-detect)
        github_repo: GitHub repo for commit links

    Returns:
        Dictionary with sync statistics
    """
    print("Syncing local sessions...")
    local_count = sync_local_sessions(db_session, storage_path, github_repo=github_repo)

    print("Syncing web sessions...")
    web_count = sync_web_sessions(
        db_session,
        storage_path,
        token=token,
        org_uuid=org_uuid,
        github_repo=github_repo,
    )

    return {
        "local_updated": local_count,
        "web_updated": web_count,
        "total_updated": local_count + web_count,
    }
