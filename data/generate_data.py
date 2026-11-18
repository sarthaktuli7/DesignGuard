"""
DesignGuard synthetic data generator.

Simulates what a real design-system audit tool would pull from Figma's REST
API: a file's node tree, compared against an approved design-token library
(colors, spacing scale, component library). Generates:
  1. design_elements   - individual layers/nodes flagged as token violations
  2. resolved_cases     - a knowledge base of historically resolved violations,
                          used by the retrieval layer as design-system precedent

All data is synthetic. Designer notes are templated (not LLM-generated) so
the dataset is reproducible and license-free.
"""
import random
import sqlite3
from datetime import datetime, timedelta

random.seed(42)

# The approved design system - what a real Figma design-system library would define
APPROVED_COLORS = [
    ("#1A1A2E", "ink-900"), ("#4A4E69", "slate-600"), ("#9A8C98", "slate-300"),
    ("#F2E9E4", "cream-100"), ("#2F6FED", "brand-blue-500"), ("#1F9D55", "success-500"),
    ("#C0392B", "danger-500"), ("#C07A00", "warning-500"),
]
APPROVED_SPACING = [4, 8, 12, 16, 24, 32, 48, 64]
APPROVED_COMPONENTS = [
    "Button/Primary", "Button/Secondary", "Input/Text", "Card/Default",
    "Modal/Standard", "Nav/TopBar", "Badge/Status", "Avatar/Default",
]

SCREENS = [
    ("Onboarding Flow", False), ("Settings Page", False), ("Marketing Landing Page", True),
    ("Pricing Page", True), ("Internal Admin Tool", False), ("Checkout Flow", True),
    ("Dashboard Home", False), ("Campaign Microsite", True), ("Help Center", False),
    ("Mobile Nav", False),
]

VIOLATION_TYPES = [
    "off_palette_color", "non_standard_spacing", "duplicate_component",
    "inconsistent_corner_radius", "unapproved_font_size",
]

NOTE_TEMPLATES = {
    "off_palette_color": [
        "Client asked for this exact brand color for the campaign launch.",
        "Picked this color from a mockup without checking the library.",
        "Needed a one-off accent color to match a partner's brand guidelines.",
    ],
    "non_standard_spacing": [
        "Eyeballed the spacing to make it look right in this specific layout.",
        "Copied spacing from an old file that predates the current token set.",
        "Needed tighter spacing here to fit content on smaller screens.",
    ],
    "duplicate_component": [
        "Built a custom version because the library component didn't support this layout.",
        "Didn't realize a library component already existed for this pattern.",
        "Needed a one-off variant for a specific partner integration.",
    ],
    "inconsistent_corner_radius": [
        "Matched the corner radius to an external asset provided by the client.",
        "Used an old radius value from a previous design system version.",
        "Rounded manually to match a screenshot from a competitor's product.",
    ],
    "unapproved_font_size": [
        "Needed a larger size here for accessibility on a dense data table.",
        "Used a legacy font size that hasn't been migrated to the new scale.",
        "Bumped the size slightly to fix a text-wrapping issue in testing.",
    ],
}

# Ground-truth tendency: how often each violation type legitimately deserves
# to be approved as an exception rather than auto-fixed or flagged
VIOLATION_MERIT_BASE_RATE = {
    "off_palette_color": 0.35,
    "non_standard_spacing": 0.55,
    "duplicate_component": 0.30,
    "inconsistent_corner_radius": 0.50,
    "unapproved_font_size": 0.60,
}

SEVERITY_BY_TYPE = {
    "off_palette_color": "brand_critical",
    "non_standard_spacing": "cosmetic",
    "duplicate_component": "moderate",
    "inconsistent_corner_radius": "cosmetic",
    "unapproved_font_size": "moderate",
}


def random_date(days_back=180):
    return datetime.now() - timedelta(days=random.randint(1, days_back))


