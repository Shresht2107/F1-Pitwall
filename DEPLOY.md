# PIT WALL — Deployment Plan
# Migration: local Ollama + local Qdrant → fully hosted free stack

## Overview of changes
| Component        | Before                        | After                          |
|------------------|-------------------------------|--------------------------------|
| Vector DB        | Docker Qdrant (localhost:6333)| Qdrant Cloud free tier         |
| LLM generation   | Ollama / qwen3:4b             | Groq API / qwen3-32b           |
| Embeddings       | Ollama / nomic-embed-text     | Nomic Atlas Embedding API      |
| FastAPI backend  | Local (port 8000)             | Render free tier               |
| Next.js frontend | Local (port 3000)             | Vercel free tier               |

## Pre-work (human must do these — Claude Code cannot)
Before starting, the user must manually:

1. Create a Qdrant Cloud account at https://cloud.qdrant.io and create a free cluster.
   - Copy the cluster URL (format: https://xxxx.us-east4-0.gcp.cloud.qdrant.io)
   - Copy the API key from the dashboard
   - Do NOT recreate the collection yet — Step 2 handles re-ingestion

2. Create a Groq account at https://console.groq.com and generate an API key.
   - Confirm that `qwen/qwen3-32b` is listed under available models

3. Create a Nomic account at https://atlas.nomic.ai and generate an API key.
   - Confirm 1M free token credits are visible in the dashboard

4. Create a Render account at https://render.com (free tier, no card needed).

5. Create a Vercel account at https://vercel.com (free tier, no card needed).

6. Ensure the project is on GitHub — both Render and Vercel deploy from a Git repo.

Once all five accounts are ready and keys are collected, hand off to Claude Code.

---

## Step 1 — Centralise all configuration in `.env` and `config.py`

### 1a. Create a `.env` file in the project root

Create a file named `.env` in the project root with the following keys.
Do NOT fill in the values — leave them as placeholders. The user will fill
them in after Claude Code creates the file.

```
# Qdrant Cloud
QDRANT_URL=https://YOUR_CLUSTER_URL.qdrant.io
QDRANT_API_KEY=YOUR_QDRANT_API_KEY

# Groq (LLM generation)
GROQ_API_KEY=YOUR_GROQ_API_KEY

# Nomic (embeddings)
NOMIC_API_KEY=YOUR_NOMIC_API_KEY
```

### 1b. Add `.env` to `.gitignore`

Open `.gitignore` (create it at the project root if it does not exist) and
add the following lines if they are not already present:

```
.env
fastf1_cache/
__pycache__/
*.pyc
*.pkl
```

### 1c. Update `config.py` to load environment variables

At the top of `config.py`, add:

```python
import os
from dotenv import load_dotenv
load_dotenv()

# Qdrant
QDRANT_URL     = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)

# Groq
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")

# Nomic
NOMIC_API_KEY  = os.getenv("NOMIC_API_KEY")
```

All other files must import these constants from `config.py` — do not read
`os.getenv` directly in individual RAG files.

---

## Step 2 — Migrate embeddings from Ollama to Nomic Atlas API

**File to edit: `rag/ingest.py`**

Replace the Ollama embedding call with the Nomic Atlas API.

Current pattern (approximate):
```python
import ollama
embedding = ollama.embeddings(model="nomic-embed-text", prompt=text)["embedding"]
```

New pattern:
```python
import nomic
from nomic import embed
nomic.login(token=config.NOMIC_API_KEY)

def embed_texts(texts: list[str]) -> list[list[float]]:
    output = embed.text(
        texts=texts,
        model="nomic-embed-text-v1.5",
        task_type="search_document",
    )
    return output["embeddings"]
```

Important details:
- The Nomic API call is batched — pass a list of texts in a single call
  rather than one text at a time. This is more efficient and uses fewer tokens.
- At ingest time use `task_type="search_document"`.
- At query time (Step 3) use `task_type="search_query"`.
- `nomic-embed-text-v1.5` produces the same 768-dimensional vectors as the
  local `nomic-embed-text` model, so existing Qdrant vectors do NOT need to
  be deleted before re-ingestion. The new vectors will be compatible.

**File to edit: `rag/retrieve.py`**

Replace the Ollama query embedding call with:
```python
from nomic import embed
import nomic
nomic.login(token=config.NOMIC_API_KEY)

def embed_query(query: str) -> list[float]:
    output = embed.text(
        texts=[query],
        model="nomic-embed-text-v1.5",
        task_type="search_query",
    )
    return output["embeddings"][0]
```

**Dependency to add:**
```
nomic
```
Add to `requirements.txt`.

---

## Step 3 — Migrate LLM generation from Ollama to Groq

**File to edit: `rag/generate.py`**

Replace the Ollama generation call with the Groq SDK.
Groq's API is OpenAI-compatible, so the change is minimal.

Current pattern (approximate):
```python
import ollama
response = ollama.chat(
    model="qwen3:4b",
    messages=[{"role": "user", "content": prompt}]
)
answer = response["message"]["content"]
```

New pattern:
```python
from groq import Groq
import config

_groq_client = Groq(api_key=config.GROQ_API_KEY)

def generate(prompt: str, think: bool = False) -> str:
    messages = [{"role": "user", "content": prompt}]
    response = _groq_client.chat.completions.create(
        model="qwen/qwen3-32b",
        messages=messages,
    )
    answer = response.choices[0].message.content

    # Strip chain-of-thought block if present (same logic as before)
    if "</think>" in answer:
        answer = answer.split("</think>")[-1].strip()

    return answer
```

Note on the `think` flag: Qwen3-32B on Groq supports thinking mode via
the `/think` and `/no_think` tokens in the prompt rather than a separate
API parameter. If `think=True`, prepend `/think\n` to the user content
before sending. If `think=False` (default for RAG Q&A), prepend `/no_think\n`
to keep responses fast and concise.

**Dependency to add:**
```
groq
```
Add to `requirements.txt`.

---

## Step 4 — Migrate Qdrant from localhost to Qdrant Cloud

**Files to edit: `rag/ingest.py` and `rag/retrieve.py`**

Every place a `QdrantClient` is instantiated, replace:

```python
# Before
from qdrant_client import QdrantClient
client = QdrantClient(host="localhost", port=6333)
```

With:
```python
# After
from qdrant_client import QdrantClient
import config

client = QdrantClient(
    url=config.QDRANT_URL,
    api_key=config.QDRANT_API_KEY,
)
```

When `QDRANT_URL` is `http://localhost:6333` and `QDRANT_API_KEY` is `None`
(the defaults in `config.py`), this behaves identically to the current local
setup — so local development still works without changing anything.

---

## Step 5 — Re-ingest into Qdrant Cloud

After the user fills in the `.env` with real keys, run:

```bash
python -m rag.ingest --recreate
```

This rebuilds the `f1_rag` collection from scratch in the cloud cluster.
Verify by opening the Qdrant Cloud dashboard and confirming the collection
shows ~420 points.

This step is a one-time manual run — not part of the automated pipeline.

---

## Step 6 — Prepare the FastAPI backend for Render

### 6a. Create `requirements.txt` in the project root

Ensure the following are present (add any that are missing):

```
fastapi
uvicorn[standard]
xgboost
scikit-learn
pandas
numpy
fastf1
requests
qdrant-client
groq
nomic
langchain-text-splitters
python-dotenv
```

### 6b. Create a `render.yaml` in the project root

```yaml
services:
  - type: web
    name: pitwall-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn api.server:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: QDRANT_URL
        sync: false
      - key: QDRANT_API_KEY
        sync: false
      - key: GROQ_API_KEY
        sync: false
      - key: NOMIC_API_KEY
        sync: false
```

`sync: false` means Render will prompt the user to fill in these values
in the dashboard rather than reading them from the file — keeping secrets
out of the repo.

### 6c. Update CORS in `api/server.py`

The deployed frontend will not be on `localhost`, so CORS must allow the
Vercel domain. Update the CORS middleware:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",              # local dev
        "https://pitwall.vercel.app",         # Vercel deployment
        "https://*.vercel.app",               # Vercel preview deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

The user must replace `pitwall.vercel.app` with their actual Vercel domain
after deploying the frontend.

---

## Step 7 — Prepare the Next.js frontend for Vercel

### 7a. Create `pitwall/.env.local` for local development

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 7b. Create `pitwall/.env.production` for the Vercel deployment

```
NEXT_PUBLIC_API_URL=https://pitwall-api.onrender.com
```

The user must replace this URL with the actual Render service URL shown
in the Render dashboard after deploying the backend.

### 7c. Update all API calls in Next.js to use the environment variable

In `pitwall/app/api/chat/route.ts` and `pitwall/app/api/race/route.ts`,
replace any hardcoded `http://localhost:8000` with:

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
```

Then use `API_URL` as the base for all fetch calls to the FastAPI backend.

### 7d. Create `pitwall/vercel.json`

```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next"
}
```

---

## Step 8 — Add a health check wake-up call

Render's free tier spins down the backend after 15 minutes of inactivity,
causing a ~30 second cold start on the first request.

**File to edit: `pitwall/components/Chat.tsx`**

On component mount, fire a silent ping to the `/health` endpoint so the
backend is warmed up before the user sends their first message:

```typescript
useEffect(() => {
  fetch(`${process.env.NEXT_PUBLIC_API_URL}/health`).catch(() => {});
}, []);
```

This runs once when the dashboard loads and silently wakes the backend.
No loading state or UI change is needed — the fetch result is discarded.

---

## Step 9 — Verify locally before deploying

With the `.env` filled in with real cloud keys, run the full local stack
against the cloud services:

```bash
# Terminal 1 — FastAPI (now talking to Groq + Nomic + Qdrant Cloud)
uvicorn api.server:app --reload --port 8000

