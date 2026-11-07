"""Unit tests for AgentDesk embedding providers (Phase 5.4F.5).

Verifies:
1. MockEmbeddingProvider:
   - Output vector dimension is exactly 384.
   - Strict determinism (identical input produces identical vectors).
   - Distinct inputs produce distinct vectors.
   - Asymmetric prefixing ('passage: ' vs 'query: ') produces distinct vectors for same content.
   - Vectors are unit-normalized.
   - Batch embedding preserves order and matches single-item embeddings.
   - Empty and invalid input rejection (None, empty, whitespace-only).
2. LocalSentenceTransformerProvider:
   - Approved E5 model configuration ('intfloat/multilingual-e5-small').
   - Offline-first configuration (local_files_only=True).
   - Lazy loading (does not instantiate model on import or __init__).
   - Single instantiation caching per provider instance.
   - Input validation before model invocation.
   - Dimension validation (must be 384).
   - Finite numeric validation (rejection of NaN and Inf).
   - Unit normalization validation (norm ~ 1.0).
   - Prefix handling ('passage: ', 'query: ', custom, avoid double-prefix).
   - Non-blocking execution via asyncio.to_thread().
   - Missing dependency error handling.
   - Model instantiation failure error handling.
3. Factory function get_embedding_provider:
   - Process-level singleton caching.
   - Cache invalidation and force_reload.
   - Default provider selection (mock in testing, local otherwise).
"""

import asyncio
import math
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.providers.embeddings import (
    EmbeddingProvider,
    MockEmbeddingProvider,
    LocalSentenceTransformerProvider,
    MOCK_EMBEDDING_DIMENSION,
    DEFAULT_MODEL_NAME,
    EXPECTED_EMBEDDING_DIMENSION,
    PREFIX_PASSAGE,
    PREFIX_QUERY,
    get_embedding_provider,
    clear_embedding_provider_cache,
)


@pytest.fixture(autouse=True)
def reset_provider_cache():
    """Ensures each test gets a clean provider cache."""
    clear_embedding_provider_cache()
    yield
    clear_embedding_provider_cache()


def _make_unit_vector(dim: int = 384) -> list[float]:
    """Helper creating a strictly unit-normalized 384-dimensional vector."""
    val = 1.0 / math.sqrt(dim)
    return [val] * dim


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
async def test_mock_provider_prefix_distinct_vectors():
    """Verifies that passage and query prefixes produce distinct vectors for identical content."""
    provider = MockEmbeddingProvider()
    text = "Clinic hours and fees"

    vec_passage = await provider.embed_text(text, is_query=False)
    vec_query = await provider.embed_text(text, is_query=True)

    assert vec_passage != vec_query


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

def test_local_provider_e5_model_configuration():
    """Verifies default model is set to intfloat/multilingual-e5-small with local_files_only=True."""
    provider = LocalSentenceTransformerProvider()
    assert provider.model_name == "intfloat/multilingual-e5-small"
    assert provider.model_name == DEFAULT_MODEL_NAME
    assert provider.local_files_only is True
    assert provider.dimension == EXPECTED_EMBEDDING_DIMENSION
    assert provider.dimension == 384


def test_local_provider_lazy_loading():
    """Verifies that LocalSentenceTransformerProvider does NOT load the model on import or __init__."""
    provider = LocalSentenceTransformerProvider()
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
async def test_local_provider_embed_text_default_passage_prefix():
    """Verifies embed_text prepends 'passage: ' by default and normalizes embedding."""
    dummy_vec = _make_unit_vector(384)
    mock_model = MagicMock()
    mock_model.encode.return_value = dummy_vec

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)
    assert provider.is_loaded is True

    result = await provider.embed_text("Customer service FAQ.")
    assert len(result) == 384
    assert result == dummy_vec

    # Verify model.encode was called with 'passage: ' prefix and normalize_embeddings=True
    mock_model.encode.assert_called_once_with(
        "passage: Customer service FAQ.",
        normalize_embeddings=True,
    )


@pytest.mark.asyncio
async def test_local_provider_embed_text_query_prefix():
    """Verifies embed_text with is_query=True prepends 'query: ' prefix."""
    dummy_vec = _make_unit_vector(384)
    mock_model = MagicMock()
    mock_model.encode.return_value = dummy_vec

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)
    result = await provider.embed_text("What are your opening hours?", is_query=True)

    assert len(result) == 384
    mock_model.encode.assert_called_once_with(
        "query: What are your opening hours?",
        normalize_embeddings=True,
    )


@pytest.mark.asyncio
async def test_local_provider_embed_text_avoids_double_prefix():
    """Verifies that already-prefixed text is not double-prefixed."""
    dummy_vec = _make_unit_vector(384)
    mock_model = MagicMock()
    mock_model.encode.return_value = dummy_vec

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)

    await provider.embed_text("passage: Already prefixed content.")
    mock_model.encode.assert_called_with(
        "passage: Already prefixed content.",
        normalize_embeddings=True,
    )

    await provider.embed_text("query: Already prefixed search.", is_query=True)
    mock_model.encode.assert_called_with(
        "query: Already prefixed search.",
        normalize_embeddings=True,
    )


