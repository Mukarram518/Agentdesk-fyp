"""AgentDesk — Demo FAQ Seeding Script (Phase 5.5A.3).

Seeds the 12 approved multilingual demo FAQs into 'AgentDesk Demo Business'
using the existing KnowledgeService and local E5 embedding provider.

Guarantees & Safety Guards:
1. Strict tenant scoping: Targets only AgentDesk Demo Business (a4ba4534-20aa-4c7c-b4b8-4b68c71b1670).
2. Owner authorization check: Verifies owner (0185c0bb-a8ce-4a35-9ec7-cafd0dddc36a) exists and holds 'owner' role.
3. Safe dry-run default: Zero database writes and zero vector embeddings generated unless --apply is passed.
4. Duplicate prevention: Deterministically matches existing FAQs by (language, question) or answer text.
5. Service encapsulation: Uses knowledge_service.create_faq() to preserve all domain validations.
6. Local E5 embedding: Uses LocalSentenceTransformerProvider ('intfloat/multilingual-e5-small').
7. Transaction atomicity: Uses an explicit database transaction with automatic rollback on error.
8. Read/Insert only: Never deletes or modifies any existing database records.
9. Zero hardcoded secrets: All credentials resolved through app.core.config.

Usage:
    python scripts/seed_demo_faqs.py              # Dry run (default, safe)
    python scripts/seed_demo_faqs.py --help       # Show command options
    python scripts/seed_demo_faqs.py --apply      # Execute database insertion & embeddings
"""

import argparse
import asyncio
import io
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import uuid

# Ensure UTF-8 stdout and stderr encoding on Windows to support Urdu characters
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure backend root is on sys.path for direct script execution
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.core.database import async_session_factory, engine
from app.models.business import Business
from app.models.business_member import BusinessMember, MemberRole
from app.models.knowledge import (
    ACTIVE_EMBEDDING_MODEL,
    EMBEDDING_VECTOR_DIMENSION,
    KnowledgeBaseEntry,
    KnowledgeLanguage,
    KnowledgeSourceType,
)
from app.models.user import User
from app.providers.embeddings import (
    LocalSentenceTransformerProvider,
    get_embedding_provider,
)
from app.repositories.business_member_repository import business_member_repository
from app.repositories.business_repository import BusinessRepository
from app.repositories.knowledge_repository import knowledge_repository
from app.repositories.user_repository import UserRepository
from app.schemas.knowledge import FAQCreate
from app.services.knowledge_service import knowledge_service, KnowledgeService

# Approved constants for Phase 5.5A
TARGET_BUSINESS_ID = uuid.UUID("a4ba4534-20aa-4c7c-b4b8-4b68c71b1670")
TARGET_BUSINESS_NAME = "AgentDesk Demo Business"
TARGET_BUSINESS_SLUG = "agentdesk-demo-business"

TARGET_OWNER_ID = uuid.UUID("0185c0bb-a8ce-4a35-9ec7-cafd0dddc36a")
TARGET_OWNER_EMAIL = "awais@gmail.com"

DEFAULT_DATASET_REL_PATH = Path("docs") / "demo-data" / "DEMO_FAQS.md"
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_DATASET_PATH = REPO_ROOT / DEFAULT_DATASET_REL_PATH

EXPECTED_FAQ_COUNT = 12
SUPPORTED_LANGUAGES = frozenset({l.value for l in KnowledgeLanguage})


def load_demo_faqs_from_markdown(file_path: Path) -> List[Dict[str, Any]]:
    """Loads and validates the 12 approved FAQs from the markdown definition file.

    Extracts the JSON array enclosed in the markdown code fence, parses it,
    and validates each entry against the FAQCreate Pydantic schema.
    """
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Demo FAQ dataset not found at expected path: {file_path}. "
            "Please verify that docs/demo-data/DEMO_FAQS.md exists."
        )

    content = file_path.read_text(encoding="utf-8")

    # Match JSON block between ```json ... ```
    match = re.search(r"```json\s*(\[\s*\{.*?\}\s*\])\s*```", content, re.DOTALL)
    if not match:
        raise ValueError(
            f"Failed to find valid JSON code fence (```json [...] ```) in {file_path}."
        )

    json_str = match.group(1)
    try:
        raw_entries = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON dataset from {file_path}: {exc}") from exc

    if not isinstance(raw_entries, list):
        raise ValueError(f"Expected JSON dataset to be a list, got {type(raw_entries).__name__}.")

    if len(raw_entries) != EXPECTED_FAQ_COUNT:
        raise ValueError(
            f"Expected exactly {EXPECTED_FAQ_COUNT} FAQ entries, found {len(raw_entries)}."
        )

    validated_entries: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_entries, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Entry #{idx} must be a dictionary.")

        # Validate with FAQCreate Pydantic schema
        try:
            faq_schema = FAQCreate(
                question=item.get("question"),
                answer=item.get("answer", ""),
                tags=item.get("tags", []),
                language=item.get("language", KnowledgeLanguage.EN.value),
            )
        except Exception as exc:
            raise ValueError(f"Validation failed for FAQ entry #{idx}: {exc}") from exc

        if faq_schema.language not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Entry #{idx} has invalid language '{faq_schema.language}'. "
                f"Supported languages: {sorted(SUPPORTED_LANGUAGES)}"
            )

        validated_entries.append({
            "id": item.get("id", idx),
            "category": item.get("category", "unclassified"),
            "question": faq_schema.question,
            "answer": faq_schema.answer,
            "tags": faq_schema.tags or [],
            "language": faq_schema.language,
        })

    return validated_entries


