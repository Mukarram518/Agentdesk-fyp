\# AgentDesk — System Architecture



\*\*Document:\*\* 02\_ARCHITECTURE.md

\*\*Project:\*\* AgentDesk — A Multi-Agent AI Platform for Small Businesses

\*\*Status:\*\* Approved Architecture Baseline

\*\*Related Documents:\*\*



\* `00\_MASTER\_DEVELOPMENT\_BLUEPRINT.md`

\* `01\_PROJECT\_SCOPE.md`

\* SRS

\* SDD



\---



\## 1. Purpose



This document defines the implementation-level architecture of AgentDesk.



It translates the approved Software Design Document into concrete architectural boundaries that will guide:



\* Backend development

\* Frontend development

\* Database implementation

\* AI orchestration

\* Agent development

\* RAG implementation

\* External integrations

\* Security

\* Testing

\* Deployment



This document is a technical source of truth for development.



Any implementation must follow this architecture unless an architectural change is explicitly approved and documented.



\---



\# 2. Architectural Goals



AgentDesk architecture must provide:



1\. Multi-tenant business isolation

2\. Clear separation of frontend and backend responsibilities

3\. Secure API boundaries

4\. Centralized AI orchestration

5\. Shared business knowledge/RAG

6\. Modular AI agents

7\. Swappable external AI providers

8\. Reliable external integrations

9\. Background processing for long-running tasks

10\. Testable business logic

11\. Maintainable code structure

12\. FYP-friendly deployment

13\. Future scalability without unnecessary complexity



\---



\# 3. High-Level Architecture



AgentDesk uses a layered web architecture.



```text

┌─────────────────────────────────────────────────────────────┐

│                        USERS                                │

│                                                             │

│  Business Owner   Customer   WhatsApp User   Web Visitor    │

└───────────────┬─────────────────┬───────────────────────────┘

&#x20;               │                 │

&#x20;               ▼                 ▼

┌─────────────────────────────────────────────────────────────┐

│                    PRESENTATION LAYER                       │

│                                                             │

│                     Next.js Frontend                        │

│                                                             │

│ Dashboard │ Onboarding │ Agents │ KB │ Leads │ Appointments │

│ Chat Widget │ Voice Simulator │ Analytics │ Settings        │

└──────────────────────────┬──────────────────────────────────┘

&#x20;                          │ HTTPS / WebSocket

&#x20;                          ▼

┌─────────────────────────────────────────────────────────────┐

│                  APPLICATION GATEWAY                        │

│                                                             │

│                         FastAPI                             │

│                                                             │

│ Authentication │ Validation │ Routing │ Authorization       │

│ REST API │ WebSocket │ Webhooks                             │

└──────────────────────────┬──────────────────────────────────┘

&#x20;                          │

&#x20;                          ▼

┌─────────────────────────────────────────────────────────────┐

│             APPLICATION / ORCHESTRATION LAYER               │

│                                                             │

│                     AI Orchestrator                         │

│                                                             │

│ Authentication │ Business │ Knowledge │ Chat │ Lead         │

│ Voice │ Booking │ Analytics │ Integration Services          │

│                                                             │

│ Agents + Tools + Business Brain                             │

└───────────────┬──────────────────┬──────────────────────────┘

&#x20;               │                  │

&#x20;               ▼                  ▼

┌────────────────────────┐   ┌────────────────────────────────┐

│      DOMAIN/DATA       │   │      EXTERNAL ADAPTERS         │

│                        │   │                                │

│ Models                 │   │ LLM Provider                  │

│ Schemas                │   │ Embedding Provider             │

│ Repositories           │   │ Deepgram                       │

│ Business Rules         │   │ ElevenLabs                     │

│                        │   │ Google Calendar                │

│                        │   │ WhatsApp                       │

└───────────────┬────────┘   │ Email                          │

&#x20;               │            │ Object Storage                 │

&#x20;               ▼            └────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐

│                         DATA LAYER                          │

│                                                             │

│ PostgreSQL + pgvector │ Redis │ S3-compatible Storage       │

└─────────────────────────────────────────────────────────────┘

```



\---



\# 4. Six Architectural Layers



AgentDesk follows six logical layers.



\## Layer 1 — Presentation



Technology:



\* Next.js

\* TypeScript

\* Tailwind CSS

\* PWA support



Responsibilities:



\* Render UI

\* Collect user input

\* Display API responses

\* Manage client-side UI state

\* Handle authenticated navigation

\* Provide chat interface

\* Provide voice simulator

\* Display dashboards

\* Display errors and loading states



The frontend must not:



\* Access PostgreSQL directly

\* Access Redis directly

\* Execute business rules that belong to the backend

\* Call private AI provider APIs directly

\* Access secret API keys

\* Determine tenant authorization



\---



\# 5. Layer 2 — Application Gateway



Technology:



\* Python

\* FastAPI

\* Pydantic



Responsibilities:



\* HTTP routing

\* Request validation

\* Authentication

\* Authorization

\* WebSocket connections

\* Webhook endpoints

\* Rate limiting

\* Request/response handling

\* API error handling



Examples:



```text

POST /api/v1/auth/register

POST /api/v1/auth/login



GET  /api/v1/business

PUT  /api/v1/business



GET  /api/v1/knowledge

POST /api/v1/knowledge



POST /api/v1/chat/message



GET  /api/v1/leads

GET  /api/v1/appointments



POST /api/v1/integrations/google/connect



POST /api/v1/webhooks/whatsapp



WS /api/v1/voice

```



The gateway should remain relatively thin.



Business logic must not become concentrated inside route handlers.



\---



\# 6. Layer 3 — Application Services and Orchestration



This is the primary application layer.



Responsibilities include:



\* Business workflows

\* AI orchestration

\* Agent execution

\* RAG retrieval

\* Lead processing

\* Appointment operations

\* Conversation processing

\* Integration coordination

\* Analytics operations



Major components:



```text

Authentication Service

Business Service

Knowledge Service

Conversation Service

Orchestrator

Chat Agent

Lead Agent

Voice Agent

Booking Service

Analytics Service

Integration Services

```



\---



\# 7. Layer 4 — Domain and Data Access



This layer contains:



\* SQLAlchemy models

\* Pydantic schemas

\* Repository classes

\* Domain/business rules

\* Database-specific operations



Repositories are responsible for persistence operations.



Example:



```text

BusinessRepository

KnowledgeRepository

ConversationRepository

MessageRepository

LeadRepository

AppointmentRepository

AnalyticsRepository

```



Services should use repositories instead of embedding raw database queries throughout the application.



\---



\# 8. Layer 5 — External Service Adapters



External providers must not be deeply coupled to business logic.



AgentDesk uses provider interfaces.



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



This allows providers to be replaced without rewriting the entire application.



\---



\# 9. Layer 6 — Data Stores



Approved data stores:



\### PostgreSQL



Primary relational database.



Used for:



\* Users

\* Businesses

\* Agent configuration

\* Knowledge entries

\* Conversations

\* Messages

\* Leads

\* Appointments

\* Analytics

\* Integration metadata



\### pgvector



Used for:



\* Knowledge embeddings

\* Similarity search

\* Tenant-scoped RAG retrieval



\### Redis



Used for:



\* Cache

\* Temporary state

\* Rate limiting

\* Active voice/session state

\* Background job coordination where required



\### S3-Compatible Storage



Used for:



\* Uploaded PDF files

\* Uploaded DOCX files

\* Other approved file artifacts



\---



\# 10. Frontend Architecture



The frontend uses Next.js with feature-oriented organization.



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

│

├── components/

├── features/

├── hooks/

├── lib/

├── services/

├── types/

├── public/

└── tests/

```



\---



\# 11. Frontend Responsibilities



\## `app/`



Contains Next.js routes and page-level UI.



Pages should compose reusable components and feature modules.



\## `components/`



Contains reusable UI components.



Examples:



```text

Button

Modal

Table

Card

Form

Input

LoadingState

ErrorState

```



\## `features/`



Contains domain-specific frontend functionality.



Examples:



```text

features/auth/

features/business/

features/knowledge/

features/chat/

features/leads/

features/appointments/

features/analytics/

```



\## `services/`



Contains frontend API clients.



Example:



```text

authService

businessService

knowledgeService

conversationService

leadService

bookingService

```



Frontend services communicate with FastAPI.



\---



\# 12. Backend Architecture



Approved backend structure:



```text

backend/

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

│   ├── models/

│   ├── schemas/

│   ├── repositories/

│   ├── services/

│   ├── security/

│   ├── middleware/

│   │

│   ├── agents/

│   │   ├── chat/

│   │   ├── lead/

│   │   └── voice/

│   │

│   ├── orchestrator/

│   ├── tools/

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

│   └── workers/

│

├── migrations/

├── tests/

├── Dockerfile

└── requirements.txt

```



\---



\# 13. Backend Dependency Direction



Dependencies should flow inward.



```text

API

&#x20;↓

Services / Orchestrator

&#x20;↓

Domain / Repositories

