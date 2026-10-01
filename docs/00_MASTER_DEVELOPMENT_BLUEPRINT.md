\# AgentDesk — Master Development Blueprint



\*\*Project:\*\* AgentDesk — A Multi-Agent AI Platform for Small Businesses

\*\*Team:\*\* Mukarram Ali \& Hadia Saleem

\*\*Document:\*\* Master Development Blueprint

\*\*Version:\*\* 1.0

\*\*Status:\*\* Implementation Baseline

\*\*Source Documents:\*\* SRS v1.0 and SDD v1.0



\---



\## 1. Purpose



This document is the master implementation plan for AgentDesk.



It converts the approved Software Requirements Specification (SRS) and Software Design Document (SDD) into a controlled development blueprint that developers and AI coding tools must follow.



This document defines:



\* approved project scope

\* system architecture

\* technology stack

\* database architecture

\* backend architecture

\* frontend architecture

\* AI orchestration

\* agent responsibilities

\* RAG architecture

\* integrations

\* security requirements

\* testing strategy

\* deployment strategy

\* development phases

\* Antigravity development rules

\* acceptance criteria



The purpose is to prevent:



\* architecture drift

\* uncontrolled feature expansion

\* duplicate implementations

\* insecure AI behavior

\* cross-tenant data access

\* unnecessary technology changes

\* AI coding tools redesigning the project without approval



\---



\# 2. Document Authority



AgentDesk documentation follows this authority hierarchy:



1\. \*\*SRS\*\* — functional and non-functional requirements

2\. \*\*SDD\*\* — approved architecture and system design

3\. \*\*Master Development Blueprint\*\*

4\. Individual technical design documents

5\. Source code



If a conflict is discovered:



1\. Stop the affected implementation.

2\. Identify the conflicting requirements.

3\. Determine the approved resolution.

4\. Update the relevant documentation.

5\. Only then modify the implementation.



No AI coding tool may silently change an approved architectural decision.



\---



\# 3. Project Vision



AgentDesk is a multi-tenant web platform that allows small businesses to configure AI agents that can:



\* answer customer questions

\* use a shared business knowledge base

\* communicate through Web Chat and WhatsApp

\* qualify leads

\* collect customer information

\* schedule appointments

\* reschedule appointments

\* cancel appointments

\* provide a browser-based voice conversation

\* support Urdu and English

\* maintain conversation history

\* provide leads and appointment information

\* provide business analytics



The central concept is the \*\*Business Brain\*\*.



The Business Brain combines:



```text

Business Profile

\+

Agent Configuration

\+

Knowledge Base

\+

Conversation Context

\+

Relevant Conversation History

\+

RAG Context

\+

Allowed Tools

\+

Language Context

```



All enabled agents use the same business context while remaining separated by their responsibilities and permissions.



\---



\# 4. Approved Project Scope



\## 4.1 Authentication



AgentDesk must support:



\* email/password registration

\* email/password login

\* Google sign-in

\* session management

\* logout

\* protected dashboard routes



\---



\## 4.2 Business Onboarding



The business owner must be able to configure:



\* business name

\* business vertical

\* business hours

\* business contacts

\* WhatsApp information

\* Google Calendar

\* AI agent settings



\---



\## 4.3 Knowledge Base



The system must support:



\* FAQ creation

\* FAQ editing

\* FAQ deletion

\* PDF uploads

\* DOCX uploads

\* maximum file size of 5 MB

\* text extraction

\* text cleaning

\* text chunking

\* embeddings

\* vector storage

\* semantic retrieval



Knowledge must always remain tenant-scoped.



\---



\## 4.4 AI Agents



The approved FYP agents are:



1\. Chat / FAQ Agent

2\. Lead Generation Agent

3\. Voice Agent



Appointment booking is provided as a shared business capability/tool used by the appropriate agents.



\---



\## 4.5 Voice Agent



The FYP voice implementation uses a browser-based simulator.



Flow:



```text

Browser Microphone

&#x20;       ↓

WebSocket

&#x20;       ↓

Speech-to-Text

&#x20;       ↓

AI Orchestrator

&#x20;       ↓

LLM / RAG / Tools

&#x20;       ↓

Text-to-Speech

&#x20;       ↓

Browser Audio

```



Live telephone/telephony deployment is outside the FYP implementation scope.



The architecture should remain extensible for future telephony.



\---



\## 4.6 Chat Agent



The Chat Agent must support:



\* Web Chat

\* WhatsApp

\* FAQ answering

\* RAG

\* Urdu

\* English

\* conversation history

\* business-context-aware responses



\---



\## 4.7 Lead Generation Agent



The Lead Agent must support:



\* buying-intent detection

\* customer name collection

\* customer contact collection

\* customer requirement/need collection

\* lead classification

\* lead storage

\* owner notification



Lead classifications:



```text

Hot

Warm

Cold

```



These classifications are application-level labels and must not be presented as objectively guaranteed predictions.



\---



