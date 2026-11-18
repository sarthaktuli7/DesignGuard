"""
Unit tests for the OpenCV visual audit module. Generates a frame with known
ground truth, then checks the detector's output against it.

Run with: python3 -m unittest tests/test_visual_audit.py -v
"""
import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.frame_generator import generate_frame
from app.visual_audit import detect_elements, analyze_frame, _rgb_distance, _measure_corner_radius


class TestColorDetection(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.frame_path = os.path.join(self.tmpdir, "test_frame.png")
        self.ground_truth = generate_frame(self.frame_path, n_elements=5, violation_rate=0.5)

    def test_detects_correct_number_of_elements(self):
        elements = detect_elements(self.frame_path)
        self.assertEqual(len(elements), len(self.ground_truth))

    def test_detected_colors_match_ground_truth(self):
        elements = detect_elements(self.frame_path)
        for detected, truth in zip(elements, self.ground_truth):
            dist = _rgb_distance(detected["fill_color_rgb"], tuple(truth["fill_color_rgb"]))
            self.assertLess(dist, 15, "detected fill color should closely match the generated color")

    def test_off_palette_colors_are_flagged(self):
        violations = analyze_frame(self.frame_path)
        color_violations = {v["element_index"] for v in violations if v["violation_type"] == "off_palette_color"}
        true_color_violations = {e["element_index"] for e in self.ground_truth if e["color_is_violation"]}
        # Every element the generator marked as an off-palette color should be caught
        self.assertTrue(true_color_violations.issubset(color_violations) or len(true_color_violations) == 0)


class TestRadiusMeasurement(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.frame_path = os.path.join(self.tmpdir, "test_frame.png")
        self.ground_truth = generate_frame(self.frame_path, n_elements=6, violation_rate=0.5)

    def test_sharp_corner_measures_near_zero(self):
        elements = detect_elements(self.frame_path)
        for detected, truth in zip(elements, self.ground_truth):
            if truth["corner_radius"] == 0:
                measured = _measure_corner_radius(self.frame_path, detected["bbox"])
                self.assertLessEqual(measured, 3, "a sharp corner should measure close to 0")

    def test_large_radius_measures_substantially_above_zero(self):
        elements = detect_elements(self.frame_path)
        for detected, truth in zip(elements, self.ground_truth):
            if truth["corner_radius"] >= 20:
                measured = _measure_corner_radius(self.frame_path, detected["bbox"])
                self.assertGreater(measured, 10, "a large radius should measure substantially above zero")


class TestSpacingDetection(unittest.TestCase):
    def test_analyze_frame_returns_list_without_error(self):
        tmpdir = tempfile.mkdtemp()
        frame_path = os.path.join(tmpdir, "test_frame.png")
        generate_frame(frame_path, n_elements=5, violation_rate=0.4)
        violations = analyze_frame(frame_path)
        self.assertIsInstance(violations, list)

    def test_every_violation_has_required_fields(self):
        tmpdir = tempfile.mkdtemp()
        frame_path = os.path.join(tmpdir, "test_frame.png")
        generate_frame(frame_path, n_elements=6, violation_rate=0.5)
        violations = analyze_frame(frame_path)
        for v in violations:
            self.assertIn("violation_type", v)
            self.assertIn("deviation", v)
            self.assertTrue(0.0 <= v["deviation"] <= 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
