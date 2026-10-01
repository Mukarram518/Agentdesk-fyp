\# AgentDesk — Folder Structure \& Code Organization



\## 1. Purpose



This document defines the official folder and file organization for the AgentDesk platform.



Its purpose is to ensure:



\* consistent project organization

\* clear separation of responsibilities

\* maintainable frontend and backend code

\* clean API/service/repository architecture

\* controlled AI agent and tool structure

\* clear RAG and provider boundaries

\* easy testing

\* safe collaboration between developers and AI coding tools

\* predictable file placement for Antigravity



This document is an implementation rule.



Antigravity must follow this structure unless an approved architectural change explicitly requires modification.



\---



\# 2. Project Root



The approved project root is:



```text

AgentDesk/

│

├── frontend/

├── backend/

├── docs/

│

├── AGENTS.md

├── README.md

├── .gitignore

├── .env.example

├── docker-compose.yml

└── LICENSE

```



\## Root Responsibilities



| File/Folder          | Responsibility                                     |

| -------------------- | -------------------------------------------------- |

| `frontend/`          | Next.js frontend application                       |

| `backend/`           | FastAPI backend application                        |

| `docs/`              | Project architecture and development documentation |

| `AGENTS.md`          | AI coding-agent rules                              |

| `README.md`          | Project overview and setup instructions            |

| `.gitignore`         | Git exclusions                                     |

| `.env.example`       | Example environment variable names                 |

| `docker-compose.yml` | Local development services                         |

| `LICENSE`            | Project license if required                        |



No application source code should be placed directly in the project root.



\---



\# 3. Frontend Structure



AgentDesk frontend uses:



\* Next.js

\* TypeScript

\* Tailwind CSS

\* PWA capabilities



Approved structure:



```text

frontend/

│

├── app/

│   ├── (auth)/

│   │   ├── login/

│   │   │   └── page.tsx

│   │   ├── register/

│   │   │   └── page.tsx

│   │   └── layout.tsx

│   │

│   ├── onboarding/

│   │   ├── page.tsx

│   │   └── layout.tsx

│   │

│   ├── dashboard/

│   │   ├── page.tsx

│   │   └── layout.tsx

│   │

│   ├── agents/

│   │   ├── page.tsx

│   │   └── \[agent]/

│   │       └── page.tsx

│   │

│   ├── knowledge/

│   │   ├── page.tsx

│   │   ├── files/

│   │   │   └── page.tsx

│   │   └── faq/

│   │       └── page.tsx

│   │

│   ├── conversations/

│   │   ├── page.tsx

│   │   └── \[conversationId]/

│   │       └── page.tsx

│   │

│   ├── leads/

│   │   ├── page.tsx

│   │   └── \[leadId]/

│   │       └── page.tsx

│   │

│   ├── appointments/

│   │   ├── page.tsx

│   │   └── \[appointmentId]/

│   │       └── page.tsx

│   │

│   ├── analytics/

│   │   └── page.tsx

│   │

│   ├── settings/

│   │   ├── page.tsx

│   │   ├── business/

│   │   │   └── page.tsx

│   │   └── integrations/

│   │       └── page.tsx

│   │

│   ├── voice/

│   │   └── page.tsx

│   │

│   ├── chat-preview/

│   │   └── page.tsx

│   │

│   ├── layout.tsx

│   ├── page.tsx

│   └── globals.css

│

├── components/

│   ├── ui/

│   ├── layout/

│   ├── forms/

│   ├── dashboard/

│   ├── agents/

│   ├── knowledge/

│   ├── conversations/

│   ├── leads/

│   ├── appointments/

│   ├── analytics/

│   ├── voice/

│   └── chat/

│

├── features/

│   ├── auth/

│   ├── onboarding/

│   ├── business/

│   ├── agents/

│   ├── knowledge/

│   ├── conversations/

│   ├── leads/

│   ├── appointments/

│   ├── analytics/

│   ├── voice/

│   └── chat/

│

├── hooks/

│

├── lib/

│   ├── api/

│   ├── auth/

│   ├── validation/

│   ├── websocket/

│   ├── constants/

│   └── utils/

│

├── services/

│   ├── auth.service.ts

│   ├── business.service.ts

│   ├── agent.service.ts

│   ├── knowledge.service.ts

│   ├── conversation.service.ts

│   ├── lead.service.ts

│   ├── appointment.service.ts

│   ├── analytics.service.ts

│   └── integration.service.ts

│

├── types/

│   ├── auth.ts

│   ├── business.ts

│   ├── agent.ts

│   ├── knowledge.ts

│   ├── conversation.ts

│   ├── lead.ts

│   ├── appointment.ts

│   └── analytics.ts

│

├── public/

│

├── tests/

│   ├── unit/

│   ├── integration/

│   └── e2e/

│

├── package.json

├── tsconfig.json

├── next.config.ts

├── tailwind.config.ts

├── postcss.config.mjs

├── eslint.config.mjs

├── Dockerfile

└── .env.example

```



