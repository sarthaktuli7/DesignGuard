"""
The agent pipeline for DesignGuard. Same Triage/Resolution/QA/Escalation
split as PaymentGuard, applied to design-system compliance instead of
payment disputes:

  1. TriageAgent      - scores the violation for exception-merit (ensemble model)
  2. ResolutionAgent  - retrieves precedent and drafts a recommended action
  3. QAAgent          - policy gate: can BLOCK a recommendation outright
  4. EscalationAgent  - routes to auto-fix or a human design-system-review queue

The hard rule carried over from PaymentGuard: the QA agent's block is
enforced in code, not merely suggested - any brand-critical violation, any
high-visibility screen above the confidence floor, and any ungrounded
recommendation gets forced to a human, regardless of how confident the
Triage model or an LLM-drafted recommendation is.
"""
import json
import pickle
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd

from app.retrieval import PrecedentRetriever

MODEL_PATH = "/home/claude/designguard/models/risk_model.pkl"
DB_PATH = "/home/claude/designguard/designguard.db"

# Policy thresholds - the QA agent's rulebook, deliberately explicit and
# readable so a design-system lead could audit this file directly.
POLICY = {
    "min_confidence_for_auto_fix": 0.70,
    "always_escalate_severity": {"brand_critical"},
    "max_prior_exceptions_for_auto": 1,
    "always_escalate_high_visibility": True,
}


def _load_model():
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


class TriageAgent:
    """Scores a flagged violation and produces an explainable merit assessment."""

    def __init__(self):
        self.artifact = _load_model()
        self.model = self.artifact["model"]
        self.scaler = self.artifact["scaler"]
        self.feature_columns = self.artifact["feature_columns"]
        self.importances = self.artifact["feature_importances"]
        self.train_means = self.artifact["train_means"]
        self.train_stds = self.artifact["train_stds"]

    def _build_features(self, element):
        row = {col: 0 for col in self.feature_columns}
        row["deviation"] = element["deviation"]
        row["prior_exceptions_count"] = element["prior_exceptions_count"]
        row["is_high_visibility"] = element["is_high_visibility"]
        type_col = f"type_{element['violation_type']}"
        if type_col in row:
            row[type_col] = 1
        sev_col = f"sev_{element['severity']}"
        if sev_col in row:
            row[sev_col] = 1
        return row

    def _explain(self, features):
        contributions = []
        for col in self.feature_columns:
            mean = self.train_means.get(col, 0)
            std = self.train_stds.get(col, 1) or 1
            z = (features[col] - mean) / std
            weight = self.importances.get(col, 0)
            contributions.append((col, round(z * weight, 4)))
        contributions.sort(key=lambda x: -abs(x[1]))
        return contributions[:5]

    def score(self, element):
        features = self._build_features(element)
        X = pd.DataFrame([[features[c] for c in self.feature_columns]], columns=self.feature_columns)
        X_scaled = self.scaler.transform(X)
        prob_merit = float(self.model.predict_proba(X_scaled)[0][1])
        confidence = round(abs(prob_merit - 0.5) * 2, 3)
        explanation = self._explain(features)

        return {
            "merit_score": round(prob_merit, 3),
            "confidence": confidence,
            "top_factors": explanation,
        }


class ResolutionAgent:
    """Retrieves precedent and drafts a recommended action for the violation.

    Drafting runs two ways, chosen automatically per call:
      - LLM mode: if ANTHROPIC_API_KEY is set and `anthropic` is installed,
        Claude drafts the recommendation and rationale (see llm_resolution.py).
      - Deterministic mode: otherwise, a similarity-weighted vote over
        retrieved precedent picks the action. No network call required.
    Either way, the QA Agent downstream enforces the same policy gate
    regardless of which method produced the draft.
    """

    def __init__(self):
        self.retriever = PrecedentRetriever()

    def draft(self, element, triage_result):
        precedent = self.retriever.retrieve(
            element["designer_note"], element["violation_type"], element["severity"]
        )

        from app.llm_resolution import llm_available, draft_with_llm
        if llm_available():
            try:
                return draft_with_llm(element, triage_result, precedent)
            except Exception as exc:
                print(f"[ResolutionAgent] LLM drafting failed ({exc}); using deterministic fallback.")

        return self._draft_deterministic(element, triage_result, precedent)

    def _draft_deterministic(self, element, triage_result, precedent):
        if not precedent:
            return {
                "recommended_action": "flag_for_review",
                "rationale": "No comparable precedent found in the resolved-case history; "
                             "recommending design-system team review before any auto-action.",
                "cited_cases": [],
                "grounded": False,
                "method": "deterministic",
            }

        vote_weights = {}
        for case in precedent:
            vote_weights[case["resolution_type"]] = vote_weights.get(case["resolution_type"], 0) + case["similarity"]
        recommended = max(vote_weights, key=vote_weights.get)

        cited_ids = [c["case_id"] for c in precedent]
        rationale = (
            f"Recommending '{recommended.replace('_', ' ')}' based on {len(precedent)} similar past case(s) "
            f"({', '.join(cited_ids)}) and a model merit score of {triage_result['merit_score']}."
        )

        return {
            "recommended_action": recommended,
            "rationale": rationale,
            "cited_cases": precedent,
            "grounded": True,
            "method": "deterministic",
        }


