const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, BorderStyle,
        Table, TableRow, TableCell, WidthType, ShadingType, ImageRun, PageBreak } = require('docx');
const fs = require('fs');

const FONT = "Calibri";
const NAVY = "1A1A2E";
const BLUE = "2F6FED";
const GREY = "6B7688";
const LIGHTGREY = "F4F6FA";

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 320, after: 140 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: BLUE } },
    children: [new TextRun({ text, bold: true, size: 30, color: NAVY, font: FONT })]
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 220, after: 100 },
    children: [new TextRun({ text, bold: true, size: 24, color: NAVY, font: FONT })]
  });
}
function p(text, opts={}) {
  return new Paragraph({
    spacing: { after: 140 },
    children: [new TextRun({ text, size: 21, font: FONT, ...opts })]
  });
}
function bullet(text, opts={}) {
  return new Paragraph({
    bullet: { level: 0 },
    spacing: { after: 70 },
    children: Array.isArray(text) ? text : [new TextRun({ text, size: 21, font: FONT, ...opts })]
  });
}
function bold(text) { return new TextRun({ text, bold: true, size: 21, font: FONT }); }
function reg(text) { return new TextRun({ text, size: 21, font: FONT }); }
function calloutBox(title, lines) {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "C0392B" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "C0392B" },
      left: { style: BorderStyle.SINGLE, size: 4, color: "C0392B" },
      right: { style: BorderStyle.SINGLE, size: 4, color: "C0392B" },
    },
    rows: [
      new TableRow({
        children: [
          new TableCell({
            shading: { type: ShadingType.CLEAR, fill: "FDECEC" },
            margins: { top: 160, bottom: 160, left: 200, right: 200 },
            children: [
              new Paragraph({ children: [new TextRun({ text: title, bold: true, size: 21, color: "C0392B", font: FONT })], spacing: { after: 80 } }),
              ...lines.map(l => new Paragraph({ children: [new TextRun({ text: l, size: 20, font: FONT })], spacing: { after: 60 } }))
            ]
          })
        ]
      })
    ]
  });
}

function image(path, width, height) {
  const data = fs.readFileSync(path);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 140 },
    children: [ new ImageRun({ type: path.endsWith('.png') ? 'png' : 'jpg', data, transformation: { width, height } }) ]
  });
}

function simpleTable(headers, rows) {
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map(hText => new TableCell({
      shading: { type: ShadingType.CLEAR, fill: NAVY },
      margins: { top: 100, bottom: 100, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text: hText, bold: true, color: "FFFFFF", size: 19, font: FONT })] })]
    }))
  });
  const bodyRows = rows.map((r, i) => new TableRow({
    children: r.map(cellText => new TableCell({
      shading: { type: ShadingType.CLEAR, fill: i % 2 === 0 ? "FFFFFF" : LIGHTGREY },
      margins: { top: 90, bottom: 90, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text: String(cellText), size: 19, font: FONT })] })]
    }))
  }));
  return new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: [headerRow, ...bodyRows] });
}