# Terminal 2 — Next.js
cd pitwall && npm run dev
```

Open http://localhost:3000/dashboard and run one of the test queries from
the project's known-good question list. Confirm:
- The chat panel returns a grounded answer
- The dashboard panels update with real race data
- No errors reference localhost:6333, ollama, or missing API keys

---

## Step 10 — Deploy

### Backend → Render
1. Push all changes to GitHub.
2. In the Render dashboard, create a new Web Service, connect the GitHub repo.
3. Render will detect `render.yaml` automatically.
4. Fill in the four environment variables in the Render dashboard
   (QDRANT_URL, QDRANT_API_KEY, GROQ_API_KEY, NOMIC_API_KEY).
5. Trigger a manual deploy. Wait for the build to complete (~3 minutes).
6. Copy the service URL (e.g. `https://pitwall-api.onrender.com`).

### Frontend → Vercel
1. In the Vercel dashboard, import the GitHub repo.
2. Set the root directory to `pitwall`.
3. Add one environment variable: `NEXT_PUBLIC_API_URL` = the Render URL from above.
4. Deploy. Vercel builds and deploys in ~2 minutes.
5. Copy the Vercel URL and update the CORS `allow_origins` list in
   `api/server.py`, then re-deploy the backend.

---

## Acceptance checklist

Claude Code should verify each item before considering the task complete:

- [ ] `.env` exists at project root with all four keys as placeholders
- [ ] `.env` is in `.gitignore` and will not be committed
- [ ] `config.py` loads all four env vars via `python-dotenv`
- [ ] `rag/ingest.py` uses Nomic Atlas API with `task_type="search_document"`
- [ ] `rag/retrieve.py` uses Nomic Atlas API with `task_type="search_query"`
- [ ] `rag/generate.py` uses Groq SDK with model `qwen/qwen3-32b`
- [ ] `rag/ingest.py` and `rag/retrieve.py` use `QdrantClient(url=..., api_key=...)` from `config`
- [ ] Local Qdrant (localhost:6333) is still the default when env vars are absent
- [ ] `requirements.txt` includes `groq`, `nomic`, `python-dotenv`
- [ ] `render.yaml` exists at project root
- [ ] CORS in `api/server.py` allows both localhost and the Vercel domain
- [ ] Next.js API routes use `NEXT_PUBLIC_API_URL` env var, not hardcoded localhost
- [ ] `pitwall/vercel.json` exists
- [ ] Health check wake-up call exists in `Chat.tsx`
- [ ] Full local test against cloud services passes with no errors
