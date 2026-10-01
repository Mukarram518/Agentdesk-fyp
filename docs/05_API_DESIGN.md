\# AgentDesk — API Design



\*\*Project:\*\* AgentDesk

\*\*Document:\*\* API Design

\*\*Version:\*\* 1.0

\*\*Status:\*\* Approved Development Baseline

\*\*Related Documents:\*\*



\* `00\_MASTER\_DEVELOPMENT\_BLUEPRINT.md`

\* `01\_PROJECT\_SCOPE.md`

\* `02\_ARCHITECTURE.md`

\* `03\_TECH\_STACK.md`

\* `04\_DATABASE\_DESIGN.md`



\---



\## 1. Purpose



This document defines the API architecture and communication contracts for AgentDesk.



The API is responsible for communication between:



\* Next.js frontend

\* Web chat widget

\* Voice simulator

\* FastAPI backend

\* AI orchestrator

\* Agent services

\* PostgreSQL database

\* Redis/background workers

\* Google Calendar

\* WhatsApp Business Cloud API

\* AI providers

\* Speech-to-text and text-to-speech providers

\* File storage



The API must follow the architecture defined in the SRS, SDD, Master Development Blueprint, Architecture Design, and Database Design.



This document is an implementation guide.



\---



\# 2. API Architecture



AgentDesk uses a REST API for normal application operations and WebSockets for real-time voice communication.



```text

&#x20;                   ┌─────────────────────┐

&#x20;                   │     Next.js Web      │

&#x20;                   └──────────┬──────────┘

&#x20;                              │

&#x20;                              │ HTTPS REST

&#x20;                              ▼

&#x20;                   ┌─────────────────────┐

&#x20;                   │    FastAPI API      │

&#x20;                   │      /api/v1        │

&#x20;                   └──────────┬──────────┘

&#x20;                              │

&#x20;             ┌────────────────┼────────────────┐

&#x20;             │                │                │

&#x20;             ▼                ▼                ▼

&#x20;       Application        Orchestrator      Services

&#x20;         Services             │                │

&#x20;             │                │                │

&#x20;             └────────┬───────┴────────┬───────┘

&#x20;                      │                │

&#x20;                      ▼                ▼

&#x20;                PostgreSQL           Redis

&#x20;                  + pgvector

```



External systems:



```text

FastAPI

&#x20; │

&#x20; ├── LLM Provider

&#x20; ├── Embedding Provider

&#x20; ├── Deepgram

&#x20; ├── ElevenLabs

&#x20; ├── Google Calendar

&#x20; ├── WhatsApp

&#x20; ├── Email Provider

&#x20; └── S3-compatible Storage

```



\---



\# 3. API Base URL



All normal application endpoints use:



```text

/api/v1

```



Example:



```text

GET /api/v1/auth/me

GET /api/v1/business

GET /api/v1/conversations

POST /api/v1/knowledge

```



The production API base URL is environment-dependent.



Example:



```text

https://api.example.com/api/v1

```



The frontend must obtain the API base URL from environment configuration.



It must not hard-code production URLs inside components.



\---



\# 4. API Versioning



The initial API version is:



```text

v1

```



Base path:



```text

/api/v1

```



Breaking API changes require a new version.



Example:



```text

/api/v2

```



Non-breaking additions may remain within `v1`.



Examples of non-breaking changes:



\* adding an optional response field

\* adding a new endpoint

\* adding an optional request parameter



Breaking changes include:



\* removing an existing field

\* changing the meaning of an existing field

\* changing required request parameters

\* changing response structure incompatibly



\---



\# 5. Transport Requirements



Normal API communication must use HTTPS in production.



Requirements:



\* HTTPS

\* TLS

\* JSON request/response bodies

\* UTF-8 encoding

\* REST conventions

\* WebSockets for voice streaming

\* multipart/form-data for file uploads



Development may use:



```text

http://localhost

```



Production must use:



```text

https://

```



\---



\# 6. Authentication



AgentDesk supports:



1\. Email/password authentication

2\. Google sign-in



Authentication is handled by the backend.



The frontend must never directly authenticate against the database.



\---



\# 7. Session Behavior



The backend creates an authenticated session after successful login.



Production authentication should use secure cookies or an equivalent secure access/refresh-token architecture.



For cookie-based authentication:



```text

HttpOnly

Secure

SameSite

```



must be configured appropriately.



Authentication credentials must never be stored in:



\* localStorage

\* source code

\* GitHub

\* frontend environment variables exposed to the browser



\---



\# 8. Authentication Endpoints



\## 8.1 Register



```http

POST /api/v1/auth/register

```



Request:



```json

{

&#x20; "email": "owner@example.com",

&#x20; "password": "StrongPassword123!"

}

```



Response:



```json

{

&#x20; "user": {

&#x20;   "id": "uuid",

&#x20;   "email": "owner@example.com",

&#x20;   "verified": false

&#x20; }

}

```



Validation:



\* valid email

