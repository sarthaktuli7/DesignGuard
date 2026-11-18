"""
Generates a batch of synthetic rendered frames, runs the OpenCV visual audit
on each, and inserts every detected violation into the same design_elements
table the metadata-based pipeline already uses - so a CV-detected violation
goes through the exact same Triage / Resolution / QA / Escalation agents and
the exact same policy gate as a metadata-detected one.

Run with: python3 run_visual_audit.py
"""
import sqlite3
import random
from datetime import datetime

from app.frame_generator import generate_frame
from app.visual_audit import analyze_frame
from app.agents import DesignGuardPipeline

DB_PATH = "/home/claude/designguard/designguard.db"
N_FRAMES = 12

SCREEN_POOL = [
    ("Onboarding Flow", 0), ("Settings Page", 0), ("Marketing Landing Page", 1),
    ("Pricing Page", 1), ("Dashboard Home", 0), ("Campaign Microsite", 1),
]

SEVERITY_BY_TYPE = {
    "off_palette_color": "brand_critical",
    "non_standard_spacing": "cosmetic",
    "inconsistent_corner_radius": "cosmetic",
}

NOTE_BY_TYPE = {
    "off_palette_color": "Flagged visually: rendered fill color does not match any token in the approved palette.",
    "non_standard_spacing": "Flagged visually: measured gap between adjacent elements does not match the approved spacing scale.",
    "inconsistent_corner_radius": "Flagged visually: measured corner radius does not match any approved radius value.",
}


def ensure_detection_source_column(cur):
    cols = [r[1] for r in cur.execute("PRAGMA table_info(design_elements)").fetchall()]
    if "detection_source" not in cols:
        cur.execute("ALTER TABLE design_elements ADD COLUMN detection_source TEXT DEFAULT 'metadata'")


def insert_visual_violations(cur, frame_id, violations):
    inserted_ids = []
    screen_name, is_high_vis = random.choice(SCREEN_POOL)

    for v in violations:
        element_id = f"VIS{frame_id:03d}{v['element_index']:02d}{v['violation_type'][:3].upper()}"
        severity = SEVERITY_BY_TYPE[v["violation_type"]]
        note = (
            NOTE_BY_TYPE[v["violation_type"]]
            + f" (detected={v['detected_value']}, nearest approved={v['nearest_approved']})"
        )
        cur.execute(
            """INSERT OR REPLACE INTO design_elements
               (element_id, file_id, screen_name, is_high_visibility, violation_type, severity,
                designer_note, deviation, prior_exceptions_count, flagged_date,
                ground_truth_merit, status, detection_source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                element_id, f"FRAME{frame_id:03d}", screen_name, is_high_vis,
                v["violation_type"], severity, note, v["deviation"],
                0, datetime.now().isoformat(), 0, "open", "visual_cv",
            ),
        )
        inserted_ids.append(element_id)
    return inserted_ids


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    ensure_detection_source_column(cur)
    conn.commit()

    all_inserted = []
    print(f"Generating {N_FRAMES} synthetic frames and running visual audit...\n")
    for frame_id in range(1, N_FRAMES + 1):
        frame_path = f"/home/claude/designguard/sample_frames/frame_{frame_id:02d}.png"
        generate_frame(frame_path, n_elements=random.randint(4, 7), violation_rate=0.4)
        violations = analyze_frame(frame_path)
        inserted = insert_visual_violations(cur, frame_id, violations)
        all_inserted.extend(inserted)
        print(f"  frame_{frame_id:02d}.png -> {len(violations)} violations detected")

    conn.commit()
    conn.close()

    print(f"\nTotal visually-detected elements inserted: {len(all_inserted)}")
    print("Running the full agent pipeline on each...\n")

    pipeline = DesignGuardPipeline()
    auto, pending = 0, 0
    for element_id in all_inserted:
        result = pipeline.process(element_id)
        if result["final_status"] == "auto_resolved":
            auto += 1
        else:
            pending += 1

    print(f"Processed {len(all_inserted)} visually-detected violations through the agent pipeline:")
    print(f"  auto_resolved: {auto}")
    print(f"  pending_human_review: {pending}")


if __name__ == "__main__":
    main()
