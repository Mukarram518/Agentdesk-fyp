-- AgentDesk Database Initialization
-- Enables pgvector and UUID extensions on PostgreSQL startup

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