&#x20;↓

Data Store



Services

&#x20;↓

Provider Interfaces

&#x20;↓

Provider Implementations

```



The following is prohibited:



```text

API → PostgreSQL directly

Agent → PostgreSQL directly

LLM → PostgreSQL directly

Frontend → PostgreSQL

Frontend → secret provider API

```



\---



\# 14. API Layer



API endpoints should follow a versioned structure.



```text

/api/v1/

```



Example:



```text

/api/v1/auth

/api/v1/business

/api/v1/agents

/api/v1/knowledge

/api/v1/conversations

/api/v1/leads

/api/v1/appointments

/api/v1/integrations

/api/v1/webhooks

```



Routes should:



1\. Authenticate request

2\. Validate request

3\. Identify current user

4\. Resolve current business

5\. Check authorization

6\. Call service

7\. Return validated response



\---



\# 15. Multi-Tenant Architecture



Multi-tenancy is required from day one.



The business is the primary tenant boundary.



```text

Owner

&#x20; │

&#x20; └── Business

&#x20;       │

&#x20;       ├── AgentConfig

&#x20;       ├── Knowledge

&#x20;       ├── Conversations

&#x20;       ├── Messages

&#x20;       ├── Leads

&#x20;       ├── Appointments

&#x20;       └── Analytics

```



Most business-owned records must contain:



```text

business\_id

```



\---



\# 16. Tenant Resolution



The backend must never trust a frontend-provided `business\_id` as proof of authorization.



Correct flow:



```text

Authenticated User

&#x20;      ↓

Current Owner

&#x20;      ↓

Authorized Business

&#x20;      ↓

Business-scoped Query

&#x20;      ↓

Data

```



Example:



```text

GET /api/v1/leads

```



The server determines:



```text

current\_user

&#x20;     ↓

current\_business

&#x20;     ↓

SELECT leads WHERE business\_id = current\_business.id

```



Not:



```text

SELECT leads WHERE business\_id = request.business\_id

```



without authorization validation.



\---



\# 17. Authentication Architecture



Authentication consists of:



```text

Registration

Login

Session/token handling

Google Sign-In

Password hashing

Authentication middleware

Authorization

Logout

```



Flow:



```text

User

&#x20;↓

Next.js Login

&#x20;↓

FastAPI Auth Endpoint

&#x20;↓

Validate Credentials

&#x20;↓

Verify Password

&#x20;↓

Create Session / Token

&#x20;↓

Authenticated Request

&#x20;↓

Authorization Middleware

&#x20;↓

Application Service

```



Passwords must never be stored in plaintext.



Password hashing should use a modern password hashing algorithm such as Argon2id.



\---



\# 18. Business Onboarding Architecture



After registration:



```text

Owner

&#x20;↓

Authentication

&#x20;↓

Create Business

&#x20;↓

Business Profile

&#x20;↓

Business Hours

&#x20;↓

Contact Information

&#x20;↓

Optional WhatsApp Configuration

&#x20;↓

Optional Google Calendar Connection

&#x20;↓

Agent Configuration

&#x20;↓

Dashboard

```



The onboarding workflow creates the initial business configuration.



\---



\# 19. Shared Business Brain



All agents operate using the same business context.



The Business Brain consists of:



```text

Business Profile

\+

Agent Configuration

\+

Knowledge Base

\+

Conversation Context

\+

Language Context

\+

Relevant RAG Results

\+

Allowed Tools

```



Conceptually:



```text

&#x20;                Business Profile

&#x20;                      │

&#x20;                      ▼

Agent Config → Business Brain ← Knowledge Base

&#x20;                      │

&#x20;                      ├── Conversation Context

&#x20;                      │

&#x20;                      ├── RAG Context

&#x20;                      │

&#x20;                      └── Allowed Tools

```



This prevents each agent from maintaining an isolated version of business knowledge.



\---



\# 20. AI Orchestrator



The orchestrator is the central intelligence routing component.



Responsibilities:



1\. Receive user input

2\. Identify language

3\. Understand intent

4\. Retrieve relevant knowledge

5\. Determine appropriate agent behavior

6\. Prepare business context

7\. Determine available tools

8\. Call the LLM

9\. Validate tool requests

10\. Execute approved tools

11\. Generate response

12\. Save conversation state



Basic flow:



```text

User Message

&#x20;    ↓

Language Detection

&#x20;    ↓

Intent Understanding

&#x20;    ↓

Tenant Context

&#x20;    ↓

RAG Retrieval

&#x20;    ↓

Agent Selection / Behavior

&#x20;    ↓

