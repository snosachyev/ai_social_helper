-- Qdrant initialization script
-- This script sets up collections for the RAG system

-- Note: Qdrant uses HTTP API, not SQL
-- This is a placeholder for initialization commands
-- Actual collection creation will be done via API calls

-- Collections to create:
-- 1. document_embeddings - for document chunks
-- 2. query_embeddings - for query history
-- 3. telegram_embeddings - for telegram messages

-- Collection configurations:
-- document_embeddings:
-- - Vector size: 768 (for sentence-transformers/all-MiniLM-L6-v2)
-- - Distance: Cosine
-- - Payload: document_id, chunk_id, text, metadata

-- query_embeddings:
-- - Vector size: 768
-- - Distance: Cosine  
-- - Payload: query_id, query_text, timestamp, user_id

-- telegram_embeddings:
-- - Vector size: 768
-- - Distance: Cosine
-- - Payload: message_id, channel_id, text, timestamp, metadata