\* password policy

\* duplicate email detection

\* password securely hashed using approved password hashing

\* never store plaintext passwords



\---



\## 8.2 Login



```http

POST /api/v1/auth/login

```



Request:



```json

{

&#x20; "email": "owner@example.com",

&#x20; "password": "StrongPassword123!"

}

```



Response:



```json

{

&#x20; "user": {

&#x20;   "id": "uuid",

&#x20;   "email": "owner@example.com"

&#x20; }

}

```



Authentication session/token is established by the backend.



\---



\## 8.3 Logout



```http

POST /api/v1/auth/logout

```



Response:



```json

{

&#x20; "success": true

}

```



The backend invalidates or clears the authenticated session.



\---



\## 8.4 Current User



```http

GET /api/v1/auth/me

```



Response:



```json

{

&#x20; "id": "uuid",

&#x20; "email": "owner@example.com",

&#x20; "verified": true

}

```



\---



\## 8.5 Google Authentication



```http

GET /api/v1/auth/google

```



The backend initiates Google OAuth.



Callback:



```http

GET /api/v1/auth/google/callback

```



The backend:



1\. validates the OAuth response

2\. identifies the owner

3\. creates or retrieves the account

4\. establishes the application session

5\. redirects to the frontend



Google credentials/tokens must never be exposed unnecessarily to the browser.



\---



\# 9. Current Business / Tenant Resolution



AgentDesk is multi-tenant.



Every authenticated owner operates within an authorized business context.



The backend must determine the current business from authenticated server-side state.



The frontend must not be trusted to provide an arbitrary `business\_id`.



Unsafe pattern:



```text

GET /api/v1/businesses/{business\_id}/leads

```



where authorization is not checked.



The backend must always verify:



```text

authenticated user

&#x20;       ↓

authorized business

&#x20;       ↓

requested resource

```



A business ID supplied by the frontend may be used as a reference only after authorization.



\---



\# 10. Tenant Isolation Rule



Every tenant-sensitive query must be scoped to the authorized business.



Example:



```text

SELECT leads

WHERE business\_id = current\_authorized\_business

```



Never:



```text

SELECT leads

```



followed by frontend filtering.



Tenant isolation must be enforced server-side.



This applies to:



\* knowledge

\* conversations

\* messages

\* leads

\* appointments

\* analytics

\* agent configuration

\* uploaded files

\* integrations

\* RAG retrieval



\---



\# 11. Standard Response Format



Successful responses should use predictable JSON structures.



Simple response:



```json

{

&#x20; "data": {}

}

```



List response:



```json

{

&#x20; "data": \[],

&#x20; "pagination": {

&#x20;   "page": 1,

&#x20;   "page\_size": 20,

&#x20;   "total": 100,

&#x20;   "total\_pages": 5

&#x20; }

}

```



Mutation response:



```json

{

&#x20; "data": {},

&#x20; "message": "Operation completed successfully"

}

```



The implementation may simplify responses for specific endpoints where appropriate, but response structures must remain consistent within the API.



\---



\# 12. Error Response Format



Errors should follow a consistent structure.



Example:



```json

{

&#x20; "error": {

&#x20;   "code": "VALIDATION\_ERROR",

&#x20;   "message": "The request contains invalid data.",

&#x20;   "details": {

&#x20;     "email": "Invalid email address."

&#x20;   }

&#x20; }

}

```



Errors must not expose:



\* stack traces

\* database credentials

\* API keys

\* provider secrets

\* internal filesystem paths

\* SQL statements

\* sensitive debugging information



\---



\# 13. Standard HTTP Status Codes



AgentDesk uses standard HTTP status codes.



| Status | Meaning                                  |

| ------ | ---------------------------------------- |

| 200    | Successful request                       |

| 201    | Resource created                         |

| 202    | Accepted for background processing       |

| 204    | Successful request with no response body |

| 400    | Invalid request                          |

| 401    | Authentication required/failed           |

| 403    | Authenticated but not authorized         |

| 404    | Resource not found                       |

| 409    | Conflict                                 |

| 413    | Request/file too large                   |

| 415    | Unsupported media type                   |

| 422    | Validation error                         |

| 429    | Rate limit exceeded                      |

| 500    | Internal server error                    |

| 502    | External provider failure                |

| 503    | Service temporarily unavailable          |



\---



\# 14. Pagination



Large collections must use pagination.



Default:



```text

page=1

page\_size=20

```



Example:



```http

GET /api/v1/conversations?page=1\&page\_size=20

```



The backend must enforce a maximum page size.



Example:



```text

maximum = 100

```



The exact value may be configured without changing the API architecture.



\---



\# 15. Filtering



Endpoints may support filters where useful.



Example:



```http

GET /api/v1/leads?status=hot

```



Conversation example:



```http

GET /api/v1/conversations?channel=whatsapp

```



Date filtering:



```http

GET /api/v1/conversations?from=2026-09-01\&to=2026-09-30

```



