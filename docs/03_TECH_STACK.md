\# AgentDesk — Technology Stack



\*\*Document:\*\* 03\_TECH\_STACK.md

\*\*Project:\*\* AgentDesk — A Multi-Agent AI Platform for Small Businesses

\*\*Status:\*\* Approved Technology Baseline

\*\*Related Documents:\*\*



\* `00\_MASTER\_DEVELOPMENT\_BLUEPRINT.md`

\* `01\_PROJECT\_SCOPE.md`

\* `02\_ARCHITECTURE.md`



\---



\# 1. Purpose



This document defines the approved technology stack for AgentDesk.



Its purpose is to prevent unnecessary technology changes during development and to provide Antigravity with clear implementation constraints.



The stack is designed around:



\* Maintainability

\* FYP feasibility

\* Low operational complexity

\* Python AI/backend ecosystem

\* Modern web development

\* Modular architecture

\* Provider replacement

\* Security

\* Testing

\* Future scalability



\---



\# 2. Technology Stack Summary



| Area                  | Approved Technology                               |

| --------------------- | ------------------------------------------------- |

| Frontend              | Next.js                                           |

| Frontend Language     | TypeScript                                        |

| UI Styling            | Tailwind CSS                                      |

| Frontend Architecture | React/Next.js                                     |

| PWA                   | Next.js PWA approach                              |

| Backend               | Python                                            |

| API Framework         | FastAPI                                           |

| Validation            | Pydantic                                          |

| ORM                   | SQLAlchemy 2.x                                    |

| Migrations            | Alembic                                           |

| Database              | PostgreSQL                                        |

| Vector Search         | pgvector                                          |

| Cache                 | Redis                                             |

| Background Jobs       | Redis-backed worker architecture                  |

| File Storage          | S3-compatible storage                             |

| AI Orchestration      | Custom Python orchestrator                        |

| LLM                   | Provider abstraction                              |

| Embeddings            | Provider abstraction                              |

| Speech-to-Text        | Deepgram adapter                                  |

| Text-to-Speech        | ElevenLabs adapter                                |

| Messaging             | WhatsApp Business Cloud API adapter               |

| Calendar              | Google Calendar API adapter                       |

| Authentication        | Application-managed authentication + Google OAuth |

| Password Hashing      | Argon2id                                          |

| Backend Testing       | pytest                                            |

| Async Testing         | pytest-asyncio                                    |

| E2E Testing           | Playwright                                        |

| Containers            | Docker                                            |

| Local Services        | Docker Compose                                    |

| Version Control       | Git                                               |

| Repository            | GitHub                                            |

| Frontend Deployment   | Vercel-compatible deployment                      |

| Backend Deployment    | Railway/Render-compatible deployment              |

| Database Deployment   | Managed PostgreSQL                                |

| Redis Deployment      | Managed Redis                                     |



\---



\# 3. Frontend Stack



\## 3.1 Next.js



Next.js is the approved frontend framework.



Responsibilities:



\* Application routing

\* Dashboard

\* Authentication UI

\* Onboarding

\* Agent configuration

\* Knowledge management

\* Conversation history

\* Lead inbox

\* Appointment management

\* Analytics

\* Chat widget

\* Voice simulator



Do not replace Next.js with:



\* React-only SPA

\* Vue

\* Angular

\* Svelte

\* Other frontend frameworks



unless an architecture change is approved.



\---



\# 4. TypeScript



TypeScript is mandatory for frontend application code.



Benefits:



\* Type safety

\* Better API integration

\* Easier refactoring

\* Better IDE support

\* Reduced runtime errors



Avoid unnecessary use of:



```text

any

```



API response types should be explicitly defined.



\---



\# 5. Tailwind CSS



Tailwind CSS is the approved styling approach.



Use it for:



\* Layout

\* Responsive design

\* Forms

\* Dashboard

\* Tables

\* Cards

\* Modals

\* Navigation

\* Chat UI



Avoid introducing another CSS framework without approval.



Examples of frameworks that should not be added casually:



\* Bootstrap

\* Material UI

\* Chakra UI

\* Ant Design



A small utility or component library may only be introduced if it solves a real requirement and is approved.



\---



\# 6. Frontend API Communication



The frontend communicates with FastAPI through HTTP APIs.



Example:



```text

Next.js

&#x20;  ↓

API Client

&#x20;  ↓

FastAPI

```



The frontend must not communicate directly with:



```text

PostgreSQL

Redis

LLM providers

Deepgram

ElevenLabs

Google Calendar

WhatsApp APIs

```



