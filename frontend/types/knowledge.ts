/**
 * AgentDesk Knowledge Base Types.
 * Strictly mirrors backend schemas from backend/app/schemas/knowledge.py.
 */

export const KNOWLEDGE_LANGUAGES = ["en", "ur", "mixed"] as const;
export type KnowledgeLanguage = (typeof KNOWLEDGE_LANGUAGES)[number];

export const KNOWLEDGE_FILE_STATUSES = [
  "pending",
  "processing",
  "ready",
  "failed",
] as const;
export type KnowledgeFileStatus = (typeof KNOWLEDGE_FILE_STATUSES)[number];

export const KNOWLEDGE_SOURCE_TYPES = ["FAQ", "document_chunk"] as const;
export type KnowledgeSourceType = (typeof KNOWLEDGE_SOURCE_TYPES)[number];

/**
 * Type guard for supported knowledge content languages.
 */
export function isKnowledgeLanguage(val: unknown): val is KnowledgeLanguage {
  return typeof val === "string" && (KNOWLEDGE_LANGUAGES as readonly string[]).includes(val.toLowerCase());
}

/**
 * Type guard for knowledge file processing statuses.
 */
export function isKnowledgeFileStatus(val: unknown): val is KnowledgeFileStatus {
  return typeof val === "string" && (KNOWLEDGE_FILE_STATUSES as readonly string[]).includes(val.toLowerCase());
}

/**
 * Payload for creating a new FAQ entry.
 * Corresponds to FAQCreate in backend.
 */
export interface FAQCreatePayload {
  question?: string | null;
  answer: string;
  tags?: string[];
  language?: KnowledgeLanguage | string;
}

/**
 * Payload for updating an existing FAQ entry.
 * Corresponds to FAQUpdate in backend.
 */
export interface FAQUpdatePayload {
  question?: string | null;
  answer?: string;
  tags?: string[];
  language?: KnowledgeLanguage | string;
}

/**
 * Representation of an FAQ entry or document chunk returned by backend.
 * Corresponds to FAQResponse in backend.
 */
export interface FAQResponse {
  id: string;
  business_id: string;
  question: string | null;
  answer: string;
  tags: string[];
  language: string;
  source_type: string;
  has_embedding: boolean;
  embedding_stale: boolean;
  source_file_id?: string | null;
  chunk_index?: number | null;
  page_number?: number | null;
  section_title?: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Query parameters for listing FAQs.
 */
export interface ListFaqsParams {
  language?: KnowledgeLanguage | string;
  limit?: number;
  offset?: number;
}

/**
 * Payload for executing a semantic search query.
 * Corresponds to KnowledgeSearchRequest in backend.
 */
export interface KnowledgeSearchRequest {
  query: string;
  top_k?: number;
  score_threshold?: number | null;
}

/**
 * Individual semantic search result item with similarity score.
 * Corresponds to KnowledgeSearchResultItem in backend.
 */
export interface KnowledgeSearchResultItem {
  entry: FAQResponse;
  score: number;
  score_metric: string;
  source_type?: string | null;
  chunk_index?: number | null;
  page_number?: number | null;
  section_title?: string | null;
  source_file_id?: string | null;
}

/**
 * Response returned from semantic search.
 * Corresponds to KnowledgeSearchResponse in backend.
 */
export interface KnowledgeSearchResponse {
  query: string;
  results: KnowledgeSearchResultItem[];
  total_results: number;
}

/**
 * Representation of an uploaded knowledge file.
 * Corresponds to KnowledgeFileResponse in backend.
 */
export interface KnowledgeFileResponse {
  id: string;
  business_id: string;
  filename: string;
  size_bytes: number;
  mime_type: string;
  processing_status: KnowledgeFileStatus | string;
  error_message?: string | null;
  chunk_count?: number | null;
  created_at: string;
  updated_at?: string | null;
}

/**
 * Paginated list response for uploaded knowledge documents.
 * Corresponds to KnowledgeFileListResponse in backend.
 */
export interface KnowledgeFileListResponse {
  items: KnowledgeFileResponse[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Query parameters for listing uploaded files.
 */
export interface ListFilesParams {
  status?: KnowledgeFileStatus | string;
  limit?: number;
  offset?: number;
}