LLM

&#x20;    ↓

Tool Request?

&#x20;  /       \\

&#x20;Yes        No

&#x20; ↓          ↓

Validate    Response

&#x20; ↓

Execute Tool

&#x20; ↓

Result

&#x20; ↓

LLM / Response

&#x20; ↓

Save Conversation

```



\---



\# 21. Agent Architecture



Agents are specialized behaviors, not independent applications.



Approved agents:



```text

Chat / FAQ Agent

Lead Generation Agent

Voice Agent

```



The orchestrator controls agent execution.



Agents must not bypass authorization or directly access infrastructure.



\---



\# 22. Chat / FAQ Agent



Responsibilities:



\* Answer business questions

\* Use shared knowledge base

\* Support Urdu and English

\* Maintain conversation context

\* Detect lead opportunities

\* Invoke booking tools when appropriate



Example:



```text

Customer:

"Do you provide AC repair in Bahawalpur?"



&#x20;       ↓



Chat Agent

&#x20;       ↓

RAG Search

&#x20;       ↓

Business Knowledge

&#x20;       ↓

LLM

&#x20;       ↓

Answer

```



\---



\# 23. Lead Agent



Lead processing may occur as part of an ongoing conversation.



The agent should identify:



```text

Name

Contact

Need

Buying intent

```



Lead score categories:



```text

Hot

Warm

Cold

```



The scoring logic must be explicit and testable.



It must not depend solely on arbitrary LLM output.



Recommended approach:



```text

LLM extracts structured signals

&#x20;         ↓

Backend validates signals

&#x20;         ↓

Deterministic scoring rules

&#x20;         ↓

Lead record

```



\---



\# 24. Booking Architecture



Appointment operations are handled by the Booking Service.



Supported operations:



```text

Check availability

Create appointment

Reschedule appointment

Cancel appointment

```



Flow:



```text

Customer

&#x20;↓

Agent

&#x20;↓

Booking Tool

&#x20;↓

Booking Service

&#x20;↓

Google Calendar Provider

&#x20;↓

Google Calendar

```



The backend remains responsible for authorization and validation.



The LLM does not directly call Google Calendar.



\---



\# 25. Tool Architecture



AI agents interact with the system through controlled tools.



Example tools:



```text

search\_knowledge

capture\_lead

check\_calendar\_availability

create\_appointment

reschedule\_appointment

cancel\_appointment

send\_owner\_alert

```



Tool execution:



```text

LLM

&#x20;↓

Tool Request

&#x20;↓

Tool Schema Validation

&#x20;↓

Authorization

&#x20;↓

Business Validation

&#x20;↓

Tool Execution

&#x20;↓

Result

```



Every tool must define:



\* Name

\* Description

\* Input schema

\* Authorization requirements

\* Business rules

\* Output schema

\* Error behavior



\---



\# 26. RAG Architecture



Knowledge processing:



```text

PDF/DOCX/FAQ

&#x20;    ↓

Validation

&#x20;    ↓

Storage

&#x20;    ↓

Text Extraction

&#x20;    ↓

Cleaning

&#x20;    ↓

Chunking

&#x20;    ↓

Embedding

&#x20;    ↓

pgvector

```



Query flow:



```text

User Question

&#x20;    ↓

Query Embedding

&#x20;    ↓

Tenant-Scoped Vector Search

&#x20;    ↓

Top Relevant Chunks

&#x20;    ↓

Context Filtering

&#x20;    ↓

LLM

&#x20;    ↓

Answer

```



The entire document must not be inserted into every prompt.



\---



\# 27. RAG Tenant Isolation



RAG queries must always be scoped to the current business.



Conceptually:



```text

similarity search

\+

business\_id filter

```



The system must never retrieve another business's knowledge.



This is a critical security requirement.



\---



\# 28. Knowledge Upload Architecture



Maximum file size:



```text

5 MB

```



Supported initial formats:



```text

PDF

DOCX

```



Flow:



```text

Frontend

&#x20;↓

Upload API

&#x20;↓

File Size Validation

&#x20;↓

MIME/Extension Validation

&#x20;↓

Safe Temporary Storage

&#x20;↓

Object Storage

&#x20;↓

Background Processing

&#x20;↓

Text Extraction

&#x20;↓

Chunking

&#x20;↓

Embedding

&#x20;↓

PostgreSQL + pgvector

```



Uploaded files must never be executed.



\---



\# 29. Voice Architecture



The FYP uses a browser-based voice simulator.



It is not dependent on live telephony.



Flow:



```text

Browser Microphone

&#x20;      ↓