\## 4.8 Appointment Booking



The platform must support:



\* calendar availability

\* appointment creation

\* appointment rescheduling

\* appointment cancellation

\* local appointment records

\* Google Calendar event IDs



\---



\## 4.9 Dashboard



The owner dashboard must provide access to:



\* business overview

\* agent settings

\* knowledge base

\* conversations

\* conversation details

\* leads

\* appointments

\* analytics

\* settings



\---



\## 4.10 Language Support



The system must support:



\* Urdu

\* English

\* automatic language detection

\* configurable language priority



Urdu retrieval quality must be tested using representative Urdu and Urdu-English queries.



\---



\# 5. Explicitly Out of Scope



The following are not part of the FYP implementation:



\* billing system

\* payment processing

\* native Android application

\* native iOS application

\* full live telephony deployment

\* content/marketing agent

\* unrelated business automation features



The content/marketing agent may be considered for a future Phase 2.



\---



\# 6. Database Architecture Resolution



\## PostgreSQL + pgvector Is Approved



The SRS contains a subsection referring to Microsoft SQL Server 7.



This conflicts with the approved architecture because:



\* the SRS software interface specifies PostgreSQL + pgvector

\* the SRS requires vector search

\* the SDD explicitly specifies PostgreSQL + pgvector

\* the SDD data design uses PostgreSQL

\* the RAG architecture requires vector similarity search



Therefore:



> \*\*AgentDesk will use PostgreSQL + pgvector as the approved database architecture.\*\*



The Microsoft SQL Server 7 subsection is treated as an obsolete/template fragment and is \*\*not an implementation requirement\*\*.



This decision must not be silently changed.



\---



\# 7. High-Level System Architecture



```text

&#x20;                        CUSTOMERS

&#x20;                           │

&#x20;             ┌─────────────┼─────────────┐

&#x20;             │             │             │

&#x20;             ▼             ▼             ▼

&#x20;         Web Chat      WhatsApp     Voice Simulator

&#x20;             │             │             │

&#x20;             └─────────────┼─────────────┘

&#x20;                           │

&#x20;                           ▼

&#x20;                 ┌──────────────────┐

&#x20;                 │     Next.js      │

&#x20;                 │   PWA Frontend   │

&#x20;                 └────────┬─────────┘

&#x20;                          │

&#x20;                    HTTPS / WebSocket

&#x20;                          │

&#x20;                          ▼

&#x20;                 ┌──────────────────┐

&#x20;                 │     FastAPI      │

&#x20;                 │ Application API  │

&#x20;                 └────────┬─────────┘

&#x20;                          │

&#x20;            ┌─────────────┼──────────────┐

&#x20;            │             │              │

&#x20;            ▼             ▼              ▼

&#x20;         Auth/       Orchestrator    Integrations

&#x20;        Business          │

&#x20;                          │

&#x20;             ┌────────────┼────────────┐

&#x20;             │            │            │

&#x20;             ▼            ▼            ▼

&#x20;           Chat          Lead        Voice

&#x20;           Agent         Agent       Agent

&#x20;             │            │            │

&#x20;             └────────────┼────────────┘

&#x20;                          ▼

&#x20;                  ┌─────────────────┐

&#x20;                  │  Business Brain │

&#x20;                  └────────┬────────┘

&#x20;                           │

&#x20;           ┌───────────────┼────────────────┐

&#x20;           │               │                │

&#x20;           ▼               ▼                ▼

&#x20;      PostgreSQL         Redis         S3 Storage

&#x20;       + pgvector

```



\---



\# 8. Logical Architecture Layers



AgentDesk follows six logical layers.



\## Layer 1 — Presentation



Technology:



\* Next.js

\* TypeScript

\* Tailwind CSS

\* PWA



Responsibilities:



\* dashboard

\* authentication screens

\* onboarding

\* agent settings

\* knowledge base

\* chat preview

\* voice simulator

\* conversations

\* leads

\* appointments

\* analytics



The frontend must not contain core business rules.



\---



\## Layer 2 — Application Gateway



Technology:



\* FastAPI



Responsibilities:



\* HTTP APIs

\* WebSocket endpoints

\* request validation

\* authentication

\* authorization

\* rate limiting

\* error handling



\---



\## Layer 3 — Orchestration and Subsystems



Subsystems:



\* Authentication

\* Business

\* Knowledge

\* Orchestrator

\* Voice

\* Chat

\* Lead

\* Booking

\* Analytics



The orchestrator coordinates AI behavior but must not bypass domain services.



\---



\## Layer 4 — Domain/Data Access



Responsibilities:



\* domain models

\* repositories

\* database operations

\* transactions

\* tenant filtering

\* business rules



\---



\## Layer 5 — External Service Adapters



External services must be isolated behind provider interfaces.



Examples:



\* LLM

\* embeddings

\* STT

\* TTS

\* Google Calendar

\* WhatsApp

\* email



\---



\## Layer 6 — Data Stores



Approved stores:



