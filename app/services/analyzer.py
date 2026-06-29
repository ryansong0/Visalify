import json
import os

RULES_PATH = os.path.join(os.path.dirname(__file__), "../rules/prohibited_terms.json")

def load_rules():
    with open(RULES_PATH, "r") as f:
        return json.load(f)

def analyze_text(text: str):
    rules = load_rules()
    findings = []

    text_lower = text.lower()

    for item in rules["managerial_terms"]:
        term = item["term"]

        start = 0
        while True:
            index = text_lower.find(term, start)

            if index == -1:
                break

            findings.append({
                "term": term,
                "matched_text": text[index: index + len(term)],
                "start": index,
                "end": index + len(term),
                "severity": item["severity"],
                "reason": item["reason"]
            })

            start = index + len(term)

    return findings