WebSocket

&#x20;      ↓

FastAPI Voice Endpoint

&#x20;      ↓

Voice Session

&#x20;      ↓

Deepgram STT

&#x20;      ↓

Text

&#x20;      ↓

AI Orchestrator

&#x20;      ↓

Tools / RAG / LLM

&#x20;      ↓

Response Text

&#x20;      ↓

ElevenLabs TTS

&#x20;      ↓

Audio

&#x20;      ↓

Browser

```



\---



\# 30. Voice Session Management



Redis may maintain temporary active voice-session state.



Example:



```text

voice\_session\_id

business\_id

conversation\_id

language

connection\_status

temporary\_context

```



Persistent conversation data remains in PostgreSQL.



Redis must not become the permanent source of truth for conversations.



\---



\# 31. WhatsApp Architecture



WhatsApp communication uses an HTTPS webhook.



Flow:



```text

WhatsApp

&#x20;   ↓

Webhook

&#x20;   ↓

Signature Verification

&#x20;   ↓

Webhook Event Validation

&#x20;   ↓

Idempotency Check

&#x20;   ↓

Conversation Resolution

&#x20;   ↓

AI Orchestrator

&#x20;   ↓

Response

&#x20;   ↓

WhatsApp Provider

&#x20;   ↓

Customer

```



Webhook processing must prevent duplicate message processing.



\---



\# 32. Web Chat Architecture



The web chat widget communicates with backend APIs.



```text

Customer

&#x20;↓

Web Chat Widget

&#x20;↓

FastAPI

&#x20;↓

Conversation Service

&#x20;↓

AI Orchestrator

&#x20;↓

RAG / Tools / LLM

&#x20;↓

Response

&#x20;↓

Widget

```



The widget must never contain provider secrets.



\---



\# 33. Google Calendar Architecture



OAuth flow:



```text

Owner

&#x20;↓

AgentDesk

&#x20;↓

Google OAuth

&#x20;↓

Google Authorization

&#x20;↓

Authorization Code

&#x20;↓

Backend

&#x20;↓

Encrypted Refresh Token

&#x20;↓

Google Calendar Provider

```



Calendar credentials must be encrypted at rest.



Calendar operations must occur through the provider adapter.



\---



\# 34. Conversation Architecture



Each conversation belongs to one business.



```text

Business

&#x20;└── Conversation

&#x20;      └── Messages

```



Conversation metadata includes:



```text

channel

language

status

started\_at

ended\_at

outcome

summary

```



Channels:



```text

Voice

WhatsApp

Web

```



\---



\# 35. Background Processing



Long-running tasks should not block normal HTTP requests.



Examples:



```text

Document processing

Embedding generation

Analytics snapshots

Email alerts

Retryable external operations

```



Conceptual flow:



```text

API

&#x20;↓

Create Job

&#x20;↓

Queue

&#x20;↓

Worker

&#x20;↓

Process

&#x20;↓

Update Database

```



Workers should be retry-safe.



\---



\# 36. Error Handling



Errors must be handled at appropriate boundaries.



Categories:



```text

Validation Error

Authentication Error

Authorization Error

Not Found

Conflict

External Provider Error

Rate Limit

Timeout

Internal Error

```



API responses should use consistent error structures.



Example:



```json

{

&#x20; "error": {

&#x20;   "code": "BUSINESS\_NOT\_FOUND",

&#x20;   "message": "Business was not found."

&#x20; }

}

```



Internal implementation details and secrets must never be returned to clients.



\---



\# 37. External Provider Failures



External services can fail.



Examples:



```text

LLM timeout

Deepgram unavailable

ElevenLabs unavailable

Google Calendar failure

WhatsApp API failure

Object storage failure

```



The application should:



\* Use timeouts

\* Retry safe operations

\* Avoid infinite retries

\* Log failures

\* Return safe user-facing messages

\* Preserve recoverable state

\* Avoid duplicate side effects



\---



\# 38. Idempotency



Idempotency is required for operations where duplicate processing could cause damage.



Important examples:



```text

WhatsApp webhook events

Appointment creation

External message delivery

Background jobs

```



The same external event should not create duplicate records.



\---



\# 39. Security Architecture



Security boundaries:



```text

Browser

&#x20;  ↓ HTTPS

API Gateway

&#x20;  ↓ Authentication

Authorization

&#x20;  ↓

Application Services

&#x20;  ↓

Repositories / Providers

&#x20;  ↓

Data Stores