async def verify_environment_and_targets(
    session: Any,
) -> Tuple[Business, User, BusinessMember]:
    """Verifies database environment, target business, target owner, and owner membership."""
    settings = get_settings()

    # Safety guard: refuse to run if testing environment is configured
    is_testing = (
        os.getenv("ENVIRONMENT") == "testing"
        or settings.ENVIRONMENT == "testing"
    )
    if is_testing:
        raise RuntimeError(
            "CRITICAL SAFETY GUARD: ENVIRONMENT is set to 'testing'. "
            "Demo FAQs belong to the development database ('agentdesk'), not 'agentdesk_test'. "
            "Aborting execution."
        )

    # Safety guard: verify database name
    parsed = urlparse(str(engine.url))
    db_name = parsed.path.lstrip("/").lower()
    if db_name != "agentdesk":
        raise RuntimeError(
            f"CRITICAL SAFETY GUARD: Expected target database 'agentdesk', but connected to '{db_name}'. "
            "Aborting execution."
        )

    # 1. Verify Business
    biz_repo = BusinessRepository()
    business = await biz_repo.get_by_id(session, TARGET_BUSINESS_ID)
    if not business:
        raise RuntimeError(
            f"Target business not found with ID: {TARGET_BUSINESS_ID}."
        )
    if not business.is_active:
        raise RuntimeError(
            f"Target business '{business.name}' ({TARGET_BUSINESS_ID}) is marked inactive."
        )
    if business.name != TARGET_BUSINESS_NAME:
        raise RuntimeError(
            f"Business ID matches {TARGET_BUSINESS_ID}, but name is '{business.name}' "
            f"(expected '{TARGET_BUSINESS_NAME}'). Aborting."
        )

    # 2. Verify User
    usr_repo = UserRepository()
    owner = await usr_repo.get_by_id(session, TARGET_OWNER_ID)
    if not owner:
        raise RuntimeError(
            f"Target owner user not found with ID: {TARGET_OWNER_ID}."
        )
    if not owner.is_active:
        raise RuntimeError(
            f"Target owner '{owner.email}' ({TARGET_OWNER_ID}) is marked inactive."
        )
    if owner.email.lower() != TARGET_OWNER_EMAIL.lower():
        raise RuntimeError(
            f"User ID matches {TARGET_OWNER_ID}, but email is '{owner.email}' "
            f"(expected '{TARGET_OWNER_EMAIL}'). Aborting."
        )

    # 3. Verify Membership and Owner Role
    membership = await business_member_repository.get_membership(
        session,
        business_id=TARGET_BUSINESS_ID,
        user_id=TARGET_OWNER_ID,
    )
    if not membership:
        raise RuntimeError(
            f"User '{owner.email}' ({TARGET_OWNER_ID}) has no membership record in "
            f"business '{business.name}' ({TARGET_BUSINESS_ID}). Aborting."
        )
    if membership.role != MemberRole.OWNER.value:
        raise RuntimeError(
            f"User '{owner.email}' has role '{membership.role}' in '{business.name}'. "
            f"Required role: '{MemberRole.OWNER.value}'. Aborting."
        )

    return business, owner, membership


