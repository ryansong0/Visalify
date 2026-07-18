"""
Visalify Benchmark Harness
--------------------------
Runs a labeled set of resume/job-description pairs against your live /match
endpoint and computes real, defensible metrics:

1. Hallucination rate: % of "clean" resumes (no managerial language) that
   incorrectly received a Regulatory Compliance Risk gap.
2. Detection recall: % of "management-heavy" resumes that correctly received
   a Regulatory Compliance Risk gap.
3. Score groundedness: % of cases where the final score stayed within a
   reasonable band of the resume/JD's expected match tier (high/medium/low).
4. Rewrite completeness: average length ratio of optimized_profile vs original
   (checks for truncation).
5. Banned-word leakage: % of management-heavy resumes whose rewrite STILL
   contains a banned supervisory word (managed/led/directed/overseeing/oversaw).

Usage:
    python benchmark_visalify.py

Requires: pip install requests --break-system-packages (if not already installed)
Requires your FastAPI backend running at http://127.0.0.1:8000
"""

import requests
import re
import json
import time

API_URL = "http://127.0.0.1:8000/match"
BANNED_WORDS = ["managed", "led", "directed", "overseeing", "oversaw"]

# ---------------------------------------------------------------------------
# TEST SET: 25 labeled resume/JD pairs
# expected_management: True if the resume contains real supervisory language
# expected_tier: "high" (>60), "medium" (30-60), "low" (<30) — rough expected match band
# ---------------------------------------------------------------------------

