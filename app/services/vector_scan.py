import numpy as np
import re
from sentence_transformers import SentenceTransformer
from app.config import settings
from app.schemas import RiskFlag

REGULATORY_KB = [
    {
        "category": "Management Consultant",
        "anchor_phrases": [
            "managing day to day operations and staff",
            "execution of corporate business strategy",
            "operating in a daily managerial or executive capacity",
            "directing product lines and project management timelines"
        ],
        "reason": "Explicitly flagged under 8 CFR 214.6. Management consultants must strictly operate in an advisory capacity, not operational management.",
        "alternative": "Reframe responsibilities around 'strategic evaluation' or 'process auditing'.",
        "base_weight": 60
    },
    {
        "category": "Non-Statutory Product Management",
        "anchor_phrases": [
            "owning product roadmap and business market fit",
            "cross functional team leadership and revenue metrics",
            "managing feature prioritization and marketing alignment",
            "product manager responsible for lifecycle execution"
        ],
        "reason": "Product Management is not a recognized statutory profession under the TN classification system.",
        "alternative": "Re-evaluate if duties align with 'Computer Systems Analyst' or 'Engineer'.",
        "base_weight": 85
    },
    {
    "category": "Engineering/Technical Team Management",
    "anchor_phrases": [
        "managed a team of engineers building software",
        "led technical strategy and architecture decisions for a team",
        "oversaw hiring, performance reviews, and staff development",
        "directed sprint planning and engineering resource allocation",
        "led a research or engineering initiative from conception to production",
        "mentored and supervised junior engineers on a team"
    ],
    "reason": "Supervisory management of engineering/technical staff is generally outside the scope of specialty-occupation or TN/H-1B individual-contributor roles.",
    "alternative": "Reframe around individual technical contribution: architecture, implementation, hands-on delivery, rather than people oversight.",
    "base_weight": 65
}
]

class VectorScanService:
    def __init__(self):
        print(f"Initializing Semantic Space via {settings.EMBEDDING_MODEL}...")
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self._bake_knowledge_base()

    @staticmethod
    def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
        """L2-normalize each row to a unit vector; zero rows are left as zero
        instead of dividing by zero, matching the original per-pair norm check."""
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def _bake_knowledge_base(self):
        for rule in REGULATORY_KB:
            encoded = np.asarray(self.model.encode(rule["anchor_phrases"]), dtype=np.float32)
            rule["embeddings"] = encoded
            rule["normalized_embeddings"] = self._normalize_rows(encoded)

    def compute_match_score(self, candidate_profile: str, job_description: str) -> int:
        profile_embed = self.model.encode([candidate_profile])[0].flatten()
        jd_embed = self.model.encode([job_description])[0].flatten()
        norm = np.linalg.norm(profile_embed) * np.linalg.norm(jd_embed)
        similarity = float(np.dot(profile_embed, jd_embed) / norm) if norm != 0 else 0.0
        scaled = max(0, min(100, int((similarity - 0.2) / 0.6 * 100)))
        return scaled

    def scan(self, latest_input: str) -> tuple:
        flags = []
        total_risk = 0

        if not latest_input.strip():
            return 0, "Safe", True, []

        sentences = [s.strip() for s in re.split(r'[.\n!]+', latest_input) if s.strip()]
        if not sentences:
            return 0, "Safe", True, []

        sentence_embeddings = np.asarray(self.model.encode(sentences), dtype=np.float32)
        normalized_sentences = self._normalize_rows(sentence_embeddings)

        # Vectorized cosine similarity: one matrix multiply per rule (against every
        # anchor phrase at once) instead of a per-sentence/per-anchor Python loop of
        # individual dot-product calls. Numerically identical to the scalar version
        # since dotting two unit vectors is exactly cosine similarity.
        per_rule_best_sim = np.stack([
            (normalized_sentences @ rule["normalized_embeddings"].T).max(axis=1)
            for rule in REGULATORY_KB
        ], axis=1)  # shape: (n_sentences, n_rules)

        for s_idx, sentence in enumerate(sentences):
            for r_idx, rule in enumerate(REGULATORY_KB):
                highest_sim = float(per_rule_best_sim[s_idx, r_idx])

                if highest_sim > settings.VECTOR_THRESHOLD:
                    scaled_penalty = int(rule["base_weight"] * highest_sim)
                    total_risk += scaled_penalty
                    flags.append(RiskFlag(
                        matched_text=sentence,
                        reason=f"Matched context via category '{rule['category']}' (Confidence: {highest_sim:.2f}). {rule['reason']}",
                        suggested_alternative=rule["alternative"]
                    ))
                    break

        risk_score = min(100, total_risk)
        level = "Critical" if risk_score >= 75 else "High" if risk_score >= 45 else "Medium" if risk_score >= 20 else "Safe"
        requires_more = len(latest_input.split()) < 15 or risk_score == 0

        return risk_score, level, requires_more, flags

vector_scanner = VectorScanService()