async def find_existing_duplicates(
    session: Any,
    faqs: List[Dict[str, Any]],
) -> List[Tuple[Dict[str, Any], bool, Optional[uuid.UUID]]]:
    """Deterministically identifies which FAQ entries already exist for the target business.

    Matches by:
    1. Exact normalized (language, question) pair.
    2. Exact normalized answer text.
    """
    existing_entries = await knowledge_repository.list_by_business(
        session,
        business_id=TARGET_BUSINESS_ID,
        source_type=KnowledgeSourceType.FAQ.value,
        limit=500,
    )

    # Build deterministic lookup indexes from existing DB records
    existing_by_lang_q: Dict[Tuple[str, str], uuid.UUID] = {}
    existing_by_answer: Dict[str, uuid.UUID] = {}

    for entry in existing_entries:
        lang_key = entry.language.strip().lower()
        q_norm = (entry.question or "").strip().lower()
        ans_norm = entry.answer.strip().lower()

        if q_norm:
            existing_by_lang_q[(lang_key, q_norm)] = entry.id
        if ans_norm:
            existing_by_answer[ans_norm] = entry.id

    results: List[Tuple[Dict[str, Any], bool, Optional[uuid.UUID]]] = []
    for item in faqs:
        item_lang = item["language"].strip().lower()
        item_q = (item["question"] or "").strip().lower()
        item_ans = item["answer"].strip().lower()

        match_id: Optional[uuid.UUID] = None
        if (item_lang, item_q) in existing_by_lang_q:
            match_id = existing_by_lang_q[(item_lang, item_q)]
        elif item_ans in existing_by_answer:
            match_id = existing_by_answer[item_ans]

        is_duplicate = match_id is not None
        results.append((item, is_duplicate, match_id))

    return results


async def execute_seed_transaction(
    session: Any,
    business_id: uuid.UUID,
    checked_faqs: List[Tuple[Dict[str, Any], bool, Optional[uuid.UUID]]],
    verbose: bool = False,
) -> Tuple[int, int]:
    """Executes insertion of all non-duplicate FAQs within a single atomic transaction.

    Guarantees:
    - Closes any pre-existing read-only transaction on the session before calling session.begin().
    - Executes all insertions inside a single `async with session.begin():` context.
    - If any FAQ creation or embedding generation fails, the entire transaction rolls back automatically.
    - Returns (inserted_count, skipped_count).
    """
    # Close any autobegun read-only transaction from prior verification queries
    # so session.begin() can start a dedicated, atomic write transaction
    if session.in_transaction():
        await session.rollback()

    inserted_count = 0
    skipped_count = 0

    async with session.begin():
        for item, is_duplicate, match_id in checked_faqs:
            if is_duplicate:
                if verbose:
                    print(f"  [SKIP] Entry #{item.get('id', 0):02d} is duplicate of {match_id}")
                skipped_count += 1
                continue

            if verbose:
                print(f"  [INSERTING] Entry #{item.get('id', 0):02d} [{item.get('language')}] ...", end=" ", flush=True)

            # Strictly invoke knowledge_service.create_faq() to preserve service layer guarantees
            created_entry = await knowledge_service.create_faq(
                db=session,
                business_id=business_id,
                question=item.get("question"),
                answer=item.get("answer", ""),
                tags=item.get("tags", []),
                language=item.get("language", KnowledgeLanguage.EN.value),
            )

            if verbose:
                print(f"Done (Entry ID: {created_entry.id}, Stale: {created_entry.embedding_stale})")

            inserted_count += 1

    return inserted_count, skipped_count


