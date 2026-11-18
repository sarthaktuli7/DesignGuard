"""
DesignGuard - Agentic Design System Compliance Platform.

Run with:  python3 -m app.main
Dashboard: http://localhost:8060/
"""
import json
import sqlite3
import sys
import os
from datetime import datetime

from flask import Flask, jsonify, request, render_template

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.agents import DesignGuardPipeline

DB_PATH = "/home/claude/designguard/designguard.db"

app = Flask(__name__)
pipeline = DesignGuardPipeline()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/stats")
def stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM design_elements").fetchone()["c"]
    open_el = conn.execute("SELECT COUNT(*) c FROM design_elements WHERE status='open'").fetchone()["c"]
    auto_resolved = conn.execute("SELECT COUNT(*) c FROM decisions WHERE final_status='auto_resolved'").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) c FROM decisions WHERE final_status='pending_human_review'").fetchone()["c"]
    approved = conn.execute("SELECT COUNT(*) c FROM decisions WHERE final_status='human_approved'").fetchone()["c"]
    rejected = conn.execute("SELECT COUNT(*) c FROM decisions WHERE final_status='human_rejected'").fetchone()["c"]
    by_type = conn.execute(
        "SELECT violation_type, COUNT(*) c FROM design_elements GROUP BY violation_type ORDER BY c DESC"
    ).fetchall()
    conn.close()
    return jsonify({
        "total_elements": total, "open_elements": open_el, "auto_resolved": auto_resolved,
        "pending_human_review": pending, "human_approved": approved, "human_rejected": rejected,
        "by_type": [dict(r) for r in by_type],
    })


@app.route("/api/elements")
def list_elements():
    status_filter = request.args.get("status")
    conn = get_conn()
    if status_filter:
        rows = conn.execute(
            "SELECT * FROM design_elements WHERE status=? ORDER BY flagged_date DESC LIMIT 100", (status_filter,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM design_elements ORDER BY flagged_date DESC LIMIT 100").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/elements/<element_id>/analyze", methods=["POST"])
def analyze_element(element_id):
    result = pipeline.process(element_id)
    return jsonify(result)


@app.route("/api/elements/<element_id>/trace")
def element_trace(element_id):
    conn = get_conn()
    element = conn.execute("SELECT * FROM design_elements WHERE element_id=?", (element_id,)).fetchone()
    trail = conn.execute(
        "SELECT * FROM audit_trail WHERE element_id=? ORDER BY log_id ASC", (element_id,)
    ).fetchall()
    decision = conn.execute(
        "SELECT * FROM decisions WHERE element_id=? ORDER BY decision_id DESC LIMIT 1", (element_id,)
    ).fetchone()
    conn.close()

    trail_out = []
    for row in trail:
        r = dict(row)
        r["detail"] = json.loads(r["detail"])
        trail_out.append(r)

    return jsonify({
        "element": dict(element) if element else None,
        "decision": dict(decision) if decision else None,
        "audit_trail": trail_out,
    })


@app.route("/api/review-queue")
def review_queue():
    conn = get_conn()
    rows = conn.execute(
        """SELECT e.element_id, e.violation_type, e.designer_note, e.screen_name, e.severity,
                  e.is_high_visibility, e.detection_source, dec.merit_score, dec.confidence,
                  dec.recommended_action, dec.block_reason, dec.decision_id
           FROM decisions dec
           JOIN design_elements e ON e.element_id = dec.element_id
           WHERE dec.final_status = 'pending_human_review'
           ORDER BY dec.decision_id DESC"""
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/decisions/<int:decision_id>/approve", methods=["POST"])
def approve_decision(decision_id):
    reviewer = request.json.get("reviewer", "unknown_reviewer") if request.is_json else "unknown_reviewer"
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM decisions WHERE decision_id=?", (decision_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "decision not found"}), 404

    cur.execute(
        "UPDATE decisions SET final_status='human_approved', human_reviewer=?, resolved_at=? WHERE decision_id=?",
        (reviewer, datetime.utcnow().isoformat(), decision_id),
    )
    cur.execute("UPDATE design_elements SET status='human_approved' WHERE element_id=?", (row["element_id"],))
    cur.execute(
        "INSERT INTO audit_trail (element_id, stage, agent, detail, timestamp) VALUES (?,?,?,?,?)",
        (row["element_id"], "human_review", "HumanReviewer",
         json.dumps({"action": "approved", "reviewer": reviewer, "recommended_action": row["recommended_action"]}),
         datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "approved"})


@app.route("/api/decisions/<int:decision_id>/reject", methods=["POST"])
def reject_decision(decision_id):
    reviewer = request.json.get("reviewer", "unknown_reviewer") if request.is_json else "unknown_reviewer"
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM decisions WHERE decision_id=?", (decision_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "decision not found"}), 404

    cur.execute(
        "UPDATE decisions SET final_status='human_rejected', human_reviewer=?, resolved_at=? WHERE decision_id=?",
        (reviewer, datetime.utcnow().isoformat(), decision_id),
    )
    cur.execute("UPDATE design_elements SET status='human_rejected' WHERE element_id=?", (row["element_id"],))
    conn.commit()
    conn.close()
    return jsonify({"status": "rejected"})


@app.route("/api/process-batch", methods=["POST"])
def process_batch():
    conn = get_conn()
    open_ids = [r["element_id"] for r in conn.execute("SELECT element_id FROM design_elements WHERE status='open'").fetchall()]
    conn.close()

    results = []
    for element_id in open_ids:
        results.append(pipeline.process(element_id))

    return jsonify({"processed": len(results), "results": results})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8060, debug=False)
