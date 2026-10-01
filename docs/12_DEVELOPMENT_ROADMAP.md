\# AgentDesk — Development Roadmap



\## 1. Purpose



This document defines the official implementation roadmap for AgentDesk.



The purpose is to provide a controlled development sequence for the complete system.



AgentDesk must be developed incrementally.



The project must not be implemented as one large task.



Each phase must:



\* have a clear objective

\* depend only on completed foundations

\* produce testable functionality

\* preserve existing functionality

\* pass its required validation

\* be committed to Git

\* be completed before dependent phases begin



Antigravity must use this document as the implementation sequence.



\---



\# 2. Development Philosophy



AgentDesk follows:



```text

Plan

&#x20;↓

Foundation

&#x20;↓

Core Backend

&#x20;↓

Business Configuration

&#x20;↓

Knowledge/RAG

&#x20;↓

AI Orchestration

&#x20;↓

Agents

&#x20;↓

Channels

&#x20;↓

Integrations

&#x20;↓

Dashboard

&#x20;↓

Security Hardening

&#x20;↓

Testing

&#x20;↓

Deployment

```



The project will be developed vertically where practical.



A feature should become usable end-to-end before unnecessary additional features are started.



\---



\# 3. Roadmap Principles



The following principles are mandatory:



1\. Do not build everything simultaneously.

2\. Do not start with voice.

3\. Do not start with WhatsApp.

4\. Build authentication before tenant-sensitive functionality.

5\. Build business onboarding before agent configuration.

6\. Build the knowledge system before RAG-dependent agents.

7\. Build the orchestrator before advanced agents.

8\. Build web chat before external messaging integration.

9\. Build booking logic before Google Calendar integration.

10\. Build the browser voice simulator before considering live telephony.

11\. Write tests throughout development.

12\. Keep every phase independently reviewable.

13\. Do not introduce unapproved technologies.

14\. Do not redesign architecture during implementation without approval.



\---



\# 4. Phase Overview



AgentDesk development is divided into the following phases:



```text

Phase 0  — Documentation \& Planning

Phase 1  — Repository \& Infrastructure Foundation

Phase 2  — Authentication

Phase 3  — Business Onboarding

Phase 4  — Agent Configuration

Phase 5  — Knowledge Base \& RAG

Phase 6  — AI Orchestrator

Phase 7  — Web Chat

Phase 8  — Lead Agent

Phase 9  — Appointment Booking

Phase 10 — Google Calendar Integration

Phase 11 — WhatsApp Integration

Phase 12 — Voice Agent \& Browser Simulator

Phase 13 — Conversation History

Phase 14 — Dashboard

Phase 15 — Analytics

Phase 16 — Security Hardening

Phase 17 — Testing \& Quality Assurance

Phase 18 — Deployment

Phase 19 — FYP Demo \& Final Stabilization

```



\---



\# 5. Phase Dependency Graph



The main dependency chain is:



```text

Documentation

&#x20;    ↓

Infrastructure

&#x20;    ↓

Authentication

&#x20;    ↓

Business

&#x20;    ↓

Agent Configuration

&#x20;    ↓

Knowledge/RAG

&#x20;    ↓

Orchestrator

&#x20;    ↓

Web Chat

&#x20;    ↓

Lead Agent

&#x20;    ↓

Booking

&#x20;    ↓

Google Calendar

&#x20;    ↓

WhatsApp

&#x20;    ↓

Voice

&#x20;    ↓

Dashboard

&#x20;    ↓

Analytics

&#x20;    ↓

Security Hardening

&#x20;    ↓

QA

&#x20;    ↓

Deployment

```



Some phases can be developed in parallel after their dependencies are complete.



However, parallel development must not introduce conflicting architecture.



\---



\# 6. Phase 0 — Documentation \& Planning



\## Objective



Establish the complete technical baseline before application implementation.



\## Required Documents



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



\## Completion Criteria



\* SRS reviewed

\* SDD reviewed

\* architecture approved

\* database architecture approved

\* API design approved

\* AI architecture approved

\* security baseline approved

\* folder structure approved

\* development roadmap approved



No major application coding should begin before this phase is complete.



\---