async def run_seed_faqs(apply: bool, file_path: Path) -> int:
    """Executes the FAQ seeding workflow in dry-run or apply mode."""
    print("=" * 80)
    print("AGENTDESK — DEMO FAQ SEEDING WORKFLOW (Phase 5.5A.3)")
    print("=" * 80)
    print(f"Execution Mode: {'APPLY (Database Writes & Embeddings)' if apply else 'DRY RUN (Read-Only Validation)'}")
    print(f"Dataset File:   {file_path}")
    print("-" * 80)

    # Step 1: Load and validate local dataset
    try:
        faq_entries = load_demo_faqs_from_markdown(file_path)
    except Exception as exc:
        print(f"[FATAL] Failed to load dataset: {exc}")
        return 1

    print(f"[OK] Successfully loaded and validated {len(faq_entries)} FAQ entries from markdown.")

    # Step 2: Verify database connection, target business, and owner authorization
    async with async_session_factory() as session:
        try:
            business, owner, membership = await verify_environment_and_targets(session)
        except Exception as exc:
            print(f"[FATAL] Environment/Target verification failed: {exc}")
            return 1

        print(f"[OK] Target Database:    agentdesk (Host port: 5434)")
        print(f"[OK] Target Business:    {business.name} (ID: {business.id})")
        print(f"[OK] Target Owner:       {owner.full_name or 'Awais'} <{owner.email}> (ID: {owner.id})")
        print(f"[OK] Authorization:      Member role '{membership.role}' verified")

        # Step 3: Verify Embedding Provider Configuration
        embedding_prov = knowledge_service.embedding_provider
        provider_name = type(embedding_prov).__name__
        model_name = getattr(embedding_prov, "model_name", ACTIVE_EMBEDDING_MODEL)
        dim = getattr(embedding_prov, "dimension", EMBEDDING_VECTOR_DIMENSION)

        print(f"[OK] Embedding Provider: {provider_name}")
        print(f"[OK] Active Model:       {model_name} ({dim} dimensions)")

        if not isinstance(embedding_prov, LocalSentenceTransformerProvider):
            print(
                f"[WARNING] Expected LocalSentenceTransformerProvider, but resolved {provider_name}. "
                "Ensure local sentence-transformers environment is active."
            )

        # Step 4: Check for duplicates against existing DB records
        checked_faqs = await find_existing_duplicates(session, faq_entries)

        print("-" * 80)
        print("FAQ ENTRIES REVIEW:")
        print("-" * 80)

        to_insert_count = 0
        duplicate_count = 0

        for item, is_duplicate, match_id in checked_faqs:
            status_label = (
                f"[DUPLICATE — WOULD SKIP] (Existing entry ID: {match_id})"
                if is_duplicate
                else "[WOULD INSERT] (New entry)"
            )
            if is_duplicate:
                duplicate_count += 1
            else:
                to_insert_count += 1

            q_display = (item['question'] or '')[:75]
            if len(item['question'] or '') > 75:
                q_display += "..."

            print(f"Entry #{item['id']:02d} [{item['language']}] [{item['category']}]")
            print(f"  Question: {q_display}")
            print(f"  Tags:     {item['tags']}")
            print(f"  Status:   {status_label}")
            print()

        print("-" * 80)
        print("ANALYSIS SUMMARY:")
        print(f"  Total Valid Entries:  {len(faq_entries)}")
        print(f"  Already in Database:  {duplicate_count}")
        print(f"  Eligible for Insert:  {to_insert_count}")
        print("-" * 80)

        # If dry run mode, finish cleanly without database writes or embeddings
        if not apply:
            if session.in_transaction():
                await session.rollback()
            print("[DRY RUN COMPLETE] Zero database writes performed. Zero embeddings generated.")
            print("To execute insertion and generate vector embeddings, run with --apply.")
            print("=" * 80)
            return 0

        # Step 5: Apply Mode — Atomic Transaction
        print("[APPLY MODE] Beginning database insertion with vector embedding generation...")

        if to_insert_count == 0:
            if session.in_transaction():
                await session.rollback()
            print("[INFO] All 12 demo FAQs are already present in the database. Nothing to insert.")
            print("=" * 80)
            return 0

        try:
            inserted_count, skipped_count = await execute_seed_transaction(
                session=session,
                business_id=TARGET_BUSINESS_ID,
                checked_faqs=checked_faqs,
                verbose=True,
            )

            print("-" * 80)
            print("[SUCCESS] Transaction committed successfully.")
            print(f"  Inserted: {inserted_count} FAQs")
            print(f"  Skipped:  {skipped_count} duplicates")
            print("=" * 80)
            return 0

        except Exception as exc:
            if session.in_transaction():
                await session.rollback()
            print("-" * 80)
            print(f"[ERROR] Transaction failed and was rolled back: {exc}")
            print("=" * 80)
            return 1


def main() -> None:
    """CLI entry point for seed_demo_faqs."""
    parser = argparse.ArgumentParser(
        description="AgentDesk Demo FAQ Seeding Script (Phase 5.5A.3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate dataset and check targets without modifying anything (Default):
  python scripts/seed_demo_faqs.py

  # Apply insertions to the database and generate vector embeddings:
  python scripts/seed_demo_faqs.py --apply

  # Use a custom dataset path:
  python scripts/seed_demo_faqs.py --file ../docs/demo-data/DEMO_FAQS.md
        """,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply insertions to the database and generate vector embeddings. "
             "Default is dry-run mode (zero writes, zero embeddings).",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help=f"Path to markdown dataset file (default: {DEFAULT_DATASET_REL_PATH})",
    )

    args = parser.parse_args()

    exit_code = asyncio.run(run_seed_faqs(apply=args.apply, file_path=args.file))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