All filters must be validated.



\---



\# 16. Sorting



Supported collection endpoints may allow controlled sorting.



Example:



```http

GET /api/v1/leads?sort=created\_at\&order=desc

```



The backend must use an allowlist of sortable fields.



The frontend must not be able to inject arbitrary SQL through sort parameters.



\---



\# 17. Idempotency



Operations that may be retried must support idempotency where necessary.



Examples:



\* appointment creation

\* external webhook processing

\* message processing

\* external integration operations



Example header:



```text

Idempotency-Key: unique-request-id

```



The backend may store idempotency records where required.



Webhook processing must be idempotent.



\---



\# 18. Authentication API Group



```text

/api/v1/auth

```



Endpoints:



```text

POST /register

POST /login

POST /logout

GET  /me

GET  /google

GET  /google/callback

```



\---



\# 19. Business API



Base:



```text

/api/v1/business

```



\## Get Business



```http

GET /api/v1/business

```



\## Create/Complete Business Onboarding



```http

POST /api/v1/business/onboarding

```



Request:



```json

{

&#x20; "name": "Example Restaurant",

&#x20; "vertical": "restaurant",

&#x20; "hours": {},

&#x20; "contacts": {},

&#x20; "whatsapp\_number": "+92XXXXXXXXXX"

}

```



\## Update Business



```http

PATCH /api/v1/business

```



\## Business Summary



```http

GET /api/v1/business/summary

```



The backend determines the authorized business.



\---



\# 20. Agent Configuration API



Base:



```text

/api/v1/agents

```



\## Get Configuration



```http

GET /api/v1/agents/config

```



\## Update Configuration



```http

PATCH /api/v1/agents/config

```



Example:



```json

{

&#x20; "voice\_enabled": true,

&#x20; "chat\_enabled": true,

&#x20; "lead\_enabled": true,

&#x20; "voice\_id": "provider-voice-id",

&#x20; "tone": "friendly",

&#x20; "greeting": "Hello! How can I help you?",

&#x20; "language\_priority": \[

&#x20;   "ur",

&#x20;   "en"

&#x20; ]

}

```



The backend validates allowed values.



The AI system must never use configuration belonging to another business.



\---



\# 21. Knowledge Base API



Base:



```text

/api/v1/knowledge

```



\## List Knowledge Entries



```http

GET /api/v1/knowledge

```



\## Create FAQ



```http

POST /api/v1/knowledge

```



Request:



```json

{

&#x20; "question": "What time do you open?",

&#x20; "answer": "We open at 9 AM.",

&#x20; "tags": \[

&#x20;   "hours"

&#x20; ],

&#x20; "language": "en"

}

```



The backend:



1\. validates input

2\. creates the knowledge record

3\. generates embedding

4\. stores the vector

5\. marks embedding status appropriately



\---



\## Get Knowledge Entry



```http

GET /api/v1/knowledge/{knowledge\_id}

```



\## Update Knowledge Entry



```http

PATCH /api/v1/knowledge/{knowledge\_id}

```



If content changes:



```text

embedding\_stale = true

```



The embedding must then be regenerated.



\## Delete Knowledge Entry



```http

DELETE /api/v1/knowledge/{knowledge\_id}

```



\---



\# 22. Knowledge File Upload



```http

POST /api/v1/knowledge/files

```



Content type:



```text

multipart/form-data

```



Allowed document types:



```text

PDF

DOCX

```



Maximum file size:



```text

5 MB

```



Processing flow:



```text

Upload

&#x20; ↓

Validate

&#x20; ↓

Store

&#x20; ↓

Extract text

&#x20; ↓

Clean text

&#x20; ↓

Chunk

&#x20; ↓

Generate embeddings

&#x20; ↓

Store vectors

&#x20; ↓

Mark processing complete

```



Large processing operations may return:



```http

202 Accepted

```



with a processing status.



\---



\# 23. Knowledge File Status



```http

GET /api/v1/knowledge/files/{file\_id}

```



Possible statuses:



```text

uploaded

processing

ready

failed

```



The frontend can poll this endpoint for processing status.



Background processing should be used where appropriate.



\---



\# 24. Chat API



The chat system supports:



\* web chat widget

\* dashboard chat preview

\* WhatsApp messages



For normal application chat:



```http

POST /api/v1/chat/messages

```



Request:



```json

{

&#x20; "conversation\_id": "uuid",

&#x20; "message": "What services do you provide?"

}

```



Response:



```json

{

&#x20; "conversation\_id": "uuid",

&#x20; "message": {

&#x20;   "role": "assistant",

&#x20;   "content": "We provide..."

&#x20; }

}

```



The backend sends the message through the orchestrator.



\---



\# 25. Web Chat Widget



The embeddable web widget communicates with:



```text

/api/v1/chat

```



The widget must not receive:



\* database credentials

\* internal provider keys

\* owner session tokens

\* private business configuration



A public widget session must use a controlled business-specific identifier/token mechanism.



