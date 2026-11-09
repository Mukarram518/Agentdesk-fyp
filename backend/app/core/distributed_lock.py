"""AgentDesk Redis Distributed Lock.

Provides a robust, tenant-scoped distributed lock implementation for coordinating
concurrent chat requests, preventing duplicate LLM inferences, and enforcing
idempotency across distributed workers.

Features:
- Unique cryptographic owner token (UUIDv4) per acquisition.
- Atomic acquisition via Redis SET NX EX.
- Configurable lock TTL (default: 30 seconds).
- Background heartbeat lease renewal (default: every 10 seconds).
- Atomic Lua scripts for lease renewal and lock release ensuring only the owning
  worker can extend or delete the lock.
- Explicit acquisition timeouts and non-blocking acquisition support.
- Proactive lease-loss detection raising LeaseLostError to abort turn persistence.
- Complete cleanup of background heartbeat tasks upon cancellation or release.
- Explicit propagation of Redis connection failures as LockConnectionError.
"""

import asyncio
import logging
from typing import Optional, Union
import uuid

import redis.asyncio as aioredis
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


# =====================================================================
# Exceptions
# =====================================================================

class LockError(Exception):
    """Base exception for all distributed lock errors."""
    pass


class LockAcquisitionError(LockError):
    """Raised when a lock cannot be acquired within the timeout or is already held."""
    pass


class LeaseLostError(LockError):
    """Raised when an acquired lock lease has been lost, expired, or overtaken."""
    pass


class LockConnectionError(LockError):
    """Raised when Redis is unreachable or raises a connection error during lock operations."""
    pass


# =====================================================================
# Atomic Lua Scripts
# =====================================================================

# Renews the lock lease TTL strictly if the stored value matches the owner token.
# Returns 1 on success, 0 if the key is missing or owned by another worker.
RENEW_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], tonumber(ARGV[2]))
else
    return 0
