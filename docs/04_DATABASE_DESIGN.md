\# AgentDesk — Database Design



\*\*Document:\*\* 04\_DATABASE\_DESIGN.md

\*\*Project:\*\* AgentDesk — A Multi-Agent AI Platform for Small Businesses

\*\*Status:\*\* Approved Database Baseline

\*\*Related Documents:\*\*



\* `00\_MASTER\_DEVELOPMENT\_BLUEPRINT.md`

\* `01\_PROJECT\_SCOPE.md`

\* `02\_ARCHITECTURE.md`

\* `03\_TECH\_STACK.md`

\* SRS

\* SDD



\---



\# 1. Purpose



This document defines the database architecture and data model for AgentDesk.



It specifies:



\* Database technology

\* Tables/entities

\* Relationships

\* Primary keys

\* Foreign keys

\* Tenant isolation

\* Vector storage

\* Indexing

\* Constraints

\* Timestamps

\* Data lifecycle

\* Migration rules

\* Security requirements



The database must support the approved AgentDesk architecture without unnecessary complexity.



\---



\# 2. Approved Database



AgentDesk uses:



```text

PostgreSQL

\+

pgvector

```



PostgreSQL is the primary persistent data store.



pgvector provides vector storage and similarity search for the RAG system.



\---



\# 3. Database Decision — SQL Server Conflict



The SRS contains a Microsoft SQL Server 7 subsection.



That subsection is treated as an obsolete/template fragment.



The approved implementation is:



```text

PostgreSQL + pgvector

```



This is consistent with:



\* SRS software interface requirements

\* SRS database architecture

\* SDD architecture

\* SDD data design

\* Master Development Blueprint



No SQL Server implementation should be introduced.



\---



\# 4. Database Principles



The database must follow these principles:



1\. PostgreSQL is the persistent source of truth.

2\. Business-owned data must be tenant-scoped.

3\. Foreign keys must preserve referential integrity.

4\. IDs should not expose sensitive information.

5\. Timestamps should be stored consistently.

6\. Database constraints should enforce important invariants.

7\. Application validation does not replace database constraints.

8\. Vector data must remain tenant-scoped.

9\. Secrets must not be stored in plaintext.

10\. Schema changes must use Alembic migrations.

11\. Soft deletion should only be used where required.

12\. Avoid unnecessary denormalization.

13\. Avoid storing large files directly inside PostgreSQL when object storage is appropriate.



\---



\# 5. Tenant Model



The primary tenant is:



```text

Business

```



The ownership relationship is:



```text

Owner

&#x20; │

&#x20; └── Business

```



Most business data belongs to exactly one business.



Conceptually:



```text

Business

&#x20;├── AgentConfig

&#x20;├── KnowledgeBaseEntry

&#x20;├── Conversation

&#x20;├── Lead

&#x20;├── Appointment

&#x20;└── AnalyticsSnapshot

```



\---



\# 6. Entity Relationship Overview



```text

┌──────────────┐

│    Owner     │

└──────┬───────┘

&#x20;      │ 1

&#x20;      │

&#x20;      │ N

┌──────▼───────┐

│   Business   │

└──────┬───────┘

&#x20;      │

&#x20;      ├───────────────┐

&#x20;      │               │

&#x20;      ▼               ▼

┌──────────────┐ ┌───────────────┐

│ AgentConfig  │ │   Knowledge   │

└──────────────┘ └───────────────┘

&#x20;      │

&#x20;      │

&#x20;      ▼

┌─────────────────┐

│  Conversation    │

└────────┬────────┘

&#x20;        │

&#x20;        ▼

┌─────────────────┐

│     Message      │

└─────────────────┘



Business

&#x20;  │

&#x20;  ├───────────────► Lead

&#x20;  │

&#x20;  ├───────────────► Appointment

&#x20;  │

&#x20;  └───────────────► AnalyticsSnapshot

```



\---



\# 7. Primary Key Strategy



Use UUIDs for application entities.



Recommended:



```text

UUID / UUIDv4

```



Example:



```text

id UUID PRIMARY KEY

```



Reasons:



\* Avoid predictable sequential identifiers

\* Easier distributed operation

\* Safer public API identifiers

\* Good fit for multi-tenant applications



Database-generated UUIDs or application-generated UUIDs may be used consistently.



Do not mix multiple ID strategies unnecessarily.



\---



\# 8. Timestamp Strategy



Persistent records should normally include:



```text

created\_at

updated\_at

```



