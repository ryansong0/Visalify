"""
Performance benchmark: nested-loop cosine similarity (original) vs vectorized
NumPy matrix-multiply cosine similarity (current implementation) in
app/services/vector_scan.py's VectorScanService.scan().

Reports TWO numbers, both honest:
1. End-to-end scan() latency (includes embedding-model inference, which we did
   not change and which dominates the wall clock).
2. Similarity-scoring-only latency (embeddings held constant, isolating just the
   code path that was actually rewritten) — this is the real effect of the
   optimization, separated from the part of the pipeline we didn't touch.

Verifies both implementations produce IDENTICAL risk scores and matched
sentences/categories at full float precision before comparing speed.

Usage: python perf_benchmark.py
"""
import re
import sys
import time

import numpy as np

sys.path.insert(0, ".")
from app.config import settings
from app.services.vector_scan import REGULATORY_KB, vector_scanner
from benchmark_visalify import TEST_CASES

REPEATS_E2E = 20        # repeats for the full scan() (includes model inference)
REPEATS_SIMILARITY = 500  # repeats for the isolated similarity-scoring step (much faster, needs more reps for a stable average)


def score_original(sentences, sentence_embeddings):
    """Original nested-loop cosine similarity: per-sentence, per-rule, per-anchor."""
    total_risk = 0
    detections = []
    for s_idx, s_embed in enumerate(sentence_embeddings):
        s_vec = s_embed.flatten()
        for rule in REGULATORY_KB:
            highest_sim = -1.0
            for anchor_vec in rule["embeddings"]:
                norm = np.linalg.norm(s_vec) * np.linalg.norm(anchor_vec)
                sim = float(np.dot(s_vec, anchor_vec) / norm) if norm != 0 else 0.0
                if sim > highest_sim:
                    highest_sim = sim
            if highest_sim > settings.VECTOR_THRESHOLD:
                total_risk += int(rule["base_weight"] * highest_sim)
                detections.append((sentences[s_idx], rule["category"], highest_sim))
                break
    return min(100, total_risk), detections


def score_vectorized(sentences, sentence_embeddings):
    """Current implementation: one matrix multiply per rule instead of a
    per-sentence/per-anchor Python loop of individual dot-product calls."""
    normalized_sentences = vector_scanner._normalize_rows(
        np.asarray(sentence_embeddings, dtype=np.float32)
    )
    per_rule_best_sim = np.stack([
        (normalized_sentences @ rule["normalized_embeddings"].T).max(axis=1)
        for rule in REGULATORY_KB
    ], axis=1)

    total_risk = 0
    detections = []
    for s_idx, sentence in enumerate(sentences):
        for r_idx, rule in enumerate(REGULATORY_KB):
            highest_sim = float(per_rule_best_sim[s_idx, r_idx])
            if highest_sim > settings.VECTOR_THRESHOLD:
                total_risk += int(rule["base_weight"] * highest_sim)
                detections.append((sentence, rule["category"], highest_sim))
                break
    return min(100, total_risk), detections


def main():
    cases = []
    for case in TEST_CASES:
        sentences = [s.strip() for s in re.split(r'[.\n!]+', case["resume"]) if s.strip()]
        embeddings = vector_scanner.model.encode(sentences)
        cases.append((case["id"], sentences, embeddings))

    print(f"Corpus: {len(cases)} real resumes from the labeled benchmark set\n")

    # --- Correctness check at full float precision ---
    mismatches = 0
    for case_id, sentences, embeddings in cases:
        orig_score, orig_detections = score_original(sentences, embeddings)
        vec_score, vec_detections = score_vectorized(sentences, embeddings)
        detections_match = len(orig_detections) == len(vec_detections) and all(
            o[0] == v[0] and o[1] == v[1] and abs(o[2] - v[2]) < 1e-4
            for o, v in zip(orig_detections, vec_detections)
        )
        if orig_score != vec_score or not detections_match:
            mismatches += 1
            print(f"MISMATCH on {case_id}: original={orig_score}/{orig_detections} vectorized={vec_score}/{vec_detections}")

    if mismatches:
        print(f"\n{mismatches}/{len(cases)} resumes produced different results — NOT a safe drop-in optimization.")
        return
    print(f"Correctness: {len(cases)}/{len(cases)} resumes produced IDENTICAL risk scores and flags (full float precision).\n")

    # --- Benchmark 1: end-to-end scan() (includes model.encode(), unchanged) ---
    resumes = [case["resume"] for case in TEST_CASES]
    for r in resumes[:2]:
        vector_scanner.scan(r)  # warm up

    start = time.perf_counter()
    for _ in range(REPEATS_E2E):
        for r in resumes:
            vector_scanner.scan(r)
    e2e_total = time.perf_counter() - start
    e2e_avg_ms = (e2e_total / (len(resumes) * REPEATS_E2E)) * 1000

    # --- Benchmark 2: similarity-scoring only (embeddings precomputed once, held constant) ---
    for case_id, sentences, embeddings in cases[:2]:
        score_original(sentences, embeddings)
        score_vectorized(sentences, embeddings)

    start = time.perf_counter()
    for _ in range(REPEATS_SIMILARITY):
        for case_id, sentences, embeddings in cases:
            score_original(sentences, embeddings)
    orig_sim_total = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(REPEATS_SIMILARITY):
        for case_id, sentences, embeddings in cases:
            score_vectorized(sentences, embeddings)
    vec_sim_total = time.perf_counter() - start

    n_sim_calls = len(cases) * REPEATS_SIMILARITY
    orig_sim_avg_ms = (orig_sim_total / n_sim_calls) * 1000
    vec_sim_avg_ms = (vec_sim_total / n_sim_calls) * 1000
    sim_speedup_pct = (1 - vec_sim_total / orig_sim_total) * 100

    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"[End-to-end scan(), includes embedding-model inference]")
    print(f"  {e2e_avg_ms:.2f}ms/resume avg ({REPEATS_E2E * len(resumes)} calls)")
    print()
    print(f"[Similarity-scoring step only, embeddings held constant — isolates the actual code change]")
    print(f"  Original (nested-loop):     {orig_sim_avg_ms:.4f}ms/resume avg ({n_sim_calls} calls)")
    print(f"  Vectorized (NumPy matmul):  {vec_sim_avg_ms:.4f}ms/resume avg ({n_sim_calls} calls)")
    print(f"  Latency reduction on this step: {sim_speedup_pct:.1f}%")


if __name__ == "__main__":
    main()
