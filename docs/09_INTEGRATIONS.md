\# AgentDesk — External Integrations Design



\*\*Project:\*\* AgentDesk — A Multi-Agent AI Platform for Small Businesses

\*\*Document:\*\* External Integrations Design

\*\*Version:\*\* 1.0

\*\*Status:\*\* Approved Architecture Baseline



\*\*Related Documents:\*\*



\* `00\_MASTER\_DEVELOPMENT\_BLUEPRINT.md`

\* `01\_PROJECT\_SCOPE.md`

\* `02\_ARCHITECTURE.md`

\* `03\_TECH\_STACK.md`

\* `04\_DATABASE\_DESIGN.md`

\* `05\_API\_DESIGN.md`

\* `06\_AI\_ORCHESTRATOR.md`

\* `07\_AGENT\_DESIGN.md`

\* `08\_RAG\_DESIGN.md`



\---



\# 1. Purpose



This document defines how AgentDesk integrates with external services.



AgentDesk depends on external services for:



\* Large language model inference

\* Text embeddings

\* Speech-to-text

\* Text-to-speech

\* WhatsApp messaging

\* Google Calendar

\* Email notifications

\* Object/file storage



The integration architecture must keep external providers isolated from the core application.



The application must be able to replace a provider without requiring a complete rewrite of the platform.



\---



\# 2. Integration Principles



All integrations must follow these principles:



1\. Use provider abstraction where appropriate.

2\. Keep API credentials on the backend.

3\. Never expose secrets to the frontend.

4\. Validate all external responses.

5\. Handle timeouts.

6\. Handle retries where safe.

7\. Log useful operational information without logging secrets.

8\. Make webhook processing idempotent.

9\. Verify webhook signatures.

10\. Apply tenant/business authorization.

11\. Fail gracefully when an external provider is unavailable.

12\. Keep provider-specific code outside core business logic.



\---



\# 3. Integration Architecture



The general architecture is:



```text id="8vyr8d"

&#x20;                   AgentDesk Core

&#x20;                        |

&#x20;                        v

&#x20;               Provider Interface

&#x20;                        |

&#x20;             ┌──────────┼──────────┐

&#x20;             │          │          │

&#x20;             v          v          v

&#x20;          Provider A  Provider B  Provider C

```



Example:



```text id="g2d6t8"

LLMProvider

&#x20;  |

&#x20;  +── GroqProvider

&#x20;  +── FutureLLMProvider

```



The orchestrator depends on:



```text id="f8t2tq"

LLMProvider

```



not directly on:



```text id="j4c9y0"

Groq API

```



\---



\# 4. Integration Categories



AgentDesk integrations are grouped into:



| Category   | Integration                  |

| ---------- | ---------------------------- |

| LLM        | LLM provider                 |

| Embeddings | Embedding provider           |

| STT        | Deepgram                     |

| TTS        | ElevenLabs                   |

| Messaging  | WhatsApp Business Cloud API  |

| Calendar   | Google Calendar API          |

| Storage    | S3-compatible object storage |

| Email      | Email provider               |

| Database   | PostgreSQL                   |

| Cache/Jobs | Redis                        |



PostgreSQL and Redis are infrastructure dependencies rather than external AI integrations, but they are included here for integration-boundary consistency.



\---



\# 5. LLM Integration



The LLM is responsible for language understanding and response generation.



Primary responsibilities:



\* Intent interpretation

\* Structured output generation

\* Tool selection

\* Response generation

\* Language-aware responses



The LLM must not directly:



\* Access the database

\* Access Redis

\* Access external APIs

\* Send WhatsApp messages

\* Modify appointments

\* Modify leads

\* Access another tenant



All actions must go through backend tools.



\---



\# 6. LLM Provider Abstraction



Recommended interface:



```python id="1u3g6s"

class LLMProvider:

&#x20;   async def generate(

&#x20;       self,

&#x20;       messages,

&#x20;       tools=None,

&#x20;       response\_schema=None

&#x20;   ):

&#x20;       ...

```



The exact implementation may use provider-specific request/response structures internally.



Core AgentDesk services must not depend on those structures.



\---



\# 7. LLM Provider Configuration



Configuration should be environment-driven.



Example:



```text id="zks2da"

LLM\_PROVIDER=...

LLM\_MODEL=...

LLM\_API\_KEY=...

LLM\_TIMEOUT\_SECONDS=...

```



Actual provider/model values should be stored in environment configuration and not committed to Git.



\---



\# 8. LLM Failure Handling



Possible failures:



\* Timeout

\* Rate limit

\* Invalid request

\* Provider outage

\* Context too large

\* Authentication failure

\* Malformed response



Handling:



```text id="x7nmyj"

Request

&#x20; |

&#x20; +-- Success → Continue

&#x20; |

&#x20; +-- Timeout → Retry if safe

&#x20; |

&#x20; +-- Rate limit → Backoff/retry if appropriate

&#x20; |

&#x20; +-- Invalid request → Fail safely

&#x20; |

&#x20; +-- Provider outage → Safe fallback/error

```



The system must not endlessly retry.



\---



\# 9. LLM Security



The backend must control:



\* System prompt

\* Tool definitions

\* Tool permissions

\* Business context

\* Retrieved knowledge

\* Conversation context



Customer messages must never be allowed to redefine system instructions.



\---



\# 10. Embedding Integration



Embeddings are used by the RAG system.



Architecture:



```text id="v7yp2k"

EmbeddingProvider

&#x20;      |

&#x20;      +── LocalEmbeddingProvider

&#x20;      |

&#x20;      +── FutureProvider

```



The RAG service depends on the interface.



The database stores the resulting vectors.



\---



\# 11. Embedding Provider Responsibilities



The embedding provider must:



\* Accept text.

\* Return vectors.

\* Validate output dimensions.

\* Handle provider/model errors.

\* Support batch processing where practical.



The provider must not:



\* Store business knowledge independently without approval.

\* Bypass tenant controls.

\* Modify database records directly.



\---



\# 12. Embedding Model Changes



Changing embedding models can change vector dimensions and retrieval behavior.



Therefore, model changes require:



1\. Architecture review.

2\. Retrieval benchmark.

3\. Database compatibility check.

4\. Re-embedding plan.

5\. Migration/testing plan.



Antigravity must not change the embedding model casually.



\---



\# 13. Deepgram STT Integration



Deepgram is the approved speech-to-text integration for the voice architecture.



Flow:



```text id="7ypr1p"

Browser Microphone

&#x20;      |

&#x20;      v

WebSocket

&#x20;      |

&#x20;      v

Voice Service

&#x20;      |

&#x20;      v

Deepgram STT

&#x20;      |

&#x20;      v

Transcript

&#x20;      |

&#x20;      v

Orchestrator

```



The voice service owns the lifecycle.



\---



\# 14. Deepgram Responsibilities



Deepgram integration handles:



\* Audio streaming

\* Speech recognition

\* Interim transcripts where supported

\* Final transcripts

\* Connection lifecycle

\* Provider errors



The core voice system should receive normalized transcript events rather than provider-specific payloads.



\---



\# 15. STT Provider Interface



Recommended conceptual interface:



```python id="zn9x9d"

class STTProvider:

&#x20;   async def connect(self, config):

&#x20;       ...



&#x20;   async def send\_audio(self, audio):

&#x20;       ...



&#x20;   async def receive\_transcript(self):

&#x20;       ...



&#x20;   async def close(self):

&#x20;       ...

```



The actual implementation may differ.



\---



\# 16. STT Audio Flow



```text id="i3u0v5"

Browser

&#x20; |

&#x20; | audio frames

&#x20; v

FastAPI WebSocket

&#x20; |

&#x20; v

Voice Service

&#x20; |

&#x20; v

Deepgram

&#x20; |

&#x20; v

Transcript events

```



The browser must not receive Deepgram credentials.



\---



\# 17. STT Failure Handling



If STT fails:



```text id="a8l6o9"

Voice session

&#x20;    |

&#x20;    v

STT failure

&#x20;    |

&#x20;    +── Retry/reconnect if safe

&#x20;    |

&#x20;    +── Notify voice session

&#x20;    |

&#x20;    +── End gracefully if recovery fails

```



The system should avoid silently losing the conversation.



\---



\# 18. ElevenLabs TTS Integration



ElevenLabs is the approved text-to-speech integration.



Flow:



```text id="xg0i3n"

Agent Response

&#x20;     |

&#x20;     v

Voice Service

&#x20;     |

&#x20;     v

ElevenLabs TTS

&#x20;     |

&#x20;     v

Audio

&#x20;     |

&#x20;     v

Browser

```



\---



\# 19. TTS Provider Interface



Recommended:



```python id="8b7bml"

class TTSProvider:

&#x20;   async def synthesize(

&#x20;       self,

&#x20;       text,

&#x20;       voice\_id,

&#x20;       language=None

&#x20;   ):

&#x20;       ...

```



The core application must not depend directly on ElevenLabs SDK objects.



\---



\# 20. Voice Configuration



Business-specific voice configuration may include:



```text id="uhqztr"

voice\_id

tone

language\_priority

greeting

```



The backend must validate configured voice IDs.



The frontend must not be allowed to choose arbitrary provider resources without backend validation.



\---



\# 21. Voice Language Handling



AgentDesk supports:



```text id="c8c5i6"

English

Urdu

Mixed Urdu-English

```



The voice pipeline is:



```text id="q0x50j"

Audio

&#x20;↓

STT

&#x20;↓

Language Detection

&#x20;↓

Orchestrator

&#x20;↓

Agent Response

&#x20;↓

TTS

```



