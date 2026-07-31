# RAG Strategy Retrieval — Root Cause Inspection Plan

## Problem Statement

Queries like "What strategy did Max run at Austria 2024?" return "strategy not provided
in context" despite the data existing in `stage2_dataset.csv` and Qdrant. The retrieved
chunk for Austria 2024 contains only the race header — not the per-driver strategy lines.

---

## Inspection Layers

### 1. Document Structure  (`rag/build_docs.py`)

**Goal:** Understand the physical layout of a generated race document.

**Measurements:**
- Full text of 3–4 representative races (winner finishes P1 early in doc; mid-grid VER)
- Character offset where the per-driver section begins vs. the race header section
- Character offset of each specific driver's line (e.g. VER at P1 vs. P5 vs. P10)
- Whether any strategy summary appears in the race header (it doesn't — confirm)
- Average character length of: header block, one driver line, full document

**What we're looking for:**
- Header block is ~300 chars. At P5, VER's line starts around char 300 + (4 × ~250) ≈ 1300.
  A driver finishing P10+ will be 2500+ chars in — deep in chunk 3 or 4.
- Strategy text for a non-winner driver is never in chunk 1 (the only chunk that reliably
  gets retrieved for a race-level query).

---

### 2. Chunk Boundaries  (`rag/ingest.py`)

**Goal:** Know exactly which chunk each piece of information falls into.

**Measurements:**
- Current `chunk_size` and `chunk_overlap` values
- For Austria 2024 and Japan 2024: enumerate every chunk with its start char, end char,
  and first 80 chars of text
- Identify the chunk index that contains VER's strategy line for each race
- Check whether a single driver line ever straddles two chunks (split at bad position)

**What we're looking for:**
- With chunk_size=800 and overlap=100, a 300-char header + 4 driver lines at ~250 chars
  each = 1300 chars total before VER's line at P5. That puts VER firmly in chunk 2.
- For a P10 driver (~2800 chars in), VER would be in chunk 4.
- Overlap of 100 chars is unlikely to carry a full driver line across chunk boundaries.

---

### 3. Retrieval Score Distribution  (`rag/retrieve.py` + Qdrant)

**Goal:** Determine whether driver-detail chunks are ever retrieved for strategy queries,
and how large the score gap is between header and detail chunks.

**Measurements:**
- Run retrieval with `top_k=20` (4× normal) for strategy queries
- For each result: year, round, chunk number (by position in doc), score, first 100 chars
- Identify: what is the highest-scoring driver-detail chunk for the correct race?
- Compare: score of Austria R11 header chunk vs. Austria R11 driver-detail chunks
- Test 5 query variants (see §6) to see if any phrasing surfaces driver chunks

**What we're looking for:**
- If the driver-detail chunk for Austria R11 never appears even in top-20, the embeddings
  are so dominated by race-identity tokens that topical queries can't surface them
- If it appears in positions 6–10, a simple top_k increase would fix it
- Score gap size determines whether the fix is a retrieval tweak or a document restructure

---

### 4. Embedding Semantic Alignment  (Ollama `nomic-embed-text`)

**Goal:** Understand whether the embedding model encodes strategy queries and driver-detail
chunks close together or far apart in vector space.

**Measurements:**
- Embed the query: "What strategy did Max run at Austria 2024?"
- Embed: (a) Austria R11 header chunk text, (b) Austria R11 VER driver-detail chunk text
- Compute cosine similarity of query vs. each chunk manually (numpy dot product)
- Repeat for a working query: "Who won Austria 2024?" — compare similarity profiles
- Repeat for "VER strategy Austria 2024" (terse) and "MEDIUM HARD strategy 2024" (compound-focused)

**What we're looking for:**
- If query ↔ header similarity >> query ↔ driver-detail similarity for ALL query variants,
  the issue is in how nomic-embed-text encodes strategy text, not in retrieval logic
- If terse query ("VER strategy Austria") shifts the gap, the fix is query rewriting
- If compound-name variant ("MEDIUM HARD") lifts driver chunks, the fix is adding
  compound names to the document header

---

### 5. Generation Prompt  (`rag/generate.py`)

**Goal:** Confirm whether the LLM is seeing strategy text at all, or whether it's correctly
reporting that no strategy info is in the context it received.

**Measurements:**
- Print the full prompt sent to qwen3:4b for a strategy query (before LLM call)
- Check: does ANY chunk in the prompt contain the word "strategy" or a compound name?
- Check: does the system prompt instruct the LLM to say "not found" explicitly?

**What we're looking for:**
- If none of the 5 chunks contain "strategy", the LLM answer ("not provided") is correct —
  the failure is entirely in retrieval, not generation
- If strategy text IS present but ignored, the failure is in prompt construction or LLM behavior

---

### 6. Cross-Query Comparison  (control set)

Run all of the following; record top-5 results (year, round, score) and LLM answer:

| # | Query | Expected result |
|---|-------|----------------|
| 1 | "Who won Japan 2024?" | Works — answer in header chunk |
| 2 | "How many DNFs at Austria 2024?" | Works — DNF count in header |
| 3 | "What strategy did Max run at Japan 2024?" | Fails — strategy in driver chunk |
| 4 | "What strategy did Max run at Austria 2024?" | Fails — driver finishing P5 |
| 5 | "VER strategy Austria 2024" | Test if terse helps |
| 6 | "What tyres did Verstappen use in Austria?" | Test synonym phrasing |
| 7 | "What strategy did Russell run at Austria 2024?" | Winner (P1) — should be closer to chunk 1 |

Query 7 is the key control: RUS won Austria 2024 (P1). His strategy line is the FIRST
driver line in the document, within chunk 1. If query 7 works but query 4 (VER, P5) fails,
it confirms the issue is purely about character offset / chunk number, not about the
query phrasing or model.

---

## Evaluation Parameters

| Parameter | Measured from | Tells us |
|-----------|--------------|---------|
| Header char length | build_docs output | Baseline before driver lines start |
| Chars-per-driver-line | build_docs output | How fast we move through chunks |
| VER char offset | build_docs output | Which chunk VER lands in |
| chunk_size / overlap | ingest.py config | Chunk boundary positions |
| Chunk index of VER line | Chunk enumeration | Confirms burial depth |
| Score: header vs detail | Qdrant retrieval | Size of the gap to close |
| Score: query variants | Qdrant retrieval | Whether phrasing can bridge the gap |
| cos_sim: query ↔ chunks | Ollama embedding | Whether embedding is the bottleneck |
| Strategy text in prompt | generate.py | Whether LLM sees strategy at all |

---

## Root Cause Categories and Likely Fix

| Root cause | Evidence | Fix direction |
|------------|----------|---------------|
| Strategy buried deep in doc, chunk 2+ never retrieved | VER chunk not in top-10 at any query variant | Add strategy to race header in build_docs.py |
| Score gap is small, top_k just needs to increase | VER chunk in positions 6–10 | Increase top_k from 5 to 10 in retrieve.py |
| Embedding doesn't associate "strategy" with compound-name text | Cosine sim query↔detail << query↔header for all variants | Add compound tokens to header or use a reranker |
| LLM ignores strategy text even when present | Strategy text in prompt but wrong answer | Fix prompt instruction in generate.py |

---

## Out of Scope

- Code fixes (inspection only until root cause confirmed)
- Is_DNF correctness (already resolved)
- Model prediction accuracy (separate concern)
