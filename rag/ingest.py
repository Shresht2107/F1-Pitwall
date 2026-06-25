"""
Ingest pipeline: build race documents → chunk → embed → upsert into Qdrant.

Run once (or re-run to rebuild the collection):
    /opt/anaconda3/bin/python3 -m rag.ingest
"""

from __future__ import annotations

import sys
import uuid

import ollama
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from rag.build_docs import build_documents

QDRANT_URL = "http://localhost:6333"
COLLECTION  = "f1_rag"
EMBED_MODEL = "nomic-embed-text"
VECTOR_DIM  = 768   # nomic-embed-text output dimension

# Each race document is ~800–1500 chars; chunk at 800 chars with 100 overlap
# so that driver-level lines stay grouped but long races split cleanly.
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _embed(text: str) -> list[float]:
    resp = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return resp["embedding"]


def setup_collection(client: QdrantClient, recreate: bool = False) -> None:
    exists = any(c.name == COLLECTION for c in client.get_collections().collections)
    if exists and recreate:
        client.delete_collection(COLLECTION)
        exists = False
    if not exists:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        print(f"Created Qdrant collection '{COLLECTION}'.")
    else:
        print(f"Collection '{COLLECTION}' already exists — skipping creation.")


def ingest(recreate: bool = False) -> None:
    client = QdrantClient(url=QDRANT_URL)
    setup_collection(client, recreate=recreate)

    docs = build_documents()
    print(f"Built {len(docs)} race documents. Chunking...")

    points: list[PointStruct] = []
    total_chunks = 0

    for text, meta in docs:
        chunks = _splitter.split_text(text)
        total_chunks += len(chunks)

        for chunk in chunks:
            vector = _embed(chunk)
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text": chunk,
                    "year": meta["year"],
                    "round": meta["round"],
                    "circuit": meta["circuit"],
                    "drivers": meta["drivers"],
                    "constructors": meta["constructors"],
                },
            )
            points.append(point)

        label = f"{meta['year']} R{meta['round']:02d} ({meta['circuit']})"
        print(f"  {label}: {len(chunks)} chunk(s)", flush=True)

    # Upsert in batches of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        client.upsert(collection_name=COLLECTION, points=points[i : i + batch_size])

    print(f"\nUpserted {total_chunks} chunks from {len(docs)} races into '{COLLECTION}'.")


if __name__ == "__main__":
    recreate = "--recreate" in sys.argv
    ingest(recreate=recreate)