The backend determines which business the widget belongs to from trusted configuration.



\---



\# 26. Conversation API



Base:



```text

/api/v1/conversations

```



\## List Conversations



```http

GET /api/v1/conversations

```



Supported filters:



```text

channel

language

status

date range

```



\## Get Conversation



```http

GET /api/v1/conversations/{conversation\_id}

```



\## Get Messages



```http

GET /api/v1/conversations/{conversation\_id}/messages

```



The backend must verify that the conversation belongs to the authorized business.



\---



\# 27. Conversation Detail



Example response:



```json

{

&#x20; "data": {

&#x20;   "id": "uuid",

&#x20;   "channel": "whatsapp",

&#x20;   "language": "ur",

&#x20;   "status": "completed",

&#x20;   "started\_at": "2026-09-29T10:00:00Z",

&#x20;   "ended\_at": "2026-09-29T10:08:00Z",

&#x20;   "outcome": "lead\_created",

&#x20;   "summary": "Customer asked about pricing and requested a callback.",

&#x20;   "messages": \[]

&#x20; }

}

```



\---



\# 28. Lead API



Base:



```text

/api/v1/leads

```



\## List Leads



```http

GET /api/v1/leads

```



Filters:



```text

status

score

date range

```



\## Get Lead



```http

GET /api/v1/leads/{lead\_id}

```



\## Update Lead Status



```http

PATCH /api/v1/leads/{lead\_id}

```



Request:



```json

{

&#x20; "status": "contacted"

}

```



Possible statuses may include:



```text

new

contacted

qualified

converted

closed

```



The final implementation must use one approved status enum consistently.



\---



\# 29. Lead Scoring



The lead agent may classify leads as:



```text

hot

warm

cold

```



Scoring must be generated by the lead subsystem according to documented business logic.



The frontend must not calculate or override the authoritative lead score.



The backend stores the result.



\---



\# 30. Lead Export



```http

GET /api/v1/leads/export

```



The endpoint generates CSV output containing only data belonging to the authorized business.



Export must respect:



\* authentication

\* tenant isolation

\* authorization

\* rate limits

\* safe content handling



\---



\# 31. Appointment API



Base:



```text

/api/v1/appointments

```



\## Get Availability



```http

GET /api/v1/appointments/availability

```



Example:



```text

GET /api/v1/appointments/availability?date=2026-10-01

```



The booking subsystem checks Google Calendar availability where configured.



\---



\## Create Appointment



```http

POST /api/v1/appointments

```



Request:



```json

{

&#x20; "customer\_name": "Ali",

&#x20; "customer\_phone": "+92XXXXXXXXXX",

&#x20; "scheduled\_at": "2026-10-01T14:00:00+05:00",

&#x20; "service": "Consultation"

}

```



Backend flow:



```text

Validate

&#x20; ↓

Check business

&#x20; ↓

Check authorization/context

&#x20; ↓

Check calendar availability

&#x20; ↓

Create Google Calendar event

&#x20; ↓

Store local appointment

```



External and local operations must handle partial failure safely.



\---



\# 32. Reschedule Appointment



```http

PATCH /api/v1/appointments/{appointment\_id}

```



Example:



```json

{

&#x20; "scheduled\_at": "2026-10-01T15:00:00+05:00"

}

```



The backend must verify:



\* appointment ownership

\* business ownership

\* new slot availability

\* Google Calendar state



\---



\# 33. Cancel Appointment



```http

POST /api/v1/appointments/{appointment\_id}/cancel

```



The backend cancels the external event where applicable and updates local state.



\---



\# 34. Google Calendar Integration



Base:



```text

/api/v1/integrations/google-calendar

```



\## Start OAuth



```http

GET /api/v1/integrations/google-calendar/connect

```



\## OAuth Callback



```http

GET /api/v1/integrations/google-calendar/callback

```



\## Integration Status



```http

GET /api/v1/integrations/google-calendar/status

```



\## Disconnect



```http

POST /api/v1/integrations/google-calendar/disconnect

```



Refresh tokens must be encrypted at rest.



\---



\# 35. WhatsApp Integration



Base:



```text

/api/v1/integrations/whatsapp

```



\## Configuration



```http

GET /api/v1/integrations/whatsapp

```



\## Connect/Configure



```http

POST /api/v1/integrations/whatsapp

```



\## Status



```http

GET /api/v1/integrations/whatsapp/status

```



Credentials must be stored securely.



Secrets must never appear in API responses.



\---



\# 36. WhatsApp Webhook



Webhook path:



```text

/api/v1/webhooks/whatsapp

```



Typical operations:



```http

GET  /api/v1/webhooks/whatsapp

POST /api/v1/webhooks/whatsapp

```



GET may be used for provider webhook verification.



POST receives incoming webhook events.



Processing:



```text

Receive webhook

&#x20;      ↓

Verify signature/authenticity

&#x20;      ↓

Check event ID/idempotency

&#x20;      ↓

Identify business

&#x20;      ↓

Create/update conversation

&#x20;      ↓

Send message to orchestrator

&#x20;      ↓

Process agent response

&#x20;      ↓

Send response through WhatsApp

```



Webhook events must be idempotent.



Duplicate events must not create duplicate conversations, messages, leads, or appointments.



\---



\# 37. Orchestrator Internal API



The orchestrator is primarily an internal application service.



It should not be unnecessarily exposed as a public endpoint.



Conceptual operation:



```text

process\_turn()

```



Input:



```json

{

&#x20; "business\_id": "uuid",

&#x20; "conversation\_id": "uuid",

&#x20; "channel": "web",

&#x20; "message": "What time do you open?",

&#x20; "language": "en"

}

```



Processing:



```text

Language Detection

&#x20;       ↓

Intent Detection

&#x20;       ↓

Business Brain

&#x20;       ↓

RAG Retrieval

&#x20;       ↓

Conversation Context

&#x20;       ↓

Agent Selection

&#x20;       ↓

Tool Permission Check

&#x20;       ↓

LLM

&#x20;       ↓

Tool Execution if required

&#x20;       ↓

Response Validation

&#x20;       ↓

Persist Message

&#x20;       ↓

Return Response

```



The orchestrator must enforce tenant isolation.



\---



\# 38. Internal Tool API



AI agents must not directly access:



\* PostgreSQL

\* Redis

\* Google Calendar

\* WhatsApp

\* arbitrary HTTP endpoints



Instead they request approved backend tools.



Examples:



```text

search\_knowledge

get\_business\_info

check\_calendar\_availability

create\_calendar\_event

reschedule\_calendar\_event

cancel\_calendar\_event

create\_lead

send\_owner\_alert

```



Tool execution flow:



```text

AI requests tool

&#x20;      ↓

Backend validates tool name

&#x20;      ↓

Validate arguments

&#x20;      ↓

Validate business/tenant

&#x20;      ↓

Validate authorization

&#x20;      ↓

Execute tool

&#x20;      ↓

Return safe result

```



The LLM never receives unrestricted system access.



\---



\# 39. Voice WebSocket API



Voice communication uses WebSockets.



Conceptual endpoint:



```text

/ws/v1/voice

```



Production example:



```text

wss://api.example.com/ws/v1/voice

```



The browser voice simulator connects to the backend.



Flow:



```text

Browser Microphone

&#x20;      ↓

WebSocket

&#x20;      ↓

FastAPI Voice Gateway

&#x20;      ↓

Deepgram STT

&#x20;      ↓

Orchestrator

&#x20;      ↓

LLM / Tools / RAG

&#x20;      ↓

ElevenLabs TTS

&#x20;      ↓

WebSocket

&#x20;      ↓

Browser Audio

```



\---



\# 40. Voice WebSocket Message Types



Client → server:



```text

start

audio

stop

```



Server → client:



```text

session\_started

transcript

assistant\_text

audio

error

session\_ended

```



Example start message:



```json

{

&#x20; "type": "start",

&#x20; "language": "ur"

}

```



Example transcript:



```json

{

&#x20; "type": "transcript",

&#x20; "text": "Aap kab open hotay hain?"

}

```



Example assistant response:



```json

{

&#x20; "type": "assistant\_text",

&#x20; "text": "Hum subah 9 bajay open hotay hain."

}

```



Audio frames must use the agreed binary/audio protocol.



The exact codec and frame format must be documented before implementation.



\---



\# 41. Voice Session Security



Every voice session must be associated with an authorized business context.



The WebSocket must not accept arbitrary business IDs without validation.



The backend must validate:



\* authenticated owner where required

\* allowed widget/simulator session

\* business context

\* agent enabled state

\* allowed voice configuration



\---



\# 42. Analytics API



Base:



```text

/api/v1/analytics

```



\## Dashboard Summary



```http

GET /api/v1/analytics/summary

```



\## Time Series



```http

GET /api/v1/analytics/timeseries

```



\## Top Intents



```http

GET /api/v1/analytics/intents

```



Analytics may include:



\* calls

\* chats

\* leads

\* bookings

\* top intents



All analytics queries must be tenant-scoped.



\---



\# 43. Dashboard API



The dashboard may aggregate information from multiple API groups.



Example:



```http

GET /api/v1/dashboard/summary

```



Possible response:



```json

{

&#x20; "data": {

&#x20;   "conversations": 120,

&#x20;   "new\_leads": 15,

&#x20;   "appointments": 8,

&#x20;   "active\_agents": 3

&#x20; }

}

```



Dashboard endpoints must not bypass service-layer rules merely for convenience.



\---



\# 44. API Layering



Every endpoint follows:



```text

Router

&#x20; ↓

Schema Validation

&#x20; ↓

Application Service

&#x20; ↓

Repository

&#x20; ↓

Database

```



For AI operations:



```text

Router

&#x20; ↓

Application Service

&#x20; ↓

Orchestrator

&#x20; ↓

Agent

&#x20; ↓

Tool

&#x20; ↓

Provider / Repository

```



Routers must remain thin.



\---



\# 45. Repository Responsibility



Repositories are responsible for data access.



Example:



```text

LeadRepository

ConversationRepository

KnowledgeRepository

AppointmentRepository

BusinessRepository

```



Repositories must not contain:



\* HTTP request handling

\* LLM prompts

\* UI logic

\* provider orchestration



\---



\# 46. Service Responsibility



Services contain application/business logic.



Examples:



```text

BusinessService

KnowledgeService

ConversationService

LeadService

BookingService

IntegrationService

```



Services coordinate:



\* validation

\* authorization context

\* repositories

\* external providers

\* transactions



\---



\# 47. Schema Validation



FastAPI/Pydantic schemas validate:



\* required fields

\* field types

\* lengths

\* enums

\* formats

\* nested structures

\* allowed values



Examples:



```text

Email

Phone

UUID

DateTime

Language

Channel

Status

```



Never trust frontend validation alone.



\---



\# 48. Input Security



API input must be treated as untrusted.



Protection must include:



\* validation

\* size limits

\* content-type validation

\* rate limiting

\* authorization

\* safe database queries

\* safe provider calls



The API must protect against:



\* SQL injection

\* XSS through stored content

\* malicious file uploads

\* oversized requests

\* unauthorized resource access

\* prompt injection through business/customer content



\---



\# 49. File Upload Security



File upload endpoints must enforce:



```text

Maximum size = 5 MB

Allowed formats = PDF, DOCX

```



The backend should validate:



1\. extension

2\. MIME type

3\. file signature/content where practical

4\. file size



Files should be stored outside the application source directory.



Uploaded documents must never be executed as code.



\---



\# 50. RAG API Boundary



RAG retrieval is an internal service.



Conceptual operation:



```text

retrieve\_context(

&#x20;   business\_id,

&#x20;   query,

&#x20;   top\_k

)

```



The query must always include tenant scope.



Conceptually:



```text

business\_id = authorized\_business\_id

```



before vector search.



Unsafe:



```text

vector similarity search across all businesses

```



Safe:



```text

vector similarity search

WHERE business\_id = authorized\_business\_id

```



\---



\# 51. External Provider Failures



External APIs may fail.



Examples:



\* LLM unavailable

\* Deepgram timeout

\* ElevenLabs timeout

\* Google Calendar failure

\* WhatsApp failure



The backend should return safe errors.



Example:



```json

{

&#x20; "error": {

&#x20;   "code": "EXTERNAL\_SERVICE\_UNAVAILABLE",

&#x20;   "message": "The requested service is temporarily unavailable."

&#x20; }

}

```



Do not expose provider credentials or raw internal provider errors to users.



Retries should be implemented only where safe.



\---



\# 52. Rate Limiting



Rate limits must be applied to sensitive and expensive endpoints.



Examples:



\* login

\* registration

\* password-related operations

\* chat

\* voice sessions

\* file uploads

\* CSV exports

\* webhooks where appropriate



Rate limits should be configurable by environment.



\---



\# 53. CORS



CORS must allow only approved frontend origins.



Development may allow:



```text

http://localhost:3000

```



Production must use the actual approved frontend domain.



Do not use:



```text

Access-Control-Allow-Origin: \*

```



for authenticated sensitive APIs unless explicitly justified.



\---



\# 54. Security Headers



Production API/frontend configuration should use appropriate security headers.



Relevant controls include:



\* HTTPS

\* HSTS

\* content-type protection

\* frame protection

\* content security policy where applicable

\* secure cookies



Exact frontend headers may be configured separately in the Next.js deployment.



\---



\# 55. OpenAPI Documentation



FastAPI automatically provides OpenAPI documentation.



Development documentation may be available through:



```text

/docs

```



and:



```text

/openapi.json

```



Production exposure should be evaluated according to the deployment/security configuration.



The OpenAPI specification must reflect actual implemented endpoints.



Do not manually document endpoints that do not exist.



\---



\# 56. API Testing



Every API module should have tests for:



\### Authentication



\* registration

\* duplicate account

\* login

\* invalid password

\* logout

\* authenticated user



\### Authorization



\* unauthorized access

\* cross-tenant access

\* invalid business context

\* protected resources



\### Knowledge



\* create FAQ

\* update FAQ

\* delete FAQ

\* file validation

\* file size limit

\* embedding processing



\### Conversations



\* create conversation

\* add message

\* retrieve conversation

\* tenant isolation



\### Leads



\* create lead

\* retrieve lead

\* update status

\* export



\### Appointments



\* availability

\* creation

\* rescheduling

\* cancellation

\* calendar failure



\### Integrations



\* OAuth callback

\* integration status

\* webhook verification

\* duplicate webhook



\### AI



\* orchestrator routing

\* RAG tenant isolation

\* tool authorization