Use timezone-aware timestamps.



Recommended PostgreSQL type:



```text

TIMESTAMPTZ

```



Example:



```text

created\_at TIMESTAMPTZ NOT NULL

updated\_at TIMESTAMPTZ NOT NULL

```



Application display timezone may be based on the business configuration.



The database should store timestamps in a consistent timezone-aware representation.



\---



\# 9. Owner Table



Conceptual table:



```text

owners

```



Fields:



| Field         | Type        | Required | Description                       |

| ------------- | ----------- | -------: | --------------------------------- |

| id            | UUID        |      Yes | Primary key                       |

| email         | VARCHAR     |      Yes | Unique owner email                |

| password\_hash | VARCHAR     |       No | Argon2id password hash            |

| google\_sub    | VARCHAR     |       No | Google account identifier         |

| active        | BOOLEAN     |      Yes | Account status                    |

| verified      | BOOLEAN     |      Yes | Email/account verification status |

| created\_at    | TIMESTAMPTZ |      Yes | Creation time                     |

| updated\_at    | TIMESTAMPTZ |      Yes | Last update                       |



\---



\# 10. Owner Constraints



Required rules:



```text

email must be unique

email must be normalized

active must have a default

verified must have a default

password must never be stored in plaintext

```



Google-only accounts may have no local password.



The exact authentication account-linking behavior must be implemented consistently.



\---



\# 11. Business Table



Conceptual table:



```text

businesses

```



Fields:



| Field                | Type        | Required | Description                   |

| -------------------- | ----------- | -------: | ----------------------------- |

| id                   | UUID        |      Yes | Primary key                   |

| owner\_id             | UUID        |      Yes | Owner foreign key             |

| name                 | VARCHAR     |      Yes | Business name                 |

| vertical             | VARCHAR     |      Yes | Business category             |

| hours                | JSONB       |      Yes | Business operating hours      |

| whatsapp\_number      | VARCHAR     |       No | WhatsApp number               |

| contacts             | JSONB       |       No | Business contact information  |

| google\_calendar\_id   | VARCHAR     |       No | Connected calendar            |

| google\_refresh\_token | TEXT        |       No | Encrypted OAuth refresh token |

| created\_at           | TIMESTAMPTZ |      Yes | Creation time                 |

| updated\_at           | TIMESTAMPTZ |      Yes | Last update                   |



\---



\# 12. Business Ownership



Relationship:



```text

Owner 1 ───── N Business

```



Foreign key:



```text

businesses.owner\_id

&#x20;   →

owners.id

```



The application should verify ownership before accessing or modifying a business.



\---



\# 13. Business Hours



Business hours may be stored as JSONB.



Example conceptual structure:



```json

{

&#x20; "monday": {

&#x20;   "enabled": true,

&#x20;   "open": "09:00",

&#x20;   "close": "18:00"

&#x20; },

&#x20; "tuesday": {

&#x20;   "enabled": true,

&#x20;   "open": "09:00",

&#x20;   "close": "18:00"

&#x20; }

}

```



The exact schema should be validated at the application layer.



Invalid hours must not be accepted.



\---



\# 14. Business Contacts



Contacts may contain structured JSONB data.



Example:



```json

{

&#x20; "phone": "+92...",

&#x20; "email": "business@example.com",

&#x20; "address": "..."

}

```



Do not place arbitrary unvalidated objects into this field.



The API schema must define accepted fields.



\---



\# 15. AgentConfig Table



Conceptual table:



```text

agent\_configs

```



Fields:



| Field             | Type        | Required | Description              |

| ----------------- | ----------- | -------: | ------------------------ |

| business\_id       | UUID        |      Yes | Primary/foreign key      |

| voice\_enabled     | BOOLEAN     |      Yes | Voice agent status       |

| chat\_enabled      | BOOLEAN     |      Yes | Chat agent status        |

| lead\_enabled      | BOOLEAN     |      Yes | Lead agent status        |

| voice\_id          | VARCHAR     |       No | TTS voice identifier     |

| tone              | VARCHAR     |       No | Agent communication tone |

| greeting          | TEXT        |       No | Greeting                 |

| language\_priority | JSONB       |      Yes | Preferred languages      |

| created\_at        | TIMESTAMPTZ |      Yes | Creation time            |

| updated\_at        | TIMESTAMPTZ |      Yes | Last update              |



\---



\# 16. AgentConfig Relationship



AgentConfig is one-to-one with Business.



```text

Business 1 ───── 1 AgentConfig

```