@pytest.mark.asyncio
async def test_local_provider_embed_batch_with_prefix():
    """Verifies embed_batch applies passage prefixes across all batch items."""
    dummy_vec_1 = _make_unit_vector(384)
    dummy_vec_2 = _make_unit_vector(384)
    mock_model = MagicMock()
    mock_model.encode.return_value = [dummy_vec_1, dummy_vec_2]

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)
    texts = ["Opening hours", "Cancellation policy"]

    results = await provider.embed_batch(texts)
    assert len(results) == 2
    assert results[0] == dummy_vec_1
    assert results[1] == dummy_vec_2

    expected_prefixed = ["passage: Opening hours", "passage: Cancellation policy"]
    mock_model.encode.assert_called_once_with(expected_prefixed, normalize_embeddings=True)


@pytest.mark.asyncio
async def test_local_provider_asyncio_to_thread_delegation():
    """Verifies model.encode() is executed via asyncio.to_thread() to avoid event loop blocking."""
    dummy_vec = _make_unit_vector(384)
    mock_model = MagicMock()
    mock_model.encode.return_value = dummy_vec

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)

    with patch("asyncio.to_thread", side_effect=asyncio.to_thread) as spy_to_thread:
        await provider.embed_text("Non-blocking test")
        assert spy_to_thread.called
        assert spy_to_thread.call_args[0][0] == mock_model.encode


@pytest.mark.asyncio
async def test_local_provider_dimension_mismatch_raises_error():
    """Verifies that an unexpected model dimension output (e.g. 512 instead of 384) raises ValueError."""
    invalid_dim_vec = [0.1] * 512
    mock_model = MagicMock()
    mock_model.encode.return_value = invalid_dim_vec

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)

    with pytest.raises(ValueError, match="dimension mismatch: expected 384, got 512"):
        await provider.embed_text("Dimension test")


@pytest.mark.asyncio
async def test_local_provider_batch_dimension_mismatch_raises_error():
    """Verifies that batch dimension mismatch raises ValueError."""
    mock_model = MagicMock()
    mock_model.encode.return_value = [_make_unit_vector(384), [0.1] * 128]

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)

    with pytest.raises(ValueError, match="dimension mismatch: expected 384, got 128"):
        await provider.embed_batch(["text 1", "text 2"])


@pytest.mark.asyncio
async def test_local_provider_non_finite_rejection():
    """Verifies that NaN or Inf in model output raises ValueError."""
    bad_vec = _make_unit_vector(384)
    bad_vec[5] = float("nan")

    mock_model = MagicMock()
    mock_model.encode.return_value = bad_vec

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)

    with pytest.raises(ValueError, match="non-finite value at index 5"):
        await provider.embed_text("NaN test")

    bad_vec_inf = _make_unit_vector(384)
    bad_vec_inf[10] = float("inf")
    mock_model.encode.return_value = bad_vec_inf

    with pytest.raises(ValueError, match="non-finite value at index 10"):
        await provider.embed_text("Inf test")


@pytest.mark.asyncio
async def test_local_provider_unnormalized_vector_rejection():
    """Verifies that a vector whose norm deviates significantly from 1.0 raises ValueError."""
    # Vector of norm ~2.0
    unnormalized_vec = [0.1] * 384
    mock_model = MagicMock()
    mock_model.encode.return_value = unnormalized_vec

    provider = LocalSentenceTransformerProvider(model_instance=mock_model)

    with pytest.raises(ValueError, match="not unit-normalized"):
        await provider.embed_text("Unnormalized test")


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


def test_local_provider_single_initialization_caching():
    """Verifies that _get_model initializes SentenceTransformer only once."""
    provider = LocalSentenceTransformerProvider()
    mock_st_instance = MagicMock()

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_st_instance) as mock_st_cls:
        m1 = provider._get_model()
        m2 = provider._get_model()
        assert m1 is m2
        mock_st_cls.assert_called_once_with(
            "intfloat/multilingual-e5-small",
            local_files_only=True,
        )


# =====================================================================
# 3. Factory Function Tests
# =====================================================================

def test_get_embedding_provider_factory():
    """Verifies that get_embedding_provider returns the requested provider types."""
    mock_p = get_embedding_provider(provider_type="mock")
    assert isinstance(mock_p, MockEmbeddingProvider)

    local_p = get_embedding_provider(provider_type="local")
    assert isinstance(local_p, LocalSentenceTransformerProvider)

    with pytest.raises(ValueError, match="Unsupported embedding provider type 'unsupported'"):
        get_embedding_provider(provider_type="unsupported")


def test_get_embedding_provider_singleton_caching():
    """Verifies that consecutive factory calls return the cached singleton instance."""
    p1 = get_embedding_provider(provider_type="local")
    p2 = get_embedding_provider(provider_type="local")
    assert p1 is p2

    # Force reload returns a new instance
    p3 = get_embedding_provider(provider_type="local", force_reload=True)
    assert p3 is not p1


def test_get_embedding_provider_default_testing(monkeypatch):
    """Verifies that in a testing environment, the factory defaults to MockEmbeddingProvider."""
    monkeypatch.setenv("ENVIRONMENT", "testing")
    provider = get_embedding_provider()
    assert isinstance(provider, MockEmbeddingProvider)