```



Security requirements include:



\* TLS in production

\* Secure authentication

\* Password hashing

\* Tenant isolation

\* Input validation

\* Authorization checks

\* Rate limiting

\* Request size limits

\* Secure cookies/tokens

\* CORS configuration

\* Security headers

\* Safe error responses

\* Secret management

\* Audit logging where appropriate



\---



\# 40. AI Security



The AI system must be treated as an untrusted decision-making component.



The LLM must not receive unrestricted infrastructure access.



Correct:



```text

LLM

&#x20;↓

Requested Tool

&#x20;↓

Backend Validation

&#x20;↓

Authorization

&#x20;↓

Business Rules

&#x20;↓

Execution

```



Incorrect:



```text

LLM

&#x20;↓

Direct Database Access

```



The system must defend against:



\* Prompt injection

\* Tool manipulation

\* Cross-tenant retrieval

\* Unauthorized tool calls

\* Malicious knowledge-base content

\* Sensitive information leakage



\---



\# 41. Provider Abstraction



Provider interfaces should be defined before provider-specific business logic.



Example:



```python

class LLMProvider:

&#x20;   async def generate(...):

&#x20;       ...

```



Implementation:



```text

LLMProvider

&#x20;└── GroqProvider

```



The rest of the application depends on the interface rather than the concrete provider.



Same principle applies to:



```text

Embeddings

STT

TTS

Calendar

Messaging

Email

Storage

```



\---



\# 42. Database Architecture



Approved database:



```text

PostgreSQL

```



Vector extension:



```text

pgvector

```



SQL Server is not part of the approved implementation architecture.



The obsolete SQL Server 7 section found in the SRS is treated as a legacy/template fragment and does not override the PostgreSQL architecture defined by the SRS architecture sections and SDD.



\---



\# 43. Core Data Relationships



```text

Owner

&#x20;│

&#x20;└── Business

&#x20;     │

&#x20;     ├── AgentConfig

&#x20;     │

&#x20;     ├── KnowledgeBaseEntry

&#x20;     │

&#x20;     ├── Conversation

&#x20;     │     └── Message

&#x20;     │

&#x20;     ├── Lead

&#x20;     │

&#x20;     ├── Appointment

&#x20;     │

&#x20;     └── AnalyticsSnapshot

```



\---



\# 44. Data Access Pattern



Services should interact with repositories.



Example:



```text

Lead API

&#x20;  ↓

LeadService

&#x20;  ↓

LeadRepository

&#x20;  ↓

PostgreSQL

```



Not:



```text

Lead API

&#x20;  ↓

Raw SQL

```



This improves:



\* Testing

\* Maintainability

\* Separation of concerns

\* Reusability



\---



\# 45. API → Service → Repository Example



For retrieving leads:



```text

GET /api/v1/leads

&#x20;       ↓

LeadRouter

&#x20;       ↓

LeadService

&#x20;       ↓

LeadRepository

&#x20;       ↓

PostgreSQL

&#x20;       ↓

LeadRepository

&#x20;       ↓

LeadService

&#x20;       ↓

Response Schema

&#x20;       ↓

API Response

```



\---



\# 46. API → Orchestrator Example



For a chat message:



```text

POST /api/v1/chat/message

&#x20;       ↓

ChatRouter

&#x20;       ↓

ConversationService

&#x20;       ↓

Orchestrator

&#x20;       ↓

Language Detection

&#x20;       ↓

RAG

&#x20;       ↓

Agent Behavior

&#x20;       ↓

LLM

&#x20;       ↓

Tool?

&#x20;  ┌────┴────┐

&#x20;  │         │

&#x20; Yes        No

&#x20;  │         │

Tool Layer   Response

&#x20;  │

Service

&#x20;  │

Database/Provider

&#x20;  │

Result

&#x20;  ↓

Orchestrator

&#x20;  ↓

Response

```



\---



\# 47. Observability



The system should provide structured logging.



Important events:



```text

Authentication events

API errors

External provider errors

Webhook processing

Background job failures

AI tool execution

Security events

Appointment operations

```



Logs must not contain:



\* Passwords

\* API keys

\* OAuth refresh tokens

\* Sensitive personal data unnecessarily

\* Full secret-bearing requests



\---



\# 48. Performance Architecture



Initial targets from the approved requirements:



```text

Voice p95:

< 1.5 seconds target



WhatsApp/Web Chat p95:

< 5 seconds target



Dashboard:

< 3 seconds interactive target



Demo concurrent active conversations:

30

