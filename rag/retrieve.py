"""
Retrieval: embed a query with nomic-embed-text and search Qdrant.

Optionally applies payload pre-filters extracted from the query text
(year, driver code, constructor) before running vector search.
"""

from __future__ import annotations

import re

import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

QDRANT_URL  = "http://localhost:6333"
COLLECTION  = "f1_rag"
EMBED_MODEL = "nomic-embed-text"
TOP_K       = 5

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL)
    return _client


def _embed(text: str) -> list[float]:
    resp = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return resp["embedding"]


# Known driver codes and constructors present in the dataset
_DRIVER_CODES = {
    "VER", "PER", "LEC", "SAI", "HAM", "RUS", "NOR", "PIA", "ALO", "STR",
    "GAS", "OCO", "ALB", "SAR", "TSU", "RIC", "ZHO", "BOT", "HUL", "MAG",
    "LAW", "BEA", "ANT", "DOO", "HAD", "BOR", "COL",
}

_CONSTRUCTOR_ALIASES: dict[str, str] = {
    "red bull": "red_bull", "redbull": "red_bull", "ferrari": "ferrari",
    "mercedes": "mercedes", "mclaren": "mclaren", "aston martin": "aston_martin",
    "alpine": "alpine", "williams": "williams", "haas": "haas",
    "rb": "rb", "racing bulls": "rb", "sauber": "sauber", "kick sauber": "sauber",
}

# Map of keyword → circuit payload string for filtering by race name
_CIRCUIT_KEYWORDS: dict[str, str] = {
    "bahrain": "Bahrain GP", "saudi": "Saudi Arabian GP", "jeddah": "Saudi Arabian GP",
    "australian": "Australian GP", "melbourne": "Australian GP",
    "japanese": "Japanese GP", "suzuka": "Japanese GP",
    "chinese": "Chinese GP", "shanghai": "Chinese GP",
    "miami": "Miami GP",
    "emilia romagna": "Emilia Romagna GP", "imola": "Emilia Romagna GP",
    "monaco": "Monaco GP", "monte carlo": "Monaco GP",
    "canadian": "Canadian GP", "montreal": "Canadian GP",
    "spanish": "Spanish GP", "barcelona": "Spanish GP",
    "austrian": "Austrian GP", "red bull ring": "Austrian GP",
    "british": "British GP", "silverstone": "British GP",
    "hungarian": "Hungarian GP", "budapest": "Hungarian GP",
    "belgian": "Belgian GP", "spa": "Belgian GP",
    "dutch": "Dutch GP", "zandvoort": "Dutch GP",
    "italian": "Italian GP", "monza": "Italian GP",
    "singapore": "Singapore GP",
    "azerbaijan": "Azerbaijan GP", "baku": "Azerbaijan GP",
    "united states": "United States GP", "cota": "United States GP", "austin": "United States GP",
    "mexico city": "Mexico City GP", "mexico": "Mexico City GP",
    "são paulo": "São Paulo GP", "brazil": "São Paulo GP", "interlagos": "São Paulo GP",
    "las vegas": "Las Vegas GP",
    "qatar": "Qatar GP", "lusail": "Qatar GP",
    "abu dhabi": "Abu Dhabi GP", "yas marina": "Abu Dhabi GP",
}


def _extract_filters(query: str) -> Filter | None:
    """
    Parse year, driver codes, circuit name, and team name from free-text query.
    Returns a Qdrant Filter or None if nothing specific was detected.
    """
    q_upper = query.upper()
    q_lower = query.lower()
    conditions = []

    # Year: four-digit number in range 2022-2024
    years = [int(m) for m in re.findall(r"\b(202[2-4])\b", query)]
    if years:
        conditions.append(FieldCondition(key="year", match=MatchAny(any=years)))

    # Driver codes: match only explicitly uppercase tokens in the original query.
    # Using q_upper would match common words ("had"→HAD, "the"→THE) as driver codes.
    tokens = set(re.findall(r'\b[A-Z]{3}\b', query))
    found_drivers = list(_DRIVER_CODES & tokens)
    if found_drivers:
        conditions.append(FieldCondition(key="drivers", match=MatchAny(any=found_drivers)))

    # Constructor: fuzzy match against alias table
    found_constructors = [cid for alias, cid in _CONSTRUCTOR_ALIASES.items() if alias in q_lower]
    if found_constructors:
        conditions.append(
            FieldCondition(key="constructors", match=MatchAny(any=list(set(found_constructors))))
        )

    # Circuit name: match known keywords → exact circuit string in payload
    found_circuit: str | None = None
    for keyword, circuit_name in _CIRCUIT_KEYWORDS.items():
        if keyword in q_lower:
            found_circuit = circuit_name
            break
    if found_circuit:
        conditions.append(FieldCondition(key="circuit", match=MatchValue(value=found_circuit)))

    if not conditions:
        return None

    return Filter(must=conditions)


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Return top_k results as dicts with keys: text, year, round, circuit, score.
    """
    client = _get_client()
    vector = _embed(query)
    payload_filter = _extract_filters(query)

    response = client.query_points(
        collection_name=COLLECTION,
        query=vector,
        query_filter=payload_filter,
        limit=top_k,
        with_payload=True,
    )
    hits = response.points

    # If filter was too restrictive and returned nothing, fall back to unfiltered
    if not hits and payload_filter is not None:
        response = client.query_points(
            collection_name=COLLECTION,
            query=vector,
            limit=top_k,
            with_payload=True,
        )
        hits = response.points

    results = []
    for hit in hits:
        p = hit.payload
        results.append({
            "text":    p.get("text", ""),
            "year":    p.get("year"),
            "round":   p.get("round"),
            "circuit": p.get("circuit", ""),
            "score":   round(hit.score, 4),
        })

    return results