Provider/model capabilities must be tested for the actual languages used by the project.



\---



\# 22. Voice FYP Scope



The FYP uses:



```text id="3mksv9"

Browser Voice Simulator

```



The architecture must remain compatible with future telephony.



Actual live telephone calling is outside the current FYP implementation scope.



\---



\# 23. WhatsApp Business Cloud API



WhatsApp is the primary external messaging integration.



Architecture:



```text id="gqv36k"

WhatsApp

&#x20;   |

&#x20;   v

Webhook

&#x20;   |

&#x20;   v

FastAPI

&#x20;   |

&#x20;   v

Webhook Verification

&#x20;   |

&#x20;   v

Tenant Resolution

&#x20;   |

&#x20;   v

Conversation

&#x20;   |

&#x20;   v

Orchestrator

&#x20;   |

&#x20;   v

Agent

&#x20;   |

&#x20;   v

WhatsApp Send API

```



Only official WhatsApp Business Cloud API integration is part of the approved architecture.



\---



\# 24. WhatsApp Webhook



The backend exposes a public HTTPS webhook endpoint.



Conceptually:



```text id="qj7v6w"

GET  /api/v1/webhooks/whatsapp

POST /api/v1/webhooks/whatsapp

```



The exact endpoint path must follow `05\_API\_DESIGN.md`.



\---



\# 25. WhatsApp Webhook Verification



Webhook requests must be verified.



The system must validate the required verification mechanism/signature according to the official WhatsApp integration configuration.



Unverified requests must not create conversations or messages.



\---



\# 26. WhatsApp Idempotency



Webhook providers may deliver events more than once.



AgentDesk must prevent duplicate processing.



Use a webhook event identifier where available.



Conceptual flow:



```text id="e50x1p"

Webhook Event

&#x20;     |

&#x20;     v

Check event ID

&#x20;     |

&#x20;     +── Already processed → Ignore safely

&#x20;     |

&#x20;     +── New → Process

```



\---



\# 27. WhatsApp Tenant Resolution



A WhatsApp message must resolve to the correct business using the verified integration configuration.



The system must not trust arbitrary:



```text id="qwdlhy"

business\_id

```



provided by a customer or browser.



\---



\# 28. WhatsApp Message Flow



```text id="zqv4e6"

Customer

&#x20;  |

&#x20;  v

WhatsApp

&#x20;  |

&#x20;  v

Webhook

&#x20;  |

&#x20;  v

Validate + Deduplicate

&#x20;  |

&#x20;  v

Business Resolution

&#x20;  |

&#x20;  v

Conversation Creation/Lookup

&#x20;  |

&#x20;  v

Orchestrator

&#x20;  |

&#x20;  +── RAG

&#x20;  +── Lead Agent

&#x20;  +── Booking

&#x20;  |

&#x20;  v

Response

&#x20;  |

&#x20;  v

WhatsApp API

```



\---



\# 29. WhatsApp Sending



The WhatsApp adapter should provide a normalized method such as:



```python id="zcln8c"

class MessagingProvider:

&#x20;   async def send\_text(

&#x20;       self,

&#x20;       recipient,

&#x20;       message

&#x20;   ):

&#x20;       ...

```



Provider-specific request formatting remains inside the adapter.



\---



\# 30. WhatsApp Failure Handling



Possible failures:



\* Invalid recipient

\* Expired/invalid token

\* Rate limit

\* Provider outage

\* Network timeout

\* Invalid message format



The application should:



\* Record failure.

\* Retry only safe operations.

\* Avoid duplicate messages.

\* Preserve conversation state.

\* Provide a useful internal error status.



\---



\# 31. Google Calendar Integration



Google Calendar is used for appointment booking.



Capabilities:



\* Read availability.

\* Create event.

\* Reschedule event.

\* Cancel event.

\* Store Google event ID.

\* Associate appointments with businesses.



\---



\# 32. Google OAuth



Business owners connect their Google account through OAuth.



Flow:



```text id="i7xv4q"

Owner

&#x20; |

&#x20; v

AgentDesk

&#x20; |

&#x20; v

Google OAuth

&#x20; |

&#x20; v

Authorization

&#x20; |

&#x20; v

Authorization Code

&#x20; |

&#x20; v

Backend

&#x20; |

&#x20; v

Tokens

```



The frontend must not permanently store Google refresh tokens.



\---



\# 33. Google Refresh Token Security



Refresh tokens are sensitive credentials.



They must be:



\* Stored only on the backend.

\* Encrypted at rest.

\* Excluded from logs.

\* Excluded from API responses.

\* Excluded from Git.

\* Rotated/revoked appropriately.



\---



\# 34. Calendar Provider Interface



Recommended:



```python id="8x9i0e"

class CalendarProvider:

&#x20;   async def get\_availability(...):

&#x20;       ...



&#x20;   async def create\_event(...):

&#x20;       ...



&#x20;   async def update\_event(...):

&#x20;       ...



&#x20;   async def cancel\_event(...):

&#x20;       ...

```



The booking service depends on this interface.



\---



\# 35. Appointment Booking Flow



```text id="f0unl7"

Customer

&#x20;  |

&#x20;  v

"Book appointment"

&#x20;  |

&#x20;  v

Orchestrator

&#x20;  |

&#x20;  v

Booking Tool

&#x20;  |

&#x20;  v

Calendar Availability

&#x20;  |

&#x20;  v

Available Slots

&#x20;  |

&#x20;  v

Customer Selects Slot

&#x20;  |

&#x20;  v

Confirmation

&#x20;  |

&#x20;  v

Create Google Event

&#x20;  |

&#x20;  v

Store Appointment

```



The backend must validate all appointment details.



\---



\# 36. Double-Booking Protection



The system must re-check availability immediately before creating an appointment.



Example:



```text id="yrq4gk"

Check availability

&#x20;     ↓

Customer confirms

&#x20;     ↓

Re-check availability

&#x20;     ↓

Create event

```



A slot that became unavailable must not be booked based on stale information.



\---



\# 37. Calendar Failure Handling



Possible failures:



\* Token expired

\* Permission revoked

\* Calendar unavailable

\* Slot unavailable

\* Google API timeout

\* Invalid event



The system should provide a safe user-facing response.



Example:



```text id="h9qgq4"

Sorry, I couldn't complete the booking right now.

Please try again.

```



Internal logs should contain the diagnostic context without exposing credentials.



\---



\# 38. Calendar Time Zones



Appointment times must be timezone-aware.



The business configuration should define the business timezone.



For Pakistan-based FYP testing, the expected timezone may be:



```text id="xj99m0"

Asia/Karachi

```



The system must not rely on the server's local timezone.



All persisted timestamps should use a consistent timezone-aware strategy.



\---



\# 39. Business Hours



Calendar availability must respect configured business hours where applicable.



Example:



```text id="zv9jgz"

Business:

Monday–Saturday

09:00–20:00

```



The booking service should avoid offering slots outside configured hours unless explicitly allowed by the business configuration.



\---



\# 40. Email Integration



Email may be used for:



\* Owner alerts

\* New lead notifications

\* Appointment notifications

\* System notifications



The email provider must also be abstracted.



Recommended:



```python id="5hjjlj"

class EmailProvider:

&#x20;   async def send(

&#x20;       self,

&#x20;       recipient,

&#x20;       subject,

&#x20;       body

&#x20;   ):

&#x20;       ...

```



\---



\# 41. Email Provider Configuration



Example:



```text id="f7twlr"

EMAIL\_PROVIDER=...

EMAIL\_API\_KEY=...

EMAIL\_FROM=...

```



Credentials must remain server-side.



\---



\# 42. Lead Notification Flow



```text id="z1b8q7"

Customer Conversation

&#x20;       |

&#x20;       v

Lead Agent

&#x20;       |

&#x20;       v

Lead Created

&#x20;       |

&#x20;       v

Owner Notification Job

&#x20;       |

&#x20;       v

Email Provider

```



The lead record must be persisted even if email delivery fails.



Notification failure must not undo lead creation.



\---



\# 43. S3-Compatible Object Storage



Object storage is used for:



\* PDF files

\* DOCX files

\* Other approved file artifacts

\* Potential voice-related temporary artifacts



The application must not assume a local filesystem in production.



\---



\# 44. Storage Provider Interface



Recommended:



```python id="2k1b4r"

class StorageProvider:

&#x20;   async def upload(...):

&#x20;       ...



&#x20;   async def download(...):

&#x20;       ...



&#x20;   async def delete(...):

&#x20;       ...



&#x20;   async def generate\_signed\_url(...):

&#x20;       ...

```



Provider-specific implementation remains isolated.



\---



\# 45. Storage Security



Storage objects must not be publicly accessible by default.



Use:



\* Private buckets

\* Authorized backend access

\* Short-lived signed URLs where required

\* Safe object keys

\* Tenant-scoped paths



Example:



```text id="r4j0xk"

business/{business\_id}/knowledge/{file\_id}

```



\---



\# 46. Storage Object Naming



Never use the raw customer filename directly as a storage key.



Instead use controlled identifiers.



Example:



```text id="c8sj9x"

business/<business\_id>/knowledge/<file\_id>/original.pdf

```



This reduces:



\* Path traversal risk

\* Naming conflicts

\* Unsafe filenames



\---



\# 47. PostgreSQL Integration



PostgreSQL is the primary application database.



It stores:



\* Owners

\* Businesses

\* Agent configuration

\* Knowledge metadata

\* Knowledge vectors

\* Conversations

\* Messages

\* Leads

