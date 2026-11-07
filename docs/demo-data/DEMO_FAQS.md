# AgentDesk — Multilingual Demo FAQ Dataset

- **Target Business**: `AgentDesk Demo Business`
- **Business Slug**: `agentdesk-demo-business`
- **Business ID**: `a4ba4534-20aa-4c7c-b4b8-4b68c71b1670`
- **Owner**: `Awais` (`awais@gmail.com` | `0185c0bb-a8ce-4a35-9ec7-cafd0dddc36a`)
- **Active Embedding Model**: `intfloat/multilingual-e5-small` (384 dimensions)
- **Total FAQ Entries**: 12 (4 English, 4 Native Urdu, 4 Roman Urdu / Mixed)

---

## 1. Machine-Readable JSON Definition

```json
[
  {
    "id": 1,
    "category": "business_hours_and_location",
    "language": "en",
    "question": "What are the business hours and office location for AgentDesk Demo Business?",
    "answer": "Official business hours and physical office address have not yet been configured for AgentDesk Demo Business. Please check back later or contact our team through this chat for direct assistance.",
    "tags": ["hours", "timings", "location", "address", "office", "unconfigured", "support"]
  },
  {
    "id": 2,
    "category": "business_hours_and_location",
    "language": "ur",
    "question": "ایجنٹ ڈیسک ڈیمو بزنس کے دفتری اوقات اور پتہ کیا ہے؟",
    "answer": "ایجنٹ ڈیسک ڈیمو بزنس کے لیے سرکاری دفتری اوقات اور دفتر کا پتہ فی الحال ترتیب نہیں دیا گیا ہے۔ براہِ کرم بعد میں دوبارہ رجوع کریں یا براہِ راست مدد کے لیے اس چیٹ کے ذریعے ہماری ٹیم سے رابطہ کریں۔",
    "tags": ["اوقات", "پتہ", "دفتر", "ٹائمنگ", "غیر_ترتیب_شدہ", "hours", "location"]
  },
  {
    "id": 3,
    "category": "business_hours_and_location",
    "language": "mixed",
    "question": "AgentDesk Demo Business ke office timings aur location kya hain?",
    "answer": "AgentDesk Demo Business ke official office timings aur physical location abhi configure nahi kiye gaye hain. Barah-e-karam baad me check karein ya direct madad ke liye is chat ke zariye hamari team se rabta karein.",
    "tags": ["timings", "location", "address", "office", "auqat", "pata", "unconfigured"]
  },
  {
    "id": 4,
    "category": "services_and_overview",
    "language": "en",
    "question": "What services does AgentDesk Demo Business provide?",
    "answer": "AgentDesk Demo Business provides autonomous AI agents tailored for small and medium businesses. Our platform capabilities include bilingual customer support across Web Chat and WhatsApp, automated lead qualification, shared business knowledge retrieval (RAG), and appointment scheduling.",
    "tags": ["services", "overview", "ai-agents", "features", "whatsapp", "rag", "support"]
  },
  {
    "id": 5,
    "category": "services_and_overview",
    "language": "ur",
    "question": "ایجنٹ ڈیسک ڈیمو بزنس کون سی خدمات فراہم کرتا ہے؟",
    "answer": "ایجنٹ ڈیسک ڈیمو بزنس چھوٹے اور درمیانے کاروباروں کے لیے خودکار اے آئی ایجنٹس فراہم کرتا ہے۔ ہمارے پلیٹ فارم کی خصوصیات میں ویب چیٹ اور واٹس ایپ پر اردو اور انگریزی میں کسٹمر سپورٹ، خودکار لیڈ کوالیفکیشن، مشترکہ بزنس نالج ریٹریول (RAG)، اور اپائنٹمنٹ شیڈولنگ شامل ہیں۔",
    "tags": ["خدمات", "اے آئی", "واٹس ایپ", "کسٹمر سپورٹ", "فیچرز", "services", "ai-agents"]
  },
  {
    "id": 6,
    "category": "services_and_overview",
    "language": "mixed",
    "question": "AgentDesk Demo Business kon si services provide karta hai?",
    "answer": "AgentDesk Demo Business small businesses ke liye smart AI agents provide karta hai. Hamare platform features me Web Chat aur WhatsApp par Urdu aur English customer support, automated lead qualification, shared business knowledge (RAG), aur appointment scheduling shamil hain.",
    "tags": ["services", "khidmaat", "ai-agents", "whatsapp", "features", "support"]
  },
  {
    "id": 7,
    "category": "appointment_booking",
    "language": "en",
    "question": "How can I book an appointment or consultation with AgentDesk Demo Business?",
    "answer": "You can request an appointment or demo consultation directly through this Web chat or WhatsApp assistant. Please provide your preferred date, time, and contact details, and our team or automated scheduling agent will review availability and confirm your booking.",
    "tags": ["appointment", "booking", "schedule", "consultation", "meeting", "demo"]
  },
  {
    "id": 8,
    "category": "appointment_booking",
    "language": "ur",
    "question": "ایجنٹ ڈیسک ڈیمو بزنس کے ساتھ اپائنٹمنٹ یا مشاورتی میٹنگ کیسے بک کریں؟",
    "answer": "آپ اس ویب چیٹ یا واٹس ایپ اسسٹنٹ کے ذریعے براہِ راست اپائنٹمنٹ یا ڈیمو مشاورت کی درخواست کر سکتے ہیں۔ براہِ کرم اپنی پسندیدہ تاریخ، وقت اور رابطہ کی تفصیلات فراہم کریں، اور ہماری ٹیم یا خودکار بکنگ ایجنٹ دستیابی کا جائزہ لے کر آپ کی بکنگ کی تصدیق کرے گا۔",
    "tags": ["اپائنٹمنٹ", "بکنگ", "شیڈول", "میٹنگ", "مشاورت", "booking", "appointment"]
  },
  {
    "id": 9,
    "category": "appointment_booking",
    "language": "mixed",
    "question": "AgentDesk Demo Business ke sath appointment ya meeting kaise book karein?",
    "answer": "Aap is Web Chat ya WhatsApp assistant ke zariye direct appointment ya demo consultation request kar sakte hain. Barah-e-karam apni pasandeeda date, time aur contact details provide karein, aur hamari team ya automated booking agent availability check karke booking confirm karega.",
    "tags": ["appointment", "booking", "meeting", "schedule", "rabta", "demo"]
  },
  {
    "id": 10,
    "category": "pricing_and_payment",
    "language": "en",
    "question": "What are the pricing packages and accepted payment methods?",
    "answer": "Official pricing packages, service rates, and payment methods have not yet been configured for AgentDesk Demo Business. For customized quotes or billing inquiries, please reach out directly through this chat or submit your requirements.",
    "tags": ["pricing", "packages", "cost", "payment", "rates", "fees", "unconfigured"]
  },
  {
    "id": 11,
    "category": "pricing_and_payment",
    "language": "ur",
    "question": "پیکیجز کی قیمتیں اور ادائیگی کے طریقے کیا ہیں؟",
    "answer": "ایجنٹ ڈیسک ڈیمو بزنس کے لیے سرکاری پیکیجز کی قیمتیں، چارجز اور ادائیگی کے طریقے فی الحال ترتیب نہیں دیے گئے ہیں۔ اپنی ضروریات کے مطابق کوٹیشن یا بلنگ سے متعلق معلومات کے لیے، براہِ کرم اس چیٹ کے ذریعے رابطہ کریں۔",
    "tags": ["قیمتیں", "پیکیجز", "ادائیگی", "بلنگ", "چارجز", "غیر_ترتیب_شدہ", "pricing", "payment"]
  },
  {
    "id": 12,
    "category": "pricing_and_payment",
    "language": "mixed",
    "question": "Packages ke charges aur payment ke tareeqay kya hain?",
    "answer": "AgentDesk Demo Business ke liye official pricing packages, rates aur payment methods abhi configure nahi kiye gaye hain. Custom quotation ya billing se mutaliq maloomat ke liye, barah-e-karam is chat ke zariye rabta karein.",
    "tags": ["pricing", "charges", "packages", "payment", "rates", "fees", "unconfigured"]
  }
]
```