```



Optimization should focus on:



\* Efficient database queries

\* Proper indexes

\* Async external calls

\* Redis for temporary/cache use

\* Background jobs

\* Limited RAG retrieval

\* Streaming where appropriate

\* Avoiding unnecessary API calls



\---



\# 49. Scalability Strategy



AgentDesk should be scalable without introducing unnecessary microservices.



Initial architecture:



```text

Next.js

&#x20;  +

FastAPI

&#x20;  +

Worker

&#x20;  +

PostgreSQL

&#x20;  +

Redis

```



Do not split every subsystem into independent microservices.



For the FYP, a modular monolith is preferred.



The architecture should allow future extraction of services if actual scale requires it.



\---



\# 50. Deployment Architecture



Approved conceptual deployment:



```text

&#x20;                   Internet

&#x20;                      │

&#x20;            ┌─────────┴─────────┐

&#x20;            │                   │

&#x20;            ▼                   ▼

&#x20;       Next.js Frontend      External APIs

&#x20;            │

&#x20;            │ HTTPS

&#x20;            ▼

&#x20;       FastAPI Backend

&#x20;            │

&#x20;      ┌─────┼──────────┐

&#x20;      │     │          │

&#x20;      ▼     ▼          ▼

&#x20;PostgreSQL Redis      Worker

&#x20;+ pgvector             │

&#x20;      │                │

&#x20;      └───────┬────────┘

&#x20;              │

&#x20;              ▼

&#x20;      S3-Compatible Storage

```



Potential deployment services:



```text

Frontend → Vercel

Backend → Railway / Render

Database → PostgreSQL deployment

Redis → Managed Redis

Storage → S3-compatible provider

```



The exact deployment provider may change without changing the application architecture.



\---



\# 51. Docker Architecture



Local development should support:



```text

frontend

backend

postgres

redis

worker

```



Conceptually:



```text

docker-compose.yml



services:

&#x20; frontend

&#x20; backend

&#x20; postgres

&#x20; redis

&#x20; worker

```



External services remain configurable through environment variables.



\---



\# 52. Environment Configuration



Secrets must be provided through environment variables.



Example:



```text

DATABASE\_URL=

REDIS\_URL=



JWT\_SECRET=



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



The exact variables will be finalized in the environment configuration documentation.



`.env` must never be committed.



`.env.example` may contain variable names but no real credentials.



\---



\# 53. Testing Architecture



Testing exists at multiple levels.



\## Unit Tests



Test:



\* Services

\* Repositories

\* Scoring rules

\* Validation

\* RAG utilities

\* Language utilities

\* Tool validation



\## Integration Tests



Test:



\* API + database

\* Authentication

\* Tenant isolation

\* RAG retrieval

\* External provider adapters

\* Booking workflow



\## End-to-End Tests



Test major user journeys:



```text

Registration

&#x20;↓

Onboarding

&#x20;↓

Knowledge Upload

&#x20;↓

Configure Agent

&#x20;↓

Chat

&#x20;↓

Lead Capture

&#x20;↓

Appointment Booking

```



\---



\# 54. Architecture-Level Security Tests



Mandatory security tests include:



```text

User A cannot access Business B

User A cannot access Business B's leads

User A cannot retrieve Business B's knowledge

User A cannot modify Business B's agent configuration

Unauthorized tools cannot execute

Invalid webhook signatures are rejected

Invalid OAuth state is rejected

Oversized uploads are rejected

Invalid file types are rejected

```



\---



\# 55. Architecture Anti-Patterns



The following are prohibited.



\## 55.1 Direct Database Access From Frontend



Incorrect:



```text

Next.js → PostgreSQL

```



\## 55.2 AI Directly Accessing Database



Incorrect:



```text

LLM → PostgreSQL

```



\## 55.3 AI Directly Accessing External Services



Incorrect:



```text

LLM → Google Calendar

```



Correct:



```text

LLM → Tool → Backend Validation → Calendar Provider

```



\## 55.4 Business Logic Inside UI Components



Complex business rules belong in backend/application services.



\## 55.5 Duplicated Orchestrators



There must be one central orchestration architecture.



Do not create:



```text

WhatsAppOrchestrator

VoiceOrchestrator

WebChatOrchestrator

```



with duplicated business logic.



Channels should feed into shared orchestration.



\## 55.6 Uncontrolled Provider Calls



All external providers should be accessed through adapters.



\## 55.7 Ignoring Tenant Scope



Every business-owned query must respect tenant boundaries.



\## 55.8 Large Monolithic Route Handlers



Route handlers should not contain hundreds of lines of business logic.



\## 55.9 Unnecessary Microservices



Do not introduce separate services merely for architectural appearance.



\---



\# 56. Channel Abstraction



