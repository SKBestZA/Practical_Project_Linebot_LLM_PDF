# PoliChatbot — LINE RAG Policy Chatbot

Mini project LINE Chatbot สำหรับตอบคำถามเกี่ยวกับระเบียบและนโยบายของบริษัท  
ใช้กระบวนการ **RAG (Retrieval-Augmented Generation)** โดยปัจจุบันใช้ **Qwen3 32B** ผ่าน Groq API  
และใช้ **Llama Guard 3 1B** ผ่าน Ollama สำหรับ Guardrail

> เริ่มต้นพัฒนาด้วย LLaMA 3.2 3B แบบ open-source รันบนเครื่อง ปัจจุบันย้ายมาใช้ Qwen3 32B ผ่าน Groq API เพื่อประสิทธิภาพที่ดีขึ้น

---

## สถาปัตยกรรมระบบ

```
LINE App
  │
  ▼
LINE Webhook (FastAPI)
  │
  ├─► Guardrail Layer
  │     ├─ Keyword Blacklist
  │     ├─ Embedding Scope Check
  │     └─ Llama Guard Safety Check
  │
  ├─► RAG Pipeline
  │     ├─ ChromaDB        ← Vector Search
  │     ├─ Hybrid Retrieval (all + department)
  │     └─ Groq API        ← LLM Answer Generation
  │
  └─► Supabase (PostgreSQL)
        ├─ Employee Data
        └─ Query Logs

Admin Dashboard (React + Vite)
  └─► จัดการพนักงาน, อัปโหลดเอกสาร PDF, ดูสถิติการใช้งาน
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.11 |
| Frontend | React, Vite, TypeScript, Tailwind CSS |
| Vector DB | ChromaDB |
| LLM | Qwen3 32B via Groq API |
| Guardrail | Llama Guard 3 1B via Ollama |
| Embedding | `paraphrase-multilingual-MiniLM-L12-v2` |
| Database | PostgreSQL (Supabase) |
| Chatbot | LINE Messaging API + LIFF |
| Infrastructure | Docker Compose, Nginx, ngrok |

---

## โครงสร้างโปรเจค

```
root/
├── backend/
│   ├── src/
│   │   ├── config/          # Database connection
│   │   ├── routers/         # API endpoints (auth, webhook, pdf, admin)
│   │   ├── services/        # Business logic (RAG pipeline, ChromaDB, Guardrail, LLM)
│   │   └── utils/           # Shared utilities (embedding, NLP, file handler)
│   ├── data/
│   │   └── sql/             # DDL / DML scripts
│   ├── models/              # Dockerfiles สำหรับ Ollama models
│   ├── config/              # .env file (ไม่ commit)
│   ├── Dockerfile.backend
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/  # Page components + shadcn/ui
│   │   │   └── lib/api.ts   # API layer ทั้งหมด
│   │   └── styles/
│   ├── Dockerfile.frontend
│   └── nginx.conf
├── docker-compose.yml       # Root compose (รวมทุก service + ngrok)
└── README.md
```

---

## การติดตั้งและรัน

### สิ่งที่ต้องมีก่อน

- [Docker](https://docs.docker.com/get-docker/) และ Docker Compose
- LINE Developer Account (สร้าง Messaging API Channel และ LIFF App)
- [Groq API Key](https://console.groq.com/)
- Supabase Project (หรือ PostgreSQL database อื่น)

---

### ขั้นตอนที่ 1 — ตั้งค่า Environment Variables

#### Backend — สร้างไฟล์ `backend/config/.env`

```bash
mkdir -p backend/config
touch backend/config/.env
```

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# LINE (ได้จาก LINE Developer Console → Messaging API)
LINE_CHANNEL_ACCESS_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LINE_CHANNEL_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# LIFF (ได้จาก LINE Developer Console → LIFF)
LIFF_ID=1234567890-xxxxxxxx
LIFF_URL=https://liff.line.me/1234567890-xxxxxxxx

# Supabase (ได้จาก Supabase Dashboard → Project Settings → API)
DATABASE_URL=postgresql://postgres:password@db.xxxxxxxxxxxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxxxxxxxxx

# Server — ใส่ ngrok URL ที่ได้หลัง docker compose up
BASE_URL=https://xxxx-xx-xx-xx-xx.ngrok-free.app
```

> **หมายเหตุ:** `OLLAMA_HOST`, `CHROMA_HOST`, `CHROMA_PORT` จะถูกตั้งค่าอัตโนมัติโดย Docker Compose ไม่ต้องใส่

#### Frontend — สร้างไฟล์ `frontend/.env`