when credentials or business logic would be exposed.



\---



\# 7. Frontend State Management



Do not introduce a large global state framework unless the application actually requires it.



Preferred approach:



\* React state for local UI state

\* Server/API state through a suitable data-fetching approach

\* URL state where appropriate

\* Context only for genuinely shared UI/application state



Avoid unnecessary complexity.



\---



\# 8. Backend Stack



\## 8.1 Python



Python is the primary backend and AI language.



It is used for:



\* FastAPI

\* AI orchestration

\* RAG

\* Agents

\* Tool execution

\* Data processing

\* Background jobs

\* Integration adapters

\* Testing



\---



\# 9. FastAPI



FastAPI is the approved backend API framework.



Responsibilities:



\* REST API

\* Authentication endpoints

\* Business endpoints

\* Knowledge endpoints

\* Conversation endpoints

\* Lead endpoints

\* Booking endpoints

\* Integration endpoints

\* Webhooks

\* WebSocket voice endpoint



FastAPI route handlers should remain thin.



\---



\# 10. Pydantic



Pydantic is used for:



\* API request validation

\* API response schemas

\* Configuration validation

\* Tool input schemas

\* Structured AI outputs where applicable



Example conceptual structure:



```text

HTTP Request

&#x20;    ↓

Pydantic Schema

&#x20;    ↓

Validated Data

&#x20;    ↓

Service

```



Never trust raw external input.



\---



\# 11. SQLAlchemy



SQLAlchemy 2.x is the approved ORM/data-access technology.



Used for:



\* PostgreSQL connection

\* Models

\* Queries

\* Transactions

\* Relationships



Repositories should encapsulate persistence operations.



Example:



```text

LeadService

&#x20;   ↓

LeadRepository

&#x20;   ↓

SQLAlchemy

&#x20;   ↓

PostgreSQL

```



\---



\# 12. Alembic



Alembic is the approved database migration system.



All schema changes must be represented through migrations.



Example:



```text

Change Model

&#x20;   ↓

Create Migration

&#x20;   ↓

Review Migration

&#x20;   ↓

Apply Migration

```



Do not manually modify production database schemas without corresponding migrations.



\---



\# 13. PostgreSQL



PostgreSQL is the approved primary database.



It stores:



\* Owner

\* Business

\* AgentConfig

\* KnowledgeBaseEntry

\* Conversation

\* Message

\* Lead

\* Appointment

\* AnalyticsSnapshot



PostgreSQL is the persistent source of truth for application data.



\---



\# 14. pgvector



pgvector is the approved vector-search extension.



It supports the AgentDesk RAG system.



Knowledge flow:



```text

Knowledge

&#x20;↓

Embedding

&#x20;↓

Vector

&#x20;↓

PostgreSQL + pgvector

```



Query:



```text

Question

&#x20;↓

Query Embedding

&#x20;↓

pgvector Similarity Search

&#x20;↓

Relevant Knowledge

```



Every vector search must respect:



```text

business\_id

```



tenant boundaries.



\---



\# 15. Database Decision



The approved database is:



\*\*PostgreSQL + pgvector\*\*



The SRS contains an obsolete Microsoft SQL Server 7 section.



That section is treated as a legacy/template fragment and is \*\*not an implementation requirement\*\*.



The architecture defined in the SRS architecture sections, SDD, and project blueprint takes precedence.



Therefore:



```text

PostgreSQL = APPROVED

SQL Server 7 = NOT APPROVED

```



\---



\# 16. Redis



Redis is used for temporary/high-speed state.



Approved uses include:



\* Cache

\* Rate limiting

\* Active voice session state

\* Temporary conversation/session state

\* Background job coordination



Redis should not be the permanent source of truth for:



\* Leads

\* Appointments

\* Conversations

\* Messages

\* Business configuration

\* Knowledge



Those belong in PostgreSQL.



\---



\# 17. Background Worker



AgentDesk requires background processing for operations that should not block API requests.



Examples:



```text

PDF processing

DOCX processing

Embedding generation

Analytics snapshots

Email notifications

Retryable jobs

Cleanup operations

```



The exact Redis-backed worker library should be selected once and used consistently.



Do not introduce multiple competing task-queue frameworks.



The selected worker must support:



\* Retries

\* Delayed execution where required

\* Failure handling

\* Job visibility

\* Idempotent processing



\---



\# 18. File Storage



Uploaded files must use S3-compatible object storage.



Examples:



```text

PDF

DOCX

Other approved business documents

```



Architecture:



```text

Browser

&#x20;↓

FastAPI

&#x20;↓

Validation

&#x20;↓

Object Storage

&#x20;↓

Background Processing

```



The exact storage provider can change without changing application architecture.



\---



\# 19. AI Architecture



AgentDesk must use provider abstraction.



The application should not scatter provider-specific API calls throughout business logic.



Approved conceptual interfaces:



```text

LLMProvider

EmbeddingProvider

STTProvider

TTSProvider

```



\---



\# 20. LLM Provider



The application must define an LLM interface.



Conceptual example:



```python

class LLMProvider:

&#x20;   async def generate(self, request):

&#x20;       ...

```



The application should depend on:



```text

LLMProvider

```



rather than:



```text

GroqProvider

```



everywhere.



A provider-specific implementation can then be used behind the interface.



\---



\# 21. Initial LLM Strategy



The initial FYP deployment should prioritize:



\* Low cost

\* Simple integration

\* Structured output/tool calling

\* Reasonable response quality

\* Urdu/English support

\* Replaceability



A low-cost provider may be used for the first implementation.



However, the architecture must not depend on one provider permanently.



Provider selection should be configurable.



Do not hard-code provider credentials or provider-specific assumptions into agents.



\---



\# 22. Embedding Provider



Embeddings also use an abstraction.



```text

EmbeddingProvider

&#x20;       │

&#x20;       └── Local Embedding Implementation

```



A local sentence-transformer model may be used initially to minimize API costs.



The embedding implementation must be replaceable.



\---



\# 23. Urdu/English Embedding Requirement



AgentDesk supports Urdu and English.



Therefore, embedding quality must be tested for both languages.



Do not assume an English-only embedding model is sufficient.



Before finalizing the embedding model, evaluate:



```text

English FAQ → English question

Urdu FAQ → Urdu question

English FAQ → Urdu question

Urdu FAQ → English question

```



The chosen model should be documented after evaluation.



\---



\# 24. Speech-to-Text



Deepgram is the approved initial STT provider adapter.



Architecture:



```text

Voice Agent

&#x20;  ↓

STTProvider

&#x20;  ↓

DeepgramProvider

&#x20;  ↓

Deepgram

```



The rest of the application must depend on `STTProvider`.



\---



\# 25. Text-to-Speech



ElevenLabs is the approved initial TTS provider adapter.



Architecture:



```text

Voice Agent

&#x20;  ↓

TTSProvider

&#x20;  ↓

ElevenLabsProvider

&#x20;  ↓

ElevenLabs

```



The rest of the application must not depend directly on ElevenLabs-specific implementation details.



\---



\# 26. WhatsApp



WhatsApp Business Cloud API is the approved messaging integration.



Architecture:



```text

WhatsApp

&#x20;  ↓

WhatsApp Adapter

&#x20;  ↓

Normalized Message

&#x20;  ↓

Conversation Service

&#x20;  ↓

AI Orchestrator

```



Webhook verification and idempotency are mandatory.



\---



\# 27. Google Calendar



Google Calendar API is the approved calendar integration.



Architecture:



```text

BookingService

&#x20;     ↓

CalendarProvider

&#x20;     ↓

GoogleCalendarProvider

&#x20;     ↓

Google Calendar API

```



OAuth credentials must be securely handled.



Refresh tokens must be encrypted at rest.



\---



\# 28. Email Provider



Email functionality should use an abstraction.



```text

EmailProvider

```



This allows the email service to change later.



Email may be used for:



\* Owner alerts

\* Lead notifications

\* Appointment notifications

\* System notifications



\---



\# 29. Authentication Technology



Authentication should use application-managed authentication.



Required components:



```text

Password hashing

Session/token management

Authentication middleware

Authorization

Google OAuth

```



Passwords must use a secure password hashing algorithm.



Approved direction:



```text

Argon2id

```



Do not store recoverable passwords.



\---



\# 30. Google Authentication



Google sign-in uses OAuth 2.0.



The backend is responsible for:



\* OAuth state validation

\* Token handling

\* Account linking

\* User identity mapping

\* Secure credential storage



Do not expose Google client secrets to the browser.



\---



\# 31. API Documentation



FastAPI's generated API documentation may be used during development.



Typical development endpoints:



```text

/docs

/redoc

```



Production exposure should be evaluated according to deployment/security requirements.



\---



\# 32. Testing Stack



\## Backend



Use:



```text

pytest

pytest-asyncio

```



Tests should cover:



\* Services

\* Repositories

\* API endpoints

\* Authentication

\* Authorization

\* Tenant isolation

\* Agent behavior

\* Tool validation

\* RAG

\* Integrations



\---



\# 33. Frontend/E2E Testing



Use:



```text

Playwright

```



for major end-to-end workflows.



Priority flows:



```text

Sign up

Login

Onboarding

Knowledge creation

Agent configuration

Chat

Lead capture

Appointment booking

Conversation history

```



\---



\# 34. Test Coverage



Target:



```text

Backend critical logic:

≥ 80% coverage

```



Coverage alone is not sufficient.



Critical security and business workflows must have explicit tests even if overall coverage is high.



\---



\# 35. Docker



Docker is the approved containerization technology.



Local development should support reproducible services.



Expected local architecture:



```text

Docker Compose

&#x20;   │

&#x20;   ├── frontend

&#x20;   ├── backend

&#x20;   ├── postgres

&#x20;   ├── redis

&#x20;   └── worker

```



\---



\# 36. Docker Compose



Docker Compose is used for local development and integration testing.



The configuration should allow a developer to start the core infrastructure without manually installing:



```text

PostgreSQL

Redis

```



on the host machine.



\---



\# 37. Git



Git is mandatory for source control.



Development should use small, meaningful commits.



Examples:



```text

feat: add authentication API

feat: add business onboarding

feat: add knowledge ingestion

fix: enforce tenant isolation

test: add lead scoring tests

docs: update architecture

```



Avoid massive commits containing unrelated changes.



\---



\# 38. GitHub



GitHub is the project repository.



Repository should contain:



```text

Source code

Documentation

Tests

Configuration templates

README

```



It must not contain:



```text

.env

API keys

OAuth secrets

Passwords

Private credentials

Production tokens

```



\---



\# 39. Environment Management



Environment variables are used for deployment-specific configuration.



Required categories:



```text

Application

Database

Redis

Authentication

LLM

Embeddings

Deepgram

ElevenLabs

Google

WhatsApp

Storage

Email

```



Example:



```text

DATABASE\_URL=

REDIS\_URL=



APP\_SECRET\_KEY=



LLM\_API\_KEY=



DEEPGRAM\_API\_KEY=

ELEVENLABS\_API\_KEY=



GOOGLE\_CLIENT\_ID=

GOOGLE\_CLIENT\_SECRET=



WHATSAPP\_ACCESS\_TOKEN=

WHATSAPP\_VERIFY\_TOKEN=



S3\_ENDPOINT=

S3\_ACCESS\_KEY=

S3\_SECRET\_KEY=

```



No actual credentials belong in Git.



\---



\# 40. Configuration Architecture



Configuration should be centralized.



Backend configuration should be loaded through a typed configuration system.



Conceptually:



```text

Environment Variables

&#x20;       ↓

Application Settings

&#x20;       ↓

Validated Configuration

&#x20;       ↓

Services

```



Do not repeatedly read environment variables directly throughout the codebase.



\---



\# 41. Logging



Use structured application logging.



Important categories:



```text

INFO

WARNING

ERROR

SECURITY

INTEGRATION

AI

WEBHOOK

BACKGROUND\_JOB

```



Logs should contain useful diagnostic context but must avoid unnecessary sensitive information.



\---



\# 42. HTTP Client



External APIs should be accessed through a consistent asynchronous HTTP client approach.



Do not create a different HTTP library for every integration.



External adapters should standardize:



\* Timeout

\* Retry

\* Error mapping

\* Logging

\* Request IDs where appropriate



\---



\# 43. Database Connection Management



Database connections must use proper pooling and lifecycle management.



The application must not create a new uncontrolled database connection for every request.



FastAPI application startup/shutdown should manage required resources correctly.



\---



\# 44. Async Architecture



FastAPI supports asynchronous operations.



Async should be used where appropriate for:



\* External API calls

\* WebSockets

\* I/O-bound operations

\* Database operations where configured

\* Background processing



CPU-heavy operations should be moved away from request handlers where necessary.



\---



\# 45. Dependency Management



Backend dependencies must be explicitly declared.



Use a reproducible dependency strategy.



The project must avoid installing random packages simply because they make one small task easier.



Before adding a dependency, evaluate:



```text

Is it necessary?

Is it maintained?

Does it introduce security risk?

Does it duplicate existing functionality?

Does it conflict with architecture?

```



\---



\# 46. Frontend Dependency Rules