---

## 2. Reviewable Entries by Category

### Category 1: Business Hours & Location

#### Entry 1.1 — English (`en`)
- **Question**: What are the business hours and office location for AgentDesk Demo Business?
- **Answer**: Official business hours and physical office address have not yet been configured for AgentDesk Demo Business. Please check back later or contact our team through this chat for direct assistance.
- **Language**: `en`
- **Tags**: `hours`, `timings`, `location`, `address`, `office`, `unconfigured`, `support`

#### Entry 1.2 — Native Urdu (`ur`)
- **Question**: ایجنٹ ڈیسک ڈیمو بزنس کے دفتری اوقات اور پتہ کیا ہے؟
- **Answer**: ایجنٹ ڈیسک ڈیمو بزنس کے لیے سرکاری دفتری اوقات اور دفتر کا پتہ فی الحال ترتیب نہیں دیا گیا ہے۔ براہِ کرم بعد میں دوبارہ رجوع کریں یا براہِ راست مدد کے لیے اس چیٹ کے ذریعے ہماری ٹیم سے رابطہ کریں۔
- **Language**: `ur`
- **Tags**: `اوقات`, `پتہ`, `دفتر`, `ٹائمنگ`, `غیر_ترتیب_شدہ`, `hours`, `location`

#### Entry 1.3 — Roman Urdu (`mixed`)
- **Question**: AgentDesk Demo Business ke office timings aur location kya hain?
- **Answer**: AgentDesk Demo Business ke official office timings aur physical location abhi configure nahi kiye gaye hain. Barah-e-karam baad me check karein ya direct madad ke liye is chat ke zariye hamari team se rabta karein.
- **Language**: `mixed`
- **Tags**: `timings`, `location`, `address`, `office`, `auqat`, `pata`, `unconfigured`

