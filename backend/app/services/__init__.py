"""AgentDesk Services Package."""

from app.services.auth_service import auth_service, AuthService
from app.services.business_service import business_service, BusinessService
from app.services.knowledge_service import (
    knowledge_service,
    KnowledgeService,
    ReembedBatchResult,
)
from app.services.document_processing_service import (
    DocumentProcessingService,
    DocumentProcessingResult,
    ProcessingResultStatus,
)

__all__ = [
    "auth_service",
    "AuthService",
    "business_service",
    "BusinessService",
    "knowledge_service",
    "KnowledgeService",
    "ReembedBatchResult",
    "DocumentProcessingService",
    "DocumentProcessingResult",
    "ProcessingResultStatus",
]