\* PostgreSQL

\* pgvector

\* Redis

\* S3-compatible object storage



\---



\# 9. Approved Technology Stack



\## Frontend



```text

Next.js

TypeScript

Tailwind CSS

PWA

Playwright

```



\## Backend



```text

Python

FastAPI

Pydantic

SQLAlchemy 2

Alembic

```



\## Database



```text

PostgreSQL

pgvector

```



\## Cache / Background Processing



```text

Redis

Background Worker

```



Only one background-job framework should be selected during implementation.



Do not introduce multiple queue systems.



\## AI



```text

Custom Python AI Orchestrator

Provider abstraction

Tool/function calling

RAG

```



\## External Services



Initial provider direction:



```text

LLM       → Provider adapter

Embeddings → Local sentence-transformer adapter

STT       → Deepgram

TTS       → ElevenLabs

Calendar  → Google Calendar API

Messaging → WhatsApp Business Cloud API

Storage   → S3-compatible storage

```



Providers must remain replaceable.



Provider pricing, limits, quotas, and availability must be verified at implementation time.



No provider is assumed to be permanently free or unlimited.



\---



\# 10. Provider Abstraction



Business logic must not directly depend on a specific external provider.



Example:



```text

LLMProvider

&#x20;   └── GroqProvider



EmbeddingProvider

&#x20;   └── LocalEmbeddingProvider



STTProvider

&#x20;   └── DeepgramProvider



TTSProvider

&#x20;   └── ElevenLabsProvider



CalendarProvider

&#x20;   └── GoogleCalendarProvider



MessagingProvider

&#x20;   └── WhatsAppProvider

```



Correct:



```text

LeadService

&#x20;     ↓

Orchestrator

&#x20;     ↓

LLMProvider

&#x20;     ↓

Configured Provider

```



Incorrect:



```text

LeadService

&#x20;     ↓

Groq API directly

```



\---



\# 11. Multi-Tenant Architecture



AgentDesk is multi-tenant from day one.



The primary tenant is the `Business`.



Every business-owned resource must be associated with a business.



The backend must determine the current business from the authenticated user/session.



The frontend must never be trusted to choose an arbitrary tenant.



Correct flow:



```text

Authenticated User

&#x20;       ↓

Authorized Business

&#x20;       ↓

Tenant Validation

&#x20;       ↓

Repository

&#x20;       ↓

Database

```



Incorrect:



```text

Frontend business\_id

&#x20;       ↓

Database query

```



The backend must verify ownership/authorization before every business-owned operation.



\---



\# 12. Database Entities



\## Owner



```text

id

email

password\_hash

google\_sub

active

verified

created\_at

updated\_at

```



Passwords must be securely hashed and must never be stored as plaintext or recoverable passwords.



\---



\## Business



```text

id

owner\_id

name

vertical

hours

whatsapp\_number

contacts

google\_calendar\_id

google\_refresh\_token

created\_at

updated\_at

```



Google refresh tokens must be encrypted at rest.



\---



\## KnowledgeBaseEntry



```text

id

business\_id

question

answer

tags

language

embedding

embedding\_stale

updated\_at

```



\---



\## AgentConfig



```text

business\_id

voice\_enabled

chat\_enabled

lead\_enabled

voice\_id

tone

greeting

language\_priority

```



\---



\## Conversation



```text

id

business\_id

channel

language

started\_at

ended\_at

status

outcome

summary

```



Channels:



```text

voice

whatsapp

web

```



\---



\## Message



```text

id

conversation\_id

role

content

audio\_link

created\_at

```



\---



\## Lead



```text

id

business\_id

conversation\_id

name

contact

need

score

status

created\_at

```



\---



\## Appointment



```text

id

business\_id

conversation\_id

customer\_name

phone

scheduled\_at

service

google\_event\_id

status

created\_at

```



\---



\## AnalyticsSnapshot



```text

id

business\_id

date

calls

chats

leads

bookings

top\_intents

```



\---



\# 13. Database Rules



1\. PostgreSQL is the only approved relational database.

2\. pgvector is used for vector search.

3\. Alembic must manage schema migrations.

4\. Production schema changes require migrations.

5\. Business-owned data must be tenant-scoped.

6\. Foreign keys must be enforced.

7\. Appropriate indexes must be created.

8\. Timestamps must be consistent.

9\. Duplicate models must not be created.

10\. Sensitive integration tokens must be encrypted.

11\. Database credentials must never be committed.

12\. Database access must happen through approved backend layers.



\---



\# 14. AI Orchestrator



The AI Orchestrator is the central intelligence coordination layer.



It is responsible for:



1\. language detection

2\. intent detection

3\. context loading

4\. RAG retrieval

5\. agent routing

6\. tool selection

7\. response generation

8\. action handling

9\. conversation persistence



Flow:



```text

Incoming Request

&#x20;     ↓

Validate Request

&#x20;     ↓

Identify Business

&#x20;     ↓

Identify Language

&#x20;     ↓

Load Business Brain

&#x20;     ↓

Retrieve Relevant Knowledge

&#x20;     ↓

Identify Intent

&#x20;     ↓

Select Agent

&#x20;     ↓

Determine Allowed Tools

&#x20;     ↓

LLM Processing

&#x20;     ↓

Tool Call if Required

&#x20;     ↓

Backend Authorization

&#x20;     ↓

Tool Execution

&#x20;     ↓

Response Generation

&#x20;     ↓

Persist Conversation

&#x20;     ↓

Return Response

```



The LLM must never directly execute privileged operations.



\---



\# 15. Business Brain



The Business Brain is constructed for every relevant interaction.



It contains:



```text

Business Profile

\+

Agent Configuration

\+

Language

\+

Conversation Context

\+

Relevant RAG Results

\+

Allowed Tools

\+

Current User Request

```



The system must not send entire databases or entire documents to the LLM.



Only relevant information should be provided.



\---



\# 16. Agent Architecture



\## 16.1 Chat / FAQ Agent



Responsibilities:



\* answer customer questions

\* retrieve relevant business knowledge

\* use business profile

\* respect configured tone

\* support Urdu and English

\* maintain conversation context

\* avoid inventing business information



\---



\## 16.2 Lead Agent



Responsibilities:



\* identify buying intent

\* collect customer details

\* collect customer requirements

\* classify lead

\* store lead

\* notify business owner



\---



\## 16.3 Voice Agent



The FYP voice pipeline is:



```text

Browser Microphone

&#x20;      ↓

WebSocket

&#x20;      ↓

Speech-to-Text

&#x20;      ↓

AI Orchestrator

&#x20;      ↓

RAG / Tools / LLM

&#x20;      ↓

Text-to-Speech

&#x20;      ↓

Browser Audio

```



The browser voice simulator is the required FYP implementation.



\---



\# 17. Tool Architecture



AI agents may request tools.



Only the backend can execute tools.



Example tools:



```text

search\_knowledge

get\_business\_hours

create\_lead

update\_lead

get\_calendar\_availability

create\_appointment

reschedule\_appointment

cancel\_appointment

```



Execution flow:



```text

LLM requests tool

&#x20;      ↓

Validate tool name

&#x20;      ↓

Validate arguments

&#x20;      ↓

Verify tenant

&#x20;      ↓

Verify permissions

&#x20;      ↓

Execute backend service

&#x20;      ↓

Return safe result

```



Never allow:



\* arbitrary database queries

\* arbitrary shell commands

\* arbitrary tool names

\* arbitrary external HTTP requests

\* unrestricted URLs from LLM output



\---



\# 18. RAG Architecture



\## Ingestion



```text

PDF / DOCX

&#x20;    ↓

File Validation

&#x20;    ↓

Secure Storage

&#x20;    ↓

Text Extraction

&#x20;    ↓

Cleaning

&#x20;    ↓

Chunking

&#x20;    ↓

Embedding

&#x20;    ↓

PostgreSQL + pgvector

```



\## Retrieval



```text

Customer Query

&#x20;     ↓

Query Embedding

&#x20;     ↓

Tenant-Scoped Vector Search

&#x20;     ↓

Similarity Filtering

&#x20;     ↓

Relevant Chunks

&#x20;     ↓

Business Brain

&#x20;     ↓

LLM

```



Rules:



\* never retrieve another business's data

\* never send entire documents unnecessarily

\* maintain embedding metadata

\* mark changed embeddings as stale

\* re-embed changed content

\* keep embedding provider replaceable

\* test Urdu retrieval quality



\---



\# 19. File Upload Security



Supported formats:



```text

PDF

DOCX

```



Maximum size:



```text

5 MB

```



Validation:



\* file extension

\* MIME/content type

\* file signature where practical

\* file size

\* safe temporary storage

\* extraction safety

\* sanitized text



Uploaded files must never be executed.



Malware scanning should be used where supported by the deployment environment.



\---



\# 20. API Architecture



API groups:



```text

/api/v1/auth

/api/v1/businesses

/api/v1/agents

/api/v1/knowledge

/api/v1/conversations

/api/v1/leads

/api/v1/bookings

/api/v1/analytics

/api/v1/integrations

/api/v1/webhooks

```



API rules:



\* validate every request

\* use Pydantic schemas

\* enforce authentication

\* enforce authorization

\* enforce tenant isolation

\* use consistent errors

\* use correct HTTP status codes

\* rate-limit sensitive/public endpoints

\* never expose internal stack traces



\---



\# 21. Authentication and Authorization



Authentication methods:



\* email/password

\* Google OAuth



Password hashing:



```text

Argon2id

```



Session security must include:



\* expiration

\* secure cookies or a properly designed token system

\* HttpOnly cookies when applicable

\* Secure cookies in production

\* appropriate SameSite configuration

\* logout/revocation



Authorization must always happen server-side.



Potential roles:



```text

BUSINESS\_OWNER

BUSINESS\_STAFF

ADMIN

```



Staff/admin roles are optional extensions and must not be introduced without documenting their permissions.



\---



\# 22. AI Security



AI-specific security controls:



\* prompt injection defenses

\* system prompt isolation

\* tenant-scoped RAG

\* tool authorization

\* tool argument validation

\* output validation

\* sensitive-data filtering

\* safe error handling

\* no direct database access

\* no unrestricted external requests



Customer messages and uploaded documents must be treated as untrusted input.



\---



\# 23. WhatsApp Integration



Use the official WhatsApp Business Cloud API.



Requirements:



\* HTTPS webhook

\* webhook verification

\* signature validation

\* tenant mapping

\* message persistence

\* retry handling

\* idempotency

\* safe error handling



Duplicate webhook events must not create:



\* duplicate messages

\* duplicate leads

\* duplicate appointments



\---



\# 24. Google Calendar Integration



Use Google Calendar API with OAuth 2.0.



Required capabilities:



\* authorization

\* availability lookup

\* appointment creation

\* appointment update

\* appointment cancellation

\* local appointment record

\* Google event ID



Refresh tokens must be encrypted.



Calendar actions must happen through backend services.



\---



\# 25. Redis and Background Processing



Redis may support:



\* caching

\* temporary session state

\* active voice state

\* job queues

\* rate limiting



Background jobs may handle:



\* document processing

\* embedding generation

\* notifications

\* analytics snapshots

\* safe retryable external operations



Do not introduce multiple job frameworks.



\---



\# 26. Frontend Structure



```text

frontend/

├── app/

│   ├── (auth)/

│   ├── dashboard/

│   ├── onboarding/

│   ├── agents/

│   ├── knowledge/

│   ├── conversations/

│   ├── leads/

│   ├── appointments/

│   ├── analytics/

│   └── settings/

├── components/

├── features/

├── hooks/

├── lib/

├── services/

├── types/

├── public/

└── tests/

```



Frontend rules:



\* components focus on presentation

\* business logic belongs in services/hooks/backend

\* API communication uses a consistent client layer

\* avoid duplicated API code

\* validate forms

\* handle loading states

\* handle errors

\* handle empty states

\* maintain responsive UI

\* protect authenticated routes



\---



\# 27. Backend Structure



```text

backend/

├── app/

│   ├── main.py

│   ├── api/

│   │   ├── auth/

│   │   ├── businesses/

│   │   ├── agents/

│   │   ├── conversations/

│   │   ├── leads/

│   │   ├── bookings/

│   │   ├── knowledge/

│   │   ├── integrations/

│   │   └── webhooks/

│   ├── core/

│   ├── models/

│   ├── schemas/

│   ├── repositories/

│   ├── services/

│   ├── security/

│   ├── middleware/

│   ├── agents/

│   │   ├── chat/

│   │   ├── lead/

│   │   └── voice/

│   ├── orchestrator/

│   ├── tools/

│   ├── rag/

│   ├── providers/

│   │   ├── llm/

│   │   ├── embeddings/

│   │   ├── stt/

│   │   ├── tts/

│   │   ├── calendar/

│   │   └── messaging/

│   ├── language/

│   └── workers/

├── migrations/

├── tests/

├── Dockerfile

└── requirements.txt

```



Do not create a second competing AI/orchestrator implementation elsewhere.



\---



\# 28. Repository Structure



```text

AgentDesk/

├── frontend/

├── backend/

├── docs/

├── AGENTS.md

├── README.md

├── .env.example

├── .gitignore

└── docker-compose.yml

```



\---



\# 29. Required Documentation



```text

docs/

├── 00\_MASTER\_DEVELOPMENT\_BLUEPRINT.md

├── 01\_PROJECT\_SCOPE.md

├── 02\_ARCHITECTURE.md

├── 03\_TECH\_STACK.md

├── 04\_DATABASE\_DESIGN.md

├── 05\_API\_DESIGN.md

├── 06\_AI\_ORCHESTRATOR.md

├── 07\_AGENT\_DESIGN.md

├── 08\_RAG\_DESIGN.md

├── 09\_INTEGRATIONS.md

├── 10\_SECURITY.md

├── 11\_FOLDER\_STRUCTURE.md

├── 12\_DEVELOPMENT\_ROADMAP.md

├── 13\_TESTING\_STRATEGY.md

├── 14\_DEPLOYMENT.md

└── 15\_ANTIGRAVITY\_RULES.md

```



All documents must remain consistent with this blueprint.



\---



\# 30. Security Baseline



Minimum controls:



\* TLS in production

\* secure password hashing

\* authentication

\* authorization

\* tenant isolation

\* input validation

\* output validation

\* rate limiting

\* request-size limits

\* CORS configuration

\* security headers

\* safe error messages

\* audit logging where appropriate

\* secret management

\* encrypted integration tokens

\* webhook verification

\* idempotency

\* safe file uploads

\* dependency updates



