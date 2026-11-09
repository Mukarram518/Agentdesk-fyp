"""Tests for AgentDesk DistributedLock (Phase 7 - Step 5C).

Verifies:
1. Successful acquisition and key storage with owner token.
2. Rejection of second owner while lock is held.
3. Correct owner-token generation and validation.
4. Heartbeat lease renewal keeping lock alive.
5. Lease expiration and ownership takeover detection.
6. LeaseLostError behavior when renewal fails.
7. Safe release by the owner deleting the key.
8. Protection against releasing another owner's lock.
9. Redis connection failure propagation as LockConnectionError.
10. Heartbeat cancellation and task cleanup upon release and context exit.
11. Concurrent acquisition behavior among multiple competing workers.
12. Chat turn key format helper (for_chat_turn).
"""

import asyncio
from unittest.mock import AsyncMock, patch
import uuid
import pytest
import redis.asyncio as aioredis

from app.core.distributed_lock import (
    DistributedLock,
    LeaseLostError,
    LockAcquisitionError,
    LockConnectionError,
    LockError,
)
from app.core.redis import get_redis_client


@pytest.fixture(autouse=True)
async def cleanup_redis_test_keys():
    """Cleans up any test lock keys before and after each test."""
    client = get_redis_client()
    yield
    # Scan and clean test keys
    keys = await client.keys("lock:test:*")
    keys.extend(await client.keys("lock:chat:test-*"))
    if keys:
        await client.delete(*keys)


@pytest.mark.asyncio
async def test_successful_acquisition():
    """Verifies that a lock can be acquired and stores the owner token with a valid TTL in Redis."""
    client = get_redis_client()
    key = f"lock:test:{uuid.uuid4()}"

    lock = DistributedLock(key=key, ttl_seconds=10, heartbeat_interval=3.0)
    assert lock.is_held is False

    acquired = await lock.acquire()
    assert acquired is True
    assert lock.is_held is True
    assert lock.lease_lost is False

    # Verify key in Redis
    stored_token = await client.get(key)
    assert stored_token == lock.owner_token

    ttl = await client.ttl(key)
    assert 0 < ttl <= 10

    # Clean release
    released = await lock.release()
    assert released is True
    assert lock.is_held is False
    assert await client.get(key) is None


@pytest.mark.asyncio
async def test_rejection_of_second_owner():
    """Verifies that a second worker cannot acquire an already held lock."""
    key = f"lock:test:{uuid.uuid4()}"

    lock_1 = DistributedLock(key=key, ttl_seconds=15, heartbeat_interval=5.0)
    lock_2 = DistributedLock(key=key, ttl_seconds=15, heartbeat_interval=5.0)

    # Worker 1 acquires
    assert await lock_1.acquire() is True

    # Worker 2 attempts non-blocking acquisition: returns False if raise_on_failure=False
    assert await lock_2.acquire(raise_on_failure=False) is False

    # Worker 2 attempts non-blocking acquisition: raises LockAcquisitionError
    with pytest.raises(LockAcquisitionError, match="Could not acquire distributed lock"):
        await lock_2.acquire(raise_on_failure=True)

    await lock_1.release()


@pytest.mark.asyncio
async def test_owner_token_uniqueness():
    """Verifies that each acquisition generates a unique cryptographic owner token."""
    key = f"lock:test:{uuid.uuid4()}"
    lock = DistributedLock(key=key, ttl_seconds=10, heartbeat_interval=3.0)

    tokens = set()
    for _ in range(3):
        await lock.acquire()
        tokens.add(lock.owner_token)
        await lock.release()

    assert len(tokens) == 3


@pytest.mark.asyncio
async def test_heartbeat_lease_renewal():
    """Verifies that background heartbeat keeps the lock alive beyond initial TTL."""
    client = get_redis_client()
    key = f"lock:test:{uuid.uuid4()}"

    # Lock with 2-second TTL, renewing every 0.6 seconds
    lock = DistributedLock(key=key, ttl_seconds=2, heartbeat_interval=0.6)
    await lock.acquire()

    # Sleep for 2.2 seconds (without heartbeat renewal, 2.0s TTL would expire and be deleted)
    await asyncio.sleep(2.2)

    # Verify lock is still held in Redis and lease has not been lost
    assert lock.is_held is True
    lock.assert_held()
    ttl = await client.ttl(key)
    assert ttl > 0
    assert await client.get(key) == lock.owner_token

    await lock.release()