\---



\# 4. Frontend App Router Responsibilities



The `app/` directory controls:



\* routes

\* layouts

\* loading states

\* error boundaries

\* page-level composition

\* route-specific UI



A route page should compose existing components and features.



A route page should not contain large amounts of business logic.



Example:



```text

app/leads/page.tsx

```



should primarily:



1\. load the leads feature

2\. request/display required data

3\. handle page-level states

4\. compose UI



Business rules should live elsewhere.



\---



\# 5. Frontend Components



The `components/` directory contains reusable UI components.



\## `components/ui/`



Generic reusable UI:



```text

Button

Input

Modal

Dialog

Dropdown

Table

Card

Badge

Tabs

Toast

Spinner

```



These components must not know anything about AgentDesk business logic.



\---



\## `components/dashboard/`



Dashboard-specific presentation components.



Examples:



```text

MetricCard

RecentConversations

LeadSummary

AppointmentSummary

AgentStatus

```



\---



\## Feature Components



Feature-specific UI belongs inside the relevant component directory.



Example:



```text

components/leads/

├── LeadTable.tsx

├── LeadCard.tsx

├── LeadDetails.tsx

├── LeadStatusBadge.tsx

└── LeadFilters.tsx

```



\---



\# 6. Frontend Features



The `features/` directory contains feature-level frontend logic.



Example:



```text

features/leads/

├── lead-form.tsx

├── lead-filters.ts

├── lead-query.ts

├── lead-validation.ts

└── lead-utils.ts

```



Use `features/` when code is specific to a particular application capability.



Do not put backend business logic here.



\---



\# 7. Frontend Services



The `services/` directory handles communication with backend APIs.



Example:



```text

services/lead.service.ts

```



Responsibilities:



\* API requests

\* request parameters

\* response handling

\* typed API interaction



Example conceptual structure:



```text

UI

&#x20;↓

Feature

&#x20;↓

Service

&#x20;↓

API

```



Services must not directly access the PostgreSQL database.



Services must not contain LLM orchestration.



Services must not contain backend authorization logic.



\---



\# 8. Frontend Hooks



`hooks/` contains reusable React hooks.



Examples:



```text

useAuth.ts

useBusiness.ts

useLeads.ts

useConversations.ts

useWebSocket.ts

useVoiceSession.ts

```



Hooks may call services.



Hooks must not directly implement backend business rules.



\---



\# 9. Frontend Lib



`lib/` contains reusable technical utilities.



Examples:



```text

lib/

├── api/

├── auth/

├── validation/

├── websocket/

├── constants/

└── utils/

```



Examples:



\* API client

\* authentication helpers

\* WebSocket helpers

\* common validation helpers

\* date formatting

\* constants



Business-specific workflows should not be hidden inside generic utility files.



\---



\# 10. Frontend Types



All shared frontend TypeScript types belong in:



```text

types/

```



Examples:



```text

types/lead.ts

types/appointment.ts

types/conversation.ts

```



Types should represent frontend-facing API/domain data.



Do not duplicate the same type in multiple unrelated files.



\---



\# 11. Backend Structure



AgentDesk backend uses:



\* Python

\* FastAPI

\* Pydantic

\* SQLAlchemy 2

\* Alembic

\* PostgreSQL

\* pgvector

\* Redis



Approved structure:



```text

backend/

│

├── app/

│   ├── main.py

│   │

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

│   │

│   ├── core/

│   │

│   ├── models/

│   │

│   ├── schemas/

│   │

│   ├── repositories/

│   │

│   ├── services/

│   │

│   ├── security/

│   │

│   ├── middleware/

│   │

│   ├── agents/

│   │   ├── chat/

│   │   ├── lead/

│   │   └── voice/

│   │

│   ├── orchestrator/

│   │

│   ├── tools/

│   │

│   ├── rag/

│   │

│   ├── providers/

│   │   ├── llm/

│   │   ├── embeddings/

│   │   ├── stt/

│   │   ├── tts/

│   │   ├── calendar/

│   │   └── messaging/

│   │

│   ├── language/

│   │

│   └── workers/

│

├── migrations/

│

├── tests/

│   ├── unit/

│   ├── integration/

│   ├── security/

│   ├── api/

│   ├── agents/

│   ├── rag/

│   └── e2e/

│

├── Dockerfile

├── requirements.txt

├── pytest.ini

└── .env.example

```



\---



\# 12. Backend API Layer



The `api/` directory contains FastAPI routes.



Example:



```text

api/

└── leads/

&#x20;   ├── router.py

&#x20;   └── dependencies.py

```



Responsibilities:



\* HTTP/WebSocket endpoints

\* request parsing

\* dependency injection

\* authentication dependency

\* calling services

\* returning API responses



API routes must not contain large business workflows.



Bad:



```text

router

&#x20;├── query database

&#x20;├── call LLM

&#x20;├── calculate lead score

&#x20;├── send email

&#x20;└── update database

```



Preferred:



```text

router

&#x20;  ↓

service

&#x20;  ↓

repository / orchestrator / provider

```



\---



\# 13. Backend Core



`core/` contains application-wide configuration and infrastructure primitives.



Examples:



```text

core/

├── config.py

├── database.py

├── redis.py

├── logging.py

├── exceptions.py

└── dependencies.py

```



Responsibilities:



\* environment configuration

\* database connection

\* Redis connection

\* logging configuration

\* common exceptions

\* application dependencies



Core must remain infrastructure-focused.



\---



\# 14. Database Models



`models/` contains SQLAlchemy database models.



Examples:



```text

models/

├── owner.py

├── business.py

├── agent\_config.py

├── knowledge\_base.py

├── conversation.py

├── message.py

├── lead.py

├── appointment.py

├── analytics\_snapshot.py

└── webhook\_event.py

```



Models represent database persistence.



Models should not contain:



\* API request validation

\* LLM prompts

\* external API calls

\* UI logic

\* complex business workflows



\---



\# 15. Pydantic Schemas



`schemas/` contains API/data validation schemas.



Example:



```text

schemas/

├── auth.py

├── business.py

├── agent.py

├── knowledge.py

├── conversation.py

├── lead.py

├── appointment.py

└── analytics.py

```



Schemas handle:



\* request validation

\* response serialization

\* structured data contracts



Do not use SQLAlchemy models as API request schemas.



\---



\# 16. Repositories



`repositories/` is the database access layer.



Example:



```text

repositories/

├── owner\_repository.py

├── business\_repository.py

├── knowledge\_repository.py

├── conversation\_repository.py

├── lead\_repository.py

├── appointment\_repository.py

└── analytics\_repository.py

```



Responsibilities:



\* database queries

\* persistence

\* retrieval

\* filtering

\* pagination

\* tenant-scoped database operations



Repositories must not:



\* call LLMs

\* call Deepgram

\* call ElevenLabs

\* call WhatsApp

\* contain HTTP route logic



\---



\# 17. Services



`services/` contains application/business workflows.



Example:



```text

services/

├── auth\_service.py

├── business\_service.py

├── agent\_service.py

├── conversation\_service.py

├── lead\_service.py

├── appointment\_service.py

├── knowledge\_service.py

└── analytics\_service.py

```



Services coordinate:



```text

API

&#x20;↓

Service

&#x20;↓

Repository

&#x20;↓

Database

```



or, where appropriate:



```text

API

&#x20;↓

Service

&#x20;↓

Provider

```



Services are responsible for application workflows, not raw infrastructure implementation.



\---



\# 18. Security Directory



`security/` contains authentication and authorization mechanisms.



Example:



```text

security/

├── password.py

├── sessions.py

├── authentication.py

├── authorization.py

├── tenant.py

├── oauth.py

└── permissions.py

```



