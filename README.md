---
title: Visalify
emoji: 🛡️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Visalify

Visalify checks a candidate's resume against a target job description for TN/H-1B-style visa roles, flags language that could read as a visa-compliance risk (supervisory/managerial phrasing that undercuts an "individual contributor" role classification), and rewrites the resume to reframe that language as hands-on technical work — without inventing skills or dropping content.

## How it works

1. **Pre-scan** — a keyword pass (spaCy lemmatization) and a semantic pass (sentence-transformer embeddings against a small regulatory knowledge base) independently flag any supervisory/managerial language in the resume.
2. **Detection** — an LLM call (Groq, `llama-3.3-70b-versatile`) scores the resume/job match and reports compliance risks and skill gaps. The pre-scan is the deterministic source of truth for *whether* a compliance risk exists — the LLM's role is limited to phrasing and skill-gap analysis, not judgment calls the small-model pass turned out to be unreliable at.
3. **Rewrite** — a second, separate LLM call reframes any flagged sentences into individual-technical-contribution language, with a deterministic regex-based scrub as a final safety net so banned supervisory terms can never leak through.

## Verified results

Measured against a labeled 25-resume validation set (`benchmark_visalify.py`):

| Metric | Result |
|---|---|
| Detection recall (management-heavy resumes correctly flagged) | 100% (8/8) |
| Hallucination rate (false positives on clean resumes) | 0% (0/17) |
| Banned-word leakage in rewrites | 0% (0/8) |
| Overall classification accuracy | 100% (25/25) |

Separately, `perf_benchmark.py` verifies that replacing a nested-loop cosine-similarity comparison with vectorized NumPy matrix operations produces **bit-for-bit identical output** while cutting the similarity-scoring step's latency by **86%**.

Both scripts are runnable and reproducible — see below.

## Stack

- **Backend**: FastAPI, spaCy, sentence-transformers, Groq API (deployed on Hugging Face Spaces)
- **Frontend**: Next.js (deployed on Vercel)

## Running locally

```bash
# Backend
pip install -r requirements-backend.txt
python -m spacy download en_core_web_sm
uvicorn app.main:app --reload

# Frontend
cd visalify-web
npm install
npm run dev
```

Requires a free [Groq API key](https://console.groq.com/keys) in a `.env` file (see `.env.example`).

## Reproducing the benchmarks

```bash
python benchmark_visalify.py   # accuracy: recall, hallucination rate, leakage
python perf_benchmark.py       # correctness + latency of the vectorized similarity scoring
```