Relevant OWASP API concerns include:



\* Broken Object Level Authorization

\* Broken Authentication

\* Broken Object Property Level Authorization

\* Unrestricted Resource Consumption

\* Broken Function Level Authorization

\* Sensitive Business Flow Abuse

\* SSRF

\* Security Misconfiguration

\* Improper API Inventory

\* Unsafe Consumption of APIs



\---



\# 31. Environment Variables and Secrets



Secrets must never be committed.



Use:



```text

.env

.env.example

```



`.env.example` contains variable names but no real credentials.



Expected categories:



```text

DATABASE\_URL

REDIS\_URL



SESSION\_SECRET / AUTH\_SECRET



LLM\_API\_KEY

DEEPGRAM\_API\_KEY

ELEVENLABS\_API\_KEY



GOOGLE\_CLIENT\_ID

GOOGLE\_CLIENT\_SECRET



WHATSAPP\_ACCESS\_TOKEN

WHATSAPP\_VERIFY\_TOKEN

WHATSAPP\_APP\_SECRET



EMAIL\_PROVIDER\_KEY



ENCRYPTION\_KEY

```



Exact variable names will be finalized during implementation.



\---



\# 32. Testing Strategy



\## Backend



Use:



```text

pytest

pytest-asyncio

```



Test:



\* authentication

\* authorization

\* tenant isolation

\* CRUD

\* RAG retrieval

\* orchestrator routing

\* tool authorization

\* lead capture

\* booking logic

\* webhook idempotency

\* request validation

\* security cases



\---



\## Frontend



Use:



```text

Playwright

```



Test:



\* sign-up

\* sign-in

\* onboarding

\* dashboard

\* agent configuration

\* knowledge base

\* chat

\* leads

\* appointments

\* important error states



\---



\## Integration Testing



External services should normally be mocked/faked during automated tests.



Live external integration tests must be explicitly configured.



\---



\# 33. Mandatory Tenant Isolation Tests



Automated tests must verify:



```text

Business A cannot read Business B data.



Business A cannot update Business B data.



Business A cannot delete Business B data.



Business A cannot retrieve Business B RAG chunks.



Business A cannot execute Business B integration actions.

```



Tenant isolation is a release-blocking security requirement.



\---



\# 34. Performance Targets



The SRS defines these engineering targets:



```text

Voice p95 latency          < 1.5 seconds

WhatsApp/Web Chat p95     < 5 seconds

Dashboard interaction     < 3 seconds

Concurrent demo sessions  30

```



These are targets, not unconditional guarantees.



Performance measurements must document:



\* environment

\* dataset

\* number of users

\* test duration

\* provider latency

\* network conditions



\---



\# 35. Reliability



External integrations should use:



\* timeouts

\* retries where safe

\* idempotency

\* controlled failures

\* logging

\* background processing where appropriate



Do not blindly retry non-idempotent operations.



For example:



```text

Appointment creation

```



must not accidentally create multiple appointments because of an automatic retry.



\---



\# 36. Data Retention



Approved retention:



```text

Business data:

Until owner deletion



Call audio:

Purged after 30 days



Transcripts:

Until owner deletion



Leads:

Until owner deletion

```



Deletion flows must handle related records consistently.



\---



\# 37. Approved UI Screens



```text

S-1   Landing

S-2   Sign-up / Sign-in

S-3   Onboarding

S-4   Dashboard

S-5   Agent Settings

S-6   Knowledge Base

S-7   Voice Simulator

S-8   Chat Preview

S-9   Conversation History

S-10  Conversation Detail

S-11  Lead Inbox

S-12  Appointments

S-13  Analytics

S-14  Settings

```



New major screens require scope approval.



\---



\# 38. Development Roadmap



\## Phase 0 — Documentation



Complete:



```text

00 Master Blueprint

01 Project Scope

02 Architecture

03 Tech Stack

04 Database Design

05 API Design

06 AI Orchestrator

07 Agent Design

08 RAG Design

09 Integrations

10 Security

11 Folder Structure

12 Development Roadmap

13 Testing Strategy

14 Deployment

15 Antigravity Rules

```



No major feature coding should begin before the baseline is reviewed.



\---



\## Phase 1 — Project Skeleton



Implement:



\* Git structure

\* Next.js

\* FastAPI

\* Docker Compose

\* PostgreSQL

\* pgvector

\* Redis

\* configuration

\* health endpoint

\* migration system

\* initial tests



Acceptance:



```text

Frontend starts

Backend starts

Database connects

Redis connects

Migration works

Tests execute

```



\---



\## Phase 2 — Authentication



Implement:



\* registration

\* login

\* logout

\* protected routes

\* Google sign-in

\* session management



Acceptance:



\* authentication works

\* protected routes are protected

\* passwords are secure

\* authorization tests pass



\---



\## Phase 3 — Business Onboarding



Implement:



\* business creation

\* profile

\* hours

\* contacts

\* integration configuration

\* agent configuration



\---