Different communication channels should converge into common conversation processing.



```text

Web Chat ────────┐

&#x20;                │

WhatsApp ────────┼──→ Conversation Layer

&#x20;                │          ↓

Voice ───────────┘     AI Orchestrator

&#x20;                          ↓

&#x20;                 Business Brain

&#x20;                          ↓

&#x20;                    Agents/Tools

```



This prevents channel-specific duplication.



\---



\# 57. Conversation Normalization



Each channel should normalize incoming messages into a common internal representation.



Conceptual structure:



```text

IncomingMessage

{

&#x20;   business\_id

&#x20;   conversation\_id

&#x20;   channel

&#x20;   customer\_identifier

&#x20;   language

&#x20;   content

&#x20;   metadata

}

```



The orchestrator should work with normalized application data rather than provider-specific payloads.



\---



\# 58. External Integration Boundary



Provider-specific formats must remain inside adapter modules.



Example:



```text

WhatsApp Payload

&#x20;     ↓

WhatsApp Adapter

&#x20;     ↓

Normalized Message

&#x20;     ↓

Application

```



Not:



```text

Application

&#x20; ↓

WhatsApp-specific payload everywhere

```



This makes provider replacement easier.



\---



\# 59. Transaction Boundaries



Database changes that belong to one logical operation should be handled transactionally.



Examples:



```text

Create Lead

Create Appointment Record

Update Agent Configuration

Create Business

Save Knowledge Entry

```



External calls should not be assumed to be transactional with PostgreSQL.



For external operations:



```text

Validate

&#x20;↓

External Operation

&#x20;↓

Persist Result

&#x20;↓

Handle Failure/Retry

```



\---



\# 60. Consistency Strategy



PostgreSQL is the source of truth for persistent application state.



Redis is temporary/supporting state.



External services are sources of external state.



Example:



```text

Appointment

PostgreSQL → local application record

Google Calendar → external calendar event

```



Both identifiers should be stored when required.



\---



\# 61. Architecture Change Policy



No developer or AI coding agent may silently change:



\* Database technology

\* Core framework

\* Layer boundaries

\* Multi-tenant model

\* Agent architecture

\* Provider abstraction

\* Authentication architecture

\* Security model

\* Approved data model



If a change is necessary:



```text

Identify problem

&#x20;↓

Propose change

&#x20;↓

Explain impact

&#x20;↓

Get approval

&#x20;↓

Update architecture documentation

&#x20;↓

Implement

&#x20;↓

Test

```



\---



\# 62. Antigravity Implementation Rule



Antigravity must treat these architecture documents as constraints.



Before implementing a feature, it must:



1\. Read `AGENTS.md`

2\. Read the relevant architecture documents

3\. Inspect existing code

4\. Identify affected modules

5\. Make the smallest appropriate change

6\. Preserve architecture

7\. Run relevant tests

8\. Report changes and test results



It must not redesign AgentDesk autonomously.



\---



\# 63. Definition of Architecture Compliance



An implementation is architecturally compliant when:



\* Frontend communicates through approved APIs

\* Backend follows layer boundaries

\* Business data is tenant-scoped

\* AI uses the orchestrator

\* Tools are validated by backend

\* External providers use adapters

\* PostgreSQL + pgvector is used as approved

\* Redis is not used as permanent source of truth

\* Secrets remain outside source control

\* Tests cover critical workflows

\* Security boundaries are preserved

\* No unnecessary architectural duplication exists



\---



\# 64. Architecture Baseline



The following decisions are considered \*\*approved and stable\*\*:



```text

Frontend:

Next.js + TypeScript



Backend:

Python + FastAPI



Database:

PostgreSQL + pgvector



Cache/temporary state:

Redis



File storage:

S3-compatible storage



Architecture:

Modular monolith



AI:

Central orchestrator



Agents:

Chat/FAQ

Lead

Voice



RAG:

Tenant-scoped vector retrieval



Voice:

Browser simulator for FYP



Messaging:

WhatsApp Business Cloud API



Calendar:

Google Calendar API



Deployment:

Frontend + backend + worker + managed data services

```



Provider implementations remain replaceable behind interfaces.



\---



\# 65. Final Architecture Rule



The most important architectural principle is:



> \*\*AgentDesk is one multi-tenant platform with one shared business brain, one central orchestration architecture, modular agents, controlled tools, tenant-scoped knowledge, and replaceable external providers.\*\*



Development must preserve this principle.



\---



\*\*Document Status:\*\* Approved Architecture Baseline

\*\*Next Document:\*\* `03\_TECH\_STACK.md`