end
"""

# Releases (deletes) the lock strictly if the stored value matches the owner token.
# Returns 1 on success, 0 if the key is missing or owned by another worker.
RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


# =====================================================================
# DistributedLock Implementation
# =====================================================================

class DistributedLock:
    """Distributed lock backed by Redis with heartbeat renewal and lease-loss safety.

    Guarantees:
    - Atomicity: Uses SET NX EX for acquisition and Lua scripts for renewal and release.
    - Safety: A worker can never extend or delete a lock held by another worker.
    - Heartbeat: Keeps the lease alive during long operations (e.g. LLM inference).
    - Lease Loss: If the lease expires or is overtaken, marks the lock as lost and raises
      LeaseLostError via assert_held() before persistence.
    """

    RENEW_LUA = RENEW_LUA
    RELEASE_LUA = RELEASE_LUA

    def __init__(
        self,
        key: str,
        redis_client: Optional[aioredis.Redis] = None,
        ttl_seconds: int = 30,
        heartbeat_interval: float = 10.0,
        acquire_timeout: float = 0.0,
        retry_delay: float = 0.1,
    ) -> None:
        """Initializes the distributed lock.

        Args:
            key: Redis lock key.
            redis_client: Optional aioredis.Redis instance (defaults to get_redis_client()).
            ttl_seconds: Lock lease duration in seconds (default: 30).
            heartbeat_interval: Interval between background renewal ticks (default: 10.0s).
            acquire_timeout: Maximum time in seconds to wait for acquisition. If 0.0,
                acquisition is non-blocking (immediate attempt only).
            retry_delay: Delay between acquisition attempts when acquire_timeout > 0.
        """
        if not key or not isinstance(key, str):
            raise ValueError("Lock key must be a non-empty string.")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer.")
        if heartbeat_interval <= 0 or heartbeat_interval >= ttl_seconds:
            raise ValueError("heartbeat_interval must be positive and strictly less than ttl_seconds.")

        self.key: str = key
        self._redis: Optional[aioredis.Redis] = redis_client
        self.ttl_seconds: int = ttl_seconds
        self.heartbeat_interval: float = heartbeat_interval
        self.acquire_timeout: float = acquire_timeout
        self.retry_delay: float = retry_delay

        self.owner_token: str = str(uuid.uuid4())
        self._is_held: bool = False
        self._lease_lost: bool = False
        self._lease_lost_reason: Optional[str] = None

        self._heartbeat_task: Optional[asyncio.Task] = None
        self._stop_heartbeat: asyncio.Event = asyncio.Event()

    @property
    def redis(self) -> aioredis.Redis:
        """Returns the active Redis client."""
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis

    @property
    def is_held(self) -> bool:
        """True if the lock was acquired and the lease has not been lost."""
        return self._is_held and not self._lease_lost

    @property
    def lease_lost(self) -> bool:
        """True if the lock lease was acquired but subsequently lost during heartbeat renewal."""
        return self._lease_lost

    @property
    def lease_lost_reason(self) -> Optional[str]:
        """Explanation of why the lease was lost, if applicable."""
        return self._lease_lost_reason

    @classmethod
    def for_chat_turn(
        cls,
        business_id: Union[uuid.UUID, str],
        request_id: Union[uuid.UUID, str],
        redis_client: Optional[aioredis.Redis] = None,
        ttl_seconds: int = 30,
        heartbeat_interval: float = 10.0,
        acquire_timeout: float = 0.0,
    ) -> "DistributedLock":
        """Factory creating a DistributedLock scoped to a specific business and request ID."""
        key = cls.build_chat_key(business_id, request_id)
        return cls(
            key=key,
            redis_client=redis_client,
            ttl_seconds=ttl_seconds,
            heartbeat_interval=heartbeat_interval,
            acquire_timeout=acquire_timeout,
        )

    @staticmethod
    def build_chat_key(
        business_id: Union[uuid.UUID, str],
        request_id: Union[uuid.UUID, str],
    ) -> str:
        """Constructs the canonical tenant-scoped chat lock key."""
        return f"lock:chat:{str(business_id)}:{str(request_id)}"

    def assert_held(self) -> None:
        """Guards critical operations by verifying that the lock lease is still valid.

        Raises:
            LeaseLostError: If the lease expired or ownership was lost.
            LockError: If the lock was never acquired or was already released.
        """
        if self._lease_lost:
            raise LeaseLostError(
                f"Distributed lock lease was lost for key '{self.key}': {self._lease_lost_reason}"
            )
        if not self._is_held:
            raise LockError(f"Distributed lock '{self.key}' is not currently held.")

    async def assert_held_async(self) -> None:
        """Actively verifies with Redis that the current worker's owner token is still held.

        Guarantees:
        1. Fast-fails if in-memory state already recorded lease loss.
        2. Probes Redis directly using the exact lock key.
        3. Fails closed (raises LockConnectionError) if Redis is unreachable.
        4. Marks lease as lost and raises LeaseLostError if the key expired or was overtaken.
        5. Never extends or mutates another worker's lease.

        Raises:
            LeaseLostError: If the key is missing/expired or owned by another worker.
            LockConnectionError: If Redis connectivity fails during verification.
            LockError: If the lock was never acquired or was already released.
        """
        # 1. Fast in-memory check
        self.assert_held()

        # 2. Active Redis probe
        try:
            raw_token = await self.redis.get(self.key)
        except (aioredis.RedisError, ConnectionError, OSError) as exc:
            self._mark_lease_lost(f"Redis connectivity failed during active lease probe: {exc}")
            raise LockConnectionError(
                f"Redis connection failure while verifying lock '{self.key}': {exc}"
            ) from exc

        if raw_token is None:
            self._mark_lease_lost("Lock key has expired or was removed from Redis")
            raise LeaseLostError(f"Distributed lock lease expired for key '{self.key}'")

        current_token = raw_token.decode("utf-8") if isinstance(raw_token, bytes) else str(raw_token)
        if current_token != self.owner_token:
            self._mark_lease_lost("Lock ownership was overtaken by another worker in Redis")
            raise LeaseLostError(
                f"Distributed lock lease overtaken by another worker for key '{self.key}'"
            )

    async def acquire(self, raise_on_failure: bool = True) -> bool:
        """Acquires the distributed lock atomically.

        Args:
            raise_on_failure: If True, raises LockAcquisitionError on acquisition failure.
                If False, returns False.

        Returns:
            bool: True if the lock was successfully acquired, False otherwise.

        Raises:
            LockAcquisitionError: If acquisition fails and raise_on_failure is True.
            LockConnectionError: If Redis connection fails.
        """
        # Generate a fresh owner token for each acquisition attempt cycle
        self.owner_token = str(uuid.uuid4())
        self._lease_lost = False
        self._lease_lost_reason = None
        self._stop_heartbeat.clear()

        deadline = asyncio.get_running_loop().time() + self.acquire_timeout

        while True:
            try:
                # Atomic acquisition via SET key token NX EX ttl
                acquired = await self.redis.set(
                    self.key,
                    self.owner_token,
                    nx=True,
                    ex=self.ttl_seconds,
                )
            except (aioredis.RedisError, ConnectionError, OSError) as exc:
                logger.error(f"Redis connection error acquiring lock '{self.key}': {exc}")
                raise LockConnectionError(
                    f"Redis connection failure while acquiring lock '{self.key}': {exc}"
                ) from exc

            if acquired:
                self._is_held = True
                self._start_heartbeat()
                logger.debug(
                    f"Acquired distributed lock '{self.key}' with token={self.owner_token} "
                    f"(ttl={self.ttl_seconds}s)"
                )
                return True

            # If non-blocking or deadline exceeded, stop
            now = asyncio.get_running_loop().time()
            if self.acquire_timeout <= 0.0 or now >= deadline:
                break

            # Bounded sleep before next retry
            sleep_duration = min(self.retry_delay, max(0.01, deadline - now))
            await asyncio.sleep(sleep_duration)

        if raise_on_failure:
            raise LockAcquisitionError(
                f"Could not acquire distributed lock for key '{self.key}' "
                f"within {self.acquire_timeout}s timeout."
            )
        return False

    async def release(self) -> bool:
        """Releases the lock safely using atomic Lua script.

        Stops the heartbeat background task, verifies that the stored token matches
        the owner token, and deletes the key. If the key is missing or held by another
        owner, deletes nothing and returns False.

        Returns:
            bool: True if the lock was owned and deleted, False otherwise.

        Raises:
            LockConnectionError: If Redis connection fails during release.
        """
        # 1. Stop background heartbeat immediately
        await self._stop_heartbeat_task()

        if not self._is_held:
            return False

        # If lease was already lost, do not attempt to delete another worker's lock
        if self._lease_lost:
            self._is_held = False
            return False

        # 2. Atomic release via Lua script
        try:
            result = await self.redis.eval(
                self.RELEASE_LUA,
                1,
                self.key,
                self.owner_token,
            )
            deleted = result == 1
        except (aioredis.RedisError, ConnectionError, OSError) as exc:
            logger.error(f"Redis connection error releasing lock '{self.key}': {exc}")
            self._is_held = False
            raise LockConnectionError(
                f"Redis connection failure while releasing lock '{self.key}': {exc}"
            ) from exc
        finally:
            self._is_held = False

        if deleted:
            logger.debug(f"Released distributed lock '{self.key}' for token={self.owner_token}")
        else:
            logger.warning(
                f"Distributed lock '{self.key}' was not deleted: already expired or overtaken."
            )
        return deleted

    # =================================================================
    # Heartbeat Lease Renewal
    # =================================================================

    def _start_heartbeat(self) -> None:
        """Spawns the background heartbeat lease renewal task."""
        self._stop_heartbeat.clear()
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(),
            name=f"heartbeat:{self.key}:{self.owner_token[:8]}",
        )

    async def _stop_heartbeat_task(self) -> None:
        """Cancels and awaits clean shutdown of the heartbeat renewal task."""
        self._stop_heartbeat.set()
        if self._heartbeat_task is not None:
            if not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except (asyncio.CancelledError, Exception):
                    pass
            self._heartbeat_task = None

    async def _heartbeat_loop(self) -> None:
        """Background loop renewing the lock lease periodically via atomic Lua script."""
        while self._is_held and not self._stop_heartbeat.is_set():
            try:
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break

            if self._stop_heartbeat.is_set():
                break

            try:
                # Atomic renewal via Lua script: extends TTL only if token matches
                result = await self.redis.eval(
                    self.RENEW_LUA,
                    1,
                    self.key,
                    self.owner_token,
                    str(self.ttl_seconds),
                )
                if result != 1:
                    # The key expired, was deleted, or belongs to another owner!
                    self._mark_lease_lost(
                        "Heartbeat renewal rejected: lock key expired or owner token mismatched."
                    )
                    break
                logger.debug(
                    f"Renewed distributed lock '{self.key}' for token={self.owner_token} "
                    f"(ttl extended to {self.ttl_seconds}s)"
                )
            except (aioredis.RedisError, ConnectionError, OSError) as exc:
                logger.warning(
                    f"Redis error during heartbeat renewal for '{self.key}': {exc}"
                )
                self._mark_lease_lost(f"Redis connectivity failed during renewal: {exc}")
                break

    def _mark_lease_lost(self, reason: str) -> None:
        """Marks the lease as lost and halts further renewals."""
        self._lease_lost = True
        self._is_held = False
        self._lease_lost_reason = reason
        logger.error(
            f"LEASE LOST for distributed lock '{self.key}' (token={self.owner_token}): {reason}"
        )

    # =================================================================
    # Async Context Manager Protocol
    # =================================================================

    async def __aenter__(self) -> "DistributedLock":
        """Acquires lock upon entering async context."""
        await self.acquire(raise_on_failure=True)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Releases lock and cleans up heartbeat upon exiting async context."""
        try:
            await self.release()
        except Exception as e:
            # Do not mask original exception if one was raised inside the context block
            if exc_type is None:
                raise
            logger.warning(f"Error during lock release in __aexit__: {e}")