\# 7. Phase 1 — Repository \& Infrastructure Foundation



\## Objective



Create the clean application foundation.



\## Tasks



\### Repository



\* initialize Git repository

\* configure `.gitignore`

\* create README

\* create `AGENTS.md`

\* create documentation structure



\### Frontend



Initialize:



\* Next.js

\* TypeScript

\* Tailwind CSS

\* PWA foundation



\### Backend



Initialize:



\* Python

\* FastAPI

\* Pydantic

\* SQLAlchemy

\* Alembic



\### Infrastructure



Configure:



\* PostgreSQL

\* pgvector

\* Redis

\* Docker

\* Docker Compose



\### Basic Backend



Create:



```text

GET /health

```



\### Basic Frontend



Create:



```text

/

```



landing page and basic application shell.



\## Completion Criteria



\* frontend starts successfully

\* backend starts successfully

\* PostgreSQL connects

\* pgvector is available

\* Redis connects

\* Docker environment works

\* health endpoint works

\* frontend communicates with backend

\* no secrets committed



\---



\# 8. Phase 2 — Authentication



\## Objective



Implement secure owner authentication.



\## Features



\* registration

\* email/password login

\* logout

\* session management

\* authentication state

\* protected routes

\* password hashing

\* validation

\* account activation/verification where required

\* Google sign-in foundation



\## Security



Implement:



\* Argon2id password hashing

\* secure sessions/tokens

\* expiration

\* authentication dependencies

\* rate limiting

\* safe errors



\## Database



Implement:



```text

Owner

```



according to `04\_DATABASE\_DESIGN.md`.



\## Tests



Required:



\* registration success

\* duplicate email

\* invalid credentials

\* login

\* logout

\* expired session

\* protected endpoint

\* password security



\## Completion Criteria



A new owner can:



```text

Register

&#x20;↓

Login

&#x20;↓

Access protected dashboard

&#x20;↓

Logout

```



\---



\# 9. Phase 3 — Business Onboarding



\## Objective



Connect an authenticated owner to their business.



\## Features



\* business creation

\* business name

\* business vertical

\* operating hours

\* contact information

\* WhatsApp information

\* Google Calendar configuration placeholder

\* current-business resolution



\## Database



Implement:



```text

Business

```



with owner relationship.



\## Security



Every business query must enforce:



```text

authenticated owner

&#x20;       ↓

authorized business

```



Never trust a frontend-supplied `business\_id`.



\## Completion Criteria



Owner can:



1\. register

2\. login

3\. create business

4\. update business information

5\. access only authorized business data



\---



\# 10. Phase 4 — Agent Configuration



\## Objective



Allow the owner to configure available AI agents.



\## Features



\* enable/disable chat agent

\* enable/disable lead agent

\* enable/disable voice agent

\* voice ID

\* tone

\* greeting

\* language priority



\## Database



Implement:



```text

AgentConfig

```



\## Frontend



Create:



```text

/agents

```



and agent configuration UI.



\## Completion Criteria



Owner can configure agents and settings persist correctly.



Disabled agents must not execute.



\---



\# 11. Phase 5 — Knowledge Base \& RAG



\## Objective



Implement the shared Business Knowledge Base.



\## Features



\### FAQ



\* add FAQ

\* edit FAQ

\* delete FAQ

\* language

\* tags



\### Documents



Support:



\* PDF

\* DOCX



Maximum:



```text

5 MB

```



\## Processing Pipeline



```text

Upload

&#x20;↓

Validation

&#x20;↓

Storage

&#x20;↓

Text Extraction

&#x20;↓

Cleaning

&#x20;↓

Chunking

&#x20;↓

Embedding

&#x20;↓

pgvector

```



\## Retrieval



```text

User Query

&#x20;↓

Embedding

&#x20;↓

Tenant-Scoped Vector Search

&#x20;↓

Relevant Chunks

&#x20;↓

Business Brain

```



\## Requirements



\* tenant isolation

\* source metadata

\* chunk limits

\* embedding status

\* failure handling

\* duplicate handling where required



\## Urdu/English



Test retrieval for:



\* English

\* Urdu

\* mixed Urdu/English