def gen_elements_and_precedent(n_elements=900):
    elements = []
    resolved_cases = []

    for i in range(n_elements):
        violation_type = random.choices(
            VIOLATION_TYPES,
            weights=[0.24, 0.26, 0.18, 0.16, 0.16],
        )[0]
        screen_name, is_high_vis = random.choice(SCREENS)
        severity = SEVERITY_BY_TYPE[violation_type]
        note = random.choice(NOTE_TEMPLATES[violation_type])

        # Numeric deviation from nearest approved token (color distance / px delta,
        # normalized to a 0-1 scale for modeling purposes)
        deviation = round(random.uniform(0.05, 0.95), 3)

        # How many times a designer has had a prior exception approved on this file
        prior_exceptions = random.choices([0, 1, 2, 3], weights=[0.55, 0.25, 0.13, 0.07])[0]

        base_rate = VIOLATION_MERIT_BASE_RATE[violation_type]
        merit_prob = base_rate
        if is_high_vis:
            merit_prob -= 0.15  # high-visibility screens get more scrutiny
        if prior_exceptions >= 2:
            merit_prob -= 0.10  # repeat requesters get more scrutiny too
        if deviation > 0.6:
            merit_prob -= 0.10  # bigger deviations from the token are harder to justify
        merit_prob = max(0.05, min(0.90, merit_prob))

        is_meritorious = random.random() < merit_prob
        filed_date = random_date(200)

        element_id = f"EL{100000+i}"
        elements.append({
            "element_id": element_id,
            "file_id": f"FILE{random.randint(1, 60):03d}",
            "screen_name": screen_name,
            "is_high_visibility": int(is_high_vis),
            "violation_type": violation_type,
            "severity": severity,
            "designer_note": note,
            "deviation": deviation,
            "prior_exceptions_count": prior_exceptions,
            "flagged_date": filed_date.isoformat(),
            "ground_truth_merit": int(is_meritorious),
            "status": "open",
        })

        # ~70% of generated elements become part of the historical "resolved" precedent
        if random.random() < 0.70:
            if is_meritorious:
                resolution_type = "approved_exception"
            else:
                resolution_type = random.choice(["auto_fixed_to_token", "auto_fixed_to_token", "changed_by_designer"])

            resolved_cases.append({
                "case_id": f"CASE{300000+i}",
                "violation_type": violation_type,
                "designer_note": note,
                "severity": severity,
                "screen_name": screen_name,
                "resolution_type": resolution_type,
                "resolution_notes": (
                    f"Resolved as {resolution_type.replace('_', ' ')} after design-system review "
                    f"of a {violation_type.replace('_', ' ')} violation."
                ),
            })
            elements[-1]["status"] = "closed"

    return elements, resolved_cases


def build_database(db_path="designguard.db"):
    elements, resolved_cases = gen_elements_and_precedent(900)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript("""
    DROP TABLE IF EXISTS design_elements;
    DROP TABLE IF EXISTS resolved_cases;
    DROP TABLE IF EXISTS decisions;
    DROP TABLE IF EXISTS audit_trail;

    CREATE TABLE design_elements (
        element_id TEXT PRIMARY KEY,
        file_id TEXT,
        screen_name TEXT,
        is_high_visibility INTEGER,
        violation_type TEXT,
        severity TEXT,
        designer_note TEXT,
        deviation REAL,
        prior_exceptions_count INTEGER,
        flagged_date TEXT,
        ground_truth_merit INTEGER,
        status TEXT
    );

    CREATE TABLE resolved_cases (
        case_id TEXT PRIMARY KEY,
        violation_type TEXT,
        designer_note TEXT,
        severity TEXT,
        screen_name TEXT,
        resolution_type TEXT,
        resolution_notes TEXT
    );

    CREATE TABLE decisions (
        decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
        element_id TEXT,
        merit_score REAL,
        confidence REAL,
        recommended_action TEXT,
        retrieved_case_ids TEXT,
        policy_blocked INTEGER,
        block_reason TEXT,
        final_status TEXT,
        human_reviewer TEXT,
        created_at TEXT,
        resolved_at TEXT
    );

    CREATE TABLE audit_trail (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        element_id TEXT,
        stage TEXT,
        agent TEXT,
        detail TEXT,
        timestamp TEXT
    );
    """)

    cur.executemany(
        "INSERT INTO design_elements VALUES (:element_id,:file_id,:screen_name,:is_high_visibility,"
        ":violation_type,:severity,:designer_note,:deviation,:prior_exceptions_count,"
        ":flagged_date,:ground_truth_merit,:status)",
        elements,
    )
    cur.executemany(
        "INSERT INTO resolved_cases VALUES (:case_id,:violation_type,:designer_note,:severity,"
        ":screen_name,:resolution_type,:resolution_notes)",
        resolved_cases,
    )

    conn.commit()
    conn.close()
    print(f"Seeded {len(elements)} flagged elements "
          f"({sum(1 for e in elements if e['status']=='open')} open), "
          f"{len(resolved_cases)} resolved precedent cases -> {db_path}")


if __name__ == "__main__":
    build_database("/home/claude/designguard/designguard.db")
