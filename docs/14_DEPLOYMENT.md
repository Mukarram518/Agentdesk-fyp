\# AgentDesk — Deployment Architecture \& Strategy



\## 1. Purpose



This document defines the official deployment strategy for AgentDesk.



It covers:



\* local development

\* testing/staging

\* production deployment

\* frontend deployment

\* backend deployment

\* PostgreSQL + pgvector

\* Redis

\* background workers

\* object storage

\* external integrations

\* environment variables

\* secrets

\* Docker

\* database migrations

\* HTTPS

\* monitoring

\* logging

\* backups

\* recovery

\* deployment verification

\* FYP demonstration deployment



The deployment architecture must remain consistent with the approved system architecture.



\---



\# 2. Deployment Principles



AgentDesk deployment follows these principles:



1\. Development, staging, and production environments are separated.

2\. Secrets are never committed to Git.

3\. Production uses HTTPS.

4\. Database migrations are version-controlled.

5\. PostgreSQL + pgvector is the approved database.

6\. Redis is used for cache/session/background-job requirements where required.

7\. Background jobs run independently from HTTP request handling.

8\. External providers are accessed through provider adapters.

9\. Production configuration must be environment-based.

10\. Deployments must be reproducible.

11\. Health checks must exist for important services.

12\. Database backups must be available for production/staging where supported.

13\. Deployment failures must not silently leave the system in an unknown state.

14\. FYP deployment should minimize unnecessary cost while preserving the approved architecture.



\---



\# 3. Deployment Environments



AgentDesk uses three primary environments:



```text

Development

&#x20;    ↓

Staging / Test

&#x20;    ↓

Production

```



\## Development



Used by developers for:



\* coding

\* local testing

\* debugging

\* database migrations

\* provider mocking

\* feature development



\## Staging



Used for:



\* integration testing

\* deployment testing

\* external provider testing

\* end-to-end testing

\* final FYP validation



\## Production



Used for:



\* live application

\* final FYP demonstration if required

\* real configured business environment



\---



\# 4. Local Development Architecture



The local environment should run the core infrastructure through Docker where practical.



Recommended topology:



```text

Developer Machine

│

├── Frontend

│   └── Next.js

│

├── Backend

│   └── FastAPI

│

├── PostgreSQL

│   └── pgvector

│

├── Redis

│

└── Worker

```



External services can be:



\* mocked

\* sandboxed

\* development credentials

\* real development credentials where appropriate



Production credentials must never be used locally unless explicitly required and securely managed.



\---



\# 5. Docker Compose



The local development environment should be represented by:



```text

docker-compose.yml

```



Core services:



```text

frontend

backend

postgres

redis

worker

```



Not every service must necessarily run inside Docker during active frontend development, but the infrastructure should remain reproducible.



\---



\# 6. Local Service Flow



```text

Browser

&#x20;  │

&#x20;  ▼

Next.js

&#x20;  │

&#x20;  ▼

FastAPI

&#x20;  │

&#x20;  ├───────────────┐

&#x20;  ▼               ▼

PostgreSQL       Redis

&#x20;  │               │

&#x20;  │               ▼

&#x20;  │             Worker

&#x20;  │

&#x20;  ▼

pgvector

```



External services:



```text

FastAPI / Worker

&#x20;      │

&#x20;      ├── LLM

&#x20;      ├── Deepgram

&#x20;      ├── ElevenLabs

&#x20;      ├── Google Calendar

&#x20;      ├── WhatsApp

&#x20;      └── S3-compatible storage

```



\---



\# 7. Frontend Deployment



The approved frontend architecture uses Next.js.



The frontend should be deployed to a managed platform capable of running the selected Next.js application.



The target deployment may use:



```text

Vercel

```



or another approved equivalent.



The exact provider can be selected based on:



\* cost

\* availability

\* Next.js compatibility

\* deployment simplicity

\* FYP requirements



Changing the hosting provider does not change the application architecture.



\---



\# 8. Frontend Production Configuration



The frontend must receive only variables that are safe for browser exposure.



Public configuration may include:



```text

NEXT\_PUBLIC\_API\_URL

NEXT\_PUBLIC\_APP\_URL

```



Private secrets must never be exposed through `NEXT\_PUBLIC\_\*`.



Never expose:



```text

LLM\_API\_KEY

DEEPGRAM\_API\_KEY

ELEVENLABS\_API\_KEY

WHATSAPP\_ACCESS\_TOKEN

GOOGLE\_CLIENT\_SECRET

DATABASE\_URL

```



to browser-side JavaScript.



\---



\# 9. Backend Deployment



The backend uses:



```text

Python

FastAPI

```



The backend should run as a dedicated service.



Possible deployment platforms:



\* Railway

\* Render

\* another approved container-compatible platform



The selected platform must support the required:



\* Python runtime

\* HTTP service

\* environment variables

\* HTTPS

\* background worker if required

\* database connectivity

\* Redis connectivity



\---



\# 10. Backend Production Process



The backend deployment flow is:



```text

GitHub

&#x20;  ↓

Build

&#x20;  ↓

Install Dependencies

&#x20;  ↓

Run Validation

&#x20;  ↓

Run Database Migration

&#x20;  ↓

Start FastAPI

&#x20;  ↓

Health Check

&#x20;  ↓

Ready

```



The exact CI/CD mechanism may vary.



\---



\# 11. Backend Start Command



The production backend should run the FastAPI application through an appropriate production ASGI server.



Example concept:



```text

uvicorn app.main:app

```



The final production command must use appropriate worker/process configuration for the selected deployment environment.



Do not use development reload mode in production.



\---



\# 12. PostgreSQL Deployment



The approved production database is:



```text

PostgreSQL

```



with:



```text

pgvector

```



required for vector search.



The production database should be managed using a reliable PostgreSQL hosting solution.



Possible deployment:



```text

Railway PostgreSQL

```



or another approved PostgreSQL provider.



\---



\# 13. PostgreSQL Requirements



Production PostgreSQL must support:



\* UUIDs

\* JSON/JSONB

\* transactions

\* indexes

\* foreign keys

\* pgvector

\* concurrent operations



The selected hosting service must provide a PostgreSQL version compatible with the application dependencies.



\---



\# 14. pgvector



pgvector is required for AgentDesk RAG.



The deployment must verify that the database supports the required vector extension.



Conceptual setup:



```text

PostgreSQL

&#x20;  │

&#x20;  └── pgvector

&#x20;         │

&#x20;         └── Knowledge Embeddings

```



The application must not silently fall back to an unrelated vector database without an approved architecture change.



\---



\# 15. Database Migrations



Alembic manages schema migrations.



Migration flow:



```text

Developer

&#x20;  ↓

SQLAlchemy Model Change

&#x20;  ↓

Alembic Migration

&#x20;  ↓

Test Database

&#x20;  ↓

Staging

&#x20;  ↓

Production

```



Never manually change the production schema without recording the change through the migration system.



\---



\# 16. Migration Safety



Before applying a production migration:



```text

\[ ] Migration reviewed

\[ ] Migration tested locally

\[ ] Migration tested on staging

\[ ] Backup available where appropriate

\[ ] Rollback/recovery plan understood

```



Destructive migrations require special review.



\---



\# 17. Redis Deployment



Redis is used for:



\* caching

\* temporary session/state requirements

\* active voice/session state where applicable

\* background job coordination



Redis must not become the permanent source of truth for business records.



Permanent business data belongs in PostgreSQL.



\---



\# 18. Redis Failure Behavior



If Redis becomes temporarily unavailable:



\* critical persistent business data must remain safe

\* the application should fail gracefully

\* operations that require Redis should return safe errors or use an appropriate fallback

\* the system must not silently lose important data



The exact fallback depends on the feature.



\---



\# 19. Background Worker



Long-running operations should not block normal HTTP requests.



Examples:



```text

Document processing

Embedding generation

Analytics snapshots

Notifications

Cleanup

External retry jobs

```



Architecture:



```text

FastAPI

&#x20;  │

&#x20;  ▼

Job Queue / Redis

&#x20;  │

&#x20;  ▼

Worker

&#x20;  │

&#x20;  ├── RAG processing

&#x20;  ├── Analytics

&#x20;  ├── Notifications

&#x20;  └── Cleanup

```



\---



\# 20. Worker Deployment



The worker should be deployed separately from the HTTP server when the hosting platform supports it.



Example:



```text

Backend Service

Worker Service

```



Both use:



\* same application codebase

\* compatible environment variables

\* same database

\* same Redis



They have different startup commands.



\---



\# 21. Worker Reliability



Background jobs should support:



\* retry

\* failure tracking

\* idempotency

\* appropriate timeouts

\* logging



A failed document-processing job should not silently appear as successfully processed.



\---



\# 22. Object Storage



Uploaded PDF/DOCX files and other persistent objects should use S3-compatible storage.



Possible providers include:



```text

S3-compatible storage

```



The exact provider may be selected based on:



\* cost

\* FYP limits

\* availability

\* compatibility



Application code must communicate through a storage abstraction where practical.



\---



\# 23. File Storage Security



Uploaded files must:



\* remain inaccessible to unauthorized tenants

\* use generated object identifiers

\* not expose predictable sensitive paths

\* have access controlled by backend authorization

\* be validated before processing



Do not store customer-uploaded files in the Git repository.



\---



\# 24. External Service Deployment



External services include:



```text

LLM

Embeddings

Deepgram

ElevenLabs

WhatsApp

Google Calendar

Email

S3-compatible storage

```



Each must have configuration isolated through environment variables and provider adapters.



\---



\# 25. Provider Configuration



Conceptual environment variables:



```text

LLM\_PROVIDER=

LLM\_API\_KEY=



EMBEDDING\_PROVIDER=



DEEPGRAM\_API\_KEY=



ELEVENLABS\_API\_KEY=



WHATSAPP\_ACCESS\_TOKEN=

WHATSAPP\_VERIFY\_TOKEN=

WHATSAPP\_APP\_SECRET=



GOOGLE\_CLIENT\_ID=

GOOGLE\_CLIENT\_SECRET=

GOOGLE\_REDIRECT\_URI=



S3\_ENDPOINT=

S3\_ACCESS\_KEY=

S3\_SECRET\_KEY=

S3\_BUCKET=

```



Exact names may be finalized during implementation.



\---



\# 26. Environment Variable Rules



Every environment-specific value must be externalized.



Examples:



```text

DATABASE\_URL

REDIS\_URL

APP\_ENV

APP\_URL

API\_URL

SECRET\_KEY

```



Never hardcode:



\* passwords

\* tokens

\* API keys

\* OAuth secrets

\* database URLs containing credentials



\---



\# 27. `.env.example`



The repository should contain:



```text

.env.example

```



It must contain variable names without real secrets.



Example:



```text

DATABASE\_URL=

REDIS\_URL=

SECRET\_KEY=

LLM\_API\_KEY=

```



Never commit:



```text

.env

.env.local

```



when they contain secrets.



\---



\# 28. Production Secrets



Production secrets should be stored in the hosting platform's secure environment-variable/secret management system.



Examples:



```text

Railway Variables

Render Environment Variables

Vercel Environment Variables

```



The exact platform can change.



The security requirement cannot.



\---



\# 29. Secret Rotation



The system should support replacing:



\* application secrets

\* provider API keys

\* OAuth credentials

\* webhook secrets



without changing source code.



If a secret is accidentally exposed:



1\. revoke it immediately

2\. generate a replacement

3\. update deployment configuration

4\. inspect Git history

5\. review logs where relevant



\---



\# 30. HTTPS



Production traffic must use HTTPS.



Architecture:



```text

Browser

&#x20;  │

&#x20;HTTPS

&#x20;  ▼

Frontend / API

```



WebSocket voice connections must also use secure WebSockets:



```text

wss://

```



not:



```text

ws://

```



in production.



\---



\# 31. Domain Structure



A possible production structure:



```text

app.example.com

api.example.com

```



Frontend:



```text

https://app.example.com

```



Backend:



```text

https://api.example.com

```