Therefore:



```text

agent\_configs.business\_id

```



should be unique and serve as the primary key where appropriate.



Conceptually:



```text

PRIMARY KEY (business\_id)

```



\---



\# 17. Knowledge Base



Conceptual table:



```text

knowledge\_base\_entries

```



Fields:



| Field           | Type        | Required | Description              |

| --------------- | ----------- | -------: | ------------------------ |

| id              | UUID        |      Yes | Primary key              |

| business\_id     | UUID        |      Yes | Tenant                   |

| question        | TEXT        |       No | FAQ question             |

| answer          | TEXT        |      Yes | Knowledge content        |

| tags            | JSONB       |       No | Tags                     |

| language        | VARCHAR     |      Yes | Content language         |

| embedding       | VECTOR      |       No | pgvector embedding       |

| embedding\_stale | BOOLEAN     |      Yes | Embedding status         |

| source\_type     | VARCHAR     |      Yes | FAQ/PDF/DOCX/etc.        |

| source\_file\_id  | UUID        |       No | Associated uploaded file |

| chunk\_index     | INTEGER     |       No | Chunk number             |

| created\_at      | TIMESTAMPTZ |      Yes | Creation time            |

| updated\_at      | TIMESTAMPTZ |      Yes | Last update              |



\---



\# 18. Knowledge Base Design Note



The original SDD defines knowledge entries primarily as question/answer records.



For document-based RAG, the implementation needs to support chunks.



Therefore the approved implementation may extend the knowledge model with:



```text

source\_type

source\_file\_id

chunk\_index

```



This is an implementation-level clarification, not a change to the project scope.



If a separate document/file table is required, it must be documented before implementation.



\---



\# 19. Knowledge Source Types



Initial source types:



```text

FAQ

PDF

DOCX

```



Example:



```text

source\_type = "FAQ"

```



or:



```text

source\_type = "PDF"

```



\---



\# 20. Embedding Storage



The embedding column uses pgvector.



Conceptually:



```text

embedding VECTOR(N)

```



where `N` matches the selected embedding model's vector dimension.



The dimension must be finalized when the embedding model is selected.



Do not hard-code an arbitrary dimension.



\---



\# 21. Embedding Model Rule



The database vector dimension must match the active embedding provider/model.



Changing embedding models with a different dimension requires a controlled migration/re-indexing strategy.



Do not simply change the vector dimension while leaving existing embeddings unchanged.



\---



\# 22. Knowledge Tenant Isolation



Every knowledge query must include:



```text

business\_id

```



Example:



```text

WHERE business\_id = :current\_business\_id

```



Vector similarity must also be tenant-scoped.



Conceptually:



```text

WHERE business\_id = current\_business

ORDER BY embedding <similarity\_operator> query\_embedding

```



The application must never perform unrestricted global knowledge retrieval.



\---



\# 23. Conversation Table



Conceptual table:



```text

conversations

```



Fields:



| Field       | Type        | Required | Description           |

| ----------- | ----------- | -------: | --------------------- |

| id          | UUID        |      Yes | Primary key           |

| business\_id | UUID        |      Yes | Tenant                |

| channel     | VARCHAR     |      Yes | Voice/WhatsApp/Web    |

| language    | VARCHAR     |      Yes | Conversation language |

| started\_at  | TIMESTAMPTZ |      Yes | Start time            |

| ended\_at    | TIMESTAMPTZ |       No | End time              |

| status      | VARCHAR     |      Yes | Conversation state    |

| outcome     | VARCHAR     |       No | Final outcome         |

| summary     | TEXT        |       No | Conversation summary  |

| created\_at  | TIMESTAMPTZ |      Yes | Creation time         |

| updated\_at  | TIMESTAMPTZ |      Yes | Last update           |



\---



\# 24. Conversation Channels



Approved channels:



```text

Voice

WhatsApp

Web

```



Use a controlled enum or validated string strategy.



Unknown channel values must be rejected.



\---



\# 25. Conversation Status



Possible states may include:



```text

ACTIVE

COMPLETED

ABANDONED

FAILED

```



The exact state machine should be centralized rather than duplicated across endpoints.



\---



\# 26. Message Table



Conceptual table:



```text

messages

```



Fields:



| Field           | Type        | Required | Description                |

| --------------- | ----------- | -------: | -------------------------- |

| id              | UUID        |      Yes | Primary key                |

| conversation\_id | UUID        |      Yes | Conversation               |

