# Visalify

**Live demo:** [visalify-app.vercel.app](https://visalify-app.vercel.app)

TN and H-1B visa rules require most specialty-occupation roles to stay hands-on technical, not managerial. The problem is that standard resume advice pushes exactly the kind of language ("managed a team," "led the initiative") that can read as a red flag to an immigration officer. Visalify checks a resume against a target job description, flags any supervisory language that could put a visa at risk, and rewrites it into hands-on technical framing, keeping every real skill and detail intact.

![Visalify demo: flags supervisory language and rewrites it to compliant technical framing](./screenshots/demo.png)

## How it works

1. **Pre-scan.** A keyword pass (regex-based word matching) and a lexical similarity pass (TF-IDF cosine similarity against a small regulatory knowledge base) each independently flag supervisory language in the resume. Both run on plain NumPy and scikit-learn, so there's no ML model to download and the backend stays small enough for free-tier hosting.
2. **Detection.** A Groq-hosted `llama-3.3-70b-versatile` call scores the resume against the job description and reports compliance risks and skill gaps. The pre-scan decides *whether* a compliance risk exists; the LLM only handles phrasing and skill-gap analysis. Early on, letting the LLM make that call directly caused it to miss most real risks, so that decision was moved to the deterministic pre-scan instead.
3. **Rewrite.** A second, separate LLM call reframes any flagged sentences around individual technical contribution. A regex-based scrub runs afterward as a last check, so a banned supervisory term can never make it into the output.

## Verified results

Measured against a labeled set of 25 resumes (`benchmark_visalify.py`):

| Metric | Result |
|---|---|
| Detection recall (management-heavy resumes correctly flagged) | 100% (8/8) |
| Hallucination rate (false positives on clean resumes) | 0% (0/17) |
| Score groundedness (match score in expected tier band) | 100% (25/25) |
| Banned-word leakage in rewrites | 0% (0/8) |
| Overall classification accuracy | 100% (25/25) |

`perf_benchmark.py` covers a separate change: swapping a nested-loop cosine-similarity comparison for vectorized NumPy matrix operations. It checks the two produce identical output first, then measures a 86% latency drop on that step.

Both scripts are meant to be run, not just read - see below.

## Stack

- **Backend**: FastAPI, scikit-learn (TF-IDF), Groq API
- **Frontend**: Next.js
- Deployed as two separate Vercel projects from this repo: the backend as a Python function, the frontend from `visalify-web/`

## Running locally

```bash
# Backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd visalify-web
npm install
npm run dev
```

You'll need a free [Groq API key](https://console.groq.com/keys) in a `.env` file (see `.env.example`).

## Reproducing the benchmarks

```bash
python benchmark_visalify.py   # accuracy: recall, hallucination rate, leakage
python perf_benchmark.py       # correctness + latency of the vectorized similarity scoring
```