TEST_CASES = [
    # --- Clean, high-match resumes (no management language) ---
    {
        "id": "clean_high_1",
        "resume": "Backend Engineer with 5 years of experience building distributed systems in Python and Go. Designed and implemented a real-time event processing pipeline using Kafka. Built and optimized PostgreSQL schemas for a high-throughput billing system. Implemented containerized deployments using Docker and Kubernetes. Skills: Python, Go, Kubernetes, Docker, PostgreSQL, Kafka.",
        "job_description": "Backend Engineer (TN visa eligible). Individual contributor role. Requirements: Strong experience with Python or Go, Kubernetes and Docker, message queues (Kafka), database schema design.",
        "expected_management": False,
        "expected_tier": "high",
    },
    {
        "id": "clean_high_2",
        "resume": "Machine Learning Engineer with 3 years of experience. Trained and deployed NLP classification models using PyTorch and Hugging Face Transformers. Built data pipelines with Airflow and Spark. Wrote unit tests achieving high coverage on model-serving code. Skills: Python, PyTorch, Spark, Airflow, Docker.",
        "job_description": "ML Engineer (H-1B sponsorship). Requirements: PyTorch or TensorFlow, NLP experience, Spark or similar distributed data tools, strong testing discipline.",
        "expected_management": False,
        "expected_tier": "high",
    },
    {
        "id": "clean_high_3",
        "resume": "Frontend Engineer with 4 years building React applications. Implemented component libraries with TypeScript and Storybook. Optimized bundle size using Webpack code-splitting, reducing load time. Built accessible UI components following WCAG guidelines. Skills: React, TypeScript, Webpack, CSS, Accessibility.",
        "job_description": "Senior Frontend Engineer. Requirements: React, TypeScript, performance optimization, accessibility experience, component design systems.",
        "expected_management": False,
        "expected_tier": "high",
    },
    {
        "id": "clean_high_4",
        "resume": "DevOps Engineer with 6 years automating infrastructure. Built Terraform modules for multi-region AWS deployments. Implemented CI/CD pipelines using GitHub Actions. Wrote Kubernetes operators for automated scaling. Skills: Terraform, AWS, Kubernetes, GitHub Actions, Python.",
        "job_description": "DevOps Engineer (TN visa eligible). Requirements: Terraform, AWS, Kubernetes, CI/CD pipeline experience.",
        "expected_management": False,
        "expected_tier": "high",
    },
    {
        "id": "clean_high_5",
        "resume": "Data Engineer with 4 years building ETL pipelines. Designed and implemented Spark jobs processing large datasets daily. Built a data warehouse using Snowflake and dbt. Automated data quality checks with Great Expectations. Skills: Spark, Snowflake, dbt, Python, SQL.",
        "job_description": "Data Engineer (H-1B eligible). Requirements: Spark, Snowflake or similar warehouse, dbt, strong SQL, data quality practices.",
        "expected_management": False,
        "expected_tier": "high",
    },
    # --- Clean, low-match resumes (real skill gap, no management language) ---
    {
        "id": "clean_low_1",
        "resume": "Software Engineer with 3 years of experience. Built REST APIs in Python using Flask. Wrote unit tests and worked on a small internal tool for tracking customer support tickets. Skills: Python, Flask, Git, SQL.",
        "job_description": "Senior Systems Engineer (H-1B sponsorship). Requirements: 5+ years Go and Rust, Kubernetes and service mesh (Istio), distributed consensus systems, gRPC and protocol buffers.",
        "expected_management": False,
        "expected_tier": "low",
    },
    {
        "id": "clean_low_2",
        "resume": "Junior Web Developer with 1 year of experience. Built simple websites using HTML, CSS, and jQuery. Skills: HTML, CSS, jQuery, WordPress.",
        "job_description": "Senior Machine Learning Engineer. Requirements: Deep learning, PyTorch, distributed training, MLOps, model deployment at scale.",
        "expected_management": False,
        "expected_tier": "low",
    },
    {
        "id": "clean_low_3",
        "resume": "Mobile Developer with 2 years building iOS apps in Swift. Built UI components using SwiftUI. Skills: Swift, SwiftUI, Xcode.",
        "job_description": "Backend Infrastructure Engineer. Requirements: Go, distributed databases, Kubernetes operators, Kafka, gRPC.",
        "expected_management": False,
        "expected_tier": "low",
    },
    {
        "id": "clean_low_4",
        "resume": "QA Analyst with 2 years of manual testing experience. Wrote test cases and executed regression testing cycles. Skills: Manual testing, Jira, Excel.",
        "job_description": "Senior Backend Engineer. Requirements: Python or Java, Kubernetes, distributed systems design, high-throughput services.",
        "expected_management": False,
        "expected_tier": "low",
    },
    {
        "id": "clean_low_5",
        "resume": "Data Analyst with 2 years using Excel and Tableau for reporting. Built dashboards for sales metrics. Skills: Excel, Tableau, SQL basics.",
        "job_description": "Senior Data Engineer. Requirements: Spark, Kafka, distributed data pipelines, Python, cloud data warehousing at scale.",
        "expected_management": False,
        "expected_tier": "low",
    },
    # --- Management-heavy resumes (real supervisory language) ---
    {
        "id": "mgmt_1",
        "resume": "Engineering Manager with 6 years of experience. Managed a team of 8 backend engineers. Led the technical strategy for migrating to microservices. Directed sprint planning and resource allocation. Oversaw hiring and performance reviews. Skills: Python, Go, Kubernetes, team leadership.",
        "job_description": "Senior Backend Engineer (H-1B sponsorship). Individual contributor role, no people management. Requirements: Python or Go, Kubernetes, system design ownership.",
        "expected_management": True,
        "expected_tier": "medium",
    },
    {
        "id": "mgmt_2",
        "resume": "Product Manager with 4 years of experience. Managed the product roadmap for a fintech platform. Led cross-functional teams of designers and engineers. Directed go-to-market strategy. Oversaw a $2M budget. Skills: Product strategy, Agile, stakeholder management.",
        "job_description": "Senior Software Engineer (TN visa eligible). Individual contributor. Requirements: Python, distributed systems, hands-on coding.",
        "expected_management": True,
        "expected_tier": "low",
    },
    {
        "id": "mgmt_3",
        "resume": "Technical Lead with 5 years of experience. Managed a team of 5 engineers building payment systems. Led architecture decisions for scaling the platform. Directed code review processes. Still writes code daily in Python and Java. Skills: Python, Java, AWS, team leadership.",
        "job_description": "Senior Backend Engineer (H-1B). Individual contributor role. Requirements: Python or Java, AWS, distributed systems.",
        "expected_management": True,
        "expected_tier": "medium",
    },
    {
        "id": "mgmt_4",
        "resume": "IT Manager with 7 years of experience. Managed a team of 10 support staff. Directed helpdesk operations and oversaw ticket escalation processes. Led vendor negotiations for hardware contracts. Skills: ITIL, team leadership, vendor management.",
        "job_description": "Senior Systems Engineer (H-1B). Individual contributor. Requirements: Linux administration, scripting, cloud infrastructure, hands-on troubleshooting.",
        "expected_management": True,
        "expected_tier": "low",
    },
    {
        "id": "mgmt_5",
        "resume": "Engineering Manager with 8 years of experience. Managed two engineering pods totaling 12 engineers. Led quarterly OKR planning. Directed the technical roadmap for the platform team. Oversaw on-call rotation policies. Occasionally contributes code in Python. Skills: Python, leadership, Agile/Scrum.",
        "job_description": "Senior Backend Engineer (TN visa eligible). Individual contributor role. Requirements: Python, system design, hands-on ownership of services.",
        "expected_management": True,
        "expected_tier": "medium",
    },
    # --- Mixed: some management language but genuinely light/borderline ---
    {
        "id": "mixed_1",
        "resume": "Senior Software Engineer with 5 years of experience. Led the design and implementation of a payment processing service handling high transaction volume. Mentored 2 junior engineers on code quality practices. Built services in Python and Go. Skills: Python, Go, Kubernetes, mentorship.",
        "job_description": "Senior Backend Engineer (H-1B sponsorship). Individual contributor role with some technical mentorship expected. Requirements: Python or Go, Kubernetes, distributed systems.",
        "expected_management": True,
        "expected_tier": "high",
    },
    {
        "id": "mixed_2",
        "resume": "Software Engineer with 4 years of experience. Directed the technical design of a caching layer that improved API response times. Built the implementation in Java. Skills: Java, Redis, distributed caching.",
        "job_description": "Senior Backend Engineer (TN visa eligible). Requirements: Java, distributed caching systems, high-performance API design.",
        "expected_management": True,
        "expected_tier": "high",
    },
    {
        "id": "mixed_3",
        "resume": "Data Scientist with 3 years of experience. Led a research initiative on fraud detection models, building and deploying the final model in production. Skills: Python, scikit-learn, fraud detection, statistical modeling.",
        "job_description": "Senior Data Scientist (H-1B). Requirements: Python, machine learning, fraud detection experience, production deployment.",
        "expected_management": True,
        "expected_tier": "high",
    },
    # --- More clean high/medium diversity ---
    {
        "id": "clean_med_1",
        "resume": "Backend Engineer with 3 years of experience in Python and Django. Built REST APIs and integrated third-party payment gateways. Skills: Python, Django, PostgreSQL, REST APIs.",
        "job_description": "Senior Backend Engineer (H-1B). Requirements: Python, Go, Kubernetes, distributed systems, message queues.",
        "expected_management": False,
        "expected_tier": "medium",
    },
    {
        "id": "clean_med_2",
        "resume": "Full-Stack Engineer with 3 years of experience. Built features using React and Node.js. Worked with MongoDB for data storage. Skills: React, Node.js, MongoDB, JavaScript.",
        "job_description": "Senior Backend Engineer (TN visa eligible). Requirements: Python or Go, Kubernetes, PostgreSQL, distributed systems.",
        "expected_management": False,
        "expected_tier": "medium",
    },
    {
        "id": "clean_med_3",
        "resume": "Cloud Engineer with 2 years of experience using AWS Lambda and API Gateway. Built serverless data processing workflows. Skills: AWS Lambda, Python, Serverless, API Gateway.",
        "job_description": "Senior Backend Engineer (H-1B). Requirements: Python, Kubernetes, Docker, distributed systems, database design.",
        "expected_management": False,
        "expected_tier": "medium",
    },
    {
        "id": "clean_med_4",
        "resume": "Security Engineer with 3 years of experience. Conducted vulnerability assessments and implemented security controls in AWS environments. Skills: AWS Security, Python scripting, penetration testing basics.",
        "job_description": "Senior Backend Engineer (TN visa eligible). Requirements: Python, Kubernetes, distributed systems, database schema design.",
        "expected_management": False,
        "expected_tier": "medium",
    },
    {
        "id": "clean_med_5",
        "resume": "Platform Engineer with 3 years of experience building internal developer tools. Built CLI tools in Go for deployment automation. Skills: Go, Docker, internal tooling.",
        "job_description": "Senior Backend Engineer (H-1B). Requirements: Go, Kubernetes, distributed systems, message queues, database optimization.",
        "expected_management": False,
        "expected_tier": "medium",
    },
    {
        "id": "clean_high_6",
        "resume": "Site Reliability Engineer with 5 years of experience. Built monitoring and alerting systems using Prometheus and Grafana. Automated incident response with custom Python tooling. Reduced on-call noise significantly through smarter alert thresholds. Skills: Python, Prometheus, Grafana, Kubernetes, SRE practices.",
        "job_description": "Senior SRE (H-1B sponsorship). Individual contributor role. Requirements: Python, Kubernetes, monitoring/observability tools, incident response.",
        "expected_management": False,
        "expected_tier": "high",
    },
    {
        "id": "clean_high_7",
        "resume": "Backend Engineer with 4 years of experience in Go. Built high-throughput gRPC services for a logistics platform. Implemented distributed tracing using OpenTelemetry. Skills: Go, gRPC, OpenTelemetry, Kubernetes, distributed systems.",
        "job_description": "Senior Backend Engineer (TN visa eligible). Individual contributor. Requirements: Go, gRPC, distributed systems, observability tooling.",
        "expected_management": False,
        "expected_tier": "high",
    },
]