Do not assume an embedding model is good for Urdu without testing.



\## Completion Criteria



Owner can upload a knowledge document and the system can retrieve relevant information for a query.



\---



\# 12. Phase 6 — AI Orchestrator



\## Objective



Implement the central AI coordination engine.



\## Responsibilities



```text

Input

&#x20;↓

Normalization

&#x20;↓

Language Detection

&#x20;↓

Intent Detection

&#x20;↓

Business Context

&#x20;↓

Conversation History

&#x20;↓

RAG

&#x20;↓

Agent Selection

&#x20;↓

Tool Selection

&#x20;↓

LLM

&#x20;↓

Validation

&#x20;↓

Response

```



\## Business Brain



The orchestrator combines:



\* business profile

\* agent configuration

\* language

\* knowledge

\* conversation context

\* allowed tools

\* system rules



\## Security



Implement:



\* prompt injection defenses

\* tool allowlists

\* argument validation

\* authorization checks

\* tenant-scoped context

\* output validation



\## Completion Criteria



A text input can pass through the orchestrator and produce a grounded response using business knowledge.



\---



\# 13. Phase 7 — Web Chat



\## Objective



Create the first complete customer-facing AI channel.



\## Features



\* web chat interface

\* message sending

\* conversation creation

\* message persistence

\* typing/loading state

\* Urdu/English handling

\* RAG-backed answers



\## Flow



```text

Customer

&#x20;↓

Web Widget

&#x20;↓

FastAPI

&#x20;↓

Orchestrator

&#x20;↓

Chat Agent

&#x20;↓

Response

&#x20;↓

Web Widget

```



\## Completion Criteria



A customer can have a complete web chat conversation with the configured business AI.



\---



\# 14. Phase 8 — Lead Agent



\## Objective



Detect and capture potential customers.



\## Lead Flow



```text

Conversation

&#x20;↓

Buying Intent

&#x20;↓

Collect Information

&#x20;↓

Name

&#x20;↓

Contact

&#x20;↓

Need

&#x20;↓

Lead Score

&#x20;↓

Lead Record

&#x20;↓

Owner Notification

```



\## Classification



Supported categories:



```text

HOT

WARM

COLD

```



The classification must follow documented rules rather than arbitrary model output.



\## Duplicate Protection



Avoid unnecessary duplicate leads from repeated messages or retries.



\## Completion Criteria



A qualifying conversation can produce a persisted lead containing:



\* name

\* contact

\* need

\* score

\* conversation reference

\* business reference

\* status



\---



\# 15. Phase 9 — Appointment Booking



\## Objective



Implement appointment management independently of Google Calendar.



\## Features



\* availability lookup

\* appointment creation

\* rescheduling

\* cancellation

\* confirmation

\* customer details

\* service details

\* timezone-aware datetime handling



\## Database



Implement:



```text

Appointment

```



\## Completion Criteria



The system can manage appointments using its own domain model.



This phase must work before depending on Google Calendar.



\---



\# 16. Phase 10 — Google Calendar Integration



\## Objective



Connect AgentDesk appointments to Google Calendar.



\## Features



\* Google OAuth

\* secure token storage

\* calendar discovery/configuration

\* availability

\* event creation

\* event update

\* event cancellation

\* synchronization



\## Flow



```text

Customer

&#x20;↓

Booking Tool

&#x20;↓

Appointment Service

&#x20;↓

Google Calendar Provider

&#x20;↓

Google Calendar

```



\## Security



\* encrypt refresh tokens

\* never expose tokens to frontend

\* validate OAuth state

\* use minimum required scopes

\* handle revoked access



\## Completion Criteria



A customer can request an appointment and the corresponding calendar event is created correctly.



\---



\# 17. Phase 11 — WhatsApp Integration



\## Objective



Connect AgentDesk to WhatsApp Business Cloud API.



\## Features



\* webhook verification

\* inbound message handling

\* outbound responses

\* conversation mapping

\* message persistence

\* lead detection

\* appointment workflow



\## Webhook Security



Implement:



\* signature verification

\* event validation

\* idempotency

\* replay protection where applicable



\## Flow