\* invalid tool arguments



\### Voice



\* WebSocket connection

\* session lifecycle

\* invalid session

\* provider failure



\---



\# 57. API Test Security Requirement



At minimum, automated tests must prove that:



```text

Business A cannot access Business B data.

```



This must be tested for:



\* conversations

\* messages

\* leads

\* appointments

\* knowledge

\* analytics

\* agent configuration

\* files



Tenant isolation is a release requirement.



\---



\# 58. Example: Web Chat Flow



```text

1\. User opens AgentDesk widget

2\. Widget establishes a controlled chat session

3\. User sends message

4\. POST /api/v1/chat/messages

5\. Backend identifies business

6\. Conversation is loaded/created

7\. Message is stored

8\. Orchestrator processes message

9\. Language is detected

10\. Relevant RAG context is retrieved

11\. Agent determines required action

12\. Tool is called if required

13\. Response is generated

14\. Response is validated

15\. Assistant message is stored

16\. Response is returned to widget

```



\---



\# 59. Example: WhatsApp Flow



```text

WhatsApp

&#x20;  ↓

Webhook

&#x20;  ↓

Signature verification

&#x20;  ↓

Idempotency check

&#x20;  ↓

Business identification

&#x20;  ↓

Conversation lookup/create

&#x20;  ↓

Store incoming message

&#x20;  ↓

Orchestrator

&#x20;  ↓

RAG / Agent / Tools

&#x20;  ↓

Generate response

&#x20;  ↓

Store response

&#x20;  ↓

WhatsApp API

&#x20;  ↓

Customer

```



\---



\# 60. Example: Appointment Flow



```text

Customer:

"I want an appointment tomorrow at 3 PM."



&#x20;       ↓



Chat/Voice Agent



&#x20;       ↓



Booking Tool



&#x20;       ↓



Check Calendar Availability



&#x20;       ↓



Available?



&#x20;  ┌────┴────┐

&#x20;  │         │

&#x20; Yes        No

&#x20;  │         │

&#x20;  ↓         ↓

Create       Suggest

Event        alternatives

&#x20;  │

&#x20;  ↓

Store Appointment

&#x20;  │

&#x20;  ↓

Confirm to Customer

```



\---



\# 61. Example: Lead Flow



```text

Customer conversation

&#x20;       ↓

Buying intent detected

&#x20;       ↓

Lead information collected

&#x20;       ↓

Name

Contact

Need

&#x20;       ↓

Lead score

&#x20;       ↓

Lead record created

&#x20;       ↓

Owner notification

```



The lead creation operation must be tenant-scoped.



\---



\# 62. API and AI Separation



AI-generated output must not automatically perform privileged operations.



For example:



```text

LLM says:

"Create appointment for 5 PM."

```



This does not directly create an appointment.



Instead:



```text

LLM

&#x20;↓

Tool request

&#x20;↓

Backend validation

&#x20;↓

Authorization

&#x20;↓

Calendar availability

&#x20;↓

Create appointment

```



The backend remains the authority.



\---



\# 63. Sensitive API Data



API responses must minimize sensitive data.



Never return:



\* password hashes

\* Google refresh tokens

\* API keys

\* WhatsApp secrets

\* provider credentials

\* internal security tokens



Encrypted values should remain encrypted and inaccessible to normal API consumers.



\---



\# 64. Logging



API logs should include useful operational information such as:



```text

request ID

endpoint

HTTP method

status code

duration

business context where appropriate

error code

```



Do not log:



\* passwords

\* access tokens

\* API keys

\* OAuth refresh tokens

\* complete sensitive customer conversations unless explicitly required and protected



\---



\# 65. Request IDs



API requests should have a request/correlation ID.



Example:



```text

X-Request-ID

```



If provided by a trusted upstream service, it may be propagated safely.



Otherwise, the backend may generate one.



This helps trace:



```text

Frontend

&#x20;↓

API

&#x20;↓

Service

&#x20;↓

Orchestrator

&#x20;↓

Provider

```



\---



\# 66. API Timeout Rules



External calls must have explicit timeouts.



No external provider request should wait indefinitely.



Applicable services include:



\* LLM

\* Deepgram

\* ElevenLabs

\* Google Calendar

\* WhatsApp

\* email

\* object storage



Timeout behavior must produce a controlled application error.



\---



\# 67. Background Processing



Long-running operations should not block normal HTTP requests.



Examples:



\* document extraction

\* embedding generation

\* analytics snapshots

\* certain notifications

\* retryable external operations



Flow:



```text

API

&#x20;↓

Queue

&#x20;↓

Worker

&#x20;↓

Processing

&#x20;↓

Database status update

```



Redis may support queue/background processing according to the approved architecture.



\---



\# 68. API Performance



Target behavior follows the project performance requirements.



Important targets include:



\* voice p95 response under approximately 1.5 seconds where practical

\* WhatsApp/web chat p95 under approximately 5 seconds

\* dashboard interactive under approximately 3 seconds



