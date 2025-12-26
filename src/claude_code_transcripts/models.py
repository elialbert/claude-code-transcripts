"""Database models for transcript metadata."""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    create_engine,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Conversation(Base):
    """Model for storing transcript metadata."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    source = Column(String(50), nullable=False)  # 'web' or 'local'
    last_updated = Column(DateTime, nullable=False)
    message_count = Column(Integer, nullable=False)
    html_path = Column(String(512), nullable=False)
    first_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Conversation(session_id='{self.session_id}', source='{self.source}', messages={self.message_count})>"


class ConversationEmbedding(Base):
    """Model for storing conversation summary embeddings."""

    __tablename__ = "conversation_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    summary_text = Column(Text, nullable=False)
    embedding = Column(
        Vector(384), nullable=False
    )  # all-MiniLM-L6-v2 produces 384-dim vectors
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    conversation = relationship("Conversation", backref="embedding")

    def __repr__(self):
        return f"<ConversationEmbedding(conversation_id={self.conversation_id})>"


class MessageEmbedding(Base):
    """Model for storing individual user query embeddings."""

    __tablename__ = "message_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    message_index = Column(Integer, nullable=False)  # Position in conversation
    message_text = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=False)
    page_number = Column(Integer, nullable=False)  # Which HTML page this appears on
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    conversation = relationship("Conversation", backref="message_embeddings")

    def __repr__(self):
        return f"<MessageEmbedding(conversation_id={self.conversation_id}, index={self.message_index})>"


def get_engine(database_url):
    """Create a database engine."""
    return create_engine(database_url)


def get_session(engine):
    """Create a database session."""
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(database_url):
    """Initialize the database with all tables."""
    engine = get_engine(database_url)

    # Enable pgvector extension (PostgreSQL only)
    if "postgresql" in database_url:
        with engine.connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()

    Base.metadata.create_all(engine)
    return engine