```text

WhatsApp

&#x20;↓

Webhook

&#x20;↓

Validation

&#x20;↓

Conversation Service

&#x20;↓

Orchestrator

&#x20;↓

Agent

&#x20;↓

WhatsApp Provider

&#x20;↓

Customer

```



\## Completion Criteria



A WhatsApp message can travel through the complete AgentDesk pipeline and receive an AI response.



\---



\# 18. Phase 12 — Voice Agent \& Browser Simulator



\## Objective



Implement the FYP voice demonstration.



\## FYP Scope



The primary FYP implementation is:



```text

Browser Microphone

&#x20;↓

WebSocket

&#x20;↓

Deepgram STT

&#x20;↓

Orchestrator

&#x20;↓

Tools / Agents

&#x20;↓

ElevenLabs TTS

&#x20;↓

Browser Audio

```



\## Features



\* microphone permission

\* WebSocket session

\* streaming speech recognition

\* language detection

\* AI response

\* text-to-speech

\* interruption handling

\* session lifecycle

\* transcript persistence



\## Performance



Target:



```text

Voice p95 < 1.5 seconds

```



where practical within the selected provider/network conditions.



\## Out of Scope



Live telephony is not required for the FYP demonstration.



The architecture should remain extensible for future telephony integration.



\## Completion Criteria



A user can speak to AgentDesk through the browser and receive a spoken response.



\---



\# 19. Phase 13 — Conversation History



\## Objective



Provide persistent conversation management.



\## Features



\* conversation list

\* channel filter

\* date filter

\* status

\* language

\* conversation details

\* messages

\* transcript

\* summary/outcome where available



\## Channels



Support:



```text

Voice

WhatsApp

Web

```



\## Completion Criteria



Owner can view previous conversations belonging only to their business.



\---



\# 20. Phase 14 — Dashboard



\## Objective



Build the primary owner dashboard.



\## Dashboard Information



Possible cards:



\* active agents

\* recent conversations

\* leads

\* appointments

\* channel activity

\* recent activity

\* knowledge status



\## Requirements



\* responsive

\* accessible

\* fast-loading

\* tenant-scoped



\## Completion Criteria



Owner has a useful centralized overview of business AI activity.



\---



\# 21. Phase 15 — Analytics



\## Objective



Provide business activity analytics.



\## Metrics



\* calls

\* chats

\* leads

\* bookings

\* top intents

\* channel distribution

\* daily activity



\## Snapshot



Implement:



```text

AnalyticsSnapshot

```



and appropriate background processing.



\## Completion Criteria



Analytics are generated and displayed correctly for the selected business.



\---



\# 22. Phase 16 — Security Hardening



\## Objective



Perform a dedicated security pass after the main functionality exists.



\## Review Areas



\### Authentication



\* password hashing

\* session security

\* expiration

\* brute-force protection



\### Authorization



\* tenant isolation

\* BOLA protection

\* function-level authorization

\* object ownership



\### API



\* input validation

\* rate limiting

\* request limits

\* safe errors

\* CORS

\* security headers



\### AI



\* prompt injection

\* tool authorization

\* data leakage

\* RAG isolation

\* output validation



\### Files



\* file size

\* MIME validation

\* file signature validation

\* safe extraction

\* temporary-file handling



\### WhatsApp



\* webhook verification

\* idempotency



\### Google



\* OAuth state

\* encrypted tokens

\* scope minimization



\### Secrets



\* `.env`

\* deployment secrets

\* Git history review



\## Completion Criteria



Security checklist from `10\_SECURITY.md` passes.



\---



\# 23. Phase 17 — Testing \& Quality Assurance



\## Objective



Perform complete application validation.



Testing strategy is defined in:



```text

docs/13\_TESTING\_STRATEGY.md

```



\## Required Categories



```text

Unit

Integration

API

Security

Agent

RAG

End-to-End

```



\## Critical End-to-End Flows



\### Flow 1 — Authentication



```text

Register

&#x20;↓

Login

&#x20;↓

Protected Dashboard

&#x20;↓

Logout

```



\### Flow 2 — Business Setup



```text

Login

&#x20;↓

Create Business

&#x20;↓

Configure Business

&#x20;↓

Configure Agent

```