Responsibilities:



\* password hashing

\* session/token validation

\* authentication

\* authorization

\* current-business resolution

\* tenant isolation

\* permission checks



Security logic must not be duplicated throughout API routes.



\---



\# 19. Middleware



`middleware/` contains cross-cutting HTTP/application middleware.



Possible examples:



```text

middleware/

├── request\_id.py

├── logging.py

├── rate\_limit.py

└── security\_headers.py

```



Middleware must remain generic.



Feature-specific business logic should not be placed here.



\---



\# 20. AI Agent Directory



The `agents/` directory contains agent-specific behavior.



Approved:



```text

agents/

├── chat/

├── lead/

└── voice/

```



Each agent may contain:



```text

agents/chat/

├── agent.py

├── prompts.py

├── schemas.py

└── policies.py

```



The exact files may vary based on implementation needs.



Agents must not directly access the database.



Agents must not directly access external providers.



Agents request capabilities through approved tools.



\---



\# 21. Orchestrator



The `orchestrator/` directory contains the central AI coordination layer.



Example:



```text

orchestrator/

├── orchestrator.py

├── context.py

├── routing.py

├── prompts.py

├── tool\_loop.py

├── output.py

└── policies.py

```



Responsibilities:



\* normalize input

\* language detection

\* intent detection

\* retrieve context

\* construct Business Brain

\* select agent

\* manage tool calls

\* validate tool requests

\* generate final response

\* enforce AI security policies



The orchestrator is the central coordination point.



Agents must not create independent competing orchestration systems.



\---



\# 22. Tools



The `tools/` directory contains controlled backend capabilities exposed to AI agents.



Example:



```text

tools/

├── knowledge\_tools.py

├── lead\_tools.py

├── booking\_tools.py

├── business\_tools.py

└── communication\_tools.py

```



A tool represents a controlled action.



Examples:



```text

search\_knowledge

create\_lead

check\_calendar\_availability

create\_appointment

reschedule\_appointment

cancel\_appointment

send\_owner\_alert

```



Tools must:



1\. validate arguments

2\. verify authorization

3\. verify tenant ownership

4\. execute controlled business logic

5\. return structured results



The LLM must never receive unrestricted database or API access.



\---



\# 23. RAG Directory



The `rag/` directory contains knowledge retrieval functionality.



Approved structure:



```text

rag/

├── ingestion/

│   ├── extractor.py

│   ├── chunker.py

│   └── pipeline.py

│

├── retrieval/

│   ├── embedder.py

│   ├── search.py

│   └── reranker.py

│

├── context.py

├── models.py

└── policies.py

```



Responsibilities:



\* document extraction

\* text cleaning

\* chunking

\* embedding generation

\* vector search

\* tenant filtering

\* context construction



RAG code must never retrieve data across businesses.



\---



\# 24. Provider Directory



External services must be isolated behind provider interfaces.



```text

providers/

├── llm/

│   ├── base.py

│   └── groq.py

│

├── embeddings/

│   ├── base.py

│   └── local.py

│

├── stt/

│   ├── base.py

│   └── deepgram.py

│

├── tts/

│   ├── base.py

│   └── elevenlabs.py

│

├── calendar/

│   ├── base.py

│   └── google.py

│

└── messaging/

&#x20;   ├── base.py

&#x20;   └── whatsapp.py

```



Application code should depend on provider interfaces rather than vendor-specific implementations.



Example:



```text

Orchestrator

&#x20;    ↓

LLMProvider

&#x20;    ↓

GroqProvider

```



not:



```text

Orchestrator

&#x20;    ↓

Groq SDK everywhere

```



This keeps providers replaceable.



\---



\# 25. Language Module



`language/` contains language-specific utilities.



Example:



```text

language/

├── detector.py

├── normalizer.py

└── constants.py

```



Responsibilities:



\* Urdu detection

\* English detection

\* mixed-language handling

\* language normalization



Do not place general AI orchestration inside this directory.



\---



\# 26. Background Workers



`workers/` contains asynchronous/background jobs.



Examples:



```text

workers/

├── knowledge\_jobs.py

├── analytics\_jobs.py

├── notification\_jobs.py

└── cleanup\_jobs.py

```



Possible jobs:



\* document processing

\* embedding generation

\* analytics snapshots

\* notifications

\* retention cleanup

\* external retry processing



Background jobs should be idempotent where possible.



\---



\# 27. Database Migrations



All database schema migrations belong in:



```text

backend/migrations/

```



Alembic manages migrations.



Developers and Antigravity must not manually modify production database schemas outside the migration process.



Every approved schema change should have an appropriate migration.



\---



\# 28. Backend Tests



Approved test structure:



```text

backend/tests/

├── unit/

├── integration/

├── security/

├── api/

├── agents/

├── rag/

└── e2e/

```



Examples:



```text

tests/unit/test\_lead\_scoring.py

tests/api/test\_auth.py

tests/security/test\_tenant\_isolation.py

tests/agents/test\_lead\_agent.py

tests/rag/test\_retrieval.py

```



Tests should mirror important application boundaries.



\---



\# 29. Frontend Tests



Frontend tests belong in:



```text

frontend/tests/

├── unit/

├── integration/

└── e2e/

```



Playwright should be used for important end-to-end user flows.



Examples:



```text

tests/e2e/auth.spec.ts

tests/e2e/onboarding.spec.ts

tests/e2e/lead-flow.spec.ts

tests/e2e/booking-flow.spec.ts

```



\---



\# 30. Documentation Structure



All project documentation belongs under:



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



These documents form the project development contract.



\---



\# 31. Environment Files



Environment variables must never be hardcoded.



Approved locations:



```text

.env

.env.local

.env.example

```



Environment files containing real secrets must never be committed.



`.env.example` contains variable names only.



Example:



```text

DATABASE\_URL=

REDIS\_URL=

LLM\_API\_KEY=

DEEPGRAM\_API\_KEY=

ELEVENLABS\_API\_KEY=

WHATSAPP\_ACCESS\_TOKEN=

GOOGLE\_CLIENT\_ID=

GOOGLE\_CLIENT\_SECRET=

```



Actual secret values belong in local/deployment secret configuration.



\---



\# 32. Configuration Rules



Application configuration belongs in backend:



```text

backend/app/core/config.py

```



Frontend configuration must use the appropriate Next.js environment mechanism.



Never scatter environment-variable reads throughout the entire codebase.



Preferred:



```text

Environment

&#x20;  ↓

Configuration

&#x20;  ↓

Application

```



\---



\# 33. Naming Conventions



\## Python



Use:



```text

snake\_case

```



Examples:



```text

lead\_service.py

knowledge\_repository.py

appointment\_tools.py

```



Classes use:



```text

PascalCase

```



Example:



```python

class LeadService:

&#x20;   ...

```



\---



\## TypeScript



Use:



```text

camelCase

```



for variables and functions.



React components use:



```text

PascalCase

```



Examples:



```text

LeadTable.tsx

ConversationCard.tsx

```



\---



\## API Routes



Use resource-oriented naming.



Example:



```text

/api/v1/leads

/api/v1/appointments

/api/v1/conversations

```



Avoid action-heavy URL structures unless an operation genuinely represents an action.



\---



\# 34. API / Service / Repository Separation



The following dependency direction is mandatory:



```text

API

&#x20;↓

Service

&#x20;↓

Repository

&#x20;↓

Database

```



For external services:



```text

Service / Orchestrator

&#x20;↓

Provider Interface

&#x20;↓

Provider Adapter

&#x20;↓

External API

```



For AI:



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



\---



\# 35. Model / Schema Separation



SQLAlchemy:



```text

models/

```



Pydantic:



```text

schemas/

```



They serve different purposes.



```text

Database representation

&#x20;       ↓

SQLAlchemy Model



API representation

&#x20;       ↓

Pydantic Schema

```



Do not merge these responsibilities simply to reduce file count.



\---



\# 36. Agent / Tool / Service Separation



The following is mandatory:



```text

Agent

&#x20;↓

Tool

&#x20;↓

Service

&#x20;↓

Repository / Provider

```



The agent decides what capability is needed.



The tool exposes that capability safely.



The service performs the business operation.



The repository/provider performs infrastructure work.



\---



\# 37. RAG / Agent Separation



RAG should remain independent from individual agents.



Correct:



```text

Agent

&#x20;↓

Orchestrator

&#x20;↓

RAG

&#x20;↓

Knowledge Repository

```



Incorrect:



```text

Lead Agent

&#x20;↓

Own private RAG implementation

```



All agents should use the shared Business Brain and shared knowledge system.



\---



\# 38. Provider Separation



Vendor SDK code belongs only inside provider adapters.



For example:



```text

providers/stt/deepgram.py

```



may contain Deepgram-specific implementation.



Other application modules should depend on:



```text

STTProvider

```



rather than directly importing the Deepgram SDK.



The same rule applies to:



\* LLM

\* embeddings

\* TTS

\* calendar

\* messaging



\---



\# 39. Shared Utilities



Before creating a new utility, check whether an existing utility already provides the functionality.



Generic utilities belong in:



```text

frontend/lib/utils/

```



or:



```text

backend/app/core/

```



depending on the application.



Do not create:



```text

utils2.py

helpers\_new.py

common\_final.py

misc.py

```



as a way of avoiding proper organization.



\---



\# 40. File Placement Decision Rules



When creating a new file, determine its responsibility first.



\### If it is a FastAPI route



Put it in:



```text

backend/app/api/

```



\### If it contains business workflow



Put it in:



```text

backend/app/services/

```



\### If it performs database queries



Put it in:



```text

backend/app/repositories/

```



\### If it represents a database table



Put it in:



```text

backend/app/models/

```



\### If it validates API input/output



Put it in:



```text

backend/app/schemas/

```



\### If it is an AI agent



Put it in:



```text

backend/app/agents/

```



\### If it exposes an AI capability



Put it in:



```text

backend/app/tools/

```



\### If it handles RAG



Put it in:



```text

backend/app/rag/

```



\### If it communicates with an external provider



Put it in:



```text

backend/app/providers/

```



\### If it handles authentication/security



Put it in:



```text

backend/app/security/

```



\### If it is a background job



Put it in:



```text

backend/app/workers/

```



\### If it is a frontend route



Put it in:



```text

frontend/app/

```



\### If it is reusable UI



Put it in:



```text

frontend/components/

```



\### If it is feature-specific frontend logic



Put it in:



```text

frontend/features/

```



\### If it calls backend APIs



Put it in:



```text

frontend/services/

```



\### If it is a reusable React hook



Put it in:



```text

frontend/hooks/

```



\### If it is a TypeScript type



Put it in:



```text

frontend/types/

```



\---



\# 41. Dependency Direction



Backend dependency direction:



```text

API

&#x20;↓

Application Services

&#x20;↓

Domain/Business Logic

&#x20;↓

Repositories / Provider Interfaces

&#x20;↓

Infrastructure

```



External provider implementations sit at the infrastructure boundary.



The direction must not become circular.



Avoid:



```text

Service → API

Repository → Service

Provider → API

Model → Service

```



\---



\# 42. Import Rules



Imports should respect architecture boundaries.



Examples of prohibited patterns:



```text

repository importing router

model importing API

agent importing database session directly

frontend component importing backend Python code

frontend component importing provider SDK

```



The application should use clear interfaces between layers.



\---



\# 43. Multi-Tenant File Placement



Tenant-sensitive logic must remain centralized.



Business resolution belongs in:



```text

security/tenant.py

```



Tenant-scoped repository methods should consistently receive the authorized business context.



Do not create a separate database access mechanism for individual agents.



Every tenant-sensitive feature must follow the same authorization model.



\---



\# 44. Conversation and AI Data



Conversation persistence belongs primarily to:



```text

models/

repositories/

services/

```



AI processing belongs to:



```text

orchestrator/

agents/

rag/

providers/

```



Do not mix database persistence code into prompts or agent classes.



\---



\# 45. Integration-Specific Files



External integration code belongs under:



```text

providers/

```



or:



```text

api/webhooks/

```



depending on responsibility.



Example:



```text

providers/calendar/google.py

```



handles Google Calendar API communication.



While:



```text

api/webhooks/whatsapp.py

```



handles incoming WhatsApp webhook requests.



Webhook validation and provider communication must remain separate responsibilities.



\---



\# 46. Prohibited Structures



The following patterns are prohibited unless explicitly approved:



```text

backend/utils\_everything/

backend/helpers/

backend/misc/

backend/common\_all/

```



