# Claude Code Transcripts Server

The server component automatically syncs and serves Claude Code transcripts from both local sessions and the Claude API.

## Features

- **Automated hourly syncing** of transcripts from Claude Code (local) and Claude Web (API)
- **Change detection** - only re-generates HTML for updated conversations
- **Semantic search** - AI-powered search using vector embeddings
- **PostgreSQL database** with pgvector for vector similarity search
- **Flask web interface** for browsing and viewing transcripts
- **Mobile-friendly UI** with dark mode
- **Manual sync trigger** via web interface
- **Direct message linking** - search results link to specific messages in transcripts

## Quick Start

### 1. Set up PostgreSQL

First, create a PostgreSQL database:

```bash
# Using psql
createdb claude_transcripts

# Or specify connection details
createdb -h localhost -U myuser claude_transcripts
```

### 2. Configure Environment Variables

Create a `.env` file or export these variables:

```bash
# Required: Database connection
export DATABASE_URL="postgresql://localhost/claude_transcripts"

# Optional: Storage location (default: ~/.claude-transcripts)
export STORAGE_PATH="/path/to/store/html/files"

# Optional: Update interval in minutes (default: 60)
export UPDATE_INTERVAL_MINUTES="60"

# Optional: Server configuration (defaults shown)
export SERVER_HOST="127.0.0.1"
export SERVER_PORT="5000"

# Optional: Claude API credentials (auto-detected on macOS)
export CLAUDE_TOKEN="your-api-token"
export CLAUDE_ORG_UUID="your-org-uuid"

# Optional: GitHub repo for commit links
export GITHUB_REPO="owner/repo"

# Optional: Embedding model for semantic search (default: all-MiniLM-L6-v2)
export EMBEDDING_MODEL="all-MiniLM-L6-v2"
```

**Note**: You can also use a `.env` file in the project root instead of exporting variables. See `.env.example` for a template.

### 3. Run Database Migrations

```bash
# Initialize the database schema
DATABASE_URL="postgresql://localhost/claude_transcripts" uv run alembic upgrade head
```

### 4. Start the Server

```bash
uv run claude-code-transcripts-server
```

The server will:
- Start on http://127.0.0.1:5000 by default
- Run an initial sync on startup
- Automatically sync every hour (configurable)
- Serve transcripts via a web interface

## Usage

### Web Interface

Navigate to `http://127.0.0.1:5000` to:
- Browse all synced transcripts
- View conversation statistics
- Manually trigger syncs
- Click any transcript to view the full HTML

### Manual Sync

Trigger a sync programmatically:

```bash
curl http://127.0.0.1:5000/sync
```

### Command Line Options

```bash
# Start server with custom host/port
uv run claude-code-transcripts-server --host 0.0.0.0 --port 8080

# Disable automatic hourly updates
uv run claude-code-transcripts-server --no-scheduler

# Run in debug mode
uv run claude-code-transcripts-server --debug
```

## Semantic Search

The server includes AI-powered semantic search that understands the meaning of your queries, not just keywords.

### How It Works

1. **Automatic Indexing**: During sync, the server generates vector embeddings for:
   - Conversation summaries
   - Individual user queries/prompts

2. **Smart Search**: Type in the search box on the web interface to find transcripts by meaning
   - Searches across all indexed content
   - Returns results ranked by semantic similarity
   - Shows similarity scores (0-100%)

3. **Direct Linking**: Results link directly to:
   - Conversation summaries → transcript index page
   - Individual messages → specific page with message anchor

### Search Examples

```
"How do I deploy a flask app?"
→ Finds conversations about deployment, even if they use different words

"Fix authentication bugs"
→ Finds messages about auth issues, login problems, etc.

"Optimize database queries"
→ Finds performance-related conversations
```

### Search API

Programmatic search via HTTP:

```bash
# Basic search
curl "http://127.0.0.1:5000/search?q=flask+deployment"

# With custom limit
curl "http://127.0.0.1:5000/search?q=database+optimization&limit=10"
```

Response format:
```json
{
  "status": "success",
  "query": "flask deployment",
  "results": [
    {
      "conversation_id": 123,
      "session_id": "session_abc",
      "text": "How do I deploy a Flask app to production?",
      "similarity": 0.89,
      "match_type": "message",
      "page_number": 2,
      "url": "/transcript/session_abc/page-002.html#msg-5",
      "source": "web"
    }
  ]
}
```

### Embedding Model

Default model: `all-MiniLM-L6-v2` (384 dimensions, fast and accurate)

To use a different model:
```bash
export EMBEDDING_MODEL="sentence-transformers/all-mpnet-base-v2"
```