\## Phase 4 — Knowledge Base / RAG



Implement:



\* FAQ CRUD

\* PDF/DOCX upload

\* extraction

\* cleaning

\* chunking

\* embeddings

\* pgvector search

\* retrieval



\---



\## Phase 5 — AI Orchestrator



Implement:



\* language detection

\* intent routing

\* Business Brain

\* RAG integration

\* provider interfaces

\* tool interfaces

\* safe tool execution

\* response generation



\---



\## Phase 6 — Web Chat



Implement:



\* chat widget

\* conversation creation

\* message persistence

\* orchestrator integration

\* chat preview



\---



\## Phase 7 — Lead Agent



Implement:



\* intent detection

\* customer detail collection

\* lead scoring/classification

\* lead persistence

\* owner notification



\---



\## Phase 8 — Google Calendar



Implement:



\* OAuth

\* availability

\* appointment creation

\* rescheduling

\* cancellation

\* local appointment mirror



\---



\## Phase 9 — WhatsApp



Implement:



\* webhook

\* verification

\* signature validation

\* inbound messages

\* outbound responses

\* conversation persistence

\* idempotency



\---



\## Phase 10 — Voice



Implement:



\* microphone

\* WebSocket

\* STT

\* orchestrator

\* TTS

\* browser playback



\---



\## Phase 11 — Dashboard



Implement:



\* overview

\* conversations

\* leads

\* appointments

\* configuration

\* analytics



\---



\## Phase 12 — Analytics



Implement:



\* analytics snapshots

\* metrics

\* top intents

\* dashboard visualizations



\---



\## Phase 13 — Security Hardening



Test:



\* tenant isolation

\* authentication

\* authorization

\* rate limiting

\* file upload

\* webhook security

\* prompt injection

\* tool authorization

\* secrets

\* dependencies



\---



\## Phase 14 — Testing and Deployment



Complete:



\* backend tests

\* frontend tests

\* integration tests

\* performance checks

\* Docker build

\* deployment

\* environment configuration

\* monitoring/logging

\* final FYP demonstration flow



\---



\# 39. Deployment Architecture



Target:



```text

&#x20;                   Internet

&#x20;                      │

&#x20;            ┌─────────┴─────────┐

&#x20;            │                   │

&#x20;            ▼                   ▼

&#x20;         Vercel              Backend

&#x20;        Next.js           Railway/Render

&#x20;                               │

&#x20;            ┌──────────────────┼─────────────────┐

&#x20;            │                  │                 │

&#x20;            ▼                  ▼                 ▼

&#x20;         FastAPI            Worker          PostgreSQL

&#x20;                                              + pgvector

&#x20;            │

&#x20;            ▼

&#x20;          Redis



External Services:

\- S3-compatible storage

\- LLM provider

\- Deepgram

\- ElevenLabs

\- WhatsApp

\- Google Calendar

\- Email provider

```



Exact hosting providers may change if the architecture remains compatible.



\---



\# 40. Local Development



Docker Compose should provide:



```text

PostgreSQL + pgvector

Redis

```



Development flow:



```text

1\. Start infrastructure

2\. Run migrations

3\. Start backend

4\. Start frontend

5\. Run tests

6\. Check health endpoints

```



\---



\# 41. Git Workflow



Recommended:



```text

main

└── feature/\*

```



Rules:



\* main should remain stable

\* use small focused commits

\* use meaningful commit messages

\* never commit secrets

\* never commit unnecessary generated files

\* run relevant tests before merging

\* review Git diff



Examples:



```text

feat(auth): add email registration



feat(knowledge): add FAQ CRUD



feat(rag): add pgvector retrieval



fix(calendar): validate appointment ownership



test(security): add tenant isolation tests

```



\---



\# 42. Antigravity Role



Antigravity is an implementation assistant.



It is \*\*not\*\* the project architect.



Antigravity must:



1\. Read relevant documentation before coding.

2\. Follow the approved architecture.

3\. Make minimal changes.

4\. Avoid unrelated refactoring.

5\. Preserve existing functionality.

6\. Validate backend input.

7\. Enforce tenant isolation.

8\. Write tests for meaningful backend logic.

9\. Run relevant tests.

10\. Never expose secrets.

11\. Never hard-code API keys.

12\. Never create duplicate services.

13\. Never introduce unapproved frameworks.

14\. Never introduce unapproved providers.

15\. Never change the database architecture without approval.

16\. Never bypass repository/service boundaries.

17\. Never allow AI agents direct database access.

18\. Never trust frontend `business\_id`.

19\. Update documentation when an approved architectural change occurs.



\---



\# 43. Antigravity Prompt Rules



Never give a broad instruction such as:



```text

Build AgentDesk completely.

```



Use focused tasks.



Example:



```text

Implement Phase 2 authentication according to:



docs/02\_ARCHITECTURE.md

docs/04\_DATABASE\_DESIGN.md

docs/10\_SECURITY.md

docs/15\_ANTIGRAVITY\_RULES.md



Requirements:



\- implement only authentication

\- do not modify unrelated modules

\- preserve the approved architecture

\- use the existing project structure

\- add tests

\- run relevant tests

\- report files changed

\- report test results

```