\### Flow 3 — Knowledge



```text

Upload Document

&#x20;↓

Process

&#x20;↓

Embed

&#x20;↓

Retrieve

&#x20;↓

AI Answer

```



\### Flow 4 — Lead



```text

Customer

&#x20;↓

Chat

&#x20;↓

Buying Intent

&#x20;↓

Lead Information

&#x20;↓

Lead Creation

```



\### Flow 5 — Booking



```text

Customer

&#x20;↓

Ask Availability

&#x20;↓

Select Time

&#x20;↓

Confirm

&#x20;↓

Appointment

```



\### Flow 6 — Google Calendar



```text

OAuth

&#x20;↓

Availability

&#x20;↓

Booking

&#x20;↓

Calendar Event

```



\### Flow 7 — WhatsApp



```text

WhatsApp

&#x20;↓

Webhook

&#x20;↓

Orchestrator

&#x20;↓

Response

```



\### Flow 8 — Voice



```text

Microphone

&#x20;↓

STT

&#x20;↓

Orchestrator

&#x20;↓

TTS

&#x20;↓

Audio

```



\---



\# 24. Phase 18 — Deployment



\## Objective



Deploy the complete system in a reproducible way.



\## Target Topology



```text

&#x20;               Internet

&#x20;                  │

&#x20;         ┌────────┴────────┐

&#x20;         │                 │

&#x20;      Vercel            Backend

&#x20;     Frontend        Railway/Render

&#x20;                           │

&#x20;                ┌──────────┼──────────┐

&#x20;                │          │          │

&#x20;            PostgreSQL   Redis      Worker

&#x20;                │

&#x20;             pgvector

```



External services:



```text

LLM

Deepgram

ElevenLabs

WhatsApp

Google Calendar

S3 Storage

```



\## Requirements



\* production environment variables

\* HTTPS

\* database migrations

\* health checks

\* logging

\* monitoring

\* backup strategy

\* worker deployment

\* secure CORS

\* production configuration



\## Completion Criteria



The application can be deployed from a documented clean environment.



\---



\# 25. Phase 19 — FYP Demo \& Final Stabilization



\## Objective



Prepare a reliable end-to-end FYP demonstration.



\## Demo Business



Configure one realistic sample business.



Example:



```text

Business

&#x20;↓

Knowledge Base

&#x20;↓

AI Agents

&#x20;↓

Web Chat

&#x20;↓

Lead

&#x20;↓

Appointment

&#x20;↓

Google Calendar

&#x20;↓

WhatsApp

&#x20;↓

Voice Simulator

```



\## Demo Requirements



The demo should demonstrate:



1\. owner login

2\. business configuration

3\. knowledge upload

4\. agent configuration

5\. web chat

6\. RAG answer

7\. lead capture

8\. appointment booking

9\. Google Calendar event

10\. WhatsApp conversation

11\. browser voice interaction

12\. conversation history

13\. dashboard

14\. analytics



\---



\# 26. Recommended Implementation Order for Antigravity



Antigravity should implement tasks in this sequence:



```text

1\. Project foundation

2\. Database connection

3\. Base API

4\. Authentication

5\. Tenant/business context

6\. Business onboarding

7\. Agent configuration

8\. Knowledge base

9\. RAG

10\. Orchestrator

11\. Web chat

12\. Lead agent

13\. Booking

14\. Google Calendar

15\. WhatsApp

16\. Voice

17\. Conversation history

18\. Dashboard

19\. Analytics

20\. Security hardening

21\. Full testing

22\. Deployment

```



Do not skip foundational phases to build visually impressive features first.



\---



\# 27. Phase Completion Rule



Every phase must end with:



```text

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



Antigravity must not automatically continue into the next major phase without the current phase passing its completion criteria.



\---



\# 28. Git Workflow



Each meaningful phase should have a logical commit.



Examples:



```text

docs: define AgentDesk development roadmap

feat: initialize application foundation

feat: implement owner authentication

feat: implement business onboarding

feat: implement agent configuration

feat: implement knowledge base

feat: implement RAG retrieval

feat: implement AI orchestrator

feat: implement web chat

feat: implement lead agent