The same principle applies to frontend packages.



Do not install packages for functionality already easily supported by:



\* Next.js

\* React

\* TypeScript

\* Tailwind CSS

\* Existing project utilities



Every significant new dependency should have a reason.



\---



\# 47. Versioning Strategy



Use stable versions compatible with the project environment.



Do not automatically upgrade major versions during feature development.



Major dependency upgrades should be treated as a separate change.



Example:



```text

Feature development

≠

Major framework migration

```



\---



\# 48. Provider Configuration



Providers should be configurable.



Conceptual configuration:



```text

LLM\_PROVIDER=...

EMBEDDING\_PROVIDER=...

STT\_PROVIDER=deepgram

TTS\_PROVIDER=elevenlabs

CALENDAR\_PROVIDER=google

MESSAGING\_PROVIDER=whatsapp

```



Exact environment variable names will be finalized during implementation.



\---



\# 49. Development Environments



AgentDesk should support:



```text

Development

Testing

Production

```



Development:



```text

Local Docker Compose

Development credentials

Test data

```



Testing:



```text

Isolated database

Mock providers where appropriate

Automated tests

```



Production:



```text

HTTPS

Secure secrets

Managed infrastructure

Production database

Monitoring/logging

```



\---



\# 50. Mocking External Providers



Tests should not depend unnecessarily on live external APIs.



Use mock/fake implementations where appropriate:



```text

FakeLLMProvider

FakeEmbeddingProvider

FakeSTTProvider

FakeTTSProvider

FakeCalendarProvider

FakeMessagingProvider

```



This improves:



\* Test speed

\* Reliability

\* Cost control

\* Reproducibility



\---



\# 51. AI Provider Failure Handling



Provider failures must be converted into application-level errors.



Example:



```text

Provider Timeout

&#x20;     ↓

Adapter

&#x20;     ↓

Application Error

&#x20;     ↓

Safe User Response

```



The rest of the application should not need to understand provider-specific error formats.



\---



\# 52. Security Technology Baseline



Minimum technology/security requirements:



```text

TLS/HTTPS

Argon2id password hashing

Secure session/token handling

Pydantic validation

SQLAlchemy parameterized queries

CORS configuration

Rate limiting

Secure headers

Encrypted OAuth refresh tokens

Environment-based secrets

Tenant authorization

Webhook verification

```



\---



\# 53. AI Structured Output



Whenever the application expects structured information from an LLM, use schema validation.



Example lead extraction:



```text

LLM

&#x20;↓

Structured JSON

&#x20;↓

Pydantic Validation

&#x20;↓

Business Rules

&#x20;↓

Database

```



Never assume that an LLM response is valid merely because it looks correct.



\---



\# 54. AI Tool Calling



Tool schemas should be strongly typed.



Example:



```text

capture\_lead

&#x20;   name: string

&#x20;   contact: string

&#x20;   need: string

```



Before execution:



```text

LLM Output

&#x20;↓

Schema Validation

&#x20;↓

Authorization

&#x20;↓

Business Rules

&#x20;↓

Execution

```



\---



\# 55. RAG Technology Stack



Approved RAG components:



```text

Document Parser

&#x20;       ↓

Text Chunker

&#x20;       ↓

EmbeddingProvider

&#x20;       ↓

PostgreSQL

&#x20;       ↓

pgvector

```



Query:



```text

User Question

&#x20;       ↓

EmbeddingProvider

&#x20;       ↓

pgvector

&#x20;       ↓

Relevant Chunks

&#x20;       ↓

LLMProvider

```



\---



\# 56. File Processing Technology



Initial document processing should support:



```text

PDF

DOCX

```



The implementation must:



\* Validate file size

\* Validate MIME type

\* Validate extension

\* Safely extract text

\* Handle malformed files

\* Prevent execution

\* Generate embeddings

\* Track processing status



\---



\# 57. PWA



AgentDesk should support Progressive Web App behavior.



Goals:



\* Responsive interface

\* Installable experience where practical

\* Mobile-friendly dashboard

\* Reliable basic application shell



PWA functionality must not compromise security or architecture.



\---



\# 58. Accessibility



The frontend should target:



\*\*WCAG 2.1 AA\*\*



Important areas:



\* Keyboard navigation

\* Form labels

\* Focus management

\* Color contrast

\* Screen-reader compatibility

\* Accessible buttons

\* Error messages

\* Responsive layouts



\---



\# 59. Browser Voice Simulator



The FYP voice implementation uses browser microphone input.



