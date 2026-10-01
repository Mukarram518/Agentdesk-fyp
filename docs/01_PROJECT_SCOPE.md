\# AgentDesk — Project Scope



\*\*Project:\*\* AgentDesk — A Multi-Agent AI Platform for Small Businesses

\*\*Team:\*\* Mukarram Ali \& Hadia Saleem

\*\*Document:\*\* Project Scope

\*\*Version:\*\* 1.0

\*\*Status:\*\* Approved Scope Baseline



\---



\# 1. Purpose



This document defines the official scope of AgentDesk.



It establishes:



\* project purpose

\* target users

\* core problem

\* project objectives

\* functional scope

\* non-functional scope

\* system boundaries

\* FYP boundaries

\* exclusions

\* expected outcomes



This document must be used to prevent uncontrolled feature expansion during development.



\---



\# 2. Project Overview



AgentDesk is a multi-tenant web platform designed to provide small businesses with configurable AI agents.



The platform allows a business owner to configure a shared business knowledge base and AI agents that can interact with customers through:



\* Web Chat

\* WhatsApp

\* Browser Voice Simulator



The AI system can answer questions, qualify leads, and assist with appointment booking.



The system supports both:



\* Urdu

\* English



The platform is designed around a shared \*\*Business Brain\*\*, allowing multiple AI agents to use the same business information and customer context.



\---



\# 3. Problem Statement



Small businesses often receive repetitive customer questions and inquiries through different communication channels.



Common problems include:



\* repeated manual responses

\* difficulty responding outside business hours

\* customer information being scattered across conversations

\* missed leads

\* manual lead qualification

\* manual appointment scheduling

\* inconsistent answers

\* lack of centralized customer conversation history

\* limited technical resources for implementing AI automation



AgentDesk aims to provide a centralized platform where a small business can configure AI assistance without building separate AI systems for every channel.



\---



\# 4. Project Objectives



The primary objectives are:



1\. Build a multi-tenant AI platform for small businesses.

2\. Provide a shared business knowledge base.

3\. Implement RAG-based business information retrieval.

4\. Provide configurable AI agents.

5\. Support Web Chat.

6\. Support WhatsApp.

7\. Provide a browser-based voice simulator.

8\. Support Urdu and English.

9\. Automate lead qualification.

10\. Assist with appointment booking.

11\. Maintain conversation history.

12\. Provide a centralized business dashboard.

13\. Maintain strong tenant isolation and security.

14\. Provide an architecture that can be extended with additional AI providers and channels.



\---



\# 5. Target Users



\## 5.1 Primary User — Business Owner



The business owner can:



\* register/login

\* configure the business

\* configure business hours

\* configure AI agents

\* add FAQs

\* upload business documents

\* review conversations

\* view leads

\* view appointments

\* connect Google Calendar

\* configure WhatsApp

\* view analytics



\---



\## 5.2 Customer



A customer interacts with AgentDesk through:



\* Web Chat

\* WhatsApp

\* Voice Simulator



The customer can:



\* ask business questions

\* request information

\* express buying intent

\* provide contact details

\* describe their requirements

\* request an appointment

\* reschedule an appointment

\* cancel an appointment



\---



\# 6. Core System Capabilities



AgentDesk consists of the following major capabilities:



```text

Authentication

Business Onboarding

Agent Configuration

Knowledge Base

RAG

AI Orchestrator

Web Chat

WhatsApp

Lead Generation

Appointment Booking

Voice Simulator

Conversation History

Dashboard

Analytics

```



\---



\# 7. Functional Scope



\## 7.1 Authentication



The system shall support:



\* email/password registration

\* email/password login

\* Google sign-in

\* logout

\* protected application routes

\* session management



\---



\## 7.2 Business Onboarding



The owner shall be able to configure:



\* business name

\* business category/vertical

\* business hours

\* contact information

\* WhatsApp information

\* Google Calendar

\* enabled AI agents



\---



\## 7.3 Knowledge Base



The system shall allow the owner to:



\* create FAQs

\* edit FAQs

\* delete FAQs

\* upload PDF files

\* upload DOCX files

\* view knowledge entries

\* manage business knowledge



Uploaded files shall be processed into searchable knowledge.



Maximum supported upload size:



```text

5 MB

```



\---



\## 7.4 RAG



The system shall:



\* extract document text

\* clean extracted text

\* divide text into chunks

\* generate embeddings

\* store embeddings in pgvector

\* perform semantic retrieval

\* provide relevant information to the AI orchestrator