The actual domain names will be selected during deployment.



\---



\# 32. CORS



Production CORS must allow only approved frontend origins.



Do not use:



```text

allow\_origins=\["\*"]

```



for a credentialed production API.



Allowed origins should be environment-specific.



\---



\# 33. Cookie / Session Configuration



Production authentication cookies, if used, should use appropriate security settings such as:



```text

Secure

HttpOnly

SameSite

```



The exact configuration depends on the final authentication implementation and frontend/backend domain arrangement.



\---



\# 34. Database Connection Security



The backend must connect to PostgreSQL through a secure connection supported by the deployment provider.



Database credentials must never be included in:



\* source code

\* frontend bundles

\* logs

\* API responses

\* error messages



\---



\# 35. Deployment Health Checks



The backend should expose a health endpoint such as:



```text

GET /health

```



The health system should verify basic application availability.



A deeper readiness check may verify:



```text

API

Database

Redis

```



without exposing sensitive information.



\---



\# 36. Health Check Principles



Health endpoints must:



\* return predictable status

\* avoid exposing secrets

\* avoid expensive AI calls

\* avoid unnecessary external API calls

\* support hosting-platform health checks



\---



\# 37. Logging



Production logs should capture useful operational information.



Examples:



\* request ID

\* endpoint

\* response status

\* duration

\* background job state

\* provider failure

\* integration failure

\* security events



Do not log:



\* passwords

\* API keys

\* access tokens

\* OAuth refresh tokens

\* unnecessary sensitive customer content



\---



\# 38. Error Monitoring



Production should provide enough monitoring to identify:



\* application crashes

\* repeated API failures

\* database errors

\* worker failures

\* external provider failures

\* abnormal latency



The monitoring provider is not architecturally mandatory.



The capability is.



\---



\# 39. AI Observability



AI-related monitoring should distinguish:



```text

LLM latency

Embedding latency

RAG retrieval latency

STT latency

TTS latency

Tool execution latency

Total response latency

```



This is important because external providers can dominate user-perceived performance.



\---



\# 40. Conversation Data Logging



Conversation content is personal/business data.



Logs should not automatically duplicate full conversations.



Prefer:



```text

conversation\_id

business\_id

channel

event\_type

duration

status

```



over logging complete customer messages unnecessarily.



\---



\# 41. Database Backups



Production PostgreSQL should have an appropriate backup mechanism.



Backup requirements:



\* regular backups

\* retention policy

\* secure storage

\* restoration procedure



Backups must not be treated as complete until restoration has been tested where practical.



\---



\# 42. Backup Scope



Backups should protect important persistent data:



\* owners

\* businesses

\* agent configurations

\* knowledge metadata

\* conversations

\* messages

\* leads

\* appointments

\* analytics



Uploaded objects stored separately must have their own storage/backup strategy.



\---



\# 43. Disaster Recovery



If a major deployment failure occurs:



```text

Identify failure

&#x20;↓

Protect data

&#x20;↓

Restore infrastructure

&#x20;↓

Restore database if necessary

&#x20;↓

Run migrations

&#x20;↓

Verify integrations

&#x20;↓

Run smoke tests

&#x20;↓

Return service

```



Recovery procedures should be documented.



\---



\# 44. Data Retention



According to the approved architecture:



\* owner/business data remains until deletion

\* transcripts/leads remain until owner deletion

\* call audio is purged after 30 days



The deployment environment must support the required cleanup jobs.



\---



\# 45. Cleanup Worker



A background cleanup job should handle applicable retention policies.



Example:



```text

cleanup\_jobs.py

```



Responsibilities may include:



```text

Old call audio

Expired temporary objects

Expired session state

Other approved temporary data

```



Deletion must be carefully scoped.



\---



\# 46. Google OAuth Deployment



Google OAuth requires environment-specific configuration.



Example:



```text

Development redirect URI

Staging redirect URI

Production redirect URI

```



The deployment must use the correct callback URL for the environment.



Do not use a production callback URL during local testing unless intentionally configured.



\---



\# 47. WhatsApp Webhook Deployment



