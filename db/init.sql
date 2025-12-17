-- DocRAG Database Schema
-- PostgreSQL 15+ with pgvector

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- trigram similarity

-- Documents table (OCR fulltext storage)
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL UNIQUE,
    client_id VARCHAR(255),
    filename VARCHAR(500),
    fulltext TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

-- Indices for documents
CREATE INDEX IF NOT EXISTS idx_documents_document_id ON documents(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_client_id ON documents(client_id);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);

-- Full-text search index for documents (Russian)
CREATE INDEX IF NOT EXISTS idx_documents_fulltext_gin ON documents 
    USING GIN(to_tsvector('russian', COALESCE(fulltext, '')));

-- Chunks table (semantic chunks for RAG)
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(255) NOT NULL UNIQUE,
    document_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(255),
    chunk_index INTEGER NOT NULL DEFAULT 0,
    text TEXT NOT NULL,
    heading VARCHAR(500),
    heading_level INTEGER DEFAULT 0,
    chunk_type VARCHAR(50) DEFAULT 'general',
    token_count INTEGER DEFAULT 0,
    embedding vector(768),  -- pgvector embedding (nomic-embed-text dimension)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

-- Indices for chunks
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_id ON chunks(chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_client ON chunks(client_id);
CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_chunks_heading ON chunks(heading);
CREATE INDEX IF NOT EXISTS idx_chunks_index ON chunks(document_id, chunk_index);

-- Full-text search index for chunks (Russian)
CREATE INDEX IF NOT EXISTS idx_chunks_text_gin ON chunks 
    USING GIN(to_tsvector('russian', text));

-- Vector similarity search index (HNSW for fast approximate search)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw ON chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Composite index for filtered fulltext search
CREATE INDEX IF NOT EXISTS idx_chunks_client_text_gin ON chunks 
    USING GIN(to_tsvector('russian', text)) 
    WHERE client_id IS NOT NULL;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_chunks_updated_at ON chunks;
CREATE TRIGGER update_chunks_updated_at
    BEFORE UPDATE ON chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust user as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO docrag;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO docrag;
