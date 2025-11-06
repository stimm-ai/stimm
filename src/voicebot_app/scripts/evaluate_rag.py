#!/usr/bin/env python3
"""Lightweight regression harness to evaluate the RAG retrieval quality."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import httpx


@dataclass
class EvaluationSample:
    question: str
    must_include: List[str]
    namespace: Optional[str]
    top_k: int


def _load_dataset(path: Path) -> List[EvaluationSample]:
    samples: List[EvaluationSample] = []
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            payload = json.loads(line)
            samples.append(
                EvaluationSample(
                    question=payload["question"],
                    must_include=list(payload.get("must_include", [])),
                    namespace=payload.get("namespace"),
                    top_k=int(payload.get("top_k", 4)),
                )
            )
    if not samples:
        raise ValueError(f"No evaluation samples found in {path}")
    return samples


def _term_found(contexts: Iterable[dict], term: str) -> bool:
    needle = term.lower()
    for ctx in contexts:
        text = (ctx.get("text") or "").lower()
        if needle in text:
            return True
    return False


def run_evaluation(
    *,
    dataset: Path,
    base_url: str,
    endpoint: str,
    timeout: float,
) -> None:
    samples = _load_dataset(dataset)
    passed = 0
    total_required_terms = 0
    total_hit_terms = 0

    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        for sample in samples:
            payload = {"question": sample.question, "top_k": sample.top_k}
            if sample.namespace:
                payload["namespace"] = sample.namespace
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
            contexts = data.get("contexts", [])

            term_hits = {
                term: _term_found(contexts, term) for term in sample.must_include
            }
            success = all(term_hits.values())

            total_required_terms += len(term_hits)
            total_hit_terms += sum(1 for hit in term_hits.values() if hit)
            if success:
                passed += 1
            else:
                missing = [term for term, hit in term_hits.items() if not hit]
                print(
                    f"[WARN] Missing terms for '{sample.question}': "
                    f"{', '.join(missing)}"
                )

    print(
        f"\nEvaluation complete against {len(samples)} samples "
        f"({passed}/{len(samples)} successful prompts)."
    )
    if total_required_terms:
        coverage = total_hit_terms / total_required_terms
        print(f"Required term coverage: {coverage:.2%}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/bayview_rag_eval.jsonl"),
        help="Path to JSONL dataset containing evaluation prompts (default: %(default)s)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8002",
        help="Base URL for the RAG service (default: %(default)s)",
    )
    parser.add_argument(
        "--endpoint",
        default="/rag/query",
        help="RAG query endpoint path (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP timeout in seconds (default: %(default)s)",
    )

    args = parser.parse_args()
    run_evaluation(
        dataset=args.dataset,
        base_url=args.base_url,
        endpoint=args.endpoint,
        timeout=args.timeout,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
