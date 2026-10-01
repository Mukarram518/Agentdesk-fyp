\# AgentDesk — AI Coding Agent Instructions



\## 1. Project Identity



Project: AgentDesk



AgentDesk is a multi-agent AI platform for small businesses.



The platform provides configurable AI agents for:



\* Web chat

\* WhatsApp

\* Lead generation and qualification

\* Appointment booking

\* Browser-based voice simulation

\* Shared business knowledge/RAG

\* Urdu and English conversations

\* Conversation history

\* Business dashboard and analytics



This is an FYP project.



The implementation must follow the approved project documentation.



\---



\## 2. Source of Truth



Before making implementation changes, read the relevant documentation in:



```text

docs/

```



The master source of truth is:



```text

docs/00\_MASTER\_DEVELOPMENT\_BLUEPRINT.md

```



Important architecture documents include:



```text

docs/01\_PROJECT\_SCOPE.md

docs/02\_ARCHITECTURE.md

docs/03\_TECH\_STACK.md

docs/04\_DATABASE\_DESIGN.md

docs/05\_API\_DESIGN.md

docs/06\_AI\_ORCHESTRATOR.md

docs/07\_AGENT\_DESIGN.md

docs/08\_RAG\_DESIGN.md

docs/09\_INTEGRATIONS.md

docs/10\_SECURITY.md

docs/11\_FOLDER\_STRUCTURE.md

docs/12\_DEVELOPMENT\_ROADMAP.md

docs/13\_TESTING\_STRATEGY.md

docs/14\_DEPLOYMENT.md

docs/15\_ANTIGRAVITY\_RULES.md

```



Do not treat assumptions as project requirements.



If documentation conflicts with another document, do not silently choose an implementation.



Stop and report the conflict.



\---



\## 3. Approved Technology Stack



\### Frontend



\* Next.js

\* TypeScript

\* Tailwind CSS

\* PWA support



\### Backend



\* Python

\* FastAPI

\* Pydantic

\* SQLAlchemy 2

\* Alembic



\### Database



\* PostgreSQL

\* pgvector



\### Cache / Background Processing



\* Redis

\* A single approved background-worker framework used consistently throughout the project



\### AI



\* Custom Python AI orchestrator

\* Provider abstraction

\* Function/tool calling



\### AI Provider Architecture



Providers must remain replaceable through interfaces/adapters.



Examples:



```text

LLMProvider

EmbeddingProvider

STTProvider

TTSProvider

CalendarProvider

MessagingProvider

```



Do not tightly couple business logic to a specific provider SDK.



\---



\## 4. Database Architecture



PostgreSQL + pgvector is the approved database architecture.



The Microsoft SQL Server 7 section appearing in the SRS is an obsolete/template fragment and is NOT an implementation requirement.



Do not introduce SQL Server.



Use PostgreSQL and pgvector according to the approved architecture documents.



\---



\## 5. Backend Architecture



The backend follows layered architecture:



```text

API

&#x20;↓

Service

&#x20;↓

Repository

&#x20;↓

Database

```



Responsibilities must remain separated.



\### API Layer



Responsible for:



\* HTTP routes

\* Request validation

\* Authentication dependency usage

\* Response schemas

\* API-level authorization checks



\### Service Layer



Responsible for:



\* Business logic

\* Use cases

\* Transaction coordination

\* Calling repositories

\* Calling controlled tools/providers where appropriate



\### Repository Layer



Responsible for:



\* Database access

\* Queries

\* Persistence operations



\### Database Layer



Responsible for:



\* SQLAlchemy models

\* Database configuration

\* Migrations

\* PostgreSQL/pgvector integration



Do not place business logic directly inside route handlers.



\---



\## 6. AI Architecture



AI requests should follow:



```text

API

&#x20;↓

Orchestrator

&#x20;↓

Agent

&#x20;↓

Tool

&#x20;↓

Service / Provider

```



Agents must NOT directly:



\* Access the database

\* Execute arbitrary SQL

\* Call external APIs directly

\* Access secrets

\* Bypass authorization



Agents request controlled tools.



The backend validates:



\* Tool name

\* Tool arguments

\* User authorization

\* Business/tenant scope

\* Allowed operation



Only then may the backend execute the tool.



\---



\## 7. Multi-Tenancy



Multi-tenancy is mandatory from the beginning.



Business-owned data must be scoped to the correct business/tenant.



Never trust a `business\_id` supplied by the frontend.



The backend must determine the authenticated user's authorized business.



Every protected operation must verify:



```text

Authenticated User

&#x20;       ↓

Authorized Business

&#x20;       ↓

Business-Scoped Data

```



Never allow one business to access another business's:



\* Conversations

\* Messages

\* Leads

\* Appointments

\* Knowledge

\* Files

\* Agent configuration

\* Analytics

\* Integrations

\* Credentials



Tenant-isolation tests are required.



\---



\## 8. Authentication and Security



Security is a core requirement, not a later feature.



Follow:



```text

docs/10\_SECURITY.md

```



Important rules:



\* Never store plaintext passwords.

\* Use secure password hashing.

\* Never expose secrets to the frontend.

\* Never commit `.env` files containing secrets.

\* Use `.env.example` for variable names only.

\* Validate all API input.

\* Enforce authorization on the backend.

\* Protect object-level access.

\* Validate uploaded files.

\* Verify WhatsApp webhook signatures.

\* Protect WebSocket connections.

\* Encrypt sensitive OAuth credentials at rest.

\* Apply rate limits where required.

\* Do not expose internal errors or stack traces to users.



\---



\## 9. AI Security



AI output must never bypass backend security.



Protect against:



\* Prompt injection

\* Tool abuse

\* Unauthorized tool calls

\* Cross-tenant retrieval

\* Sensitive information leakage

\* Malicious uploaded documents

\* Manipulated tool arguments



RAG retrieval must always be tenant-scoped.



Never allow retrieved knowledge from Business A to be returned to Business B.



\---



\## 10. RAG Rules



The knowledge pipeline follows:



```text

Upload

&#x20;↓

Validate

&#x20;↓

Extract

&#x20;↓

Clean

&#x20;↓

Chunk

&#x20;↓

Embed

&#x20;↓

Store in pgvector

```



Query flow:



```text

User Query

&#x20;↓

Embedding

&#x20;↓

Tenant-Scoped Similarity Search

&#x20;↓

Relevant Context

&#x20;↓

Orchestrator

&#x20;↓

LLM

```



Never send an entire uploaded document to the LLM when retrieval can provide the relevant context.



Embedding providers must remain replaceable.



Multilingual and Urdu retrieval quality must be tested rather than assumed.



\---



\## 11. External Integrations



External providers must be isolated behind provider/adaptor layers.



Relevant integrations include:



\* LLM provider

\* Embeddings

\* Deepgram

\* ElevenLabs

\* WhatsApp Business Cloud API

\* Google Calendar

\* Email

\* S3-compatible object storage



Do not scatter provider SDK calls throughout the application.



\---



\## 12. Frontend Architecture



Frontend responsibilities should remain separated.



Preferred flow:



```text

Route

&#x20;↓

Feature

&#x20;↓

Hook

&#x20;↓

Service

&#x20;↓

API Client

&#x20;↓

FastAPI Backend

```



The frontend must not contain backend business rules.



Do not expose secrets or provider credentials in client-side code.



\---



\## 13. Development Process



AgentDesk must be implemented phase-by-phase.



Do NOT attempt to build the entire platform at once.



Follow:



```text

Documentation

&#x20;↓

Implementation

&#x20;↓

Tests

&#x20;↓

Manual Verification

&#x20;↓

Documentation Check

&#x20;↓

Git Commit

&#x20;↓

Git Push

&#x20;↓

Next Phase

```



