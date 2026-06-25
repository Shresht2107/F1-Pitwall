"""
Interactive F1 RAG CLI.

Usage:
    /opt/anaconda3/bin/python3 -m rag.cli            # standard mode
    /opt/anaconda3/bin/python3 -m rag.cli --think    # enable qwen3 thinking mode
"""

from __future__ import annotations

import argparse
import sys

from rag.generate import generate
from rag.retrieve import retrieve


def main() -> None:
    parser = argparse.ArgumentParser(description="F1 RAG — natural language Q&A over race data")
    parser.add_argument("--think", action="store_true", help="Enable qwen3 chain-of-thought reasoning")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve (default: 5)")
    args = parser.parse_args()

    mode = "thinking" if args.think else "fast"
    print(f"\nF1 RAG  |  model: qwen3:4b ({mode} mode)  |  top-k: {args.top_k}")
    print("Ask anything about F1 2022–2024. Type 'exit' to quit.\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            sys.exit(0)

        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            print("Bye.")
            sys.exit(0)

        chunks = retrieve(query, top_k=args.top_k)

        if not chunks:
            print("RAG: No relevant race data found.\n")
            continue

        # Show sources so the user can verify grounding
        sources = ", ".join(
            f"{c['year']} R{c['round']} {c['circuit']} (score={c['score']})"
            for c in chunks
        )
        print(f"[Sources: {sources}]")

        answer = generate(query, chunks, think=args.think)
        print(f"\nRAG: {answer}\n")


if __name__ == "__main__":
    main()
