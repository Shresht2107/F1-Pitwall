"""
Ingest pipeline: build race documents → chunk → embed → upsert into Qdrant.

Run once (or re-run to rebuild the collection):
    /opt/anaconda3/bin/python3 -m rag.ingest
    /opt/anaconda3/bin/python3 -m rag.ingest --recreate
"""

from __future__ import annotations

import sys
import uuid

import nomic
from nomic import embed
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams

import config
from rag.build_docs import build_documents

nomic.login(token=config.NOMIC_API_KEY)

COLLECTION = "f1_rag"
VECTOR_DIM = 768   # nomic-embed-text-v1.5 output dimension

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _get_client() -> QdrantClient:
    return QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY, timeout=60)


def _embed_batch(texts: list[str]) -> list[list[float]]:
    output = embed.text(
        texts=texts,
        model="nomic-embed-text-v1.5",
        task_type="search_document",
    )
    return output["embeddings"]


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
        # Qdrant Cloud requires explicit payload indexes for filtered fields
        for field, schema in [
            ("year",         PayloadSchemaType.INTEGER),
            ("drivers",      PayloadSchemaType.KEYWORD),
            ("constructors", PayloadSchemaType.KEYWORD),
            ("circuit",      PayloadSchemaType.KEYWORD),
        ]:
            client.create_payload_index(
                collection_name=COLLECTION,
                field_name=field,
                field_schema=schema,
            )
        print(f"Created Qdrant collection '{COLLECTION}' with payload indexes.")
    else:
        print(f"Collection '{COLLECTION}' already exists — skipping creation.")


def ingest(recreate: bool = False) -> None:
    client = _get_client()
    setup_collection(client, recreate=recreate)

    docs = build_documents()
    print(f"Built {len(docs)} race documents. Chunking...")

    # Collect all chunks and their metadata first, then embed in one batched call
    all_chunks: list[str] = []
    all_meta: list[dict] = []

    for text, meta in docs:
        chunks = _splitter.split_text(text)
        for chunk in chunks:
            all_chunks.append(chunk)
            all_meta.append(meta)
        label = f"{meta['year']} R{meta['round']:02d} ({meta['circuit']})"
        print(f"  {label}: {len(chunks)} chunk(s)", flush=True)

    print(f"\nEmbedding {len(all_chunks)} chunks via Nomic Atlas API...")
    vectors = _embed_batch(all_chunks)

    points: list[PointStruct] = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vectors[i],
            payload={
                "text":         all_chunks[i],
                "year":         all_meta[i]["year"],
                "round":        all_meta[i]["round"],
                "circuit":      all_meta[i]["circuit"],
                "drivers":      all_meta[i]["drivers"],
                "constructors": all_meta[i]["constructors"],
            },
        )
        for i in range(len(all_chunks))
    ]

    # Upsert in batches of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        client.upsert(collection_name=COLLECTION, points=points[i : i + batch_size])

    print(f"Upserted {len(points)} chunks from {len(docs)} races into '{COLLECTION}'.")


if __name__ == "__main__":
    recreate = "--recreate" in sys.argv
    ingest(recreate=recreate)