---

### Category 2: Services & Overview

#### Entry 2.1 — English (`en`)
- **Question**: What services does AgentDesk Demo Business provide?
- **Answer**: AgentDesk Demo Business provides autonomous AI agents tailored for small and medium businesses. Our platform capabilities include bilingual customer support across Web Chat and WhatsApp, automated lead qualification, shared business knowledge retrieval (RAG), and appointment scheduling.
- **Language**: `en`
- **Tags**: `services`, `overview`, `ai-agents`, `features`, `whatsapp`, `rag`, `support`

#### Entry 2.2 — Native Urdu (`ur`)
- **Question**: ایجنٹ ڈیسک ڈیمو بزنس کون سی خدمات فراہم کرتا ہے؟
- **Answer**: ایجنٹ ڈیسک ڈیمو بزنس چھوٹے اور درمیانے کاروباروں کے لیے خودکار اے آئی ایجنٹس فراہم کرتا ہے۔ ہمارے پلیٹ فارم کی خصوصیات میں ویب چیٹ اور واٹس ایپ پر اردو اور انگریزی میں کسٹمر سپورٹ، خودکار لیڈ کوالیفکیشن، مشترکہ بزنس نالج ریٹریول (RAG)، اور اپائنٹمنٹ شیڈولنگ شامل ہیں۔
- **Language**: `ur`
- **Tags**: `خدمات`, `اے آئی`, `واٹس ایپ`, `کسٹمر سپورٹ`, `فیچرز`, `services`, `ai-agents`

#### Entry 2.3 — Roman Urdu (`mixed`)
- **Question**: AgentDesk Demo Business kon si services provide karta hai?
- **Answer**: AgentDesk Demo Business small businesses ke liye smart AI agents provide karta hai. Hamare platform features me Web Chat aur WhatsApp par Urdu aur English customer support, automated lead qualification, shared business knowledge (RAG), aur appointment scheduling shamil hain.
- **Language**: `mixed`
- **Tags**: `services`, `khidmaat`, `ai-agents`, `whatsapp`, `features`, `support`

---

### Category 3: Appointment Booking

#### Entry 3.1 — English (`en`)
- **Question**: How can I book an appointment or consultation with AgentDesk Demo Business?
- **Answer**: You can request an appointment or demo consultation directly through this Web chat or WhatsApp assistant. Please provide your preferred date, time, and contact details, and our team or automated scheduling agent will review availability and confirm your booking.
- **Language**: `en`
- **Tags**: `appointment`, `booking`, `schedule`, `consultation`, `meeting`, `demo`