```env
# LIFF ID จาก LINE Developer Console (ตัวเลขเดียวกับ backend)
VITE_LIFF_ID=1234567890-xxxxxxxx

# frontend และ backend อยู่บน domain เดียวกันผ่าน nginx ใส่แค่ path พอ
VITE_API_URL=/api
```

---

### ขั้นตอนที่ 2 — ตั้งค่า ngrok (สำหรับ LINE Webhook)

สร้างไฟล์ `ngrok.yml` ที่ root:

```yaml
version: "3"
authtoken: your-ngrok-authtoken
tunnels:
  frontend:
    proto: http
    addr: frontend:80
  backend:
    proto: http
    addr: backend:8000
```

---

### ขั้นตอนที่ 3 — Build และรัน

```bash
# Build และรัน ทุก service พร้อมกัน
docker compose up --build

# รันแบบ background
docker compose up --build -d
```

Service ที่จะรันขึ้นมา:

| Service | Port | คำอธิบาย |
|---|---|---|
| backend | 8000 (internal) | FastAPI |
| frontend | 80 (internal) | React Admin Dashboard |
| chromadb | 8000 (internal) | Vector Database |
| ollama | 11434 (internal) | Llama Guard |
| ngrok | 4040 | Dashboard + Tunnel |

---

### ขั้นตอนที่ 4 — ตั้งค่า LINE Webhook

1. เปิด ngrok dashboard ที่ `http://localhost:4040`
2. Copy URL ของ backend tunnel เช่น `https://xxxx.ngrok-free.app`
3. ไปที่ LINE Developer Console → Messaging API
4. ตั้ง Webhook URL เป็น `https://xxxx.ngrok-free.app/webhook/line`
5. อัปเดต `BASE_URL` ใน `.env` ให้ตรงกับ ngrok URL แล้ว restart backend

```bash
docker compose restart backend
```

---

### ขั้นตอนที่ 5 — เข้าใช้งาน Admin Dashboard

เปิด browser ที่ ngrok frontend URL ที่ได้จาก `http://localhost:4040`

---

## ตรวจสอบ Logs

```bash
# ดู log ทุก service
docker compose logs -f

# ดูเฉพาะ backend
docker compose logs -f backend

# ดูเฉพาะ ollama
docker compose logs -f ollama
```

---

## RAG Pipeline

```
User Message
    │
    ▼
[ด่าน 0] Greeting Fast Track
    │
    ▼
[ด่าน 1] Input Guardrail
         ├─ Keyword Blacklist
         ├─ Embedding Scope Check (in_scope?)
         └─ Llama Guard Safety Check
    │
    ▼
[ด่าน 2] Hybrid Retrieval
         ├─ Score all-collection per file
         ├─ Score department-collection per file
         ├─ Rerank → Top 3 files
         └─ Deep fetch + dedup
    │
    ▼
[ด่าน 3] LLM Answer (Groq API)
    │
    ▼
[ด่าน 4] Output Guardrail (Whitelist + Llama Guard)
    │
    ▼
LINE Flex Message + Source Documents
```

---

## Environment Variables — Reference

**Backend** (`backend/config/.env`)

| Variable | คำอธิบาย |
|---|---|
| `GROQ_API_KEY` | Groq API key สำหรับ LLM |
| `LINE_CHANNEL_ACCESS_TOKEN` | สำหรับส่งข้อความผ่าน LINE |
| `LINE_CHANNEL_SECRET` | สำหรับ verify webhook signature |
| `LIFF_ID` | LIFF App ID |
| `LIFF_URL` | URL ของ LIFF App |
| `DATABASE_URL` | PostgreSQL connection string |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon/service key |
| `BASE_URL` | URL ของ server ที่ expose ออกภายนอก |
| `OLLAMA_HOST` | ตั้งอัตโนมัติโดย Docker Compose |
| `CHROMA_HOST` | ตั้งอัตโนมัติโดย Docker Compose |
| `CHROMA_PORT` | ตั้งอัตโนมัติโดย Docker Compose |

> **หมายเหตุ Authentication:** ระบบใช้ UUID Token ที่ generate จาก `gen_random_uuid()` เก็บใน `Admin.Token` column แทน JWT ทำให้ logout แล้ว token หมดทันที แต่ทุก request จะ query DB เพื่อตรวจสอบ

**Frontend** (`frontend/.env`)

| Variable | คำอธิบาย |
|---|---|
| `VITE_LIFF_ID` | LIFF App ID (ตัวเดียวกับ backend) |
| `VITE_API_URL` | Path ของ backend เช่น `/api` (same domain ผ่าน nginx) |