Available models: See [sentence-transformers documentation](https://www.sbert.net/docs/pretrained_models.html)

### Performance

- **First query**: 1-2 seconds (model loads on first use)
- **Subsequent queries**: < 100ms
- **Indexing**: ~100 messages/second during sync
- **Storage**: ~1.5 KB per message embedding

## Configuration Details

### Database URL Format

PostgreSQL:
```
postgresql://username:password@localhost:5432/database_name
```

For local development with PostgreSQL:
```
postgresql://localhost/claude_transcripts
```

### Storage Path

HTML files are organized by session ID:
```
~/.claude-transcripts/
├── session_abc123/
│   ├── index.html
│   ├── page-001.html
│   ├── page-002.html
│   └── ...
├── session_def456/
│   └── ...
```

### Update Interval

Set how often to sync transcripts (in minutes):
```bash
export UPDATE_INTERVAL_MINUTES="30"  # Sync every 30 minutes
```

## Database Schema

The server uses three main tables:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Main conversations table
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    source VARCHAR(50) NOT NULL,          -- 'local' or 'web'
    last_updated TIMESTAMP NOT NULL,
    message_count INTEGER NOT NULL,
    html_path VARCHAR(512) NOT NULL,
    first_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_conversations_session_id ON conversations(session_id);

-- Conversation summary embeddings for semantic search
CREATE TABLE conversation_embeddings (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER UNIQUE NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    summary_text TEXT NOT NULL,
    embedding vector(384) NOT NULL,       -- 384-dim vector for all-MiniLM-L6-v2
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_conversation_embeddings_conversation_id ON conversation_embeddings(conversation_id);

-- Individual message embeddings for fine-grained search
CREATE TABLE message_embeddings (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_index INTEGER NOT NULL,       -- Position in conversation
    message_text TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    page_number INTEGER NOT NULL,         -- Which HTML page
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_message_embeddings_conversation_id ON message_embeddings(conversation_id);
```

## Running in Production

### Using systemd

Create `/etc/systemd/system/claude-transcripts.service`:

```ini
[Unit]
Description=Claude Code Transcripts Server
After=network.target postgresql.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/claude-code-transcripts
Environment="DATABASE_URL=postgresql://localhost/claude_transcripts"
Environment="STORAGE_PATH=/var/lib/claude-transcripts"
ExecStart=/home/youruser/.local/bin/uv run claude-code-transcripts-server
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable claude-transcripts
sudo systemctl start claude-transcripts
```

### Using Docker

Example `Dockerfile`:

```dockerfile
FROM python:3.11-slim

RUN pip install uv

WORKDIR /app
COPY . .

RUN uv sync

EXPOSE 5000

CMD ["uv", "run", "claude-code-transcripts-server", "--host", "0.0.0.0"]
```

Build and run:
```bash
docker build -t claude-transcripts .
docker run -p 5000:5000 \
  -e DATABASE_URL="postgresql://host.docker.internal/claude_transcripts" \
  -e STORAGE_PATH="/data" \
  -v /path/to/storage:/data \
  claude-transcripts
```

## Troubleshooting

### Database Connection Errors

Verify PostgreSQL is running:
```bash
psql -h localhost -U postgres -c "SELECT version();"
```

Test connection string:
```bash
psql "postgresql://localhost/claude_transcripts"
```

### Claude API Authentication

On macOS, credentials are auto-detected from keychain. On other platforms:

```bash
# Get your token (log into claude.ai and check browser dev tools)
export CLAUDE_TOKEN="your-token"

# Get org UUID from config
export CLAUDE_ORG_UUID="your-org-uuid"
```

### Storage Path Permissions

Ensure the server has write access:
```bash
mkdir -p ~/.claude-transcripts
chmod 755 ~/.claude-transcripts
```

### Migration Issues

Reset migrations (WARNING: deletes all data):
```bash
DATABASE_URL="postgresql://localhost/claude_transcripts" uv run alembic downgrade base
DATABASE_URL="postgresql://localhost/claude_transcripts" uv run alembic upgrade head
```

## Development

Run tests:
```bash
uv run pytest
```

Format code:
```bash
uv run black .
```

Create a new migration:
```bash
DATABASE_URL="postgresql://localhost/claude_transcripts" uv run alembic revision --autogenerate -m "Description"
```

## API Reference

### GET /

Main page - lists all transcripts.

### GET /transcript/<session_id>

View a specific transcript's index page.

### GET /transcript/<session_id>/page-<num>.html

View a specific page of a transcript.

### GET /sync

Trigger a manual sync of all transcripts.

Returns:
```json
{
  "status": "success",
  "timestamp": "2025-01-01T12:00:00",
  "stats": {
    "local_updated": 5,
    "web_updated": 3,
    "total_updated": 8
  }
}
```