#### Entry 3.2 — Native Urdu (`ur`)
- **Question**: ایجنٹ ڈیسک ڈیمو بزنس کے ساتھ اپائنٹمنٹ یا مشاورتی میٹنگ کیسے بک کریں؟
- **Answer**: آپ اس ویب چیٹ یا واٹس ایپ اسسٹنٹ کے ذریعے براہِ راست اپائنٹمنٹ یا ڈیمو مشاورت کی درخواست کر سکتے ہیں۔ براہِ کرم اپنی پسندیدہ تاریخ، وقت اور رابطہ کی تفصیلات فراہم کریں، اور ہماری ٹیم یا خودکار بکنگ ایجنٹ دستیابی کا جائزہ لے کر آپ کی بکنگ کی تصدیق کرے گا۔
- **Language**: `ur`
- **Tags**: `اپائنٹمنٹ`, `بکنگ`, `شیڈول`, `میٹنگ`, `مشاورت`, `booking`, `appointment`

#### Entry 3.3 — Roman Urdu (`mixed`)
- **Question**: AgentDesk Demo Business ke sath appointment ya meeting kaise book karein?
- **Answer**: Aap is Web Chat ya WhatsApp assistant ke zariye direct appointment ya demo consultation request kar sakte hain. Barah-e-karam apni pasandeeda date, time aur contact details provide karein, aur hamari team ya automated booking agent availability check karke booking confirm karega.
- **Language**: `mixed`
- **Tags**: `appointment`, `booking`, `meeting`, `schedule`, `rabta`, `demo`

---

### Category 4: Pricing & Payment

#### Entry 4.1 — English (`en`)
- **Question**: What are the pricing packages and accepted payment methods?
- **Answer**: Official pricing packages, service rates, and payment methods have not yet been configured for AgentDesk Demo Business. For customized quotes or billing inquiries, please reach out directly through this chat or submit your requirements.
- **Language**: `en`
- **Tags**: `pricing`, `packages`, `cost`, `payment`, `rates`, `fees`, `unconfigured`

#### Entry 4.2 — Native Urdu (`ur`)
- **Question**: پیکیجز کی قیمتیں اور ادائیگی کے طریقے کیا ہیں؟
- **Answer**: ایجنٹ ڈیسک ڈیمو بزنس کے لیے سرکاری پیکیجز کی قیمتیں، چارجز اور ادائیگی کے طریقے فی الحال ترتیب نہیں دیے گئے ہیں۔ اپنی ضروریات کے مطابق کوٹیشن یا بلنگ سے متعلق معلومات کے لیے، براہِ کرم اس چیٹ کے ذریعے رابطہ کریں۔
- **Language**: `ur`
- **Tags**: `قیمتیں`, `پیکیجز`, `ادائیگی`, `بلنگ`, `چارجز`, `غیر_ترتیب_شدہ`, `pricing`, `payment`

#### Entry 4.3 — Roman Urdu (`mixed`)
- **Question**: Packages ke charges aur payment ke tareeqay kya hain?
- **Answer**: AgentDesk Demo Business ke liye official pricing packages, rates aur payment methods abhi configure nahi kiye gaye hain. Custom quotation ya billing se mutaliq maloomat ke liye, barah-e-karam is chat ke zariye rabta karein.
- **Language**: `mixed`
- **Tags**: `pricing`, `charges`, `packages`, `payment`, `rates`, `fees`, `unconfigured`

---

## 3. Loading Method via KnowledgeService

When approved, the dataset can be ingested directly through `KnowledgeService.create_faq()` using the active `LocalSentenceTransformerProvider`:

```python
import json
import uuid
from app.core.database import async_session_factory
from app.services.knowledge_service import knowledge_service

DEMO_BIZ_ID = uuid.UUID("a4ba4534-20aa-4c7c-b4b8-4b68c71b1670")

async def load_demo_faqs(entries_file: str):
    with open(entries_file, "r", encoding="utf-8") as f:
        entries = json.load(f)

    async with async_session_factory() as db:
        for item in entries:
            entry = await knowledge_service.create_faq(
                db=db,
                business_id=DEMO_BIZ_ID,
                question=item["question"],
                answer=item["answer"],
                tags=item["tags"],
                language=item["language"],
            )
            # Transaction committed by session context
```
