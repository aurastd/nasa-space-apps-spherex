import unittest

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord

from utils import spherex_data as sx


class ImageCandidateTests(unittest.TestCase):
    def setUp(self):
        center = SkyCoord(150 * u.deg, 2 * u.deg)
        self.target = sx.Target(center.ra.deg, center.dec.deg, epoch=sx.T_REF)
        self.grid, self.shape, _ = sx.make_grid(center, 8.0)
        self.center_x, self.center_y = np.round(self.grid.world_to_pixel(center)).astype(int)

    def _frame_with_peak(self, x, y):
        rng = np.random.default_rng(42)
        image = rng.normal(0, 1, self.shape).astype(np.float32)
        image[y, x] += 12
        return sx.Frame(60000.0, 1, 1.0, image)

    def test_detects_nearby_peak_and_returns_sky_position(self):
        x, y = self.center_x + 3, self.center_y + 4
        frame = self._frame_with_peak(x, y)

        candidates = sx.image_candidates([frame], self.grid, self.target)

        self.assertTrue(candidates)
        expected = self.grid.pixel_to_world(x, y)
        self.assertAlmostEqual(candidates[0]["ra"], expected.ra.deg, places=7)
        self.assertAlmostEqual(candidates[0]["dec"], expected.dec.deg, places=7)
        self.assertGreaterEqual(candidates[0]["snr"], 5.0)

    def test_ignores_peaks_outside_search_radius(self):
        frame = self._frame_with_peak(self.center_x + 35, self.center_y)

        candidates = sx.image_candidates([frame], self.grid, self.target, radius_arcmin=0.5)

        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