| role            | VARCHAR     |      Yes | user/assistant/system/tool |

| content         | TEXT        |      Yes | Message content            |

| audio\_link      | TEXT        |       No | Audio object reference     |

| created\_at      | TIMESTAMPTZ |      Yes | Message timestamp          |



\---



\# 27. Message Relationship



```text

Conversation 1 ───── N Message

```



Foreign key:



```text

messages.conversation\_id

&#x20;   →

conversations.id

```



Messages must not exist without a valid conversation.



\---



\# 28. Message Roles



Supported application roles may include:



```text

USER

ASSISTANT

SYSTEM

TOOL

```



The application must control which roles can be created by external users.



A client must never be allowed to submit arbitrary `SYSTEM` messages.



\---



\# 29. Lead Table



Conceptual table:



```text

leads

```



Fields:



| Field           | Type        | Required | Description          |

| --------------- | ----------- | -------: | -------------------- |

| id              | UUID        |      Yes | Primary key          |

| business\_id     | UUID        |      Yes | Tenant               |

| conversation\_id | UUID        |       No | Source conversation  |

| name            | VARCHAR     |       No | Customer name        |

| contact         | VARCHAR     |       No | Phone/email/contact  |

| need            | TEXT        |       No | Customer requirement |

| score           | VARCHAR     |      Yes | Hot/Warm/Cold        |

| status          | VARCHAR     |      Yes | Lead status          |

| created\_at      | TIMESTAMPTZ |      Yes | Creation time        |

| updated\_at      | TIMESTAMPTZ |      Yes | Last update          |



\---



\# 30. Lead Relationship



```text

Business 1 ───── N Lead



Conversation 1 ───── N Lead

```



The conversation relationship may be nullable because leads may be imported or created through future channels.



For the initial FYP, conversation-generated leads are the primary flow.



\---



\# 31. Lead Score



Allowed initial categories:



```text

HOT

WARM

COLD

```



The backend should validate the allowed values.



The LLM should not have unrestricted authority to write arbitrary scores.



\---



\# 32. Lead Scoring



Recommended architecture:



```text

Conversation

&#x20;↓

LLM extracts buying signals

&#x20;↓

Structured validation

&#x20;↓

Deterministic scoring rules

&#x20;↓

Lead score

&#x20;↓

Database

```



The scoring rules must be implemented in testable backend logic.



\---



\# 33. Lead Status



Example statuses:



```text

NEW

CONTACTED

QUALIFIED

CONVERTED

LOST

```



The final initial status set must be defined consistently in the implementation.



Do not create different status definitions in different modules.



\---



\# 34. Appointment Table



Conceptual table:



```text

appointments

```



Fields:



| Field           | Type        | Required | Description         |

| --------------- | ----------- | -------: | ------------------- |

| id              | UUID        |      Yes | Primary key         |

| business\_id     | UUID        |      Yes | Tenant              |

| conversation\_id | UUID        |       No | Source conversation |

| customer\_name   | VARCHAR     |      Yes | Customer            |

| customer\_phone  | VARCHAR     |       No | Customer phone      |

| scheduled\_at    | TIMESTAMPTZ |      Yes | Appointment time    |

| service         | VARCHAR     |       No | Requested service   |

| google\_event\_id | VARCHAR     |       No | External event      |

| status          | VARCHAR     |      Yes | Appointment status  |

| created\_at      | TIMESTAMPTZ |      Yes | Creation time       |

| updated\_at      | TIMESTAMPTZ |      Yes | Last update         |



\---



\# 35. Appointment Status



Initial statuses may include:



```text

PENDING

CONFIRMED

RESCHEDULED

CANCELLED

COMPLETED

```



The exact state transitions must be centralized.



\---



\# 36. Appointment External Identifier



When an appointment is synchronized with Google Calendar:



```text

google\_event\_id

```



stores the external event identifier.



This allows:



\* Update

\* Reschedule

\* Cancel

\* Synchronization



The local appointment ID remains the application's primary identifier.



\---



\# 37. AnalyticsSnapshot Table



Conceptual table:



```text

analytics\_snapshots

```



Fields:



| Field       | Type        | Required | Description        |

| ----------- | ----------- | -------: | ------------------ |

| id          | UUID        |      Yes | Primary key        |

| business\_id | UUID        |      Yes | Tenant             |

| date        | DATE        |      Yes | Snapshot date      |

| calls       | INTEGER     |      Yes | Number of calls    |

| chats       | INTEGER     |      Yes | Number of chats    |