Do not create giant files such as:



```text

app.py

services.py

utils.py

agents.py

models.py

```



containing unrelated functionality.



Do not create duplicate implementations:



```text

lead\_service.py

lead\_service\_v2.py

lead\_service\_new.py

lead\_service\_final.py

```



Do not place secrets in source files.



Do not place database queries inside frontend code.



Do not place external SDK calls directly inside React components.



Do not create separate private RAG systems for each agent.



Do not create multiple orchestrators without approval.



\---



\# 47. Avoid Premature Abstraction



The structure must be modular, but unnecessary abstraction is also prohibited.



Do not create:



```text

FactoryFactory

ManagerManager

ServiceService

AbstractSomethingProvider

```



without a real architectural need.



Use abstractions where they provide:



\* provider replacement

\* security boundary

\* testability

\* clear responsibility

\* reusable domain behavior



\---



\# 48. Antigravity File-Creation Rules



Before creating a new file, Antigravity must:



1\. read `AGENTS.md`

2\. inspect the relevant architecture documentation

3\. determine whether an existing file already handles the responsibility

4\. identify the correct layer

5\. create the file in the approved directory

6\. avoid unnecessary new folders

7\. avoid duplicate functionality

8\. update tests where necessary



Antigravity must not create a new architectural layer merely because it is convenient.



\---



\# 49. Antigravity Existing-Code Rule



Before modifying code, Antigravity must inspect:



\* related files

\* existing services

\* existing repositories

\* existing schemas

\* existing providers

\* existing tests



It must extend existing functionality when appropriate rather than creating duplicate implementations.



\---



\# 50. Antigravity Documentation Rule



If implementation reveals a genuine conflict with the approved architecture:



1\. stop before making an architectural change

2\. identify the conflict

3\. explain the proposed change

4\. request approval

5\. update the appropriate documentation after approval



Do not silently redesign the system.



\---



\# 51. Exact High-Level Architecture



The final code organization follows:



```text

AgentDesk

│

├── Frontend

│   │

│   ├── Routes

│   ├── Components

│   ├── Features

│   ├── Hooks

│   ├── Services

│   ├── Lib

│   └── Types

│

├── Backend

│   │

│   ├── API

│   ├── Core

│   ├── Security

│   ├── Services

│   ├── Repositories

│   ├── Models

│   ├── Schemas

│   │

│   ├── AI

│   │   ├── Orchestrator

│   │   ├── Agents

│   │   ├── Tools

│   │   └── RAG

│   │

│   ├── Providers

│   ├── Language

│   ├── Workers

│   └── Middleware

│

├── Database

│   └── PostgreSQL + pgvector

│

├── Cache

│   └── Redis

│

├── External Services

│   ├── LLM

│   ├── Embeddings

│   ├── Deepgram

│   ├── ElevenLabs

│   ├── WhatsApp

│   └── Google Calendar

│

└── Documentation

```



\---



\# 52. Complete Backend Dependency Flow



```text

&#x20;                   ┌─────────────────────┐

&#x20;                   │      FastAPI API    │

&#x20;                   └──────────┬──────────┘

&#x20;                              │

&#x20;                              ▼

&#x20;                   ┌─────────────────────┐

&#x20;                   │ Application Services│

&#x20;                   └───────┬─────┬───────┘

&#x20;                           │     │

&#x20;                ┌──────────┘     └──────────┐

&#x20;                ▼                           ▼

&#x20;       ┌─────────────────┐        ┌──────────────────┐

&#x20;       │  Repositories   │        │ Provider Adapter │

&#x20;       └────────┬────────┘        └────────┬─────────┘

&#x20;                │                          │

&#x20;                ▼                          ▼

&#x20;       PostgreSQL/pgvector           External APIs

```



AI flow:



```text

User Message

&#x20;    │

&#x20;    ▼

FastAPI

&#x20;    │

&#x20;    ▼

Orchestrator

&#x20;    │

&#x20;    ├── Language Detection

&#x20;    ├── Intent Detection

&#x20;    ├── Business Context

&#x20;    ├── Conversation History

&#x20;    ├── RAG

&#x20;    │

&#x20;    ▼

Agent

&#x20;    │

&#x20;    ▼

Tool Request

&#x20;    │

&#x20;    ▼

Authorization

&#x20;    │

&#x20;    ▼

Service

&#x20;    │

&#x20;    ├── Repository

&#x20;    └── Provider

&#x20;    │

&#x20;    ▼

Tool Result

&#x20;    │

&#x20;    ▼

Orchestrator

&#x20;    │

&#x20;    ▼

Response

```