\* Appointments

\* Analytics



PostgreSQL + pgvector is the approved database architecture.



\---



\# 48. PostgreSQL Access



Application code should use:



```text id="t6c9r7"

FastAPI

&#x20;↓

Service

&#x20;↓

Repository

&#x20;↓

SQLAlchemy

&#x20;↓

PostgreSQL

```



Core application code must not scatter raw database connections throughout the project.



\---



\# 49. Redis Integration



Redis may be used for:



\* Background jobs

\* Temporary state

\* Caching

\* Active voice session state

\* Rate limiting

\* Short-lived locks where necessary



Redis must not become the permanent source of truth for business data.



Persistent business data belongs in PostgreSQL.



\---



\# 50. Background Jobs



Integration-related asynchronous work includes:



```text id="hlf5iy"

Document processing

Embedding generation

Email notifications

Webhook processing

Retry jobs

Analytics snapshots

Cleanup tasks

```



Architecture:



```text id="0y8f6v"

FastAPI

&#x20;  |

&#x20;  v

Queue

&#x20;  |

&#x20;  v

Worker

&#x20;  |

&#x20;  +── External Provider

```



\---



\# 51. External Provider Timeouts



Every network integration should use explicit timeouts.



Never allow an external API request to hang indefinitely.



Example conceptual configuration:



```text id="8z2y7u"

connect\_timeout

read\_timeout

total\_timeout

```



Actual values must be selected according to provider behavior and performance targets.



\---



\# 52. Retry Rules



Retries must be selective.



Safe candidates may include:



\* Temporary network failures

\* 5xx provider errors

\* Temporary connection errors



Do not automatically retry:



\* Invalid credentials

\* Invalid request payload

\* Invalid recipient

\* Unauthorized request

\* Permanent validation failures



\---



\# 53. Exponential Backoff



Retryable operations should use bounded exponential backoff where appropriate.



Example:



```text id="6n5l1z"

Attempt 1

&#x20;  ↓

short delay

&#x20;  ↓

Attempt 2

&#x20;  ↓

longer delay

&#x20;  ↓

Attempt 3

&#x20;  ↓

Failure

```



Maximum attempts must be limited.



\---



\# 54. Rate Limits



External providers may impose rate limits.



AgentDesk should:



\* Detect rate-limit responses.

\* Respect provider retry information where available.

\* Apply application-level rate limits.

\* Avoid retry storms.

\* Queue non-urgent work where practical.



\---



\# 55. Circuit-Breaker/Fallback Strategy



A full circuit-breaker system is optional for the FYP.



However, the architecture should allow provider failures to be isolated.



For example:



```text id="q8n6qg"

ElevenLabs unavailable

&#x20;      ↓

Voice response fails safely

```



This must not cause:



```text id="xq2mkw"

Database corruption

```



or:



```text id="a2xg7s"

Other channels to fail unnecessarily

```



\---



\# 56. Integration Error Model



External provider errors should be normalized.



Conceptually:



```python id="w6h1g3"

class IntegrationError:

&#x20;   provider: str

&#x20;   code: str

&#x20;   retryable: bool

&#x20;   message: str

```



The user-facing message should not expose:



\* API keys

\* Internal URLs

\* Stack traces

\* Provider credentials

\* Sensitive request data



\---



\# 57. Integration Logging



Logs should capture useful metadata such as:



```text id="nq5z8h"

provider

operation

duration

status

retry\_count

error\_code

business\_id

request/correlation ID

```



Avoid logging:



\* API keys

\* OAuth refresh tokens

\* Passwords

\* Full authorization headers

\* Unnecessary customer message content



\---



\# 58. Correlation IDs



External requests should be traceable through a correlation/request ID.



Example:



```text id="d70a0w"

Request ID:

req\_12345

```



The same ID can be associated with:



```text id="4f4q3r"

API request

→ service

→ provider call

→ error/log

```



This helps debugging.



\---



\# 59. Secret Management



Secrets belong in environment configuration or an approved secret manager.



Examples:



```text id="5i7xsc"

DATABASE\_URL

REDIS\_URL

LLM\_API\_KEY

DEEPGRAM\_API\_KEY

ELEVENLABS\_API\_KEY

WHATSAPP\_ACCESS\_TOKEN

WHATSAPP\_VERIFY\_TOKEN

GOOGLE\_CLIENT\_ID

GOOGLE\_CLIENT\_SECRET

EMAIL\_API\_KEY

S3\_ACCESS\_KEY

S3\_SECRET\_KEY

```



These must never be committed to Git.



\---



\# 60. `.env.example`



The repository should include:



```text id="2d9y0d"

.env.example

```



It may contain:



```text

LLM\_API\_KEY=

DEEPGRAM\_API\_KEY=

ELEVENLABS\_API\_KEY=

WHATSAPP\_ACCESS\_TOKEN=

```