Each AI coding task must have a defined boundary.



\---



\# 44. Definition of Done



A feature is complete only when:



\* implementation follows the approved architecture

\* input validation exists

\* authorization exists

\* tenant isolation is preserved

\* tests are added

\* relevant tests pass

\* errors are handled

\* secrets are protected

\* documentation is updated when necessary

\* unrelated files were not changed

\* Git diff has been reviewed



\---



\# 45. Release Gates



Before the final FYP demonstration:



\## Functional



```text

Authentication

Business onboarding

Knowledge Base

RAG

Web Chat

Lead Generation

Google Calendar

WhatsApp

Voice Simulator

Dashboard

Analytics

```



must work according to the approved scope.



\## Security



```text

Tenant isolation

Authentication

Authorization

Webhook verification

Tool authorization

File upload restrictions

Secret protection

```



must be verified.



\## Testing



```text

Backend tests

Frontend tests

Integration tests

Important error paths

Security tests

```



must pass.



\## Deployment



```text

Production build

Database migrations

Environment variables

External integrations

Logging/monitoring

```



must be verified.



\---



\# 46. FYP Demonstration Flow



Recommended demonstration:



```text

1\. Owner signs in.



2\. Owner completes business onboarding.



3\. Owner configures business information.



4\. Owner adds FAQs or uploads a business document.



5\. AgentDesk processes the document.



6\. Embeddings are stored in pgvector.



7\. Owner enables Chat, Lead, and Voice agents.



8\. Customer asks a business question.



9\. Agent retrieves relevant knowledge.



10\. Agent responds in Urdu or English.



11\. Customer demonstrates buying intent.



12\. Lead Agent collects:

&#x20;   - name

&#x20;   - contact

&#x20;   - need



13\. Lead is stored.



14\. Customer requests an appointment.



15\. Agent checks Google Calendar.



16\. Appointment is created.



17\. Owner views:

&#x20;   - conversation

&#x20;   - lead

&#x20;   - appointment



18\. Voice Simulator demonstrates the same Business Brain.

```



The demonstration should emphasize that multiple channels and agents share the same business context.



\---



\# 47. Future Extension Points



The architecture should allow future:



\* live telephony

\* content/marketing agent

\* additional messaging channels

\* additional LLM providers

\* additional embedding providers

\* additional STT providers

\* additional TTS providers

\* staff accounts

\* advanced analytics

\* billing



Future features must use the same:



\* provider abstraction

\* service boundaries

\* authorization

\* tenant isolation

\* Business Brain

\* tool architecture



\---



\# 48. Non-Negotiable Architecture Decisions



The following are locked unless explicitly approved:



```text

PostgreSQL + pgvector



FastAPI backend



Next.js frontend



Multi-tenant architecture



Shared Business Brain



Provider abstraction



Backend-controlled tools



Tenant-scoped RAG



Browser voice simulator for FYP



WhatsApp Business Cloud API



Google Calendar integration



Redis



S3-compatible file storage

```



Security rules that cannot be bypassed:



```text

No secrets in Git.



No plaintext passwords.



No frontend-only authorization.



No cross-tenant queries.



No unrestricted AI tools.



No direct AI database access.



No arbitrary external requests from LLM output.



No executable uploaded files.



No unverified WhatsApp webhook processing.

```



\---



\# 49. Final Development Principle



AgentDesk must be developed as a controlled software system, not as one large AI-generated application.



The implementation order is:



```text

Documentation

&#x20;     ↓

Architecture

&#x20;     ↓

Infrastructure

&#x20;     ↓

Authentication

&#x20;     ↓

Business

&#x20;     ↓

Knowledge / RAG

&#x20;     ↓

AI Orchestrator

&#x20;     ↓

Web Chat

&#x20;     ↓

Lead

&#x20;     ↓

Calendar

&#x20;     ↓

WhatsApp

&#x20;     ↓

Voice

&#x20;     ↓

Dashboard

&#x20;     ↓

Analytics

&#x20;     ↓

Security Hardening

&#x20;     ↓

Testing

&#x20;     ↓

Deployment

```



Do not jump directly to complex voice, WhatsApp, or multi-agent behavior before the foundational backend, database, authentication, and RAG layers are stable.



\---



\# 50. Blueprint Approval Rule



This document is the implementation baseline for AgentDesk.



Before development begins:



1\. Mukarram and Hadia review this blueprint.

2\. Any required changes are made to the documentation.

3\. The final blueprint is committed to Git.

4\. The remaining technical documents are created from this blueprint.

5\. `AGENTS.md` is finalized.

6\. Only after documentation approval does Antigravity begin implementation.



Any major architectural change after approval requires explicit review and documentation before implementation.



\*\*End of Master Development Blueprint\*\*