feat: implement appointment booking

feat: integrate Google Calendar

feat: integrate WhatsApp

feat: implement browser voice agent

feat: implement conversation history

feat: implement dashboard

feat: implement analytics

security: harden application security

test: complete end-to-end coverage

chore: prepare production deployment

```



Commits should represent coherent changes.



Avoid giant commits containing unrelated phases.



\---



\# 29. Branching



The main branch should remain stable.



Recommended workflow:



```text

main

&#x20;│

&#x20;├── feature/authentication

&#x20;├── feature/knowledge-base

&#x20;├── feature/orchestrator

&#x20;├── feature/web-chat

&#x20;└── feature/voice

```



For a small FYP team, simple feature branches may be used where practical.



Do not create unnecessary branch complexity.



\---



\# 30. Phase Validation Checklist



Before moving to the next phase:



```text

\[ ] Implementation complete

\[ ] Existing functionality still works

\[ ] Required tests pass

\[ ] Security requirements checked

\[ ] Tenant isolation checked

\[ ] No secrets committed

\[ ] No unnecessary dependencies added

\[ ] No duplicate services created

\[ ] Documentation still matches implementation

\[ ] Git commit created

\[ ] Git push successful

\[ ] Working tree clean

```



\---



\# 31. Architecture Change Rule



If implementation reveals that an architectural decision must change:



Antigravity must stop and report:



```text

1\. Current architecture

2\. Problem discovered

3\. Why current design is insufficient

4\. Proposed change

5\. Files affected

6\. Documentation affected

7\. Risks

8\. Alternative options

```



No major architectural change should be silently implemented.



\---



\# 32. Scope Protection



The following remain outside the core FYP implementation:



\* billing/payment system

\* native Android application

\* native iOS application

\* marketing/content agent

\* full production telephony system



These must not consume implementation time unless explicitly approved.



\---



\# 33. MVP Priority



If time becomes limited, implementation should focus on the core demonstrable chain:



```text

Authentication

&#x20;↓

Business Onboarding

&#x20;↓

Knowledge Base

&#x20;↓

RAG

&#x20;↓

Orchestrator

&#x20;↓

Web Chat

&#x20;↓

Lead Agent

&#x20;↓

Appointment Booking

&#x20;↓

Google Calendar

```



Then add:



```text

WhatsApp

&#x20;↓

Voice

&#x20;↓

Dashboard

&#x20;↓

Analytics

```



This keeps the core system functional even if optional features require additional time.



\---



\# 34. Performance Checkpoints



Performance should be measured throughout development rather than only before deployment.



Targets from the approved architecture:



| Area              | Target                                |

| ----------------- | ------------------------------------- |

| Voice             | p95 < 1.5 sec where practical         |

| Web/WhatsApp chat | p95 < 5 sec                           |

| Dashboard         | interactive < 3 sec                   |

| Demo concurrency  | approximately 30 active conversations |



Measurements should distinguish:



\* application processing time

\* database time

\* provider latency

\* network latency

\* total user-perceived latency



\---



\# 35. Cost-Control Strategy



The FYP should avoid unnecessary external API usage.



Rules:



\* use provider abstractions

\* avoid unnecessary LLM calls

\* keep prompts compact

\* limit RAG context

\* cache reusable information where appropriate

\* process documents asynchronously

\* avoid repeated embeddings

\* use local embeddings where suitable

\* use development/test substitutes where appropriate



No architecture decision should depend on an assumption of unlimited free API usage.



\---



\# 36. Team Development



The project has two primary student developers.



Responsibilities may be divided by module, but architecture must remain shared.



Possible division:



```text

Developer A

├── Backend/API

├── Database

├── Orchestrator

├── Integrations

└── AI



Developer B

├── Frontend

├── Dashboard

├── UI/UX

├── Chat Interface

└── Testing/Integration Support

```



The exact division can change.



The architecture cannot be duplicated between developers.



\---



\# 37. Documentation Synchronization



Implementation and documentation must remain synchronized.



If an approved implementation changes:



```text

Database

→ update 04\_DATABASE\_DESIGN.md



API

→ update 05\_API\_DESIGN.md



Orchestrator