but never real credentials.



\---



\# 61. Frontend Security



The frontend may receive:



```text id="l9r7m2"

public configuration

```



but must never receive:



\* LLM API keys

\* Deepgram secret keys

\* ElevenLabs API keys

\* WhatsApp access tokens

\* Google refresh tokens

\* S3 secret credentials

\* Database credentials



\---



\# 62. OAuth Security



OAuth flows must:



\* Validate state.

\* Validate redirect URI.

\* Use HTTPS in production.

\* Store sensitive tokens server-side.

\* Encrypt refresh tokens.

\* Handle revoked access.

\* Avoid exposing tokens in URLs/logs.



\---



\# 63. Webhook Security



All public webhooks must:



\* Validate provider requirements.

\* Verify signatures/tokens.

\* Validate payload structure.

\* Apply idempotency.

\* Avoid trusting arbitrary tenant IDs.

\* Return appropriate HTTP status codes.

\* Avoid expensive processing directly in the request when background processing is appropriate.



\---



\# 64. Webhook Processing Architecture



Preferred:



```text id="t30u4s"

Webhook Request

&#x20;     |

&#x20;     v

Verify

&#x20;     |

&#x20;     v

Validate

&#x20;     |

&#x20;     v

Deduplicate

&#x20;     |

&#x20;     v

Persist Event

&#x20;     |

&#x20;     v

Queue Job

&#x20;     |

&#x20;     v

Worker

```



This improves reliability.



\---



\# 65. Integration Health



The dashboard or admin tooling may eventually expose integration status.



Example:



```text id="h4n0v1"

Google Calendar

Connected



WhatsApp

Connected



Knowledge Embeddings

Ready



Voice Services

Configured

```



The FYP may implement a simplified version.



\---



\# 66. Integration Configuration Ownership



Business integrations belong to the relevant business.



Example:



```text id="u8q9tm"

Business A

&#x20;├── Google Calendar A

&#x20;├── WhatsApp A

&#x20;└── Agent configuration A



Business B

&#x20;├── Google Calendar B

&#x20;├── WhatsApp B

&#x20;└── Agent configuration B

```



Integration credentials must never be reused across businesses unless explicitly designed as platform-level credentials.



\---



\# 67. Provider Adapters



Suggested structure:



```text id="l2n6x9"

backend/app/providers/



├── llm/

│   ├── base.py

│   └── ...

├── embeddings/

│   ├── base.py

│   └── ...

├── stt/

│   ├── base.py

│   └── deepgram.py

├── tts/

│   ├── base.py

│   └── elevenlabs.py

├── calendar/

│   ├── base.py

│   └── google.py

├── messaging/

│   ├── base.py

│   └── whatsapp.py

├── email/

│   ├── base.py

│   └── ...

└── storage/

&#x20;   ├── base.py

&#x20;   └── s3.py

```



Exact filenames may be adjusted while preserving the architectural boundary.



\---



\# 68. Dependency Direction



Approved dependency direction:



```text id="7j1lpn"

API

&#x20;↓

Application Services

&#x20;↓

Provider Interfaces

&#x20;↓

Provider Adapters

&#x20;↓

External APIs

```



The reverse dependency is prohibited.



Provider adapters must not control core application logic.



\---



\# 69. Provider Swapping



The architecture should allow:



```text id="e1xq4p"

Deepgram

&#x20;  ↓

Another STT provider

```



without rewriting:



```text id="k31q2r"

Orchestrator

```



Likewise:



```text id="9v1v2j"

ElevenLabs

&#x20;  ↓

Another TTS provider

```



should not require changing the agent architecture.



\---



\# 70. Provider Configuration vs Business Configuration



Provider credentials are platform configuration.



Business configuration is tenant data.



Example:



```text id="e8h9x1"

Platform:

DEEPGRAM\_API\_KEY



Business:

voice\_id

tone

greeting

language\_priority

```



Do not mix these responsibilities.



\---



\# 71. Integration Data Flow



The general rule is:



```text id="wq8x5m"

External Provider

&#x20;      ↓

Adapter

&#x20;      ↓

Normalized Result

&#x20;      ↓

Application Service

&#x20;      ↓

Domain/Application Logic

```



Not:



```text id="9k8s0m"

External Provider

&#x20;      ↓

Database directly

```



\---



\# 72. Integration Testing



Each integration should have tests.



\## LLM



Test:



\* Normal generation

\* Tool calls

\* Invalid responses

\* Timeout

\* Rate limit



\## Embeddings



Test:



\* Vector generation

\* Correct dimensions

\* Failure

\* Batch processing



\## Deepgram



Test:



\* Connection

\* Transcript events

\* Disconnect

\* Failure



\## ElevenLabs



Test:



\* TTS request

\* Audio response

\* Failure



\## WhatsApp



Test:



\* Webhook verification

\* Event processing