| leads       | INTEGER     |      Yes | Number of leads    |

| bookings    | INTEGER     |      Yes | Number of bookings |

| top\_intents | JSONB       |       No | Intent summary     |

| created\_at  | TIMESTAMPTZ |      Yes | Creation time      |



\---



\# 38. Analytics Uniqueness



A business should normally have one daily snapshot.



Recommended constraint:



```text

UNIQUE (business\_id, date)

```



This prevents duplicate daily snapshots.



\---



\# 39. Optional File Metadata Table



For document ingestion, the implementation may use a dedicated file table.



Conceptual table:



```text

knowledge\_files

```



Possible fields:



| Field             | Type        | Description           |

| ----------------- | ----------- | --------------------- |

| id                | UUID        | File identifier       |

| business\_id       | UUID        | Tenant                |

| filename          | VARCHAR     | Original filename     |

| storage\_key       | TEXT        | Object storage path   |

| mime\_type         | VARCHAR     | MIME type             |

| size\_bytes        | BIGINT      | File size             |

| processing\_status | VARCHAR     | Processing state      |

| error\_message     | TEXT        | Safe processing error |

| created\_at        | TIMESTAMPTZ | Upload time           |

| updated\_at        | TIMESTAMPTZ | Last update           |



This table is an implementation-level extension required to manage uploaded document lifecycle cleanly.



If implemented, it must remain tenant-scoped.



\---



\# 40. File Processing Status



Possible states:



```text

UPLOADED

PROCESSING

COMPLETED

FAILED

```



The worker updates processing status.



Example:



```text

Upload

&#x20;↓

UPLOADED

&#x20;↓

PROCESSING

&#x20;↓

COMPLETED

```



or:



```text

PROCESSING

&#x20;↓

FAILED

```



\---



\# 41. Integration Credential Storage



External credentials must not be stored as plaintext.



Examples:



```text

Google refresh token

WhatsApp credentials

Provider secrets

```



Application secrets should normally come from environment/secret management.



Business-specific OAuth credentials stored in PostgreSQL must be encrypted before persistence.



\---



\# 42. Sensitive Data Rules



Never store:



```text

Plaintext passwords

API keys in normal text columns

Unencrypted OAuth refresh tokens

Unnecessary provider secrets

```



Do not log sensitive values.



\---



\# 43. Foreign Key Relationships



Required relationships:



```text

businesses.owner\_id

&#x20;   → owners.id



agent\_configs.business\_id

&#x20;   → businesses.id



knowledge\_base\_entries.business\_id

&#x20;   → businesses.id



conversations.business\_id

&#x20;   → businesses.id



messages.conversation\_id

&#x20;   → conversations.id



leads.business\_id

&#x20;   → businesses.id



leads.conversation\_id

&#x20;   → conversations.id



appointments.business\_id

&#x20;   → businesses.id



appointments.conversation\_id

&#x20;   → conversations.id



analytics\_snapshots.business\_id

&#x20;   → businesses.id

```



If `knowledge\_files` is implemented:



```text

knowledge\_files.business\_id

&#x20;   → businesses.id

```



\---



\# 44. Delete Behavior



Delete behavior must be explicitly defined.



For child records belonging to a business, deletion should not accidentally leave orphaned records.



Example:



```text

Business deletion

&#x20;↓

Business-owned data cleanup

&#x20;↓

External credential cleanup

&#x20;↓

Object storage cleanup

```



Cascading deletes may be used where safe.



For sensitive or important records, explicit application-level deletion workflows may be preferable.



Do not blindly apply `CASCADE` to every relationship.



\---



\# 45. Conversation Retention



Approved retention requirements:



\* Owner/business data remains until deletion.

\* Transcripts remain until owner deletion.

\* Leads remain until owner deletion.

\* Call audio is purged after 30 days.



Audio storage cleanup should be handled through a background job.



\---



\# 46. Audio Storage



Audio should not normally be stored directly inside PostgreSQL.



Use object storage.



Database stores:



```text

audio\_link

```



or a storage object key.



The object itself is stored in S3-compatible storage.



\---



\# 47. Data Lifecycle



Example knowledge lifecycle:



```text

Upload

&#x20;↓

Validate

&#x20;↓

Store

&#x20;↓

Extract

&#x20;↓

Chunk

&#x20;↓

Embed

&#x20;↓

Persist vectors

&#x20;↓

Available for RAG

```



If knowledge changes:



```text

Update content

&#x20;↓

embedding\_stale = true

&#x20;↓

Re-embedding job

&#x20;↓

New embedding

&#x20;↓

embedding\_stale = false

```



\---



\# 48. Embedding Staleness



Whenever embedded content changes:



```text

embedding\_stale = true

```



The worker should regenerate the embedding.



This prevents stale vector representations from silently remaining active.



\---



\# 49. Database Indexing



Important indexes should include:



```text

owners.email



businesses.owner\_id



knowledge\_base\_entries.business\_id



conversations.business\_id

conversations.started\_at



messages.conversation\_id

messages.created\_at



leads.business\_id

leads.created\_at

leads.status



appointments.business\_id

appointments.scheduled\_at

appointments.status



analytics\_snapshots.business\_id

analytics\_snapshots.date

```



Exact indexes should be created through migrations.



\---



\# 50. Vector Index



A pgvector index should be introduced after confirming the selected embedding model and expected dataset size.



The index strategy should match:



\* Vector dimension

\* Similarity metric

\* Dataset size

\* PostgreSQL/pgvector capabilities



Do not select a vector index configuration blindly.



\---



\# 51. Vector Similarity Metric



The similarity metric must be consistent between:



\* Embedding generation

\* Database vector search

\* Vector index



The selected metric should be documented once the embedding implementation is finalized.



\---



\# 52. Query Isolation



Every repository query for business-owned data must be tenant-aware.



Bad:



```python id="evk1e6"

repository.get\_lead(lead\_id)

```



when the caller has no tenant authorization context.



Preferred:



```python id="o4c4ah"

repository.get\_lead(

&#x20;   lead\_id=lead\_id,

&#x20;   business\_id=current\_business\_id

)

```



\---



\# 53. Repository Responsibility



Repositories are responsible for persistence.



Examples:



```text

OwnerRepository

BusinessRepository

AgentConfigRepository

KnowledgeRepository

ConversationRepository

MessageRepository

LeadRepository

AppointmentRepository

AnalyticsRepository

KnowledgeFileRepository

```



Repositories should not contain:



\* LLM prompts

\* UI logic

\* HTTP request handling

\* Provider orchestration

\* Agent decision-making



\---



\# 54. Service Responsibility



Services contain application/business workflows.



Example:



```text

LeadService

&#x20;↓

LeadRepository

```



A service may coordinate:



```text

Repository

Provider

Business Rules

Transactions

```



but should not become a generic dumping ground.



\---



\# 55. Database Transaction Rules



Use transactions for logically atomic database operations.



Examples:



```text

Create Business + Initial AgentConfig

Create Lead + Related Records

Update Appointment Status

Update Knowledge Entry

```



External API calls should not be assumed to participate in PostgreSQL transactions.



\---



\# 56. Concurrency Considerations



Important operations require protection against race conditions.



Examples:



```text

Appointment booking

Lead updates

Agent configuration updates

Webhook processing

Knowledge processing

```



Use appropriate database constraints, transaction isolation, locking, or idempotency mechanisms.



Do not rely solely on frontend checks.



\---



\# 57. Appointment Concurrency



The system must avoid creating duplicate appointments for the same business/time slot when the business rules prohibit overlap.



Correct flow:



```text

Check availability

&#x20;↓

Validate requested slot

&#x20;↓

Create/update external calendar event

&#x20;↓

Persist local appointment

```



Concurrency protection must exist on the backend.



\---



\# 58. Webhook Idempotency Data



WhatsApp webhook processing should track an external event/message identifier where necessary.



The implementation may introduce a dedicated webhook event table if required.



Example:



```text

webhook\_events

```



Potential fields:



```text

id

provider

external\_event\_id

business\_id

status

received\_at

processed\_at

```



Unique constraints should prevent duplicate processing.



This is an implementation detail and must be kept minimal.



\---



\# 59. Database Security



Production PostgreSQL must use:



\* Strong credentials

\* TLS where supported/required

\* Restricted network access

\* Least-privilege database user

\* No public database exposure unless necessary

\* Secure backups



The application database user should not automatically receive unnecessary administrative privileges.



\---



\# 60. Backup Strategy



Production deployment should provide database backups.



At minimum:



```text

Regular automated backups

\+

Recovery procedure

```



The exact backup frequency depends on the deployment provider.



FYP development environments may use simpler backup arrangements.



\---



\# 61. Migration Strategy



Every schema change requires an Alembic migration.



Example:



```text

Modify SQLAlchemy model

&#x20;       ↓

Generate migration

&#x20;       ↓

Review migration

&#x20;       ↓

Test migration

&#x20;       ↓

Apply migration

```



Do not rely on:



```text

create\_all()

```



as the production schema management strategy.



\---



\# 62. Migration Rules



Migrations must be:



\* Version controlled

\* Reproducible

\* Reviewable

\* Tested

\* Ordered

\* Safe for existing data



Destructive migrations require special care.



\---



\# 63. Seed Data



Development may use seed data.



Seed data should be:



\* Clearly marked as development/test data

\* Reproducible

\* Safe

\* Free of real customer information



Production must not receive fake test data accidentally.



\---



\# 64. Database Naming Convention



Use consistent naming.



Recommended:



```text

snake\_case

```



Examples:



```text

business\_id

created\_at

updated\_at

google\_event\_id

embedding\_stale

```



Table names should use consistent plural naming.



Example:



```text

owners

businesses

conversations

messages

leads

appointments

```



\---



\# 65. JSONB Usage Rules



JSONB may be used for genuinely flexible structured data.



Approved examples:



```text

business hours

business contacts

tags

language priority

top intents

```



Do not use JSONB to avoid designing normal relational structures.



For frequently queried relational data, use proper columns/tables.



\---



\# 66. Data Validation



Validation exists at three levels:



```text

Frontend

&#x20;  ↓

API/Pydantic

&#x20;  ↓

Database constraints

```



Frontend validation improves UX.



Backend validation provides security.



Database constraints preserve integrity.



Frontend validation must never be treated as a security boundary.



\---



\# 67. Data Access Security Rule



Every request must follow:



```text

Authenticated User

&#x20;       ↓

Authorized Business

&#x20;       ↓

Tenant-Scoped Repository Query

&#x20;       ↓

Database

```



Never:



```text

Client-provided business\_id

&#x20;       ↓

Database

```



without authorization.



\---



\# 68. Performance Rules



Avoid:



\* N+1 queries

\* Unindexed filtering

\* Loading entire conversation histories unnecessarily

\* Loading entire knowledge bases

\* Full-table vector scans when the dataset requires an index

\* Excessive joins for simple dashboard queries



Use:



\* Proper indexes

\* Pagination

\* Selective columns

\* Efficient joins

\* Query limits

\* Vector retrieval limits



\---



\# 69. Pagination



Large datasets must be paginated.



Especially:



```text

Conversations

Messages

Leads

Appointments

Knowledge entries

```



Do not return an unlimited number of database records from an API endpoint.



\---



\# 70. Conversation Pagination



Conversation lists should return a limited page.



Conversation messages should also support pagination or controlled history retrieval.



The AI context window must not automatically include the entire conversation forever.



Relevant recent history and summarized context should be used.



\---



\# 71. Database and AI Separation



The LLM does not directly query PostgreSQL.



Correct:



```text

LLM

&#x20;↓

RAG/Tool Layer

&#x20;↓

Repository/Service

&#x20;↓

PostgreSQL

```



This protects:



\* Tenant isolation

\* Authorization

\* Data integrity

\* Predictability



\---



\# 72. Database and Frontend Separation



The frontend has no direct database access.



Correct:



```text

Next.js

&#x20;↓

FastAPI

&#x20;↓

Service

&#x20;↓

Repository

&#x20;↓

PostgreSQL

```



\---



\# 73. Database Source of Truth



PostgreSQL is authoritative for persistent AgentDesk application state.



```text

PostgreSQL

&#x20;   ↓

Business state

&#x20;   ↓

Application state

```



Redis is not authoritative.



External services are not authoritative for AgentDesk's local records.



\---



\# 74. Database Diagram — Simplified



```text

&#x20;                   ┌──────────────┐

&#x20;                   │    owners    │

&#x20;                   └──────┬───────┘

&#x20;                          │

&#x20;                          │ owner\_id

&#x20;                          ▼

&#x20;                   ┌──────────────┐

&#x20;                   │  businesses  │

&#x20;                   └──────┬───────┘

&#x20;                          │

&#x20;         ┌────────────────┼───────────────────┐

&#x20;         │                │                   │

&#x20;         ▼                ▼                   ▼

&#x20;┌────────────────┐ ┌───────────────┐ ┌────────────────┐

&#x20;│ agent\_configs  │ │   knowledge   │ │ conversations  │

&#x20;└────────────────┘ └───────────────┘ └───────┬────────┘

&#x20;                                              │

&#x20;                                              ▼

&#x20;                                      ┌──────────────┐

&#x20;                                      │   messages   │

&#x20;                                      └──────────────┘



&#x20;         Business

&#x20;            │

&#x20;      ┌─────┴─────┐

&#x20;      ▼           ▼

&#x20;   ┌──────┐   ┌──────────────┐

&#x20;   │ leads│   │ appointments │

&#x20;   └──────┘   └──────────────┘



&#x20;            Business

&#x20;                │

&#x20;                ▼

&#x20;       ┌────────────────────┐

&#x20;       │ analytics\_snapshots│

&#x20;       └────────────────────┘

```



