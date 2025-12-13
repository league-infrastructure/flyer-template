import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import yaml

from flyte.template_analyzer import analyze_template


class TestTemplateAnalyzer(unittest.TestCase):
    def test_detects_regions_and_writes_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = tmp / "input.png"
            out = tmp / "out"
            out.mkdir(parents=True, exist_ok=True)

            # white background
            img = np.full((200, 200, 3), 255, dtype=np.uint8)

            # two green regions (#6fe600) in BGR
            green_bgr = (0x00, 0xE6, 0x6F)
            cv2.rectangle(img, (10, 10), (59, 49), green_bgr, thickness=-1)
            cv2.rectangle(img, (100, 120), (179, 169), green_bgr, thickness=-1)

            cv2.imwrite(str(src), img)

            result = analyze_template(src, out)
            regions_path = Path(result["regions"])
            self.assertTrue(regions_path.exists())

            data = yaml.safe_load(regions_path.read_text(encoding="utf-8"))
            self.assertEqual(data["source"], "input.png")
            self.assertEqual(data["content_color"], "#6fe600")
            self.assertEqual(len(data["regions"]), 2)

            r1, r2 = data["regions"]
            self.assertEqual(r1["id"], 1)
            self.assertEqual(r2["id"], 2)

            # Sorted top-to-bottom then left-to-right
            self.assertEqual((r1["x"], r1["y"], r1["width"], r1["height"]), (10, 10, 50, 40))
            self.assertEqual((r2["x"], r2["y"], r2["width"], r2["height"]), (100, 120, 80, 50))

            self.assertEqual(r1["background_color"], "#ffffff")
            self.assertEqual(r2["background_color"], "#ffffff")

            template_img = cv2.imread(str(Path(result["template"])), cv2.IMREAD_COLOR)
            self.assertIsNotNone(template_img)

            # Pixels well inside regions should now match background (white)
            self.assertTrue((template_img[20, 20] == np.array([255, 255, 255])).all())
            self.assertTrue((template_img[140, 140] == np.array([255, 255, 255])).all())


if __name__ == "__main__":
    unittest.main()
