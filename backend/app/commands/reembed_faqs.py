"""AgentDesk administrative CLI command for FAQ E5 re-embedding.

Usage:
    # Dry-run inspection across all businesses:
    python -m app.commands.reembed_faqs --dry-run

    # Dry-run inspection for a specific business:
    python -m app.commands.reembed_faqs --business-id <UUID> --dry-run

    # Controlled execution of up to 2 batches (max 100 FAQs):
    python -m app.commands.reembed_faqs --batch-size 50 --max-batches 2

    # Tenant-scoped execution:
    python -m app.commands.reembed_faqs --business-id <UUID> --batch-size 50
"""

import argparse
import asyncio
import os
import sys
import time
from typing import Optional
import uuid

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.database import async_session_factory
from app.models.knowledge import ACTIVE_EMBEDDING_MODEL
from app.repositories.knowledge_repository import knowledge_repository
from app.services.knowledge_service import knowledge_service, ReembedBatchResult


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AgentDesk FAQ E5 re-embedding administrative tool."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate and report eligible FAQ count without modifying any database records.",
    )
    parser.add_argument(
        "--business-id",
        type=str,
        default=None,
        help="UUID of the specific business tenant to re-embed. If omitted, operates across all tenants.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size per transaction (1 to 50, default: 50).",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Maximum number of batches to process before stopping (default: unlimited until complete).",
    )
    return parser.parse_args()


async def run_reembed(
    dry_run: bool = False,
    business_id_str: Optional[str] = None,
    batch_size: int = 50,
    max_batches: Optional[int] = None,
) -> int:
    # Parse and validate business_id if provided
    business_id: Optional[uuid.UUID] = None
    if business_id_str:
        try:
            business_id = uuid.UUID(business_id_str)
        except ValueError:
            print(f"Error: Invalid UUID format for --business-id '{business_id_str}'.")
            return 1

    bounded_batch_size = min(max(1, batch_size), 50)

    print("=" * 65)
    print("AgentDesk — FAQ E5 Re-embedding Administrative Command")
    print("=" * 65)
    print(f"Active Target Model : {ACTIVE_EMBEDDING_MODEL}")
    print(f"Tenant Scope        : {business_id or 'ALL TENANTS (Platform-wide)'}")
    print(f"Batch Size          : {bounded_batch_size}")
    print(f"Max Batches         : {max_batches or 'Unlimited (until complete)'}")
    print(f"Execution Mode      : {'DRY RUN (No database modifications)' if dry_run else 'LIVE EXECUTION'}")
    print("-" * 65)

    start_time = time.perf_counter()

    # 1. Pre-run count inspection
    async with async_session_factory() as db:
        initial_count = await knowledge_repository.count_faqs_needing_reembed(
            db=db,
            business_id=business_id,
            target_model=ACTIVE_EMBEDDING_MODEL,
        )
        invalid_count = await knowledge_repository.count_faqs_with_blank_answer(
            db=db,
            business_id=business_id,
        )

    print(f"Initial eligible FAQs requiring E5 embedding: {initial_count}")
    print(f"Unprocessable FAQs (blank/whitespace answer) : {invalid_count} (excluded from selection)")

    if initial_count == 0:
        print("\nAll eligible FAQ entries already have active, non-stale E5 embeddings.")
        if invalid_count > 0:
            print(f"Notice: {invalid_count} unprocessable FAQ(s) with blank answers remain excluded.")
        print("No work needed. Exiting.")
        return 0

    # 2. Dry Run Execution
    if dry_run:
        print("\n[DRY RUN] Simulating batch retrieval...")
        async with async_session_factory() as db:
            result: ReembedBatchResult = await knowledge_service.reembed_faq_batch(
                db=db,
                business_id=business_id,
                batch_size=bounded_batch_size,
                dry_run=True,
            )

        print(f"[DRY RUN] First batch eligible entries: {result.scanned}")
        print(f"[DRY RUN] Total remaining eligible    : {result.remaining}")
        print(f"[DRY RUN] Unprocessable blank entries : {invalid_count} (excluded from selection)")
        if result.entry_ids:
            print(f"[DRY RUN] Sample entry IDs (up to 5) :")
            for eid in result.entry_ids[:5]:
                print(f"   - {eid}")
        print("\n[DRY RUN] Verification complete. Zero records were modified.")
        return 0

    # 3. Live Batch Execution Loop
    print("\n[LIVE] Beginning iterative batch re-embedding...")
    total_reembedded = 0
    total_failed = 0
    batch_num = 0
    last_remaining = initial_count
    stopped_due_to_no_progress = False

    while True:
        if max_batches is not None and batch_num >= max_batches:
            print(f"\n[LIVE] Reached maximum requested batches ({max_batches}). Halting.")
            break

        batch_num += 1
        batch_start = time.perf_counter()

        async with async_session_factory() as db:
            try:
                res: ReembedBatchResult = await knowledge_service.reembed_faq_batch(
                    db=db,
                    business_id=business_id,
                    batch_size=bounded_batch_size,
                    dry_run=False,
                )
                await db.commit()
            except Exception as exc:
                await db.rollback()
                print(f"\n[ERROR] Batch {batch_num} failed and rolled back cleanly: {exc}")
                return 1

        batch_duration = time.perf_counter() - batch_start
        total_reembedded += res.reembedded
        total_failed += res.failed
        last_remaining = res.remaining

        print(
            f"  Batch {batch_num:3d}: Re-embedded {res.reembedded:2d} | "
            f"Failed {res.failed:2d} | Remaining {res.remaining:4d} | "
            f"Time: {batch_duration:.2f}s"
        )

        # Safety: avoid infinite loop if no progress is made
        if res.scanned == 0:
            if res.remaining > 0:
                print(f"\n[WARNING] Batch retrieved 0 entries, but {res.remaining} eligible records remain.")
                print("[WARNING] Halting to avoid infinite loop. Operation incomplete.")
                stopped_due_to_no_progress = True
            break

        if res.reembedded == 0:
            print(f"\n[WARNING] Batch made no progress (0 entries re-embedded, {res.failed} failed).")
            print(f"[WARNING] Halting to avoid infinite loop. Remaining eligible records: {res.remaining}.")
            stopped_due_to_no_progress = True
            break

        if res.remaining == 0:
            break

    total_duration = time.perf_counter() - start_time
    print("=" * 65)
    print("Re-embedding Operation Summary")
    print(f"Total Batches Executed  : {batch_num}")
    print(f"Total FAQs Re-embedded  : {total_reembedded}")
    print(f"Total FAQs Failed       : {total_failed}")
    print(f"Total Remaining Eligible: {last_remaining}")
    print(f"Unprocessable Excluded  : {invalid_count}")
    print(f"Elapsed Time            : {total_duration:.2f}s")
    print("=" * 65)

    if last_remaining == 0 and not stopped_due_to_no_progress:
        print("\n[LIVE] All eligible FAQ entries have been successfully processed.")
        return 0
    else:
        print(f"\n[LIVE] Process completed with {last_remaining} eligible entries remaining. Incomplete.")
        return 1 if stopped_due_to_no_progress else 0


def main() -> None:
    args = parse_args()
    exit_code = asyncio.run(
        run_reembed(
            dry_run=args.dry_run,
            business_id_str=args.business_id,
            batch_size=args.batch_size,
            max_batches=args.max_batches,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