RAG retrieval must always be restricted to the current business.



\---



\## 7.5 AI Orchestrator



The orchestrator shall:



\* identify language

\* understand customer intent

\* load business context

\* retrieve relevant knowledge

\* determine the appropriate agent behavior

\* determine available tools

\* generate responses

\* coordinate backend actions

\* maintain conversation context



The LLM shall not directly access the database or external privileged services.



\---



\# 8. Chat / FAQ Agent Scope



The Chat Agent shall:



\* answer customer questions

\* use the business knowledge base

\* use business configuration

\* support Urdu

\* support English

\* maintain conversation context

\* avoid unsupported business claims

\* provide appropriate responses based on available knowledge



The Chat Agent will operate through:



\* Web Chat

\* WhatsApp



\---



\# 9. Lead Generation Agent Scope



The Lead Agent shall:



\* detect potential buying intent

\* ask appropriate qualification questions

\* collect customer name

\* collect customer contact

\* collect customer need

\* classify the lead

\* store the lead

\* make the lead visible to the business owner

\* support owner notification



Lead classifications:



```text

Hot

Warm

Cold

```



These classifications are internal application labels.



\---



\# 10. Appointment Booking Scope



AgentDesk shall integrate with Google Calendar.



Supported operations:



\* check availability

\* create appointment

\* reschedule appointment

\* cancel appointment

\* store local appointment information

\* store Google Calendar event ID



The system shall require appropriate authorization before performing calendar operations.



\---



\# 11. Voice Agent Scope



The FYP implementation shall provide a browser-based voice simulator.



The voice simulator shall support:



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



The FYP does not require live telephone/telephony functionality.



The architecture should remain extensible for future telephony.



\---



\# 12. WhatsApp Scope



The system shall support WhatsApp Business Cloud API integration.



The integration shall provide:



\* webhook verification

\* webhook signature validation

\* incoming message processing

\* AI response generation

\* outgoing responses

\* conversation persistence

\* tenant mapping

\* duplicate-event protection



\---



\# 13. Conversation History Scope



The system shall maintain conversation records containing information such as:



\* business

\* channel

\* language

\* start time

\* end time

\* status

\* outcome

\* summary



Messages shall maintain:



\* role

\* content

\* timestamp

\* optional audio reference



Supported channels:



```text

Web

WhatsApp

Voice

```



\---



\# 14. Dashboard Scope



The dashboard shall provide business owners with access to:



\* business overview

\* agent configuration

\* knowledge base

\* conversations

\* conversation details

\* leads

\* appointments

\* analytics

\* settings



\---



\# 15. Analytics Scope



Analytics are a \*\*Should\*\* requirement.



The platform may provide:



\* number of calls

\* number of chats

\* number of leads

\* number of bookings

\* top customer intents



Analytics should be generated from stored application data rather than directly from the LLM.



\---



\# 16. Language Scope



Supported languages:



```text

English

Urdu

```



The system shall be capable of:



\* detecting the customer's language

\* responding in the appropriate language

\* using multilingual business knowledge

\* maintaining language context during conversations



Urdu RAG quality must be tested before final demonstration.



\---



\# 17. Multi-Tenant Scope



AgentDesk must be multi-tenant from the beginning.



Each business must have isolated:



\* business profile

\* agent configuration

\* knowledge

\* conversations

\* messages

\* leads

\* appointments

\* analytics

\* integration credentials



A business must never be able to access another business's data.



Tenant isolation is a core system requirement.



\---



\# 18. Security Scope



The project includes:



\* secure authentication

\* password hashing

\* authorization

\* tenant isolation

\* API validation

\* rate limiting

\* secure file uploads

\* webhook verification

\* encrypted integration credentials

\* secure secret management

\* AI tool authorization

\* prompt injection protection

\* safe error handling



Security is part of the core implementation rather than an optional enhancement.



\---



\# 19. Non-Functional Scope



\## Performance



Target requirements:



```text

Voice p95 response latency: < 1.5 seconds

Web/WhatsApp p95 latency:   < 5 seconds

Dashboard interaction:      < 3 seconds

Demo concurrency target:    30 active conversations

```



These are engineering targets and depend on deployment infrastructure and external provider latency.



\---



\## Reliability



The system should provide:



\* timeout handling

\* controlled retries

\* idempotency

\* error logging

\* graceful external-service failures

\* background processing for appropriate operations



\---



\## Security



The system shall protect:



\* customer information

\* business information

\* authentication credentials