\* Duplicate event

\* Message sending

\* Invalid payload



\## Google Calendar



Test:



\* OAuth

\* Availability

\* Create event

\* Update event

\* Cancel event

\* Expired token

\* Conflict



\---



\# 73. Mocking External Services



Automated tests should not depend on live paid/external services wherever possible.



Use mocks/fakes for:



```text id="5m1c6w"

LLM

STT

TTS

WhatsApp

Google Calendar

Email

Storage

```



Integration tests may use sandbox/test environments where available.



\---



\# 74. External Integration Contract Tests



Provider adapters should be tested against expected normalized interfaces.



Example:



```text id="y5c0rq"

WhatsApp Adapter

&#x20;      ↓

MessagingProvider contract

```



The rest of the application should receive the same conceptual result regardless of provider implementation.



\---



\# 75. Security Testing



Mandatory integration security tests include:



\* Invalid webhook signature.

\* Forged webhook.

\* Unauthorized OAuth callback.

\* Token leakage prevention.

\* Cross-tenant integration access.

\* Unauthorized calendar modification.

\* Unauthorized message sending.

\* Secret exposure through API responses.



\---



\# 76. Performance Testing



Measure:



```text id="d2d4jq"

LLM latency

Embedding latency

STT latency

TTS latency

WhatsApp API latency

Calendar API latency

Storage latency

```



These measurements help identify bottlenecks.



\---



\# 77. Failure Isolation



One integration failure should not unnecessarily break unrelated functionality.



Example:



```text id="f90z3r"

Google Calendar unavailable

```



should not prevent:



```text id="1f8l8w"

FAQ chat

```



from working.



Similarly:



```text id="t5x5qb"

ElevenLabs unavailable

```



should not corrupt conversation persistence.



\---



\# 78. FYP Cost-Control Strategy



The FYP should prioritize low-cost development.



Use:



\* Local embeddings where practical.

\* Free/test tiers where legitimately available.

\* Provider abstractions.

\* Mock services during development.

\* Local Docker services.

\* Limited AI calls during testing.

\* Small representative datasets.



Do not design the system around assumptions of unlimited free API usage.



\---



\# 79. Development Environments



\### Local



```text id="2tx4o3"

Frontend

Next.js



Backend

FastAPI



Database

PostgreSQL + pgvector



Cache/Queue

Redis



Storage

S3-compatible/local development adapter

```



External providers may be mocked.



\---



\### Staging



Use:



```text id="y9v2wv"

Separate credentials

Separate database

Separate storage

Separate integrations

```



Never use production secrets for local development.



\---



\### Production/Demo



Use:



```text id="2i2s8k"

HTTPS

Production secrets

Managed PostgreSQL

Redis

Object storage

Configured external providers

```



\---



\# 80. Integration Environment Variables



The application should centralize configuration.



Example conceptual grouping:



```text id="q2b2v7"

\# Database

DATABASE\_URL=



\# Redis

REDIS\_URL=



\# LLM

LLM\_PROVIDER=

LLM\_MODEL=

LLM\_API\_KEY=



\# Embeddings

EMBEDDING\_PROVIDER=

EMBEDDING\_MODEL=



\# STT

DEEPGRAM\_API\_KEY=



\# TTS

ELEVENLABS\_API\_KEY=



\# WhatsApp

WHATSAPP\_ACCESS\_TOKEN=

WHATSAPP\_VERIFY\_TOKEN=

WHATSAPP\_PHONE\_NUMBER\_ID=



\# Google

GOOGLE\_CLIENT\_ID=

GOOGLE\_CLIENT\_SECRET=

GOOGLE\_REDIRECT\_URI=



\# Email

EMAIL\_PROVIDER=

EMAIL\_API\_KEY=

EMAIL\_FROM=



\# Storage

S3\_ENDPOINT=

S3\_BUCKET=

S3\_ACCESS\_KEY=

S3\_SECRET\_KEY=

```



Actual variables may be renamed to match implementation conventions.



\---



\# 81. Integration Documentation



For every provider, the project should document:



\* Purpose

\* Credentials required

\* Environment variables

\* API endpoint requirements

\* Authentication

\* Request/response normalization

\* Timeouts

\* Retry behavior

\* Failure behavior

\* Testing strategy



Provider-specific implementation details should live close to the adapter or supporting documentation.



\---



\# 82. Integration Change Policy



Changing an external provider requires review.



Examples:



```text id="u1h0e5"

Deepgram → another STT

ElevenLabs → another TTS

Provider A → Provider B for LLM

Google Calendar → another calendar service

```



Before changing:



1\. Confirm requirement.

2\. Check architecture impact.

3\. Update provider interface if required.

4\. Update integration documentation.

5\. Update environment configuration.

6\. Update tests.

7\. Run regression tests.



\---



\# 83. Antigravity Rules



Antigravity must:



\* Read `09\_INTEGRATIONS.md` before implementing integrations.

\* Use provider interfaces.

\* Keep credentials server-side.

\* Never commit secrets.

\* Never expose API keys to frontend code.

\* Validate provider responses.

\* Implement bounded retries.

\* Implement timeouts.

\* Preserve idempotency.

\* Verify webhooks.

\* Preserve tenant isolation.

\* Avoid provider-specific code in domain services.

\* Write tests for integration boundaries.

\* Make minimal changes.

\* Avoid replacing approved providers without permission.



\---



\# 84. Prohibited Integration Patterns



Do not implement:



```text id="q9xj5d"

Frontend → Deepgram directly using secret API key

```



```text id="g4g5z0"

Frontend → ElevenLabs using secret API key

```



```text id="5w4w4r"

LLM → PostgreSQL directly

```



```text id="l4v0v7"

Webhook → database mutation without verification

```



```text id="4ks8x7"

LLM → Google Calendar directly

```



```text id="7j3zj6"

Provider SDK calls scattered across every service

```



\---



\# 85. Final Integration Architecture



The approved architecture is:



```text id="d3y4w0"

&#x20;                        AgentDesk

&#x20;                           |

&#x20;             ┌─────────────┴─────────────┐

&#x20;             |                           |

&#x20;       Application Core             Background Worker

&#x20;             |                           |

&#x20;             v                           v

&#x20;      Provider Interfaces          Provider Interfaces

&#x20;             |                           |

&#x20;   ┌─────────┼──────────┐       ┌────────┼─────────┐

&#x20;   |         |          |       |        |         |

&#x20;   v         v          v       v        v         v

&#x20;  LLM     Embedding    STT     TTS    Calendar   Messaging

&#x20;   |         |          |       |        |         |

&#x20;   v         v          v       v        v         v

&#x20;Provider  Provider   Deepgram ElevenLabs Google   WhatsApp

&#x20;                                           Calendar

```



Supporting infrastructure:



```text id="9k2h0m"

&#x20;                 AgentDesk

&#x20;                    |

&#x20;       ┌────────────┼────────────┐

&#x20;       v            v            v

&#x20;  PostgreSQL      Redis       S3 Storage

&#x20;  + pgvector

```



\---



\# 86. Final Integration Principles



AgentDesk integrations must follow these core rules:



```text id="f5g6l4"

1\. Core application logic must not depend directly on provider SDKs.



2\. Provider-specific implementations belong behind adapters.



3\. Secrets remain server-side.



4\. External responses must be validated.



5\. Network calls require timeouts.



6\. Retry only operations that are safe to retry.



7\. Webhooks require verification and idempotency.



8\. Google refresh tokens must be protected.



9\. Tenant/business authorization applies to integrations.



10\. External failures must be isolated.



11\. Tests must cover integration boundaries.



12\. Provider changes require controlled architectural review.

```



\---



\# 87. Definition of Done



The integration layer is considered complete when:



\* \[ ] LLM provider interface exists.

\* \[ ] Embedding provider interface exists.

\* \[ ] STT provider interface exists.

\* \[ ] TTS provider interface exists.

\* \[ ] Calendar provider interface exists.

\* \[ ] Messaging provider interface exists.

\* \[ ] Email provider interface exists.

\* \[ ] Storage provider interface exists.

\* \[ ] Provider credentials are server-side.

\* \[ ] `.env.example` exists.

\* \[ ] No secrets are committed.

\* \[ ] WhatsApp webhook verification exists.

\* \[ ] WhatsApp idempotency exists.

\* \[ ] Google OAuth is securely implemented.

\* \[ ] Google refresh tokens are encrypted.

\* \[ ] Calendar double-booking protection exists.

\* \[ ] External requests have timeouts.

\* \[ ] Retry behavior is bounded.

\* \[ ] Provider failures are normalized.

\* \[ ] Integration tests exist.

\* \[ ] Tenant isolation is tested.

\* \[ ] FYP providers can be mocked.

\* \[ ] Documentation matches implementation.



\---



\# 88. Final Architecture Baseline



The approved AgentDesk external integration model is:



```text id="r0p9me"

&#x20;                   AgentDesk Core

&#x20;                        |

&#x20;                Stable Interfaces

&#x20;                        |

&#x20;         ┌──────────────┼──────────────┐

&#x20;         |              |              |

&#x20;      AI Stack       Business APIs   Storage

&#x20;         |              |              |

&#x20;   ┌─────┼─────┐     ┌──┼───┐          |

&#x20;   v     v     v     v      v          v

&#x20;  LLM   STT   TTS  WhatsApp Calendar   S3

&#x20;   |

&#x20;Embeddings

```



External providers are replaceable implementation details.



The AgentDesk core architecture remains stable.



\*\*This document is the approved external integration baseline for AgentDesk.\*\*