Technology boundary:



```text

Browser

&#x20;↓

WebSocket

&#x20;↓

FastAPI

&#x20;↓

STT Adapter

&#x20;↓

Orchestrator

&#x20;↓

TTS Adapter

&#x20;↓

Browser

```



Live telephony is not required for the FYP implementation.



The backend architecture should remain extensible for future telephony integration.



\---



\# 60. Deployment Stack



Recommended deployment structure:



```text

Frontend

&#x20;   ↓

Vercel-compatible hosting



Backend

&#x20;   ↓

Railway / Render-compatible hosting



Worker

&#x20;   ↓

Railway / Render-compatible worker



PostgreSQL

&#x20;   ↓

Managed PostgreSQL



Redis

&#x20;   ↓

Managed Redis



Files

&#x20;   ↓

S3-compatible storage

```



Deployment providers are replaceable.



The application must not become tightly coupled to a specific hosting provider.



\---



\# 61. Local Development Stack



A developer should be able to work locally with:



```text

Windows/Linux/macOS

Git

Docker

Docker Compose

Python

Node.js

npm/pnpm

VS Code or equivalent IDE

```



The project documentation should specify the exact supported runtime versions once finalized.



\---



\# 62. Technology Selection Rules



Before adding or changing technology:



\### Rule 1



Check existing stack.



\### Rule 2



Check architecture documents.



\### Rule 3



Prefer existing dependencies.



\### Rule 4



Avoid unnecessary complexity.



\### Rule 5



Use provider abstraction for external services.



\### Rule 6



Do not replace approved core technologies without approval.



\### Rule 7



Document approved architectural changes.



\---



\# 63. Technologies That Must Not Be Introduced Casually



Do not introduce:



```text

MongoDB

MySQL

SQL Server

Firebase as primary backend

Supabase as replacement backend

Django

Flask

Express

NestJS

Angular

Vue

Kubernetes

Kafka

RabbitMQ

Multiple competing task queues

Multiple ORMs

Multiple frontend frameworks

```



unless an explicit architecture change is approved.



This does not mean these technologies are inherently bad. They are simply outside the current approved AgentDesk baseline.



\---



\# 64. Architecture vs Provider Flexibility



Core architecture is stable.



Providers are replaceable.



Stable:



```text

Next.js

FastAPI

PostgreSQL

pgvector

Redis

Modular Monolith

Central Orchestrator

Provider Interfaces

```



Replaceable:



```text

LLM provider

Embedding provider

STT provider

TTS provider

Email provider

Storage provider

Deployment provider

```



This distinction must be maintained.



\---



\# 65. FYP Cost-Control Strategy



The implementation should minimize unnecessary paid API usage.



Preferred approach:



```text

Local embeddings

\+

Mock providers during tests

\+

Provider abstraction

\+

Background processing

\+

Efficient RAG

```



Live external APIs should primarily be used for:



\* Demonstrations

\* Integration testing

\* Required real functionality



Never design the system around the assumption that a third-party provider will remain permanently free or unlimited.



\---



\# 66. Technology Stack Approval



The following stack is the approved baseline:



```text

Frontend:

Next.js + TypeScript + Tailwind CSS



Backend:

Python + FastAPI + Pydantic



Database:

PostgreSQL + pgvector



ORM:

SQLAlchemy



Migrations:

Alembic



Cache:

Redis



Workers:

Redis-backed background worker



Storage:

S3-compatible



AI:

Custom Python Orchestrator



LLM:

Provider abstraction



Embeddings:

Provider abstraction



STT:

Deepgram adapter



TTS:

ElevenLabs adapter



Messaging:

WhatsApp Business Cloud API adapter



Calendar:

Google Calendar API adapter



Testing:

pytest + pytest-asyncio + Playwright



Containers:

Docker + Docker Compose



Source Control:

Git + GitHub

```



\---



\# 67. Final Technology Rule



Antigravity must \*\*not select technologies based on convenience during implementation\*\*.



If an approved technology can solve the requirement, use it.



If a new technology appears necessary:



```text

Identify requirement

&#x20;       ↓

Check approved stack

&#x20;       ↓

Check whether existing technology can solve it

&#x20;       ↓

If not, propose technology

&#x20;       ↓

Get approval

&#x20;       ↓

Update documentation

&#x20;       ↓

Implement

```



\---



\*\*Document Status:\*\* Approved Technology Baseline

\*\*Next Document:\*\* `04\_DATABASE\_DESIGN.md`