\* integration credentials

\* uploaded documents

\* conversation data



\---



\## Accessibility



The frontend should target:



```text

WCAG 2.1 AA

```



The application should be responsive and usable on common desktop and mobile browser sizes.



\---



\## PWA



The frontend should support Progressive Web App behavior according to the approved SRS.



\---



\# 20. Data Retention Scope



The approved retention policy is:



| Data          | Retention            |

| ------------- | -------------------- |

| Business data | Until owner deletion |

| Call audio    | Purged after 30 days |

| Transcripts   | Until owner deletion |

| Leads         | Until owner deletion |



Deletion functionality must be designed to prevent unnecessary orphaned data.



\---



\# 21. FYP Demonstration Scope



The FYP demonstration should show one configured business.



The demonstration should cover:



1\. Owner authentication

2\. Business onboarding

3\. Knowledge base configuration

4\. Document/FAQ processing

5\. AI response using RAG

6\. Urdu/English interaction

7\. Lead qualification

8\. Lead storage

9\. Google Calendar booking

10\. Conversation history

11\. Dashboard

12\. Browser voice interaction



The system remains architecturally multi-tenant even though the primary demonstration uses one business.



\---



\# 22. Explicit Exclusions



The following are outside the current project scope:



\### Billing



No:



\* subscriptions

\* payment processing

\* invoices for AgentDesk itself

\* payment gateway



\---



\### Native Mobile Applications



No:



\* native Android application

\* native iOS application



The web application/PWA is the approved client.



\---



\### Full Telephony



The FYP does not require:



\* real phone numbers

\* PSTN integration

\* SIP infrastructure

\* live inbound/outbound phone deployment



Only the browser voice simulator is required.



\---



\### Marketing / Content Agent



The content/marketing agent is not part of the current FYP scope.



It may be considered for Phase 2.



\---



\# 23. Scope Change Rules



Any new feature must be evaluated before implementation.



A proposed feature must answer:



1\. Is it required by the SRS?

2\. Is it required by the SDD?

3\. Does it support an existing approved capability?

4\. Does it affect the architecture?

5\. Does it require new external services?

6\. Does it introduce additional security risks?

7\. Does it affect the FYP schedule?

8\. Does it require database changes?



If the feature changes approved architecture or scope, documentation must be updated before implementation.



\---



\# 24. Scope Protection Rules



The following must not happen without explicit approval:



\* replacing PostgreSQL

\* replacing FastAPI

\* replacing Next.js

\* removing multi-tenancy

\* adding a new AI provider directly into business logic

\* adding large unrelated features

\* redesigning the architecture during coding

\* creating duplicate agent systems

\* bypassing the central orchestrator

\* allowing agents direct database access

\* removing security controls for convenience



\---



\# 25. Expected Final Outcome



At completion, AgentDesk should provide a working FYP platform where a small business can:



```text

Register

&#x20;  ↓

Configure Business

&#x20;  ↓

Configure Agents

&#x20;  ↓

Add Business Knowledge

&#x20;  ↓

Use RAG

&#x20;  ↓

Receive Customer Conversations

&#x20;  ↓

Answer Questions

&#x20;  ↓

Qualify Leads

&#x20;  ↓

Book Appointments

&#x20;  ↓

Store Conversations

&#x20;  ↓

View Leads

&#x20;  ↓

View Appointments

&#x20;  ↓

View Analytics

```



The final system should demonstrate how multiple AI capabilities can operate through one shared business context.



\---



\# 26. Scope Baseline



The following capabilities form the official AgentDesk FYP scope:



```text

✓ Authentication

✓ Business Onboarding

✓ Multi-Tenancy

✓ Knowledge Base

✓ PDF/DOCX Processing

✓ RAG

✓ Shared Business Brain

✓ Chat Agent

✓ Lead Agent

✓ Browser Voice Agent

✓ Web Chat

✓ WhatsApp

✓ Google Calendar

✓ Conversation History

✓ Lead Management

✓ Appointment Management

✓ Dashboard

✓ Basic Analytics

✓ Urdu/English

✓ Security

✓ Testing

✓ Deployment

```



The following are excluded:



```text

✗ Billing

✗ Native Android

✗ Native iOS

✗ Live Telephony

✗ Marketing/Content Agent

```



\---



\# 27. Scope Approval



This document represents the approved functional boundary for the AgentDesk FYP.



Development should remain within this scope unless a scope change is explicitly reviewed and documented.



\*\*End of Project Scope\*\*



