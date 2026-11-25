/**
 * AgentDesk Knowledge Base API Client.
 * Typed HTTP functions for FAQ management, semantic search, and document file processing.
 */

import { apiClient, type ApiClient } from "./client";
import type {
  FAQCreatePayload,
  FAQUpdatePayload,
  FAQResponse,
  ListFaqsParams,
  KnowledgeSearchRequest,
  KnowledgeSearchResponse,
  KnowledgeFileResponse,
  KnowledgeFileListResponse,
  ListFilesParams,
} from "@/types/knowledge";

/**
 * Retrieves the list of FAQs for the authenticated business.
 * Endpoint: GET /api/v1/knowledge
 */
export async function listFaqs(
  params?: ListFaqsParams,
  options: { client?: ApiClient } = {}
): Promise<FAQResponse[]> {
  const client = options.client || apiClient;
  return client.listFaqs(params);
}

/**
 * Creates a new FAQ entry for the authenticated business.
 * Endpoint: POST /api/v1/knowledge
 */
export async function createFaq(
  payload: FAQCreatePayload,
  options: { client?: ApiClient } = {}
): Promise<FAQResponse> {
  const client = options.client || apiClient;
  return client.createFaq(payload);
}

/**
 * Retrieves a single FAQ entry by ID.
 * Endpoint: GET /api/v1/knowledge/:knowledgeId
 */
export async function getFaq(
  knowledgeId: string,
  options: { client?: ApiClient } = {}
): Promise<FAQResponse> {
  const client = options.client || apiClient;
  return client.getFaq(knowledgeId);
}

/**
 * Updates an existing FAQ entry using PATCH.
 * Endpoint: PATCH /api/v1/knowledge/:knowledgeId
 */
export async function updateFaq(
  knowledgeId: string,
  payload: FAQUpdatePayload,
  options: { client?: ApiClient } = {}
): Promise<FAQResponse> {
  const client = options.client || apiClient;
  return client.updateFaq(knowledgeId, payload);
}

/**
 * Deletes an existing FAQ entry.
 * Endpoint: DELETE /api/v1/knowledge/:knowledgeId
 */
export async function deleteFaq(
  knowledgeId: string,
  options: { client?: ApiClient } = {}
): Promise<void> {
  const client = options.client || apiClient;
  return client.deleteFaq(knowledgeId);
}

/**
 * Executes a tenant-scoped semantic vector search across FAQs and document chunks.
 * Endpoint: POST /api/v1/knowledge/search
 */
export async function searchKnowledge(
  payload: KnowledgeSearchRequest,
  options: { client?: ApiClient } = {}
): Promise<KnowledgeSearchResponse> {
  const client = options.client || apiClient;
  return client.searchKnowledge(payload);
}

/**
 * Uploads a PDF or DOCX knowledge document.
 * Endpoint: POST /api/v1/knowledge/files
 * Uses multipart/form-data without manually overriding boundary headers.
 */
export async function uploadFile(
  file: File | Blob,
  filename?: string,
  options: { client?: ApiClient } = {}
): Promise<KnowledgeFileResponse> {
  const client = options.client || apiClient;
  return client.uploadKnowledgeFile(file, filename);
}

/**
 * Lists uploaded knowledge files for the authenticated business.
 * Endpoint: GET /api/v1/knowledge/files
 */
export async function listFiles(
  params?: ListFilesParams,
  options: { client?: ApiClient } = {}
): Promise<KnowledgeFileListResponse> {
  const client = options.client || apiClient;
  return client.listKnowledgeFiles(params);
}

/**
 * Retrieves status and processing metadata for a single knowledge file.
 * Endpoint: GET /api/v1/knowledge/files/:fileId
 */
export async function getFileStatus(
  fileId: string,
  options: { client?: ApiClient } = {}
): Promise<KnowledgeFileResponse> {
  const client = options.client || apiClient;
  return client.getKnowledgeFileStatus(fileId);
}

/**
 * Deletes an uploaded knowledge file and cascades chunk deletion.
 * Endpoint: DELETE /api/v1/knowledge/files/:fileId
 */
export async function deleteFile(
  fileId: string,
  options: { client?: ApiClient } = {}
): Promise<void> {
  const client = options.client || apiClient;
  return client.deleteKnowledgeFile(fileId);
}
