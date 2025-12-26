"""Add vector embeddings tables

Revision ID: add_vector_embeddings
Revises: 9f626c3218c2
Create Date: 2025-12-26 16:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "add_vector_embeddings"
down_revision: Union[str, Sequence[str], None] = "9f626c3218c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create conversation_embeddings table
    op.create_table(
        "conversation_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_embeddings_conversation_id",
        "conversation_embeddings",
        ["conversation_id"],
        unique=True,
    )

    # Create message_embeddings table
    op.create_table(
        "message_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("message_index", sa.Integer(), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_message_embeddings_conversation_id",
        "message_embeddings",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_message_embeddings_conversation_id", table_name="message_embeddings"
    )
    op.drop_table("message_embeddings")
    op.drop_index(
        "ix_conversation_embeddings_conversation_id",
        table_name="conversation_embeddings",
    )
    op.drop_table("conversation_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
