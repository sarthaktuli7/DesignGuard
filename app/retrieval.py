"""
Retrieval layer: given a flagged violation's designer note and type, find the
most similar historically resolved cases and surface what happened to them.
Same contract as PaymentGuard's retriever: cite real precedent or explicitly
flag that none was found - never fabricate a justification.
"""
import sqlite3
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DB_PATH = "/home/claude/designguard/designguard.db"
SIMILARITY_THRESHOLD = 0.12


class PrecedentRetriever:
    def __init__(self, db_path=DB_PATH):
        conn = sqlite3.connect(db_path)
        self.cases = pd.read_sql_query("SELECT * FROM resolved_cases", conn)
        conn.close()

        self.vectorizer = TfidfVectorizer(stop_words="english", max_features=500)
        self._matrix = self.vectorizer.fit_transform(self.cases["designer_note"])

    def retrieve(self, designer_note, violation_type, severity, top_k=3):
        query_vec = self.vectorizer.transform([designer_note])
        sims = cosine_similarity(query_vec, self._matrix)[0]

        candidates = self.cases.copy()
        candidates["similarity"] = sims

        # Boost cases that share violation type / severity - same-category
        # precedent is more relevant than pure text similarity
        candidates.loc[candidates["violation_type"] == violation_type, "similarity"] += 0.20
        candidates.loc[candidates["severity"] == severity, "similarity"] += 0.05
        candidates["similarity"] = candidates["similarity"].clip(upper=1.0)

        top = candidates.sort_values("similarity", ascending=False).head(top_k)
        top = top[top["similarity"] >= SIMILARITY_THRESHOLD]

        if top.empty:
            return []

        return [
            {
                "case_id": row["case_id"],
                "similarity": round(float(row["similarity"]), 3),
                "resolution_type": row["resolution_type"],
                "resolution_notes": row["resolution_notes"],
            }
            for _, row in top.iterrows()
        ]