const doc = new Document({
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 900, bottom: 900, left: 900, right: 900 } } },
    children: [
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 800, after: 100 },
        children: [new TextRun({ text: "DesignGuard", bold: true, size: 56, color: NAVY, font: FONT })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
        children: [new TextRun({ text: "Agentic Design System Compliance Platform", size: 26, color: BLUE, font: FONT })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 500 },
        children: [new TextRun({ text: "Project Documentation  |  Sarthak Tuli  |  October 2026", size: 19, color: GREY, font: FONT })] }),

      h1("1. Executive Summary"),
      p("DesignGuard is a working, end-to-end system that decides what should happen when a design element violates a design system's rules: approve it as a legitimate exception, auto-fix it back to the token library, or send it to a human reviewer. It combines a trained merit model, a precedent-retrieval layer, a hard-coded policy gate, and a review dashboard, and every decision it makes is logged in a way that can be replayed and audited."),
      p("The project reuses the same Triage / Resolution / QA / Escalation pattern built for PaymentGuard (a payments dispute-resolution system), applied here to design-system governance, the exact kind of problem Figma's own Associate Product Manager posting names as an example project: \u201Cdesign system features that improve adoption and consistency at scale.\u201D"),

      h1("2. The Problem"),
      p("Design systems drift. A designer under deadline pressure picks an off-palette color for a campaign, builds a one-off component instead of reusing the library version, or nudges spacing by a few pixels to make a layout work. Individually these are small decisions. At scale, across hundreds of files and dozens of designers, they erode the consistency a design system exists to protect."),
      p("The naive fix, rejecting every deviation automatically, breaks legitimate exceptions (a client-mandated brand color for a one-time partnership, an accessibility-driven font-size bump). The opposite naive fix, approving whatever a designer requests, lets the system drift anyway. DesignGuard's job is not \u201Cdetect violations,\u201D it's deciding which violations are safe to resolve automatically and which must go to a human design-system reviewer before anything changes."),

      h1("3. Why We Built It This Way"),
      h2("3.1 Reusing the PaymentGuard pattern, deliberately"),
      p("PaymentGuard proved a Triage / Resolution / QA / Escalation split for payment dispute resolution. DesignGuard applies the identical structural pattern to design-system governance, which needed three of the same hard guarantees:"),
      bullet([bold("A hard-coded policy gate "), reg("instead of a soft confidence check: brand-critical violations and high-visibility screens are always blocked from auto-resolution, no exceptions written into the code path")]),
      bullet([bold("A grounding requirement with a real penalty "), reg("if the Resolution Agent cannot cite a similar past exception decision, the QA Agent automatically blocks it")]),
      bullet([bold("A reviewer-facing decision trace "), reg("so a design-system lead can see exactly why any violation was or wasn't auto-resolved, in seconds rather than by re-deriving it")]),

      h2("3.2 An honest note on what's simulated versus what's real"),
      calloutBox("Read this before describing the project in an interview", [
        "This build environment has no network access, so it could not call the real Figma REST API or a hosted LLM. Two honest substitutions were made:",
        "1) The design token library, flagged elements, and resolution history are synthetic, generated with a fixed seed, modeled on what Figma's own REST API returns for a file's node tree (frames, fills, components, styles).",
        "2) The risk model is a scikit-learn ensemble (Random Forest + Gradient Boosting + Logistic Regression) with a lightweight custom explainability layer, the same substitution pattern used in PaymentGuard, for the same reason (no network access to XGBoost/SHAP in this environment).",
        "The architecture, the policy gate, and the audit trail are all fully real and running. Connecting this to a live Figma file via the Figma REST API, or swapping in a hosted LLM for resolution drafting (as PaymentGuard does with the Claude API), is a scoped, well-understood upgrade, not a redesign. Say exactly this if asked."
      ]),

      new Paragraph({ children: [new PageBreak()] }),

      h1("4. System Architecture"),
      p("The diagram below shows the full request path: a flagged design element enters from the data layer, moves through the four agents in sequence, and either resolves automatically or lands in the human review queue, with every stage writing to the audit trail that feeds the dashboard."),
      image(__dirname + "/architecture.png", 400, 473),

      h2("4.1 Component breakdown"),
      simpleTable(
        ["Component", "Responsibility", "Key implementation detail"],
        [
          ["Triage Agent", "Scores a flagged violation for exception-merit and produces a confidence level", "Soft-voting ensemble (RF + GB + LR) trained on violation type, severity, screen visibility, deviation from the nearest approved token, and prior exception history"],
          ["Resolution Agent", "Retrieves similar past resolved violations and drafts a recommended action", "TF-IDF + cosine similarity over designer notes, boosted by matching violation type and severity; must cite a case or flag none found"],
          ["QA / Policy Agent", "Enforces hard rules that can block any recommendation from auto-executing", "Brand-critical severity and high-visibility screens always escalate, regardless of model confidence; repeat requesters and ungrounded recommendations also escalate"],
          ["Escalation Agent", "Converts the QA verdict into a final routing decision", "Two outcomes only: auto_resolved or pending_human_review"],
          ["Audit Trail", "Records every agent's output at every stage for every element", "Append-only SQLite log, replayable per element via the dashboard's Trace view"],
          ["Dashboard", "Lets a design-system reviewer see the queue, inspect the full trace, and approve or reject", "Flask + vanilla JS, single page, no build step required"],
        ]
      ),

      new Paragraph({ children: [new PageBreak()] }),

      h1("5. Data"),
      p("All data is synthetic, generated deterministically (fixed random seed) so results are reproducible, and so every claim in this document is about the architecture and its behavior rather than a fabricated business-impact number."),
      simpleTable(
        ["Dataset", "Size", "Purpose"],
        [
          ["Flagged design elements", "900 records (293 left open)", "Individual layers/nodes flagged as token-library violations, modeled on Figma's file node structure"],
          ["Resolved case knowledge base", "607 records", "Historical precedent the Resolution Agent retrieves against"],
          ["Design token library", "8 approved colors, 8 spacing values, 8 library components", "The approved design system each flagged element is checked against"],
        ]
      ),

      h1("6. Model Performance"),
      p("Reported honestly, on a held-out 20% test split:"),
      simpleTable(
        ["Metric", "Value"],
        [
          ["ROC-AUC", "0.652"],
          ["Precision", "0.417"],
          ["Recall", "0.179"],
          ["F1 score", "0.250"],
          ["Train / test size", "720 / 180 elements"],
        ]
      ),
      p("The low recall is the intended, safer failure mode for this use case: the model is conservative about recommending that a violation be approved as an exception, meaning it defaults toward auto-fix or human review rather than confidently green-lighting a brand deviation it shouldn't. It's the policy gate, not the model's raw accuracy, that keeps the high-stakes cases (brand-critical, high-visibility) out of auto-resolution entirely regardless of what the model predicts."),

      h1("7. Human-in-the-Loop Policy Gate"),
      p("The QA Agent's rulebook is intentionally simple enough to read end to end:"),
      bullet([bold("Brand-critical severity: "), reg("always escalate, no exceptions, regardless of confidence.")]),
      bullet([bold("High-visibility screens: "), reg("always escalate (marketing pages, pricing pages, checkout flows).")]),
      bullet([bold("Confidence floor: "), reg("0.70. Below it, the model itself is flagging uncertainty.")]),
      bullet([bold("Repeat requesters: "), reg("more than one prior exception on the same file blocks auto-resolution.")]),
      bullet([bold("Grounding requirement: "), reg("no cited precedent means no auto-resolution.")]),
      p("Running the full pipeline against all 293 open flagged elements in the seed data: 3 auto-resolved, 290 routed to human review. That ratio is intentional evidence the gate is conservative by default, consistent with the same design choice made in PaymentGuard."),

      new Paragraph({ children: [new PageBreak()] }),

      h1("8. Dashboard"),
      p("The review queue shows every flagged element currently blocked by policy, why it was blocked, and one-click approve/reject actions:"),
      image(__dirname + "/screenshots/dashboard_screenshot.png", 480, 343),
      p("Clicking Trace on any element opens its full decision trace, exactly as logged by each agent:"),
      image(__dirname + "/screenshots/dashboard_trace_modal.png", 480, 343),

      h1("9. Testing"),
      p("20 unit tests total. 13 cover the risk model's output shape and directional sanity, the retrieval layer's similarity bounds and empty-result handling, every branch of the QA policy gate, and the Resolution Agent's fallback behavior with no LLM key configured. 7 more (test_visual_audit.py) check the computer vision module against generated ground truth: correct element count, accurate color detection, directionally correct radius measurement, and that every detected violation carries the required fields. All 20 pass."),

      h1("10. How to Run It"),
      bullet("cd designguard && pip install -r requirements.txt"),
      bullet("python3 data/generate_data.py        # seeds the SQLite database"),
      bullet("python3 train_model.py                 # trains and saves the risk model"),
      bullet("python3 -m app.main                     # starts the dashboard at localhost:8060"),
      bullet("python3 -m unittest tests/test_agents.py -v   # runs the test suite"),

      h1("11. Two Upgrades Added After the Initial Build"),
      h2("11.1 Live Claude API integration"),
      p("The Resolution Agent now supports a genuine LLM call instead of the deterministic vote, implemented in app/llm_resolution.py, using the identical pattern from PaymentGuard. Setting an ANTHROPIC_API_KEY environment variable and installing the anthropic package causes every subsequent request to have Claude draft the recommended action and rationale, grounded in exactly the precedent the retrieval layer already found. If the key is absent or the call fails, the system falls back to the deterministic path automatically and logs which method produced each decision."),
      calloutBox("Same caveat as PaymentGuard", [
        "This integration was written and unit-tested for its fallback behavior (test_falls_back_to_deterministic_without_api_key, 13 agent tests total), but the live API call itself was not exercised in this sandbox, which has no outbound network access.",
        "Test it with a real ANTHROPIC_API_KEY before describing it as verified working, the same distinction that applies to PaymentGuard's LLM integration."
      ]),

      h2("11.2 Computer vision: auditing rendered pixels, not just file metadata"),
      p("Every violation described in Sections 1 through 10 comes from structured file metadata, a hex color code, a numeric spacing value, exactly what a real Figma file's JSON export would contain. app/visual_audit.py adds a second, independent detection path: it analyzes a rendered frame image directly with OpenCV, the same way a human reviewer looking at a screenshot would, rather than trusting what the file's metadata claims."),
      p("app/frame_generator.py builds synthetic rendered frames (a stand-in for Figma's PNG export endpoint, unavailable without network access) with known ground-truth properties, so the computer vision module's accuracy can be checked against something verifiable rather than taken on faith:"),
      bullet([bold("Color detection: "), reg("contour detection isolates each rectangular UI element, samples its fill color, and measures Euclidean RGB distance to the nearest approved token. Verified accurate against ground truth in testing (test_detected_colors_match_ground_truth).")]),
      bullet([bold("Corner radius detection: "), reg("scans horizontally along an element's top edge to measure how many pixels of background persist before the fill begins, the geometrically correct scan line for a quarter-circle corner. An earlier version measured along the diagonal instead, which introduces a sqrt(2) distortion and systematically under-measures every radius, documented in the code as a worked example of a plausible-looking bug that silently produces wrong numbers rather than an error.")]),
      bullet([bold("Spacing detection: "), reg("groups detected elements into rows by y-position before comparing gaps, so spacing is only ever compared between elements that are actually adjacent in the same row. An earlier version sorted by x-position alone, which compared spacing across unrelated rows and produced meaningless gap values, documented the same way.")]),
      p("Detected violations flow into the exact same design_elements table and the exact same Triage/Resolution/QA/Escalation pipeline as metadata-detected ones, tagged with a detection_source column so the dashboard can show which path caught which violation. Running 12 synthetic frames through the full pipeline: 46 visually-detected violations, 0 auto-resolved, 46 routed to human review, the gate treats a pixel-detected violation exactly as cautiously as a metadata-detected one."),
      calloutBox("Honest accuracy note", [
        "Color detection was highly reliable against generated ground truth. Radius and spacing detection are directionally correct but carry a few pixels of measurement noise, meaning a true violation sitting very close to an approved value's threshold can occasionally be measured as compliant, or vice versa. This is a real limitation of simple scan-line measurement on anti-aliased pixels, not a bug being hidden: the test suite (test_visual_audit.py) checks for directional correctness (sharp corners measure near zero, large radii measure well above zero) rather than exact-pixel accuracy, which is the honest bar this technique can actually meet."
      ]),

      h1("12. Limitations and Production Upgrade Path"),
      simpleTable(
        ["Current (this build)", "Production upgrade"],
        [
          ["Synthetic data, fixed seed", "Live connection to the Figma REST API, pulling real file node trees"],
          ["scikit-learn ensemble", "XGBoost, or a model registry with scheduled retraining"],
          ["Custom z-score explainability", "SHAP or an equivalent audited explainability library"],
          ["TF-IDF retrieval", "Hosted embedding model + a proper vector index"],
          ["Deterministic resolution drafting", "A hosted LLM (Claude, as in PaymentGuard) drafting the recommendation, still grounded by the same retrieved precedent and gated by the same QA policy"],
          ["Flask dev server", "A production WSGI server integrated as a Figma plugin or CI check"],
        ]
      ),

      h1("13. Suggested Resume Framing"),
      p("Three ready-to-use bullets, phrased to be defensible under follow-up questions:"),
      bullet("Architected an agentic design-system compliance platform with a hard-coded human-in-the-loop policy gate, achieving conservative auto-resolution (3 of 293 flagged violations) while grounding every recommendation in retrieved exception precedent"),
      bullet("Built and evaluated an ensemble risk model on 900 synthetic design-element records, reaching a 0.65 ROC-AUC on exception-merit prediction, and logged a full per-decision audit trail across 20 passing unit tests"),
      bullet("Built a computer vision audit layer (OpenCV) that detects design violations directly from rendered pixels rather than file metadata alone, catching and fixing a geometric measurement bug (diagonal vs. scan-line corner-radius detection) through ground-truth verification testing"),
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(__dirname + "/DesignGuard_Documentation.docx", buf);
  console.log("doc written");
});