\---



\# 75. Database Rules for Antigravity



Antigravity must:



1\. Read this document before modifying the schema.

2\. Use PostgreSQL.

3\. Use SQLAlchemy.

4\. Use Alembic migrations.

5\. Preserve tenant isolation.

6\. Add appropriate foreign keys.

7\. Add appropriate indexes.

8\. Avoid unnecessary schema changes.

9\. Never store plaintext secrets.

10\. Never bypass repositories without a documented reason.

11\. Update migrations when schema changes.

12\. Run database tests after schema changes.

13\. Never silently replace PostgreSQL with another database.



\---



\# 76. Schema Change Procedure



If Antigravity determines that a new table/field is required:



```text

Requirement

&#x20;   ↓

Check existing schema

&#x20;   ↓

Check this document

&#x20;   ↓

Determine whether existing structure is sufficient

&#x20;   ↓

If new structure is required:

&#x20;   ↓

Explain reason

&#x20;   ↓

Implement migration

&#x20;   ↓

Update database documentation if architectural

&#x20;   ↓

Run tests

```



Small implementation details may be added without changing the overall architecture, but major structural changes require approval.



\---



\# 77. Required Initial Tables



The initial implementation should include at minimum:



```text

owners

businesses

agent\_configs

knowledge\_base\_entries

conversations

messages

leads

appointments

analytics\_snapshots

```



Additional tables should only be introduced when justified by an actual requirement.



Possible implementation-support tables include:



```text

knowledge\_files

webhook\_events

```



if needed.



\---



\# 78. Initial Database Build Order



Recommended migration order:



```text

1\. owners

2\. businesses

3\. agent\_configs

4\. knowledge\_files (if implemented)

5\. knowledge\_base\_entries

6\. conversations

7\. messages

8\. leads

9\. appointments

10\. analytics\_snapshots

11\. indexes

12\. vector indexes

13\. additional constraints

```



Foreign-key dependencies should determine the final exact migration ordering.



\---



\# 79. FYP Demo Data



The FYP demonstration may use a single configured business.



However, the schema must remain multi-tenant.



```text

Demo:

1 Business



Architecture:

N Businesses

```



The demo limitation must never become an excuse to remove `business\_id` tenant boundaries.



\---



\# 80. Database Testing Requirements



Database tests must verify:



\### Ownership



```text

Owner → Business

```



\### Tenant isolation



```text

Business A cannot retrieve Business B data.

```



\### Foreign keys



Invalid relationships must fail.



\### Constraints



Invalid states must fail.



\### Vector retrieval



Knowledge retrieval must remain tenant-scoped.



\### Migrations



A fresh database must build successfully from migrations.



\---



\# 81. Definition of Done — Database



The database implementation is complete for a feature when:



\* Required tables exist

\* Models match the approved design

\* Foreign keys are correct

\* Constraints are defined

\* Tenant filtering exists

\* Indexes are appropriate

\* Migration exists

\* Migration runs successfully

\* Tests pass

\* Sensitive fields are protected

\* Documentation remains accurate



\---



\# 82. Final Database Baseline



The approved database architecture is:



```text

Database:

PostgreSQL



Vector:

pgvector



ORM:

SQLAlchemy 2.x



Migrations:

Alembic



Primary ID:

UUID



Timestamp:

TIMESTAMPTZ



Tenant:

Business



Persistent Source of Truth:

PostgreSQL



Temporary/Cache:

Redis



File Storage:

S3-compatible object storage

```



\---



\# 83. Final Database Principle



The most important database rule is:



> \*\*Every business-owned record and every knowledge retrieval operation must remain securely associated with the correct business tenant.\*\*



No feature is complete if it works functionally but can cross tenant boundaries.



\---



\*\*Document Status:\*\* Approved Database Baseline

\*\*Next Document:\*\* `05\_API\_DESIGN.md`