\---



\# 53. Complete Frontend Dependency Flow



```text

Next.js Route

&#x20;     │

&#x20;     ▼

Feature

&#x20;     │

&#x20;     ▼

Hook

&#x20;     │

&#x20;     ▼

Service

&#x20;     │

&#x20;     ▼

API Client

&#x20;     │

&#x20;     ▼

FastAPI Backend

```



UI components should remain presentation-focused.



\---



\# 54. Documentation Authority



When deciding where code belongs, documentation should be consulted in this order:



```text

00\_MASTER\_DEVELOPMENT\_BLUEPRINT.md

&#x20;       ↓

02\_ARCHITECTURE.md

&#x20;       ↓

03\_TECH\_STACK.md

&#x20;       ↓

04\_DATABASE\_DESIGN.md

&#x20;       ↓

05\_API\_DESIGN.md

&#x20;       ↓

06\_AI\_ORCHESTRATOR.md

&#x20;       ↓

07\_AGENT\_DESIGN.md

&#x20;       ↓

08\_RAG\_DESIGN.md

&#x20;       ↓

09\_INTEGRATIONS.md

&#x20;       ↓

10\_SECURITY.md

&#x20;       ↓

11\_FOLDER\_STRUCTURE.md

```



If documents conflict, do not silently choose a new architecture.



The conflict must be identified and resolved explicitly.



\---



\# 55. Definition of Done



The folder structure is considered correctly implemented when:



\* frontend and backend are separated

\* routes are separated from business logic

\* services are separated from repositories

\* models are separated from API schemas

\* agents are separated from tools

\* orchestrator is centralized

\* RAG is shared and tenant-aware

\* external providers are isolated

\* security logic has a dedicated boundary

\* background jobs have a dedicated location

\* tests have clear locations

\* migrations are separated

\* environment configuration is separated

\* documentation is centralized

\* no duplicate architectural layers exist

\* no secrets are committed

\* imports respect dependency direction

\* tenant isolation is preserved



\---



\# 56. Non-Negotiable Rules



The following rules are mandatory:



1\. PostgreSQL + pgvector remains the approved database architecture.

2\. FastAPI remains the backend API framework.

3\. Next.js remains the frontend framework.

4\. API, service, repository, model, and schema responsibilities remain separated.

5\. The orchestrator remains the central AI coordination layer.

6\. Agents do not directly access databases.

7\. Agents do not directly access external APIs.

8\. Tools are the controlled bridge between AI decisions and backend capabilities.

9\. RAG remains shared and tenant-scoped.

10\. External providers remain behind provider interfaces.

11\. Tenant isolation must never be bypassed.

12\. Secrets must never be committed.

13\. Duplicate services or duplicate orchestrators must not be created.

14\. Architectural changes require approval.

15\. Tests must accompany meaningful implementation changes.

16\. Existing functionality must not be unnecessarily broken or rewritten.



\---



\# 57. Final Folder Architecture



AgentDesk follows a modular architecture organized around responsibility rather than file type alone.



The core principle is:



```text

Presentation

&#x20;   ↓

API

&#x20;   ↓

Application Services

&#x20;   ↓

Domain Capabilities

&#x20;   ↓

Repositories / Provider Interfaces

&#x20;   ↓

Infrastructure

```



AI follows:



```text

Input

&#x20;↓

Orchestrator

&#x20;↓

Agent

&#x20;↓

Tool

&#x20;↓

Service / Provider

&#x20;↓

Result

```



Knowledge follows:



```text

Document

&#x20;↓

Ingestion

&#x20;↓

Chunking

&#x20;↓

Embedding

&#x20;↓

pgvector

&#x20;↓

Tenant-Scoped Retrieval

&#x20;↓

Business Brain

```



This structure is the official implementation baseline for AgentDesk.



Antigravity must treat this document and the other approved architecture documents as the source of truth and must not redesign the project independently.