WhatsApp requires a publicly reachable HTTPS webhook.



Flow:



```text

WhatsApp

&#x20;  ↓

HTTPS

&#x20;  ↓

AgentDesk Webhook

&#x20;  ↓

Verification

&#x20;  ↓

Signature Validation

&#x20;  ↓

Idempotency

&#x20;  ↓

Message Processing

```



The webhook must not be exposed through an unsecured development URL in production.



\---



\# 48. Voice Deployment



Production voice architecture:



```text

Browser

&#x20;  │

&#x20;Secure WebSocket

&#x20;  ▼

FastAPI

&#x20;  │

&#x20;  ▼

Deepgram

&#x20;  │

&#x20;  ▼

Orchestrator

&#x20;  │

&#x20;  ▼

ElevenLabs

&#x20;  │

&#x20;  ▼

Browser

```



The FYP primarily demonstrates browser voice.



Live telephony remains outside the core FYP implementation.



\---



\# 49. Frontend Build Verification



Before frontend deployment:



```text

\[ ] Dependencies install

\[ ] TypeScript checks

\[ ] Lint passes

\[ ] Unit tests pass

\[ ] Production build succeeds

\[ ] Environment variables verified

```



\---



\# 50. Backend Build Verification



Before backend deployment:



```text

\[ ] Dependencies install

\[ ] Python tests pass

\[ ] Coverage target checked

\[ ] Migration validated

\[ ] Import/startup check passes

\[ ] Environment variables verified

\[ ] Docker build succeeds

```



\---



\# 51. Docker Image Rules



Production images should:



\* use a suitable base image

\* avoid unnecessary packages

\* avoid secrets

\* run as a non-root user where practical

\* expose only required ports

\* use deterministic dependency installation where practical



\---



\# 52. Dockerfile Separation



Frontend and backend may have separate Dockerfiles.



Example:



```text

frontend/Dockerfile

backend/Dockerfile

```



Do not combine unrelated application environments into one giant image.



\---



\# 53. CI/CD



A basic CI/CD flow may be:



```text

Git Push

&#x20;  ↓

CI

&#x20;  ├── Lint

&#x20;  ├── Type Check

&#x20;  ├── Unit Tests

&#x20;  ├── Integration Tests

&#x20;  └── Build

&#x20;  ↓

Deployment

&#x20;  ↓

Migration

&#x20;  ↓

Health Check

```



Production deployment should preferably require a successful CI stage.



\---



\# 54. Pull Request Validation



Before merging significant changes:



```text

\[ ] Tests pass

\[ ] Lint passes

\[ ] Type checks pass

\[ ] Architecture respected

\[ ] Security reviewed

\[ ] Tenant isolation reviewed where relevant

\[ ] Documentation updated if necessary

```



\---



\# 55. Database Migration Deployment Flow



The recommended flow:



```text

Create Migration

&#x20;     ↓

Local Test

&#x20;     ↓

Commit

&#x20;     ↓

CI Test

&#x20;     ↓

Staging

&#x20;     ↓

Verify

&#x20;     ↓

Production

```



Do not manually modify production tables to "quickly fix" a deployment.



\---



\# 56. Zero-Downtime Considerations



For the FYP, complete enterprise-grade zero-downtime deployment is not required.



However, avoid migrations that unnecessarily break the running application.



Prefer:



```text

Add

&#x20;↓

Deploy Compatible Code

&#x20;↓

Migrate Data

&#x20;↓

Remove Old Structure Later

```



for major schema changes where practical.



\---



\# 57. Deployment Rollback



If an application release fails:



```text

Detect failure

&#x20;↓

Stop rollout

&#x20;↓

Inspect logs

&#x20;↓

Rollback application if safe

&#x20;↓

Restore database only when necessary

&#x20;↓

Verify health

```



Database rollback must be handled carefully because application rollback and schema rollback are not always equivalent.



\---



\# 58. Smoke Tests After Deployment



Immediately after deployment verify:



```text

GET /health

```



Then:



```text

Register/Login

Business access

Knowledge retrieval

Chat

Lead

Booking

```



For enabled integrations:



```text

Google Calendar

WhatsApp

Voice

```



Run only the integrations required for the current deployment.



\---



\# 59. Production Smoke Test



Minimum:



```text

\[ ] Frontend opens

\[ ] Backend health works

\[ ] Database connection works

\[ ] Authentication works

\[ ] Business data loads

\[ ] Knowledge base works

\[ ] Chat works

\[ ] Lead creation works

\[ ] Booking works

```



\---



\# 60. FYP Deployment Strategy



The FYP should use a controlled deployment rather than an unnecessarily complex production infrastructure.



Recommended conceptual setup:



```text

Frontend

&#x20;   ↓

Vercel



Backend

&#x20;   ↓

Railway / Render



PostgreSQL + pgvector

&#x20;   ↓

Managed PostgreSQL



Redis

&#x20;   ↓

Managed Redis



Worker

&#x20;   ↓

Separate worker service



Files

&#x20;   ↓

S3-compatible storage

```



This is sufficient for demonstrating the architecture without building unnecessary infrastructure.



\---



\# 61. FYP Cost Control



For the FYP:



\* use free/low-cost tiers where practical

\* avoid unnecessary always-on resources

\* use local embeddings if suitable

\* use mocked providers during development

\* limit AI calls during testing

\* avoid storing unnecessary audio

\* use one demo business

\* keep worker workloads controlled



Cost optimization must not weaken:



\* security

\* tenant isolation

\* data integrity

\* core functionality



\---



\# 62. Production Configuration Checklist



```text

\[ ] APP\_ENV=production

\[ ] Production database configured

\[ ] Redis configured

\[ ] Secret keys configured

\[ ] CORS configured

\[ ] Frontend URL configured

\[ ] OAuth URLs configured

\[ ] WhatsApp webhook configured

\[ ] Storage configured

\[ ] LLM provider configured

\[ ] STT configured

\[ ] TTS configured

\[ ] Logging configured

\[ ] Health check configured

```



\---



\# 63. Security Deployment Checklist



```text

\[ ] HTTPS enabled

\[ ] Secure cookies configured

\[ ] Secrets not in Git

\[ ] Production secrets separated

\[ ] Database credentials protected

\[ ] CORS restricted

\[ ] Rate limiting enabled

\[ ] Webhook verification enabled

\[ ] OAuth configuration verified

\[ ] Tenant isolation verified

\[ ] File upload limits enabled

\[ ] Security headers enabled

\[ ] WebSocket authentication enabled

```



\---



\# 64. Database Deployment Checklist



```text

\[ ] PostgreSQL available

\[ ] pgvector available

\[ ] Migration completed

\[ ] Indexes verified

\[ ] Connection pooling configured

\[ ] Backup available

\[ ] Database credentials secured

\[ ] Production data isolated

```



\---



\# 65. External Integration Checklist



\### LLM



```text

\[ ] API key configured

\[ ] Provider adapter works

\[ ] Timeout configured

\[ ] Retry policy configured

```



\### Deepgram



```text

\[ ] API key configured

\[ ] WebSocket/streaming path tested

\[ ] Timeout handling tested

```



\### ElevenLabs



```text

\[ ] API key configured

\[ ] Voice configuration tested

\[ ] Failure handling tested

```



\### Google Calendar



```text

\[ ] OAuth credentials configured

\[ ] Redirect URI configured

\[ ] Token encryption enabled

\[ ] Calendar flow tested

```



\### WhatsApp



```text

\[ ] Access token configured

\[ ] Webhook configured

\[ ] Verification tested

\[ ] Signature validation tested

```



\### Storage



```text

\[ ] Bucket configured

\[ ] Credentials configured

\[ ] File upload tested

\[ ] File authorization tested

```



\---



\# 66. Monitoring Checklist



Monitor:



```text

\[ ] API availability

\[ ] API latency

\[ ] Error rate

\[ ] Database errors

\[ ] Redis errors

\[ ] Worker failures

\[ ] LLM failures

\[ ] RAG failures

\[ ] STT failures

\[ ] TTS failures

\[ ] WhatsApp failures

\[ ] Calendar failures

```



