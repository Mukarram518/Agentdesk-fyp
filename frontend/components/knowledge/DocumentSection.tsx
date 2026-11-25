"use client";

import React, { useState, useRef } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  FileTextIcon,
  UploadCloudIcon,
  RefreshIcon,
  TrashIcon,
  AlertCircleIcon,
  CheckCircleIcon,
} from "@/components/ui/icons";
import { useKnowledgeContext } from "@/lib/knowledge/knowledge-context";
import type { KnowledgeFileResponse } from "@/types/knowledge";

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB
const ALLOWED_EXTENSIONS = [".pdf", ".docx"];

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export function DocumentSection() {
  const {
    files,
    filesTotal,
    isLoadingFiles,
    isUploading,
    isMutating,
    isPolling,
    error,
    uploadFile,
    deleteFile,
    refreshFileStatus,
    fetchFiles,
    clearError,
  } = useKnowledgeContext();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [deletingFile, setDeletingFile] = useState<KnowledgeFileResponse | null>(null);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);

  const validateAndUpload = async (file: File) => {
    setLocalError(null);
    clearError();

    const lowerName = file.name.toLowerCase();
    const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
    if (!hasValidExt) {
      setLocalError("Invalid file type. Please upload a PDF or DOCX file.");
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setLocalError(
        `File "${file.name}" exceeds the 5 MB limit (${formatFileSize(file.size)}). Please choose a smaller file.`
      );
      return;
    }

    try {
      await uploadFile(file, file.name);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch {
      // Handled via store state error
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      void validateAndUpload(selectedFile);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      void validateAndUpload(droppedFile);
    }
  };

  const handleRefreshSingle = async (fileId: string) => {
    setRefreshingId(fileId);
    try {
      await refreshFileStatus(fileId);
    } finally {
      setRefreshingId(null);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deletingFile) return;
    try {
      await deleteFile(deletingFile.id);
      setDeletingFile(null);
    } catch {
      // Error is captured in store state
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Zone */}
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        className={`p-6 sm:p-8 rounded-2xl border-2 border-dashed transition duration-150 text-center flex flex-col items-center justify-center ${
          dragActive
            ? "border-cherry bg-cherry-soft/40"
            : "border-border-main bg-white hover:border-cherry/40 hover:bg-warm-ivory/20"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={handleFileChange}
          className="hidden"
          id="knowledge-file-upload"
          disabled={isUploading}
        />

        <div className="w-12 h-12 rounded-2xl bg-cherry-soft text-cherry flex items-center justify-center mb-3 shadow-xs">
          {isUploading ? (
            <div className="w-6 h-6 rounded-full border-2 border-cherry border-t-transparent animate-spin" />
          ) : (
            <UploadCloudIcon className="w-6 h-6" />
          )}
        </div>

        <h3 className="text-sm font-semibold text-main-text">
          {isUploading ? "Uploading & Dispatching Document..." : "Upload Business Documents"}
        </h3>
        <p className="text-xs text-secondary-text mt-1 max-w-sm">
          Drag and drop PDF or DOCX files here (max 5 MB). Documents are automatically
          chunked, vectorized, and indexed for AI customer support.
        </p>

        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="text-xs gap-1.5"
          >
            <span>{isUploading ? "Uploading..." : "Select File from Device"}</span>
          </Button>
        </div>
      </div>

      {/* Validation / API Error Banner */}
      {(localError || error) && (
        <div
          role="alert"
          className="p-3.5 rounded-xl bg-status-error/10 border border-status-error/20 flex items-start gap-3 text-xs text-status-error"
        >
          <AlertCircleIcon className="w-4 h-4 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold">Error: </span>
            <span>{localError || error}</span>
          </div>
          <button
            type="button"
            onClick={() => {
              setLocalError(null);
              clearError();
            }}
            className="text-xs underline hover:no-underline font-medium"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Header Bar with Polling Status & Refresh Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
        <div className="flex items-center gap-2">
          <h4 className="text-sm font-semibold text-main-text">
            Indexed Documents ({filesTotal || files.length})
          </h4>
          {isPolling && (
            <Badge variant="indigo" className="text-[10px] gap-1.5 py-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-cherry animate-pulse" />
              <span>Indexing in progress</span>
            </Badge>
          )}
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => fetchFiles()}
          disabled={isLoadingFiles}
          className="text-xs gap-1.5 self-start sm:self-auto"
        >
          <RefreshIcon
            className={`w-3.5 h-3.5 ${isLoadingFiles ? "animate-spin text-cherry" : ""}`}
          />
          <span>Refresh All</span>
        </Button>
      </div>

      {/* Documents List */}
      {isLoadingFiles && files.length === 0 ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="p-4 rounded-xl border border-border-main bg-white space-y-3"
            >
              <div className="flex items-center justify-between">
                <div className="w-48 h-4 bg-warm-ivory border border-border-soft rounded" />
                <div className="w-20 h-4 bg-warm-ivory border border-border-soft rounded" />
              </div>
              <div className="w-32 h-3 bg-warm-ivory border border-border-soft rounded" />
            </div>
          ))}
        </div>
      ) : files.length === 0 ? (
        <EmptyState
          icon={<FileTextIcon className="w-6 h-6 text-cherry" />}
          title="No documents uploaded yet"
          description="Upload PDF or DOCX policy manuals, price lists, or catalog files to empower AI agents with deep company knowledge."
          actionText="Upload a document"
          onAction={() => fileInputRef.current?.click()}
        />
      ) : (
        <div className="space-y-3">
          {files.map((file) => {
            const status = file.processing_status?.toLowerCase();
            const isPending = status === "pending";
            const isProcessing = status === "processing";
            const isReady = status === "ready";
            const isFailed = status === "failed";
            const isSingleRefreshing = refreshingId === file.id;

            return (
              <Card
                key={file.id}
                className="p-4 sm:p-5 hover:border-cherry/40 transition duration-150"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div className="flex items-start gap-3 min-w-0 flex-1">
                    <div className="w-9 h-9 rounded-lg bg-cherry-soft text-cherry flex items-center justify-center shrink-0 border border-border-soft mt-0.5">
                      <FileTextIcon className="w-5 h-5" />
                    </div>

                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold text-main-text truncate">
                          {file.filename}
                        </span>

                        {/* Status Badge */}
                        {isReady && (
                          <Badge variant="success" className="text-[10px] gap-1">
                            <CheckCircleIcon className="w-3 h-3 text-status-success" />
                            <span>Ready</span>
                          </Badge>
                        )}
                        {isProcessing && (
                          <Badge variant="indigo" className="text-[10px] gap-1">
                            <div className="w-2.5 h-2.5 rounded-full border border-cherry border-t-transparent animate-spin" />
                            <span>Processing</span>
                          </Badge>
                        )}
                        {isPending && (
                          <Badge variant="warning" className="text-[10px] gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-status-warning" />
                            <span>Pending Dispatch</span>
                          </Badge>
                        )}
                        {isFailed && (
                          <Badge variant="outline" className="text-[10px] gap-1 text-status-error border-status-error/30 bg-status-error/5">
                            <AlertCircleIcon className="w-3 h-3 text-status-error" />
                            <span>Processing Failed</span>
                          </Badge>
                        )}

                        {file.chunk_count !== undefined && file.chunk_count !== null && (
                          <span className="text-[11px] px-2 py-0.5 rounded-full bg-warm-ivory text-secondary-text border border-border-soft">
                            {file.chunk_count} {file.chunk_count === 1 ? "chunk" : "chunks"}
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-secondary-text">
                        <span>{formatFileSize(file.size_bytes)}</span>
                        <span>•</span>
                        <span>Uploaded {formatDate(file.created_at)}</span>
                      </div>

                      {/* Failure explanation */}
                      {isFailed && (
                        <div className="mt-2 p-2.5 rounded-lg bg-status-error/5 border border-status-error/20 text-xs text-status-error">
                          <p className="font-medium">Failure Reason:</p>
                          <p className="mt-0.5 text-[11px] text-secondary-text">
                            {file.error_message ||
                              "Document parsing encountered an unrecoverable format or encoding issue. Verify the file is not password-protected and try re-uploading."}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 self-end sm:self-start shrink-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRefreshSingle(file.id)}
                      disabled={isSingleRefreshing}
                      aria-label="Refresh status"
                      className="text-xs p-1.5 h-auto text-secondary-text hover:text-main-text"
                    >
                      <RefreshIcon
                        className={`w-4 h-4 ${isSingleRefreshing ? "animate-spin text-cherry" : ""}`}
                      />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeletingFile(file)}
                      aria-label="Delete document"
                      className="text-xs p-1.5 h-auto text-secondary-text hover:text-status-error"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Delete Document Confirmation Dialog */}
      {deletingFile && (
        <div
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="delete-file-dialog-title"
          className="fixed inset-0 z-50 bg-main-text/40 backdrop-blur-xs flex items-center justify-center p-4"
        >
          <div className="bg-white rounded-2xl border border-border-main p-6 max-w-md w-full shadow-lg space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-status-error/10 text-status-error flex items-center justify-center shrink-0">
                <TrashIcon className="w-5 h-5" />
              </div>
              <div>
                <h3
                  id="delete-file-dialog-title"
                  className="text-sm font-semibold text-main-text"
                >
                  Delete Document
                </h3>
                <p className="text-xs text-secondary-text mt-0.5">
                  Are you sure you want to delete &quot;{deletingFile.filename}&quot;?
                </p>
              </div>
            </div>

            <p className="text-xs text-secondary-text leading-relaxed">
              This action permanently removes the stored file, all extracted document chunks, and
              their corresponding vector embeddings. AI agents will no longer be able to reference
              this document.
            </p>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setDeletingFile(null)}
                disabled={isMutating}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleConfirmDelete}
                disabled={isMutating}
                className="text-xs bg-status-error hover:bg-status-error/90 border-transparent text-white gap-1.5"
              >
                {isMutating && (
                  <div className="w-3 h-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
                )}
                <span>Confirm Delete</span>
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
