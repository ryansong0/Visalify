import json
import os
import spacy

nlp = spacy.load("en_core_web_sm")

RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "rules", "prohibited_terms.json")

def analyze_text(text: str):
    with open(RULES_PATH, "r") as f:
        rules = json.load(f)
    findings = []

    doc = nlp(text)
    text_lower = text.lower()

    severity_weights = {
        "low": 10,
        "medium": 30,
        "high": 70,
        "critical": 100
    }

    total_possible_risk = 0
    accumulated_risk = 0

    for item in rules["managerial_terms"]:
        term = item["term"]

        start = 0
        severity = item.get("severity", "low").lower()
        weight = severity_weights.get(severity, 10)
        while True:
            index = text_lower.find(term, start)

            if index == -1:
                break

            is_false_positive = False

            for token in doc:
                if token.idx <= index < (token.idx + len(token.text)):
                    children_text = [child.text.lower() for child in token.children]

                    technical_objects = ["pipeline", "pipelines", "system", "systems", "database", "databases", "code"]
                    if any(obj in children_text for obj in technical_objects):
                        is_false_positive = True
                    break

            if not is_false_positive:
                findings.append({
                    "term": term,
                    "matched_text": text[index: index + len(term)],
                    "start": index,
                    "end": index + len(term),
                    "severity": item["severity"],
                    "reason": item["reason"],
                    "suggested_alternative": item.get("suggestion", "rephrase phrase structurally")
                })

                accumulated_risk += weight

            start = index + len(term)

    final_risk_score = min(accumulated_risk, 100)

    if final_risk_score >= 70:
        overall_risk = "Critical"
    elif final_risk_score >= 40:
        overall_risk = "Medium"
    elif final_risk_score > 0:
        overall_risk = "Low"
    else:
        overall_risk = "Safe"

    return {
        "risk_score": final_risk_score,
        "overall_risk_level": overall_risk,
        "flags": findings
    }