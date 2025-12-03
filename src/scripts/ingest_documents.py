#!/usr/bin/env python3
"""LEGACY: Utility script to chunk markdown files and ingest them into the RAG service.

This script uses the legacy /knowledge/documents endpoint.
For new RAG admin management, consider using the upload endpoints via
/rag-configs/{rag_config_id}/documents/upload instead.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence
from uuid import NAMESPACE_URL, uuid5

import httpx

DEFAULT_TARGET_WORDS = 180
DEFAULT_MAX_WORDS = 240
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9']+")


@dataclass(frozen=True)
class DocumentChunk:
    text: str
    section: str
    chunk_index: int
    chunk_count: int
    source: str
    checksum: str
    namespace: str | None
    point_id: str

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.point_id,
            "text": self.text,
            "metadata": {
                "source": self.source,
                "section": self.section,
                "chunk_index": self.chunk_index,
                "chunks_total": self.chunk_count,
                "checksum": self.checksum,
            },
        }
        if self.namespace:
            payload["namespace"] = self.namespace
        payload["metadata"]["word_count"] = len(_tokenize(self.text))
        return payload


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _sliding_chunks(items: Sequence[str], target_words: int, max_words: int) -> Iterator[list[str]]:
    chunk: list[str] = []
    word_count = 0

    for item in items:
        tokens = _tokenize(item)
        if not tokens:
            continue

        prospective_count = word_count + len(tokens)
        if chunk and prospective_count > max_words:
            yield chunk
            chunk = []
            word_count = 0

        chunk.append(item)
        word_count += len(tokens)

        if word_count >= target_words:
            yield chunk
            chunk = []
            word_count = 0

    if chunk:
        yield chunk


def _parse_sections(text: str) -> Iterator[tuple[str, list[str]]]:
    current_title = "Overview"
    buffer: list[str] = []

    for line in text.splitlines():
        heading_match = HEADING_PATTERN.match(line.strip())
        if heading_match:
            if buffer:
                yield current_title, buffer
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            current_title = title or f"Untitled H{level}"
            buffer = []
        else:
            buffer.append(line)

    if buffer:
        yield current_title, buffer


def _section_paragraphs(lines: list[str]) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append("\n".join(current).strip())
                current = []
            continue
        current.append(line.rstrip())

    if current:
        paragraphs.append("\n".join(current).strip())

    return [p for p in paragraphs if p]


def _chunk_markdown(path: Path, *, namespace: str | None, target_words: int, max_words: int) -> list[DocumentChunk]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Document {path} is empty")

    chunks: list[DocumentChunk] = []
    seen_checksums: set[str] = set()

    for section_title, lines in _parse_sections(text):
        paragraphs = _section_paragraphs(lines)
        if not paragraphs:
            continue

        merged_chunks = list(_sliding_chunks(paragraphs, target_words, max_words))
        total = len(merged_chunks) or 1

        for index, chunk_items in enumerate(merged_chunks or [paragraphs]):
            body = "\n\n".join(chunk_items).strip()
            enriched_text = f"{section_title}\n\n{body}" if section_title else body
            checksum = hashlib.sha256(enriched_text.encode("utf-8")).hexdigest()
            if checksum in seen_checksums:
                continue
            seen_checksums.add(checksum)
            point_id = str(uuid5(NAMESPACE_URL, checksum))
            chunks.append(
                DocumentChunk(
                    text=enriched_text,
                    section=section_title or "General",
                    chunk_index=index,
                    chunk_count=total,
                    source=path.name,
                    checksum=checksum,
                    namespace=namespace,
                    point_id=point_id,
                )
            )

    return chunks


def _build_payload(paths: Iterable[Path], namespace: str | None, target_words: int, max_words: int) -> dict:
    documents = []

    for path in paths:
        file_chunks = _chunk_markdown(path, namespace=namespace, target_words=target_words, max_words=max_words)
        if not file_chunks:
            continue
        for chunk in file_chunks:
            documents.append(chunk.to_payload())

    if not documents:
        raise ValueError("No documents prepared for ingestion")

    return {"documents": documents}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="Paths to text/markdown files to ingest",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("VOICEBOT_API_URL", "http://localhost:8001"),
        help="Base URL for the RAG service (default: %(default)s)",
    )
    parser.add_argument(
        "--endpoint",
        default="/knowledge/documents",
        help="Ingestion endpoint path (default: %(default)s)",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Optional namespace to assign to all ingested documents",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--target-words",
        type=int,
        default=DEFAULT_TARGET_WORDS,
        help="Preferred number of words per chunk before splitting (default: %(default)s)",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=DEFAULT_MAX_WORDS,
        help="Hard cap on words per chunk (default: %(default)s)",
    )

    args = parser.parse_args()
    if args.max_words < args.target_words:
        parser.error("--max-words must be greater than or equal to --target-words")

    payload = _build_payload(args.files, args.namespace, args.target_words, args.max_words)

    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        response = client.post(args.endpoint, json=payload)
        response.raise_for_status()

    print(
        "Successfully ingested",
        len(payload["documents"]),
        "chunk(s) into",
        args.base_url,
        "namespace",
        args.namespace or "<default>",
    )


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