The implementation should measure actual performance rather than claiming the target is met without testing.



\---



\# 69. API Documentation Rules



Whenever an endpoint is implemented, document:



```text

Method

Path

Authentication

Purpose

Request

Response

Errors

Authorization

Side effects

```



If implementation changes an approved API contract, update the API documentation.



\---



\# 70. API Change Policy



Do not change an API contract casually.



Before making a breaking change:



1\. identify affected frontend/backend components

2\. update this document

3\. update OpenAPI

4\. update tests

5\. update related documentation

6\. migrate consumers

7\. verify backwards compatibility where required



\---



\# 71. Antigravity Implementation Rules



Antigravity must follow these API rules.



\### Rule 1 — Follow the documentation



Use:



```text

00\_MASTER\_DEVELOPMENT\_BLUEPRINT.md

01\_PROJECT\_SCOPE.md

02\_ARCHITECTURE.md

03\_TECH\_STACK.md

04\_DATABASE\_DESIGN.md

05\_API\_DESIGN.md

```



as the source of truth.



\### Rule 2 — Do not redesign



Do not introduce a different API architecture without explicit approval.



\### Rule 3 — Do not bypass service layers



Do not place business logic directly inside route handlers.



\### Rule 4 — Validate everything



All external input must be validated.



\### Rule 5 — Enforce tenant isolation



Never trust frontend-provided tenant identifiers.



\### Rule 6 — Protect secrets



Never expose credentials through API responses or source code.



\### Rule 7 — Test API behavior



Every new endpoint requires appropriate tests.



\### Rule 8 — Preserve existing behavior



Do not modify unrelated endpoints while implementing a feature.



\### Rule 9 — No duplicate APIs



Do not create multiple endpoints performing the same responsibility without documented reason.



\### Rule 10 — Update documentation



If an approved API contract changes, update this document.



\---



\# 72. Definition of Done — API



An API feature is complete only when:



\* endpoint is implemented

\* request schema exists

\* response schema is defined

\* validation exists

\* authentication is handled

\* authorization is handled

\* tenant isolation is enforced

\* service layer is used

\* repository layer is used where database access is required

\* external provider errors are handled

\* tests exist

\* OpenAPI is accurate

\* no secrets are exposed

\* existing functionality remains intact



\---



\# 73. API Release Gate



Before release, verify:



```text

\[ ] Authentication works

\[ ] Authorization works

\[ ] Tenant isolation tests pass

\[ ] Validation works

\[ ] Error responses are safe

\[ ] Rate limits exist where required

\[ ] File limits are enforced

\[ ] Webhook signatures are verified

\[ ] Webhook idempotency works

\[ ] External provider failures are handled

\[ ] API documentation is accurate

\[ ] Tests pass

\[ ] No secrets are committed

```



\---



\# 74. Final API Architecture



AgentDesk API follows:



```text

Next.js / Web Widget

&#x20;       │

&#x20;       │ HTTPS REST

&#x20;       ▼

&#x20;    FastAPI

&#x20;       │

&#x20;       ▼

&#x20;   API Routers

&#x20;       │

&#x20;       ▼

Application Services

&#x20;       │

&#x20;  ┌────┴─────┐

&#x20;  │          │

Repositories  Orchestrator

&#x20;  │          │

&#x20;  ▼          ▼

PostgreSQL   Agents

\+ pgvector    │

&#x20;  │          ▼

&#x20;  │         Tools

&#x20;  │          │

&#x20;  │          ▼

&#x20;  │       Providers

&#x20;  │

&#x20;  ▼

&#x20;Redis / Workers

```



Real-time voice:



```text

Browser

&#x20;  │

&#x20;WebSocket

&#x20;  ▼

FastAPI Voice Gateway

&#x20;  │

&#x20;  ▼

Deepgram

&#x20;  │

&#x20;  ▼

Orchestrator

&#x20;  │

&#x20;  ▼

LLM / Tools / RAG

&#x20;  │

&#x20;  ▼

ElevenLabs

&#x20;  │

&#x20;  ▼

Browser

```



External messaging:



```text

WhatsApp

&#x20;  ↓

Verified Webhook

&#x20;  ↓

FastAPI

&#x20;  ↓

Conversation

&#x20;  ↓

Orchestrator

&#x20;  ↓

Agent / Tools / RAG

&#x20;  ↓

WhatsApp

```



\---



\# 75. Final Rule



The AgentDesk API is a controlled boundary between the user interface, AI systems, business logic, data, and external services.



The API must remain:



\* secure

\* tenant-isolated

\* validated

\* testable

\* versioned

\* documented

\* provider-independent

\* consistent with the approved architecture



\*\*The frontend requests actions.

The backend authorizes actions.

The services execute business logic.

The repositories access data.

The AI requests tools.

The backend validates and executes tools.\*\*



No component may bypass these boundaries without explicit architectural approval.



\*\*Status: Approved Development Baseline\*\*



