"""
Visual audit layer: analyzes a rendered frame image directly with OpenCV,
rather than reading a file's structured metadata. This catches violations
that only exist visually - a color that was sampled with an eyedropper
instead of applied from the token library would look identical in a
screenshot but might carry a slightly different hex value in the file's
JSON, for instance, and conversely, some visual drift only shows up once
rendered (anti-aliasing, effects, overlapping layers).

This module is independent of app/agents.py's structured-metadata path -
together they give DesignGuard two different ways of catching the same
underlying problem, which is the actual justification for building this
rather than just trusting file metadata.
"""
import math
import cv2
import numpy as np

APPROVED_COLORS_RGB = [
    (26, 26, 46), (74, 78, 105), (154, 140, 152), (242, 233, 228),
    (47, 111, 237), (31, 157, 85), (192, 57, 43), (192, 122, 0),
]
APPROVED_SPACING = [4, 8, 12, 16, 24, 32, 48, 64]
APPROVED_RADII = [0, 4, 8, 12, 16]

BG_COLOR_RGB = (248, 249, 251)
COLOR_MATCH_THRESHOLD = 30.0   # max RGB Euclidean distance still considered "on palette"
SPACING_MATCH_THRESHOLD = 3    # px tolerance against the approved spacing scale
RADIUS_MATCH_THRESHOLD = 3     # px tolerance against the approved radius scale


def _rgb_distance(c1, c2):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def _nearest(value, approved_list):
    return min(approved_list, key=lambda a: abs(a - value) if isinstance(a, (int, float)) else _rgb_distance(a, value))


def detect_elements(image_path):
    """
    Finds distinct, non-background rectangular regions in a rendered frame
    via contour detection on a background-subtracted mask. Returns each
    region's bounding box and its average fill color.
    """
    img_bgr = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    bg = np.array(BG_COLOR_RGB)
    diff = np.abs(img_rgb.astype(int) - bg.astype(int)).sum(axis=2)
    mask = (diff > 15).astype(np.uint8) * 255

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    elements = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 20 or h < 20:
            continue  # skip noise/anti-aliasing fragments

        # Sample fill color from the center of the bounding box, away from
        # rounded corners and edges, so it reads the flat fill not the background
        cx, cy = x + w // 2, y + h // 2
        sample = img_rgb[cy - 3:cy + 3, cx - 3:cx + 3].reshape(-1, 3)
        avg_color = tuple(int(v) for v in sample.mean(axis=0))

        elements.append({"bbox": (x, y, w, h), "fill_color_rgb": avg_color})

    # Group into rows first (cluster by y-position within a tolerance), then
    # sort left-to-right within each row - matters for spacing comparisons,
    # since comparing x-gaps across two different rows produces nonsense.
    elements.sort(key=lambda e: e["bbox"][1])
    rows = []
    row_tolerance = 40
    for el in elements:
        placed = False
        for row in rows:
            if abs(row[0]["bbox"][1] - el["bbox"][1]) <= row_tolerance:
                row.append(el)
                placed = True
                break
        if not placed:
            rows.append([el])

    ordered = []
    for row in rows:
        row.sort(key=lambda e: e["bbox"][0])
        for i, el in enumerate(row):
            el["row_position"] = i  # 0 = first in its row, no left-neighbor to compare spacing against
        ordered.extend(row)
    return ordered


def _measure_corner_radius(image_path, bbox):
    """
    Estimates corner radius by scanning horizontally along the bounding
    box's top-most row, from the left edge inward, measuring how many
    pixels of background persist before the fill begins.

    This is the geometrically correct scan line: for a quarter-circle
    corner of radius R centered at (R, R) relative to the corner, the top
    edge (the row at y-offset 0) is background for exactly the first R
    pixels and fill from R onward. An earlier version of this function
    scanned the diagonal instead, which introduces a sqrt(2) distortion
    and under-measures every radius - worth knowing if you build on this,
    since it's an easy mistake to repeat.
    """
    img_bgr = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    x, y, w, h = bbox
    bg = np.array(BG_COLOR_RGB)

    max_check = min(40, w // 2, h // 2)
    row_y = y
    if row_y >= img_rgb.shape[0]:
        return 0

    radius = 0
    for d in range(max_check):
        px = x + d
        if px >= img_rgb.shape[1]:
            break
        pixel = img_rgb[row_y, px].astype(int)
        if np.abs(pixel - bg).sum() > 15:
            radius = d
            break
        radius = d + 1
    return radius


def analyze_frame(image_path):
    """
    Full visual audit of one rendered frame. Returns a list of detected
    violations (only - compliant elements are not returned, matching the
    existing agents.py contract which only ever sees flagged elements).
    """
    elements = detect_elements(image_path)
    violations = []

    for i, el in enumerate(elements):
        x, y, w, h = el["bbox"]
        color = el["fill_color_rgb"]

        nearest_color = min(APPROVED_COLORS_RGB, key=lambda c: _rgb_distance(c, color))
        color_dev = _rgb_distance(color, nearest_color)
        if color_dev > COLOR_MATCH_THRESHOLD:
            violations.append({
                "element_index": i,
                "bbox": el["bbox"],
                "violation_type": "off_palette_color",
                "detected_value": color,
                "nearest_approved": nearest_color,
                "deviation": round(min(color_dev / 200.0, 1.0), 3),  # normalize to ~0-1
            })

        radius = _measure_corner_radius(image_path, el["bbox"])
        nearest_radius = min(APPROVED_RADII, key=lambda r: abs(r - radius))
        radius_dev = abs(radius - nearest_radius)
        if radius_dev > RADIUS_MATCH_THRESHOLD:
            violations.append({
                "element_index": i,
                "bbox": el["bbox"],
                "violation_type": "inconsistent_corner_radius",
                "detected_value": radius,
                "nearest_approved": nearest_radius,
                "deviation": round(min(radius_dev / 20.0, 1.0), 3),
            })

        if el.get("row_position", 0) > 0:
            prev_x, prev_y, prev_w, prev_h = elements[i - 1]["bbox"]
            gap = x - (prev_x + prev_w)
            if gap > 0:
                nearest_spacing = min(APPROVED_SPACING, key=lambda s: abs(s - gap))
                spacing_dev = abs(gap - nearest_spacing)
                if spacing_dev > SPACING_MATCH_THRESHOLD:
                    violations.append({
                        "element_index": i,
                        "bbox": el["bbox"],
                        "violation_type": "non_standard_spacing",
                        "detected_value": gap,
                        "nearest_approved": nearest_spacing,
                        "deviation": round(min(spacing_dev / 40.0, 1.0), 3),
                    })

    return violations
