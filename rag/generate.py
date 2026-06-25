"""
Generation: build a prompt from retrieved chunks and call qwen3:4b via Ollama.

Thinking mode is off by default (faster, sufficient for factual Q&A).
Pass think=True to enable qwen3's chain-of-thought for complex queries.
"""

from __future__ import annotations

import re

import ollama

GEN_MODEL = "qwen3:4b"

_SYSTEM_PROMPT = """\
You are an expert Formula 1 analyst. Answer the user's question using ONLY the \
race data provided in the context below. Be concise and specific — cite driver \
names, positions, points, and seasons where relevant. If the answer cannot be \
determined from the provided context, say so clearly rather than guessing.
/no_think"""

def _strip_thinking(text: str) -> str:
    """
    qwen3 via Ollama may embed thinking content directly in the response without
    a proper opening <think> tag — only the closing </think> is reliably present.
    Strip everything up to and including the last </think> when it appears.
    """
    marker = "</think>"
    idx = text.rfind(marker)
    if idx != -1:
        text = text[idx + len(marker):]
    return text.strip()


def generate(query: str, context_chunks: list[dict], think: bool = False) -> str:
    """
    Build a RAG prompt and call qwen3:4b.

    context_chunks: list of dicts from retrieve.retrieve(), each with 'text' key.
    think: keep qwen3 chain-of-thought in the response (slower, better for
           complex multi-step reasoning). Off by default.
    """
    context_text = "\n\n---\n\n".join(
        f"[{c['year']} Round {c['round']} — {c['circuit']}]\n{c['text']}"
        for c in context_chunks
    )

    system = _SYSTEM_PROMPT if not think else _SYSTEM_PROMPT.replace("/no_think", "/think")

    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"Context:\n{context_text}\n\nQuestion: {query}",
        },
    ]

    response = ollama.chat(
        model=GEN_MODEL,
        messages=messages,
        options={"temperature": 0.1},
        think=think,
    )

    answer = response.message.content

    if not think:
        answer = _strip_thinking(answer)

    return answer