def has_banned_words(text: str) -> list:
    """Return list of banned words found in text (case-insensitive, whole-word only).

    A plain substring check would flag words like "enabled" or "modeled" as leaking
    "led", since "led" is a substring of their "-ed" past-tense ending. Match on word
    boundaries instead, consistent with the app's own BANNED_TERMS_PATTERN.
    """
    return [w for w in BANNED_WORDS if re.search(rf"\b{re.escape(w)}\b", text, re.IGNORECASE)]


def run_benchmark():
    results = []
    print(f"Running {len(TEST_CASES)} test cases against {API_URL}...\n")

    for i, case in enumerate(TEST_CASES, 1):
        print(f"[{i}/{len(TEST_CASES)}] {case['id']}...", end=" ", flush=True)
        try:
            resp = requests.post(
                API_URL,
                json={
                    "candidate_profile": case["resume"],
                    "job_description": case["job_description"],
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

            gaps = data.get("detected_gaps", [])
            has_compliance_gap = any(
                g.get("category") == "Regulatory Compliance Risk" for g in gaps
            )
            score = data.get("overall_match_score", 0)
            optimized = data.get("optimized_profile", "")

            original_banned = has_banned_words(case["resume"])
            rewritten_banned = has_banned_words(optimized) if case["expected_management"] else []

            length_ratio = len(optimized.strip()) / max(len(case["resume"].strip()), 1)

            results.append({
                "id": case["id"],
                "expected_management": case["expected_management"],
                "detected_management": has_compliance_gap,
                "expected_tier": case["expected_tier"],
                "score": score,
                "length_ratio": round(length_ratio, 2),
                "banned_words_remaining": rewritten_banned,
            })
            print(f"score={score}, compliance_flagged={has_compliance_gap}, length_ratio={length_ratio:.2f}")

        except Exception as e:
            print(f"FAILED: {e}")
            results.append({
                "id": case["id"], "error": str(e)
            })

        time.sleep(0.5)  # be gentle on local Ollama

    print("\n" + "=" * 70)
    print("SUMMARY METRICS")
    print("=" * 70)

    valid = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]

    if failed:
        print(f"\nWARNING: {len(failed)} requests failed entirely (see errors above)")

    if not valid:
        print("No valid results to analyze.")
        return

    # 1. Hallucination rate (false positives on clean resumes)
    clean_cases = [r for r in valid if not r["expected_management"]]
    false_positives = [r for r in clean_cases if r["detected_management"]]
    hallucination_rate = len(false_positives) / len(clean_cases) * 100 if clean_cases else 0

    # 2. Detection recall (true positives on management-heavy resumes)
    mgmt_cases = [r for r in valid if r["expected_management"]]
    true_positives = [r for r in mgmt_cases if r["detected_management"]]
    detection_recall = len(true_positives) / len(mgmt_cases) * 100 if mgmt_cases else 0

    # 3. Score groundedness (rough band check)
    tier_bands = {"high": (60, 100), "medium": (30, 65), "low": (0, 40)}
    grounded = 0
    for r in valid:
        lo, hi = tier_bands[r["expected_tier"]]
        if lo <= r["score"] <= hi:
            grounded += 1
    score_groundedness = grounded / len(valid) * 100 if valid else 0

    # 4. Rewrite completeness (avg length ratio, flag if <0.6 = truncated)
    avg_length_ratio = sum(r["length_ratio"] for r in valid) / len(valid)
    truncated_count = sum(1 for r in valid if r["length_ratio"] < 0.6)

    # 5. Banned-word leakage (management resumes only)
    leaked = [r for r in mgmt_cases if r["banned_words_remaining"]]
    leakage_rate = len(leaked) / len(mgmt_cases) * 100 if mgmt_cases else 0

    print(f"\nTotal test cases run: {len(valid)}/{len(TEST_CASES)} ({len(failed)} failed)")
    print(f"\n1. Hallucination rate (false compliance flags on clean resumes): {hallucination_rate:.1f}%  ({len(false_positives)}/{len(clean_cases)})")
    print(f"2. Detection recall (correctly flagged management-heavy resumes): {detection_recall:.1f}%  ({len(true_positives)}/{len(mgmt_cases)})")
    print(f"3. Score groundedness (score landed in expected tier band): {score_groundedness:.1f}%  ({grounded}/{len(valid)})")
    print(f"4. Avg rewrite length ratio (1.0 = same length as original): {avg_length_ratio:.2f}")
    print(f"   Truncated rewrites (<60% of original length): {truncated_count}/{len(valid)}")
    print(f"5. Banned-word leakage in rewrites (management cases only): {leakage_rate:.1f}%  ({len(leaked)}/{len(mgmt_cases)})")

    if false_positives:
        print(f"\nFalse positive IDs: {[r['id'] for r in false_positives]}")
    missed = [r for r in mgmt_cases if not r["detected_management"]]
    if missed:
        print(f"Missed detection IDs: {[r['id'] for r in missed]}")
    if leaked:
        print(f"Leakage IDs: {[(r['id'], r['banned_words_remaining']) for r in leaked]}")

    # Save raw results to file for your records / resume citation
    with open("benchmark_results.json", "w") as f:
        json.dump({
            "results": results,
            "summary": {
                "total_cases": len(TEST_CASES),
                "hallucination_rate_pct": round(hallucination_rate, 1),
                "detection_recall_pct": round(detection_recall, 1),
                "score_groundedness_pct": round(score_groundedness, 1),
                "avg_rewrite_length_ratio": round(avg_length_ratio, 2),
                "banned_word_leakage_pct": round(leakage_rate, 1),
            }
        }, f, indent=2)
    print("\nFull results saved to benchmark_results.json")


if __name__ == "__main__":
    run_benchmark()