@pytest.mark.asyncio
async def test_lease_lost_on_ownership_takeover():
    """Verifies that if the lock key is overtaken by another owner, heartbeat detects it and marks lease lost."""
    client = get_redis_client()
    key = f"lock:test:{uuid.uuid4()}"

    lock = DistributedLock(key=key, ttl_seconds=2, heartbeat_interval=0.5)
    await lock.acquire()

    # Overwrite the key with another owner's token in Redis
    alien_token = str(uuid.uuid4())
    await client.set(key, alien_token, ex=10)

    # Wait for heartbeat tick to detect mismatch
    await asyncio.sleep(1.2)

    assert lock.lease_lost is True
    assert lock.is_held is False

    with pytest.raises(LeaseLostError, match="Distributed lock lease was lost"):
        lock.assert_held()

    # Release should not delete the alien token
    released = await lock.release()
    assert released is False
    assert await client.get(key) == alien_token


@pytest.mark.asyncio
async def test_safe_release_by_owner():
    """Verifies that the owner safely releases the lock and allows immediate subsequent acquisition."""
    key = f"lock:test:{uuid.uuid4()}"
    lock_1 = DistributedLock(key=key, ttl_seconds=10, heartbeat_interval=3.0)
    lock_2 = DistributedLock(key=key, ttl_seconds=10, heartbeat_interval=3.0)

    await lock_1.acquire()
    assert await lock_2.acquire(raise_on_failure=False) is False

    await lock_1.release()

    # Worker 2 can now acquire
    assert await lock_2.acquire() is True
    await lock_2.release()


@pytest.mark.asyncio
async def test_protection_against_releasing_another_owners_lock():
    """Verifies that a lock instance never deletes a Redis key owned by a different worker."""
    client = get_redis_client()
    key = f"lock:test:{uuid.uuid4()}"

    lock = DistributedLock(key=key, ttl_seconds=10, heartbeat_interval=3.0)
    await lock.acquire()

    # Tamper key in Redis
    another_token = "foreign_worker_token"
    await client.set(key, another_token, ex=10)

    # Attempt release by original lock
    deleted = await lock.release()
    assert deleted is False

    # Foreign worker token must still be in Redis!
    assert await client.get(key) == another_token


@pytest.mark.asyncio
async def test_redis_connection_failure_propagation():
    """Verifies that Redis connection failures raise LockConnectionError rather than silent fallback."""
    key = f"lock:test:{uuid.uuid4()}"

    # Mock Redis client that raises ConnectionError
    mock_redis = AsyncMock()
    mock_redis.set.side_effect = aioredis.ConnectionError("Connection refused")

    lock = DistributedLock(key=key, redis_client=mock_redis)

    with pytest.raises(LockConnectionError, match="Redis connection failure"):
        await lock.acquire()


@pytest.mark.asyncio
async def test_heartbeat_cancellation_and_task_cleanup():
    """Verifies that heartbeat background task is cancelled and cleaned up upon release."""
    key = f"lock:test:{uuid.uuid4()}"
    lock = DistributedLock(key=key, ttl_seconds=10, heartbeat_interval=1.0)

    await lock.acquire()
    assert lock._heartbeat_task is not None
    assert not lock._heartbeat_task.done()

    await lock.release()
    assert lock._heartbeat_task is None


@pytest.mark.asyncio
async def test_async_context_manager_protocol():
    """Verifies DistributedLock works with async context manager and cleans up automatically."""
    client = get_redis_client()
    key = f"lock:test:{uuid.uuid4()}"

    async with DistributedLock(key=key, ttl_seconds=10, heartbeat_interval=2.0) as lock:
        assert lock.is_held is True
        lock.assert_held()
        assert await client.get(key) == lock.owner_token

    # Exited context: key must be deleted
    assert await client.get(key) is None


@pytest.mark.asyncio
async def test_concurrent_acquisition_serialized():
    """Verifies that multiple competing tasks serialize execution without race conditions."""
    key = f"lock:test:{uuid.uuid4()}"
    execution_order = []

    async def worker(worker_id: int):
        # 1.5s timeout allows subsequent workers to wait their turn
        lock = DistributedLock(
            key=key,
            ttl_seconds=5,
            heartbeat_interval=1.0,
            acquire_timeout=2.0,
            retry_delay=0.05,
        )
        async with lock:
            execution_order.append(f"start_{worker_id}")
            await asyncio.sleep(0.08)
            execution_order.append(f"end_{worker_id}")

    # Launch 3 workers concurrently
    await asyncio.gather(worker(1), worker(2), worker(3))

    # Verify each start is immediately followed by its end (strictly serialized execution)
    assert len(execution_order) == 6
    for i in range(0, 6, 2):
        start_item = execution_order[i]
        end_item = execution_order[i + 1]
        assert start_item.replace("start_", "") == end_item.replace("end_", "")


