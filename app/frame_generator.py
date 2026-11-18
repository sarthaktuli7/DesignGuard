"""
Generates synthetic "rendered frame" images - a stand-in for what you'd get
exporting a Figma frame to PNG. Real DesignGuard would pull these via the
Figma REST API's image export endpoint; this sandbox has no network access,
so frames are generated directly with known ground-truth properties
(exact fill colors, spacing, corner radii) so the CV module's output can be
checked against something verifiable.
"""
import random
from PIL import Image, ImageDraw

random.seed(7)

APPROVED_COLORS_RGB = [
    (26, 26, 46), (74, 78, 105), (154, 140, 152), (242, 233, 228),
    (47, 111, 237), (31, 157, 85), (192, 57, 43), (192, 122, 0),
]
OFF_PALETTE_COLORS_RGB = [
    (255, 105, 180), (0, 206, 209), (255, 215, 0), (138, 43, 226),
]
APPROVED_SPACING = [4, 8, 12, 16, 24, 32, 48, 64]
APPROVED_RADII = [0, 4, 8, 12, 16]

CANVAS_W, CANVAS_H = 900, 560
BG_COLOR = (248, 249, 251)


def _rounded_rect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def generate_frame(path, n_elements=5, violation_rate=0.4):
    """
    Draws a synthetic UI frame with n_elements rectangular "components"
    (buttons/cards), laid out left-to-right with randomized spacing.
    Returns ground truth for every element placed, so the CV module's
    detections can be checked for accuracy.
    """
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    ground_truth = []
    x = 40
    y = 60
    row_height = 120

    for i in range(n_elements):
        is_violation_color = random.random() < violation_rate
        is_violation_spacing = random.random() < violation_rate
        is_violation_radius = random.random() < violation_rate

        w = random.choice([120, 150, 180])
        h = row_height

        color = random.choice(OFF_PALETTE_COLORS_RGB) if is_violation_color else random.choice(APPROVED_COLORS_RGB)
        spacing_before = random.choice([3, 6, 10, 20, 40]) if is_violation_spacing else random.choice(APPROVED_SPACING)
        radius = random.choice([2, 6, 10, 20, 28]) if is_violation_radius else random.choice(APPROVED_RADII)

        if i > 0:
            x += spacing_before

        if x + w > CANVAS_W - 40:
            x = 40
            y += row_height + 40

        box = [x, y, x + w, y + h]
        _rounded_rect(draw, box, radius, color)

        ground_truth.append({
            "element_index": i,
            "bbox": box,
            "fill_color_rgb": color,
            "spacing_before": spacing_before if i > 0 else None,
            "corner_radius": radius,
            "color_is_violation": is_violation_color,
            "spacing_is_violation": is_violation_spacing,
            "radius_is_violation": is_violation_radius,
        })

        x += w

    img.save(path)
    return ground_truth


if __name__ == "__main__":
    import json
    gt = generate_frame("/home/claude/designguard/sample_frames/frame_01.png", n_elements=6, violation_rate=0.45)
    with open("/home/claude/designguard/sample_frames/frame_01_ground_truth.json", "w") as f:
        json.dump(gt, f, indent=2)
    print(f"Generated frame with {len(gt)} elements")
    for e in gt:
        print(f"  #{e['element_index']}: color={e['fill_color_rgb']} radius={e['corner_radius']} "
              f"spacing_before={e['spacing_before']} "
              f"violations: color={e['color_is_violation']} spacing={e['spacing_is_violation']} radius={e['radius_is_violation']}")
