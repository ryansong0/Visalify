import json
import os
import spacy

nlp = spacy.load("en_core_web_sm")

RULES_PATH = os.path.join(os.path.dirname(__file__), "../rules/prohibited_terms.json")

def analyze_text(text: str):
    with open(RULES_PATH, "r") as f:
        rules = json.load(f)
    findings = []

    doc = nlp(text)
    text_lower = text.lower()

    for item in rules["managerial_terms"]:
        term = item["term"]

        start = 0
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
                    "reason": item["reason"]
                })

            start = index + len(term)

    return findings