@pytest.mark.asyncio
async def test_for_chat_turn_factory_and_key_format():
    """Verifies that for_chat_turn builds the canonical tenant-scoped key."""
    biz_id = uuid.uuid4()
    req_id = uuid.uuid4()

    lock = DistributedLock.for_chat_turn(business_id=biz_id, request_id=req_id)
    assert lock.key == f"lock:chat:{biz_id}:{req_id}"


@pytest.mark.asyncio
async def test_assert_held_async_success():
    """Verifies that assert_held_async succeeds when the worker owns the active key."""
    client = get_redis_client()
    key = f"lock:test:{uuid.uuid4()}"
    lock = DistributedLock(key=key, ttl_seconds=10, heartbeat_interval=3.0)

    await lock.acquire()
    try:
        # Should not raise
        await lock.assert_held_async()
        assert lock.is_held is True
        assert lock.lease_lost is False
    finally:
        await lock.release()


@pytest.mark.asyncio
async def test_assert_held_async_expired_or_missing():
    """Verifies that assert_held_async marks lease lost and raises LeaseLostError if key vanished."""
    client = get_redis_client()
    key = f"lock:test:{uuid.uuid4()}"
    lock = DistributedLock(key=key, ttl_seconds=10, heartbeat_interval=3.0)

    await lock.acquire()
    try:
        # Simulate eviction or external expiration
        await client.delete(key)

        with pytest.raises(LeaseLostError, match="Distributed lock lease expired"):
            await lock.assert_held_async()

        assert lock.lease_lost is True
        assert lock.is_held is False
    finally:
        await lock.release()


@pytest.mark.asyncio
async def test_assert_held_async_different_owner():
    """Verifies that assert_held_async raises LeaseLostError if key was overtaken by another worker."""
    client = get_redis_client()
    key = f"lock:test:{uuid.uuid4()}"
    lock = DistributedLock(key=key, ttl_seconds=10, heartbeat_interval=3.0)

    await lock.acquire()
    try:
        # Another worker took the lock with a different token
        await client.set(key, "other-worker-token", ex=10)

        with pytest.raises(LeaseLostError, match="Distributed lock lease overtaken"):
            await lock.assert_held_async()

        assert lock.lease_lost is True
        assert lock.is_held is False
    finally:
        await lock.release()


@pytest.mark.asyncio
async def test_assert_held_async_redis_connection_error():
    """Verifies that assert_held_async fails closed with LockConnectionError if Redis is down."""
    key = f"lock:test:{uuid.uuid4()}"
    lock = DistributedLock(key=key, ttl_seconds=10, heartbeat_interval=3.0)

    await lock.acquire()
    try:
        with patch.object(lock.redis, "get", side_effect=aioredis.ConnectionError("Redis connection dropped")):
            with pytest.raises(LockConnectionError, match="Redis connection failure"):
                await lock.assert_held_async()

            assert lock.lease_lost is True
            assert lock.is_held is False
    finally:
        # Release won't delete since lease_lost is True
        await lock.release()


@pytest.mark.asyncio
async def test_heartbeat_redis_disconnect_marks_lease_lost():
    """Verifies that a Redis failure during background heartbeat renewal marks the lease as lost."""
    key = f"lock:test:{uuid.uuid4()}"
    # Use very short heartbeat interval for fast test
    lock = DistributedLock(key=key, ttl_seconds=5, heartbeat_interval=0.05)

    await lock.acquire()
    try:
        # Simulate Redis connection failure during eval
        with patch.object(lock.redis, "eval", side_effect=aioredis.ConnectionError("Network partition")):
            # Wait for heartbeat tick to encounter the error
            await asyncio.sleep(0.15)

            assert lock.lease_lost is True
            assert lock.is_held is False
            assert "Redis connectivity failed during renewal" in (lock.lease_lost_reason or "")
    finally:
        await lock.release()