\---



\# 67. Deployment Incident Workflow



When production has a serious problem:



```text

Detect

&#x20;↓

Assess

&#x20;↓

Protect customer/business data

&#x20;↓

Stop harmful operation

&#x20;↓

Investigate logs

&#x20;↓

Mitigate

&#x20;↓

Restore service

&#x20;↓

Verify

&#x20;↓

Document incident

&#x20;↓

Add regression prevention

```



\---



\# 68. Deployment Documentation



The README should provide enough information for a new developer to understand:



\* prerequisites

\* local setup

\* environment variables

\* Docker setup

\* database migration

\* running frontend

\* running backend

\* running worker

\* running tests



Deployment-specific information should remain consistent with this document.



\---



\# 69. Antigravity Deployment Rules



Antigravity must:



1\. follow the approved deployment architecture

2\. not introduce a new hosting provider without approval

3\. not replace PostgreSQL

4\. not remove Redis because it is inconvenient

5\. not place secrets in code

6\. not expose backend credentials to frontend

7\. not bypass migrations

8\. not disable HTTPS requirements

9\. not weaken CORS/security settings to make deployment "work"

10\. not use production credentials for ordinary tests

11\. not deploy unfinished phases accidentally

12\. verify health after deployment changes

13\. document approved deployment changes



\---



\# 70. Antigravity Production Safety Rule



Before making production-related changes, Antigravity should identify:



```text

Affected service

Affected environment

Affected database

Affected secrets

Migration requirements

Rollback considerations

Smoke tests

```



For destructive operations, human approval is required.



\---



\# 71. Deployment Definition of Done



A deployment is complete when:



```text

\[ ] Application builds

\[ ] Frontend deployed

\[ ] Backend deployed

\[ ] Database configured

\[ ] pgvector available

\[ ] Redis configured

\[ ] Worker configured

\[ ] Environment variables configured

\[ ] HTTPS enabled

\[ ] Authentication verified

\[ ] Tenant isolation verified

\[ ] Core workflows verified

\[ ] Required integrations verified

\[ ] Health checks pass

\[ ] Logs available

\[ ] Backups configured where applicable

\[ ] Smoke tests pass

\[ ] Documentation updated

```



\---



\# 72. Final Deployment Architecture



The approved deployment topology is:



```text

&#x20;                        Internet

&#x20;                           │

&#x20;                           ▼

&#x20;                   ┌───────────────┐

&#x20;                   │    Browser    │

&#x20;                   └───────┬───────┘

&#x20;                           │

&#x20;                           ▼

&#x20;                   ┌───────────────┐

&#x20;                   │    Next.js    │

&#x20;                   │   Frontend    │

&#x20;                   └───────┬───────┘

&#x20;                           │ HTTPS

&#x20;                           ▼

&#x20;                   ┌───────────────┐

&#x20;                   │    FastAPI    │

&#x20;                   │    Backend    │

&#x20;                   └───┬────┬───┬──┘

&#x20;                       │    │   │

&#x20;           ┌───────────┘    │   └───────────┐

&#x20;           ▼                ▼               ▼

&#x20;     PostgreSQL           Redis           Worker

&#x20;      + pgvector

&#x20;           │                │               │

&#x20;           └────────────────┴───────────────┘

&#x20;                            │

&#x20;                            ▼

&#x20;                  External Integrations

&#x20;                            │

&#x20;         ┌──────────────────┼──────────────────┐

&#x20;         │                  │                  │

&#x20;        LLM              WhatsApp          Google

&#x20;                                            Calendar

&#x20;         │                  │                  │

&#x20;     Deepgram          ElevenLabs          Storage

```



\---



\# 73. Final Deployment Principle



AgentDesk deployment must preserve the same architecture used during development.



The deployment environment must not become a reason to redesign the application.



The core principle is:



```text

Same Architecture

\+

Environment-specific Configuration

\+

Secure Deployment

\+

Reproducible Infrastructure

\+

Verified Releases

```



The FYP deployment should remain simple enough to manage while still demonstrating the intended production-ready architecture.