→ update 06\_AI\_ORCHESTRATOR.md



Agents

→ update 07\_AGENT\_DESIGN.md



RAG

→ update 08\_RAG\_DESIGN.md



Integrations

→ update 09\_INTEGRATIONS.md



Security

→ update 10\_SECURITY.md



Folder structure

→ update 11\_FOLDER\_STRUCTURE.md

```



The master blueprint should also be updated when a major approved architectural decision changes.



\---



\# 38. Antigravity Master Development Rule



Antigravity must treat the roadmap as a controlled sequence.



A valid implementation prompt should identify:



```text

Phase

&#x20;↓

Feature

&#x20;↓

Relevant documentation

&#x20;↓

Allowed files/modules

&#x20;↓

Acceptance criteria

&#x20;↓

Tests

```



Example:



```text

Implement Phase 2 authentication according to:



docs/02\_ARCHITECTURE.md

docs/04\_DATABASE\_DESIGN.md

docs/05\_API\_DESIGN.md

docs/10\_SECURITY.md

docs/11\_FOLDER\_STRUCTURE.md

docs/12\_DEVELOPMENT\_ROADMAP.md



Implement only the authentication scope for Phase 2.



Do not implement later phases.



Do not redesign the architecture.



Do not introduce new frameworks or providers.



Run the relevant tests after implementation.

```



\---



\# 39. Antigravity Prohibited Behavior



Antigravity must not:



\* build the entire project in one task

\* skip phases

\* implement future functionality prematurely

\* redesign architecture without approval

\* introduce arbitrary frameworks

\* replace PostgreSQL with another database

\* create a second orchestrator

\* create separate RAG systems for each agent

\* bypass tenant authorization

\* hardcode secrets

\* directly expose provider credentials

\* place business logic inside frontend components

\* put database queries inside API routes

\* create duplicate services

\* ignore failing tests

\* delete working functionality to simplify implementation



\---



\# 40. Definition of Roadmap Completion



The roadmap is complete when:



\* all required phases have been implemented

\* core FYP functionality works end-to-end

\* security requirements pass

\* tenant isolation is verified

\* automated tests pass

\* external integrations are validated

\* deployment is reproducible

\* documentation matches implementation

\* FYP demo flow is stable



\---



\# 41. Final Development Principle



AgentDesk should be developed as a real software product, not as one large AI-generated code dump.



The correct approach is:



```text

Understand

&#x20;↓

Design

&#x20;↓

Implement

&#x20;↓

Test

&#x20;↓

Review

&#x20;↓

Commit

&#x20;↓

Continue

```



The documentation defines the architecture.



The roadmap defines the implementation order.



Tests define whether an implementation works.



Git preserves the development history.



Human approval controls architectural changes.



\---



\# 42. Final Roadmap



The official sequence is:



```text

PHASE 0

Documentation

&#x20;       ↓

PHASE 1

Infrastructure

&#x20;       ↓

PHASE 2

Authentication

&#x20;       ↓

PHASE 3

Business Onboarding

&#x20;       ↓

PHASE 4

Agent Configuration

&#x20;       ↓

PHASE 5

Knowledge + RAG

&#x20;       ↓

PHASE 6

AI Orchestrator

&#x20;       ↓

PHASE 7

Web Chat

&#x20;       ↓

PHASE 8

Lead Agent

&#x20;       ↓

PHASE 9

Appointment Booking

&#x20;       ↓

PHASE 10

Google Calendar

&#x20;       ↓

PHASE 11

WhatsApp

&#x20;       ↓

PHASE 12

Voice

&#x20;       ↓

PHASE 13

Conversation History

&#x20;       ↓

PHASE 14

Dashboard

&#x20;       ↓

PHASE 15

Analytics

&#x20;       ↓

PHASE 16

Security Hardening

&#x20;       ↓

PHASE 17

Testing / QA

&#x20;       ↓

PHASE 18

Deployment

&#x20;       ↓

PHASE 19

FYP Demo / Stabilization

```



This sequence is the approved development roadmap for AgentDesk.



No phase should be skipped merely to accelerate development.



The project should move forward only when the current phase satisfies its acceptance criteria.