class QAAgent:
    """Policy gate. Can block a recommendation from auto-executing."""

    def review(self, element, triage_result, resolution_draft):
        reasons_to_block = []

        if element["severity"] in POLICY["always_escalate_severity"]:
            reasons_to_block.append("brand-critical violations always require design-system review")

        if element["is_high_visibility"] and POLICY["always_escalate_high_visibility"]:
            reasons_to_block.append("high-visibility screens always require human review")

        if triage_result["confidence"] < POLICY["min_confidence_for_auto_fix"]:
            reasons_to_block.append(
                f"model confidence {triage_result['confidence']} below required "
                f"{POLICY['min_confidence_for_auto_fix']}"
            )

        if element["prior_exceptions_count"] > POLICY["max_prior_exceptions_for_auto"]:
            reasons_to_block.append(
                f"file has {element['prior_exceptions_count']} prior exceptions, above auto-fix limit"
            )

        if not resolution_draft["grounded"]:
            reasons_to_block.append("recommendation is not grounded in any retrieved precedent")

        blocked = len(reasons_to_block) > 0
        return {
            "policy_blocked": blocked,
            "block_reasons": reasons_to_block,
        }


class EscalationAgent:
    """Final routing: auto-fix, or hand off to the human design-system review queue."""

    def route(self, element, qa_result):
        if qa_result["policy_blocked"]:
            return "pending_human_review"
        return "auto_resolved"


class DesignGuardPipeline:
    """Orchestrates all four agents against one flagged element and writes the audit trail."""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.triage = TriageAgent()
        self.resolution = ResolutionAgent()
        self.qa = QAAgent()
        self.escalation = EscalationAgent()

    def _log(self, cur, element_id, stage, agent, detail):
        cur.execute(
            "INSERT INTO audit_trail (element_id, stage, agent, detail, timestamp) VALUES (?,?,?,?,?)",
            (element_id, stage, agent, json.dumps(detail), datetime.utcnow().isoformat()),
        )

    def process(self, element_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        element = dict(cur.execute("SELECT * FROM design_elements WHERE element_id=?", (element_id,)).fetchone())

        triage_result = self.triage.score(element)
        self._log(cur, element_id, "triage", "TriageAgent", triage_result)

        resolution_draft = self.resolution.draft(element, triage_result)
        self._log(cur, element_id, "resolution_draft", "ResolutionAgent", resolution_draft)

        qa_result = self.qa.review(element, triage_result, resolution_draft)
        self._log(cur, element_id, "qa_review", "QAAgent", qa_result)

        final_status = self.escalation.route(element, qa_result)
        self._log(cur, element_id, "escalation", "EscalationAgent", {"final_status": final_status})

        cur.execute(
            """INSERT INTO decisions
               (element_id, merit_score, confidence, recommended_action, retrieved_case_ids,
                policy_blocked, block_reason, final_status, human_reviewer, created_at, resolved_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                element_id,
                triage_result["merit_score"],
                triage_result["confidence"],
                resolution_draft["recommended_action"],
                json.dumps([c["case_id"] for c in resolution_draft["cited_cases"]]),
                int(qa_result["policy_blocked"]),
                "; ".join(qa_result["block_reasons"]) if qa_result["block_reasons"] else None,
                final_status,
                None,
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat() if final_status == "auto_resolved" else None,
            ),
        )
        cur.execute("UPDATE design_elements SET status=? WHERE element_id=?", (final_status, element_id))

        conn.commit()
        decision_id = cur.lastrowid
        conn.close()

        return {
            "decision_id": decision_id,
            "element_id": element_id,
            "triage": triage_result,
            "resolution_draft": resolution_draft,
            "qa": qa_result,
            "final_status": final_status,
        }