The roadmap is defined in:



```text

docs/12\_DEVELOPMENT\_ROADMAP.md

```



Do not skip phases without explicit approval.



\---



\## 14. Architecture Change Rule



Do not redesign the architecture without approval.



If you discover an architecture problem, STOP implementation and report:



1\. Current architecture

2\. Problem discovered

3\. Why the current design is insufficient

4\. Proposed change

5\. Files/documents affected

6\. Risks

7\. Alternatives



Then wait for human approval.



Do not automatically implement the proposed architecture change.



\---



\## 15. Code Quality Rules



Before creating new code:



1\. Inspect the existing repository.

2\. Search for existing implementations.

3\. Reuse existing utilities/components/services when appropriate.

4\. Avoid duplicate functionality.

5\. Keep changes focused.

6\. Do not perform unrelated refactoring.



Use clear naming and maintainable structure.



Prefer small, understandable modules over unnecessarily complex abstractions.



\---



\## 16. Testing Rules



Testing is part of implementation.



Do not:



\* Delete tests because they fail.

\* Disable tests to make a build pass.

\* Weaken assertions without approval.

\* Claim tests passed when they were not executed.



Follow:



```text

docs/13\_TESTING\_STRATEGY.md

```



Important test areas include:



\* Authentication

\* Authorization

\* Tenant isolation

\* BOLA protection

\* API validation

\* Database operations

\* RAG retrieval

\* Urdu/English behavior

\* Orchestrator routing

\* Tool authorization

\* Agent behavior

\* Booking concurrency

\* WebSocket security

\* File upload validation

\* Webhook verification

\* Frontend flows

\* End-to-end FYP flows



Backend coverage target:



```text

>= 80%

```



Coverage is not a substitute for meaningful tests.



\---



\## 17. Secrets and Environment Variables



Never commit:



```text

.env

```



Never hardcode:



\* API keys

\* Passwords

\* OAuth secrets

\* Database passwords

\* Provider credentials

\* JWT secrets

\* Encryption keys



Use:



```text

.env.example

```



for documented variable names.



\---



\## 18. Git Rules



Use small logical commits.



Examples:



```text

feat: add authentication foundation

feat: add business onboarding

feat: add knowledge base

feat: add orchestrator foundation

test: add authentication tests

fix: enforce business tenant isolation

docs: update architecture

```



Do not create one huge commit containing unrelated features.



Do not rewrite Git history unless explicitly instructed.



\---



\## 19. Destructive Operations



Never perform destructive operations without explicit approval.



This includes:



\* Deleting important files

\* Dropping databases

\* Removing migrations

\* Resetting production data

\* Rewriting Git history

\* Removing major dependencies

\* Replacing architecture

\* Disabling security controls

\* Disabling tests



If destructive action appears necessary, stop and ask.



\---



\## 20. Current Project State



The repository currently contains the project documentation/planning layer.



Implementation should begin only after the documentation has been reviewed and the implementation phase has been explicitly started.



Do not assume that a missing implementation means it should be created immediately.



\---



\## 21. Human Decision Authority



The human developer remains the final decision-maker for:



\* Architecture

\* Technology changes

\* Database redesign

\* Provider changes

\* Security exceptions

\* Major dependencies

\* Deployment architecture

\* Breaking API changes

\* Destructive operations

\* Scope changes



The coding agent provides analysis and implementation assistance.



The coding agent does not independently redefine the project.



\---



\## 22. Default Behavior



When given a new task:



1\. Read the relevant documentation.

2\. Inspect existing code.

3\. Identify affected files.

4\. Check architectural consistency.

5\. Implement the smallest correct change.

6\. Add/update tests.

7\. Run relevant tests.

8\. Report exactly what changed.

9\. Report exactly what was tested.

10\. Report any remaining issues.



If requirements are ambiguous and the ambiguity could affect architecture, security, data integrity, or project scope:



STOP and ask for clarification.



Do not guess.



