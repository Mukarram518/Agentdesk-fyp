"""Unit tests for AgentDesk embedding providers (Phase 5.2B).

Verifies:
1. MockEmbeddingProvider:
   - Output vector dimension is exactly 384.
   - Strict determinism (identical input produces identical vectors).
   - Distinct inputs produce distinct vectors.
   - Vectors are unit-normalized.
   - Batch embedding preserves order and matches single-item embeddings.
   - Empty and invalid input rejection (None, empty, whitespace-only).
2. LocalSentenceTransformerProvider:
   - Lazy loading (does not instantiate model on import or __init__).
   - Input validation before model invocation.
   - Dimension validation on model outputs.
   - Single-text and batch embedding using mocked model.
   - Missing dependency error handling.
   - Model instantiation failure error handling.
3. Factory function get_embedding_provider.
"""

import math
from unittest.mock import MagicMock, patch
import pytest

from app.providers.embeddings import (
    EmbeddingProvider,
    MockEmbeddingProvider,
    LocalSentenceTransformerProvider,
    MOCK_EMBEDDING_DIMENSION,
    EXPECTED_EMBEDDING_DIMENSION,
    get_embedding_provider,
)


# =====================================================================
# 1. MockEmbeddingProvider Tests
# =====================================================================

def test_mock_provider_dimension_property():
    """Verifies that MockEmbeddingProvider reports the expected 384 dimensions."""
    provider = MockEmbeddingProvider()
    assert provider.dimension == 384
    assert provider.dimension == MOCK_EMBEDDING_DIMENSION


@pytest.mark.asyncio
async def test_mock_provider_embed_text_dimension():
    """Verifies that embed_text produces a vector of exactly 384 float dimensions."""
    provider = MockEmbeddingProvider()
    vec = await provider.embed_text("Welcome to AgentDesk!")
    assert isinstance(vec, list)
    assert len(vec) == 384
    assert all(isinstance(x, float) for x in vec)


@pytest.mark.asyncio
async def test_mock_provider_determinism():
    """Verifies that identical text always yields the exact same vector output."""
    provider = MockEmbeddingProvider()
    text = "Frequently Asked Questions about our dental clinic."

    vec1 = await provider.embed_text(text)
    vec2 = await provider.embed_text(text)

    assert vec1 == vec2


@pytest.mark.asyncio
async def test_mock_provider_distinct_inputs():
    """Verifies that distinct inputs produce distinct deterministic vectors."""
    provider = MockEmbeddingProvider()

    vec_a = await provider.embed_text("What are your opening hours?")
    vec_b = await provider.embed_text("Do you offer root canal treatments?")

    assert vec_a != vec_b


@pytest.mark.asyncio
async def test_mock_provider_unit_normalization():
    """Verifies that generated mock vectors are unit-normalized (L2 norm ~ 1.0)."""
    provider = MockEmbeddingProvider()
    vec = await provider.embed_text("Normalization check text.")

    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-4


@pytest.mark.asyncio
async def test_mock_provider_embed_batch():
    """Verifies batch embedding matches individual calls and preserves order."""
    provider = MockEmbeddingProvider()
    texts = [
        "First chunk of business policy.",
        "Second chunk of business policy.",
        "Third chunk of business policy.",
    ]

    batch_vectors = await provider.embed_batch(texts)
    assert len(batch_vectors) == 3

    for i, text in enumerate(texts):
        single_vec = await provider.embed_text(text)
        assert batch_vectors[i] == single_vec
        assert len(batch_vectors[i]) == 384


@pytest.mark.asyncio
async def test_mock_provider_empty_batch_returns_empty_list():
    """Verifies that passing an empty list to embed_batch returns an empty list."""
    provider = MockEmbeddingProvider()
    batch_vectors = await provider.embed_batch([])
    assert batch_vectors == []


@pytest.mark.asyncio
async def test_mock_provider_empty_input_validation():
    """Verifies that empty, whitespace, and None inputs are rejected with ValueError."""
    provider = MockEmbeddingProvider()

    with pytest.raises(ValueError, match="cannot be empty"):
        await provider.embed_text("")

    with pytest.raises(ValueError, match="cannot be empty"):
        await provider.embed_text("   ")

    with pytest.raises(ValueError, match="non-null string"):
        await provider.embed_text(None)  # type: ignore

    with pytest.raises(ValueError, match="cannot be empty"):
        await provider.embed_batch(["valid text", ""])

    with pytest.raises(ValueError, match="non-null string"):
        await provider.embed_batch(["valid text", None])  # type: ignore

    with pytest.raises(ValueError, match="must be a list"):
        await provider.embed_batch(None)  # type: ignore


# =====================================================================
# 2. LocalSentenceTransformerProvider Tests (Offline / Mocked Model)
# =====================================================================

def test_local_provider_lazy_loading():
    """Verifies that LocalSentenceTransformerProvider does NOT load the model on import or __init__."""
    provider = LocalSentenceTransformerProvider()
    assert provider.dimension == EXPECTED_EMBEDDING_DIMENSION
    assert provider.dimension == 384
    assert provider.is_loaded is False
    assert provider._model is None


@pytest.mark.asyncio
async def test_local_provider_validates_input_before_loading():
    """Verifies input validation triggers without invoking model loading."""
    provider = LocalSentenceTransformerProvider()

    with pytest.raises(ValueError, match="cannot be empty"):
        await provider.embed_text("")

    assert provider.is_loaded is False

    # Empty batch returns [] without loading model
    result = await provider.embed_batch([])
    assert result == []
    assert provider.is_loaded is False


@pytest.mark.asyncio
async def test_local_provider_embed_text_with_mocked_model():
    """Verifies embed_text using an injected mock model instance."""
    # Create mock model that returns a 384-dimensional list/array
    dummy_vec = [0.05] * 384
    mock_model = MagicMock()
    mock_model.encode.return_value = dummy_vec

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)
    assert provider.is_loaded is True

    result = await provider.embed_text("Customer service FAQ.")
    assert len(result) == 384
    assert result == dummy_vec

    # Verify model.encode was called with normalize_embeddings=True
    mock_model.encode.assert_called_once_with("Customer service FAQ.", normalize_embeddings=True)


@pytest.mark.asyncio
async def test_local_provider_embed_batch_with_mocked_model():
    """Verifies embed_batch using an injected mock model instance."""
    dummy_vec_1 = [0.1] * 384
    dummy_vec_2 = [0.2] * 384
    mock_model = MagicMock()
    mock_model.encode.return_value = [dummy_vec_1, dummy_vec_2]

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)
    texts = ["Opening hours", "Cancellation policy"]

    results = await provider.embed_batch(texts)
    assert len(results) == 2
    assert results[0] == dummy_vec_1
    assert results[1] == dummy_vec_2
    mock_model.encode.assert_called_once_with(texts, normalize_embeddings=True)


@pytest.mark.asyncio
async def test_local_provider_dimension_mismatch_raises_error():
    """Verifies that an unexpected model dimension output (e.g. 512 instead of 384) raises ValueError."""
    invalid_dim_vec = [0.1] * 512  # 512 dimensions instead of expected 384
    mock_model = MagicMock()
    mock_model.encode.return_value = invalid_dim_vec

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)

    with pytest.raises(ValueError, match="dimension mismatch: expected 384, got 512"):
        await provider.embed_text("Dimension test")


@pytest.mark.asyncio
async def test_local_provider_batch_dimension_mismatch_raises_error():
    """Verifies that batch dimension mismatch raises ValueError."""
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.1] * 384, [0.1] * 128]

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)

    with pytest.raises(ValueError, match="dimension mismatch: expected 384, got 128"):
        await provider.embed_batch(["text 1", "text 2"])


def test_local_provider_missing_dependency_error():
    """Verifies that an ImportError when importing sentence_transformers raises a clear RuntimeError."""
    provider = LocalSentenceTransformerProvider()

    with patch.dict("sys.modules", {"sentence_transformers": None}):
        with pytest.raises(RuntimeError, match="package is required for LocalSentenceTransformerProvider"):
            provider._get_model()


def test_local_provider_model_instantiation_failure_error():
    """Verifies that an exception during model instantiation raises a detailed RuntimeError."""
    provider = LocalSentenceTransformerProvider()

    with patch("sentence_transformers.SentenceTransformer", side_effect=Exception("Failed to find weights")):
        with pytest.raises(RuntimeError, match="Failed to load sentence-transformers model"):
            provider._get_model()


# =====================================================================
# 3. Factory Function Tests
# =====================================================================

def test_get_embedding_provider_factory():
    """Verifies that get_embedding_provider returns the requested provider types."""
    # Explicit mock request
    mock_p = get_embedding_provider(provider_type="mock")
    assert isinstance(mock_p, MockEmbeddingProvider)

    # Explicit local request
    local_p = get_embedding_provider(provider_type="local")
    assert isinstance(local_p, LocalSentenceTransformerProvider)

    # Invalid provider type
    with pytest.raises(ValueError, match="Unsupported embedding provider type 'unsupported'"):
        get_embedding_provider(provider_type="unsupported")


def test_get_embedding_provider_default_testing(monkeypatch):
    """Verifies that in a testing environment, the factory defaults to MockEmbeddingProvider."""
    monkeypatch.setenv("ENVIRONMENT", "testing")
    provider = get_embedding_provider()
    assert isinstance(provider, MockEmbeddingProvider)

